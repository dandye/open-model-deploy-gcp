"""Unit tests for Cost-Weighted Signal Detection Theory and Decision Loss Engine."""

from typing import Any, Dict, List
import pytest

from scripts.eval_cost_engine import (
    AssetCriticality,
    DecisionOutcome,
    OperationalLossScorecard,
    SignalDetectionMetrics,
    calculate_expected_loss_matrix,
    calculate_operational_loss,
    calculate_sdt_metrics,
    calculate_counterfactual_consistency,
    classify_decision_outcome,
)


def test_enums_and_dataclasses():
    """Verifies enum values and dataclass structures."""
    assert AssetCriticality.LOW == "LOW"
    assert AssetCriticality.STANDARD == "STANDARD"
    assert AssetCriticality.HIGH == "HIGH"
    assert AssetCriticality.CRITICAL == "CRITICAL"

    assert DecisionOutcome.TRUE_POSITIVE == "TRUE_POSITIVE"
    assert DecisionOutcome.FALSE_POSITIVE == "FALSE_POSITIVE"
    assert DecisionOutcome.TRUE_NEGATIVE == "TRUE_NEGATIVE"
    assert DecisionOutcome.FALSE_NEGATIVE == "FALSE_NEGATIVE"

    sdt = SignalDetectionMetrics(
        d_prime=2.12,
        criterion_c=0.22,
        hit_rate=0.8,
        false_alarm_rate=0.1,
        hits=8,
        misses=2,
        false_alarms=1,
        correct_rejections=9,
    )
    assert sdt.d_prime == 2.12
    assert sdt.hits == 8

    scorecard = OperationalLossScorecard(
        total_loss_usd=55000.0,
        fp_loss_usd=5000.0,
        fn_loss_usd=50000.0,
        investigation_cost_usd=0.05,
        case_losses=[],
    )
    assert scorecard.total_loss_usd == 55000.0


def test_calculate_sdt_metrics_standard():
    """Tests standard Signal Detection calculation with 8 hits, 2 misses, 1 FA, 9 CR."""
    res = calculate_sdt_metrics(hits=8, misses=2, false_alarms=1, correct_rejections=9)
    assert res.hits == 8
    assert res.misses == 2
    assert res.false_alarms == 1
    assert res.correct_rejections == 9
    assert res.hit_rate == pytest.approx(0.8, rel=1e-4)
    assert res.false_alarm_rate == pytest.approx(0.1, rel=1e-4)
    assert res.d_prime > 1.5
    assert res.d_prime == pytest.approx(2.1232, abs=1e-3)
    assert res.criterion_c == pytest.approx(0.2200, abs=1e-3)


def test_calculate_sdt_metrics_perfect_discrimination_half_count_correction():
    """Tests 100% hit rate and 0% false alarm rate with Macmillan & Kaplan 1985 half-count correction."""
    res = calculate_sdt_metrics(hits=10, misses=0, false_alarms=0, correct_rejections=10)
    # Target trials = 10, hits = 10 -> corrected hit rate = (10 - 0.5) / 10 = 0.95
    # Noise trials = 10, FA = 0 -> corrected FA rate = 0.5 / 10 = 0.05
    assert res.hit_rate == pytest.approx(0.95, rel=1e-4)
    assert res.false_alarm_rate == pytest.approx(0.05, rel=1e-4)
    assert res.d_prime > 3.0
    assert res.d_prime == pytest.approx(3.2897, abs=1e-3)
    # Symmetrical rates 0.95 and 0.05 yield neutral criterion bias c = 0
    assert res.criterion_c == pytest.approx(0.0, abs=1e-5)


def test_calculate_sdt_metrics_zero_sensitivity_chance():
    """Tests random chance performance where hit rate equals false alarm rate (d_prime = 0)."""
    res = calculate_sdt_metrics(hits=5, misses=5, false_alarms=5, correct_rejections=5)
    assert res.hit_rate == pytest.approx(0.5, rel=1e-4)
    assert res.false_alarm_rate == pytest.approx(0.5, rel=1e-4)
    assert res.d_prime == pytest.approx(0.0, abs=1e-5)
    assert res.criterion_c == pytest.approx(0.0, abs=1e-5)


