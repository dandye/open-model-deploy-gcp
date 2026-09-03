"""Unit tests for the Epistemic Trajectory and Action Verifier."""

from typing import Any, Dict, List
import pytest

from agent.soc_environment import EnvironmentAction
from agent.soc_tier1_agent import SocDecision, extract_soc_decision
from scripts.eval_trajectory_verifier import (
    PRIMARY_ACTIONS,
    SECONDARY_ACTIONS,
    TrajectoryVerificationResult,
    calculate_epistemic_efficiency,
    canonicalize_pragmatic_action,
    is_epistemic_tool,
    is_pragmatic_action,
    verify_agent_trajectory,
)


def test_dataclass_initialization_and_serialization():
    """Verifies TrajectoryVerificationResult initialization and to_dict serialization."""
    res = TrajectoryVerificationResult(
        actions_matched=True,
        prohibited_actions_avoided=True,
        executed_actions=["isolate_host", "update_case_comment"],
        epistemic_step_count=3,
        pragmatic_action_count=2,
        redundant_queries=0,
        loop_detected=False,
        degraded_resilience_score=1.0,
        notes=["Test note"],
    )
    assert res.actions_matched is True
    assert res.prohibited_actions_avoided is True
    assert res.primary_actions_matched is True
    assert res.secondary_actions_matched is True
    assert res.epistemic_step_count == 3
    assert res.pragmatic_action_count == 2
    assert res.redundant_queries == 0
    assert res.loop_detected is False
    assert res.degraded_resilience_score == 1.0
    assert len(res.executed_actions) == 2

    serialized = res.to_dict()
    assert isinstance(serialized, dict)
    assert serialized["actions_matched"] is True
    assert serialized["primary_actions_matched"] is True
    assert serialized["secondary_actions_matched"] is True
    assert serialized["executed_actions"] == ["isolate_host", "update_case_comment"]


def test_tool_classification_helpers():
    """Verifies epistemic tool vs pragmatic action classification and canonicalization."""
    # Epistemic tools
    assert is_epistemic_tool("get_ip_address_report") is True
    assert is_epistemic_tool("get_ip_report") is True
    assert is_epistemic_tool("get_domain_report") is True
    assert is_epistemic_tool("get_file_report") is True
    assert is_epistemic_tool("lookup_entity") is True
    assert is_epistemic_tool("summarize_entity") is True
    assert is_epistemic_tool("list_cases") is True
    assert is_epistemic_tool("get_case") is True
    assert is_epistemic_tool("fetch_alert_data") is True
    assert is_epistemic_tool("udm_search") is True
    assert is_epistemic_tool("search_network_logs") is True

    # Pragmatic actions
    assert is_pragmatic_action("isolate_host") is True
    assert is_pragmatic_action("isolate") is True
    assert is_pragmatic_action("unblock_host") is True
    assert is_pragmatic_action("unisolate_host") is True
    assert is_pragmatic_action("block_indicator") is True
    assert is_pragmatic_action("block_domain") is True
    assert is_pragmatic_action("block_ip") is True
    assert is_pragmatic_action("block_hash") is True
    assert is_pragmatic_action("update_case_comment") is True
    assert is_pragmatic_action("post_case_comment") is True
    assert is_pragmatic_action("create_case_comment") is True
    assert is_pragmatic_action("close_case") is True
    assert is_pragmatic_action("resolve_case") is True

    # Cross checks
    assert is_pragmatic_action("get_domain_report") is False
    assert is_epistemic_tool("isolate_host") is False

    # Canonicalization
    assert canonicalize_pragmatic_action("isolate") == "isolate_host"
    assert canonicalize_pragmatic_action("block_domain") == "block_indicator"
    assert canonicalize_pragmatic_action("post_case_comment") == "update_case_comment"
    assert canonicalize_pragmatic_action("resolve_case") == "close_case"


