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

from agent.hierarchical_soc_agent import CLASSIFICATION_RUNBOOK_MAP
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

DEFAULT_FALLBACK_RUNBOOK: str = "basic_ioc_enrichment.md"

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
    r"\bCASE-(?:GEN\d+-[A-Z0-9-]*?\d+|\d+)\b", re.IGNORECASE
)

ALERT_TYPE_TO_RUNBOOK: Dict[str, str] = dict(CLASSIFICATION_RUNBOOK_MAP)

MIN_FORBIDDEN_LITERAL_LENGTH = 4


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
    cleaned_literals = sorted(
        {str(x).strip() for x in (forbidden_literals or []) if len(str(x).strip()) >= MIN_FORBIDDEN_LITERAL_LENGTH},
        key=lambda s: (-len(s), s),
    )
    if cleaned_literals:
        body = "|".join(re.escape(x) for x in cleaned_literals)
        lit_pattern = re.compile(rf"(?<![A-Za-z0-9-])(?:{body})(?![A-Za-z0-9-])", re.IGNORECASE)
        sanitized = lit_pattern.sub("[LITERAL_REDACTED]", sanitized)

    return sanitized


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

        implicated_stage = self.target_stages[0] if self.target_stages else "STAGE_A_IDENTITY"
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
    # 1. Direct component name if valid
    comp = trace.get("component_name")
    if comp and str(comp) in CORE_RUNBOOKS:
        return str(comp)

    # 2. Alert type mapping
    alert_type = str(trace.get("alert_type") or "").strip()
    if alert_type in ALERT_TYPE_TO_RUNBOOK:
        return ALERT_TYPE_TO_RUNBOOK[alert_type]

    # 3. Keyword heuristic on case_id, alert_type, name, and prompt
    text_corpus = " ".join([
        str(trace.get("case_id") or ""),
        str(trace.get("eval_id") or ""),
        str(trace.get("name") or ""),
        str(trace.get("alert_type") or ""),
        str(trace.get("prompt") or ""),
    ]).upper()

    if any(k in text_corpus for k in ("LATERAL", "PSEXEC", "WMI")):
        return "lateral_movement_hunt_psexec_wmi.md"
    if any(k in text_corpus for k in ("LOGIN", "IMPOSSIBLE_TRAVEL", "MFA", "VPN")):
        return "suspicious_login_triage.md"
    if any(k in text_corpus for k in ("MALWARE", "HASH", "SHA256", "RANSOMWARE")):
        return "malware_triage.md"

    return DEFAULT_FALLBACK_RUNBOOK