def test_calculate_sdt_metrics_response_bias():
    """Tests criterion c for liberal/aggressive vs conservative decision bias."""
    # Liberal / Aggressive bias: flags almost everything as a threat
    res_liberal = calculate_sdt_metrics(hits=9, misses=1, false_alarms=9, correct_rejections=1)
    assert res_liberal.d_prime == pytest.approx(0.0, abs=1e-5)
    assert res_liberal.criterion_c < -1.0

    # Conservative bias: hesitates to flag threats
    res_conservative = calculate_sdt_metrics(hits=1, misses=9, false_alarms=1, correct_rejections=9)
    assert res_conservative.d_prime == pytest.approx(0.0, abs=1e-5)
    assert res_conservative.criterion_c > 1.0


def test_calculate_sdt_metrics_zero_trial_safety():
    """Verifies that empty trial counts are handled without division-by-zero errors."""
    res = calculate_sdt_metrics(hits=0, misses=0, false_alarms=0, correct_rejections=0)
    assert res.d_prime == pytest.approx(0.0, abs=1e-5)
    assert res.criterion_c == pytest.approx(0.0, abs=1e-5)
    assert res.hit_rate == 0.5
    assert res.false_alarm_rate == 0.5


def test_calculate_operational_loss_all_tiers_and_outcomes():
    """Verifies asymmetric financial loss matrix lookup across all 4 criticality tiers."""
    # False Positive (Containment disruption of benign asset)
    assert calculate_operational_loss(DecisionOutcome.FALSE_POSITIVE, AssetCriticality.CRITICAL) == 50000.0
    assert calculate_operational_loss(DecisionOutcome.FALSE_POSITIVE, AssetCriticality.HIGH) == 5000.0
    assert calculate_operational_loss(DecisionOutcome.FALSE_POSITIVE, AssetCriticality.STANDARD) == 250.0
    assert calculate_operational_loss(DecisionOutcome.FALSE_POSITIVE, AssetCriticality.LOW) == 50.0

    # False Negative (Uncontained threat on asset)
    assert calculate_operational_loss(DecisionOutcome.FALSE_NEGATIVE, AssetCriticality.CRITICAL) == 250000.0
    assert calculate_operational_loss(DecisionOutcome.FALSE_NEGATIVE, AssetCriticality.HIGH) == 50000.0
    assert calculate_operational_loss(DecisionOutcome.FALSE_NEGATIVE, AssetCriticality.STANDARD) == 5000.0
    assert calculate_operational_loss(DecisionOutcome.FALSE_NEGATIVE, AssetCriticality.LOW) == 200.0

    # True Positive and True Negative (Zero operational blast radius loss)
    for crit in [AssetCriticality.LOW, AssetCriticality.STANDARD, AssetCriticality.HIGH, AssetCriticality.CRITICAL]:
        assert calculate_operational_loss(DecisionOutcome.TRUE_POSITIVE, crit) == 0.0
        assert calculate_operational_loss(DecisionOutcome.TRUE_NEGATIVE, crit) == 0.0


def test_calculate_operational_loss_string_inputs():
    """Verifies string inputs are normalized to enums gracefully."""
    assert calculate_operational_loss("FALSE_POSITIVE", "CRITICAL") == 50000.0
    assert calculate_operational_loss("fp", "high") == 5000.0
    assert calculate_operational_loss("fn", "critical") == 250000.0
    assert calculate_operational_loss("tp", "standard") == 0.0
    assert calculate_operational_loss("tn", "low") == 0.0


def test_calculate_operational_loss_custom_costs():
    """Verifies custom cost overrides in operational loss calculations."""
    custom = {
        "FALSE_POSITIVE_CRITICAL": 75000.0,
        "FALSE_NEGATIVE_LOW": 500.0,
    }
    loss_crit = calculate_operational_loss(
        DecisionOutcome.FALSE_POSITIVE,
        AssetCriticality.CRITICAL,
        custom_costs=custom,
    )
    assert loss_crit == 75000.0

    loss_low_fn = calculate_operational_loss(
        DecisionOutcome.FALSE_NEGATIVE,
        AssetCriticality.LOW,
        custom_costs=custom,
    )
    assert loss_low_fn == 500.0

    # Fallback to default when not in custom dict
    loss_high_fp = calculate_operational_loss(
        DecisionOutcome.FALSE_POSITIVE,
        AssetCriticality.HIGH,
        custom_costs=custom,
    )
    assert loss_high_fp == 5000.0