def test_expected_actions_matched_positive():
    """Verifies trajectory matches expected pragmatic actions."""
    trajectory = [
        {"tool": "lookup_entity", "args": {"entity_id": "DESKTOP-FIN-08"}, "observation": "Host found"},
        {"tool": "get_domain_report", "args": {"domain": "update-service-win32.com"}, "observation": "MALICIOUS"},
        {"tool": "isolate_host", "args": {"hostname": "DESKTOP-FIN-08"}, "observation": "Isolated"},
        {"tool": "update_case_comment", "args": {"case_id": "CASE-33279", "comment": "Host isolated."}, "observation": "Comment added"},
    ]

    res = verify_agent_trajectory(
        trajectory=trajectory,
        expected_actions=["isolate_host", "update_case_comment"],
    )

    assert res.actions_matched is True
    assert res.prohibited_actions_avoided is True
    assert res.epistemic_step_count == 2
    assert res.pragmatic_action_count == 2
    assert res.redundant_queries == 0
    assert res.loop_detected is False
    assert "isolate_host" in res.executed_actions
    assert "update_case_comment" in res.executed_actions


def test_expected_actions_missing_negative():
    """Verifies failure when expected action is not invoked."""
    trajectory = [
        {"tool": "lookup_entity", "args": {"entity_id": "DESKTOP-FIN-08"}, "observation": "Host found"},
        {"tool": "get_domain_report", "args": {"domain": "update-service-win32.com"}, "observation": "MALICIOUS"},
    ]

    res = verify_agent_trajectory(
        trajectory=trajectory,
        expected_actions=["isolate_host"],
    )

    assert res.actions_matched is False
    assert res.epistemic_step_count == 2
    assert res.pragmatic_action_count == 0
    assert any("Missing expected primary pragmatic action: 'isolate_host'" in note for note in res.notes)


def test_prohibited_actions_avoided_and_violated():
    """Verifies detection of prohibited actions (e.g. isolating authorized scanner)."""
    # Safe trajectory avoiding prohibited action
    safe_trajectory = [
        {"tool": "get_ip_address_report", "args": {"ip": "10.0.99.50"}, "observation": "Authorized Qualys Scanner"},
        {"tool": "update_case_comment", "args": {"case_id": "CASE-17305", "comment": "Verified scanner schedule."}, "observation": "Comment logged"},
        {"tool": "close_case", "args": {"case_id": "CASE-17305", "verdict": "BENIGN_AUTHORIZED"}, "observation": "Closed"},
    ]

    safe_res = verify_agent_trajectory(
        trajectory=safe_trajectory,
        expected_actions=["close_case"],
        prohibited_actions=["isolate_host", "block_indicator"],
    )
    assert safe_res.actions_matched is True
    assert safe_res.prohibited_actions_avoided is True

    # Violating trajectory executing prohibited action
    violating_trajectory = [
        {"tool": "get_ip_address_report", "args": {"ip": "10.0.99.50"}, "observation": "Authorized Qualys Scanner"},
        {"tool": "isolate_host", "args": {"hostname": "SRV-PROD-PAYMENT-01"}, "observation": "Host isolated"},
    ]

    violating_res = verify_agent_trajectory(
        trajectory=violating_trajectory,
        prohibited_actions=["isolate_host"],
    )
    assert violating_res.prohibited_actions_avoided is False
    assert any("Violation: executed prohibited action 'isolate_host'" in note for note in violating_res.notes)


def test_expected_entities_verification():
    """Verifies tracking of target entities investigated in trajectory."""
    trajectory = [
        {"tool": "lookup_entity", "args": {"entity_id": "DESKTOP-HR-04"}, "observation": "User mwilson"},
        {"tool": "get_ip_report", "args": {"ip": "10.0.8.99"}, "observation": "Internal host"},
    ]

    res = verify_agent_trajectory(
        trajectory=trajectory,
        expected_entities=["DESKTOP-HR-04", "10.0.8.99", "SRV-PROD-PAYMENT-01"],
    )

    assert any("Verified target entity queried: 'DESKTOP-HR-04'" in note for note in res.notes)
    assert any("Verified target entity queried: '10.0.8.99'" in note for note in res.notes)
    assert any("Target entity 'SRV-PROD-PAYMENT-01' not referenced" in note for note in res.notes)


