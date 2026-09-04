"""Hierarchical Multi-Agent Supervisor / Worker Architecture for SOC Tier 1 Operations.

Implements Approach 3:
- SOCRunbookWorkerAgent: Specialized epistemic investigation agent grounded in translated runbooks.
- SOCSupervisorAgent (HierarchicalSOCTier1Agent): Classification, worker dispatch, synthesis, and containment.
"""

from copy import deepcopy
from dataclasses import asdict, dataclass, field
import inspect
import json
import os
from pathlib import Path
import re
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_RUNBOOKS_DIR = ROOT_DIR / "third_party" / "ai-runbooks" / ".clinerules" / "run_books"

try:
    from agent.gemma_agent import GemmaAgent
    from agent.soc_tier1_agent import (
        LOCAL_CANONICAL_MAP,
        SOC_TIER1_PERSONA,
        SocDecision,
        SocTier1Agent,
        _dict_to_action,
        _extract_json_dicts,
        _normalize_verdict,
        extract_soc_decision,
        is_epistemic_tool,
        is_pragmatic_action,
    )
    from agent.soc_tools import (
        get_domain_report,
        get_file_report,
        get_ip_address_report,
        list_cases,
        lookup_entity,
    )
except ModuleNotFoundError:
    from gemma_agent import GemmaAgent
    from soc_tier1_agent import (
        LOCAL_CANONICAL_MAP,
        SOC_TIER1_PERSONA,
        SocDecision,
        SocTier1Agent,
        _dict_to_action,
        _extract_json_dicts,
        _normalize_verdict,
        extract_soc_decision,
        is_epistemic_tool,
        is_pragmatic_action,
    )
    from soc_tools import (
        get_domain_report,
        get_file_report,
        get_ip_address_report,
        list_cases,
        lookup_entity,
    )


CLASSIFICATION_RUNBOOK_MAP: Dict[str, str] = {
    "MALWARE_HASH": "malware_triage.md",
    "C2_BEACON": "basic_ioc_enrichment.md",
    "PHISHING_DOMAIN": "basic_ioc_enrichment.md",
    "SUSPICIOUS_LOGIN": "suspicious_login_triage.md",
    "LATERAL_MOVEMENT": "lateral_movement_hunt_psexec_wmi.md",
}

DEFAULT_FALLBACK_RUNBOOK: str = "basic_ioc_enrichment.md"


