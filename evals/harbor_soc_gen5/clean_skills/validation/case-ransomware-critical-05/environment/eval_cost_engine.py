"""Cost-Weighted Signal Detection Theory and Decision Loss Engine for Agentic Evaluations.

Implements Signal Detection Theory sensitivity (d') and criterion bias (c) calculations
with Macmillan & Kaplan (1985) half-count extreme corrections, alongside an asymmetric
operational financial blast-radius loss matrix across asset criticality tiers.
"""

from dataclasses import asdict, dataclass, field
from enum import Enum
import math
from pathlib import Path
import re
import statistics
import sys
from typing import Any, Dict, List, Optional, Set, Tuple, Union

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


class AssetCriticality(str, Enum):
    """Asset criticality tiers for operational blast-radius weighting."""

    LOW = "LOW"
    STANDARD = "STANDARD"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DecisionOutcome(str, Enum):
    """Signal detection classification outcomes for SOC containment decisions."""

    TRUE_POSITIVE = "TRUE_POSITIVE"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    TRUE_NEGATIVE = "TRUE_NEGATIVE"
    FALSE_NEGATIVE = "FALSE_NEGATIVE"


@dataclass
class SignalDetectionMetrics:
    """Signal Detection Theory (SDT) metrics and count statistics."""

    d_prime: float
    criterion_c: float
    hit_rate: float
    false_alarm_rate: float
    hits: int
    misses: int
    false_alarms: int
    correct_rejections: int

    def to_dict(self) -> Dict[str, Any]:
        """Serializes SDT metrics to a dictionary."""
        return asdict(self)