def extract_trace_diagnosis(
    trace: Mapping[str, Any],
    pass_threshold: float = 0.80,
    forbidden_literals: Sequence[str] = (),
) -> AquaTraceDiagnosis:
    """Diagnoses a single execution trace into a structured root cause and procedural stage."""
    case_id = str(trace.get("case_id") or trace.get("eval_id") or "UNKNOWN_CASE")
    implicated_runbook = resolve_implicated_runbook(trace)

    score_val = trace.get("score")
    if score_val is None:
        score_val = trace.get("reward", 0.0)
    score = float(score_val)

    loss_penalty_val = trace.get("loss_penalty")
    loss_penalty = float(loss_penalty_val) if loss_penalty_val is not None else score

    raw_assert = trace.get("assert_passed")
    assert_passed = bool(score >= pass_threshold if raw_assert is None else raw_assert)

    expected_verdict = str(
        trace.get("expected_verdict") or trace.get("ground_truth_label") or ""
    ).strip().upper()
    actual_verdict = str(trace.get("actual_verdict") or "").strip().upper()

    expected_actions = tuple(str(a) for a in (trace.get("expected_actions") or ()))
    executed_actions = tuple(str(a) for a in (trace.get("executed_actions") or ()))
    prohibited_actions = tuple(str(a) for a in (trace.get("prohibited_actions") or ()))
    prohibited_entity_violations = tuple(str(v) for v in (trace.get("prohibited_entity_violations") or ()))

    trajectory = trace.get("trajectory") or []
    if not isinstance(trajectory, list):
        trajectory = []

    # Calculate epistemic steps
    if trace.get("epistemic_step_count") is not None:
        epistemic_steps = int(trace["epistemic_step_count"])
    else:
        epistemic_steps = sum(
            1 for step in trajectory if isinstance(step, dict) and is_epistemic_tool(str(step.get("tool") or ""))
        )

    # Missing expected actions
    missing_expected = tuple(a for a in expected_actions if a not in executed_actions)

    # Prohibited actions executed
    prohibited_executed = tuple(a for a in executed_actions if a in prohibited_actions)

    is_inert = bool(trace.get("inert", False))
    zero_tool_hesitation = False

    # Check zero tool hesitation
    if (len(trajectory) == 0 or epistemic_steps == 0) and not (
        len(expected_actions) == 0 and score >= pass_threshold and trace.get("zero_tool_hesitation") is False
    ):
        zero_tool_hesitation = True

    # Taxonomy mapping from JEV choice if present
    jev_choice_raw = str(trace.get("jev_choice") or "").strip()
    jev_category = SOC_FAILURE_TAXONOMY.get(jev_choice_raw, jev_choice_raw)

    failure_category = "FLAWLESS_CONTAINMENT"
    implicated_stage = "STAGE_A_IDENTITY"

    # Stage 1 Classification cascade
    if zero_tool_hesitation:
        failure_category = "PREMATURE_TERMINATION_ZERO_TOOLS"
        implicated_stage = "STAGE_A_IDENTITY"
    elif is_inert or jev_category == "INERT":
        is_inert = True
        failure_category = "INERT"
        implicated_stage = "STAGE_A_IDENTITY"
    elif prohibited_executed or prohibited_entity_violations or (
        actual_verdict == "MALICIOUS" and expected_verdict == "BENIGN" and any("isolate" in a or "block" in a for a in executed_actions)
    ):
        failure_category = "OVER_CONTAINMENT_FALSE_ALARM"
        implicated_stage = "STAGE_D_CONTAINMENT"
    elif "MALICIOUS" in expected_verdict and (
        any("isolate" in a or "block" in a for a in missing_expected) or actual_verdict == "BENIGN"
    ):
        failure_category = "MISSED_MALICIOUS_BREACH"
        implicated_stage = "STAGE_D_CONTAINMENT"
    elif "INCONCLUSIVE" in expected_verdict or (
        any(k in f"{case_id} {trace.get('alert_type', '')} {trace.get('prompt', '')}".upper() for k in ("503", "TOOL_OUTAGE"))
        and score < pass_threshold
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
    elif not assert_passed or score < pass_threshold:
        failure_category = "RUNBOOK_PROCEDURAL_VIOLATION"
        implicated_stage = "STAGE_B_ROUTING"
    else:
        failure_category = "FLAWLESS_CONTAINMENT"
        implicated_stage = "STAGE_D_CONTAINMENT"

    # Compute operational loss USD
    if trace.get("operational_loss_usd") is not None:
        operational_loss_usd = float(trace["operational_loss_usd"])
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

    # Sanitize root cause summary and remediation constraint
    clean_root_cause = sanitize_text(root_cause_summary, forbidden_literals=forbidden_literals)
    clean_remediation = sanitize_text(remediation_constraint, forbidden_literals=forbidden_literals)

    return AquaTraceDiagnosis(
        case_id=case_id,
        implicated_runbook=implicated_runbook,
        failure_category=failure_category,
        implicated_stage=implicated_stage,
        zero_tool_hesitation=zero_tool_hesitation,
        inert=is_inert,
        prohibited_actions_executed=prohibited_executed,
        prohibited_entity_violations=prohibited_entity_violations,
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
        if cat != "FLAWLESS_CONTAINMENT" or diag.score < pass_threshold:
            failed_count += 1
            total_loss += diag.operational_loss_usd

    # Cluster failures by (implicated_runbook, failure_category, implicated_stage)
    grouped: Dict[Tuple[str, str, str], List[AquaTraceDiagnosis]] = {}
    for d in diagnoses:
        if d.failure_category != "FLAWLESS_CONTAINMENT" or d.score < pass_threshold:
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

        # Consolidate root cause and instruction
        consolidated_root_cause = group[0].root_cause_summary
        targeted_instruction = group[0].remediation_constraint

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
    frozen_runbooks: List[str] = [rb for rb in all_runbooks if rb not in runbooks_with_failures]

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