@dataclass
class WorkerInvestigationReport:
    """Structured report produced by SOCRunbookWorkerAgent after epistemic investigation."""

    classification: str
    runbook_name: str
    target_entities: List[str] = field(default_factory=list)
    findings: Dict[str, Any] = field(default_factory=dict)
    evidence: List[str] = field(default_factory=list)
    risk_level: str = "UNKNOWN"  # BENIGN, SUSPICIOUS, MALICIOUS, UNKNOWN
    recommended_escalation: Optional[str] = None
    raw_response: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serializes investigation report to dictionary."""
        return asdict(self)

    def __getitem__(self, key: str) -> Any:
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key)


class SOCTier1Response(dict):
    """Standard response object matching SOCTier1Agent.query output.

    Inherits from dict for backwards compatibility with dictionary indexing and
    serialization, while offering typed properties for multi-agent metadata.
    """

    def __init__(
        self,
        response: str,
        trajectory: Optional[List[Dict[str, Any]]] = None,
        usage: Optional[Dict[str, int]] = None,
        backend: str = "Unknown",
        endpoint_id: Optional[str] = None,
        classification: Optional[str] = None,
        runbook: Optional[str] = None,
        worker_report: Optional[Union[WorkerInvestigationReport, Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> None:
        traj = trajectory or []
        usg = usage or {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        serialized_worker_report: Optional[Dict[str, Any]] = None
        if isinstance(worker_report, WorkerInvestigationReport):
            serialized_worker_report = worker_report.to_dict()
        elif isinstance(worker_report, dict):
            serialized_worker_report = worker_report

        super().__init__(
            response=response,
            trajectory=traj,
            usage=usg,
            backend=backend,
            endpoint_id=endpoint_id,
            classification=classification,
            runbook=runbook,
            worker_report=serialized_worker_report,
            **kwargs,
        )

    @property
    def response(self) -> str:
        return self["response"]

    @property
    def trajectory(self) -> List[Dict[str, Any]]:
        return self["trajectory"]

    @property
    def usage(self) -> Dict[str, int]:
        return self["usage"]

    @property
    def backend(self) -> str:
        return self["backend"]

    @property
    def endpoint_id(self) -> Optional[str]:
        return self["endpoint_id"]

    @property
    def classification(self) -> Optional[str]:
        return self.get("classification")

    @property
    def runbook(self) -> Optional[str]:
        return self.get("runbook")

    @property
    def worker_report(self) -> Optional[Dict[str, Any]]:
        return self.get("worker_report")

    def to_dict(self) -> Dict[str, Any]:
        return dict(self)


def load_runbook(runbook_name: str, runbooks_dir: Optional[Path] = None) -> str:
    """Loads markdown content for a given runbook from the repository submodule."""
    base_dir = runbooks_dir or DEFAULT_RUNBOOKS_DIR
    target_path = base_dir / runbook_name
    if target_path.exists():
        return target_path.read_text(encoding="utf-8")

    # Check fallback directory under ROOT_DIR if runbooks_dir is custom
    fallback_path = DEFAULT_RUNBOOKS_DIR / runbook_name
    if fallback_path.exists():
        return fallback_path.read_text(encoding="utf-8")

    # Safe built-in operational runbook text if submodule is missing
    return (
        f"# Fallback Runbook: {runbook_name}\n\n"
        "## Investigation Steps\n"
        "1. Identify primary technical indicators (IPs, domains, hashes, hostnames).\n"
        "2. Query available threat intelligence and telemetry tools.\n"
        "3. Correlate observations with known threat families and adversary infrastructure.\n"
        "4. Document factual observations and assess threat severity (BENIGN, SUSPICIOUS, MALICIOUS).\n"
    )


def get_generic_worker_instruction(classification: str) -> str:
    """Generates generic investigation system instructions without procedural runbook steps."""
    return (
        f"You are the SOC Worker Agent specializing in {classification} alert investigation.\n"
        "Your mission is strictly epistemic investigation and evidence collection using available tools.\n\n"
        "OPERATIONAL RULES:\n"
        "1. Epistemic Investigation Only: Invoke tools (e.g. get_ip_address_report, get_domain_report, "
        "get_file_report, lookup_entity, list_cases) to gather telemetry, reputation, and case history. "
        "Do NOT execute containment actions (e.g. isolate_host, block_indicator, close_case). "
        "Containment decisions are strictly reserved for the SOC Supervisor Agent.\n"
        "2. Grounded Observations: You must invoke at least one investigation tool to gather verified telemetry "
        "before concluding your investigation.\n"
        "3. Structured Worker Report: Once investigation is complete, output a structured summary including "
        "[Context & Enrichment], [Findings & Evidence], [Preliminary Risk Assessment], and conclude with a ```worker_report JSON block.\n\n"
        "### Investigation Objective:\n"
        "Investigate the technical indicators (IPs, domains, hashes, hostnames, users) referenced in the alert. "
        "Query available tools to collect verified telemetry and report your findings.\n"
    )


def translate_runbook_to_system_instruction(runbook_content: str, classification: str) -> str:
    """Translates a raw runbook markdown into executable system instructions for the worker agent."""
    if not runbook_content or runbook_content.strip() == "":
        return get_generic_worker_instruction(classification)

    # Normalize tool identifiers from third-party runbook syntax to local tool function names
    translated = runbook_content
    replacements = [
        ("gti-mcp.get_file_report", "get_file_report"),
        ("gti-mcp.get_ip_address_report", "get_ip_address_report"),
        ("gti-mcp.get_domain_report", "get_domain_report"),
        ("secops-mcp.lookup_entity", "lookup_entity"),
        ("secops-soar.list_cases", "list_cases"),
        ("gti-mcp: get_file_report", "Available tool: get_file_report"),
        ("gti-mcp: get_ip_address_report", "Available tool: get_ip_address_report"),
        ("gti-mcp: get_domain_report", "Available tool: get_domain_report"),
        ("secops-mcp: lookup_entity", "Available tool: lookup_entity"),
        ("secops-soar: list_cases", "Available tool: list_cases"),
    ]
    for old_syntax, new_syntax in replacements:
        translated = translated.replace(old_syntax, new_syntax)

    persona = (
        f"You are the SOC Runbook Worker Agent specializing in {classification} alert triage.\n"
        "Your mission is strictly epistemic investigation and evidence collection following the runbook below.\n\n"
        "OPERATIONAL RULES:\n"
        "1. Epistemic Investigation Only: Invoke tools to gather telemetry, reputation, and case history. "
        "Do NOT execute containment actions (e.g. isolate_host, block_indicator, close_case). "
        "Containment decisions are strictly reserved for the SOC Supervisor Agent.\n"
        "2. Grounded Observations: You must invoke at least one investigation tool to gather verified telemetry "
        "before concluding your investigation.\n"
        "3. Structured Worker Report: Once investigation is complete, output a structured summary including "
        "[Context & Enrichment], [Findings & Evidence], [Preliminary Risk Assessment], and conclude with a ```worker_report JSON block.\n\n"
        f"### Active Investigation Runbook ({classification}):\n"
        f"{translated}\n"
    )
    return persona


def extract_worker_report(
    response_text: str,
    classification: str,
    runbook_name: str,
    trajectory: List[Dict[str, Any]],
) -> WorkerInvestigationReport:
    """Extracts structured WorkerInvestigationReport from worker LLM response and trajectory."""
    # 1. Look for fenced worker_report or json block
    report_patterns = [
        r"```worker_report\s*(\{.*?\})\s*```",
        r"```(?:json)?\s*(\{\s*\"classification\".*?\})\s*```",
    ]
    for pattern in report_patterns:
        match = re.search(pattern, response_text, re.DOTALL | re.IGNORECASE)
        if match:
            try:
                data = json.loads(match.group(1))
                if isinstance(data, dict):
                    raw_risk = str(data.get("risk_level") or data.get("verdict") or "UNKNOWN").upper()
                    risk_level = _normalize_verdict(raw_risk) if raw_risk != "UNKNOWN" else "UNKNOWN"
                    raw_entities = data.get("target_entities") or []
                    if isinstance(raw_entities, str):
                        raw_entities = [raw_entities]
                    findings = data.get("findings") if isinstance(data.get("findings"), dict) else {}
                    evidence = data.get("evidence") if isinstance(data.get("evidence"), list) else []
                    return WorkerInvestigationReport(
                        classification=str(data.get("classification") or classification),
                        runbook_name=runbook_name,
                        target_entities=[str(e) for e in raw_entities],
                        findings=findings,
                        evidence=[str(ev) for ev in evidence],
                        risk_level=risk_level,
                        recommended_escalation=data.get("recommended_escalation"),
                        raw_response=response_text,
                    )
            except Exception:
                pass

    # 2. Heuristic extraction from trajectory and text
    target_entities: List[str] = []
    findings: Dict[str, Any] = {}
    evidence: List[str] = []

    for step in trajectory:
        tool = str(step.get("tool") or "")
        args = step.get("args") or {}
        obs = str(step.get("observation") or "")

        for k, v in args.items():
            val_str = str(v).strip()
            if val_str and val_str not in target_entities:
                target_entities.append(val_str)

        call_repr = f"{tool}({json.dumps(args, sort_keys=True)})"
        findings[call_repr] = obs[:300]
        if "reputation" in obs or "verdict" in obs or "threat_category" in obs or "isolated" in obs:
            evidence.append(f"{tool}: {obs[:200]}")

    # Risk level determination from response text or observations
    risk_level = "UNKNOWN"
    verdict_match = re.search(
        r"(?:Preliminary Risk Assessment|Risk Level|Threat Assessment|Verdict):\s*([^\n\r]+)",
        response_text,
        re.IGNORECASE,
    )
    if verdict_match:
        risk_level = _normalize_verdict(verdict_match.group(1))
    else:
        # Fallback to trajectory observations
        all_obs_text = " ".join(str(s.get("observation") or "") for s in trajectory).upper()
        if any(term in all_obs_text for term in ("MALICIOUS", "C2_SERVER", "TROJAN", "LOKIBOT", "PSEXEC")):
            risk_level = "MALICIOUS"
        elif any(term in all_obs_text for term in ("BENIGN", "SAFE", "RFC-5737", "AUTHORIZED SCANNER")):
            risk_level = "BENIGN"
        elif "SUSPICIOUS" in all_obs_text:
            risk_level = "SUSPICIOUS"

    return WorkerInvestigationReport(
        classification=classification,
        runbook_name=runbook_name,
        target_entities=target_entities,
        findings=findings,
        evidence=evidence,
        risk_level=risk_level,
        recommended_escalation="Tier 2 Responder" if risk_level == "MALICIOUS" else None,
        raw_response=response_text,
    )


class SOCRunbookWorkerAgent(SocTier1Agent):
    """Specialized SOC Sub-Agent that executes a selected runbook for epistemic investigation."""

    def __init__(
        self,
        classification: str,
        runbook_name: str,
        runbook_content: str,
        project_id: Optional[str] = None,
        region: str = "us-central1",
        endpoint_id: Optional[str] = None,
        cloudrun_url: Optional[str] = None,
        managed_model: Optional[str] = None,
        use_live_mcp: bool = False,
        environment: Optional[Any] = None,
    ):
        system_instruction = translate_runbook_to_system_instruction(runbook_content, classification)
        super().__init__(
            project_id=project_id,
            region=region,
            endpoint_id=endpoint_id,
            cloudrun_url=cloudrun_url,
            managed_model=managed_model,
            use_live_mcp=use_live_mcp,
            environment=environment,
        )
        self.classification = classification
        self.runbook_name = runbook_name
        self.system_instruction = system_instruction
        self.name = f"soc_runbook_worker_{classification.lower()}"

        # Restrict worker strictly to epistemic investigation tools
        if use_live_mcp:
            from agent.secops_mcp_tools import (
                fetch_alert_data,
                get_case,
                list_cases as mcp_list_cases,
                summarize_entity,
                udm_search,
            )
            worker_tools: List[Callable] = [
                mcp_list_cases,
                get_case,
                summarize_entity,
                udm_search,
                fetch_alert_data,
            ]
        else:
            worker_tools: List[Callable] = [
                lookup_entity,
                get_ip_address_report,
                get_domain_report,
                get_file_report,
                list_cases,
            ]
        self.tools = worker_tools
        self.tools_dict = {tool.__name__: tool for tool in worker_tools}

    def investigate(
        self,
        prompt: str,
        max_iterations: int = 5,
        max_tokens: Optional[int] = None,
        temperature: float = 0.2,
    ) -> Tuple[WorkerInvestigationReport, List[Dict[str, Any]], Dict[str, int]]:
        """Executes epistemic investigation loop guided by the translated runbook."""
        tools_doc = self._build_tools_description()
        react_instructions = (
            f"{self.system_instruction}\n\n"
            f"Available Investigation Tools:\n{tools_doc}\n\n"
            "Interaction Protocol (ReAct):\n"
            "To gather information, output Thought and Action using one of the following formats:\n"
            "Format 1 (Standard ReAct): Action: <tool_name>(<arg_name>=\"<value>\")\n"
            "Format 2 (JSON Action): Action: {\"name\": \"<tool_name>\", \"arguments\": {\"<arg_name>\": \"<value>\"}}\n"
            "Format 3 (Fenced Block): ```tool_call\n{\"name\": \"<tool_name>\", \"args\": {\"<arg_name>\": \"<value>\"}}\n```\n\n"
            "When you receive the Observation, analyze it. You must invoke at least one investigation tool before concluding.\n"
            "When you have gathered sufficient evidence to fulfill the runbook, conclude with:\n"
            "Final Answer:\n"
            "[Context & Enrichment]\n<entities and observations>\n\n"
            "[Findings & Evidence]\n<correlated technical evidence>\n\n"
            "[Preliminary Risk Assessment]\n<BENIGN, SUSPICIOUS, or MALICIOUS>\n\n"
            "```worker_report\n"
            "{\n"
            f'  "classification": "{self.classification}",\n'
            '  "target_entities": ["<entity1>", ...],\n'
            '  "findings": {"<entity>": "<summary>"},\n'
            '  "evidence": ["<evidence1>", ...],\n'
            '  "risk_level": "<BENIGN|SUSPICIOUS|MALICIOUS>"\n'
            "}\n"
            "```\n"
        )

        current_prompt = f"{react_instructions}\n\nAlert To Investigate:\n{prompt}\n"
        trajectory: List[Dict[str, Any]] = []
        final_answer = ""
        total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        for iteration in range(max_iterations):
            step_output, step_usage = self._call_llm_step(current_prompt, max_tokens=max_tokens, temperature=temperature)
            total_usage["prompt_tokens"] += step_usage.get("prompt_tokens", 0)
            total_usage["completion_tokens"] += step_usage.get("completion_tokens", 0)
            total_usage["total_tokens"] += step_usage.get("total_tokens", 0)

            if not step_output:
                break

            # 1. Parse and execute tool invocation
            parsed = self._parse_action(step_output)
            if parsed:
                tool_name, tool_args = parsed
                observation = self._execute_tool_action(tool_name, tool_args)
                trajectory.append({
                    "iteration": iteration + 1,
                    "tool": tool_name,
                    "args": tool_args,
                    "observation": observation,
                    "agent": "worker",
                })
                current_prompt += f"{step_output}\nObservation: {observation}\n"
                continue

            # 2. Enforce epistemic investigation on premature completion in step 0
            if iteration == 0 and iteration < max_iterations - 1:
                is_premature = (
                    "Final Answer:" in step_output
                    or "[Findings & Evidence]" in step_output
                    or "```worker_report" in step_output
                )
                if is_premature:
                    reflection = (
                        "Observation: Investigation incomplete. You have not called any investigation tools "
                        "(e.g. get_ip_address_report, get_domain_report, get_file_report, lookup_entity, list_cases). "
                        "You must invoke an investigation tool to gather verified telemetry before issuing findings."
                    )
                    current_prompt += f"{step_output}\n{reflection}\n"
                    continue

            # 3. Explicit Final Answer
            if "Final Answer:" in step_output:
                final_answer = step_output.split("Final Answer:", 1)[1].strip()
                break

            # Direct report output without explicit Final Answer tag
            if "[Context & Enrichment]" in step_output and "[Findings & Evidence]" in step_output:
                final_answer = step_output.strip()
                break

            final_answer = step_output.strip()
            break

        if not final_answer:
            final_answer = "Investigation iterations completed."

        report = extract_worker_report(final_answer, self.classification, self.runbook_name, trajectory)
        return report, trajectory, total_usage


class SOCSupervisorAgent(GemmaAgent):
    """Hierarchical SOC Supervisor Agent (Approach 3).

    Orchestrates alert triage by:
    1. Classifying alerts into operational runbook domains.
    2. Dispatching specialized SOCRunbookWorkerAgent with translated runbooks.
    3. Receiving worker findings and synthesizing final threat verdicts.
    4. Formulating and executing containment actions in the environment.
    5. Maintaining a unified trajectory of epistemic and pragmatic steps.
    """

    def __init__(
        self,
        project_id: Optional[str] = None,
        region: str = "us-central1",
        endpoint_id: Optional[str] = None,
        cloudrun_url: Optional[str] = None,
        managed_model: Optional[str] = None,
        use_live_mcp: bool = False,
        environment: Optional[Any] = None,
        runbooks_dir: Optional[Path] = None,
        use_runbooks: bool = True,
    ):
        super().__init__(
            project_id=project_id,
            region=region,
            endpoint_id=endpoint_id,
            cloudrun_url=cloudrun_url,
            managed_model=managed_model,
            system_instruction=SOC_TIER1_PERSONA,
            tools=[],
        )
        self.use_live_mcp = use_live_mcp
        self.environment = environment
        self.runbooks_dir = runbooks_dir or DEFAULT_RUNBOOKS_DIR
        self.use_runbooks = use_runbooks
        self.name = "hierarchical_soc_supervisor"
        self.last_backend: str = "Unknown"

    def classify_alert(self, prompt: str) -> str:
        """Classifies the alert prompt into a primary operational runbook category.

        Categories:
        - MALWARE_HASH: File hash, binary anomaly, ransomware, trojan, suspicious executable.
        - LATERAL_MOVEMENT: PsExec, WMI abuse, SMB session, remote process launch.
        - SUSPICIOUS_LOGIN: Authentication anomaly, impossible travel, failed logins, scanner noise.
        - PHISHING_DOMAIN: Phishing URLs, lookalike domains, credential harvesting.
        - C2_BEACON: Command and control, beaconing, malicious IP traffic, DNS tunneling.
        """
        p_lower = prompt.lower()

        # 1. Lateral Movement indicators
        lateral_keywords = [
            "psexec", "wmi", "wmic", "lateral movement", "smb session",
            "remote execution", "pass-the-hash", "type 3 logon", "admin$",
            "remote process", "serviceinstalled",
        ]
        if any(k in p_lower for k in lateral_keywords):
            return "LATERAL_MOVEMENT"

        # 2. File Hash / Malware indicators
        hash_regex = r"\b[a-fA-F0-9]{32}\b|\b[a-fA-F0-9]{40}\b|\b[a-fA-F0-9]{64}\b"
        malware_keywords = [
            "sha256", "md5", "sha1", "ransomware", "trojan", "malware",
            "binary", "mimikatz", "payload", "quarantine file",
            "revoked certificate", "unsigned binary", "malicious file",
        ]
        has_hash = bool(re.search(hash_regex, prompt))
        if has_hash or any(k in p_lower for k in malware_keywords):
            # Check if domain/IP beaconing is the primary alert subject
            is_beacon_subject = (
                "connecting repeatedly to" in p_lower
                or ("beacon" in p_lower and "domain" in p_lower)
            )
            if not is_beacon_subject or has_hash or "ransomware" in p_lower or "certificate" in p_lower:
                return "MALWARE_HASH"

        # 3. Suspicious Login / Authentication indicators
        login_keywords = [
            "suspicious login", "impossible travel", "failed login", "untrusted location",
            "logon", "brute force", "authentication log", "auth attempt", "vpn authentication",
            "scanner noise", "authorized scanner", "qualys",
        ]
        if any(k in p_lower for k in login_keywords):
            return "SUSPICIOUS_LOGIN"

        # 4. Phishing Domain indicators
        phish_keywords = [
            "phishing", "typosquat", "credential harvest", "lookalike domain",
            "phish", "fake login page", "harvesting",
        ]
        if any(k in p_lower for k in phish_keywords):
            return "PHISHING_DOMAIN"

        # 5. C2 Beaconing / Network Indicator indicators
        c2_keywords = [
            "c2", "beacon", "beaconing", "command and control", "command & control",
            "dns tunnel", "tunneling", "outbound", "connecting repeatedly",
            "network connection", "ip address", "ip ",
        ]
        if any(k in p_lower for k in c2_keywords):
            return "C2_BEACON"

        # Structural fallback based on entity syntax
        if re.search(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", prompt):
            return "C2_BEACON"
        if re.search(r"\b[a-zA-Z0-9_\-]+\.(?:com|org|net|io|co|info|biz|xyz|site)\b", prompt):
            return "PHISHING_DOMAIN"

        return "C2_BEACON"

    def get_runbook_for_classification(self, classification: str) -> str:
        """Resolves classification category to runbook filename."""
        return CLASSIFICATION_RUNBOOK_MAP.get(classification, DEFAULT_FALLBACK_RUNBOOK)

    def _call_llm_step(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: float = 0.2,
    ) -> Tuple[str, Dict[str, int]]:
        """Invokes LLM backend for supervisor reasoning step."""
        res = super().query(prompt=prompt, max_tokens=max_tokens, temperature=temperature)
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        if isinstance(res, dict):
            self.last_backend = res.get("backend", "Unknown")
            usage = res.get("usage", usage)
            return res.get("response", ""), usage
        return str(res), usage

    def _synthesize_verdict_and_containment(
        self,
        prompt: str,
        classification: str,
        runbook_name: str,
        worker_report: WorkerInvestigationReport,
        max_tokens: Optional[int] = None,
        temperature: float = 0.2,
    ) -> Tuple[str, SocDecision, Dict[str, int]]:
        """Synthesizes worker investigation findings into final triage report and containment decision."""
        supervisor_instruction = (
            f"{SOC_TIER1_PERSONA}\n\n"
            "You are the Lead SOC Supervisor Agent conducting final synthesis and containment decision.\n\n"
            f"Original Alert:\n{prompt}\n\n"
            f"Alert Classification: {classification}\n"
            f"{f'Runbook Executed: {runbook_name}' if runbook_name != 'none' else 'Mode: Generic Multi-Agent Investigation (No Procedural Runbook)'}\n\n"
            "Worker Investigation Telemetry:\n"
            f"- Target Entities: {worker_report.target_entities}\n"
            f"- Preliminary Risk: {worker_report.risk_level}\n"
            f"- Evidence Observations: {worker_report.evidence}\n"
            f"- Worker Findings: {json.dumps(worker_report.findings, indent=2)}\n"
            f"- Worker Summary:\n{worker_report.raw_response}\n\n"
            "Supervisor Mission:\n"
            "1. Synthesize the findings into an authoritative threat assessment (BENIGN, SUSPICIOUS, or MALICIOUS).\n"
            "2. Determine containment actions:\n"
            "   - For MALICIOUS / active threat: recommend isolate_host, block_indicator, update_case_comment. Avoid close_case.\n"
            "   - For BENIGN / false positive: recommend close_case, update_case_comment. Avoid isolate_host and block_indicator.\n"
            "   - For SUSPICIOUS / ambiguous: recommend update_case_comment, block_indicator if indicated, escalate to Tier 2.\n"
            "3. Structure your response into the standard four sections followed by the ```soc_decision block:\n"
            "[Context & Enrichment]\n"
            "<entities and enrichment findings>\n\n"
            "[Analysis & Verdict]\n"
            "<threat assessment and verdict: BENIGN, SUSPICIOUS, or MALICIOUS>\n\n"
            "[Action & Escalation]\n"
            "<containment decisions and mitigation plan>\n\n"
            "[SOAR Documentation]\n"
            "<markdown case log comment>\n\n"
            "```soc_decision\n"
            "{\n"
            '  "verdict": "<BENIGN|SUSPICIOUS|MALICIOUS>",\n'
            '  "recommended_actions": ["<action1>", ...],\n'
            '  "target_entity": "<primary entity>",\n'
            '  "rationale": "<summary explanation>"\n'
            "}\n"
            "```\n"
        )

        step_output, usage = self._call_llm_step(supervisor_instruction, max_tokens=max_tokens, temperature=temperature)
        decision = extract_soc_decision(step_output)

        # Fallback decision construction if LLM omitted structured decision
        if decision is None:
            raw_risk = worker_report.risk_level.upper()
            verdict = _normalize_verdict(raw_risk) if raw_risk != "UNKNOWN" else "INCONCLUSIVE"
            target_entity = worker_report.target_entities[0] if worker_report.target_entities else None

            if verdict == "MALICIOUS":
                recommended_actions = ["isolate_host", "block_indicator", "update_case_comment"]
                prohibited_avoided = ["close_case"]
                rationale = "Confirmed active adversary threat during runbook investigation."
            elif verdict == "BENIGN":
                recommended_actions = ["close_case", "update_case_comment"]
                prohibited_avoided = ["isolate_host", "block_indicator"]
                rationale = "Verified benign activity or authorized scanner noise."
            else:
                recommended_actions = ["update_case_comment"]
                prohibited_avoided = []
                rationale = "Investigation inconclusive or requires Tier 2 escalation."

            decision = SocDecision(
                verdict=verdict,
                recommended_actions=recommended_actions,
                target_entity=target_entity,
                rationale=rationale,
                prohibited_actions_avoided=prohibited_avoided,
            )

        # Ensure response text contains standard sections and decision block
        final_text = step_output.strip()
        if not ("[Context & Enrichment]" in final_text and "[Analysis & Verdict]" in final_text):
            entities_str = ", ".join(worker_report.target_entities) if worker_report.target_entities else "None"
            evidence_str = "\n".join(f"- {e}" for e in worker_report.evidence) if worker_report.evidence else "- Investigated indicators."
            actions_str = ", ".join(decision.recommended_actions) if decision.recommended_actions else "update_case_comment"
            runbook_display = runbook_name if runbook_name != "none" else "None (Generic Investigation)"
            triage_doc_str = f"under {runbook_name}" if runbook_name != "none" else "via generic multi-agent investigation"
            final_text = (
                "[Context & Enrichment]\n"
                f"- Classification: {classification}\n"
                f"- Runbook: {runbook_display}\n"
                f"- Entities: {entities_str}\n"
                f"{evidence_str}\n\n"
                "[Analysis & Verdict]\n"
                f"- Threat Assessment: {decision.verdict}\n"
                f"- Correlation: {decision.rationale or 'Telemetry analyzed across investigation steps.'}\n\n"
                "[Action & Escalation]\n"
                f"- Recommended Actions: {actions_str}\n"
                f"- Escalation: {'Tier 2 Incident Response' if decision.verdict == 'MALICIOUS' else 'Resolved'}\n\n"
                "[SOAR Documentation]\n"
                f"Triage completed {triage_doc_str}. Verdict: {decision.verdict}. Actions: {actions_str}.\n\n"
                "```soc_decision\n"
                f"{json.dumps(decision.to_dict(), indent=2)}\n"
                "```\n"
            )
        elif "```soc_decision" not in final_text:
            final_text += f"\n\n```soc_decision\n{json.dumps(decision.to_dict(), indent=2)}\n```\n"

        return final_text, decision, usage

    def _execute_containment_decisions(
        self,
        decision: SocDecision,
        worker_report: WorkerInvestigationReport,
        prompt: str,
    ) -> List[Dict[str, Any]]:
        """Executes containment actions against SocEnvironment or records them for trajectory verifier."""
        executed_steps: List[Dict[str, Any]] = []
        seen_actions: Set[str] = set()

        for action in decision.recommended_actions:
            canonical_act = LOCAL_CANONICAL_MAP.get(action, action)
            if canonical_act in seen_actions:
                continue
            seen_actions.add(canonical_act)

            # 1. Isolate Host
            if canonical_act == "isolate_host":
                target_host = self._resolve_target_host(decision, worker_report, prompt)
                if target_host:
                    args = {"hostname": target_host}
                    if self.environment is not None:
                        obs = self.environment.execute_action("isolate_host", args)
                    else:
                        obs = {"status": "SUCCESS", "action": "isolate_host", "hostname": target_host, "message": f"Host '{target_host}' isolated."}
                    executed_steps.append({
                        "tool": "isolate_host",
                        "args": args,
                        "observation": json.dumps(obs) if isinstance(obs, dict) else str(obs),
                        "agent": "supervisor",
                    })

            # 2. Block Indicator
            elif canonical_act == "block_indicator":
                target_indicator = self._resolve_target_indicator(decision, worker_report, prompt)
                if target_indicator:
                    args = {"indicator": target_indicator}
                    if self.environment is not None:
                        obs = self.environment.execute_action("block_indicator", args)
                    else:
                        obs = {"status": "SUCCESS", "action": "block_indicator", "indicator": target_indicator, "message": f"Indicator '{target_indicator}' blocked."}
                    executed_steps.append({
                        "tool": "block_indicator",
                        "args": args,
                        "observation": json.dumps(obs) if isinstance(obs, dict) else str(obs),
                        "agent": "supervisor",
                    })

            # 3. Close Case
            elif canonical_act == "close_case":
                target_case = self._resolve_target_case(prompt)
                args = {"case_id": target_case, "verdict": decision.verdict}
                if self.environment is not None:
                    obs = self.environment.execute_action("close_case", args)
                else:
                    obs = {"status": "SUCCESS", "action": "close_case", "case_id": target_case, "message": f"Case '{target_case}' closed."}
                executed_steps.append({
                    "tool": "close_case",
                    "args": args,
                    "observation": json.dumps(obs) if isinstance(obs, dict) else str(obs),
                    "agent": "supervisor",
                })

            # 4. Update Case Comment
            elif canonical_act == "update_case_comment":
                target_case = self._resolve_target_case(prompt)
                comment_text = decision.rationale or f"Runbook investigation complete. Verdict: {decision.verdict}."
                args = {"case_id": target_case, "comment": comment_text}
                if self.environment is not None:
                    obs = self.environment.execute_action("update_case_comment", args)
                else:
                    obs = {"status": "SUCCESS", "action": "update_case_comment", "case_id": target_case, "message": "Case comment posted."}
                executed_steps.append({
                    "tool": "update_case_comment",
                    "args": args,
                    "observation": json.dumps(obs) if isinstance(obs, dict) else str(obs),
                    "agent": "supervisor",
                })

            # 5. Unblock Host
            elif canonical_act == "unblock_host":
                target_host = self._resolve_target_host(decision, worker_report, prompt)
                if target_host:
                    args = {"hostname": target_host}
                    if self.environment is not None:
                        obs = self.environment.execute_action("unblock_host", args)
                    else:
                        obs = {"status": "SUCCESS", "action": "unblock_host", "hostname": target_host, "message": f"Host '{target_host}' unblocked."}
                    executed_steps.append({
                        "tool": "unblock_host",
                        "args": args,
                        "observation": json.dumps(obs) if isinstance(obs, dict) else str(obs),
                        "agent": "supervisor",
                    })

        return executed_steps

    def _resolve_target_host(
        self,
        decision: SocDecision,
        worker_report: WorkerInvestigationReport,
        prompt: str,
    ) -> Optional[str]:
        """Resolves target hostname from decision, worker report entities, or alert prompt."""
        known_hosts = set()
        if self.environment is not None and hasattr(self.environment, "hosts"):
            known_hosts = set(self.environment.hosts.keys())

        # Check target_entity from decision
        if decision.target_entity:
            ent = str(decision.target_entity).strip()
            if ent in known_hosts or ent.startswith("DESKTOP-") or ent.startswith("SRV-") or ent.startswith("GW-"):
                return ent

        # Check worker report target entities
        for ent in worker_report.target_entities:
            clean_ent = str(ent).strip()
            if clean_ent in known_hosts or clean_ent.startswith("DESKTOP-") or clean_ent.startswith("SRV-") or clean_ent.startswith("GW-"):
                return clean_ent

        # Regex search in prompt
        host_matches = re.findall(r"\b(DESKTOP-[A-Z0-9\-]+|SRV-[A-Z0-9\-]+|GW-[A-Z0-9\-]+)\b", prompt)
        if host_matches:
            return host_matches[0]

        if known_hosts:
            return sorted(list(known_hosts))[0]

        return None

    def _resolve_target_indicator(
        self,
        decision: SocDecision,
        worker_report: WorkerInvestigationReport,
        prompt: str,
    ) -> Optional[str]:
        """Resolves target indicator (domain, IP, or hash) from decision, worker, or prompt."""
        if decision.target_entity:
            ent = str(decision.target_entity).strip()
            if not (ent.startswith("DESKTOP-") or ent.startswith("SRV-") or ent.startswith("GW-")):
                return ent

        for ent in worker_report.target_entities:
            clean_ent = str(ent).strip()
            if not (clean_ent.startswith("DESKTOP-") or clean_ent.startswith("SRV-") or clean_ent.startswith("GW-")):
                return clean_ent

        # Regex search for domain
        domain_matches = re.findall(r"\b([a-zA-Z0-9_\-]+\.(?:com|org|net|io|co|biz|info|xyz|site))\b", prompt)
        if domain_matches:
            return domain_matches[0]

        # Regex search for IP
        ip_matches = re.findall(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b", prompt)
        if ip_matches:
            # Prefer non-RFC1918 public IP if available
            for ip in ip_matches:
                if not (ip.startswith("10.") or ip.startswith("192.168.") or ip.startswith("172.16.")):
                    return ip
            return ip_matches[0]

        # Regex search for file hash
        hash_matches = re.findall(r"\b([a-fA-F0-9]{32,64})\b", prompt)
        if hash_matches:
            return hash_matches[0]

        return None

    def _resolve_target_case(self, prompt: str) -> str:
        """Resolves target SOAR case ID from prompt or environment inventory."""
        case_match = re.search(r"\b(CASE-[A-Z0-9\-]+)\b", prompt)
        if case_match:
            return case_match.group(1)

        if self.environment is not None and hasattr(self.environment, "cases") and self.environment.cases:
            return list(self.environment.cases.keys())[0]

        return "CASE-101"

    def format_triage_prompt(self, query: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Formats an operational triage request with optional case metadata."""
        if not context:
            return query
        ctx_str = "\n".join(f"- {k}: {v}" for k, v in context.items())
        return f"Operational Triage Request:\n{query}\n\nCase Context:\n{ctx_str}\n\nPerform initial investigation and provide the triage report."

    def query(
        self,
        prompt: str,
        max_iterations: int = 5,
        max_tokens: Optional[int] = None,
        temperature: float = 0.2,
    ) -> SOCTier1Response:
        """Executes hierarchical supervisor-worker alert triage.

        1. Classifies alert prompt into operational domain.
        2. Resolves and translates corresponding runbook from submodule.
        3. Dispatches SOCRunbookWorkerAgent for epistemic investigation.
        4. Synthesizes findings into authoritative verdict and containment decision.
        5. Executes containment actions against environment.
        6. Constructs unified trajectory for evaluation verification and returns SOCTier1Response.
        """
        # 1. Alert Classification
        classification = self.classify_alert(prompt)

        # 2. Runbook Mapping & Loading
        if self.use_runbooks:
            runbook_name = self.get_runbook_for_classification(classification)
            runbook_content = load_runbook(runbook_name, self.runbooks_dir)
        else:
            runbook_name = "none"
            runbook_content = ""

        # 3. Worker Dispatch
        worker = SOCRunbookWorkerAgent(
            classification=classification,
            runbook_name=runbook_name,
            runbook_content=runbook_content,
            project_id=self.project_id,
            region=self.region,
            endpoint_id=self.endpoint_id,
            cloudrun_url=self.cloudrun_url,
            managed_model=self.managed_model,
            use_live_mcp=self.use_live_mcp,
            environment=self.environment,
        )
        # Inherit supervisor LLM caller so mocks and configurations apply uniformly
        worker._call_llm_step = self._call_llm_step

        worker_report, worker_trajectory, worker_usage = worker.investigate(
            prompt=prompt,
            max_iterations=max_iterations,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        # 4. Supervisor Synthesis
        final_response, decision, supervisor_usage = self._synthesize_verdict_and_containment(
            prompt=prompt,
            classification=classification,
            runbook_name=runbook_name,
            worker_report=worker_report,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        # 5. Execute Containment Decisions
        supervisor_steps = self._execute_containment_decisions(
            decision=decision,
            worker_report=worker_report,
            prompt=prompt,
        )

        # 6. Build Unified Trajectory
        unified_trajectory: List[Dict[str, Any]] = []
        all_steps = list(worker_trajectory) + list(supervisor_steps)
        for idx, step in enumerate(all_steps):
            unified_step = dict(step)
            unified_step["iteration"] = idx + 1
            unified_trajectory.append(unified_step)

        total_usage = {
            "prompt_tokens": worker_usage.get("prompt_tokens", 0) + supervisor_usage.get("prompt_tokens", 0),
            "completion_tokens": worker_usage.get("completion_tokens", 0) + supervisor_usage.get("completion_tokens", 0),
            "total_tokens": worker_usage.get("total_tokens", 0) + supervisor_usage.get("total_tokens", 0),
        }

        return SOCTier1Response(
            response=final_response,
            trajectory=unified_trajectory,
            usage=total_usage,
            backend=self.last_backend,
            endpoint_id=self.endpoint_id,
            classification=classification,
            runbook=runbook_name,
            worker_report=worker_report,
        )


# Exported primary aliases
HierarchicalSOCTier1Agent = SOCSupervisorAgent
SOCTier1Agent = SocTier1Agent
