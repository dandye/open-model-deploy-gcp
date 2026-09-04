"""GEPA (Genetic Engine for Prompt Ad-hoc Optimization) for Incident Response Runbooks.

This module provides data structures, seed runbook loaders, serialization utilities,
and multi-objective fitness metrics for evolving cybersecurity incident response runbooks.
"""

import argparse
from collections.abc import Mapping, Sequence
import json
import math
import os
from pathlib import Path
import re
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import gepa

try:
    from agent.hierarchical_soc_agent import HierarchicalSOCTier1Agent
    from agent.soc_environment import SocEnvironment
    from agent.soc_tier1_agent import extract_soc_decision
except ModuleNotFoundError:
    from hierarchical_soc_agent import HierarchicalSOCTier1Agent
    from soc_environment import SocEnvironment
    from soc_tier1_agent import extract_soc_decision

from scripts.eval_soc_agent import evaluate_assertions
from scripts.eval_trajectory_verifier import verify_agent_trajectory
DEFAULT_RUNBOOKS_DIR = (
    ROOT_DIR / "third_party" / "ai-runbooks" / ".clinerules" / "run_books"
)

CORE_RUNBOOKS: List[str] = [
    "basic_ioc_enrichment.md",
    "suspicious_login_triage.md",
    "malware_triage.md",
    "lateral_movement_hunt_psexec_wmi.md",
]


def load_seed_runbooks(
    runbooks_dir: Optional[Union[str, Path]] = None,
) -> Dict[str, str]:
    """Load the core seed runbooks from disk.

    Args:
        runbooks_dir: Path to directory containing runbooks. Defaults to DEFAULT_RUNBOOKS_DIR.

    Returns:
        Dict mapping runbook filename to markdown string content.

    Raises:
        FileNotFoundError: If any core runbook file is missing.
    """
    source_dir = Path(runbooks_dir) if runbooks_dir is not None else DEFAULT_RUNBOOKS_DIR

    candidate: Dict[str, str] = {}
    for runbook_name in CORE_RUNBOOKS:
        file_path = source_dir / runbook_name
        if not file_path.exists():
            raise FileNotFoundError(
                f"Core runbook {runbook_name} not found in directory: {source_dir}"
            )
        candidate[runbook_name] = file_path.read_text(encoding="utf-8")

    return candidate