def test_calculate_expected_loss_matrix_multi_case():
    """Verifies multi-case operational loss scorecard aggregation including token and tool costs."""
    cases_evaluation: List[Dict[str, Any]] = [
        {
            "case_id": "CASE-101",
            "outcome": "FALSE_POSITIVE",
            "criticality": "HIGH",
            "usage": {"total_tokens": 2000, "prompt_tokens": 1500, "completion_tokens": 500},
            "tool_steps": 4,
        },
        {
            "case_id": "CASE-102",
            "outcome": "FALSE_NEGATIVE",
            "criticality": "STANDARD",
            "total_tokens": 1000,
            "trajectory": [{"tool": "get_ip_report"}, {"tool": "get_domain_report"}],
        },
        {
            "case_id": "CASE-103",
            "outcome": "TRUE_POSITIVE",
            "criticality": "CRITICAL",
            "total_tokens": 3000,
            "tool_steps": 5,
        },
        {
            "case_id": "CASE-104",
            "outcome": "TRUE_NEGATIVE",
            "criticality": "LOW",
            "total_tokens": 500,
            "tool_steps": 1,
        },
    ]

    cost_per_token = 0.000002
    cost_per_tool = 0.001

    # Expected:
    # CASE-101: FP High = $5000.0, Tokens: 2000 * 2e-6 = $0.004, Tools: 4 * 0.001 = $0.004 -> Inv: $0.008, Total: $5000.008
    # CASE-102: FN Std = $5000.0, Tokens: 1000 * 2e-6 = $0.002, Tools: 2 * 0.001 = $0.002 -> Inv: $0.004, Total: $5000.004
    # CASE-103: TP Crit = $0.0, Tokens: 3000 * 2e-6 = $0.006, Tools: 5 * 0.001 = $0.005 -> Inv: $0.011, Total: $0.011
    # CASE-104: TN Low = $0.0, Tokens: 500 * 2e-6 = $0.001, Tools: 1 * 0.001 = $0.001 -> Inv: $0.002, Total: $0.002
    # Total FP loss = $5000.0
    # Total FN loss = $5000.0
    # Total Inv cost = 0.008 + 0.004 + 0.011 + 0.002 = $0.025
    # Total loss = $10000.025

    scorecard = calculate_expected_loss_matrix(
        cases_evaluation=cases_evaluation,
        cost_per_token=cost_per_token,
        cost_per_tool_step=cost_per_tool,
    )

    assert scorecard.fp_loss_usd == pytest.approx(5000.0, abs=1e-2)
    assert scorecard.fn_loss_usd == pytest.approx(5000.0, abs=1e-2)
    assert scorecard.investigation_cost_usd == pytest.approx(0.025, abs=1e-4)
    assert scorecard.total_loss_usd == pytest.approx(10000.025, abs=1e-2)
    assert len(scorecard.case_losses) == 4
    assert scorecard.case_losses[0]["case_id"] == "CASE-101"
    assert scorecard.case_losses[0]["decision_loss_usd"] == 5000.0


def test_classify_decision_outcome_backward_compatibility():
    """Verifies backward compatibility with explicit agent_contained_or_flagged."""
    assert classify_decision_outcome(ground_truth_threat=True, agent_contained_or_flagged=True) == DecisionOutcome.TRUE_POSITIVE
    assert classify_decision_outcome(ground_truth_threat=False, agent_contained_or_flagged=True) == DecisionOutcome.FALSE_POSITIVE
    assert classify_decision_outcome(ground_truth_threat=True, agent_contained_or_flagged=False) == DecisionOutcome.FALSE_NEGATIVE
    assert classify_decision_outcome(ground_truth_threat=False, agent_contained_or_flagged=False) == DecisionOutcome.TRUE_NEGATIVE

    # Positional invocation compatibility
    assert classify_decision_outcome(True, True) == DecisionOutcome.TRUE_POSITIVE
    assert classify_decision_outcome(False, False) == DecisionOutcome.TRUE_NEGATIVE

    # Support for agent_flagged_threat parameter name
    assert classify_decision_outcome(ground_truth_threat=True, agent_flagged_threat=True) == DecisionOutcome.TRUE_POSITIVE
    assert classify_decision_outcome(ground_truth_threat=False, agent_flagged_threat=False) == DecisionOutcome.TRUE_NEGATIVE


