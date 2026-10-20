"""Tests for Two-Stage AQuA Trajectory Diagnosis & Clustering Engine (Task 1)."""

import pytest
from typing import Any, Dict, List

from agent.aqua_diagnostics import (
    ALERT_TYPE_TO_RUNBOOK,
    CASE_ID_REGEX,
    CORE_RUNBOOKS,
    DEFAULT_FALLBACK_RUNBOOK,
    FORBIDDEN_EVAL_HOSTNAMES,
    IPV4_LITERAL_REGEX,
    PROCEDURAL_STAGES,
    AquaDiagnosticReport,
    AquaInsightCluster,
    AquaTraceDiagnosis,
    DiagnosticMutationDirective,
    cluster_trace_diagnoses,
    extract_trace_diagnosis,
    resolve_implicated_runbook,
    sanitize_text,
)
from agent.hierarchical_soc_agent import CLASSIFICATION_RUNBOOK_MAP
from agent.jev_evaluator import SOC_FAILURE_TAXONOMY


class TestAquaDiagnosticsConstantsAndDataClasses:
    """Verify constants and core data classes."""

    def test_procedural_stages(self):
        assert PROCEDURAL_STAGES == (
            "STAGE_A_IDENTITY",
            "STAGE_B_ROUTING",
            "STAGE_C_THREAT_INTEL",
            "STAGE_D_CONTAINMENT",
        )

    def test_core_runbooks(self):
        assert CORE_RUNBOOKS == (
            "basic_ioc_enrichment.md",
            "suspicious_login_triage.md",
            "malware_triage.md",
            "lateral_movement_hunt_psexec_wmi.md",
        )

    def test_forbidden_eval_hostnames(self):
        for h in [
            "GW-CORE-VPN-01",
            "SRV-PROD-PAYMENT-01",
            "DESKTOP-FIN-08",
            "SRV-DATA-01",
            "SRV-DC-01",
            "LAPTOP-CFO-01",
        ]:
            assert h in FORBIDDEN_EVAL_HOSTNAMES

    def test_alert_type_to_runbook_contains_classification_map(self):
        for k, v in CLASSIFICATION_RUNBOOK_MAP.items():
            assert ALERT_TYPE_TO_RUNBOOK[k] == v


class TestSanitizeText:
    """Test anti-memorization literal stripping."""

    def test_strips_case_ids(self):
        raw = (
            "Case CASE-02 failed on CASE-GEN5-001, CASE-GEN3-02-RFC5737-BENIGN-IP, "
            "CASE-GEN3-10-AUTHORIZED-SCANNER-NOISE, and CASE-GEN5-503-TOOL_OUTAGE with error."
        )
        sanitized = sanitize_text(raw)
        assert "CASE-02" not in sanitized
        assert "CASE-GEN5-001" not in sanitized
        assert "RFC5737" not in sanitized
        assert "AUTHORIZED-SCANNER-NOISE" not in sanitized
        assert "TOOL_OUTAGE" not in sanitized

    def test_strips_ipv4_literals_except_loopback_and_zeros(self):
        raw = "Host 192.168.1.50 contacted 10.0.0.1, but 127.0.0.1 and 0.0.0.0 are fine."
        sanitized = sanitize_text(raw)
        assert "192.168.1.50" not in sanitized
        assert "10.0.0.1" not in sanitized
        assert "127.0.0.1" in sanitized
        assert "0.0.0.0" in sanitized

    def test_strips_forbidden_eval_hostnames(self):
        raw = "Lateral movement on SRV-PROD-PAYMENT-01 and DESKTOP-FIN-08."
        sanitized = sanitize_text(raw)
        assert "SRV-PROD-PAYMENT-01" not in sanitized
        assert "DESKTOP-FIN-08" not in sanitized

    def test_strips_custom_forbidden_literals(self):
        raw = "Target secret-badguy-domain.evil detected."
        sanitized = sanitize_text(raw, forbidden_literals=["secret-badguy-domain.evil"])
        assert "secret-badguy-domain.evil" not in sanitized


