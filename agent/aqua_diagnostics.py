"""Two-Stage AQuA Trajectory Diagnosis and Clustering Engine for GEPA Runbook Optimization.

Provides structured root-cause attribution, stage-level procedural failure mapping,
and anti-memorization sanitized prompt blocks for reflective mutation in SOC agent runbooks.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from agent.hierarchical_soc_agent import (
    CLASSIFICATION_RUNBOOK_MAP,
    DEFAULT_FALLBACK_RUNBOOK,
)
from agent.jev_evaluator import SOC_FAILURE_TAXONOMY
from scripts.eval_trajectory_verifier import is_epistemic_tool

ROOT_DIR = Path(__file__).resolve().parent.parent

# Procedural stages of runbook execution
PROCEDURAL_STAGES: Tuple[str, ...] = (
    "STAGE_A_IDENTITY",
    "STAGE_B_ROUTING",
    "STAGE_C_THREAT_INTEL",
    "STAGE_D_CONTAINMENT",
)

CORE_RUNBOOKS: Tuple[str, ...] = (
    "basic_ioc_enrichment.md",
    "suspicious_login_triage.md",
    "malware_triage.md",
    "lateral_movement_hunt_psexec_wmi.md",
)

FORBIDDEN_EVAL_HOSTNAMES: Tuple[str, ...] = (
    "GW-CORE-VPN-01",
    "SRV-PROD-PAYMENT-01",
    "DESKTOP-FIN-08",
    "SRV-DATA-01",
    "SRV-DC-01",
    "LAPTOP-CFO-01",
)

IPV4_LITERAL_REGEX: re.Pattern = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(?:/(?:[1-2]?\d|3[0-2]))?\b"
)

CASE_ID_REGEX: re.Pattern = re.compile(
    r"\bCASE-(?:GEN\d+-[A-Z0-9_-]+|[A-Z0-9_-]*\d[A-Z0-9_-]*)\b", re.IGNORECASE
)

ALERT_TYPE_TO_RUNBOOK: Dict[str, str] = dict(CLASSIFICATION_RUNBOOK_MAP)

MIN_FORBIDDEN_LITERAL_LENGTH = 4


def compile_forbidden_literals(
    literals: Optional[Sequence[str]],
) -> Optional[re.Pattern]:
    """One case-insensitive alternation over the manifest literals, longest first, bounded so that
    `evil.example` does not match inside `notevil.example` and `10.10.3.4` not inside `10.10.3.45`."""
    cleaned = sorted(
        {
            str(x).strip()
            for x in (literals or [])
            if len(str(x).strip()) >= MIN_FORBIDDEN_LITERAL_LENGTH
        },
        key=lambda s: (-len(s), s),
    )
    if not cleaned:
        return None
    body = "|".join(re.escape(x) for x in cleaned)
    return re.compile(rf"(?<![A-Za-z0-9-])(?:{body})(?![A-Za-z0-9-])", re.IGNORECASE)


def sanitize_text(text: str, forbidden_literals: Sequence[str] = ()) -> str:
    """Strips case IDs, IPv4 literals (except loopback/zeros), forbidden hostnames and literals.

    Ensures zero evaluation benchmark memorization leaks into reflective prompts or summaries.
    """
    if not text:
        return ""

    sanitized = text

    # Strip CASE-... IDs
    sanitized = CASE_ID_REGEX.sub("[CASE_ID_REDACTED]", sanitized)

    # Strip IPv4 literals, preserving 127.0.0.1 and 0.0.0.0
    def _ip_replacer(match: re.Match) -> str:
        ip = match.group(0)
        if ip in ("127.0.0.1", "0.0.0.0"):
            return ip
        return "[IP_REDACTED]"

    sanitized = IPV4_LITERAL_REGEX.sub(_ip_replacer, sanitized)

    # Strip forbidden eval hostnames
    for hostname in FORBIDDEN_EVAL_HOSTNAMES:
        pattern = re.compile(rf"\b{re.escape(hostname)}\b", re.IGNORECASE)
        sanitized = pattern.sub("[HOSTNAME_REDACTED]", sanitized)

    # Strip custom forbidden literals
    lit_pattern = compile_forbidden_literals(forbidden_literals)
    if lit_pattern is not None:
        sanitized = lit_pattern.sub("[LITERAL_REDACTED]", sanitized)

    return sanitized


def sanitize_payload(
    payload: Any,
    forbidden_literals: Sequence[str] = (),
) -> Any:
    """Recursively scrubs strings in a dict/list/tuple/str payload using sanitize_text."""
    if isinstance(payload, str):
        return sanitize_text(payload, forbidden_literals=forbidden_literals)
    if isinstance(payload, Mapping):
        return {
            sanitize_text(str(k), forbidden_literals=forbidden_literals): sanitize_payload(
                v, forbidden_literals=forbidden_literals
            )
            for k, v in payload.items()
        }
    if isinstance(payload, list):
        return [sanitize_payload(item, forbidden_literals=forbidden_literals) for item in payload]
    if isinstance(payload, tuple):
        return tuple(sanitize_payload(item, forbidden_literals=forbidden_literals) for item in payload)
    return payload


@dataclass(frozen=True)
class AquaTraceDiagnosis:
    """Detailed per-trace diagnostic attribution."""

    case_id: str
    implicated_runbook: str
    failure_category: str
    implicated_stage: str
    zero_tool_hesitation: bool
    inert: bool
    prohibited_actions_executed: Tuple[str, ...]
    prohibited_entity_violations: Tuple[str, ...]
    missing_expected_actions: Tuple[str, ...]
    operational_loss_usd: float
    score: float
    root_cause_summary: str
    remediation_constraint: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AquaInsightCluster:
    """Clustered aggregate of procedural failures sharing runbook, failure category, and stage."""

    cluster_id: str
    implicated_runbook: str
    failure_category: str
    implicated_stage: str
    occurrence_count: int
    total_operational_loss_usd: float
    mean_score: float
    affected_case_ids: Tuple[str, ...]
    consolidated_root_cause: str
    targeted_mutation_instruction: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DiagnosticMutationDirective:
    """Mutation directive rendered into reflective dataset / prompt block."""

    runbook_name: str
    is_frozen: bool
    target_stages: Tuple[str, ...]
    primary_failure_categories: Tuple[str, ...]
    clusters: Tuple[AquaInsightCluster, ...]

    def render_prompt_block(self, forbidden_literals: Sequence[str] = ()) -> str:
        """Renders sanitized markdown prompt directive for runbook reflection."""
        if self.is_frozen:
            return (
                f"### Runbook: {self.runbook_name}\n"
                "LOCKED_PASSING_RUNBOOK: Do not modify; reproduce <curr_param> verbatim.\n"
                "All benchmark evaluation test cases on this runbook achieved flawless containment."
            )

        stages_str = ", ".join(self.target_stages)
        cats_str = ", ".join(self.primary_failure_categories)

        has_zero_tools = "PREMATURE_TERMINATION_ZERO_TOOLS" in self.primary_failure_categories

        lines = [
            f"### AQuA Diagnostic Cluster Summary for `{self.runbook_name}`",
            f"- Target Stages: {stages_str}",
            f"- Primary Failure Categories: {cats_str}",
        ]

        if has_zero_tools:
            lines.append(
                "- Mandatory Epistemic Tool Requirement: Before rendering any final verdict or containment, "
                "the agent MUST invoke at least one epistemic investigation tool (`lookup_entity`, "
                "`get_ip_address_report`, `get_domain_report`, `get_file_report`, or `list_cases`)."
            )

        lines.append("\n#### Targeted Mutation Instructions:")
        for idx, cluster in enumerate(self.clusters, 1):
            sanitized_instruction = sanitize_text(
                cluster.targeted_mutation_instruction, forbidden_literals=forbidden_literals
            )
            sanitized_root_cause = sanitize_text(
                cluster.consolidated_root_cause, forbidden_literals=forbidden_literals
            )
            lines.append(
                f"{idx}. Stage: `{cluster.implicated_stage}` | Failure: `{cluster.failure_category}` "
                f"(Impact: {cluster.occurrence_count} incidents, loss: ${cluster.total_operational_loss_usd:,.2f})\n"
                f"   - Root Cause: {sanitized_root_cause}\n"
                f"   - Directive: {sanitized_instruction}"
            )

        implicated_stage = ", ".join(self.target_stages) if self.target_stages else "STAGE_A_IDENTITY"
        lines.append(
            f"\nSurgical Constraint: Modify ONLY the implicated stage ({implicated_stage}) "
            "while preserving all other stages and markdown headings verbatim."
        )

        raw_block = "\n".join(lines)
        return sanitize_text(raw_block, forbidden_literals=forbidden_literals)


@dataclass(frozen=True)
class AquaDiagnosticReport:
    """Overall diagnostic and clustering report across an evaluation set."""

    total_cases: int
    failed_cases: int
    zero_tool_hesitation_cases: int
    inert_cases: int
    total_operational_loss_usd: float
    category_counts: Dict[str, int]
    diagnoses: Tuple[AquaTraceDiagnosis, ...]
    clusters: Tuple[AquaInsightCluster, ...]
    frozen_runbooks: Tuple[str, ...]
    directives: Dict[str, DiagnosticMutationDirective]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_cases": self.total_cases,
            "failed_cases": self.failed_cases,
            "zero_tool_hesitation_cases": self.zero_tool_hesitation_cases,
            "inert_cases": self.inert_cases,
            "total_operational_loss_usd": self.total_operational_loss_usd,
            "category_counts": self.category_counts,
            "diagnoses": [d.to_dict() for d in self.diagnoses],
            "clusters": [c.to_dict() for c in self.clusters],
            "frozen_runbooks": list(self.frozen_runbooks),
            "directives": {
                k: {
                    "runbook_name": v.runbook_name,
                    "is_frozen": v.is_frozen,
                    "target_stages": list(v.target_stages),
                    "primary_failure_categories": list(v.primary_failure_categories),
                    "clusters": [c.to_dict() for c in v.clusters],
                }
                for k, v in self.directives.items()
            },
        }


def resolve_implicated_runbook(trace: Mapping[str, Any]) -> str:
    """Deterministically maps a trace to one of CORE_RUNBOOKS."""
    # 1. Direct component or implicated_runbook name if valid
    for field_name in ("component_name", "implicated_runbook"):
        comp = trace.get(field_name)
        if comp and str(comp) in CORE_RUNBOOKS:
            return str(comp)

    # 2. Alert type mapping
    alert_type = str(trace.get("alert_type") or "").strip()
    if alert_type in CORE_RUNBOOKS:
        return alert_type
    if alert_type in ALERT_TYPE_TO_RUNBOOK:
        return ALERT_TYPE_TO_RUNBOOK[alert_type]

    # 3. Classify using SOCSupervisorAgent.classify_alert rules across trace metadata
    text_corpus = " ".join([
        str(trace.get("prompt") or ""),
        str(trace.get("name") or ""),
        str(trace.get("alert_type") or ""),
        str(trace.get("family_id") or ""),
        str(trace.get("case_id") or ""),
        str(trace.get("eval_id") or ""),
    ])
    p_lower = text_corpus.lower()

    lateral_keywords = (
        "psexec", "wmi", "wmic", "lateral movement", "lateral", "smb session",
        "remote execution", "pass-the-hash", "type 3 logon", "admin$",
        "remote process", "serviceinstalled",
    )
    if any(k in p_lower for k in lateral_keywords):
        return "lateral_movement_hunt_psexec_wmi.md"

    hash_regex = r"\b[a-fA-F0-9]{32}\b|\b[a-fA-F0-9]{40}\b|\b[a-fA-F0-9]{64}\b"
    malware_keywords = (
        "sha256", "md5", "sha1", "ransomware", "trojan", "malware",
        "binary", "mimikatz", "payload", "quarantine file",
        "revoked certificate", "unsigned binary", "malicious file", "hash",
    )
    has_hash = bool(re.search(hash_regex, text_corpus))
    if has_hash or any(k in p_lower for k in malware_keywords):
        is_beacon_subject = (
            "connecting repeatedly to" in p_lower
            or ("beacon" in p_lower and "domain" in p_lower)
        )
        if not is_beacon_subject or has_hash or "ransomware" in p_lower or "certificate" in p_lower:
            return "malware_triage.md"

    login_keywords = (
        "suspicious login", "impossible travel", "impossible_travel", "failed login",
        "untrusted location", "logon", "brute force", "authentication log",
        "auth attempt", "vpn authentication", "vpn login", "mfa", "login",
        "scanner noise", "authorized scanner", "qualys", "scanner",
    )
    if any(k in p_lower for k in login_keywords):
        # Do not misattribute RFC5737 / C2 gateway connection attempts that only mention VPN in the hostname
        if not ("rfc5737" in p_lower or "connecting repeatedly" in p_lower):
            return "suspicious_login_triage.md"

    return DEFAULT_FALLBACK_RUNBOOK


def extract_trace_diagnosis(
    trace: Mapping[str, Any],
    pass_threshold: float = 0.80,
    forbidden_literals: Sequence[str] = (),
) -> AquaTraceDiagnosis:
    """Diagnoses a single execution trace into a structured root cause and procedural stage."""
    case_id = str(trace.get("case_id") or trace.get("eval_id") or "UNKNOWN_CASE")
    implicated_runbook = resolve_implicated_runbook(trace)

    traj_verif = (
        trace.get("trajectory_verification")
        if isinstance(trace.get("trajectory_verification"), Mapping)
        else {}
    )
    soc_dec = (
        trace.get("soc_decision")
        if isinstance(trace.get("soc_decision"), Mapping)
        else {}
    )
    assertions_dict = (
        trace.get("assertions")
        if isinstance(trace.get("assertions"), Mapping)
        else {}
    )
    jev_eval_dict = (
        trace.get("jev_evaluation")
        if isinstance(trace.get("jev_evaluation"), Mapping)
        else {}
    )

    if trace.get("score") is not None:
        score = float(trace["score"])
    elif trace.get("gen5_reward") is not None:
        score = float(trace["gen5_reward"])
    elif trace.get("reward") is not None:
        score = float(trace["reward"])
    elif trace.get("rubric_score") is not None:
        raw_rubric = float(trace["rubric_score"])
        score = raw_rubric / 100.0 if raw_rubric > 1.0 else raw_rubric
    else:
        score = 0.0

    loss_penalty_val = trace.get("loss_penalty")
    loss_penalty = float(loss_penalty_val) if loss_penalty_val is not None else score

    raw_assert = trace.get("assert_passed")
    if raw_assert is None and "all_passed" in assertions_dict:
        raw_assert = assertions_dict.get("all_passed")
    assert_passed = bool(score >= pass_threshold if raw_assert is None else raw_assert)

    raw_passed = trace.get("passed")
    if raw_passed is not None:
        case_failed = not bool(raw_passed)
    else:
        case_failed = (not assert_passed) or (score < pass_threshold)

    expected_verdict = str(
        trace.get("expected_verdict") or trace.get("ground_truth_label") or ""
    ).strip().upper()
    if not expected_verdict and trace.get("ground_truth_threat") is not None:
        expected_verdict = "MALICIOUS" if trace.get("ground_truth_threat") else "BENIGN"

    actual_verdict = str(
        trace.get("actual_verdict") or soc_dec.get("verdict") or ""
    ).strip().upper()
    if not actual_verdict and trace.get("agent_threat_call") is not None:
        actual_verdict = "MALICIOUS" if trace.get("agent_threat_call") else "BENIGN"

    decision_outcome = str(trace.get("decision_outcome") or "").strip().upper()

    expected_actions = tuple(str(a) for a in (trace.get("expected_actions") or ()))
    raw_exec = trace.get("executed_actions")
    if raw_exec is None:
        raw_exec = traj_verif.get("executed_actions")
    executed_actions = tuple(str(a) for a in (raw_exec or ()))

    prohibited_actions = tuple(str(a) for a in (trace.get("prohibited_actions") or ()))
    raw_ent_viols = trace.get("prohibited_entity_violations")
    if raw_ent_viols is None:
        raw_ent_viols = traj_verif.get("prohibited_entity_violations")
    prohibited_entity_violations = tuple(str(v) for v in (raw_ent_viols or ()))

    trajectory = trace.get("trajectory") or []
    if not isinstance(trajectory, list):
        trajectory = []

    # Calculate epistemic steps
    if trace.get("epistemic_step_count") is not None:
        epistemic_steps = int(trace["epistemic_step_count"])
    elif traj_verif.get("epistemic_step_count") is not None:
        epistemic_steps = int(traj_verif["epistemic_step_count"])
    else:
        epistemic_steps = sum(
            1 for step in trajectory if isinstance(step, dict) and is_epistemic_tool(str(step.get("tool") or ""))
        )

    # Missing expected actions
    missing_expected = tuple(a for a in expected_actions if a not in executed_actions)

    # Prohibited actions executed
    prohibited_executed = tuple(a for a in executed_actions if a in prohibited_actions)

    # Taxonomy mapping from JEV choice if present
    jev_choice_raw = str(
        trace.get("jev_choice") or jev_eval_dict.get("primary_choice") or ""
    ).strip()
    jev_category = SOC_FAILURE_TAXONOMY.get(jev_choice_raw, jev_choice_raw)

    is_inert = bool(
        trace.get("inert", False)
        or traj_verif.get("inert", False)
        or jev_category == "INERT"
    )

    if isinstance(trace.get("zero_tool_hesitation"), bool):
        zero_tool_hesitation = bool(trace["zero_tool_hesitation"]) and not is_inert
    else:
        has_no_tools = (
            len(trajectory) == 0
            and epistemic_steps == 0
            and len(executed_actions) == 0
        )
        zero_tool_hesitation = bool(
            not is_inert
            and has_no_tools
            and not (len(expected_actions) == 0 and not case_failed)
        )

    failure_category = "FLAWLESS_CONTAINMENT"
    implicated_stage = "STAGE_A_IDENTITY"

    # Stage 1 Classification cascade
    if is_inert:
        failure_category = "INERT"
        implicated_stage = "STAGE_A_IDENTITY"
    elif zero_tool_hesitation:
        failure_category = "PREMATURE_TERMINATION_ZERO_TOOLS"
        implicated_stage = "STAGE_A_IDENTITY"
    elif prohibited_executed or prohibited_entity_violations or (
        case_failed and decision_outcome == "FALSE_POSITIVE"
    ) or (
        actual_verdict == "MALICIOUS" and expected_verdict == "BENIGN" and any("isolate" in a or "block" in a for a in executed_actions)
    ):
        failure_category = "OVER_CONTAINMENT_FALSE_ALARM"
        implicated_stage = "STAGE_D_CONTAINMENT"
    elif (
        "MALICIOUS" in expected_verdict and (
            any("isolate" in a or "block" in a for a in missing_expected) or actual_verdict == "BENIGN"
        )
    ) or (case_failed and decision_outcome == "FALSE_NEGATIVE"):
        failure_category = "MISSED_MALICIOUS_BREACH"
        implicated_stage = "STAGE_D_CONTAINMENT"
    elif case_failed and (
        "INCONCLUSIVE" in expected_verdict
        or any(k in f"{case_id} {trace.get('alert_type', '')} {trace.get('prompt', '')}".upper() for k in ("503", "TOOL_OUTAGE"))
    ):
        failure_category = "DEGRADED_MODE_FAILURE"
        implicated_stage = "STAGE_C_THREAT_INTEL"
    elif jev_category and jev_category in SOC_FAILURE_TAXONOMY.values() and jev_category != "FLAWLESS_CONTAINMENT":
        failure_category = jev_category
        stage_map = {
            "PREMATURE_TERMINATION_ZERO_TOOLS": "STAGE_A_IDENTITY",
            "RUNBOOK_PROCEDURAL_VIOLATION": "STAGE_B_ROUTING",
            "UNGROUNDED_HALLUCINATED_CLAIM": "STAGE_C_THREAT_INTEL",
            "DEGRADED_MODE_FAILURE": "STAGE_C_THREAT_INTEL",
            "OVER_CONTAINMENT_FALSE_ALARM": "STAGE_D_CONTAINMENT",
            "MISSED_MALICIOUS_BREACH": "STAGE_D_CONTAINMENT",
        }
        implicated_stage = stage_map.get(failure_category, "STAGE_B_ROUTING")
    elif case_failed:
        failure_category = "RUNBOOK_PROCEDURAL_VIOLATION"
        implicated_stage = "STAGE_B_ROUTING"
    else:
        failure_category = "FLAWLESS_CONTAINMENT"
        implicated_stage = "STAGE_D_CONTAINMENT"

    # Compute operational loss USD
    if trace.get("operational_loss_usd") is not None:
        operational_loss_usd = float(trace["operational_loss_usd"])
    elif trace.get("case_loss_usd") is not None:
        operational_loss_usd = float(trace["case_loss_usd"])
    elif failure_category == "FLAWLESS_CONTAINMENT":
        operational_loss_usd = 0.0
    else:
        if 0 < loss_penalty < 1.0:
            operational_loss_usd = -10000.0 * math.log(max(loss_penalty, 1e-9))
        elif loss_penalty <= 0.0:
            operational_loss_usd = 10000.0
        else:
            operational_loss_usd = 1000.0 * (1.0 - min(score, 1.0))
        if zero_tool_hesitation and operational_loss_usd == 0.0:
            operational_loss_usd = 500.0

    # Formulate root cause and remediation constraint
    if failure_category == "PREMATURE_TERMINATION_ZERO_TOOLS":
        root_cause_summary = (
            "Premature termination without invoking mandatory epistemic investigation tools. "
            "Agent concluded verdict immediately upon receiving alert context."
        )
        remediation_constraint = (
            "Mandate epistemic telemetry gathering via lookup_entity, get_ip_address_report, "
            "get_domain_report, or get_file_report prior to state evaluation."
        )
    elif failure_category == "OVER_CONTAINMENT_FALSE_ALARM":
        viol = ", ".join(prohibited_executed or prohibited_entity_violations) or "containment action"
        root_cause_summary = f"Over-containment on benign or unverified target ({viol})."
        remediation_constraint = (
            "Enforce strict evidence threshold before executing pragmatic containment actions "
            "(isolate_host, block_indicator)."
        )
    elif failure_category == "MISSED_MALICIOUS_BREACH":
        missing_str = ", ".join(missing_expected) or "host isolation / indicator blocking"
        root_cause_summary = f"Failed to execute required containment ({missing_str}) on confirmed malicious activity."
        remediation_constraint = (
            "Ensure confirmed malicious determinations immediately route to active containment."
        )
    elif failure_category == "DEGRADED_MODE_FAILURE":
        root_cause_summary = "Failed to handle tool failure, API outage, or degraded telemetry gracefully."
        remediation_constraint = (
            "Implement resilient fallback and state preservation when upstream enrichment tools return 503 or errors."
        )
    elif failure_category == "UNGROUNDED_HALLUCINATED_CLAIM":
        root_cause_summary = "Formulated claims or verdicts not supported by actual tool observations."
        remediation_constraint = "Verify that all verdict assertions are grounded directly in tool return payloads."
    elif failure_category == "RUNBOOK_PROCEDURAL_VIOLATION":
        root_cause_summary = "Procedural deviation from prescribed triage sequence or routing criteria."
        remediation_constraint = "Follow procedural stage routing strictly without skipping triage checks."
    elif failure_category == "INERT":
        root_cause_summary = "Inert trace: No investigative or pragmatic state advancement observed."
        remediation_constraint = "Activate investigation cycle on receipt of triage dispatch."
    else:
        root_cause_summary = "Flawless containment: all actions verified, zero procedural violations."
        remediation_constraint = "Maintain current verified procedural logic."

    # Sanitize root cause summary, remediation constraint, and entity violations
    clean_root_cause = sanitize_text(root_cause_summary, forbidden_literals=forbidden_literals)
    clean_remediation = sanitize_text(remediation_constraint, forbidden_literals=forbidden_literals)
    clean_entity_violations = tuple(
        sanitize_text(v, forbidden_literals=forbidden_literals) for v in prohibited_entity_violations
    )

    return AquaTraceDiagnosis(
        case_id=case_id,
        implicated_runbook=implicated_runbook,
        failure_category=failure_category,
        implicated_stage=implicated_stage,
        zero_tool_hesitation=zero_tool_hesitation,
        inert=is_inert,
        prohibited_actions_executed=prohibited_executed,
        prohibited_entity_violations=clean_entity_violations,
        missing_expected_actions=missing_expected,
        operational_loss_usd=operational_loss_usd,
        score=score,
        root_cause_summary=clean_root_cause,
        remediation_constraint=clean_remediation,
    )


def cluster_trace_diagnoses(
    traces: Sequence[Mapping[str, Any]],
    all_runbooks: Sequence[str] = CORE_RUNBOOKS,
    pass_threshold: float = 0.80,
    forbidden_literals: Sequence[str] = (),
    require_evaluated_to_freeze: bool = False,
) -> AquaDiagnosticReport:
    """Aggregates per-trace diagnoses into structured insight clusters and mutation directives."""
    diagnoses: List[AquaTraceDiagnosis] = []
    category_counts: Dict[str, int] = {}
    zero_tool_count = 0
    inert_count = 0
    failed_count = 0
    total_loss = 0.0

    for trace in traces:
        diag = extract_trace_diagnosis(
            trace,
            pass_threshold=pass_threshold,
            forbidden_literals=forbidden_literals,
        )
        diagnoses.append(diag)

        cat = diag.failure_category
        category_counts[cat] = category_counts.get(cat, 0) + 1

        if diag.zero_tool_hesitation:
            zero_tool_count += 1
        if diag.inert:
            inert_count += 1
        if cat != "FLAWLESS_CONTAINMENT":
            failed_count += 1
            total_loss += diag.operational_loss_usd

    # Cluster failures by (implicated_runbook, failure_category, implicated_stage)
    grouped: Dict[Tuple[str, str, str], List[AquaTraceDiagnosis]] = {}
    for d in diagnoses:
        if d.failure_category != "FLAWLESS_CONTAINMENT":
            key = (d.implicated_runbook, d.failure_category, d.implicated_stage)
            grouped.setdefault(key, []).append(d)

    clusters: List[AquaInsightCluster] = []
    for (runbook, cat, stage), group in grouped.items():
        key_str = f"{runbook}:{cat}:{stage}"
        cluster_id = hashlib.sha256(key_str.encode("utf-8")).hexdigest()[:12]
        count = len(group)
        group_loss = sum(x.operational_loss_usd for x in group)
        mean_score = sum(x.score for x in group) / count if count > 0 else 0.0
        affected_ids = tuple(x.case_id for x in group)

        # Consolidate distinct root causes and instructions across the cluster
        distinct_causes = list(dict.fromkeys(x.root_cause_summary for x in group))
        distinct_instructions = list(dict.fromkeys(x.remediation_constraint for x in group))
        consolidated_root_cause = " | ".join(distinct_causes)
        targeted_instruction = " ".join(distinct_instructions)

        clusters.append(
            AquaInsightCluster(
                cluster_id=cluster_id,
                implicated_runbook=runbook,
                failure_category=cat,
                implicated_stage=stage,
                occurrence_count=count,
                total_operational_loss_usd=group_loss,
                mean_score=mean_score,
                affected_case_ids=affected_ids,
                consolidated_root_cause=consolidated_root_cause,
                targeted_mutation_instruction=targeted_instruction,
            )
        )

    # Sort clusters deterministically: -loss, -occurrence, cluster_id
    clusters.sort(key=lambda c: (-c.total_operational_loss_usd, -c.occurrence_count, c.cluster_id))

    # Formulate directives per runbook
    runbooks_with_failures = {c.implicated_runbook for c in clusters}
    evaluated_runbooks = {d.implicated_runbook for d in diagnoses}
    if require_evaluated_to_freeze:
        frozen_runbooks: List[str] = [
            rb for rb in all_runbooks if rb in evaluated_runbooks and rb not in runbooks_with_failures
        ]
    else:
        frozen_runbooks = [rb for rb in all_runbooks if rb not in runbooks_with_failures]

    directives: Dict[str, DiagnosticMutationDirective] = {}
    for rb in all_runbooks:
        rb_clusters = tuple(c for c in clusters if c.implicated_runbook == rb)
        is_frozen = (rb in frozen_runbooks)

        target_stages = tuple(dict.fromkeys(c.implicated_stage for c in rb_clusters))
        primary_categories = tuple(dict.fromkeys(c.failure_category for c in rb_clusters))

        directives[rb] = DiagnosticMutationDirective(
            runbook_name=rb,
            is_frozen=is_frozen,
            target_stages=target_stages,
            primary_failure_categories=primary_categories,
            clusters=rb_clusters,
        )

    return AquaDiagnosticReport(
        total_cases=len(traces),
        failed_cases=failed_count,
        zero_tool_hesitation_cases=zero_tool_count,
        inert_cases=inert_count,
        total_operational_loss_usd=total_loss,
        category_counts=category_counts,
        diagnoses=tuple(diagnoses),
        clusters=tuple(clusters),
        frozen_runbooks=tuple(frozen_runbooks),
        directives=directives,
    )