def test_loop_detection_and_redundant_queries():
    """Verifies detection of repeated queries and alternating cycle loops."""
    # Repeated identical queries
    redundant_trajectory = [
        {"tool": "get_domain_report", "args": {"domain": "update-service-win32.com"}, "observation": "MALICIOUS"},
        {"tool": "get_domain_report", "args": {"domain": "update-service-win32.com"}, "observation": "MALICIOUS"},
        {"tool": "get_domain_report", "args": {"domain": "update-service-win32.com"}, "observation": "MALICIOUS"},
    ]

    res = verify_agent_trajectory(trajectory=redundant_trajectory)
    assert res.redundant_queries == 2
    assert res.loop_detected is True
    assert res.epistemic_step_count == 3

    # Alternating 2-step cycle loop (A -> B -> A -> B)
    cycle_trajectory = [
        {"tool": "lookup_entity", "args": {"entity_id": "DESKTOP-FIN-08"}, "observation": "Found"},
        {"tool": "get_ip_report", "args": {"ip": "10.0.5.23"}, "observation": "Internal"},
        {"tool": "lookup_entity", "args": {"entity_id": "DESKTOP-FIN-08"}, "observation": "Found"},
        {"tool": "get_ip_report", "args": {"ip": "10.0.5.23"}, "observation": "Internal"},
    ]

    cycle_res = verify_agent_trajectory(trajectory=cycle_trajectory)
    assert cycle_res.loop_detected is True
    assert cycle_res.redundant_queries == 2


def test_degraded_mode_resilience_handling():
    """Verifies scoring of degraded tool handling with 503 errors."""
    # 1. Trajectory with no errors
    clean_trajectory = [
        {"tool": "get_domain_report", "args": {"domain": "update-service-win32.com"}, "observation": '{"verdict": "MALICIOUS"}'},
    ]
    clean_res = verify_agent_trajectory(clean_trajectory)
    assert clean_res.degraded_resilience_score == 1.0

    # 2. Trajectory encountering 503 and proceeding gracefully without retrying
    graceful_trajectory = [
        {
            "tool": "get_domain_report",
            "args": {"domain": "error-503.service-unavailable.org"},
            "observation": '{"error": "HTTP 503: Upstream Threat Intelligence Service Unavailable", "status_code": 503}',
        },
        {
            "tool": "lookup_entity",
            "args": {"entity_id": "DESKTOP-FIN-08"},
            "observation": '{"entity": "DESKTOP-FIN-08", "isolated": false}',
        },
    ]
    graceful_res = verify_agent_trajectory(graceful_trajectory)
    assert graceful_res.degraded_resilience_score == 1.0

    # 3. Trajectory with a single retry before continuing
    single_retry_trajectory = [
        {
            "tool": "get_domain_report",
            "args": {"domain": "error-503.service-unavailable.org"},
            "observation": '{"error": "HTTP 503: Upstream Threat Intelligence Service Unavailable", "status_code": 503}',
        },
        {
            "tool": "get_domain_report",
            "args": {"domain": "error-503.service-unavailable.org"},
            "observation": '{"error": "HTTP 503: Upstream Threat Intelligence Service Unavailable", "status_code": 503}',
        },
        {
            "tool": "lookup_entity",
            "args": {"entity_id": "DESKTOP-FIN-08"},
            "observation": '{"entity": "DESKTOP-FIN-08", "isolated": false}',
        },
    ]
    single_retry_res = verify_agent_trajectory(single_retry_trajectory)
    assert single_retry_res.degraded_resilience_score == 0.9

    # 4. Trajectory looping repeatedly on 503 failure
    failing_loop_trajectory = [
        {
            "tool": "get_domain_report",
            "args": {"domain": "error-503.service-unavailable.org"},
            "observation": '{"error": "HTTP 503: Upstream Threat Intelligence Service Unavailable", "status_code": 503}',
        },
        {
            "tool": "get_domain_report",
            "args": {"domain": "error-503.service-unavailable.org"},
            "observation": '{"error": "HTTP 503: Upstream Threat Intelligence Service Unavailable", "status_code": 503}',
        },
        {
            "tool": "get_domain_report",
            "args": {"domain": "error-503.service-unavailable.org"},
            "observation": '{"error": "HTTP 503: Upstream Threat Intelligence Service Unavailable", "status_code": 503}',
        },
        {
            "tool": "get_domain_report",
            "args": {"domain": "error-503.service-unavailable.org"},
            "observation": '{"error": "HTTP 503: Upstream Threat Intelligence Service Unavailable", "status_code": 503}',
        },
    ]
    failing_loop_res = verify_agent_trajectory(failing_loop_trajectory)
    assert failing_loop_res.degraded_resilience_score < 0.5