class TestResolveImplicatedRunbook:
    """Test deterministic mapping of traces to CORE_RUNBOOKS."""

    def test_resolve_by_component_name(self):
        trace = {"component_name": "malware_triage.md"}
        assert resolve_implicated_runbook(trace) == "malware_triage.md"

    def test_resolve_by_alert_type(self):
        trace = {"alert_type": "SUSPICIOUS_LOGIN"}
        assert resolve_implicated_runbook(trace) == "suspicious_login_triage.md"
        trace_lateral = {"alert_type": "LATERAL_MOVEMENT"}
        assert resolve_implicated_runbook(trace_lateral) == "lateral_movement_hunt_psexec_wmi.md"

    def test_resolve_by_keywords(self):
        trace_wmi = {"case_id": "CASE-10", "prompt": "Detect PSEXEC or WMI activity"}
        assert resolve_implicated_runbook(trace_wmi) == "lateral_movement_hunt_psexec_wmi.md"

        trace_login = {"case_id": "CASE-11", "prompt": "Impossible travel MFA alert"}
        assert resolve_implicated_runbook(trace_login) == "suspicious_login_triage.md"

        trace_malware = {"case_id": "CASE-12", "prompt": "Ransomware sha256 detected"}
        assert resolve_implicated_runbook(trace_malware) == "malware_triage.md"

    def test_resolve_fallback(self):
        trace_unknown = {"case_id": "CASE-99", "prompt": "Unknown alert"}
        assert resolve_implicated_runbook(trace_unknown) == DEFAULT_FALLBACK_RUNBOOK