def test_classify_decision_outcome_negation_not_threat():
    """Verifies that negation phrases prevent false positive misclassification (fixes Case 2 bug)."""
    response = "No containment or blocking actions are required. Close the alert as benign false positive."
    outcome = classify_decision_outcome(
        ground_truth_threat=False,
        response_text=response,
    )
    assert outcome == DecisionOutcome.TRUE_NEGATIVE

    # Additional negation and benign phrase variations
    outcome_not_malicious = classify_decision_outcome(
        ground_truth_threat=False,
        response_text="Analysis shows this is not malicious. The host is safe.",
    )
    assert outcome_not_malicious == DecisionOutcome.TRUE_NEGATIVE

    outcome_non_routable = classify_decision_outcome(
        ground_truth_threat=False,
        response_text="Destination IP is non-routable private space. Close the alert.",
    )
    assert outcome_non_routable == DecisionOutcome.TRUE_NEGATIVE

    outcome_negated_action = classify_decision_outcome(
        ground_truth_threat=False,
        response_text="Do not isolate host. Close the alert as safe.",
    )
    assert outcome_negated_action == DecisionOutcome.TRUE_NEGATIVE

    outcome_no_evidence = classify_decision_outcome(
        ground_truth_threat=False,
        response_text="This alert is benign. No evidence of malicious activity.",
    )
    assert outcome_no_evidence == DecisionOutcome.TRUE_NEGATIVE


def test_classify_decision_outcome_with_structured_verdict():
    """Verifies structured verdict classification across benign and malicious categories."""
    # Benign verdicts
    for benign_v in ["BENIGN", "FALSE_POSITIVE", "SAFE", "INCONCLUSIVE_BENIGN", "Verdict: Benign"]:
        outcome_tn = classify_decision_outcome(
            ground_truth_threat=False,
            verdict_str=benign_v,
        )
        assert outcome_tn == DecisionOutcome.TRUE_NEGATIVE

        outcome_fn = classify_decision_outcome(
            ground_truth_threat=True,
            verdict_str=benign_v,
        )
        assert outcome_fn == DecisionOutcome.FALSE_NEGATIVE

    # Malicious verdicts
    for mal_v in ["MALICIOUS", "SUSPICIOUS", "CRITICAL_MALICIOUS", "TRUE_POSITIVE", "Verdict: Malicious"]:
        outcome_tp = classify_decision_outcome(
            ground_truth_threat=True,
            verdict_str=mal_v,
        )
        assert outcome_tp == DecisionOutcome.TRUE_POSITIVE

        outcome_fp = classify_decision_outcome(
            ground_truth_threat=False,
            verdict_str=mal_v,
        )
        assert outcome_fp == DecisionOutcome.FALSE_POSITIVE


def test_classify_decision_outcome_with_actions():
    """Verifies action list resolution for containment vs closure actions."""
    # Closure action on benign alert -> TRUE_NEGATIVE
    outcome_close = classify_decision_outcome(
        ground_truth_threat=False,
        recommended_actions=["close_case"],
    )
    assert outcome_close == DecisionOutcome.TRUE_NEGATIVE

    outcome_resolve = classify_decision_outcome(
        ground_truth_threat=False,
        executed_actions=["get_ip_report"],
        recommended_actions=["resolve_case"],
    )
    assert outcome_resolve == DecisionOutcome.TRUE_NEGATIVE

    # Containment actions -> Threat flagged
    outcome_isolate_tp = classify_decision_outcome(
        ground_truth_threat=True,
        recommended_actions=["isolate_host"],
    )
    assert outcome_isolate_tp == DecisionOutcome.TRUE_POSITIVE

    outcome_isolate_fp = classify_decision_outcome(
        ground_truth_threat=False,
        recommended_actions=["isolate_host"],
    )
    assert outcome_isolate_fp == DecisionOutcome.FALSE_POSITIVE

    outcome_block_ip = classify_decision_outcome(
        ground_truth_threat=True,
        executed_actions=["block_ip"],
    )
    assert outcome_block_ip == DecisionOutcome.TRUE_POSITIVE

    # Containment actions take precedence over closure actions
    outcome_mixed = classify_decision_outcome(
        ground_truth_threat=True,
        recommended_actions=["close_case", "block_indicator"],
    )
    assert outcome_mixed == DecisionOutcome.TRUE_POSITIVE