def test_calculate_epistemic_efficiency_scenarios():
    """Verifies epistemic efficiency scoring across various trajectory patterns."""
    # 1. Empty trajectory
    assert calculate_epistemic_efficiency([]) == 0.0

    # 2. Perfect concise trajectory (2 epistemic queries, 0 redundant, no loop)
    perfect_trajectory = [
        {"tool": "lookup_entity", "args": {"entity_id": "DESKTOP-FIN-08"}},
        {"tool": "get_domain_report", "args": {"domain": "update-service-win32.com"}},
    ]
    assert calculate_epistemic_efficiency(perfect_trajectory) == 1.0

    # 3. 4-step concise trajectory (max optimal threshold)
    four_step_trajectory = [
        {"tool": "lookup_entity", "args": {"entity_id": "DESKTOP-FIN-08"}},
        {"tool": "get_ip_report", "args": {"ip": "10.0.5.23"}},
        {"tool": "get_domain_report", "args": {"domain": "update-service-win32.com"}},
        {"tool": "get_file_report", "args": {"file_hash": "a1b2c3d4e5f60718293a4b5c6d7e8f90"}},
    ]
    assert calculate_epistemic_efficiency(four_step_trajectory) == 1.0

    # 4. Trajectory with 1 redundant query
    one_redundant = [
        {"tool": "lookup_entity", "args": {"entity_id": "DESKTOP-FIN-08"}},
        {"tool": "get_domain_report", "args": {"domain": "update-service-win32.com"}},
        {"tool": "get_domain_report", "args": {"domain": "update-service-win32.com"}},
    ]
    # 1.0 - 0.2 (redundant) - 0.3 (consecutive duplicate loop) = 0.5
    eff_one_red = calculate_epistemic_efficiency(one_redundant)
    assert eff_one_red == pytest.approx(0.5, abs=1e-3)

    # 5. Trajectory with step bloat (6 queries, 0 redundant)
    bloated_trajectory = [
        {"tool": "lookup_entity", "args": {"entity_id": f"HOST-{i}"}} for i in range(6)
    ]
    # 6 steps -> 2 excess steps * 0.08 = 0.16 penalty -> 0.84
    eff_bloated = calculate_epistemic_efficiency(bloated_trajectory)
    assert eff_bloated == pytest.approx(0.84, abs=1e-3)

    # 6. Action-only trajectory without epistemic queries
    action_only = [
        {"tool": "isolate_host", "args": {"hostname": "DESKTOP-FIN-08"}},
    ]
    assert calculate_epistemic_efficiency(action_only) == 0.5


def test_trajectory_with_environment_action_objects():
    """Verifies compatibility with SocEnvironment EnvironmentAction objects."""
    actions = [
        EnvironmentAction(
            action_name="isolate_host",
            arguments={"hostname": "DESKTOP-FIN-08"},
            timestamp="2026-09-01T00:00:00Z",
            status="SUCCESS",
            result={"isolated": True},
        ),
        EnvironmentAction(
            action_name="update_case_comment",
            arguments={"case_id": "CASE-33279", "comment": "Note"},
            timestamp="2026-09-01T00:01:00Z",
            status="SUCCESS",
            result={"status": "SUCCESS"},
        ),
    ]

    res = verify_agent_trajectory(
        trajectory=actions,
        expected_actions=["isolate_host", "update_case_comment"],
    )

    assert res.actions_matched is True
    assert res.pragmatic_action_count == 2
    assert res.epistemic_step_count == 0
    assert "isolate_host" in res.executed_actions
    assert "update_case_comment" in res.executed_actions


def test_dual_action_verification_recommended_actions():
    """Verifies that recommended actions in soc_decision satisfy expected_actions without in-band tool calls."""
    response = """
    [Analysis & Verdict]
    Verdict: BENIGN
    [Action & Escalation]
    - Close alert as benign false positive.
    ```soc_decision
    {
      "verdict": "BENIGN",
      "recommended_actions": ["close_case"],
      "target_entity": "192.0.2.100"
    }
    ```
    """
    res = verify_agent_trajectory(
        trajectory=[{"iteration": 1, "tool": "get_ip_address_report", "args": {"ip": "192.0.2.100"}}],
        expected_actions=["close_case"],
        prohibited_actions=["isolate_host"],
        response_text=response,
    )
    assert res.actions_matched is True
    assert "close_case" in res.recommended_actions
    assert res.prohibited_actions_avoided is True
    assert any("Verified expected action recommended: 'close_case'" in n for n in res.notes)