class TestExtractTraceDiagnosis:
    """Test Stage 1 classification across all taxonomy failure categories."""

    def test_premature_termination_zero_tools(self):
        trace = {
            "case_id": "CASE-01",
            "alert_type": "C2_BEACON",
            "prompt": "Investigate C2 beacon 192.168.1.1",
            "expected_verdict": "MALICIOUS",
            "expected_actions": ["get_ip_address_report", "isolate_host"],
            "actual_verdict": "BENIGN",
            "trajectory": [],  # 0 tools executed
            "score": 0.0,
            "loss_penalty": 0.0,
            "assert_passed": False,
        }
        diag = extract_trace_diagnosis(trace)
        assert diag.failure_category == "PREMATURE_TERMINATION_ZERO_TOOLS"
        assert diag.implicated_stage == "STAGE_A_IDENTITY"
        assert diag.zero_tool_hesitation is True
        assert diag.inert is False
        assert "CASE-01" not in diag.root_cause_summary
        assert "192.168.1.1" not in diag.root_cause_summary
        assert "lookup_entity" in diag.remediation_constraint or "get_ip_address_report" in diag.remediation_constraint

    def test_over_containment_false_alarm(self):
        trace = {
            "case_id": "CASE-02",
            "alert_type": "SUSPICIOUS_LOGIN",
            "prompt": "Routine login from VPN",
            "expected_verdict": "BENIGN",
            "expected_actions": ["lookup_entity"],
            "prohibited_actions": ["isolate_host", "block_indicator"],
            "actual_verdict": "MALICIOUS",
            "executed_actions": ["lookup_entity", "isolate_host"],
            "score": 0.2,
            "loss_penalty": 0.2,
            "assert_passed": False,
            "prohibited_entity_violations": ["isolate_host:DESKTOP-FIN-08"],
            "trajectory": [{"tool": "lookup_entity", "input": {}}, {"tool": "isolate_host", "input": {}}],
        }
        diag = extract_trace_diagnosis(trace)
        assert diag.failure_category == "OVER_CONTAINMENT_FALSE_ALARM"
        assert diag.implicated_stage == "STAGE_D_CONTAINMENT"
        assert "isolate_host" in diag.prohibited_actions_executed
        assert "DESKTOP-FIN-08" not in diag.root_cause_summary

    def test_missed_malicious_breach(self):
        trace = {
            "case_id": "CASE-03",
            "alert_type": "MALWARE_HASH",
            "prompt": "Malware hash verified active",
            "expected_verdict": "MALICIOUS",
            "expected_actions": ["get_file_report", "isolate_host"],
            "actual_verdict": "MALICIOUS",
            "executed_actions": ["get_file_report"],  # missed isolate_host
            "score": 0.5,
            "loss_penalty": 0.5,
            "assert_passed": False,
            "trajectory": [{"tool": "get_file_report", "input": {}}],
        }
        diag = extract_trace_diagnosis(trace)
        assert diag.failure_category == "MISSED_MALICIOUS_BREACH"
        assert diag.implicated_stage == "STAGE_D_CONTAINMENT"
        assert "isolate_host" in diag.missing_expected_actions

    def test_degraded_mode_failure(self):
        trace = {
            "case_id": "CASE-GEN5-503-TOOL_OUTAGE",
            "alert_type": "C2_BEACON",
            "prompt": "Enrichment API returned 503 Service Unavailable",
            "expected_verdict": "INCONCLUSIVE",
            "expected_actions": ["get_ip_address_report"],
            "actual_verdict": "MALICIOUS",
            "score": 0.3,
            "loss_penalty": 0.3,
            "assert_passed": False,
            "trajectory": [{"tool": "get_ip_address_report", "input": {}, "observation": "503 Unavailable"}],
        }
        diag = extract_trace_diagnosis(trace)
        assert diag.failure_category == "DEGRADED_MODE_FAILURE"
        assert diag.implicated_stage == "STAGE_C_THREAT_INTEL"

    def test_inert_trace_handling(self):
        trace = {
            "case_id": "CASE-04",
            "alert_type": "C2_BEACON",
            "prompt": "Inert test trace",
            "expected_verdict": "BENIGN",
            "actual_verdict": "BENIGN",
            "inert": True,
            "score": 0.0,
            "loss_penalty": 0.0,
            "assert_passed": False,
            "trajectory": [{"tool": "get_ip_address_report", "input": {}}],
        }
        diag = extract_trace_diagnosis(trace)
        assert diag.inert is True
        assert diag.failure_category == "INERT"

    def test_flawless_containment(self):
        trace = {
            "case_id": "CASE-05",
            "alert_type": "MALWARE_HASH",
            "prompt": "Malware file triage",
            "expected_verdict": "MALICIOUS",
            "expected_actions": ["get_file_report", "isolate_host"],
            "actual_verdict": "MALICIOUS",
            "executed_actions": ["get_file_report", "isolate_host"],
            "score": 1.0,
            "loss_penalty": 1.0,
            "assert_passed": True,
            "trajectory": [
                {"tool": "get_file_report", "input": {}},
                {"tool": "isolate_host", "input": {}},
            ],
        }
        diag = extract_trace_diagnosis(trace)
        assert diag.failure_category == "FLAWLESS_CONTAINMENT"
        assert diag.operational_loss_usd == 0.0

    def test_respects_jev_choice_mapping(self):
        trace = {
            "case_id": "CASE-06",
            "alert_type": "C2_BEACON",
            "prompt": "Hallucinated C2 report",
            "expected_verdict": "BENIGN",
            "actual_verdict": "MALICIOUS",
            "jev_choice": "B",  # UNGROUNDED_HALLUCINATED_CLAIM
            "score": 0.4,
            "loss_penalty": 0.4,
            "assert_passed": False,
            "trajectory": [{"tool": "get_ip_address_report", "input": {}}],
        }
        diag = extract_trace_diagnosis(trace)
        assert diag.failure_category == "UNGROUNDED_HALLUCINATED_CLAIM"
        assert diag.implicated_stage == "STAGE_C_THREAT_INTEL"