def test_classify_decision_outcome_context_aware_text():
    """Verifies text analysis when verdict_str and actions are absent."""
    # Affirmative threat phrases
    outcome_tp = classify_decision_outcome(
        ground_truth_threat=True,
        response_text="Confirmed malicious behavior observed. Isolate host DESKTOP-01.",
    )
    assert outcome_tp == DecisionOutcome.TRUE_POSITIVE

    # Un-negated containment overrides benign mention
    outcome_unnegated_containment = classify_decision_outcome(
        ground_truth_threat=True,
        response_text="The IP looks safe, but we must isolate host immediately due to ransomware.",
    )
    assert outcome_unnegated_containment == DecisionOutcome.TRUE_POSITIVE


def test_classify_decision_outcome_priority_hierarchy():
    """Verifies strict priority ordering: explicit flag -> verdict_str -> actions -> text -> default."""
    # 1. Explicit flag overrides verdict_str
    outcome_flag_override = classify_decision_outcome(
        ground_truth_threat=True,
        agent_contained_or_flagged=False,
        verdict_str="MALICIOUS",
    )
    assert outcome_flag_override == DecisionOutcome.FALSE_NEGATIVE

    # 2. verdict_str overrides actions
    outcome_verdict_override = classify_decision_outcome(
        ground_truth_threat=False,
        verdict_str="BENIGN",
        recommended_actions=["isolate_host"],
    )
    assert outcome_verdict_override == DecisionOutcome.TRUE_NEGATIVE

    # 3. actions override text analysis
    outcome_actions_override = classify_decision_outcome(
        ground_truth_threat=False,
        recommended_actions=["close_case"],
        response_text="The traffic seems suspicious and malicious.",
    )
    assert outcome_actions_override == DecisionOutcome.TRUE_NEGATIVE


def test_classify_decision_outcome_undetermined_default():
    """Verifies default non-threat classification when all inputs are empty or undetermined."""
    # Empty inputs default to threat = False
    assert classify_decision_outcome(ground_truth_threat=False) == DecisionOutcome.TRUE_NEGATIVE
    assert classify_decision_outcome(ground_truth_threat=True) == DecisionOutcome.FALSE_NEGATIVE


def test_counterfactual_consistency_perfect_discrimination():
    """Verifies counterfactual consistency calculation with 100% consistent pairs (1.0)."""
    eval_cases = [
        {
            "eval_id": "CASE-01",
            "ground_truth_label": "MALICIOUS",
            "counterfactual_pair_id": "CASE-06",
            "expected_actions": ["isolate_host"],
        },
        {
            "eval_id": "CASE-06",
            "ground_truth_label": "SUSPICIOUS",
            "counterfactual_pair_id": "CASE-01",
            "prohibited_actions": ["isolate_host"],
        },
        {
            "eval_id": "CASE-05",
            "ground_truth_label": "MALICIOUS",
            "counterfactual_pair_id": "CASE-10",
            "expected_actions": ["isolate_host"],
        },
        {
            "eval_id": "CASE-10",
            "ground_truth_label": "BENIGN",
            "counterfactual_pair_id": "CASE-05",
            "prohibited_actions": ["isolate_host"],
        },
    ]

    # Model correctly isolates threat and avoids isolating non-threat twins
    case_results = [
        {"eval_id": "CASE-01", "executed_actions": ["isolate_host"], "decision_outcome": "TRUE_POSITIVE"},
        {"eval_id": "CASE-06", "executed_actions": ["update_case_comment"], "decision_outcome": "TRUE_NEGATIVE"},
        {"eval_id": "CASE-05", "executed_actions": ["isolate_host"], "decision_outcome": "TRUE_POSITIVE"},
        {"eval_id": "CASE-10", "executed_actions": ["close_case"], "decision_outcome": "TRUE_NEGATIVE"},
    ]

    report = calculate_counterfactual_consistency(case_results, eval_cases)
    assert report["counterfactual_consistency_score"] == 1.0
    assert report["total_pairs"] == 2
    assert report["evaluated_pairs"] == 2
    assert report["consistent_pairs"] == 2
    assert report["inconsistent_pairs"] == 0
    assert report["partial_pairs"] == 0
    assert len(report["pairs"]) == 2
    assert all(p["consistent"] for p in report["pairs"])