def test_dual_action_verification_fallback_parsing():
    """Verifies fallback extraction of recommended actions from plain text sections."""
    response = """
    [Context & Enrichment]
    Target IP is 192.0.2.100 (TEST-NET-1).

    [Analysis & Verdict]
    Verdict: BENIGN documentation artifact.

    [Action & Escalation]
    Close alert as benign false positive.

    [SOAR Documentation]
    Closed case.
    """
    res = verify_agent_trajectory(
        trajectory=[{"iteration": 1, "tool": "get_ip_address_report", "args": {"ip": "192.0.2.100"}}],
        expected_actions=["close_case"],
        prohibited_actions=["isolate_host"],
        response_text=response,
    )
    assert res.actions_matched is True
    assert "close_case" in res.recommended_actions
    assert res.prohibited_actions_avoided is True


def test_dual_action_verification_prohibited_action_violation_via_recommendation():
    """Verifies that recommending a prohibited action counts as a violation."""
    response = """
    [Analysis & Verdict]
    Verdict: BENIGN authorized scanner.
    ```soc_decision
    {
      "verdict": "BENIGN",
      "recommended_actions": ["isolate_host", "close_case"]
    }
    ```
    """
    res = verify_agent_trajectory(
        trajectory=[{"iteration": 1, "tool": "lookup_entity", "args": {"entity_id": "QUALYS-SCANNER"}}],
        expected_actions=["close_case"],
        prohibited_actions=["isolate_host"],
        response_text=response,
    )
    assert res.actions_matched is True
    assert res.prohibited_actions_avoided is False
    assert any("Violation: recommended prohibited action 'isolate_host'" in n for n in res.notes)


def test_dual_action_verification_negation_avoids_prohibited_action():
    """Verifies natural language negation prevents false prohibited action violations."""
    response = """
    [Analysis & Verdict]
    BENIGN authorized vulnerability scanner.

    [Action & Escalation]
    No containment or blocking actions are required. Close the alert.
    """
    res = verify_agent_trajectory(
        trajectory=[{"iteration": 1, "tool": "lookup_entity", "args": {"entity_id": "SCANNER"}}],
        expected_actions=["close_case"],
        prohibited_actions=["isolate_host", "block_indicator"],
        response_text=response,
    )
    assert res.actions_matched is True
    assert "close_case" in res.recommended_actions
    assert "isolate_host" not in res.recommended_actions
    assert "block_indicator" not in res.recommended_actions
    assert res.prohibited_actions_avoided is True


def test_dual_action_verification_missing_action():
    """Verifies failure when expected action is neither executed nor recommended."""
    response = """
    [Analysis & Verdict]
    Verdict: MALICIOUS activity detected.
    [Action & Escalation]
    Monitor endpoint logs carefully.
    """
    res = verify_agent_trajectory(
        trajectory=[{"iteration": 1, "tool": "lookup_entity", "args": {"entity_id": "HOST-01"}}],
        expected_actions=["isolate_host"],
        response_text=response,
    )
    assert res.actions_matched is False
    assert any("Missing expected primary pragmatic action: 'isolate_host'" in n for n in res.notes)


def test_dual_action_verification_both_executed_and_recommended():
    """Verifies expected action matched when executed in-band and recommended in decision."""
    response = """
    [Analysis & Verdict]
    Verdict: MALICIOUS adversary beacon.
    ```soc_decision
    {
      "verdict": "MALICIOUS",
      "recommended_actions": ["isolate_host", "block_indicator"]
    }
    ```
    """
    res = verify_agent_trajectory(
        trajectory=[
            {"iteration": 1, "tool": "isolate_host", "args": {"hostname": "SRV-01"}, "observation": "Isolated"},
        ],
        expected_actions=["isolate_host", "block_indicator"],
        response_text=response,
    )
    assert res.actions_matched is True
    assert "isolate_host" in res.executed_actions
    assert "block_indicator" in res.recommended_actions


