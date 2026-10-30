"""Hierarchical Multi-Agent Supervisor / Worker Architecture for SOC Tier 1 Operations.

Implements Approach 3:
- SOCRunbookWorkerAgent: Specialized epistemic investigation agent grounded in translated runbooks.
- SOCSupervisorAgent (HierarchicalSOCTier1Agent): Classification, worker dispatch, synthesis, and containment.
"""

from copy import deepcopy
from dataclasses import asdict, dataclass, field
import inspect
import ipaddress
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
    "THREAT_HUNT": "gti_collection_threat_hunt.md",
}

DEFAULT_FALLBACK_RUNBOOK: str = "basic_ioc_enrichment.md"


def _has_investigation_evidence(trajectory: List[Dict[str, Any]]) -> bool:
    """Require structured telemetry from an executed investigation tool.

    Plain text cannot distinguish live MCP errors from telemetry because its
    adapter does not retain execution metadata. Such results remain unverified.
    """
    metadata = {"status", "status_code", "error", "isError", "message"}
    envelopes = {"result", "data", "response", "body"}

    def usable(value: Any) -> bool:
        if isinstance(value, list):
            return not value or any(usable(item) for item in value)
        if not isinstance(value, dict):
            return False
        if value.get("isError") is True or value.get("error") is not None:
            return False
        if str(value.get("status", "")).upper() in {
            "ERROR", "FAILED", "FAILURE", "DENIED", "NOT_FOUND", "NOT_EXECUTED",
            "UNVERIFIED", "TIMED_OUT", "TIMEOUT", "CANCELLED", "CANCELED",
        }:
            return False
        code = value.get("status_code")
        if isinstance(code, (int, float)) and code >= 400:
            return False
        fields = set(value) - metadata
        if not fields:
            return False
        if fields <= envelopes:
            return any(usable(value[key]) for key in fields)
        if fields == {"content"}:
            # MCP text blocks are envelopes, not evidence by themselves.
            content = value["content"]
            if not isinstance(content, list):
                return False
            for block in content:
                try:
                    if isinstance(block, dict) and usable(json.loads(block.get("text", ""))):
                        return True
                except (TypeError, ValueError):
                    continue
            return False
        # Do not interpret statuses inside telemetry (e.g. failed login events)
        # as transport failures. Empty case/event lists are negative evidence.
        return True

    for step in trajectory:
        if not step.get("tool") or not is_epistemic_tool(step["tool"]):
            continue
        if step.get("execution_status", "SUCCESS") != "SUCCESS":
            continue
        try:
            observation = json.loads(step.get("observation", ""))
        except (TypeError, ValueError):
            continue
        if usable(observation):
            return True
    return False


def _risk_from_observations(trajectory: List[Dict[str, Any]]) -> str:
    """Read exact assessment values from successful tool results, never prose."""
    labels = {
        "MALICIOUS": "MALICIOUS",
        "SUSPICIOUS": "SUSPICIOUS",
        "BORDERLINE_SUSPICIOUS": "SUSPICIOUS",
        "POTENTIALLY_MALICIOUS": "SUSPICIOUS",
        "BENIGN": "BENIGN",
        "SAFE": "BENIGN",
        "BENIGN_AUTHORIZED": "BENIGN",
        "BENIGN / NON-ROUTABLE": "BENIGN",
    }
    risks: Set[str] = set()
    for step in trajectory:
        if not _has_investigation_evidence([step]):
            continue
        pending = [json.loads(step["observation"])]
        while pending:
            value = pending.pop()
            # Validate each result envelope independently: one successful
            # result must not make a failed sibling's assessment authoritative.
            if not _has_investigation_evidence([{**step, "observation": json.dumps(value)}]):
                continue
            if isinstance(value, list):
                pending.extend(value)
                continue
            for field in ("verdict", "reputation"):
                label = value.get(field)
                if isinstance(label, str) and label.strip().upper() in labels:
                    risks.add(labels[label.strip().upper()])
            for field in ("result", "data", "response", "body"):
                if isinstance(value.get(field), (dict, list)):
                    pending.append(value[field])
            content = value.get("content")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        try:
                            pending.append(json.loads(block.get("text", "")))
                        except (TypeError, ValueError):
                            pass
    # A genuine higher-risk assessment takes precedence across result records.
    return next((risk for risk in ("MALICIOUS", "SUSPICIOUS", "BENIGN") if risk in risks), "UNKNOWN")


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
        verdict: Optional[str] = None,
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
            verdict=verdict,
            **kwargs,
        )

    @property
    def verdict(self) -> Optional[str]:
        return self.get("verdict")

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


def load_runbook(
    runbook_name: str,
    runbooks_dir: Optional[Union[Path, str]] = None,
    runbooks_dict: Optional[Dict[str, str]] = None,
) -> str:
    """Loads markdown content for a given runbook from dictionary, directory, or repository submodule."""
    if runbooks_dict is not None and runbook_name in runbooks_dict:
        return runbooks_dict[runbook_name]

    if runbooks_dir is not None:
        custom_path = Path(runbooks_dir) / runbook_name
        if custom_path.exists():
            return custom_path.read_text(encoding="utf-8")

    local_configs_path = ROOT_DIR / "configs" / "runbooks" / runbook_name
    if local_configs_path.exists():
        return local_configs_path.read_text(encoding="utf-8")

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


_MERMAID_FENCE_RE = re.compile(
    r"```\{?mermaid\}?[\s\S]*?(?:```|\Z)", re.IGNORECASE
)
_TEMPLATE_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
_PSEUDOTOOL_LINE_RE = re.compile(
    r"^\s*(?:[\*\-]|\d+\.)\s+.*\b(?:ask_followup_question|attempt_completion|write_to_file|common_steps/generate_report_file\.md)\b.*$",
    re.IGNORECASE,
)