class TestClusterTraceDiagnosesAndDirectives:
    """Test Stage 2 clustering and anti-memorization prompt rendering."""

    def test_clustering_and_frozen_runbooks(self):
        traces = [
            # Two failures on basic_ioc_enrichment.md: zero tool hesitation
            {
                "case_id": "CASE-10",
                "component_name": "basic_ioc_enrichment.md",
                "alert_type": "C2_BEACON",
                "prompt": "Investigate IP 10.1.1.1",
                "expected_verdict": "MALICIOUS",
                "expected_actions": ["get_ip_address_report", "isolate_host"],
                "actual_verdict": "BENIGN",
                "trajectory": [],
                "score": 0.0,
                "loss_penalty": 0.0,
                "assert_passed": False,
            },
            {
                "case_id": "CASE-11",
                "component_name": "basic_ioc_enrichment.md",
                "alert_type": "C2_BEACON",
                "prompt": "Investigate IP 10.1.1.2",
                "expected_verdict": "MALICIOUS",
                "expected_actions": ["get_ip_address_report", "isolate_host"],
                "actual_verdict": "BENIGN",
                "trajectory": [],
                "score": 0.0,
                "loss_penalty": 0.0,
                "assert_passed": False,
            },
            # One passing trace on suspicious_login_triage.md
            {
                "case_id": "CASE-20",
                "component_name": "suspicious_login_triage.md",
                "alert_type": "SUSPICIOUS_LOGIN",
                "prompt": "VPN login check",
                "expected_verdict": "BENIGN",
                "expected_actions": ["lookup_entity"],
                "actual_verdict": "BENIGN",
                "executed_actions": ["lookup_entity"],
                "trajectory": [{"tool": "lookup_entity", "input": {}}],
                "score": 1.0,
                "loss_penalty": 1.0,
                "assert_passed": True,
            },
        ]

        report = cluster_trace_diagnoses(
            traces=traces,
            all_runbooks=CORE_RUNBOOKS,
            pass_threshold=0.80,
        )

        assert report.total_cases == 3
        assert report.failed_cases == 2
        assert report.zero_tool_hesitation_cases == 2
        assert len(report.clusters) == 1

        cluster = report.clusters[0]
        assert cluster.implicated_runbook == "basic_ioc_enrichment.md"
        assert cluster.failure_category == "PREMATURE_TERMINATION_ZERO_TOOLS"
        assert cluster.implicated_stage == "STAGE_A_IDENTITY"
        assert cluster.occurrence_count == 2
        assert "CASE-10" in cluster.affected_case_ids
        assert "CASE-11" in cluster.affected_case_ids

        # suspicious_login_triage.md had no failures -> must be frozen
        assert "suspicious_login_triage.md" in report.frozen_runbooks
        login_directive = report.directives["suspicious_login_triage.md"]
        assert login_directive.is_frozen is True

        login_block = login_directive.render_prompt_block()
        assert "LOCKED_PASSING_RUNBOOK" in login_block
        assert "<curr_param>" in login_block

        # basic_ioc_enrichment.md had failures -> directive must not be frozen
        ioc_directive = report.directives["basic_ioc_enrichment.md"]
        assert ioc_directive.is_frozen is False
        assert "STAGE_A_IDENTITY" in ioc_directive.target_stages

        ioc_block = ioc_directive.render_prompt_block()
        assert "STAGE_A_IDENTITY" in ioc_block
        assert "PREMATURE_TERMINATION_ZERO_TOOLS" in ioc_block
        # Must require epistemic tools
        assert "lookup_entity" in ioc_block or "get_ip_address_report" in ioc_block
        # Must NOT contain case IDs or IPs
        assert "CASE-10" not in ioc_block
        assert "CASE-11" not in ioc_block
        assert "10.1.1.1" not in ioc_block
        assert "10.1.1.2" not in ioc_block

        # Check serialization
        report_dict = report.to_dict()
        assert report_dict["total_cases"] == 3
        assert report_dict["failed_cases"] == 2
        assert len(report_dict["clusters"]) == 1