def test_counterfactual_consistency_inconsistent_containment():
    """Verifies counterfactual consistency calculation with inconsistent pairs (0.0)."""
    eval_cases = [
        {
            "eval_id": "CASE-01",
            "ground_truth_label": "MALICIOUS",
            "counterfactual_pair_id": "CASE-06",
            "expected_actions": ["isolate_host"],
        },
        {
            "eval_id": "CASE-06",
            "ground_truth_label": "SUSPICIOUS",
            "counterfactual_pair_id": "CASE-01",
            "prohibited_actions": ["isolate_host"],
        },
        {
            "eval_id": "CASE-05",
            "ground_truth_label": "MALICIOUS",
            "counterfactual_pair_id": "CASE-10",
            "expected_actions": ["isolate_host"],
        },
        {
            "eval_id": "CASE-10",
            "ground_truth_label": "BENIGN",
            "counterfactual_pair_id": "CASE-05",
            "prohibited_actions": ["isolate_host"],
        },
    ]

    # In pair 1: threat missed containment. In pair 2: non-threat mistakenly isolated.
    case_results = [
        {"eval_id": "CASE-01", "executed_actions": ["close_case"], "decision_outcome": "FALSE_NEGATIVE"},
        {"eval_id": "CASE-06", "executed_actions": ["update_case_comment"], "decision_outcome": "TRUE_NEGATIVE"},
        {"eval_id": "CASE-05", "executed_actions": ["isolate_host"], "decision_outcome": "TRUE_POSITIVE"},
        {"eval_id": "CASE-10", "executed_actions": ["isolate_host"], "decision_outcome": "FALSE_POSITIVE"},
    ]

    report = calculate_counterfactual_consistency(case_results, eval_cases)
    assert report["counterfactual_consistency_score"] == 0.0
    assert report["total_pairs"] == 2
    assert report["consistent_pairs"] == 0
    assert report["inconsistent_pairs"] == 2
    assert report["pairs"][0]["threat_contained"] is False
    assert report["pairs"][1]["non_threat_avoided_containment"] is False


def test_counterfactual_consistency_partial_pairs():
    """Verifies handling of partial pairs where one case result is missing."""
    eval_cases = [
        {
            "eval_id": "CASE-01",
            "ground_truth_label": "MALICIOUS",
            "counterfactual_pair_id": "CASE-06",
        },
        {
            "eval_id": "CASE-06",
            "ground_truth_label": "BENIGN",
            "counterfactual_pair_id": "CASE-01",
        },
        {
            "eval_id": "CASE-05",
            "ground_truth_label": "MALICIOUS",
            "counterfactual_pair_id": "CASE-10",
        },
        {
            "eval_id": "CASE-10",
            "ground_truth_label": "BENIGN",
            "counterfactual_pair_id": "CASE-05",
        },
    ]

    # CASE-10 is omitted from results
    case_results = [
        {"eval_id": "CASE-01", "executed_actions": ["isolate_host"], "decision_outcome": "TRUE_POSITIVE"},
        {"eval_id": "CASE-06", "executed_actions": ["close_case"], "decision_outcome": "TRUE_NEGATIVE"},
        {"eval_id": "CASE-05", "executed_actions": ["isolate_host"], "decision_outcome": "TRUE_POSITIVE"},
    ]

    report = calculate_counterfactual_consistency(case_results, eval_cases)
    assert report["total_pairs"] == 2
    assert report["evaluated_pairs"] == 1
    assert report["consistent_pairs"] == 1
    assert report["partial_pairs"] == 1
    assert report["counterfactual_consistency_score"] == 1.0


def test_counterfactual_consistency_shared_group_tags():
    """Verifies counterfactual pairing when cases share an explicit group identifier tag."""
    eval_cases = [
        {
            "eval_id": "THREAT-A",
            "ground_truth_label": "MALICIOUS",
            "counterfactual_pair_id": "PAIR-ALPHA",
        },
        {
            "eval_id": "BENIGN-A",
            "ground_truth_label": "BENIGN",
            "counterfactual_pair_id": "PAIR-ALPHA",
        },
    ]

    case_results = [
        {"eval_id": "THREAT-A", "executed_actions": ["block_indicator"], "decision_outcome": "TRUE_POSITIVE"},
        {"eval_id": "BENIGN-A", "executed_actions": ["close_case"], "decision_outcome": "TRUE_NEGATIVE"},
    ]

    report = calculate_counterfactual_consistency(case_results, eval_cases)
    assert report["counterfactual_consistency_score"] == 1.0
    assert report["consistent_pairs"] == 1