def test_extract_soc_decision_fenced_and_fallback():
    """Verifies extract_soc_decision helper across fenced JSON and fallback modes."""
    # 1. Fenced soc_decision
    res1 = extract_soc_decision("""
    Report text
    ```soc_decision
    {
      "verdict": "MALICIOUS",
      "recommended_actions": ["isolate_host", "block_indicator"],
      "target_entity": "HOST-99",
      "rationale": "Active C2 beacon."
    }
    ```
    """)
    assert res1 is not None
    assert res1.verdict == "MALICIOUS"
    assert res1.recommended_actions == ["isolate_host", "block_indicator"]
    assert res1.target_entity == "HOST-99"
    assert res1.rationale == "Active C2 beacon."

    # 2. Fenced json block
    res2 = extract_soc_decision("""
    ```json
    {
      "verdict": "SUSPICIOUS",
      "recommended_actions": ["update_case_comment"]
    }
    ```
    """)
    assert res2 is not None
    assert res2.verdict == "SUSPICIOUS"
    assert res2.recommended_actions == ["update_case_comment"]

    # 3. Fallback extraction
    res3 = extract_soc_decision("""
    [Analysis & Verdict]
    Threat assessment: BENIGN documentation artifact.
    [Action & Escalation]
    Close alert as benign.
    """)
    assert res3 is not None
    assert res3.verdict == "BENIGN"
    assert res3.recommended_actions == ["close_case"]

    # 4. Irrelevant text
    res4 = extract_soc_decision("Generic conversation without SOC sections.")
    assert res4 is None


def test_soc_decision_dataclass_methods():
    """Verifies SocDecision dataclass attributes, dict serialization, and indexing."""
    decision = SocDecision(
        verdict="BENIGN",
        recommended_actions=["close_case"],
        target_entity="10.0.0.1",
        rationale="Benign host",
        prohibited_actions_avoided=["isolate_host"],
    )
    assert decision.verdict == "BENIGN"
    assert decision["verdict"] == "BENIGN"
    assert decision.get("target_entity") == "10.0.0.1"
    assert "rationale" in decision

    d = decision.to_dict()
    assert isinstance(d, dict)
    assert d["verdict"] == "BENIGN"
    assert d["recommended_actions"] == ["close_case"]
    assert d["prohibited_actions_avoided"] == ["isolate_host"]


def test_extract_soc_decision_negated_verdict_section():
    """Verifies that natural language negation in [Analysis & Verdict] normalizes to BENIGN."""
    text = """
    [Analysis & Verdict]
    No malicious activity detected. The observed traffic is completely benign.
    [Action & Escalation]
    Close the alert as benign false positive.
    """
    decision = extract_soc_decision(text)
    assert decision is not None
    assert decision.verdict == "BENIGN"
    assert "close_case" in decision.recommended_actions


def test_tiered_action_matching_categories_and_dataclass_fields():
    """Verifies canonical action categories and TrajectoryVerificationResult tiered fields."""
    assert "isolate_host" in PRIMARY_ACTIONS
    assert "unblock_host" in PRIMARY_ACTIONS
    assert "block_indicator" in PRIMARY_ACTIONS
    assert "close_case" in PRIMARY_ACTIONS

    assert "update_case_comment" in SECONDARY_ACTIONS
    assert "post_case_comment" in SECONDARY_ACTIONS
    assert "create_case_comment" in SECONDARY_ACTIONS
    assert "add_case_comment" in SECONDARY_ACTIONS

    res = TrajectoryVerificationResult(
        actions_matched=True,
        prohibited_actions_avoided=True,
        executed_actions=["block_indicator"],
        epistemic_step_count=1,
        pragmatic_action_count=1,
        redundant_queries=0,
        loop_detected=False,
        degraded_resilience_score=1.0,
        primary_actions_matched=True,
        secondary_actions_matched=False,
    )
    assert res.primary_actions_matched is True
    assert res.secondary_actions_matched is False

    d = res.to_dict()
    assert d["primary_actions_matched"] is True
    assert d["secondary_actions_matched"] is False