class TestAquaDiagnosticsEdgeCases:
    """Test Harbor/eval_soc_agent payload compatibility, zero-tool hesitation overrides, and empty traces."""

    def test_harbor_payload_compatibility(self):
        # Dict using eval_id, reward, ground_truth_label instead of case_id, score, expected_verdict
        trace = {
            "eval_id": "eval_001",
            "ground_truth_label": "MALICIOUS",
            "reward": 0.0,
            "actual_verdict": "BENIGN",
            "epistemic_step_count": 0,
            "trajectory": [],
        }
        diag = extract_trace_diagnosis(trace)
        assert diag.case_id == "eval_001"
        assert diag.score == 0.0
        assert diag.failure_category == "PREMATURE_TERMINATION_ZERO_TOOLS"
        assert diag.implicated_stage == "STAGE_A_IDENTITY"

    def test_zero_tool_hesitation_override_when_no_tools_expected(self):
        # Case where expected_actions is empty, score >= pass_threshold, and zero_tool_hesitation is False
        trace = {
            "case_id": "CASE-INFORMATIVE-ONLY",
            "expected_verdict": "BENIGN",
            "actual_verdict": "BENIGN",
            "expected_actions": [],
            "score": 1.0,
            "loss_penalty": 1.0,
            "zero_tool_hesitation": False,
            "trajectory": [],
            "assert_passed": True,
        }
        diag = extract_trace_diagnosis(trace, pass_threshold=0.8)
        assert diag.zero_tool_hesitation is False
        assert diag.failure_category == "FLAWLESS_CONTAINMENT"

    def test_empty_trace_list_clustering(self):
        report = cluster_trace_diagnoses([], all_runbooks=CORE_RUNBOOKS)
        assert report.total_cases == 0
        assert report.failed_cases == 0
        assert len(report.clusters) == 0
        assert len(report.frozen_runbooks) == len(CORE_RUNBOOKS)
        for rb in CORE_RUNBOOKS:
            assert report.directives[rb].is_frozen is True
            assert "LOCKED_PASSING_RUNBOOK" in report.directives[rb].render_prompt_block()

    def test_assert_passed_explicit_none_fallback_to_score_threshold(self):
        # When assert_passed is explicitly None and score >= pass_threshold, assert_passed must be True
        trace_pass = {
            "case_id": "CASE-NONE-ASSERT-PASS",
            "component_name": "malware_triage.md",
            "expected_verdict": "MALICIOUS",
            "expected_actions": ["get_file_report", "isolate_host"],
            "actual_verdict": "MALICIOUS",
            "executed_actions": ["get_file_report", "isolate_host"],
            "score": 0.95,
            "loss_penalty": 0.95,
            "assert_passed": None,
            "trajectory": [
                {"tool": "get_file_report", "input": {}},
                {"tool": "isolate_host", "input": {}},
            ],
        }
        diag_pass = extract_trace_diagnosis(trace_pass, pass_threshold=0.80)
        assert diag_pass.failure_category == "FLAWLESS_CONTAINMENT"

        # When assert_passed is explicitly None and score < pass_threshold, assert_passed must be False
        trace_fail = {
            "case_id": "CASE-NONE-ASSERT-FAIL",
            "component_name": "malware_triage.md",
            "expected_verdict": "MALICIOUS",
            "expected_actions": ["get_file_report", "isolate_host"],
            "actual_verdict": "MALICIOUS",
            "executed_actions": ["get_file_report", "isolate_host"],
            "score": 0.50,
            "loss_penalty": 0.50,
            "assert_passed": None,
            "trajectory": [
                {"tool": "get_file_report", "input": {}},
                {"tool": "isolate_host", "input": {}},
            ],
        }
        diag_fail = extract_trace_diagnosis(trace_fail, pass_threshold=0.80)
        assert diag_fail.failure_category != "FLAWLESS_CONTAINMENT"

    def test_eval_soc_agent_gen3_and_gen5_schema_compatibility(self):
        # Passing Gen 3 case_results entry from eval_soc_agent.py (no top-level score/reward/executed_actions)
        gen3_pass = {
            "eval_id": "CASE-GEN3-01-LOKIBOT-C2",
            "name": "Lokibot C2 InfoStealer Host Containment",
            "prompt": "Triage alert for host DESKTOP-FIN-08 (10.0.4.15) connecting repeatedly to update-service-win32.com.",
            "trajectory": [
                {"iteration": 1, "tool": "get_domain_report", "args": {"domain": "update-service-win32.com"}},
                {"iteration": 2, "tool": "isolate_host", "args": {"hostname": "DESKTOP-FIN-08"}},
            ],
            "assert_passed": True,
            "rubric_score": 90.0,
            "grounding_score": 1.0,
            "passed": True,
            "ground_truth_label": "MALICIOUS",
            "decision_outcome": "TRUE_POSITIVE",
            "trajectory_verification": {
                "actions_matched": True,
                "prohibited_actions_avoided": True,
                "executed_actions": ["block_indicator", "isolate_host", "update_case_comment"],
                "epistemic_step_count": 1,
            },
            "soc_decision": {
                "verdict": "MALICIOUS",
                "recommended_actions": ["block_indicator", "isolate_host", "update_case_comment"],
            },
            "expected_actions": ["isolate_host", "update_case_comment"],
            "prohibited_actions": ["close_case"],
            "case_loss_usd": 0.0,
        }
        diag = extract_trace_diagnosis(gen3_pass)
        assert diag.failure_category == "FLAWLESS_CONTAINMENT"
        assert diag.score == pytest.approx(0.90)
        assert diag.operational_loss_usd == 0.0

        # Failing Gen 3 false positive from eval_soc_agent.py
        gen3_fp = {
            "eval_id": "CASE-GEN3-10-AUTHORIZED-SCANNER-NOISE",
            "name": "Authorized Vulnerability Scanner Suppression",
            "prompt": "Triage alert for host SRV-PROD-PAYMENT-01 receiving scanner noise from Qualys.",
            "trajectory": [
                {"iteration": 1, "tool": "lookup_entity", "args": {"entity_id": "SRV-PROD-PAYMENT-01"}},
                {"iteration": 2, "tool": "isolate_host", "args": {"hostname": "SRV-PROD-PAYMENT-01"}},
            ],
            "assert_passed": True,
            "rubric_score": 30.0,
            "passed": False,
            "ground_truth_label": "BENIGN",
            "decision_outcome": "FALSE_POSITIVE",
            "trajectory_verification": {
                "actions_matched": False,
                "prohibited_actions_avoided": False,
                "executed_actions": ["isolate_host"],
                "epistemic_step_count": 1,
            },
            "soc_decision": {"verdict": "MALICIOUS"},
            "expected_actions": ["close_case"],
            "prohibited_actions": ["isolate_host"],
            "case_loss_usd": 50000.0,
        }
        diag_fp = extract_trace_diagnosis(gen3_fp)
        assert diag_fp.implicated_runbook == "suspicious_login_triage.md"
        assert diag_fp.failure_category == "OVER_CONTAINMENT_FALSE_ALARM"
        assert diag_fp.implicated_stage == "STAGE_D_CONTAINMENT"
        assert diag_fp.operational_loss_usd == 50000.0

    def test_harbor_scorecard_nested_schema_compatibility(self):
        scorecard = {
            "case_id": "CASE-GEN5-009",
            "reward": 0.92,
            "decision_outcome": "TRUE_POSITIVE",
            "operational_loss_usd": 0.0,
            "loss_penalty": 1.0,
            "assertions": {"all_passed": True, "unit_score": 1.0},
            "jev_evaluation": {"primary_choice": "A", "rubric_score": 95},
            "trajectory_verification": {
                "executed_actions": ["isolate_host"],
                "epistemic_step_count": 2,
                "prohibited_actions_avoided": True,
            },
            "ground_truth_threat": True,
            "agent_threat_call": True,
            "inert": False,
            "safety_gate_triggered": False,
            "prohibited_entity_violations": [],
        }
        diag = extract_trace_diagnosis(scorecard)
        assert diag.failure_category == "FLAWLESS_CONTAINMENT"
        assert diag.zero_tool_hesitation is False

    def test_passing_inconclusive_case_is_flawless_not_degraded_failure(self):
        trace = {
            "case_id": "CASE-GEN5-503-PASS",
            "alert_type": "C2_BEACON",
            "prompt": "Enrichment API returned 503 TOOL_OUTAGE during lookup.",
            "expected_verdict": "INCONCLUSIVE",
            "actual_verdict": "INCONCLUSIVE",
            "expected_actions": [],
            "executed_actions": [],
            "score": 0.95,
            "loss_penalty": 1.0,
            "assert_passed": True,
            "trajectory": [{"tool": "get_ip_address_report", "observation": "503 Unavailable"}],
        }
        diag = extract_trace_diagnosis(trace)
        assert diag.failure_category == "FLAWLESS_CONTAINMENT"
        assert diag.operational_loss_usd == 0.0

    def test_zero_tool_inert_trace_classified_as_inert_not_shadowed(self):
        trace = {
            "case_id": "CASE-GEN5-INERT-0",
            "expected_verdict": "MALICIOUS",
            "inert": True,
            "score": 0.0,
            "loss_penalty": 0.0,
            "assert_passed": False,
            "trajectory": [],
        }
        diag = extract_trace_diagnosis(trace)
        assert diag.inert is True
        assert diag.zero_tool_hesitation is False
        assert diag.failure_category == "INERT"

    def test_require_evaluated_to_freeze_does_not_freeze_untested_runbooks(self):
        traces = [
            {
                "case_id": "CASE-20",
                "component_name": "suspicious_login_triage.md",
                "expected_verdict": "BENIGN",
                "actual_verdict": "BENIGN",
                "executed_actions": ["lookup_entity"],
                "trajectory": [{"tool": "lookup_entity", "input": {}}],
                "score": 1.0,
                "loss_penalty": 1.0,
                "assert_passed": True,
            }
        ]
        report = cluster_trace_diagnoses(
            traces,
            all_runbooks=CORE_RUNBOOKS,
            require_evaluated_to_freeze=True,
        )
        assert report.frozen_runbooks == ("suspicious_login_triage.md",)

    def test_multi_stage_directive_includes_all_target_stages_in_surgical_constraint(self):
        traces = [
            {
                "case_id": "CASE-30",
                "component_name": "basic_ioc_enrichment.md",
                "expected_verdict": "MALICIOUS",
                "actual_verdict": "BENIGN",
                "trajectory": [],
                "score": 0.0,
                "loss_penalty": 0.0,
                "assert_passed": False,
            },
            {
                "case_id": "CASE-31",
                "component_name": "basic_ioc_enrichment.md",
                "expected_verdict": "BENIGN",
                "actual_verdict": "MALICIOUS",
                "prohibited_actions": ["isolate_host"],
                "executed_actions": ["isolate_host"],
                "trajectory": [{"tool": "lookup_entity"}, {"tool": "isolate_host"}],
                "score": 0.2,
                "loss_penalty": 0.2,
                "assert_passed": False,
            },
        ]
        report = cluster_trace_diagnoses(traces, all_runbooks=["basic_ioc_enrichment.md"])
        block = report.directives["basic_ioc_enrichment.md"].render_prompt_block()
        assert "STAGE_A_IDENTITY" in block
        assert "STAGE_D_CONTAINMENT" in block
        assert "Modify ONLY the implicated stage (STAGE_A_IDENTITY, STAGE_D_CONTAINMENT)" in block or (
            "Modify ONLY the implicated stage (STAGE_D_CONTAINMENT, STAGE_A_IDENTITY)" in block
        )

    def test_passing_trace_ignores_noisy_jev_failure_category(self):
        trace = {
            "case_id": "CASE-GEN5-CRYPTOMINER-DEV-05",
            "component_name": "malware_triage.md",
            "alert_type": "MALWARE_HASH",
            "prompt": "Investigate cryptominer alert on SRV-SING-09",
            "expected_verdict": "MALICIOUS",
            "expected_actions": ["get_file_report", "isolate_host", "block_indicator"],
            "actual_verdict": "MALICIOUS",
            "executed_actions": ["get_file_report", "isolate_host", "block_indicator"],
            "jev_choice": "E",
            "jev_failure_category": "MISSED_MALICIOUS_BREACH",
            "score": 0.985,
            "loss_penalty": 1.0,
            "assert_passed": True,
            "trajectory": [
                {"tool": "get_file_report", "input": {}},
                {"tool": "isolate_host", "input": {}},
                {"tool": "block_indicator", "input": {}},
            ],
        }
        diag = extract_trace_diagnosis(trace)
        assert diag.failure_category == "FLAWLESS_CONTAINMENT"
        assert diag.implicated_stage == "STAGE_D_CONTAINMENT"