@dataclass
class OperationalLossScorecard:
    """Dollar-denominated operational financial loss scorecard."""

    total_loss_usd: float
    fp_loss_usd: float
    fn_loss_usd: float
    investigation_cost_usd: float
    case_losses: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes operational loss scorecard to a dictionary."""
        return asdict(self)


# Default asymmetric operational blast-radius loss table in USD.
DEFAULT_OPERATIONAL_LOSS_MATRIX: Dict[Tuple[DecisionOutcome, AssetCriticality], float] = {
    # False Positives: Disruption, downtime, and unnecessary incident response
    (DecisionOutcome.FALSE_POSITIVE, AssetCriticality.CRITICAL): 50000.0,
    (DecisionOutcome.FALSE_POSITIVE, AssetCriticality.HIGH): 5000.0,
    (DecisionOutcome.FALSE_POSITIVE, AssetCriticality.STANDARD): 250.0,
    (DecisionOutcome.FALSE_POSITIVE, AssetCriticality.LOW): 50.0,
    # False Negatives: Uncontained adversary activity, data exfiltration, ransomware
    (DecisionOutcome.FALSE_NEGATIVE, AssetCriticality.CRITICAL): 250000.0,
    (DecisionOutcome.FALSE_NEGATIVE, AssetCriticality.HIGH): 50000.0,
    (DecisionOutcome.FALSE_NEGATIVE, AssetCriticality.STANDARD): 5000.0,
    (DecisionOutcome.FALSE_NEGATIVE, AssetCriticality.LOW): 200.0,
    # True Positives & True Negatives: Zero blast-radius damage
    (DecisionOutcome.TRUE_POSITIVE, AssetCriticality.CRITICAL): 0.0,
    (DecisionOutcome.TRUE_POSITIVE, AssetCriticality.HIGH): 0.0,
    (DecisionOutcome.TRUE_POSITIVE, AssetCriticality.STANDARD): 0.0,
    (DecisionOutcome.TRUE_POSITIVE, AssetCriticality.LOW): 0.0,
    (DecisionOutcome.TRUE_NEGATIVE, AssetCriticality.CRITICAL): 0.0,
    (DecisionOutcome.TRUE_NEGATIVE, AssetCriticality.HIGH): 0.0,
    (DecisionOutcome.TRUE_NEGATIVE, AssetCriticality.STANDARD): 0.0,
    (DecisionOutcome.TRUE_NEGATIVE, AssetCriticality.LOW): 0.0,
}


def normalize_decision_outcome(outcome: Union[DecisionOutcome, str]) -> DecisionOutcome:
    """Normalizes string or enum representation to DecisionOutcome."""
    if isinstance(outcome, DecisionOutcome):
        return outcome
    clean_str = str(outcome).strip().upper()
    shorthand_map = {
        "TP": DecisionOutcome.TRUE_POSITIVE,
        "FP": DecisionOutcome.FALSE_POSITIVE,
        "TN": DecisionOutcome.TRUE_NEGATIVE,
        "FN": DecisionOutcome.FALSE_NEGATIVE,
        "TRUE_POSITIVE": DecisionOutcome.TRUE_POSITIVE,
        "FALSE_POSITIVE": DecisionOutcome.FALSE_POSITIVE,
        "TRUE_NEGATIVE": DecisionOutcome.TRUE_NEGATIVE,
        "FALSE_NEGATIVE": DecisionOutcome.FALSE_NEGATIVE,
    }
    if clean_str in shorthand_map:
        return shorthand_map[clean_str]
    try:
        return DecisionOutcome(clean_str)
    except ValueError:
        return DecisionOutcome.TRUE_NEGATIVE


def normalize_criticality(criticality: Union[AssetCriticality, str]) -> AssetCriticality:
    """Normalizes string or enum representation to AssetCriticality."""
    if isinstance(criticality, AssetCriticality):
        return criticality
    clean_str = str(criticality).strip().upper()
    try:
        return AssetCriticality(clean_str)
    except ValueError:
        return AssetCriticality.STANDARD


# Canonical verdict sets for structured decision evaluation
BENIGN_VERDICTS = {
    "BENIGN",
    "FALSE_POSITIVE",
    "SAFE",
    "INCONCLUSIVE",
    "INCONCLUSIVE_DEGRADED",
    "INCONCLUSIVE_BENIGN",
    "CLEAN",
    "NON_MALICIOUS",
}

MALICIOUS_VERDICTS = {
    "MALICIOUS",
    "SUSPICIOUS",
    "CRITICAL_MALICIOUS",
    "TRUE_POSITIVE",
}

# Containment and closure action categories
CONTAINMENT_ACTIONS = {
    "isolate_host",
    "isolate",
    "quarantine_host",
    "quarantine",
    "block_indicator",
    "block_domain",
    "block_ip",
    "block_hash",
}

CLOSURE_ACTIONS = {
    "close_case",
    "resolve_case",
    "close_alert",
    "resolve_alert",
    "dismiss_case",
}

# Context-aware phrases for text analysis (precedence: benign/negation over affirmative threat)
BENIGN_CONTEXT_PHRASES = [
    "no containment",
    "no blocking",
    "not malicious",
    "non-malicious",
    "no malicious",
    "no threat",
    "no security threat",
    "no evidence of malicious",
    "verdict: benign",
    "benign false positive",
    "benign",
    "false positive",
    "non-routable",
    "safe",
    "close the alert",
    "close case",
    "close the case",
    "resolve alert",
    "inconclusive",
    "degraded",
    "service unavailable",
]

AFFIRMATIVE_THREAT_PHRASES = [
    "verdict: malicious",
    "verdict: suspicious",
    "isolate host",
    "block domain",
]


def _has_unnegated_containment_action(text_lower: str) -> bool:
    """Detects whether response text contains an affirmative un-negated containment action."""
    containment_patterns = [
        r"\bisolate\s+(?:the\s+)?host\b",
        r"\bblock\s+(?:the\s+)?(?:domain|ip|indicator|hash)\b",
        r"\bquarantine\s+(?:the\s+)?host\b",
    ]
    for pat in containment_patterns:
        for match in re.finditer(pat, text_lower):
            start = match.start()
            window_start = max(0, start - 40)
            boundary_idx = max(
                text_lower.rfind(".", window_start, start),
                text_lower.rfind(";", window_start, start),
                text_lower.rfind("!", window_start, start),
                text_lower.rfind("?", window_start, start),
                text_lower.rfind("\n", window_start, start),
            )
            if boundary_idx != -1:
                window_start = boundary_idx + 1
            clause_preceding = text_lower[window_start:start]
            if re.search(r"\b(no|not|do not|don't|no need to|without|never|avoid)\b", clause_preceding):
                continue
            return True
    return False


def classify_decision_outcome(
    ground_truth_threat: bool,
    agent_contained_or_flagged: Optional[bool] = None,
    verdict_str: Optional[str] = None,
    executed_actions: Optional[List[str]] = None,
    recommended_actions: Optional[List[str]] = None,
    response_text: Optional[str] = None,
    agent_flagged_threat: Optional[bool] = None,
) -> DecisionOutcome:
    """Classifies ground truth threat vs agent containment decisions with context-aware analysis.

    Evaluation priority hierarchy:
    1. Explicit agent_contained_or_flagged / agent_flagged_threat (backward compatibility).
    2. Structured verdict_str (e.g. from SocDecision or parsed analysis).
    3. Action intent across executed_actions and recommended_actions.
    4. Context-aware text analysis on response_text with negation precedence.
    5. Fallback default: threat = False.
    6. Maps (ground_truth_threat, threat) to DecisionOutcome.
    """
    if agent_contained_or_flagged is None and agent_flagged_threat is not None:
        agent_contained_or_flagged = agent_flagged_threat

    threat: Optional[bool] = None

    # 1. Explicit boolean flag
    if agent_contained_or_flagged is not None:
        threat = bool(agent_contained_or_flagged)

    # 2. Structured verdict string
    if threat is None and verdict_str is not None:
        clean_v = str(verdict_str).strip().upper().replace("[", "").replace("]", "").strip()
        if clean_v.startswith("VERDICT:"):
            clean_v = clean_v.split(":", 1)[1].strip()

        if clean_v in BENIGN_VERDICTS:
            threat = False
        elif clean_v in MALICIOUS_VERDICTS:
            threat = True
        elif any(b in clean_v for b in ["NOT MALICIOUS", "BENIGN", "FALSE_POSITIVE", "SAFE"]):
            threat = False
        elif any(m in clean_v for m in MALICIOUS_VERDICTS):
            threat = True

    # 3. Actions (executed and recommended)
    if threat is None and (executed_actions is not None or recommended_actions is not None):
        all_actions: List[str] = []
        if executed_actions:
            all_actions.extend([str(a).strip().lower().replace("-", "_") for a in executed_actions if a])
        if recommended_actions:
            all_actions.extend([str(a).strip().lower().replace("-", "_") for a in recommended_actions if a])

        has_containment = any(a in CONTAINMENT_ACTIONS for a in all_actions)
        has_closure = any(a in CLOSURE_ACTIONS for a in all_actions)

        if has_containment:
            threat = True
        elif has_closure:
            threat = False

    # 4. Context-aware text analysis on response_text
    if threat is None and response_text:
        text_lower = response_text.lower()
        has_unnegated_containment = _has_unnegated_containment_action(text_lower)
        has_affirmative_verdict = bool(re.search(r"\bverdict:\s*(?:malicious|suspicious)\b", text_lower))
        has_benign_phrase = any(phrase in text_lower for phrase in BENIGN_CONTEXT_PHRASES)

        if has_benign_phrase and not has_unnegated_containment and not has_affirmative_verdict:
            threat = False
        else:
            has_affirmative_threat = any(phrase in text_lower for phrase in AFFIRMATIVE_THREAT_PHRASES)
            has_unnegated_malicious = bool(
                re.search(
                    r"(?<!no\s)(?<!not\s)(?<!non-)(?<!zero\s)(?<!no\sevidence\sof\s)\b(?:malicious(?!\s+(?:intelligence|feed|service))\b|threat(?!\s+(?:intelligence|feed|service))\b|c2|ransomware)\b",
                    text_lower,
                )
            )
            if (
                has_affirmative_threat
                or has_unnegated_containment
                or has_affirmative_verdict
                or has_unnegated_malicious
            ):
                threat = True

    # 5. Default fallback
    if threat is None:
        threat = False

    # 6. Map to DecisionOutcome
    if ground_truth_threat and threat:
        return DecisionOutcome.TRUE_POSITIVE
    if not ground_truth_threat and threat:
        return DecisionOutcome.FALSE_POSITIVE
    if ground_truth_threat and not threat:
        return DecisionOutcome.FALSE_NEGATIVE
    return DecisionOutcome.TRUE_NEGATIVE


def calculate_sdt_metrics(
    hits: int,
    misses: int,
    false_alarms: int,
    correct_rejections: int,
) -> SignalDetectionMetrics:
    """Calculates Signal Detection Theory metrics (d' sensitivity and c criterion bias).

    Applies the Macmillan & Kaplan (1985) standard half-count extreme correction
    when hit rate or false alarm rate equals 0 or 1, avoiding infinite Z-scores.

    Args:
        hits: Count of true positive detections on actual threats.
        misses: Count of false negative misses on actual threats.
        false_alarms: Count of false positive alerts on benign activity.
        correct_rejections: Count of true negative passes on benign activity.

    Returns:
        SignalDetectionMetrics dataclass containing d', c, rates, and trial counts.
    """
    n_signal = hits + misses
    n_noise = false_alarms + correct_rejections

    # Apply half-count extreme correction (Macmillan & Kaplan, 1985)
    if n_signal == 0:
        hit_rate = 0.5
    elif hits == 0:
        hit_rate = 0.5 / n_signal
    elif hits == n_signal:
        hit_rate = (n_signal - 0.5) / n_signal
    else:
        hit_rate = hits / n_signal

    if n_noise == 0:
        false_alarm_rate = 0.5
    elif false_alarms == 0:
        false_alarm_rate = 0.5 / n_noise
    elif false_alarms == n_noise:
        false_alarm_rate = (n_noise - 0.5) / n_noise
    else:
        false_alarm_rate = false_alarms / n_noise

    # Clamp probability within valid open interval (1e-7, 1 - 1e-7) for inverse CDF
    eps = 1e-7
    clamped_hr = min(max(hit_rate, eps), 1.0 - eps)
    clamped_far = min(max(false_alarm_rate, eps), 1.0 - eps)

    # Compute standard normal quantile values (Z-scores)
    normal_dist = statistics.NormalDist()
    z_h = normal_dist.inv_cdf(clamped_hr)
    z_f = normal_dist.inv_cdf(clamped_far)

    # d' = Z(H) - Z(F)
    d_prime = float(z_h - z_f)

    # c = -0.5 * (Z(H) + Z(F))
    criterion_c = float(-0.5 * (z_h + z_f))

    # Clean up near-zero precision artifacts
    if abs(d_prime) < 1e-12:
        d_prime = 0.0
    if abs(criterion_c) < 1e-12:
        criterion_c = 0.0

    return SignalDetectionMetrics(
        d_prime=d_prime,
        criterion_c=criterion_c,
        hit_rate=hit_rate,
        false_alarm_rate=false_alarm_rate,
        hits=hits,
        misses=misses,
        false_alarms=false_alarms,
        correct_rejections=correct_rejections,
    )


def calculate_operational_loss(
    outcome: Union[DecisionOutcome, str],
    criticality: Union[AssetCriticality, str],
    custom_costs: Optional[Dict[Any, float]] = None,
) -> float:
    """Calculates operational financial loss in USD based on decision outcome and asset tier.

    Args:
        outcome: Decision outcome (e.g. FALSE_POSITIVE, FALSE_NEGATIVE).
        criticality: Asset criticality tier (e.g. LOW, STANDARD, HIGH, CRITICAL).
        custom_costs: Optional dictionary of custom cost overrides.

    Returns:
        Dollar-denominated loss amount as a float.
    """
    norm_outcome = normalize_decision_outcome(outcome)
    norm_criticality = normalize_criticality(criticality)

    if custom_costs:
        # Check direct tuple key
        if (norm_outcome, norm_criticality) in custom_costs:
            return float(custom_costs[(norm_outcome, norm_criticality)])
        # Check string tuple key
        if (norm_outcome.value, norm_criticality.value) in custom_costs:
            return float(custom_costs[(norm_outcome.value, norm_criticality.value)])
        # Check string combination key
        str_key = f"{norm_outcome.value}_{norm_criticality.value}"
        if str_key in custom_costs:
            return float(custom_costs[str_key])
        # Check shorthand string key
        short_outcome = "FP" if norm_outcome == DecisionOutcome.FALSE_POSITIVE else (
            "FN" if norm_outcome == DecisionOutcome.FALSE_NEGATIVE else (
                "TP" if norm_outcome == DecisionOutcome.TRUE_POSITIVE else "TN"
            )
        )
        short_key = f"{short_outcome}_{norm_criticality.value}"
        if short_key in custom_costs:
            return float(custom_costs[short_key])

    return DEFAULT_OPERATIONAL_LOSS_MATRIX.get(
        (norm_outcome, norm_criticality),
        0.0,
    )


def calculate_expected_loss_matrix(
    cases_evaluation: List[Dict[str, Any]],
    cost_per_token: float = 0.000002,
    cost_per_tool_step: float = 0.001,
) -> OperationalLossScorecard:
    """Aggregates decision losses and investigation compute costs across multiple evaluated cases.

    Args:
        cases_evaluation: List of case evaluation result dictionaries.
        cost_per_token: Financial cost in USD per model token processed.
        cost_per_tool_step: Financial cost in USD per tool execution step.

    Returns:
        OperationalLossScorecard summarizing total, FP, FN, and investigation costs.
    """
    total_fp_loss: float = 0.0
    total_fn_loss: float = 0.0
    total_investigation_cost: float = 0.0
    case_losses: List[Dict[str, Any]] = []

    for idx, case in enumerate(cases_evaluation):
        case_id = str(case.get("case_id") or case.get("id") or f"case_{idx + 1}")
        raw_outcome = (
            case.get("outcome")
            or case.get("decision_outcome")
            or case.get("verdict_outcome")
            or ("TRUE_POSITIVE" if case.get("passed") else "FALSE_NEGATIVE")
        )
        raw_criticality = (
            case.get("criticality")
            or case.get("criticality_tier")
            or case.get("asset_criticality")
            or case.get("tier")
            or "STANDARD"
        )

        outcome = normalize_decision_outcome(raw_outcome)
        criticality = normalize_criticality(raw_criticality)

        # Decision blast-radius loss
        decision_loss = calculate_operational_loss(outcome, criticality)

        if outcome == DecisionOutcome.FALSE_POSITIVE:
            total_fp_loss += decision_loss
        elif outcome == DecisionOutcome.FALSE_NEGATIVE:
            total_fn_loss += decision_loss

        # Token usage calculation
        tokens: int = 0
        if "total_tokens" in case:
            tokens = int(case["total_tokens"])
        elif "usage" in case and isinstance(case["usage"], dict):
            usage = case["usage"]
            tokens = int(usage.get("total_tokens", usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)))
        elif "prompt_tokens" in case or "completion_tokens" in case:
            tokens = int(case.get("prompt_tokens", 0)) + int(case.get("completion_tokens", 0))

        token_cost = float(tokens * cost_per_token)

        # Tool execution step count
        tool_steps: int = 0
        if "tool_steps" in case:
            tool_steps = int(case["tool_steps"])
        elif "tool_calls" in case:
            tc = case["tool_calls"]
            tool_steps = len(tc) if isinstance(tc, list) else int(tc)
        elif "trajectory" in case:
            traj = case["trajectory"]
            tool_steps = len(traj) if isinstance(traj, list) else int(traj)
        elif "tool_call_count" in case:
            tool_steps = int(case["tool_call_count"])

        tool_cost = float(tool_steps * cost_per_tool_step)
        investigation_cost = token_cost + tool_cost
        total_investigation_cost += investigation_cost

        case_total_loss = decision_loss + investigation_cost

        case_losses.append({
            "case_id": case_id,
            "outcome": outcome.value,
            "criticality": criticality.value,
            "decision_loss_usd": round(decision_loss, 2),
            "tokens": tokens,
            "token_cost_usd": round(token_cost, 6),
            "tool_steps": tool_steps,
            "tool_cost_usd": round(tool_cost, 6),
            "investigation_cost_usd": round(investigation_cost, 6),
            "total_loss_usd": round(case_total_loss, 2),
        })

    total_loss = total_fp_loss + total_fn_loss + total_investigation_cost

    return OperationalLossScorecard(
        total_loss_usd=round(total_loss, 2),
        fp_loss_usd=round(total_fp_loss, 2),
        fn_loss_usd=round(total_fn_loss, 2),
        investigation_cost_usd=round(total_investigation_cost, 4),
        case_losses=case_losses,
    )


DISRUPTIVE_CONTAINMENT_ACTIONS = {
    "isolate_host",
    "isolate",
    "quarantine_host",
    "quarantine",
}


def _is_threat_scenario(case_dict: Dict[str, Any]) -> bool:
    """Determines whether an evaluation case represents an active threat requiring containment."""
    label = str(
        case_dict.get("ground_truth_label")
        or case_dict.get("ground_truth")
        or case_dict.get("verdict")
        or ""
    ).strip().upper()
    if label in ("MALICIOUS", "CRITICAL_MALICIOUS", "TRUE_POSITIVE"):
        return True
    if label in ("BENIGN", "SAFE", "FALSE_POSITIVE", "INCONCLUSIVE", "INCONCLUSIVE_DEGRADED", "AMBIGUOUS"):
        return False

    # Check expected and prohibited actions
    expected = [str(a).lower().replace("-", "_") for a in case_dict.get("expected_actions", [])]
    prohibited = [str(a).lower().replace("-", "_") for a in case_dict.get("prohibited_actions", [])]
    if any(a in CONTAINMENT_ACTIONS for a in expected):
        return True
    if any(a in CONTAINMENT_ACTIONS for a in prohibited):
        return False
    return label == "SUSPICIOUS"


def _did_threat_trigger_containment(result: Dict[str, Any]) -> bool:
    """Checks whether the threat scenario triggered containment or blocking actions."""
    executed: List[str] = []
    if "executed_actions" in result:
        executed.extend([str(a).lower().replace("-", "_") for a in result["executed_actions"]])
    if "actions" in result:
        executed.extend([str(a).lower().replace("-", "_") for a in result["actions"]])
    if "trajectory" in result and isinstance(result["trajectory"], list):
        for step in result["trajectory"]:
            if isinstance(step, dict):
                act = step.get("tool") or step.get("action")
                if act:
                    executed.append(str(act).lower().replace("-", "_"))
    if any(a in CONTAINMENT_ACTIONS for a in executed):
        return True

    if "recommended_actions" in result:
        rec = [str(a).lower().replace("-", "_") for a in result["recommended_actions"]]
        if any(a in CONTAINMENT_ACTIONS for a in rec):
            return True

    outcome = str(result.get("decision_outcome") or result.get("outcome") or "").strip().upper()
    if outcome in (DecisionOutcome.TRUE_POSITIVE.value, "TRUE_POSITIVE", "TP"):
        return True

    resp = str(result.get("response") or result.get("response_text") or result.get("text") or "").strip().lower()
    if resp and _has_unnegated_containment_action(resp):
        return True

    if result.get("passed", False):
        expected = result.get("expected_actions", [])
        if any(a in CONTAINMENT_ACTIONS for a in expected):
            return True

    return False


def _did_non_threat_avoid_disruption(result: Dict[str, Any]) -> bool:
    """Checks whether the benign/ambiguous twin avoided disruptive host isolation."""
    executed: List[str] = []
    if "executed_actions" in result:
        executed.extend([str(a).lower().replace("-", "_") for a in result["executed_actions"]])
    if "actions" in result:
        executed.extend([str(a).lower().replace("-", "_") for a in result["actions"]])
    if "trajectory" in result and isinstance(result["trajectory"], list):
        for step in result["trajectory"]:
            if isinstance(step, dict):
                act = step.get("tool") or step.get("action")
                if act:
                    executed.append(str(act).lower().replace("-", "_"))
    if any(a in DISRUPTIVE_CONTAINMENT_ACTIONS for a in executed):
        return False

    if "recommended_actions" in result:
        rec = [str(a).lower().replace("-", "_") for a in result["recommended_actions"]]
        if any(a in DISRUPTIVE_CONTAINMENT_ACTIONS for a in rec):
            return False

    outcome = str(result.get("decision_outcome") or result.get("outcome") or "").strip().upper()
    if outcome in (DecisionOutcome.FALSE_POSITIVE.value, "FALSE_POSITIVE", "FP"):
        return False

    resp = str(result.get("response") or result.get("response_text") or result.get("text") or "").strip().lower()
    if resp and re.search(r"\b(?:isolate|quarantine)\s+(?:the\s+)?host\b", resp):
        if not re.search(r"\b(no|not|do not|don't|no need to|without|never|avoid)\b", resp):
            return False

    return True


def calculate_counterfactual_consistency(
    case_results: List[Dict[str, Any]],
    eval_cases: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Evaluates counterfactual discrimination consistency across paired threat/benign scenarios.

    Args:
        case_results: List of evaluated case result dictionaries.
        eval_cases: Optional list of evaluation case definitions specifying counterfactual_pair_id.

    Returns:
        Dictionary with counterfactual_consistency_score, totals, and per-pair diagnostic breakdowns.
    """
    case_info_map: Dict[str, Dict[str, Any]] = {}
    if eval_cases:
        for c in eval_cases:
            cid = str(c.get("eval_id") or c.get("case_id") or c.get("id") or "").strip()
            if cid:
                case_info_map[cid] = dict(c)

    results_map: Dict[str, Dict[str, Any]] = {}
    for r in case_results:
        cid = str(r.get("eval_id") or r.get("case_id") or r.get("id") or "").strip()
        if cid:
            results_map[cid] = dict(r)
            if cid not in case_info_map:
                case_info_map[cid] = dict(r)
            else:
                case_info_map[cid].update(r)

    processed_pairs: Set[Any] = set()
    pair_diagnostics: List[Dict[str, Any]] = []

    for cid, info in case_info_map.items():
        pair_target = info.get("counterfactual_pair_id")
        if not pair_target:
            continue
        pair_target_str = str(pair_target).strip()
        if not pair_target_str:
            continue

        if pair_target_str in case_info_map:
            canon_key = tuple(sorted([cid, pair_target_str]))
            if canon_key in processed_pairs:
                continue
            processed_pairs.add(canon_key)
            id_a, id_b = canon_key
            pair_name = f"{id_a} <-> {id_b}"

            # Check if both cases were evaluated in results_map
            if id_a in results_map and id_b in results_map:
                info_a = case_info_map[id_a]
                info_b = case_info_map[id_b]
                res_a = results_map[id_a]
                res_b = results_map[id_b]

                is_threat_a = _is_threat_scenario(info_a)
                is_threat_b = _is_threat_scenario(info_b)

                if is_threat_a and not is_threat_b:
                    t_id, t_info, t_res = id_a, info_a, res_a
                    nt_id, nt_info, nt_res = id_b, info_b, res_b
                elif is_threat_b and not is_threat_a:
                    t_id, t_info, t_res = id_b, info_b, res_b
                    nt_id, nt_info, nt_res = id_a, info_a, res_a
                else:
                    label_a = str(info_a.get("ground_truth_label", "")).upper()
                    if "MALICIOUS" in label_a:
                        t_id, t_info, t_res = id_a, info_a, res_a
                        nt_id, nt_info, nt_res = id_b, info_b, res_b
                    else:
                        t_id, t_info, t_res = id_b, info_b, res_b
                        nt_id, nt_info, nt_res = id_a, info_a, res_a

                threat_contained = _did_threat_trigger_containment(t_res)
                non_threat_avoided = _did_non_threat_avoid_disruption(nt_res)
                consistent = bool(threat_contained and non_threat_avoided)

                pair_diagnostics.append({
                    "pair_id": pair_name,
                    "threat_case_id": t_id,
                    "non_threat_case_id": nt_id,
                    "threat_label": t_info.get("ground_truth_label", "MALICIOUS"),
                    "non_threat_label": nt_info.get("ground_truth_label", "BENIGN"),
                    "threat_contained": threat_contained,
                    "non_threat_avoided_containment": non_threat_avoided,
                    "consistent": consistent,
                    "status": "EVALUATED",
                    "details": (
                        "Threat correctly contained and non-threat avoided disruptive isolation."
                        if consistent
                        else (
                            "Threat missed containment."
                            if not threat_contained and non_threat_avoided
                            else (
                                "Non-threat suffered disruptive containment."
                                if threat_contained and not non_threat_avoided
                                else "Both threat containment and non-threat avoidance failed."
                            )
                        )
                    ),
                })
            else:
                missing_case = id_a if id_a not in results_map else id_b
                pair_diagnostics.append({
                    "pair_id": pair_name,
                    "threat_case_id": id_a,
                    "non_threat_case_id": id_b,
                    "status": "PARTIAL",
                    "consistent": False,
                    "details": f"Missing result for case '{missing_case}'",
                })
        else:
            # Check for shared group tag matches
            group_matches = [
                other_id for other_id, other_info in case_info_map.items()
                if other_id != cid and str(other_info.get("counterfactual_pair_id", "")).strip() == pair_target_str
            ]
            if group_matches:
                for other_id in group_matches:
                    canon_key = tuple(sorted([cid, other_id]))
                    if canon_key in processed_pairs:
                        continue
                    processed_pairs.add(canon_key)
                    id_a, id_b = canon_key
                    pair_name = f"{pair_target_str}: {id_a} <-> {id_b}"

                    if id_a in results_map and id_b in results_map:
                        info_a = case_info_map[id_a]
                        info_b = case_info_map[id_b]
                        res_a = results_map[id_a]
                        res_b = results_map[id_b]

                        is_threat_a = _is_threat_scenario(info_a)
                        is_threat_b = _is_threat_scenario(info_b)

                        if is_threat_a and not is_threat_b:
                            t_id, t_info, t_res = id_a, info_a, res_a
                            nt_id, nt_info, nt_res = id_b, info_b, res_b
                        elif is_threat_b and not is_threat_a:
                            t_id, t_info, t_res = id_b, info_b, res_b
                            nt_id, nt_info, nt_res = id_a, info_a, res_a
                        else:
                            label_a = str(info_a.get("ground_truth_label", "")).upper()
                            if "MALICIOUS" in label_a:
                                t_id, t_info, t_res = id_a, info_a, res_a
                                nt_id, nt_info, nt_res = id_b, info_b, res_b
                            else:
                                t_id, t_info, t_res = id_b, info_b, res_b
                                nt_id, nt_info, nt_res = id_a, info_a, res_a

                        threat_contained = _did_threat_trigger_containment(t_res)
                        non_threat_avoided = _did_non_threat_avoid_disruption(nt_res)
                        consistent = bool(threat_contained and non_threat_avoided)

                        pair_diagnostics.append({
                            "pair_id": pair_name,
                            "threat_case_id": t_id,
                            "non_threat_case_id": nt_id,
                            "threat_label": t_info.get("ground_truth_label", "MALICIOUS"),
                            "non_threat_label": nt_info.get("ground_truth_label", "BENIGN"),
                            "threat_contained": threat_contained,
                            "non_threat_avoided_containment": non_threat_avoided,
                            "consistent": consistent,
                            "status": "EVALUATED",
                            "details": (
                                "Threat correctly contained and non-threat avoided disruptive isolation."
                                if consistent
                                else (
                                    f"Threat '{t_id}' missed containment."
                                    if not threat_contained and non_threat_avoided
                                    else (
                                        f"Non-threat '{nt_id}' suffered disruptive containment."
                                        if threat_contained and not non_threat_avoided
                                        else f"Both threat '{t_id}' missed containment and non-threat '{nt_id}' suffered disruptive containment."
                                    )
                                )
                            ),
                        })
                    else:
                        missing_case = id_a if id_a not in results_map else id_b
                        pair_diagnostics.append({
                            "pair_id": pair_name,
                            "threat_case_id": id_a,
                            "non_threat_case_id": id_b,
                            "status": "PARTIAL",
                            "consistent": False,
                            "details": f"Missing result for case '{missing_case}'",
                        })
            else:
                canon_key = (cid, pair_target_str)
                if canon_key not in processed_pairs:
                    processed_pairs.add(canon_key)
                    pair_diagnostics.append({
                        "pair_id": f"{cid} <-> {pair_target_str}",
                        "threat_case_id": cid,
                        "non_threat_case_id": pair_target_str,
                        "status": "PARTIAL",
                        "consistent": False,
                        "details": f"Missing counterfactual twin case definition for '{pair_target_str}'",
                    })

    total_pairs = len(pair_diagnostics)
    evaluated_pairs = sum(1 for p in pair_diagnostics if p["status"] == "EVALUATED")
    consistent_pairs = sum(1 for p in pair_diagnostics if p["status"] == "EVALUATED" and p["consistent"])
    inconsistent_pairs = evaluated_pairs - consistent_pairs
    partial_pairs = sum(1 for p in pair_diagnostics if p["status"] == "PARTIAL")

    consistency_score = (
        round(consistent_pairs / evaluated_pairs, 4) if evaluated_pairs > 0 else 0.0
    )

    return {
        "counterfactual_consistency_score": consistency_score,
        "total_pairs": total_pairs,
        "evaluated_pairs": evaluated_pairs,
        "consistent_pairs": consistent_pairs,
        "inconsistent_pairs": inconsistent_pairs,
        "partial_pairs": partial_pairs,
        "pairs": pair_diagnostics,
        "pair_diagnostics": pair_diagnostics,
    }