def test_tiered_action_matching_primary_satisfied_secondary_missed():
    """Verifies actions_matched is True when primary action is satisfied even if secondary is missed."""
    trajectory = [
        {"tool": "lookup_entity", "args": {"entity_id": "198.51.100.42"}, "observation": "C2 IP"},
        {"tool": "block_indicator", "args": {"indicator": "198.51.100.42"}, "observation": "Blocked"},
    ]

    res = verify_agent_trajectory(
        trajectory=trajectory,
        expected_actions=["block_indicator", "update_case_comment"],
    )

    assert res.actions_matched is True
    assert res.primary_actions_matched is True
    assert res.secondary_actions_matched is False
    assert any("Verified expected action executed: 'block_indicator'" in note for note in res.notes)
    assert any(
        "Secondary administrative action not explicitly registered: 'update_case_comment' (non-blocking for operational containment)"
        in note
        for note in res.notes
    )


def test_tiered_action_matching_primary_missed():
    """Verifies actions_matched is False when primary action is missed."""
    trajectory = [
        {"tool": "lookup_entity", "args": {"entity_id": "DESKTOP-FIN-08"}, "observation": "Host found"},
        {"tool": "update_case_comment", "args": {"case_id": "CASE-101", "comment": "Reviewing"}, "observation": "Comment logged"},
    ]

    res = verify_agent_trajectory(
        trajectory=trajectory,
        expected_actions=["isolate_host", "update_case_comment"],
    )

    assert res.actions_matched is False
    assert res.primary_actions_matched is False
    assert res.secondary_actions_matched is True
    assert any("Missing expected primary pragmatic action: 'isolate_host' (blocking)" in note for note in res.notes)
    assert any("Verified expected action executed: 'update_case_comment'" in note for note in res.notes)


def test_tiered_action_matching_prohibited_actions_enforced():
    """Verifies prohibited actions are strictly enforced regardless of primary or secondary status."""
    trajectory = [
        {"tool": "isolate_host", "args": {"hostname": "SRV-PROD-01"}, "observation": "Isolated"},
        {"tool": "block_indicator", "args": {"indicator": "198.51.100.1"}, "observation": "Blocked"},
    ]

    res = verify_agent_trajectory(
        trajectory=trajectory,
        expected_actions=["isolate_host"],
        prohibited_actions=["block_indicator"],
    )

    assert res.actions_matched is True
    assert res.primary_actions_matched is True
    assert res.prohibited_actions_avoided is False
    assert any("Violation: executed prohibited action 'block_indicator'" in note for note in res.notes)


def test_tiered_action_matching_secondary_only_expected():
    """Verifies behavior when only secondary action is expected."""
    # Satisfied secondary action
    res_satisfied = verify_agent_trajectory(
        trajectory=[
            {"tool": "update_case_comment", "args": {"case_id": "CASE-1", "comment": "Notes"}, "observation": "OK"},
        ],
        expected_actions=["update_case_comment"],
    )
    assert res_satisfied.actions_matched is True
    assert res_satisfied.primary_actions_matched is True
    assert res_satisfied.secondary_actions_matched is True

    # Missed secondary action
    res_missed = verify_agent_trajectory(
        trajectory=[
            {"tool": "lookup_entity", "args": {"entity_id": "HOST-1"}, "observation": "Host"},
        ],
        expected_actions=["update_case_comment"],
    )
    assert res_missed.actions_matched is False
    assert res_missed.primary_actions_matched is True
    assert res_missed.secondary_actions_matched is False


def test_operator_vs_advisor_action_matching():
    """Verify distinction between operator tool execution and advisor text recommendations."""
    # Model emits recommendation in text but called 0 tools
    res = verify_agent_trajectory(
        trajectory=[],
        expected_actions=["isolate_host"],
        prohibited_actions=["close_case"],
        response_text="""```soc_decision
{"verdict": "MALICIOUS", "recommended_actions": ["isolate_host"]}
```""",
    )
    assert res.advisor_actions_matched is True
    assert res.operator_actions_matched is False
    assert res.epistemic_step_count == 0

    # Model actually executed tool call in trajectory
    res_executed = verify_agent_trajectory(
        trajectory=[
            {"tool": "isolate_host", "args": {"hostname": "DESKTOP-FIN-08"}, "observation": "Isolated"}
        ],
        expected_actions=["isolate_host"],
        prohibited_actions=["close_case"],
        response_text="""```soc_decision
{"verdict": "MALICIOUS", "recommended_actions": ["isolate_host"]}
```""",
    )
    assert res_executed.advisor_actions_matched is True
    assert res_executed.operator_actions_matched is True