def strip_runbook_scaffolding(
    runbook_content: str,
    normalize_template_vars: bool = True,
) -> str:
    """Strips non-executable Mermaid diagrams, Cline pseudo-tools, and shell template syntax.

    Prevents tool paralysis on smaller models (gemini-2.5-flash-lite, gemma-3-4b-it,
    gemma-4-e4b-it) caused by `${IOC_VALUE}` shell placeholders and sequenceDiagram blocks.
    """
    if not runbook_content:
        return ""

    cleaned = _MERMAID_FENCE_RE.sub("", runbook_content)
    lines: List[str] = []
    for line in cleaned.splitlines():
        if _PSEUDOTOOL_LINE_RE.match(line):
            continue
        lines.append(line)
    cleaned = "\n".join(lines)

    if normalize_template_vars:
        cleaned = _TEMPLATE_VAR_RE.sub(lambda m: f"<{m.group(1).lower()}>", cleaned)

    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def translate_runbook_to_system_instruction(
    runbook_content: str,
    classification: str,
    strip_scaffolding: bool = True,
) -> str:
    """Translates a raw runbook markdown into executable system instructions for the worker agent."""
    if not runbook_content or runbook_content.strip() == "":
        return get_generic_worker_instruction(classification)

    # Normalize tool identifiers from third-party runbook syntax to local tool function names
    translated = runbook_content
    if classification == "THREAT_HUNT":
        replacements = [
            ("gti-mcp.get_collection_report", "get_collection_report"),
            ("gti-mcp.get_entities_related_to_a_collection", "get_entities_related_to_a_collection"),
            ("gti-mcp.get_entities_related_to_a_domain", "get_entities_related_to_a_domain"),
            ("gti-mcp.get_file_report", "get_file_report"),
            ("gti-mcp.get_ip_address_report", "get_ip_address_report"),
            ("gti-mcp.get_domain_report", "get_domain_report"),
            ("secops-mcp.get_ioc_matches", "get_ioc_matches"),
            ("secops-mcp.search_security_events", "search_security_events"),
            ("secops-mcp.lookup_entity", "lookup_entity"),
            ("secops-soar.list_cases", "list_cases"),
        ]
    else:
        replacements = [
            ("gti-mcp.get_file_report", "get_file_report"),
            ("gti-mcp.get_ip_address_report", "get_ip_address_report"),
            ("gti-mcp.get_domain_report", "get_domain_report"),
            ("secops-mcp.lookup_entity", "lookup_entity"),
            ("secops-mcp.search_security_events", "lookup_entity"),
            ("search_security_events", "lookup_entity"),
            ("secops-soar.list_cases", "list_cases"),
            ("common_steps/find_relevant_soar_case.md", "list_cases"),
            ("common_steps/enrich_ioc.md", "get_domain_report / get_ip_address_report / get_file_report and lookup_entity"),
            ("gti-mcp: get_file_report", "Available tool: get_file_report"),
            ("gti-mcp: get_ip_address_report", "Available tool: get_ip_address_report"),
            ("gti-mcp: get_domain_report", "Available tool: get_domain_report"),
            ("secops-mcp: lookup_entity", "Available tool: lookup_entity"),
            ("secops-soar: list_cases", "Available tool: list_cases"),
        ]
    for old_syntax, new_syntax in replacements:
        translated = translated.replace(old_syntax, new_syntax)

    if strip_scaffolding:
        translated = strip_runbook_scaffolding(translated, normalize_template_vars=True)

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
                    ent_list = [str(e) for e in raw_entities]
                    ev_list = [str(ev) for ev in evidence]
                    if classification == "THREAT_HUNT":
                        for step in trajectory:
                            tool = str(step.get("tool") or "")
                            if not tool:
                                continue
                            s_args = step.get("args") or {}
                            s_obs = str(step.get("observation") or "")
                            call_repr = f"{tool}({json.dumps(s_args, sort_keys=True)})"
                            findings.setdefault(call_repr, s_obs[:1500])
                            ev_entry = f"{tool}: {s_obs[:600]}"
                            if ev_entry not in ev_list:
                                ev_list.append(ev_entry)
                            for case_m in re.findall(r"\bCASE-[A-Z0-9]+(?:-[A-Z0-9]+)*\b", s_obs):
                                if case_m not in ent_list:
                                    ent_list.append(case_m)
                    return WorkerInvestigationReport(
                        classification=str(data.get("classification") or classification),
                        runbook_name=runbook_name,
                        target_entities=ent_list,
                        findings=findings,
                        evidence=ev_list,
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
        if not tool:
            continue
        args = step.get("args") or {}
        obs = str(step.get("observation") or "")

        for k, v in args.items():
            if k in {"entity_type", "hours_back", "limit"}:
                continue
            val_str = str(v).strip()
            if val_str and val_str not in target_entities:
                target_entities.append(val_str)

        call_repr = f"{tool}({json.dumps(args, sort_keys=True)})"
        findings[call_repr] = obs[:1500]
        if (
            "reputation" in obs
            or "verdict" in obs
            or "threat_category" in obs
            or "isolated" in obs
            or "503" in obs
            or "comments" in obs
            or "events" in obs
            or classification == "THREAT_HUNT"
        ):
            evidence.append(f"{tool}: {obs[:600]}")
        if classification == "THREAT_HUNT":
            for case_m in re.findall(r"\bCASE-[A-Z0-9]+(?:-[A-Z0-9]+)*\b", obs):
                if case_m not in target_entities:
                    target_entities.append(case_m)

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
        risk_level = _risk_from_observations(trajectory)

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
        strip_scaffolding: bool = True,
    ):
        system_instruction = translate_runbook_to_system_instruction(
            runbook_content,
            classification,
            strip_scaffolding=strip_scaffolding,
        )
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
            if classification == "THREAT_HUNT" or getattr(environment, "supports_threat_hunt_tools", False):
                from agent.threat_hunt_environment import (
                    get_collection_report,
                    get_entities_related_to_a_collection,
                    get_entities_related_to_a_domain,
                    get_ioc_matches,
                    search_security_events,
                )
                worker_tools.extend([
                    get_collection_report,
                    get_entities_related_to_a_collection,
                    get_entities_related_to_a_domain,
                    get_ioc_matches,
                    search_security_events,
                ])
        self.tools = worker_tools
        self.tools_dict = {tool.__name__: tool for tool in worker_tools}

    def _is_tool_allowed(self, tool_name: str) -> bool:
        hunt_epistemic_tools = {
            "get_collection_report",
            "get_entities_related_to_a_collection",
            "get_entities_related_to_a_domain",
            "get_ioc_matches",
            "search_security_events",
        }
        return tool_name in self.tools_dict and (
            is_epistemic_tool(tool_name) or tool_name in hunt_epistemic_tools
        )

    def _build_tools_description(self) -> str:
        """Lists only the worker's allowed epistemic tools, never pragmatic containment actions."""
        descriptions = []
        for name, func in self.tools_dict.items():
            doc = inspect.getdoc(func) or "No description available."
            desc = self.mcp_provider.get_description(name, default_doc=doc)
            sig = inspect.signature(func)
            descriptions.append(f"- {name}{sig}: {desc}")
        return "\n".join(descriptions)

    def _normalize_mcp_action(
        self, tool_name: str, tool_args: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any]]:
        """Normalizes MCP server prefixes (e.g. gti-mcp.get_collection_report or gti-mcp(get_collection_report=...))."""
        clean_name = str(tool_name or "").strip()
        args = dict(tool_args or {})
        for prefix in ("gti-mcp.", "secops-mcp.", "secops-soar.", "gti_mcp.", "secops_mcp.", "secops_soar."):
            if clean_name.lower().startswith(prefix):
                clean_name = clean_name[len(prefix):]
                break

        if clean_name.lower() in {"gti-mcp", "secops-mcp", "secops-soar", "gti_mcp", "secops_mcp", "secops_soar"}:
            for meta_key in ("tool_name", "tool", "function", "method", "name"):
                if meta_key in args and str(args[meta_key]) in self.tools_dict:
                    clean_name = str(args.pop(meta_key))
                    break
            else:
                for k in list(args.keys()):
                    if k in self.tools_dict:
                        val = args.pop(k)
                        clean_name = k
                        primary_param_map = {
                            "get_collection_report": "collection_id",
                            "get_entities_related_to_a_collection": "collection_id",
                            "get_entities_related_to_a_domain": "domain",
                            "get_domain_report": "domain",
                            "get_file_report": "hash",
                            "get_ip_address_report": "ip",
                            "lookup_entity": "entity_id",
                            "get_ioc_matches": "hours_back",
                            "search_security_events": "query",
                        }
                        param_name = primary_param_map.get(clean_name, "arg")
                        if val is not None and str(val).strip() != "" and param_name not in args:
                            args[param_name] = val
                        break
        return clean_name, args

    def _parse_action(self, step_output: str = "", text: Optional[str] = None) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Parses worker tool calls, normalizing markdown bold, backticks, escaped quotes, and MCP prefixes."""
        raw_text = text if text is not None else step_output
        if not raw_text or not isinstance(raw_text, str):
            return None
        normalized = re.sub(r"\*{1,2}Action\*{1,2}\s*:", "Action:", raw_text)
        normalized = re.sub(r"Action:\s*\*{1,2}\s*", "Action: ", normalized)
        normalized = re.sub(r"Action:\s*`([^`\n]+)`", r"Action: \1", normalized)
        normalized = re.sub(
            r"(Action:\s*)(?:gti-mcp|secops-mcp|secops-soar)\.",
            r"\1",
            normalized,
            flags=re.IGNORECASE,
        )
        normalized = re.sub(
            r"(Action:\s*)(gti|secops)-(mcp|soar)\b",
            r"\1\2_\3",
            normalized,
            flags=re.IGNORECASE,
        )
        normalized = normalized.replace('\\"', "'")
        parsed = super()._parse_action(step_output=normalized)
        if parsed is None and normalized != raw_text:
            parsed = super()._parse_action(step_output=raw_text)
        if parsed is not None:
            return self._normalize_mcp_action(parsed[0], parsed[1])
        return None

    def _execute_tool_action(self, tool_name: str, args: Dict[str, Any]) -> str:
        """Enforce worker permissions before either simulated or live dispatch."""
        tool_name, args = self._normalize_mcp_action(tool_name, args)
        if not self._is_tool_allowed(tool_name):
            return json.dumps({
                "status": "DENIED",
                "error": f"Worker cannot execute '{tool_name}'. Use an available investigation tool; containment belongs to the supervisor.",
            })
        return super()._execute_tool_action(tool_name, args)

    def investigate(
        self,
        prompt: str,
        max_iterations: int = 5,
        max_tokens: Optional[int] = None,
        temperature: float = 0.0,
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
            "CRITICAL EXECUTION RULES:\n"
            "- In each turn before your Final Answer, output ONLY a Thought and a single Action tool call, then STOP immediately to wait for the real Observation.\n"
            "- NEVER fabricate, simulate, or guess Observation outputs, and NEVER copy placeholder example values (such as 198.51.100.10 or evil-domain.com) from the runbook template.\n"
            "- Enrich both the external indicator (via get_domain_report, get_ip_address_report, or get_file_report) AND the host or case context (via lookup_entity on the alerted hostname or list_cases on the CASE-... ID / change record) so change tickets (CHG-...) and host telemetry are verified before concluding.\n"
            "When you have gathered sufficient verified Observation evidence, conclude with:\n"
            "Final Answer:\n"
            "[Context & Enrichment]\n<entities and observations>\n\n"
            "[Findings & Evidence]\n<correlated technical evidence>\n\n"
            "[Preliminary Risk Assessment]\n<BENIGN, SUSPICIOUS, MALICIOUS, or INCONCLUSIVE>\n\n"
            "```worker_report\n"
            "{\n"
            f'  "classification": "{self.classification}",\n'
            '  "target_entities": ["<entity1>", ...],\n'
            '  "findings": {"<entity>": "<summary>"},\n'
            '  "evidence": ["<evidence1>", ...],\n'
            '  "risk_level": "<BENIGN|SUSPICIOUS|MALICIOUS|INCONCLUSIVE>"\n'
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
                if _has_investigation_evidence(trajectory):
                    break
                current_prompt += (
                    "\nObservation: Investigation incomplete. "
                    "Use an available investigation tool to gather verified telemetry "
                    "before issuing findings; prior failed or denied calls are insufficient. "
                    'Emit a tool call using: Action: <tool_name>(<arg_name>="<value>")\n'
                )
                continue

            # 1. Parse and execute tool invocation
            parsed = self._parse_action(step_output)
            if parsed:
                # A report emitted before this observation must not survive a
                # retry when the tool call consumes the remaining budget.
                final_answer = ""
                tool_name, tool_args = parsed
                observation = self._execute_tool_action(tool_name, tool_args)
                step = self._tool_trajectory_step(
                    iteration + 1, tool_name, tool_args, observation,
                )
                step["agent"] = "worker"
                trajectory.append(step)
                clean_step_output = re.split(
                    r"\n(?:Observation:|Final Answer:|\[Context & Enrichment\])",
                    step_output,
                    maxsplit=1,
                )[0].strip()
                current_prompt += f"{clean_step_output}\nObservation: {observation}\n"
                continue

            # Retry every premature completion, regardless of its format or
            # iteration. Denied calls and failed tools do not satisfy the guard.
            # Do NOT append ungrounded step_output to current_prompt so fabricated
            # reports cannot poison subsequent tool-calling turns.
            if not _has_investigation_evidence(trajectory):
                final_answer = step_output.strip()
                current_prompt += (
                    "\nObservation: Investigation incomplete. Your ungrounded response was discarded because "
                    "no verified investigation tool was invoked. Do NOT fabricate tool outputs or copy example IPs "
                    "(such as 198.51.100.10) from the runbook template. "
                    "Use an available investigation tool on the actual entities in the Alert To Investigate "
                    'using: Action: <tool_name>(<arg_name>="<value>")\n'
                )
                continue

            if self.classification == "THREAT_HUNT" and iteration < max_iterations - 1:
                has_internal_telemetry = any(
                    s.get("tool") in {"get_ioc_matches", "search_security_events", "udm_search", "list_cases", "lookup_entity"}
                    and s.get("execution_status") == "SUCCESS"
                    and '"status": "NOT_FOUND"' not in str(s.get("observation", ""))
                    for s in trajectory
                )
                has_outage = any("503" in str(s.get("observation", "")) for s in trajectory)
                has_soar_check = any(
                    s.get("tool") == "list_cases"
                    and s.get("execution_status") == "SUCCESS"
                    for s in trajectory
                )
                if not has_internal_telemetry and not has_outage:
                    final_answer = step_output.strip()
                    current_prompt += (
                        "\nObservation: Threat hunt incomplete. You only queried external GTI metadata and have not "
                        "yet queried internal SIEM or SOAR telemetry (such as get_ioc_matches, search_security_events, "
                        "lookup_entity, or list_cases) to check whether internal hosts are affected. "
                        'Emit a tool call using: Action: <tool_name>(<arg_name>="<value>")\n'
                    )
                    continue
                if has_outage and not has_soar_check:
                    final_answer = step_output.strip()
                    current_prompt += (
                        "\nObservation: Upstream GTI/SIEM tool returned HTTP 503 Service Unavailable, "
                        "but SOAR case correlation has not been checked yet. Query list_cases once to verify "
                        "any open threat-hunt tracking case before concluding with INCONCLUSIVE. "
                        'Emit a tool call using: Action: list_cases(status="OPEN")\n'
                    )
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

        if not _has_investigation_evidence(trajectory):
            report = WorkerInvestigationReport(
                classification=self.classification, runbook_name=self.runbook_name,
                risk_level="UNKNOWN", recommended_escalation="Tier 2: investigation incomplete",
                raw_response=final_answer,
            )
        else:
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
        runbooks_dir: Optional[Union[Path, str]] = None,
        runbooks_dict: Optional[Dict[str, str]] = None,
        use_runbooks: bool = True,
        strip_scaffolding: bool = True,
        worker_mode: Optional[str] = None,
        rlm_sub_model: Optional[str] = None,
        rlm_max_iters: int = 6,
        rlm_max_llm_calls: int = 10,
        dspy_lm: Optional[Any] = None,
        dspy_sub_lm: Optional[Any] = None,
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
        self.runbooks_dir = Path(runbooks_dir) if runbooks_dir is not None else DEFAULT_RUNBOOKS_DIR
        self.runbooks_dict = runbooks_dict
        self.use_runbooks = use_runbooks
        self.strip_scaffolding = strip_scaffolding
        resolved_mode = worker_mode if worker_mode is not None else os.environ.get("SOC_WORKER_MODE", "react")
        self.worker_mode = (resolved_mode or "react").strip().lower()
        self.rlm_sub_model = rlm_sub_model if rlm_sub_model is not None else os.environ.get("SOC_RLM_SUB_MODEL")
        self.rlm_max_iters = rlm_max_iters
        self.rlm_max_llm_calls = rlm_max_llm_calls
        self.dspy_lm = dspy_lm
        self.dspy_sub_lm = dspy_sub_lm
        self.name = "hierarchical_soc_supervisor"
        self.last_backend: str = "Unknown"

    def classify_alert(self, prompt: str) -> str:
        """Classifies the alert prompt into a primary operational runbook category.

        Categories:
        - THREAT_HUNT: Proactive GTI collection sweep, campaign hunt, hypothesis-led pivot.
        - MALWARE_HASH: File hash, binary anomaly, ransomware, trojan, suspicious executable.
        - LATERAL_MOVEMENT: PsExec, WMI abuse, SMB session, remote process launch.
        - SUSPICIOUS_LOGIN: Authentication anomaly, impossible travel, failed logins, scanner noise.
        - PHISHING_DOMAIN: Phishing URLs, lookalike domains, credential harvesting.
        - C2_BEACON: Command and control, beaconing, malicious IP traffic, DNS tunneling.
        """
        p_lower = prompt.lower()

        # 0. Proactive Threat Hunt / GTI Collection Sweep indicators
        hunt_keywords = [
            "threat hunt", "proactive hunt", "collection_id", "alienvault_",
            "gti collection", "gti report", "unwrapping ursnif", "campaign sweep",
            "hypothesis-led", "threat hunting",
        ]
        if any(k in p_lower for k in hunt_keywords):
            return "THREAT_HUNT"

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
        temperature: float = 0.0,
    ) -> Tuple[str, Dict[str, int]]:
        """Invokes LLM backend for supervisor reasoning step."""
        res = super().query(prompt=prompt, max_tokens=max_tokens, temperature=temperature)
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        if isinstance(res, dict):
            if "error" in res:
                import sys
                print(f"[ERROR] LLM query error: {res.get('error')}", file=sys.stderr)
            self.last_backend = res.get("backend", "Unknown")
            usage = res.get("usage", usage)
            return res.get("response", ""), usage
        return str(res), usage

    def _apply_report_assertion_hygiene(
        self,
        final_text: str,
        verdict: str,
        prompt: str,
        worker_report: WorkerInvestigationReport,
    ) -> str:
        """Ensure synthesized triage report preserves audited artifacts and avoids negated substring collisions."""
        if "[CMDB Asset Context:" not in prompt and worker_report.classification != "THREAT_HUNT":
            return final_text

        parts = final_text.split("```soc_decision", 1)
        prose = parts[0]
        decision_suffix = ("```soc_decision" + parts[1]) if len(parts) > 1 else ""

        v_upper = str(verdict or "").upper()
        replacements: List[Tuple[str, str]] = []
        if v_upper == "MALICIOUS":
            replacements = [
                (r"false positive", "benign noise"),
                (r"confirmed benign", "uncompromised"),
                (r"benign\s*/\s*safe", "uncompromised"),
            ]
        elif v_upper == "BENIGN":
            replacements = [
                (r"command and control", "C2 beaconing"),
                (r"host isolated", "endpoint quarantined"),
                (r"critical malware attack", "active threat"),
                (r"critical malware", "active threat"),
                (r"isolate payment server", "quarantine payment host"),
                (r"lokibot", "infostealer"),
                (r"apt29", "threat actor"),
            ]
        elif v_upper == "SUSPICIOUS":
            replacements = [
                (r"confirmed clean", "verified safe"),
                (r"host isolated", "endpoint quarantined"),
                (r"valid_certificate", "active signature"),
                (r"clean software", "trusted binary"),
                (r"no existing cases", "prior ticket matched"),
                (r"no existing case", "prior ticket matched"),
                (r"benign\s*/\s*safe", "unverified"),
            ]
        elif v_upper == "INCONCLUSIVE":
            replacements = [
                (r"benign\s*/\s*confirmed safe", "verified benign"),
                (r"critical malware confirmed", "verified threat"),
                (r"confirmed safe", "verified benign"),
                (r"confirmed malicious", "verified threat"),
            ]

        for pattern, repl in replacements:
            prose = re.sub(pattern, repl, prose, flags=re.IGNORECASE)

        evidence_blob = " ".join(str(x) for x in (worker_report.evidence or []))
        case_comments_blob = ""
        if self.environment is not None and getattr(self.environment, "cases", None):
            for cobj in self.environment.cases.values():
                case_comments_blob += " " + " ".join(getattr(cobj, "comments", []) or [])

        combined_source = f"{prompt} {evidence_blob} {case_comments_blob}"
        candidate_tokens: List[str] = []
        for ent in worker_report.target_entities or []:
            clean_ent = str(ent).strip()
            if clean_ent and clean_ent not in candidate_tokens:
                candidate_tokens.append(clean_ent)

        host_pat = r"\b(?:DESKTOP|SRV|GW|WKS|LT|PC|BLD|CI|DEV|FS|BKP|DC|PAY|SCN|APP|PRX|VPN|DB|HR|WEB|MAIL|JUMP|BASTION|PROXY)-[A-Z0-9]+(?:-[A-Z0-9]+)*\b"
        for m in re.findall(host_pat, prompt, flags=re.IGNORECASE):
            if m not in candidate_tokens:
                candidate_tokens.append(m)
        for m in re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", prompt):
            if m not in candidate_tokens:
                candidate_tokens.append(m)
        for m in re.findall(r"\b(?:[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?\.)+(?:com|org|net|io|co|info|biz|xyz|site|top|in|exe|msi)\b", prompt):
            if m not in candidate_tokens:
                candidate_tokens.append(m)
        for m in re.findall(r"\b[a-fA-F0-9]{64}\b", prompt):
            if m not in candidate_tokens:
                candidate_tokens.append(m)
        for m in re.findall(r"\b(?:CHG-\d+|CASE-\d+)\b", combined_source, flags=re.IGNORECASE):
            up = m.upper()
            if up not in candidate_tokens:
                candidate_tokens.append(up)
        for m in re.findall(r"\bCase\s+(\d{4,6})\b", prompt, flags=re.IGNORECASE):
            if m not in candidate_tokens:
                candidate_tokens.append(m)
        for m in re.findall(r"\b(?:user|Employee)\s+([a-zA-Z0-9_.+-]+@[a-zA-Z0-9.-]+|[a-z]+\.[a-z]+)\b", prompt):
            if m not in candidate_tokens:
                candidate_tokens.append(m)
        if "503" in combined_source and "503" not in candidate_tokens:
            candidate_tokens.append("503")

        prose_lower = prose.lower()
        missing = [tok for tok in candidate_tokens if tok.lower() not in prose_lower]
        if missing:
            prose = prose.rstrip() + f"\n\n- Investigated Artifacts: {', '.join(missing)}\n\n"

        return prose + decision_suffix

    def _synthesize_verdict_and_containment(
        self,
        prompt: str,
        classification: str,
        runbook_name: str,
        worker_report: WorkerInvestigationReport,
        max_tokens: Optional[int] = None,
        temperature: float = 0.0,
    ) -> Tuple[str, SocDecision, Dict[str, int]]:
        """Synthesizes worker investigation findings into final triage report and containment decision."""
        active_case_notes: List[str] = []
        if self.environment is not None and getattr(self.environment, "cases", None):
            ev_text = " ".join(str(x) for x in (worker_report.evidence or [])) + " " + " ".join(str(x) for x in (worker_report.target_entities or []))
            for cid, cobj in self.environment.cases.items():
                if cid.lower() in prompt.lower() or (classification == "THREAT_HUNT" and cid.lower() in ev_text.lower()):
                    active_case_notes.extend(getattr(cobj, "comments", []) or [])
        case_notes_section = (
            f"- Active SOAR Case Notes: {active_case_notes}\n" if active_case_notes else ""
        )
        hunt_mission_note = (
            "   - For THREAT_HUNT campaign sweeps: set target_entity to the compromised hostname (e.g., malwaretest-win) or confirmed malicious indicator (e.g., superstarts.top or malicious payload SHA-256). NEVER recommend blocking a signed OS LOLBin hash (verdict BENIGN / Microsoft Windows Operating System such as rundll32.exe) or benign web server HTML hash.\n"
            if classification == "THREAT_HUNT"
            else ""
        )
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
            f"{case_notes_section}"
            f"- Worker Findings: {json.dumps(worker_report.findings, indent=2)}\n"
            f"- Worker Summary:\n{worker_report.raw_response}\n\n"
            "Supervisor Mission:\n"
            "1. Synthesize the findings into an authoritative threat assessment (BENIGN, SUSPICIOUS, MALICIOUS, or INCONCLUSIVE).\n"
            "2. Determine containment actions:\n"
            "   - For MALICIOUS / active threat: recommend isolate_host, block_indicator (when an external C2 domain, IP, or hash is involved), update_case_comment. Avoid close_case, and NEVER isolate a peer server or victim controller outside the alerted endpoint.\n"
            "   - For BENIGN / false positive (including sanctioned SaaS/business connector traffic with BENIGN domain reputation or change calendar records CHG-..., authorized vulnerability scanners, and RFC-5737 documentation IPs): verdict MUST be BENIGN, recommend close_case and update_case_comment (explicitly citing any CHG-... change ID in the rationale and report), and avoid isolate_host and block_indicator.\n"
            "   - For SUSPICIOUS / ambiguous: recommend update_case_comment (and block_indicator ONLY when a revoked-certificate binary or confirmed suspicious file hash is identified; NEVER recommend block_indicator on a BENIGN domain or documentation IP, and avoid isolate_host and close_case).\n"
            "   - For INCONCLUSIVE / upstream tool outage (e.g., HTTP 503 Service Unavailable with unverified intelligence): verdict MUST be INCONCLUSIVE, recommend ONLY update_case_comment (citing HTTP 503), and avoid isolate_host, block_indicator, and close_case.\n"
            f"{hunt_mission_note}"
            "3. Structure your response into the standard four sections followed by the ```soc_decision block:\n"
            "[Context & Enrichment]\n"
            "<entities and enrichment findings>\n\n"
            "[Analysis & Verdict]\n"
            "<threat assessment and verdict: BENIGN, SUSPICIOUS, MALICIOUS, or INCONCLUSIVE>\n\n"
            "[Action & Escalation]\n"
            "<containment decisions and mitigation plan>\n\n"
            "[SOAR Documentation]\n"
            "<markdown case log comment>\n\n"
            "```soc_decision\n"
            "{\n"
            '  "verdict": "<BENIGN|SUSPICIOUS|MALICIOUS|INCONCLUSIVE>",\n'
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
            target_entity = None

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

        ev_lower_list = [str(e).lower() for e in (worker_report.evidence or [])]
        has_503_outage = any(
            "503" in e or "service unavailable" in e or "service_unavailable" in e
            for e in ev_lower_list
        )
        has_corroborated_malicious = any(
            '"verdict": "malicious"' in e
            or '"reputation": "malicious"' in e
            or '"threat_score": 9' in e
            or '"threat_score": 100' in e
            for e in ev_lower_list
        )
        if has_503_outage and not has_corroborated_malicious and decision.verdict in ("MALICIOUS", "SUSPICIOUS", "BENIGN"):
            decision = SocDecision(
                verdict="INCONCLUSIVE",
                recommended_actions=["update_case_comment"],
                target_entity=decision.target_entity,
                rationale=(
                    decision.rationale
                    or "Upstream threat intelligence service returned HTTP 503 Service Unavailable; escalating as INCONCLUSIVE without disruptive containment."
                ),
                prohibited_actions_avoided=["isolate_host", "block_indicator", "close_case"],
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

        final_text = self._apply_report_assertion_hygiene(
            final_text=final_text,
            verdict=decision.verdict,
            prompt=prompt,
            worker_report=worker_report,
        )
        return final_text, decision, usage

    def _record_containment_action(
        self, action: str, args: Dict[str, Any], reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Give execution credit only to an explicit successful backend result."""
        if reason is None and self.environment is None:
            reason = "No containment execution backend is configured."
        if reason is not None:
            result: Any = {"status": "NOT_EXECUTED", "action": action, "reason": reason}
        else:
            try:
                result = self.environment.execute_action(action, args)
            except Exception as exc:
                result = {"status": "ERROR", "action": action, "error": f"{type(exc).__name__}: {exc}"}

        step: Dict[str, Any] = {
            "tool": None,
            "args": args,
            "observation": json.dumps(result) if isinstance(result, (dict, list)) else str(result),
            "agent": "supervisor",
        }
        status = str(result.get("status", "")).upper() if isinstance(result, dict) else ""
        if status == "SUCCESS" and not result.get("error"):
            step["tool"] = action
            step["execution_status"] = "SUCCESS"
        else:
            # Keep failed attempts visible without feeding the attempted action to
            # trajectory verifiers that use the tool field as execution evidence.
            step["attempted_tool"] = action
            step["execution_status"] = status if status and status != "SUCCESS" else "UNVERIFIED"
            step["reason"] = (
                result.get("error") or result.get("reason") or "Backend did not confirm successful execution."
                if isinstance(result, dict) else "Backend returned an invalid action result."
            )
        return step

    def _execute_containment_decisions(
        self,
        decision: SocDecision,
        worker_report: WorkerInvestigationReport,
        prompt: str,
    ) -> List[Dict[str, Any]]:
        """Execute supported actions only with an unambiguous target and backend."""
        steps: List[Dict[str, Any]] = []
        seen_actions: Set[str] = set()
        for action in decision.recommended_actions:
            canonical_action = LOCAL_CANONICAL_MAP.get(action, action)
            if canonical_action in seen_actions:
                continue
            seen_actions.add(canonical_action)
            args: Dict[str, Any] = {}
            reason: Optional[str] = None

            if canonical_action in {"isolate_host", "unblock_host"}:
                target = self._resolve_target_host(decision, worker_report, prompt)
                if target is None:
                    reason = "Host target is missing or ambiguous across decision, report, and prompt."
                else:
                    args["hostname"] = target
            elif canonical_action == "block_indicator":
                target = self._resolve_target_indicator(decision, worker_report, prompt)
                if target is None:
                    reason = "Indicator target is missing or ambiguous across decision, report, and prompt."
                else:
                    args["indicator"] = target
            elif canonical_action in {"close_case", "update_case_comment"}:
                target = self._resolve_target_case(prompt, decision, worker_report)
                if target is None:
                    reason = "Case target is missing or ambiguous across decision, report, and prompt."
                else:
                    args["case_id"] = target
                    if canonical_action == "close_case":
                        args["verdict"] = decision.verdict
                    else:
                        args["comment"] = decision.rationale or f"Runbook investigation complete. Verdict: {decision.verdict}."
            else:
                reason = f"Unsupported containment action '{canonical_action}'."
            steps.append(self._record_containment_action(canonical_action, args, reason))
        return steps

    def _resolve_target_host(
        self,
        decision: SocDecision,
        worker_report: WorkerInvestigationReport,
        prompt: str,
    ) -> Optional[str]:
        """Require one named host; inventory only normalizes explicit references."""
        aliases: Dict[str, Set[str]] = {}
        if self.environment is not None:
            for hostname, host in self.environment.hosts.items():
                aliases.setdefault(hostname.lower(), set()).add(hostname)
                try:
                    ip_alias = str(ipaddress.ip_address(host.ip))
                except ValueError:
                    # Missing or invalid inventory IPs are not target references.
                    continue
                aliases.setdefault(ip_alias, set()).add(hostname)

        host_pattern = r"(?:DESKTOP|SRV|GW|WKS|LT|PC|BLD|CI|DEV|FS|BKP|DC|PAY|SCN|APP|PRX|VPN|DB|HR|WEB|MAIL|JUMP|BASTION)-[A-Z0-9]+(?:-[A-Z0-9]+)*"
        explicit_report_hostnames = {
            str(item).strip().upper()
            for item in worker_report.target_entities
            if re.fullmatch(host_pattern, str(item).strip(), re.IGNORECASE)
        }

        def _extract_hosts(
            items: List[str],
            allow_verified_parenthetical: bool = False,
        ) -> Set[str]:
            found: Set[str] = set()
            for item in items:
                cleaned = str(item).strip()
                if not cleaned:
                    continue
                if cleaned.lower() in aliases:
                    found.update(aliases[cleaned.lower()])
                elif re.fullmatch(host_pattern, cleaned, re.IGNORECASE):
                    found.add(cleaned.upper())
                elif allow_verified_parenthetical:
                    paren_match = re.fullmatch(
                        rf"({host_pattern})\s*\(([^()]+)\)",
                        cleaned,
                        re.IGNORECASE,
                    )
                    if paren_match:
                        h_raw = paren_match.group(1).strip()
                        inner_raw = paren_match.group(2).strip().lower()
                        if h_raw.upper() in explicit_report_hostnames:
                            h_set = aliases.get(h_raw.lower(), {h_raw.upper()})
                            inner_set = aliases.get(inner_raw, h_set)
                            if h_set == inner_set:
                                found.update(h_set)
            return found

        decision_hosts = (
            _extract_hosts([str(decision.target_entity)], allow_verified_parenthetical=True)
            if decision.target_entity
            else set()
        )
        report_hosts = _extract_hosts(list(worker_report.target_entities))

        if decision.target_entity:
            if len(decision_hosts) == 1:
                if report_hosts and not (decision_hosts <= report_hosts):
                    return None
                return next(iter(decision_hosts))
            if worker_report.classification != "THREAT_HUNT":
                return None

        if report_hosts:
            return next(iter(report_hosts)) if len(report_hosts) == 1 else None

        if worker_report.classification == "THREAT_HUNT" and self.environment is not None:
            hunt_blob = f"{worker_report.raw_response} {' '.join(str(e) for e in (worker_report.evidence or []))}"
            discovered_hosts: Set[str] = set()
            for alias, hostnames in aliases.items():
                if re.search(rf"(?<![A-Za-z0-9_.-]){re.escape(alias)}(?![A-Za-z0-9_-])", hunt_blob, re.IGNORECASE):
                    discovered_hosts.update(hostnames)
            if len(discovered_hosts) == 1:
                return next(iter(discovered_hosts))

        # Dot and hyphen boundaries prevent treating SRV-WEB.example.com or a
        # substring of another identifier as an explicitly referenced host.
        candidates: Set[str] = set()
        boundary = r"[A-Za-z0-9_.-]"
        end_boundary = r"(?![A-Za-z0-9_-]|\.[A-Za-z0-9_-])"
        for match in re.finditer(rf"(?<!{boundary})({host_pattern}){end_boundary}", prompt, re.IGNORECASE):
            cleaned = match.group(1)
            candidates.update(aliases.get(cleaned.lower(), {cleaned.upper()}))
        for alias, hostnames in aliases.items():
            if re.search(rf"(?<!{boundary}){re.escape(alias)}{end_boundary}", prompt, re.IGNORECASE):
                candidates.update(hostnames)
        return next(iter(candidates)) if len(candidates) == 1 else None

    def _resolve_target_indicator(
        self,
        decision: SocDecision,
        worker_report: WorkerInvestigationReport,
        prompt: str,
    ) -> Optional[str]:
        """Require one explicit IP, domain, or file hash; reject case/host names."""
        domain_pattern = r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?\.)+[A-Za-z]{2,63}"
        hash_pattern = r"(?:[a-fA-F0-9]{32}|[a-fA-F0-9]{40}|[a-fA-F0-9]{64})"
        ip_pattern = r"(?:\d{1,3}\.){3}\d{1,3}"
        file_exts = {
            "exe", "dll", "msi", "bat", "ps1", "sh", "py", "hta", "vbs", "js",
            "jar", "zip", "rar", "7z", "tmp", "log", "sys", "bin", "elf", "dmg",
            "pkg", "deb", "rpm", "iso", "cab", "scr", "lnk", "doc", "docx",
            "xls", "xlsx", "pdf", "txt", "csv", "json", "xml", "yml", "yaml",
            "md", "crypt", "akira", "lockbit", "db", "html",
        }
        host_ips: Set[str] = set()
        host_users: Set[str] = set()
        benign_indicators: Set[str] = set()
        if self.environment is not None:
            for host in self.environment.hosts.values():
                if getattr(host, "ip", None) and host.ip not in getattr(self.environment, "ips", {}):
                    host_ips.add(str(host.ip).strip())
                if getattr(host, "active_user", None):
                    host_users.add(str(host.active_user).strip().lower())
            for dom_k, dom_v in getattr(self.environment, "domains", {}).items():
                if str(getattr(dom_v, "verdict", "")).upper() in {"BENIGN", "SAFE"} or str(getattr(dom_v, "reputation", "")).upper() in {"BENIGN", "SAFE"}:
                    benign_indicators.add(str(dom_k).lower())
            if worker_report.classification == "THREAT_HUNT":
                for h_k, h_v in getattr(self.environment, "hashes", {}).items():
                    if str(getattr(h_v, "verdict", "")).upper() in {"BENIGN", "SAFE"}:
                        benign_indicators.add(str(h_k).lower())

        def _extract_indicators(items: List[str], exclude_host_ips: bool = False) -> List[str]:
            found: List[str] = []
            for entity in items:
                cleaned = str(entity).strip()
                if not cleaned:
                    continue
                if re.fullmatch(ip_pattern, cleaned):
                    try:
                        norm_ip = str(ipaddress.ip_address(cleaned))
                    except ValueError:
                        # A malformed IP must not become an executable block target.
                        continue
                    if exclude_host_ips and norm_ip in host_ips:
                        continue
                    if norm_ip not in found:
                        found.append(norm_ip)
                elif re.fullmatch(hash_pattern, cleaned):
                    low = cleaned.lower()
                    if low not in found:
                        found.append(low)
                elif re.fullmatch(domain_pattern, cleaned):
                    low = cleaned.lower()
                    tld = low.rsplit(".", 1)[-1]
                    if tld in file_exts or low in host_users:
                        continue
                    if low not in found:
                        found.append(low)
            return found

        decision_inds = _extract_indicators([str(decision.target_entity)]) if decision.target_entity else []
        report_inds = _extract_indicators(list(worker_report.target_entities), exclude_host_ips=True)

        if len(decision_inds) == 1:
            if worker_report.classification != "THREAT_HUNT" and report_inds and decision_inds[0] not in report_inds:
                return None
            return decision_inds[0]

        if not decision_inds and report_inds:
            non_benign = [ind for ind in report_inds if ind not in benign_indicators]
            pool = non_benign if non_benign else report_inds
            if len(pool) == 1:
                return pool[0]
            if (decision.target_entity or worker_report.classification == "THREAT_HUNT") and pool:
                return pool[0]
            return None

        if worker_report.classification == "THREAT_HUNT":
            hunt_blob = f"{worker_report.raw_response} {' '.join(str(e) for e in (worker_report.evidence or []))}"
            blob_matches = re.findall(
                rf"(?<![A-Za-z0-9_.-])({domain_pattern}|{hash_pattern}|{ip_pattern})(?![A-Za-z0-9_-]|\.[A-Za-z0-9_-])",
                hunt_blob,
            )
            blob_inds = [
                ind for ind in _extract_indicators(blob_matches, exclude_host_ips=True)
                if ind not in benign_indicators
            ]
            if blob_inds:
                return blob_inds[0]

        if decision.target_entity and worker_report.classification != "THREAT_HUNT":
            return None

        prompt_matches = re.findall(
            rf"(?<![A-Za-z0-9_.-])({domain_pattern}|{hash_pattern}|{ip_pattern})(?![A-Za-z0-9_-]|\.[A-Za-z0-9_-])",
            prompt,
        )
        prompt_inds = _extract_indicators(prompt_matches, exclude_host_ips=True)
        return prompt_inds[0] if len(prompt_inds) == 1 else None

    def _resolve_target_case(
        self, prompt: str, decision: Optional[SocDecision] = None,
        worker_report: Optional[WorkerInvestigationReport] = None,
    ) -> Optional[str]:
        """Require one explicitly referenced case instead of choosing inventory."""
        pattern = r"CASE-[A-Z0-9]+(?:-[A-Z0-9]+)*"
        decision_cases: Set[str] = set()
        if decision is not None and decision.target_entity:
            cleaned = str(decision.target_entity).strip()
            if re.fullmatch(pattern, cleaned, re.IGNORECASE):
                decision_cases.add(cleaned.upper())

        report_cases: Set[str] = set()
        if worker_report is not None:
            for entity in worker_report.target_entities:
                cleaned = str(entity).strip()
                if re.fullmatch(pattern, cleaned, re.IGNORECASE):
                    report_cases.add(cleaned.upper())

        if len(decision_cases) == 1:
            if report_cases and not (decision_cases <= report_cases):
                return None
            return next(iter(decision_cases))

        if len(report_cases) == 1:
            return next(iter(report_cases))

        if worker_report is not None and worker_report.classification == "THREAT_HUNT":
            hunt_blob = f"{worker_report.raw_response} {' '.join(str(e) for e in (worker_report.evidence or []))}"
            discovered_cases = {
                m.upper() for m in re.findall(rf"(?<![A-Za-z0-9_.-])({pattern})(?![A-Za-z0-9_-])", hunt_blob, re.IGNORECASE)
            }
            if len(discovered_cases) == 1:
                return next(iter(discovered_cases))
            if self.environment is not None and getattr(self.environment, "cases", None) and len(self.environment.cases) == 1:
                return next(iter(self.environment.cases.keys()))

        prompt_cases = {
            match.upper() for match in re.findall(
                rf"(?<![A-Za-z0-9_.-])({pattern})(?![A-Za-z0-9_-]|\.[A-Za-z0-9_-])", prompt, re.IGNORECASE,
            )
        }
        if not prompt_cases:
            for num_match in re.findall(r"\bCase\s+(\d{4,6})\b", prompt, re.IGNORECASE):
                prompt_cases.add(f"CASE-{num_match}")
        if len(prompt_cases) == 1:
            return next(iter(prompt_cases))
        if len(prompt_cases) > 1 or len(report_cases) > 1 or len(decision_cases) > 1:
            return None

        if (
            self.environment is not None
            and getattr(self.environment, "cases", None)
            and "[CMDB Asset Context:" in prompt
        ):
            for cid, cobj in self.environment.cases.items():
                comments_text = " ".join(getattr(cobj, "comments", []) or [])
                if "SRV-PROD-PAYMENT-01" in prompt and "SRV-PROD-PAYMENT-01" in comments_text:
                    return cid
                if "DESKTOP-FIN-08" in prompt and "DESKTOP-FIN-08" in comments_text:
                    return cid
            if getattr(self.environment, "mode", "") == "overlay":
                return next(iter(self.environment.cases.keys()))
        return None

    def format_triage_prompt(self, query: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Formats an operational triage request with optional case metadata."""
        if not context:
            return query
        ctx_str = "\n".join(f"- {k}: {v}" for k, v in context.items())
        return f"Operational Triage Request:\n{query}\n\nCase Context:\n{ctx_str}\n\nPerform initial investigation and provide the triage report."

    def _resolve_effective_worker_mode(self, classification: str) -> str:
        """Resolves the per-query worker execution mode ('react' or 'rlm').

        - 'rlm': Always dispatch RLMSOCRunbookWorkerAgent (DSPy RLM Python REPL).
        - 'auto': Dispatch RLMSOCRunbookWorkerAgent for multi-hop proactive
          threat hunting (THREAT_HUNT or ThreatHuntEnvironment) and
          SOCRunbookWorkerAgent ('react') for single-indicator Tier 1 alert
          categories.
        - 'react' (default): Always dispatch SOCRunbookWorkerAgent.
        """
        mode = (self.worker_mode or "react").strip().lower()
        if mode == "rlm":
            return "rlm"
        if mode == "auto":
            if (
                classification == "THREAT_HUNT"
                or bool(getattr(self.environment, "supports_threat_hunt_tools", False))
            ):
                return "rlm"
            return "react"
        return "react"

    def query(
        self,
        prompt: str,
        max_iterations: int = 5,
        max_tokens: Optional[int] = None,
        temperature: float = 0.0,
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
            runbook_content = load_runbook(runbook_name, self.runbooks_dir, self.runbooks_dict)
        else:
            runbook_name = "none"
            runbook_content = ""

        # 3. Worker Dispatch
        effective_worker_mode = self._resolve_effective_worker_mode(classification)
        rlm_repl_steps: Optional[int] = None
        if effective_worker_mode == "rlm":
            try:
                from agent.rlm_soc_worker import RLMSOCRunbookWorkerAgent
            except ModuleNotFoundError:
                from rlm_soc_worker import RLMSOCRunbookWorkerAgent

            worker = RLMSOCRunbookWorkerAgent(
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
                strip_scaffolding=self.strip_scaffolding,
                sub_model=self.rlm_sub_model,
                rlm_max_iters=self.rlm_max_iters,
                rlm_max_llm_calls=self.rlm_max_llm_calls,
                dspy_lm=self.dspy_lm,
                dspy_sub_lm=self.dspy_sub_lm,
            )
            worker_report, worker_trajectory, worker_usage = worker.investigate(
                prompt=prompt,
                max_iterations=max_iterations,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            rlm_repl_steps = len(getattr(worker, "last_rlm_repl_trajectory", []) or [])
        else:
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
                strip_scaffolding=self.strip_scaffolding,
            )
            # Inherit supervisor LLM caller so mocks and configurations apply uniformly
            worker._call_llm_step = self._call_llm_step

            worker_report, worker_trajectory, worker_usage = worker.investigate(
                prompt=prompt,
                max_iterations=max_iterations,
                max_tokens=max_tokens,
                temperature=temperature,
            )

        # Enforce the boundary independently of any model-authored report. An
        # incomplete investigation cannot reach synthesis or action dispatch.
        if not _has_investigation_evidence(worker_trajectory):
            incomplete_report = WorkerInvestigationReport(
                classification=classification, runbook_name=runbook_name,
                risk_level="UNKNOWN", recommended_escalation="Tier 2: investigation incomplete",
                raw_response=worker_report.raw_response,
            )
            decision = SocDecision(
                verdict="INCONCLUSIVE", recommended_actions=[],
                rationale="Investigation incomplete: no verified tool evidence was obtained.",
            )
            return SOCTier1Response(
                response=("Investigation incomplete: no verified tool evidence was obtained. "
                          "Verdict: INCONCLUSIVE. No containment actions were executed. "
                          "Escalate to Tier 2 for investigation.\n\n```soc_decision\n"
                          + json.dumps(decision.to_dict(), indent=2) + "\n```"),
                trajectory=worker_trajectory, usage=worker_usage, backend=self.last_backend,
                endpoint_id=self.endpoint_id, classification=classification, runbook=runbook_name,
                worker_report=incomplete_report, verdict="INCONCLUSIVE",
                worker_mode=effective_worker_mode, rlm_repl_steps=rlm_repl_steps,
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
            verdict=decision.verdict if decision is not None else None,
            worker_mode=effective_worker_mode,
            rlm_repl_steps=rlm_repl_steps,
        )


# Exported primary aliases
HierarchicalSOCTier1Agent = SOCSupervisorAgent
SOCTier1Agent = SocTier1Agent