def save_runbooks(
    candidate: Dict[str, str],
    output_dir: Union[str, Path],
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Write candidate runbooks and optional evolution metadata to output directory.

    Args:
        candidate: Dict mapping runbook filename to markdown content.
        output_dir: Directory where runbooks and metadata should be written.
        metadata: Optional metadata dictionary saved as evolution_metadata.json.
    """
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    for filename, content in candidate.items():
        file_path = target_dir / filename
        file_path.write_text(content, encoding="utf-8")

    if metadata is not None:
        meta_path = target_dir / "evolution_metadata.json"
        meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def calculate_loss_penalty(
    expected_label: str,
    actual_verdict: str,
    executed_actions: List[str],
    prohibited_actions: List[str],
) -> float:
    """Calculate operational loss penalty score.

    Penalizes prohibited actions and classification errors:
    - If prohibited action executed: +10000.0 loss
    - If false positive (verdict MALICIOUS when expected BENIGN): +5000.0 loss
    - If false negative (verdict BENIGN when expected MALICIOUS): +10000.0 loss

    Score formula: exp(-loss / 10000.0)

    Args:
        expected_label: Expected ground truth label (BENIGN or MALICIOUS).
        actual_verdict: Actual model triage verdict (BENIGN, MALICIOUS, SUSPICIOUS, etc.).
        executed_actions: List of action names executed by agent.
        prohibited_actions: List of prohibited action names for this case.

    Returns:
        Penalty score between 0.0 and 1.0 (1.0 = zero loss).
    """
    loss = 0.0

    prohibited_set = set(prohibited_actions or [])
    if any(action in prohibited_set for action in (executed_actions or [])):
        loss += 10000.0

    norm_expected = (expected_label or "").strip().upper()
    norm_actual = (actual_verdict or "").strip().upper()

    if norm_actual == "MALICIOUS" and norm_expected == "BENIGN":
        loss += 5000.0
    elif norm_actual == "BENIGN" and norm_expected == "MALICIOUS":
        loss += 10000.0

    return math.exp(-loss / 10000.0)


def calculate_case_fitness(
    rubric_score: float,
    assertions_passed: bool,
    operator_compliance: float,
    loss_penalty: float,
) -> float:
    """Calculate multi-objective case fitness score.

    Formula:
        0.40 * rubric_score + 0.20 * (1.0 if assertions_passed else 0.0)
        + 0.20 * operator_compliance + 0.20 * loss_penalty

    Args:
        rubric_score: Normalized rubric score between 0.0 and 1.0.
        assertions_passed: Boolean indicating whether all deterministic assertions passed.
        operator_compliance: Normalized compliance score between 0.0 and 1.0.
        loss_penalty: Loss penalty score between 0.0 and 1.0.

    Returns:
        Weighted composite fitness score.
    """
    assert_score = 1.0 if assertions_passed else 0.0
    fitness = (
        0.40 * float(rubric_score)
        + 0.20 * assert_score
        + 0.20 * float(operator_compliance)
        + 0.20 * float(loss_penalty)
    )
    return fitness


class GoogleGenAILM:
    """LanguageModel implementation using Google GenAI SDK for GEPA reflective mutation."""

    def __init__(
        self,
        model: str = "gemini-2.5-pro",
        project_id: Optional[str] = None,
        location: str = "us-central1",
        client: Optional[Any] = None,
    ):
        self.model = model
        self.project_id = project_id
        self.location = location
        if client is not None:
            self.client = client
        else:
            try:
                from google import genai
                self.client = genai.Client(
                    project=self.project_id,
                    location=self.location,
                    vertexai=True,
                )
            except Exception:
                self.client = None

    def __call__(self, prompt: Union[str, List[Dict[str, Any]]]) -> str:
        """Execute model generation for a prompt string or chat message list."""
        if isinstance(prompt, str):
            contents: Any = prompt
        elif isinstance(prompt, list):
            parts = []
            for item in prompt:
                if isinstance(item, dict):
                    role = item.get("role", "user")
                    text = item.get("content", "")
                    parts.append(f"{role}: {text}")
                else:
                    parts.append(str(item))
            contents = "\n".join(parts)
        else:
            contents = str(prompt)

        if self.client is None:
            raise RuntimeError("Google GenAI client is not configured.")

        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config={"temperature": 0.2},
        )
        return getattr(response, "text", "") or str(response or "")


FORBIDDEN_EVAL_HOSTNAMES: List[str] = [
    "GW-CORE-VPN-01",
    "SRV-PROD-PAYMENT-01",
    "DESKTOP-FIN-08",
    "SRV-DATA-01",
    "SRV-DC-01",
    "LAPTOP-CFO-01",
]

SHORT_CIRCUIT_PATTERNS: List[str] = [
    r"skip\s+(?:all\s+)?enrichment",
    r"skip\s+(?:all\s+)?investigation",
    r"skip\s+steps?\s+\d+",
    r"proceed\s+directly\s+to\s+step\s+\d+",
]

IPV4_LITERAL_REGEX: re.Pattern = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(?:/(?:[1-2]?\d|3[0-2]))?\b"
)


def validate_runbook_candidate(
    candidate: Dict[str, str],
    forbidden_hostnames: Optional[List[str]] = None,
) -> Tuple[bool, List[str]]:
    """Validates a candidate runbook set against anti-memorization guardrails.

    Rejects candidate runbooks containing:
    1. Literal IPv4 addresses or CIDR blocks (except 127.0.0.1/0.0.0.0).
    2. Hardcoded evaluation benchmark hostnames.
    3. Short-circuit / bypass directives (e.g. 'skip all enrichment').

    Args:
        candidate: Mapping of runbook filenames to markdown content.
        forbidden_hostnames: Optional list of static hostnames to prohibit.

    Returns:
        Tuple of (is_valid: bool, violations: List[str]).
    """
    violations: List[str] = []
    hostnames_to_check = forbidden_hostnames or FORBIDDEN_EVAL_HOSTNAMES

    for filename, content in candidate.items():
        cleaned_content = re.sub(r"\(e\.g\.[^)]*\)", "", content, flags=re.IGNORECASE)
        found_ips = IPV4_LITERAL_REGEX.findall(cleaned_content)
        for ip in found_ips:
            if ip not in ("127.0.0.1", "0.0.0.0"):
                violations.append(
                    f"{filename}: Contains hardcoded IPv4 literal '{ip}'. Runbooks must express network scopes via generic variables or telemetry query classifications."
                )

        for hostname in hostnames_to_check:
            if re.search(rf"\b{re.escape(hostname)}\b", cleaned_content, re.IGNORECASE):
                violations.append(
                    f"{filename}: Contains hardcoded evaluation benchmark hostname '{hostname}'. Runbooks must reference assets via dynamic context."
                )

        for pattern in SHORT_CIRCUIT_PATTERNS:
            match = re.search(pattern, cleaned_content, re.IGNORECASE)
            if match:
                violations.append(
                    f"{filename}: Contains short-circuit investigation directive '{match.group(0)}'. Epistemic enrichment tools must never be bypassed."
                )

    return (len(violations) == 0, violations)


class RunbookGEPAAdapter(gepa.GEPAAdapter):
    """GEPA adapter for evaluating and reflectively refining incident response runbooks."""

    def __init__(
        self,
        task_lm: str = "gemini-2.5-flash-lite",
        project_id: Optional[str] = None,
        region: str = "us-central1",
        use_live_mcp: bool = False,
        max_iterations: int = 5,
        agent_factory: Optional[Callable[..., Any]] = None,
    ):
        self.task_lm = task_lm
        resolved_project_id = (
            project_id
            or os.environ.get("PROJECT_ID")
            or os.environ.get("GCP_PROJECT_ID")
            or os.environ.get("GOOGLE_CLOUD_PROJECT")
        )
        if not resolved_project_id:
            try:
                import google.auth
                _, default_project = google.auth.default()
                resolved_project_id = default_project
            except Exception:
                pass
        self.project_id = resolved_project_id or ""
        self.region = region
        self.use_live_mcp = use_live_mcp
        self.max_iterations = max_iterations
        self.agent_factory = agent_factory or HierarchicalSOCTier1Agent

    def evaluate(
        self,
        batch: List[Dict[str, Any]],
        candidate: Dict[str, str],
        capture_traces: bool = False,
    ) -> gepa.EvaluationBatch:
        """Evaluates runbook candidate against a batch of evaluation cases."""
        outputs: List[str] = []
        scores: List[float] = []
        trajectories: List[Dict[str, Any]] = []

        is_valid, violations = validate_runbook_candidate(candidate)
        if not is_valid:
            rejection_msg = (
                "Candidate rejected by anti-memorization validator. Violations:\n"
                + "\n".join(f"- {v}" for v in violations)
            )
            for case in batch:
                outputs.append(rejection_msg)
                scores.append(0.0)
                trajectories.append({
                    "case_id": case.get("eval_id", ""),
                    "alert_type": case.get("name", ""),
                    "prompt": case.get("prompt", ""),
                    "cmdb_context": case.get("cmdb_context", {}),
                    "expected_verdict": case.get("ground_truth_label", ""),
                    "expected_actions": case.get("expected_actions", []),
                    "prohibited_actions": case.get("prohibited_actions", []),
                    "actual_verdict": "REJECTED_MEMORIZED",
                    "executed_actions": [],
                    "summary": rejection_msg,
                    "score": 0.0,
                    "loss_penalty": 0.0,
                    "assert_passed": False,
                    "component_name": "",
                    "trajectory": [],
                })
            return gepa.EvaluationBatch(
                outputs=outputs,
                scores=scores,
                trajectories=trajectories,
            )

        for case in batch:
            try:
                env = None
                if not self.use_live_mcp:
                    env = SocEnvironment()

                agent = self.agent_factory(
                    runbooks_dict=candidate,
                    environment=env,
                    managed_model=self.task_lm,
                    project_id=self.project_id,
                    region=self.region,
                    use_live_mcp=self.use_live_mcp,
                )

                prompt = case.get("prompt", "")
                response = agent.query(prompt, max_iterations=self.max_iterations)

                resp_text = getattr(response, "response", "") or ""
                agent_traj = getattr(response, "trajectory", []) or []

                traj_verif = verify_agent_trajectory(
                    trajectory=agent_traj,
                    expected_actions=case.get("expected_actions", []),
                    prohibited_actions=case.get("prohibited_actions", []),
                    expected_entities=case.get("expected_entities", []),
                    response_text=resp_text,
                )

                assertions = case.get("assertions", {}) or {}
                must_contain = assertions.get("must_contain", [])
                must_not_contain = assertions.get("must_not_contain", [])
                assert_passed, _ = evaluate_assertions(
                    resp_text,
                    must_contain=must_contain,
                    must_not_contain=must_not_contain,
                )

                epistemic_pts = 25.0 * min(1.0, traj_verif.epistemic_step_count / 1.0)
                if traj_verif.operator_actions_matched:
                    action_pts = 25.0
                elif traj_verif.advisor_actions_matched:
                    action_pts = 12.5
                else:
                    action_pts = 0.0

                assertion_pts = 25.0 * (1.0 if assert_passed else 0.0)
                rubric_normalized = (epistemic_pts + action_pts + assertion_pts + 25.0) / 100.0

                actual_verdict = ""
                if hasattr(response, "get"):
                    actual_verdict = response.get("verdict", "")
                if not actual_verdict:
                    decision_obj = extract_soc_decision(resp_text)
                    if decision_obj is not None:
                        actual_verdict = getattr(decision_obj, "verdict", "")

                loss_penalty = calculate_loss_penalty(
                    expected_label=case.get("ground_truth_label", ""),
                    actual_verdict=actual_verdict,
                    executed_actions=traj_verif.executed_actions,
                    prohibited_actions=case.get("prohibited_actions", []),
                )

                op_compliance = 1.0 if traj_verif.operator_actions_matched else 0.0
                fitness = calculate_case_fitness(
                    rubric_score=rubric_normalized,
                    assertions_passed=assert_passed,
                    operator_compliance=op_compliance,
                    loss_penalty=loss_penalty,
                )

                outputs.append(resp_text)
                scores.append(fitness)

                if capture_traces:
                    trajectories.append({
                        "case_id": case.get("eval_id", case.get("id", "")),
                        "alert_type": case.get("alert_type", getattr(response, "classification", "")),
                        "prompt": prompt,
                        "cmdb_context": case.get("cmdb_context", {}),
                        "expected_verdict": case.get("ground_truth_label", ""),
                        "expected_actions": case.get("expected_actions", []),
                        "prohibited_actions": case.get("prohibited_actions", []),
                        "actual_verdict": actual_verdict,
                        "executed_actions": traj_verif.executed_actions,
                        "summary": f"Case evaluated. Fitness: {fitness:.3f}, loss_penalty: {loss_penalty:.3f}, assert_passed: {assert_passed}",
                        "score": fitness,
                        "loss_penalty": loss_penalty,
                        "assert_passed": assert_passed,
                        "component_name": getattr(response, "runbook", ""),
                        "trajectory": agent_traj,
                    })

            except Exception as e:
                import traceback
                traceback.print_exc(file=sys.stderr)
                outputs.append(f"Evaluation error: {e}")
                scores.append(0.0)
                if capture_traces:
                    trajectories.append({
                        "case_id": case.get("eval_id", case.get("id", "")),
                        "alert_type": case.get("alert_type", ""),
                        "prompt": case.get("prompt", ""),
                        "cmdb_context": case.get("cmdb_context", {}),
                        "expected_verdict": case.get("ground_truth_label", ""),
                        "expected_actions": case.get("expected_actions", []),
                        "prohibited_actions": case.get("prohibited_actions", []),
                        "actual_verdict": "ERROR",
                        "executed_actions": [],
                        "summary": f"Exception encountered during evaluation: {e}",
                        "score": 0.0,
                        "loss_penalty": 0.0,
                        "assert_passed": False,
                        "component_name": "",
                        "trajectory": [],
                    })

        return gepa.EvaluationBatch(
            outputs=outputs,
            scores=scores,
            trajectories=trajectories if capture_traces else None,
        )

    def make_reflective_dataset(
        self,
        candidate: Dict[str, str],
        eval_batch: gepa.EvaluationBatch,
        components_to_update: List[str],
    ) -> Mapping[str, Sequence[Mapping[str, Any]]]:
        """Builds diagnostic reflection records for teacher model runbook revision."""
        dataset: Dict[str, List[Dict[str, Any]]] = {name: [] for name in components_to_update}
        trajectories = eval_batch.trajectories or []

        for comp_name in components_to_update:
            for trace in trajectories:
                trace_comp = trace.get("component_name", "")
                # If trace specifies component_name, check match; otherwise match via classification or allow all
                if trace_comp and trace_comp != comp_name:
                    continue

                score = trace.get("score", 1.0)
                loss_pen = trace.get("loss_penalty", 1.0)
                assert_pass = trace.get("assert_passed", True)

                # Filter to underperforming cases
                if score >= 0.95 and loss_pen >= 1.0 and assert_pass:
                    continue

                prompt = trace.get("prompt", "")
                executed_actions = trace.get("executed_actions", [])
                prohibited_actions = trace.get("prohibited_actions", [])
                case_id = trace.get("case_id", "")

                feedback_items: List[str] = []

                if "isolate_host" in executed_actions and "isolate_host" in prohibited_actions:
                    feedback_items.append(
                        "False positive operational disruption: The agent executed prohibited host isolation on an asset requiring safe resolution. "
                        "The runbook must guide the agent to perform epistemic verification (checking CMDB asset role, network routing classification, and corroborating SIEM events) "
                        "before taking disruptive containment actions."
                    )
                elif "MALICIOUS" in trace.get("expected_verdict", "").upper() and "isolate_host" not in executed_actions:
                    feedback_items.append(
                        "Missed containment: Confirmed active malware or C2 activity requires immediate host isolation. "
                        "The runbook must mandate host isolation for confirmed malicious threats."
                    )
                else:
                    feedback_items.append(
                        f"Triage operational failure: score={score:.2f}, loss_penalty={loss_pen:.2f}. "
                        f"Prohibited actions executed: {[a for a in executed_actions if a in prohibited_actions]}. "
                        "The runbook instructions should be clarified to avoid prohibited actions, gather verified telemetry, and adhere to operational guardrails."
                    )

                record = {
                    "Inputs": {
                        "case_id": case_id,
                        "alert_type": trace.get("alert_type", ""),
                        "prompt": prompt,
                        "cmdb_context": trace.get("cmdb_context", {}),
                        "expected_verdict": trace.get("expected_verdict", ""),
                        "expected_actions": trace.get("expected_actions", []),
                        "prohibited_actions": prohibited_actions,
                    },
                    "Generated Outputs": {
                        "actual_verdict": trace.get("actual_verdict", ""),
                        "executed_actions": executed_actions,
                        "summary": trace.get("summary", ""),
                    },
                    "Feedback": " ".join(feedback_items),
                }
                dataset[comp_name].append(record)

        return dataset


def build_reflection_prompt_template() -> str:
    """Build domain-specific reflection prompt template for GEPA mutation.

    Instructs the reflection LM to refine the active runbook with procedural
    epistemic verification steps, asset inventory correlation, and threat
    intelligence reputation, while strictly forbidding hardcoded network literals,
    hostnames, short-circuit bypasses, and emojis.

    Returns:
        Template string containing placeholders <curr_param> and <side_info>.
    """
    return (
        "You are an expert Security Operations Center (SOC) engineering teacher tasked with refining\n"
        "cybersecurity incident response runbooks to optimize Tier 1 autonomous agent performance.\n\n"
        "Here is the active incident response runbook component to improve:\n"
        "```markdown\n"
        "<curr_param>\n"
        "```\n\n"
        "The following diagnostic evaluation traces contain cases where the autonomous agent underperformed,\n"
        "including case context, inputs, actual actions, and concrete feedback:\n"
        "```\n"
        "<side_info>\n"
        "```\n\n"
        "Refinement Guidelines and Operational Guardrails:\n"
        "1. Epistemic Evidence Verification Sequence: Refine the runbook into a disciplined 4-stage procedural flow:\n"
        "   - Stage A: Asset Identity & CMDB Context: Query lookup_entity to determine asset business role, criticality, and authorized tags.\n"
        "   - Stage B: Network Routing & Scope Verification: Query get_ip_address_report or get_domain_report to determine if target infrastructure is public, private, or reserved documentation space.\n"
        "   - Stage C: Threat Intelligence Reputation: Check GTI reputation scores and known malware associations.\n"
        "   - Stage D: Corroboration of Malicious Activity: Correlate telemetry with observed behaviors (e.g. active malware, C2 beaconing vs benign scanning).\n"
        "2. Mandatory Epistemic Investigation (No Short-Circuits): Forbid instructions that tell the analyst to 'skip all enrichment' or 'bypass investigation'. The analyst must always execute telemetry queries to substantiate their findings.\n"
        "3. Anti-Memorization Rule (Generalization): Strictly DO NOT hardcode specific IP addresses, CIDR blocks, domain names, or hostnames in the runbook. All triage logic must rely on dynamic variables (e.g. ${IOC_VALUE}, ${ASSET_ROLE}, ${IP_ROUTING_TYPE}).\n"
        "4. Strict Malicious Containment: Maintain unambiguous containment protocols (isolate_host, block_indicator) when high-severity malicious activity is corroborated.\n"
        "5. Output Standards: Output exclusively the refined markdown runbook without conversational preamble.\n"
        "6. Strictly NO EMOJIS: Do not include any emojis anywhere in the runbook content or markdown headings.\n\n"
        "Provide the complete revised runbook inside ```markdown blocks."
    )


def build_arg_parser() -> argparse.ArgumentParser:
    """Build command-line argument parser for GEPA runbook optimization.

    Returns:
        Configured ArgumentParser.
    """
    parser = argparse.ArgumentParser(
        description="Evolve SOC incident response runbooks using GEPA Pareto optimization."
    )
    parser.add_argument(
        "--max-metric-calls",
        type=int,
        default=15,
        help="Maximum metric evaluation calls (default: 15).",
    )
    parser.add_argument(
        "--task-lm",
        type=str,
        default="gemini-2.5-flash-lite",
        help="Task model flavor or name for agent triage (default: gemini-2.5-flash-lite).",
    )
    parser.add_argument(
        "--reflection-lm",
        type=str,
        default="gemini-2.5-pro",
        help="Teacher model for reflective mutation (default: gemini-2.5-pro).",
    )
    project_default = (
        os.environ.get("PROJECT_ID")
        or os.environ.get("GCP_PROJECT_ID")
        or os.environ.get("GOOGLE_CLOUD_PROJECT")
    )
    if not project_default:
        try:
            import google.auth
            _, default_project = google.auth.default()
            project_default = default_project
        except Exception:
            pass
    project_default = project_default or ""
    region_default = os.environ.get("REGION", "us-central1")
    parser.add_argument(
        "--project-id",
        type=str,
        default=project_default,
        help=f"Google Cloud Project ID (default: {project_default}).",
    )
    parser.add_argument(
        "--region",
        type=str,
        default=region_default,
        help=f"Google Cloud Region (default: {region_default}).",
    )
    parser.add_argument(
        "--evalset",
        type=str,
        default="configs/evals/gen3/soc_tier1_interactive.json",
        help="Path to evaluation dataset JSON (default: configs/evals/gen3/soc_tier1_interactive.json).",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="configs/runbooks/gepa_evolved",
        help="Output directory for evolved runbooks (default: configs/runbooks/gepa_evolved).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for optimization reproducibility (default: 42).",
    )
    parser.add_argument(
        "--split-train-val",
        action="store_true",
        default=False,
        help="Split dataset into separate train and validation subsets (default: False, optimizes on full dataset).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Execute single evaluation batch on sample cases without mutation.",
    )
    return parser


def main(args: Optional[List[str]] = None) -> int:
    """CLI entrypoint for GEPA runbook optimization.

    Args:
        args: Optional list of CLI arguments (uses sys.argv[1:] if None).

    Returns:
        0 on success, non-zero on failure.
    """
    parser = build_arg_parser()
    parsed_args = parser.parse_args(args)

    print(f"Loading seed runbooks from {DEFAULT_RUNBOOKS_DIR}...")
    seed_candidate = load_seed_runbooks()

    evalset_path = ROOT_DIR / parsed_args.evalset if not Path(parsed_args.evalset).is_absolute() else Path(parsed_args.evalset)
    if not evalset_path.exists():
        print(f"Evaluation dataset not found: {evalset_path}", file=sys.stderr)
        return 1

    eval_data = json.loads(evalset_path.read_text(encoding="utf-8"))
    eval_cases = eval_data.get("eval_cases", [])
    if not eval_cases:
        print(f"No evaluation cases found in: {evalset_path}", file=sys.stderr)
        return 1

    if getattr(parsed_args, "split_train_val", False):
        split_index = min(6, len(eval_cases))
        trainset = eval_cases[:split_index]
        valset = eval_cases[split_index:] if split_index < len(eval_cases) else eval_cases[:split_index]
    else:
        trainset = eval_cases
        valset = eval_cases

    output_dir = ROOT_DIR / parsed_args.output_dir if not Path(parsed_args.output_dir).is_absolute() else Path(parsed_args.output_dir)

    adapter = RunbookGEPAAdapter(
        task_lm=parsed_args.task_lm,
        project_id=parsed_args.project_id,
        region=parsed_args.region,
        agent_factory=HierarchicalSOCTier1Agent,
    )

    if parsed_args.dry_run:
        print("Dry run mode enabled: executing single evaluation batch on 2 cases...")
        dry_batch = eval_cases[:2]
        eval_batch = adapter.evaluate(dry_batch, seed_candidate, capture_traces=True)
        print(f"Dry run complete. Evaluated {len(eval_batch.scores)} cases.")
        for i, score in enumerate(eval_batch.scores):
            print(f"  Case {i + 1} score: {score:.3f}")
        return 0

    reflection_lm = GoogleGenAILM(
        model=parsed_args.reflection_lm,
        project_id=parsed_args.project_id,
        location=parsed_args.region,
    )

    reflection_prompt_template = build_reflection_prompt_template()

    print(f"Starting GEPA optimization (max_metric_calls={parsed_args.max_metric_calls}, seed={parsed_args.seed})...")
    result = gepa.optimize(
        seed_candidate=seed_candidate,
        trainset=trainset,
        valset=valset,
        adapter=adapter,
        reflection_lm=reflection_lm,
        max_metric_calls=parsed_args.max_metric_calls,
        reflection_prompt_template=reflection_prompt_template,
        candidate_selection_strategy="pareto",
        seed=parsed_args.seed,
    )

    # Select the Pareto-evolved candidate over the unmutated seed when proposals exist
    best_candidate = seed_candidate
    if hasattr(result, "candidates") and len(result.candidates) > 1:
        best_candidate = result.candidates[-1]
    elif hasattr(result, "best_candidate"):
        best_candidate = result.best_candidate
    metadata: Dict[str, Any] = {
        "task_lm": parsed_args.task_lm,
        "reflection_lm": parsed_args.reflection_lm,
        "max_metric_calls": parsed_args.max_metric_calls,
        "seed": parsed_args.seed,
    }
    if hasattr(result, "best_score"):
        metadata["best_score"] = getattr(result, "best_score")

    print(f"Saving evolved runbooks to {output_dir}...")
    save_runbooks(candidate=best_candidate, output_dir=output_dir, metadata=metadata)
    print("Runbook evolution complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

