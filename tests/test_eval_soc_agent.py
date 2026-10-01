"""Unit tests for the SOC Tier 1 evaluation runner assertion logic and reporting."""

import json
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.eval_soc_agent import (
    SemanticJudgeResult,
    calculate_aggregate_score,
    evaluate_assertions,
    judge_response_with_llm,
    main,
    run_evaluation,
)

CONFIG_PATH = ROOT_DIR / "configs" / "evals" / "soc_tier1_triage.json"
GEN3_CONFIG_PATH = ROOT_DIR / "configs" / "evals" / "gen3" / "soc_tier1_interactive.json"


def test_evaluate_assertions_on_new_cases():
    """Verify assertion engine validates expected strings on simulated responses (Task 4 Brief)."""
    # Case 06: DNS Tunneling
    resp_06 = (
        "Identified borderline DNS tunnel on tunnel-data.cdn-edge-update.net. "
        "Recommend rate limiting and traffic capture."
    )
    passed, fails = evaluate_assertions(
        resp_06, ["tunnel-data.cdn-edge-update.net", "tunnel"], ["CRITICAL RANSOMWARE"]
    )
    assert passed is True
    assert len(fails) == 0

    # Case 09: Tool Failure
    resp_09 = (
        "Encountered HTTP 503 error on domain lookup. Relying on host telemetry. "
        "Threat intelligence service unavailable."
    )
    passed, fails = evaluate_assertions(resp_09, ["503", "unavailable"], ["Lokibot"])
    assert passed is True
    assert len(fails) == 0

    # Case 10: Authorized Scanner
    resp_10 = (
        "Identified 10.0.99.50 as internal authorized vulnerability scanner (Qualys). "
        "Closing alert as benign false positive."
    )
    passed, fails = evaluate_assertions(
        resp_10, ["10.0.99.50", "scanner"], ["MALICIOUS", "isolate host"]
    )
    assert passed is True
    assert len(fails) == 0


CONFORMING_RESPONSES = {
    "CASE-01-LOKIBOT-C2": (
        "Host DESKTOP-FIN-08 exhibited persistent beaconing to update-service-win32.com. "
        "Recommend immediate host isolation and escalation to Tier 2."
    ),
    "CASE-02-RFC5737-BENIGN-IP": (
        "The IP address 192.0.2.100 is reserved under TEST-NET-1 (RFC 5737) for documentation. "
        "Non-routable and benign."
    ),
    "CASE-03-PHISHING-CRED-HARVEST": (
        "Detected credential harvesting phishing email sent to user john.doe@company.com "
        "from evil.com. Revoke credentials and block sender."
    ),
    "CASE-04-DUPLICATE-SOAR-CASE": (
        "Found existing duplicate investigation CASE-33279. Appending findings to case 33279."
    ),
    "CASE-05-RANSOMWARE-ESCALATION": (
        "Active ransomware infection on file server. Isolate network interface immediately "
        "and escalate to Incident Response."
    ),
    "CASE-06-AMBIGUOUS-DNS-TUNNEL": (
        "Identified borderline DNS tunnel on tunnel-data.cdn-edge-update.net. "
        "Recommend rate limiting and traffic capture."
    ),
    "CASE-07-LATERAL-MOVEMENT": (
        "Detected lateral movement activity initiated from DESKTOP-HR-04 targeting server "
        "10.0.8.99 via SMB. Isolate host and revoke credentials."
    ),
    "CASE-08-SUPPLY-CHAIN-REVOKED-CERT": (
        "Binary hash a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90 from Acme Corp "
        "has a revoked digital certificate. Quarantine binary."
    ),
    "CASE-09-TOOL-FAILURE-RESILIENCE": (
        "Encountered HTTP 503 error on domain lookup. Relying on host telemetry. "
        "Threat intelligence service unavailable."
    ),
    "CASE-10-AUTHORIZED-SCANNER-TRUE-NEGATIVE": (
        "Identified 10.0.99.50 as internal authorized vulnerability scanner (Qualys). "
        "Closing alert as benign false positive."
    ),
}

GEN3_CONFORMING_RESPONSES = {
    "CASE-GEN3-01-LOKIBOT-C2": (
        "Host DESKTOP-FIN-08 exhibited persistent beaconing to update-service-win32.com. "
        "Executing host isolation and updating case documentation. Escalating to Tier 2.\n"
        "```soc_decision\n"
        "{\n"
        '  "verdict": "MALICIOUS",\n'
        '  "recommended_actions": ["isolate_host", "update_case_comment"],\n'
        '  "target_entity": "DESKTOP-FIN-08",\n'
        '  "rationale": "Active Lokibot C2 beaconing to update-service-win32.com"\n'
        "}\n"
        "```"
    ),
    "CASE-GEN3-02-RFC5737-BENIGN-IP": (
        "The IP address 192.0.2.100 is reserved under TEST-NET-1 (RFC 5737) for documentation. "
        "Non-routable and benign. Resolving and closing alert safely.\n"
        "```soc_decision\n"
        "{\n"
        '  "verdict": "BENIGN",\n'
        '  "recommended_actions": ["close_case"],\n'
        '  "target_entity": "192.0.2.100",\n'
        '  "rationale": "RFC-5737 documentation subnet is non-routable"\n'
        "}\n"
        "```"
    ),
    "CASE-GEN3-03-PHISHING-CRED-HARVEST": (
        "Detected credential harvesting phishing email sent to user john.doe from evil.com. "
        "Executing block_indicator on evil.com and updating case comment.\n"
        "```soc_decision\n"
        "{\n"
        '  "verdict": "MALICIOUS",\n'
        '  "recommended_actions": ["block_indicator", "update_case_comment"],\n'
        '  "target_entity": "evil.com",\n'
        '  "rationale": "Phishing infrastructure targeting john.doe"\n'
        "}\n"
        "```"
    ),
    "CASE-GEN3-04-DUPLICATE-SOAR-CASE": (
        "Found existing duplicate investigation CASE-33279. Appending findings to case 33279 comment.\n"
        "```soc_decision\n"
        "{\n"
        '  "verdict": "SUSPICIOUS",\n'
        '  "recommended_actions": ["update_case_comment"],\n'
        '  "target_entity": "198.51.100.42",\n'
        '  "rationale": "Existing case 33279 found; appended notes without duplicate ticket"\n'
        "}\n"
        "```"
    ),
    "CASE-GEN3-05-RANSOMWARE-ESCALATION": (
        "Active ransomware infection on file server 10.0.5.23 (DESKTOP-FIN-08). Executing isolate_host immediately "
        "and escalating to Incident Response.\n"
        "```soc_decision\n"
        "{\n"
        '  "verdict": "MALICIOUS",\n'
        '  "recommended_actions": ["isolate_host", "update_case_comment"],\n'
        '  "target_entity": "DESKTOP-FIN-08",\n'
        '  "rationale": "Critical ransomware infection with README_DECRYPT on 10.0.5.23"\n'
        "}\n"
        "```"
    ),
    "CASE-GEN3-06-AMBIGUOUS-DNS-TUNNEL": (
        "Identified borderline DNS tunnel on tunnel-data.cdn-edge-update.net from DESKTOP-FIN-08. "
        "Updating case comment with monitoring request while avoiding disruptive isolation.\n"
        "```soc_decision\n"
        "{\n"
        '  "verdict": "SUSPICIOUS",\n'
        '  "recommended_actions": ["update_case_comment"],\n'
        '  "target_entity": "tunnel-data.cdn-edge-update.net",\n'
        '  "rationale": "Borderline DNS tunnel requires monitoring without disruptive isolation"\n'
        "}\n"
        "```"
    ),
    "CASE-GEN3-07-LATERAL-MOVEMENT-PSEXEC": (
        "Detected lateral movement activity initiated from DESKTOP-HR-04 (10.0.8.99) via PsExec. "
        "Executing isolate_host and updating case comment.\n"
        "```soc_decision\n"
        "{\n"
        '  "verdict": "MALICIOUS",\n'
        '  "recommended_actions": ["isolate_host", "update_case_comment"],\n'
        '  "target_entity": "DESKTOP-HR-04",\n'
        '  "rationale": "PsExec lateral movement from mwilson on 10.0.8.99"\n'
        "}\n"
        "```"
    ),
    "CASE-GEN3-08-SUPPLY-CHAIN-REVOKED-CERT": (
        "Binary hash a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90 for invoice_update.exe "
        "has a revoked certificate. Executing block_indicator and updating case comment.\n"
        "```soc_decision\n"
        "{\n"
        '  "verdict": "SUSPICIOUS",\n'
        '  "recommended_actions": ["block_indicator", "update_case_comment"],\n'
        '  "target_entity": "invoice_update.exe",\n'
        '  "rationale": "Revoked certificate on invoice_update.exe binary"\n'
        "}\n"
        "```"
    ),
    "CASE-GEN3-09-TOOL-503-OUTAGE-RESILIENCE": (
        "Encountered HTTP 503 error on domain lookup for error-503.service-unavailable.org. "
        "Threat intelligence service unavailable. Documented inconclusive status in case comment.\n"
        "```soc_decision\n"
        "{\n"
        '  "verdict": "INCONCLUSIVE",\n'
        '  "recommended_actions": ["update_case_comment"],\n'
        '  "target_entity": "error-503.service-unavailable.org",\n'
        '  "rationale": "503 Service Unavailable encountered; retained case for retry"\n'
        "}\n"
        "```"
    ),
    "CASE-GEN3-10-AUTHORIZED-SCANNER-NOISE": (
        "Identified host SRV-PROD-PAYMENT-01 (10.0.99.50) port scan as authorized Qualys Scanner testing. "
        "Updating case comment and closing case safely.\n"
        "```soc_decision\n"
        "{\n"
        '  "verdict": "BENIGN",\n'
        '  "recommended_actions": ["close_case", "update_case_comment"],\n'
        '  "target_entity": "SRV-PROD-PAYMENT-01",\n'
        '  "rationale": "Authorized Qualys vulnerability scanner testing"\n'
        "}\n"
        "```"
    ),
}


def test_evaluate_assertions_all_10_cases_conforming():
    """Verify assertion checking passes for all 10 cases with conforming responses."""
    assert CONFIG_PATH.exists(), f"Missing config file at {CONFIG_PATH}"
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    for case in data["eval_cases"]:
        case_id = case["eval_id"]
        assert case_id in CONFORMING_RESPONSES, f"Missing simulated response for {case_id}"
        resp_text = CONFORMING_RESPONSES[case_id]
        must_contain = case.get("assertions", {}).get("must_contain", [])
        must_not_contain = case.get("assertions", {}).get("must_not_contain", [])

        passed, failures = evaluate_assertions(
            response_text=resp_text,
            must_contain=must_contain,
            must_not_contain=must_not_contain,
        )
        assert passed is True, f"Case {case_id} failed assertions unexpectedly: {failures}"
        assert len(failures) == 0


def test_evaluate_assertions_all_10_cases_missing_must_contain():
    """Verify assertion checking fails when required substrings are missing across all 10 cases."""
    assert CONFIG_PATH.exists()
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    empty_response = "Generic uninformative response without required indicators."
    for case in data["eval_cases"]:
        case_id = case["eval_id"]
        must_contain = case.get("assertions", {}).get("must_contain", [])
        must_not_contain = case.get("assertions", {}).get("must_not_contain", [])

        passed, failures = evaluate_assertions(
            response_text=empty_response,
            must_contain=must_contain,
            must_not_contain=must_not_contain,
        )
        assert passed is False, f"Case {case_id} should have failed due to missing must_contain"
        assert len(failures) == len(must_contain)
        for fail_msg in failures:
            assert "Missing required substring" in fail_msg


def test_evaluate_assertions_all_10_cases_prohibited_substrings():
    """Verify assertion checking fails when prohibited substrings are injected across all 10 cases."""
    assert CONFIG_PATH.exists()
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    for case in data["eval_cases"]:
        case_id = case["eval_id"]
        base_resp = CONFORMING_RESPONSES[case_id]
        must_contain = case.get("assertions", {}).get("must_contain", [])
        must_not_contain = case.get("assertions", {}).get("must_not_contain", [])

        if not must_not_contain:
            continue

        for prohibited in must_not_contain:
            bad_response = f"{base_resp} Injected prohibited text: {prohibited}"
            passed, failures = evaluate_assertions(
                response_text=bad_response,
                must_contain=must_contain,
                must_not_contain=must_not_contain,
            )
            assert passed is False, f"Case {case_id} should have failed due to prohibited: {prohibited}"
            prohibited_failures = [f for f in failures if "Contained prohibited substring" in f]
            assert len(prohibited_failures) >= 1
            assert any(prohibited.lower() in f.lower() for f in prohibited_failures)


def test_evaluate_assertions_case_insensitivity():
    """Verify assertion checking handles uppercase, lowercase, and mixed-case inputs."""
    text = "UPPERCASE DOMAIN update-service-win32.com ON HOST desktop-fin-08 MUST ESCALATE."
    passed, failures = evaluate_assertions(
        response_text=text,
        must_contain=["UPDATE-SERVICE-WIN32.COM", "DESKTOP-FIN-08", "escalat"],
        must_not_contain=["benign", "FALSE POSITIVE"],
    )
    assert passed is True
    assert len(failures) == 0

    prohibited_text = "Host DESKTOP-FIN-08 was found to be benign."
    passed, failures = evaluate_assertions(
        response_text=prohibited_text,
        must_contain=["desktop-fin-08"],
        must_not_contain=["BENIGN"],
    )
    assert passed is False
    assert len(failures) == 1
    assert "Contained prohibited substring: 'BENIGN'" in failures[0]


def test_evaluate_assertions_edge_cases():
    """Verify assertion checking handles None, empty strings, and empty rule lists."""
    passed, failures = evaluate_assertions("", [], [])
    assert passed is True
    assert len(failures) == 0

    passed, failures = evaluate_assertions(None, ["required"], None)
    assert passed is False
    assert len(failures) == 1

    passed, failures = evaluate_assertions("Some text", None, None)
    assert passed is True
    assert len(failures) == 0


def test_calculate_aggregate_score_10_cases():
    """Verify calculate_aggregate_score computes correct statistics across 10 cases."""
    results = [
        {"eval_id": f"CASE-0{i+1}", "rubric_score": 80.0 + i * 2, "passed": i % 2 == 0, "latency_s": 2.0 + i * 0.1, "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}, "trajectory": [{"tool": "test"}]}
        for i in range(10)
    ]
    summary = calculate_aggregate_score(results, gen=2)

    assert summary["total_cases"] == 10
    assert summary["passed_cases"] == 5
    assert summary["pass_rate"] == 50.0
    assert summary["avg_rubric_score"] == pytest.approx(89.0, rel=1e-2)
    assert summary["total_prompt_tokens"] == 1000
    assert summary["total_completion_tokens"] == 500
    assert summary["total_tokens"] == 1500
    assert summary["avg_tokens_per_case"] == 150.0
    assert summary["total_tool_calls"] == 10
    assert summary["avg_latency_s"] == pytest.approx(2.45, rel=1e-2)
    assert summary["avg_generation_tps"] > 0
    assert summary["avg_total_tps"] > 0


def test_calculate_aggregate_score_empty_results():
    """Verify calculate_aggregate_score defaults cleanly for empty results on Gen 2 and Gen 3."""
    gen2_summary = calculate_aggregate_score([], gen=2)
    assert gen2_summary["total_cases"] == 0
    assert gen2_summary["pass_rate"] == 0.0

    gen3_summary = calculate_aggregate_score([], gen=3)
    assert gen3_summary["total_cases"] == 0
    assert gen3_summary["actions_matched_rate"] == 0.0
    assert gen3_summary["operator_actions_matched_rate"] == 0.0
    assert gen3_summary["advisor_actions_matched_rate"] == 0.0
    assert gen3_summary["prohibited_avoided_rate"] == 0.0


def test_calculate_aggregate_score_gen3_sdt_and_loss():
    """Verify calculate_aggregate_score computes SDT metrics and operational loss matrix for Gen 3."""
    results = [
        {
            "eval_id": "CASE-GEN3-01",
            "rubric_score": 90.0,
            "passed": True,
            "latency_s": 2.5,
            "usage": {"total_tokens": 1500},
            "trajectory": [{"tool": "get_domain_report"}, {"tool": "isolate_host"}],
            "decision_outcome": "TRUE_POSITIVE",
            "asset_criticality": "STANDARD",
            "epistemic_efficiency": 1.0,
            "trajectory_verification": {"actions_matched": True, "prohibited_actions_avoided": True},
        },
        {
            "eval_id": "CASE-GEN3-02",
            "rubric_score": 85.0,
            "passed": True,
            "latency_s": 1.5,
            "usage": {"total_tokens": 1000},
            "trajectory": [{"tool": "get_ip_report"}, {"tool": "close_case"}],
            "decision_outcome": "TRUE_NEGATIVE",
            "asset_criticality": "LOW",
            "epistemic_efficiency": 1.0,
            "trajectory_verification": {"actions_matched": True, "prohibited_actions_avoided": True},
        },
        {
            "eval_id": "CASE-GEN3-03",
            "rubric_score": 70.0,
            "passed": False,
            "latency_s": 3.0,
            "usage": {"total_tokens": 2000},
            "trajectory": [{"tool": "get_file_report"}],
            "decision_outcome": "FALSE_NEGATIVE",
            "asset_criticality": "HIGH",
            "epistemic_efficiency": 0.8,
            "trajectory_verification": {"actions_matched": False, "prohibited_actions_avoided": True},
        },
        {
            "eval_id": "CASE-GEN3-04",
            "rubric_score": 60.0,
            "passed": False,
            "latency_s": 2.0,
            "usage": {"total_tokens": 1200},
            "trajectory": [{"tool": "isolate_host"}],
            "decision_outcome": "FALSE_POSITIVE",
            "asset_criticality": "STANDARD",
            "epistemic_efficiency": 0.5,
            "trajectory_verification": {"actions_matched": True, "prohibited_actions_avoided": False},
        },
    ]

    summary = calculate_aggregate_score(results, gen=3)
    assert summary["total_cases"] == 4
    assert summary["passed_cases"] == 2
    assert summary["pass_rate"] == 50.0
    assert "sdt_metrics" in summary
    assert "operational_loss" in summary
    sdt = summary["sdt_metrics"]
    assert sdt["hits"] == 1
    assert sdt["correct_rejections"] == 1
    assert sdt["misses"] == 1
    assert sdt["false_alarms"] == 1

    loss = summary["operational_loss"]
    # FP Standard ($250) + FN High ($50,000) = $50,250 + compute cost
    assert loss["fp_loss_usd"] == 250.0
    assert loss["fn_loss_usd"] == 50000.0
    assert loss["total_loss_usd"] > 50250.0

    assert summary["avg_epistemic_efficiency"] == pytest.approx(0.825, rel=1e-2)
    assert summary["actions_matched_rate"] == 75.0
    assert summary["prohibited_avoided_rate"] == 75.0


def test_run_evaluation_10_cases_mocked():
    """Verify run_evaluation executes Gen 2 cases and compiles summary output."""
    assert CONFIG_PATH.exists()

    with patch("scripts.eval_soc_agent.SocTier1Agent") as mock_agent_cls, \
         patch("scripts.eval_soc_agent.genai.Client") as mock_genai_cls, \
         patch("scripts.eval_soc_agent.judge_response_with_llm") as mock_judge:

        mock_agent = MagicMock()
        def mock_query(prompt: str):
            for case_id, resp in CONFORMING_RESPONSES.items():
                return {
                    "response": resp,
                    "backend": "MockBackend",
                    "usage": {"prompt_tokens": 120, "completion_tokens": 60, "total_tokens": 180},
                    "trajectory": [{"iteration": 1, "tool": "lookup_entity", "args": {"entity_id": "10.0.4.15"}, "observation": "{}"}],
                }
            return {"response": "default", "usage": {}, "trajectory": []}

        mock_agent.query.side_effect = mock_query
        mock_agent_cls.return_value = mock_agent

        mock_judge.return_value = SemanticJudgeResult(
            rubric_score=90.0,
            passed=True,
            grounding_score=0.95,
            critique="Appropriate SOC triage response.",
        )

        eval_result = run_evaluation(
            evalset_path=CONFIG_PATH,
            flavor="gemma-3-4b-it",
            project_id="test-proj",
            region="us-central1",
            gen=2,
        )

        assert eval_result["flavor"] == "gemma-3-4b-it"
        assert eval_result["summary"]["total_cases"] == 10
        assert len(eval_result["case_results"]) == 10
        assert eval_result["summary"]["total_prompt_tokens"] == 1200
        assert eval_result["summary"]["total_completion_tokens"] == 600
        assert eval_result["summary"]["total_tokens"] == 1800
        assert eval_result["summary"]["total_tool_calls"] == 10


def test_run_evaluation_gen3_interactive_mocked():
    """Verify run_evaluation executes all 10 Gen 3 interactive cases with SDT and loss engine."""
    assert GEN3_CONFIG_PATH.exists(), f"Gen 3 evalset missing at {GEN3_CONFIG_PATH}"

    with patch("scripts.eval_soc_agent.SocTier1Agent") as mock_agent_cls, \
         patch("scripts.eval_soc_agent.genai.Client") as mock_genai_cls, \
         patch("scripts.eval_soc_agent.judge_response_with_llm") as mock_judge:

        mock_agent = MagicMock()

        def mock_query(prompt: str):
            # Match prompt to simulated response
            for case_id, resp in GEN3_CONFORMING_RESPONSES.items():
                if "192.0.2.100" in prompt:
                    return {
                        "response": GEN3_CONFORMING_RESPONSES["CASE-GEN3-02-RFC5737-BENIGN-IP"],
                        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
                        "trajectory": [
                            {"iteration": 1, "tool": "get_ip_address_report", "args": {"ip": "192.0.2.100"}, "observation": "RFC 5737 Test IP"},
                            {"iteration": 2, "tool": "close_case", "args": {"case_id": "CASE-02", "verdict": "BENIGN"}, "observation": "Closed"},
                        ],
                    }
                elif "503" in prompt or "outage" in prompt.lower() or "error-503" in prompt:
                    return {
                        "response": GEN3_CONFORMING_RESPONSES["CASE-GEN3-09-TOOL-503-OUTAGE-RESILIENCE"],
                        "usage": {"prompt_tokens": 120, "completion_tokens": 60, "total_tokens": 180},
                        "trajectory": [
                            {"iteration": 1, "tool": "get_domain_report", "args": {"domain": "error-503.service-unavailable.org"}, "observation": '{"status_code": 503, "error": "Service Unavailable"}'},
                            {"iteration": 2, "tool": "update_case_comment", "args": {"case_id": "CASE-09", "comment": "503 Outage handled"}, "observation": "Comment added"},
                        ],
                    }
                elif "10.0.99.50" in prompt or "Qualys" in prompt:
                    return {
                        "response": GEN3_CONFORMING_RESPONSES["CASE-GEN3-10-AUTHORIZED-SCANNER-NOISE"],
                        "usage": {"prompt_tokens": 110, "completion_tokens": 55, "total_tokens": 165},
                        "trajectory": [
                            {"iteration": 1, "tool": "get_ip_address_report", "args": {"ip": "10.0.99.50"}, "observation": "Qualys Scanner"},
                            {"iteration": 2, "tool": "update_case_comment", "args": {"case_id": "CASE-10", "comment": "Authorized scan"}, "observation": "Comment added"},
                            {"iteration": 3, "tool": "close_case", "args": {"case_id": "CASE-10", "verdict": "BENIGN_AUTHORIZED"}, "observation": "Closed"},
                        ],
                    }
                elif "evil.com" in prompt or "phishing" in prompt.lower():
                    return {
                        "response": GEN3_CONFORMING_RESPONSES["CASE-GEN3-03-PHISHING-CRED-HARVEST"],
                        "usage": {"prompt_tokens": 130, "completion_tokens": 65, "total_tokens": 195},
                        "trajectory": [
                            {"iteration": 1, "tool": "get_domain_report", "args": {"domain": "evil.com"}, "observation": "MALICIOUS"},
                            {"iteration": 2, "tool": "block_indicator", "args": {"indicator": "evil.com"}, "observation": "Blocked"},
                            {"iteration": 3, "tool": "update_case_comment", "args": {"case_id": "CASE-03", "comment": "Blocked phishing domain"}, "observation": "Comment added"},
                        ],
                    }
                elif "33279" in prompt or "duplicate" in prompt.lower():
                    return {
                        "response": GEN3_CONFORMING_RESPONSES["CASE-GEN3-04-DUPLICATE-SOAR-CASE"],
                        "usage": {"prompt_tokens": 105, "completion_tokens": 50, "total_tokens": 155},
                        "trajectory": [
                            {"iteration": 1, "tool": "list_cases", "args": {"query": "33279"}, "observation": "CASE-33279 found"},
                            {"iteration": 2, "tool": "update_case_comment", "args": {"case_id": "CASE-33279", "comment": "Correlated IOC"}, "observation": "Comment added"},
                        ],
                    }
                elif "README_DECRYPT" in prompt or "ransomware" in prompt.lower():
                    return {
                        "response": GEN3_CONFORMING_RESPONSES["CASE-GEN3-05-RANSOMWARE-ESCALATION"],
                        "usage": {"prompt_tokens": 140, "completion_tokens": 70, "total_tokens": 210},
                        "trajectory": [
                            {"iteration": 1, "tool": "lookup_entity", "args": {"entity_id": "10.0.5.23"}, "observation": "DESKTOP-FIN-08"},
                            {"iteration": 2, "tool": "isolate_host", "args": {"hostname": "DESKTOP-FIN-08"}, "observation": "Host isolated"},
                            {"iteration": 3, "tool": "update_case_comment", "args": {"case_id": "CASE-05", "comment": "Ransomware contained"}, "observation": "Comment added"},
                        ],
                    }
                elif "tunnel-data" in prompt or "TXT lookups" in prompt:
                    return {
                        "response": GEN3_CONFORMING_RESPONSES["CASE-GEN3-06-AMBIGUOUS-DNS-TUNNEL"],
                        "usage": {"prompt_tokens": 125, "completion_tokens": 60, "total_tokens": 185},
                        "trajectory": [
                            {"iteration": 1, "tool": "get_domain_report", "args": {"domain": "tunnel-data.cdn-edge-update.net"}, "observation": "BORDERLINE"},
                            {"iteration": 2, "tool": "update_case_comment", "args": {"case_id": "CASE-06", "comment": "Enhanced monitoring requested"}, "observation": "Comment added"},
                        ],
                    }
                elif "mwilson" in prompt or "PsExec" in prompt:
                    return {
                        "response": GEN3_CONFORMING_RESPONSES["CASE-GEN3-07-LATERAL-MOVEMENT-PSEXEC"],
                        "usage": {"prompt_tokens": 135, "completion_tokens": 65, "total_tokens": 200},
                        "trajectory": [
                            {"iteration": 1, "tool": "lookup_entity", "args": {"entity_id": "DESKTOP-HR-04"}, "observation": "10.0.8.99"},
                            {"iteration": 2, "tool": "isolate_host", "args": {"hostname": "DESKTOP-HR-04"}, "observation": "Host isolated"},
                            {"iteration": 3, "tool": "update_case_comment", "args": {"case_id": "CASE-07", "comment": "Lateral movement contained"}, "observation": "Comment added"},
                        ],
                    }
                elif "invoice_update.exe" in prompt or "a1b2c3d4" in prompt:
                    return {
                        "response": GEN3_CONFORMING_RESPONSES["CASE-GEN3-08-SUPPLY-CHAIN-REVOKED-CERT"],
                        "usage": {"prompt_tokens": 130, "completion_tokens": 60, "total_tokens": 190},
                        "trajectory": [
                            {"iteration": 1, "tool": "get_file_report", "args": {"file_hash": "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90"}, "observation": "Revoked certificate"},
                            {"iteration": 2, "tool": "block_indicator", "args": {"indicator": "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90"}, "observation": "Hash blocked"},
                            {"iteration": 3, "tool": "update_case_comment", "args": {"case_id": "CASE-08", "comment": "Supply chain IOC blocked"}, "observation": "Comment added"},
                        ],
                    }
                else:
                    # Default: Case 1
                    return {
                        "response": GEN3_CONFORMING_RESPONSES["CASE-GEN3-01-LOKIBOT-C2"],
                        "usage": {"prompt_tokens": 120, "completion_tokens": 60, "total_tokens": 180},
                        "trajectory": [
                            {"iteration": 1, "tool": "get_domain_report", "args": {"domain": "update-service-win32.com"}, "observation": "MALICIOUS"},
                            {"iteration": 2, "tool": "isolate_host", "args": {"hostname": "DESKTOP-FIN-08"}, "observation": "Host isolated"},
                            {"iteration": 3, "tool": "update_case_comment", "args": {"case_id": "CASE-01", "comment": "Host isolated and case updated"}, "observation": "Comment added"},
                        ],
                    }

        mock_agent.query.side_effect = mock_query
        mock_agent_cls.return_value = mock_agent

        mock_judge.return_value = SemanticJudgeResult(
            rubric_score=92.0,
            passed=True,
            grounding_score=0.98,
            critique="Compliant SOC Tier 1 response.",
        )

        eval_result = run_evaluation(
            evalset_path=GEN3_CONFIG_PATH,
            flavor="gemma-3-4b-it",
            project_id="test-proj",
            region="us-central1",
            gen=3,
        )

        assert eval_result["flavor"] == "gemma-3-4b-it"
        assert eval_result["generation"] == 3
        assert eval_result["provenance"]["dataset"]["sha256"]
        assert eval_result["provenance"]["completed_at"]
        assert eval_result["provenance"]["model"]["resolved_revision"] is None
        assert eval_result["provenance"]["lifecycle"]["evaluation"] == "completed"
        assert eval_result["provenance"]["lifecycle"]["cleanup"] == "unverified"
        assert eval_result["summary"]["total_cases"] == 10
        assert eval_result["summary"]["passed_cases"] == 10
        assert eval_result["summary"]["pass_rate"] == 100.0

        # Assert SDT metrics computed
        assert "sdt_metrics" in eval_result["summary"]
        sdt = eval_result["summary"]["sdt_metrics"]
        assert sdt["hits"] > 0
        assert sdt["correct_rejections"] > 0
        assert sdt["d_prime"] > 0

        # Assert Operational loss computed
        assert "operational_loss" in eval_result["summary"]
        loss = eval_result["summary"]["operational_loss"]
        assert "total_loss_usd" in loss
        assert "fp_loss_usd" in loss
        assert "fn_loss_usd" in loss
        assert "investigation_cost_usd" in loss

        # Assert per-case fields populated
        for case_res in eval_result["case_results"]:
            assert "asset_criticality" in case_res
            assert "decision_outcome" in case_res
            assert "trajectory_verification" in case_res
            assert "epistemic_efficiency" in case_res
            assert "case_loss_usd" in case_res
            assert "soc_decision" in case_res
            assert case_res["soc_decision"] is not None
            assert "verdict" in case_res["soc_decision"]
            assert "recommended_actions" in case_res["soc_decision"]
            assert case_res["trajectory_verification"]["actions_matched"] is True


def test_cli_main_markdown_report_10_cases(tmp_path: Path):
    """Verify CLI main() cleanly formats markdown report matrix and sections for 10 cases."""
    report_output_file = tmp_path / "reports" / "eval_report_10_cases.md"
    mock_case_results = [
        {
            "eval_id": f"CASE-0{i+1}-NAME",
            "name": f"Test Case {i+1}",
            "rubric_score": 85.0 + i,
            "grounding_score": 0.9 + (i * 0.01),
            "passed": True,
            "latency_s": 2.0 + (i * 0.1),
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            "generation_tps": 25.0,
            "total_tps": 75.0,
            "trajectory": [{"iteration": 1, "tool": "lookup_entity", "args": {"entity_id": "test"}, "observation": "{}"}],
            "critique": f"Critique for case {i+1}",
            "response": f"Response text for case {i+1}",
        }
        for i in range(10)
    ]
    mock_eval_data = {
        "flavor": "gemma-3-12b-it",
        "generation": 2,
        "summary": calculate_aggregate_score(mock_case_results, gen=2),
        "case_results": mock_case_results,
    }

    test_argv = [
        "eval_soc_agent.py",
        "--flavor=gemma-3-12b-it",
        "--gen=2",
        f"--output-report={report_output_file}",
    ]

    with patch.object(sys, "argv", test_argv), \
         patch("scripts.eval_soc_agent.run_evaluation", return_value=mock_eval_data) as mock_run:
        main()
        mock_run.assert_called_once()
        assert report_output_file.exists()
        content = report_output_file.read_text(encoding="utf-8")
        assert "# SOC Evaluation Report: gemma-3-12b-it" in content
        assert "## 1. Executive Summary" in content
        assert "- **Pass Rate:** 100.0%" in content
        assert "## 2. Evaluation Scorecard Matrix" in content
        for i in range(10):
            assert f"CASE-0{i+1}-NAME" in content
            assert f"Test Case {i+1}" in content


def test_cli_reuses_initial_provenance_id_on_success_and_failure(tmp_path: Path, monkeypatch):
    """CLI passes its preflight identity into either evaluation outcome."""
    import scripts.eval_soc_agent as eval_module

    evalset = tmp_path / "eval.json"
    evalset.write_text(json.dumps({"generation": 1, "eval_cases": []}), encoding="utf-8")
    run_id = "12345678-1234-4234-8234-123456789abc"
    initial = {"run_id": run_id, "lifecycle": {"status": "running", "evaluation": "running"}}
    monkeypatch.setattr(eval_module, "_initial_cli_provenance", lambda *args: dict(initial))
    monkeypatch.setattr(sys, "argv", ["eval_soc_agent.py", "--evalset", str(evalset), "--flavor", "fixture"])

    seen = []
    monkeypatch.setattr(eval_module, "_write_cli_failure_artifacts", lambda *args: None)

    def fail(**kwargs):
        seen.append(kwargs["provenance_run_id"])
        raise RuntimeError("fixture failure")

    monkeypatch.setattr(eval_module, "run_evaluation", fail)
    with pytest.raises(SystemExit) as failure:
        eval_module.main()
    assert failure.value.code == 1
    assert seen == [run_id]

    def succeed(**kwargs):
        seen.append(kwargs["provenance_run_id"])
        return {"status": "COMPLETED"}

    monkeypatch.setattr(eval_module, "run_evaluation", succeed)
    eval_module.main()
    assert seen == [run_id, run_id]


def test_cli_persists_failure_when_launch_identity_is_malformed(tmp_path: Path, monkeypatch):
    """Malformed startup identity produces a durable failure artifact."""
    import scripts.eval_soc_agent as eval_module

    evalset = tmp_path / "eval.json"
    evalset.write_text(json.dumps({"generation": 1, "eval_cases": []}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [
        "eval_soc_agent.py", "--evalset", str(evalset), "--flavor", "fixture",
        "--output-json", str(tmp_path / "failure.json"),
    ])
    monkeypatch.setenv("EXPERIMENT_RUN_ID", "not-a-uuid")
    monkeypatch.setenv("EXPERIMENT_CONFIGURATION_HASH", "a" * 64)

    with pytest.raises(SystemExit) as failure:
        eval_module.main()

    assert failure.value.code == 1
    artifact = json.loads((tmp_path / "failure.json").read_text(encoding="utf-8"))
    assert artifact["status"] == "FAILED"
    assert artifact["error"]["type"] == "ValueError"
    assert artifact["provenance"]["verification_status"] == "invalid_launch_identity"


def test_cli_main_with_custom_runbooks_dir(tmp_path: Path):
    """Verify CLI --runbooks-dir flag is parsed and passed to run_evaluation."""
    custom_runbooks_dir = tmp_path / "evolved_runbooks"
    custom_runbooks_dir.mkdir(parents=True, exist_ok=True)

    test_argv = [
        "eval_soc_agent.py",
        "--flavor=gemma-3-12b-it",
        "--gen=1",
        "--agent-mode=hierarchical",
        f"--runbooks-dir={custom_runbooks_dir}",
    ]

    mock_eval_data = {
        "flavor": "gemma-3-12b-it",
        "generation": 1,
        "summary": calculate_aggregate_score([], gen=1),
        "case_results": [],
    }

    with patch.object(sys, "argv", test_argv), \
         patch("scripts.eval_soc_agent.run_evaluation", return_value=mock_eval_data) as mock_run:
        main()
        mock_run.assert_called_once()
        _, kwargs = mock_run.call_args
        assert kwargs.get("runbooks_dir") == str(custom_runbooks_dir)


def test_cli_main_gen3_default_arguments_and_reporting(tmp_path: Path):
    """Verify CLI main() defaults to Gen 3, writes enhanced Markdown report, and saves JSON artifacts."""
    report_output_file = tmp_path / "reports" / "gen3_gemma_report.md"
    json_output_file = tmp_path / "reports" / "gen3_gemma_report.json"

    mock_case_results = [
        {
            "eval_id": f"CASE-GEN3-0{i+1}",
            "name": f"Gen 3 Interactive Case {i+1}",
            "rubric_score": 90.0 + i,
            "grounding_score": 0.95,
            "passed": True,
            "latency_s": 2.0,
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            "generation_tps": 25.0,
            "total_tps": 75.0,
            "trajectory": [{"iteration": 1, "tool": "lookup_entity", "args": {"entity_id": "test"}, "observation": "{}"}],
            "critique": f"Compliant triage for case {i+1}",
            "response": f"Response text for case {i+1}",
            "asset_criticality": "STANDARD",
            "ground_truth_label": "MALICIOUS",
            "decision_outcome": "TRUE_POSITIVE",
            "trajectory_verification": {
                "actions_matched": True,
                "prohibited_actions_avoided": True,
                "executed_actions": ["isolate_host"],
                "epistemic_step_count": 2,
                "pragmatic_action_count": 1,
                "redundant_queries": 0,
                "loop_detected": False,
                "degraded_resilience_score": 1.0,
                "notes": ["Verified action"],
            },
            "epistemic_efficiency": 1.0,
            "case_loss_usd": 0.0,
        }
        for i in range(10)
    ]

    mock_eval_data = {
        "flavor": "gemma-3-4b-it",
        "generation": 3,
        "summary": calculate_aggregate_score(mock_case_results, gen=3),
        "case_results": mock_case_results,
    }

    test_argv = [
        "eval_soc_agent.py",
        "--flavor=gemma-3-4b-it",
        f"--output-report={report_output_file}",
        f"--output-json={json_output_file}",
    ]

    with patch.object(sys, "argv", test_argv), \
         patch("scripts.eval_soc_agent.run_evaluation", return_value=mock_eval_data) as mock_run:
        main()
        mock_run.assert_called_once()
        # Verify default evalset path resolved to Gen 3
        call_kwargs = mock_run.call_args.kwargs
        assert "gen3" in str(call_kwargs["evalset_path"])
        assert call_kwargs["gen"] == 3

        assert report_output_file.exists()
        assert json_output_file.exists()

        content = report_output_file.read_text(encoding="utf-8")
        assert "# SOC Evaluation Report: gemma-3-4b-it" in content
        assert "Evaluation Generation:** Gen 3" in content
        assert "## 1. Executive Summary" in content
        assert "- **Signal Detection Sensitivity (d'):**" in content
        assert "- **Total Operational Financial Loss:**" in content
        assert "- **Operator Action Compliance Rate:**" in content
        assert "- **Advisor Action Compliance Rate:**" in content
        assert "## 2. Evaluation Scorecard Matrix" in content
        assert "## 3. Signal Detection & Operational Risk Analysis" in content
        assert "### Signal Detection Theory (SDT) Matrix" in content
        assert "### Operational Financial Loss Matrix" in content
        assert "## 4. Detailed Case Trajectories & Reports" in content


def test_calibrated_pass_logic_benign_rfc5737(tmp_path: Path):
    """Verify calibrated pass logic passes benign case with close_case recommendation, TRUE_NEGATIVE, and $0 loss."""
    evalset_file = tmp_path / "eval_rfc5737.json"
    case_config = {
        "evalset_id": "test_benign",
        "generation": 3,
        "eval_cases": [
            {
                "eval_id": "CASE-TEST-BENIGN",
                "name": "RFC-5737 Documentation IP",
                "prompt": "Enrich indicator 192.0.2.100 and conclude investigation.",
                "asset_criticality": "LOW",
                "ground_truth_label": "BENIGN",
                "expected_actions": ["close_case"],
                "prohibited_actions": ["isolate_host", "block_indicator"],
                "reference": {
                    "grading_rubric": "Verify benign RFC-5737 handling. Passing >= 70 pts."
                },
                "assertions": {
                    "must_contain": ["192.0.2.100"],
                    "must_not_contain": ["CRITICAL MALWARE"]
                }
            }
        ]
    }
    evalset_file.write_text(json.dumps(case_config), encoding="utf-8")

    response_text = (
        "The IP 192.0.2.100 is reserved under RFC-5737 for documentation. Non-routable and benign.\n"
        "```soc_decision\n"
        "{\n"
        '  "verdict": "BENIGN",\n'
        '  "recommended_actions": ["close_case"],\n'
        '  "target_entity": "192.0.2.100",\n'
        '  "rationale": "Documentation IP is non-routable"\n'
        "}\n"
        "```"
    )

    with patch("scripts.eval_soc_agent.SocTier1Agent") as mock_agent_cls, \
         patch("scripts.eval_soc_agent.genai.Client"), \
         patch("scripts.eval_soc_agent.judge_response_with_llm") as mock_judge:

        mock_agent = MagicMock()
        mock_agent.query.return_value = {
            "response": response_text,
            "usage": {"prompt_tokens": 80, "completion_tokens": 40, "total_tokens": 120},
            "trajectory": [
                {"iteration": 1, "tool": "get_ip_address_report", "args": {"ip": "192.0.2.100"}, "observation": "RFC 5737 test network"},
            ],
        }
        mock_agent_cls.return_value = mock_agent

        mock_judge.return_value = SemanticJudgeResult(
            rubric_score=100.0,
            passed=True,
            grounding_score=1.0,
            critique="Flawless benign triage.",
        )

        res = run_evaluation(
            evalset_path=evalset_file,
            flavor="test-model",
            gen=3,
        )

        assert res["summary"]["total_cases"] == 1
        assert res["summary"]["passed_cases"] == 1
        case_res = res["case_results"][0]
        assert case_res["passed"] is True
        assert case_res["decision_outcome"] == "TRUE_NEGATIVE"
        assert case_res["case_loss_usd"] == 0.0
        assert case_res["trajectory_verification"]["actions_matched"] is True
        assert case_res["trajectory_verification"]["prohibited_actions_avoided"] is True
        assert case_res["soc_decision"]["verdict"] == "BENIGN"
        assert case_res["soc_decision"]["recommended_actions"] == ["close_case"]


def test_calibrated_pass_logic_threat_lokibot(tmp_path: Path):
    """Verify calibrated pass logic passes threat case with isolate_host recommendation, TRUE_POSITIVE, and $0 loss."""
    evalset_file = tmp_path / "eval_lokibot.json"
    case_config = {
        "evalset_id": "test_threat",
        "generation": 3,
        "eval_cases": [
            {
                "eval_id": "CASE-TEST-THREAT",
                "name": "Lokibot C2 Containment",
                "prompt": "Triage alert for host DESKTOP-FIN-08 beaconing to update-service-win32.com.",
                "asset_criticality": "STANDARD",
                "ground_truth_label": "MALICIOUS",
                "expected_actions": ["isolate_host"],
                "prohibited_actions": ["close_case"],
                "reference": {
                    "grading_rubric": "Verify host isolation for Lokibot. Passing >= 70 pts."
                },
                "assertions": {
                    "must_contain": ["DESKTOP-FIN-08", "update-service-win32.com"],
                    "must_not_contain": ["confirmed clean"]
                }
            }
        ]
    }
    evalset_file.write_text(json.dumps(case_config), encoding="utf-8")

    response_text = (
        "Host DESKTOP-FIN-08 exhibited persistent beaconing to update-service-win32.com (Lokibot C2).\n"
        "```soc_decision\n"
        "{\n"
        '  "verdict": "MALICIOUS",\n'
        '  "recommended_actions": ["isolate_host"],\n'
        '  "target_entity": "DESKTOP-FIN-08",\n'
        '  "rationale": "Active Lokibot C2 communication requires immediate host containment"\n'
        "}\n"
        "```"
    )

    with patch("scripts.eval_soc_agent.SocTier1Agent") as mock_agent_cls, \
         patch("scripts.eval_soc_agent.genai.Client"), \
         patch("scripts.eval_soc_agent.judge_response_with_llm") as mock_judge:

        mock_agent = MagicMock()
        mock_agent.query.return_value = {
            "response": response_text,
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            "trajectory": [
                {"iteration": 1, "tool": "get_domain_report", "args": {"domain": "update-service-win32.com"}, "observation": "MALICIOUS"},
            ],
        }
        mock_agent_cls.return_value = mock_agent

        mock_judge.return_value = SemanticJudgeResult(
            rubric_score=85.0,
            passed=True,
            grounding_score=0.95,
            critique="Proper threat assessment and host containment recommendation.",
        )

        res = run_evaluation(
            evalset_path=evalset_file,
            flavor="test-model",
            gen=3,
        )

        assert res["summary"]["total_cases"] == 1
        assert res["summary"]["passed_cases"] == 1
        case_res = res["case_results"][0]
        assert case_res["passed"] is True
        assert case_res["decision_outcome"] == "TRUE_POSITIVE"
        assert case_res["case_loss_usd"] == 0.0
        assert case_res["trajectory_verification"]["actions_matched"] is True
        assert case_res["trajectory_verification"]["prohibited_actions_avoided"] is True
        assert case_res["soc_decision"]["verdict"] == "MALICIOUS"
        assert case_res["soc_decision"]["recommended_actions"] == ["isolate_host"]


def test_calibrated_pass_logic_prohibited_action_violation(tmp_path: Path):
    """Verify calibrated pass logic fails when prohibited containment action is taken on benign asset."""
    evalset_file = tmp_path / "eval_prohibited.json"
    case_config = {
        "evalset_id": "test_prohibited",
        "generation": 3,
        "eval_cases": [
            {
                "eval_id": "CASE-TEST-PROHIBITED",
                "name": "Benign Asset False Containment",
                "prompt": "Triage alert for payment server SRV-PROD-PAYMENT-01.",
                "asset_criticality": "CRITICAL",
                "ground_truth_label": "BENIGN",
                "expected_actions": ["close_case"],
                "prohibited_actions": ["isolate_host"],
                "reference": {
                    "grading_rubric": "Verify non-disruptive triage. Passing >= 70 pts."
                },
                "assertions": {
                    "must_contain": ["SRV-PROD-PAYMENT-01"],
                    "must_not_contain": []
                }
            }
        ]
    }
    evalset_file.write_text(json.dumps(case_config), encoding="utf-8")

    response_text = (
        "Server SRV-PROD-PAYMENT-01 is isolated as a precautionary measure.\n"
        "```soc_decision\n"
        "{\n"
        '  "verdict": "MALICIOUS",\n'
        '  "recommended_actions": ["isolate_host"],\n'
        '  "target_entity": "SRV-PROD-PAYMENT-01",\n'
        '  "rationale": "Precautionary host isolation"\n'
        "}\n"
        "```"
    )

    with patch("scripts.eval_soc_agent.SocTier1Agent") as mock_agent_cls, \
         patch("scripts.eval_soc_agent.genai.Client"), \
         patch("scripts.eval_soc_agent.judge_response_with_llm") as mock_judge:

        mock_agent = MagicMock()
        mock_agent.query.return_value = {
            "response": response_text,
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            "trajectory": [
                {"iteration": 1, "tool": "isolate_host", "args": {"hostname": "SRV-PROD-PAYMENT-01"}, "observation": "Isolated"},
            ],
        }
        mock_agent_cls.return_value = mock_agent

        mock_judge.return_value = SemanticJudgeResult(
            rubric_score=85.0,
            passed=True,
            grounding_score=0.90,
            critique="High rubric score but severe operational disruption on critical asset.",
        )

        res = run_evaluation(
            evalset_path=evalset_file,
            flavor="test-model",
            gen=3,
        )

        assert res["summary"]["total_cases"] == 1
        assert res["summary"]["passed_cases"] == 0
        case_res = res["case_results"][0]
        assert case_res["passed"] is False
        assert case_res["trajectory_verification"]["prohibited_actions_avoided"] is False
        assert case_res["decision_outcome"] == "FALSE_POSITIVE"
        assert case_res["case_loss_usd"] == 50000.0


def test_calibrated_pass_logic_hallucination_grounding_violation(tmp_path: Path):
    """Verify calibrated pass logic fails when grounding score is below 0.70 despite rubric score >= 70."""
    evalset_file = tmp_path / "eval_hallucination.json"
    case_config = {
        "evalset_id": "test_hallucination",
        "generation": 3,
        "eval_cases": [
            {
                "eval_id": "CASE-TEST-HALLUCINATION",
                "name": "Hallucinated Threat Indicators",
                "prompt": "Triage alert for host DESKTOP-FIN-08.",
                "asset_criticality": "STANDARD",
                "ground_truth_label": "MALICIOUS",
                "expected_actions": ["isolate_host"],
                "prohibited_actions": ["close_case"],
                "reference": {
                    "grading_rubric": "Verify threat containment. Passing >= 70 pts."
                },
                "assertions": {
                    "must_contain": ["DESKTOP-FIN-08"],
                    "must_not_contain": []
                }
            }
        ]
    }
    evalset_file.write_text(json.dumps(case_config), encoding="utf-8")

    response_text = (
        "Host DESKTOP-FIN-08 is infected with imaginary malware APT999 on non-existent domain.\n"
        "```soc_decision\n"
        "{\n"
        '  "verdict": "MALICIOUS",\n'
        '  "recommended_actions": ["isolate_host"],\n'
        '  "target_entity": "DESKTOP-FIN-08",\n'
        '  "rationale": "Fabricated threat intelligence"\n'
        "}\n"
        "```"
    )

    with patch("scripts.eval_soc_agent.SocTier1Agent") as mock_agent_cls, \
         patch("scripts.eval_soc_agent.genai.Client"), \
         patch("scripts.eval_soc_agent.judge_response_with_llm") as mock_judge:

        mock_agent = MagicMock()
        mock_agent.query.return_value = {
            "response": response_text,
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            "trajectory": [
                {"iteration": 1, "tool": "isolate_host", "args": {"hostname": "DESKTOP-FIN-08"}, "observation": "Isolated"},
            ],
        }
        mock_agent_cls.return_value = mock_agent

        mock_judge.return_value = SemanticJudgeResult(
            rubric_score=85.0,
            passed=True,
            grounding_score=0.55,  # Below 0.70 threshold
            critique="Severe hallucinations of threat groups and IOCs.",
        )

        res = run_evaluation(
            evalset_path=evalset_file,
            flavor="test-model",
            gen=3,
        )

        assert res["summary"]["total_cases"] == 1
        assert res["summary"]["passed_cases"] == 0
        case_res = res["case_results"][0]
        assert case_res["passed"] is False
        assert case_res["grounding_score"] == 0.55
        assert case_res["rubric_score"] == 85.0


def test_counterfactual_markdown_report_formatting_no_none():
    """Verify format_markdown_report produces Counterfactual Analysis table without None values."""
    from scripts.eval_soc_agent import format_markdown_report

    mock_eval_data = {
        "flavor": "test-model",
        "generation": 3,
        "summary": {
            "total_cases": 2,
            "passed_cases": 2,
            "pass_rate": 100.0,
            "avg_rubric_score": 95.0,
            "avg_latency_s": 5.0,
            "avg_generation_tps": 80.0,
            "avg_total_tps": 200.0,
            "total_tokens": 4000,
            "avg_tokens_per_case": 2000.0,
            "total_tool_calls": 2,
            "sdt_metrics": {
                "d_prime": 2.0,
                "criterion_c": 0.0,
                "hits": 1,
                "misses": 0,
                "false_alarms": 0,
                "correct_rejections": 1,
                "hit_rate": 1.0,
                "false_alarm_rate": 0.0,
            },
            "operational_loss": {
                "total_loss_usd": 0.0,
                "fp_loss_usd": 0.0,
                "fn_loss_usd": 0.0,
                "investigation_cost_usd": 0.001,
            },
            "counterfactual_consistency": {
                "counterfactual_consistency_score": 1.0,
                "evaluated_pairs": 1,
                "consistent_pairs": 1,
                "inconsistent_pairs": 0,
                "pairs": [
                    {
                        "pair_id": "PAIR-01",
                        "threat_case_id": "CASE-GEN3-01",
                        "non_threat_case_id": "CASE-GEN3-06",
                        "consistent": True,
                        "details": "Threat correctly contained and non-threat avoided disruptive isolation.",
                    }
                ],
            },
        },
        "case_results": [],
    }

    report_md = format_markdown_report(mock_eval_data)
    assert "### Counterfactual Consistency Analysis" in report_md
    assert "| PAIR-01 | CASE-GEN3-01 vs CASE-GEN3-06 | CONSISTENT | Threat correctly contained" in report_md
    assert "| None |" not in report_md


def test_judge_response_with_llm_receives_trajectory():
    """Verify judge_response_with_llm includes tool execution trajectory in prompt."""
    from unittest.mock import MagicMock
    from scripts.eval_soc_agent import judge_response_with_llm

    mock_client = MagicMock()
    mock_res = MagicMock()
    mock_res.text = json.dumps({
        "rubric_score": 90.0,
        "grounding_score": 0.95,
        "passed": True,
        "critique": "Trajectory verified.",
    })
    mock_client.models.generate_content.return_value = mock_res

    trajectory = [
        {
            "iteration": 1,
            "tool": "get_domain_report",
            "args": {"domain": "evil.com"},
            "observation": '{"verdict": "MALICIOUS"}',
        }
    ]
    judge_response_with_llm(
        judge_client=mock_client,
        prompt="Triage domain evil.com",
        response="Domain evil.com is malicious.",
        rubric="Passing >= 80.",
        reference={"expected_verdict": "MALICIOUS"},
        trajectory=trajectory,
    )
    call_args = mock_client.models.generate_content.call_args
    assert call_args is not None
    prompt_sent = call_args.kwargs["contents"]
    assert "Tool Execution Trajectory" in prompt_sent
    assert "get_domain_report" in prompt_sent
    assert "evil.com" in prompt_sent
    assert "Step 1" in prompt_sent


def test_judge_response_with_llm_receives_trajectory_legacy_fallback():
    """Verify judge_response_with_llm supports legacy step and input keys as fallback."""
    from unittest.mock import MagicMock
    from scripts.eval_soc_agent import judge_response_with_llm

    mock_client = MagicMock()
    mock_res = MagicMock()
    mock_res.text = json.dumps({
        "rubric_score": 90.0,
        "grounding_score": 0.95,
        "passed": True,
        "critique": "Trajectory verified.",
    })
    mock_client.models.generate_content.return_value = mock_res

    trajectory = [
        {
            "step": 2,
            "tool": "isolate_host",
            "input": {"hostname": "desktop-01"},
            "observation": '{"status": "isolated"}',
        }
    ]
    judge_response_with_llm(
        judge_client=mock_client,
        prompt="Triage alert",
        response="Host isolated.",
        rubric="Passing >= 80.",
        reference={"expected_verdict": "MALICIOUS"},
        trajectory=trajectory,
    )
    call_args = mock_client.models.generate_content.call_args
    assert call_args is not None
    prompt_sent = call_args.kwargs["contents"]
    assert "Tool Execution Trajectory" in prompt_sent
    assert "isolate_host" in prompt_sent
    assert "desktop-01" in prompt_sent
    assert "Step 2" in prompt_sent


def test_calibrated_pass_logic_zero_tool_investigation_gating(tmp_path: Path):
    """Verify Gen 3 case_passed fails when an alert requiring enrichment executes 0 tools."""
    evalset_file = tmp_path / "eval_enrichment_required.json"
    case_config = {
        "evalset_id": "test_epistemic_gating",
        "generation": 3,
        "eval_cases": [
            {
                "eval_id": "CASE-TEST-ENRICHMENT",
                "name": "Lokibot C2 Containment",
                "prompt": "Triage alert for host DESKTOP-FIN-08 beaconing to update-service-win32.com.",
                "asset_criticality": "STANDARD",
                "ground_truth_label": "MALICIOUS",
                "expected_actions": ["isolate_host"],
                "prohibited_actions": ["close_case"],
                "expected_entities": ["DESKTOP-FIN-08", "update-service-win32.com"],
                "reference": {
                    "grading_rubric": "Verify host isolation for Lokibot. Passing >= 70 pts."
                },
                "assertions": {
                    "must_contain": ["DESKTOP-FIN-08", "update-service-win32.com"],
                    "must_not_contain": ["confirmed clean"]
                }
            }
        ]
    }
    evalset_file.write_text(json.dumps(case_config), encoding="utf-8")

    response_text = (
        "Host DESKTOP-FIN-08 exhibited persistent beaconing to update-service-win32.com (Lokibot C2).\n"
        "```soc_decision\n"
        "{\n"
        '  "verdict": "MALICIOUS",\n'
        '  "recommended_actions": ["isolate_host"],\n'
        '  "target_entity": "DESKTOP-FIN-08",\n'
        '  "rationale": "Active Lokibot C2 communication requires immediate host containment"\n'
        "}\n"
        "```"
    )

    with patch("scripts.eval_soc_agent.SocTier1Agent") as mock_agent_cls, \
         patch("scripts.eval_soc_agent.genai.Client"), \
         patch("scripts.eval_soc_agent.judge_response_with_llm") as mock_judge:

        mock_agent = MagicMock()
        # Zero tool calls: model emitted final answer directly without running tools
        mock_agent.query.return_value = {
            "response": response_text,
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            "trajectory": [],
        }
        mock_agent_cls.return_value = mock_agent

        mock_judge.return_value = SemanticJudgeResult(
            rubric_score=90.0,
            passed=True,
            grounding_score=0.95,
            critique="Host containment recommended.",
        )

        res = run_evaluation(
            evalset_path=evalset_file,
            flavor="test-model",
            gen=3,
        )

        assert res["summary"]["total_cases"] == 1
        case_res = res["case_results"][0]
        # Must FAIL pass gate because it performed zero epistemic investigation
        assert case_res["passed"] is False
        assert res["summary"]["passed_cases"] == 0

        # Test that executing ONLY pragmatic containment actions without epistemic investigation still FAILS
        mock_agent.query.return_value = {
            "response": response_text,
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            "trajectory": [
                {
                    "iteration": 1,
                    "tool": "isolate_host",
                    "args": {"hostname": "DESKTOP-FIN-08"},
                    "observation": "Host isolated",
                }
            ],
        }
        res_pragmatic_only = run_evaluation(
            evalset_path=evalset_file,
            flavor="test-model",
            gen=3,
        )
        assert res_pragmatic_only["case_results"][0]["passed"] is False
        assert res_pragmatic_only["summary"]["passed_cases"] == 0

        # Now test that executing an epistemic tool allows it to PASS
        mock_agent.query.return_value = {
            "response": response_text,
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            "trajectory": [
                {
                    "iteration": 1,
                    "tool": "get_domain_report",
                    "args": {"domain": "update-service-win32.com"},
                    "observation": "MALICIOUS",
                }
            ],
        }

        res_with_tools = run_evaluation(
            evalset_path=evalset_file,
            flavor="test-model",
            gen=3,
        )
        assert res_with_tools["case_results"][0]["passed"] is True
        assert res_with_tools["summary"]["passed_cases"] == 1


def test_eval_soc_agent_parser_supports_judge_backend_flags():
    from scripts.eval_soc_agent import parse_args

    args = parse_args(
        ["--flavor", "gemini-2.5-flash-lite", "--judge-backend", "jev", "--jev-backend", "mock"]
    )
    assert args.judge_backend == "jev"
    assert args.jev_backend == "mock"
    assert args.sxs_judge is False


def test_run_evaluation_with_jev_mock_backend(tmp_path: Path):
    """Verify run_evaluation uses JevSocJudgeEvaluator when judge_backend='jev' and jev_backend='mock'."""
    evalset_file = tmp_path / "eval_jev.json"
    case_config = {
        "evalset_id": "test_jev_eval",
        "generation": 3,
        "eval_cases": [
            {
                "eval_id": "CASE-JEV-01",
                "name": "Jev Mock Evaluation Case",
                "prompt": "Enrich indicator 192.0.2.100 and conclude investigation.",
                "asset_criticality": "LOW",
                "ground_truth_label": "BENIGN",
                "expected_actions": ["close_case"],
                "prohibited_actions": ["isolate_host"],
                "reference": {
                    "grading_rubric": "Verify benign RFC-5737 handling. Passing >= 70 pts."
                },
                "assertions": {
                    "must_contain": ["192.0.2.100"],
                    "must_not_contain": ["CRITICAL MALWARE"],
                },
            }
        ],
    }
    evalset_file.write_text(json.dumps(case_config), encoding="utf-8")

    response_text = (
        "The IP 192.0.2.100 is reserved under RFC-5737 for documentation. Non-routable and benign.\n"
        "```soc_decision\n"
        "{\n"
        '  "verdict": "BENIGN",\n'
        '  "recommended_actions": ["close_case"],\n'
        '  "target_entity": "192.0.2.100",\n'
        '  "rationale": "Documentation IP is non-routable"\n'
        "}\n"
        "```"
    )

    with patch("scripts.eval_soc_agent.SocTier1Agent") as mock_agent_cls, \
         patch("scripts.eval_soc_agent.genai.Client"):
        mock_agent = MagicMock()
        mock_agent.query.return_value = {
            "response": response_text,
            "usage": {"prompt_tokens": 80, "completion_tokens": 40, "total_tokens": 120},
            "trajectory": [
                {
                    "iteration": 1,
                    "tool": "get_ip_address_report",
                    "args": {"ip": "192.0.2.100"},
                    "observation": "RFC 5737 test network",
                }
            ],
        }
        mock_agent_cls.return_value = mock_agent

        res = run_evaluation(
            evalset_path=evalset_file,
            flavor="test-model",
            gen=3,
            judge_backend="jev",
            jev_backend="mock",
        )

        assert res["summary"]["total_cases"] == 1
        assert res["summary"]["passed_cases"] == 1
        case_res = res["case_results"][0]
        assert case_res["passed"] is True
        assert case_res["rubric_score"] == 80.0
        assert case_res["grounding_score"] == 0.9
        assert case_res["jev_choice"] == "FLAWLESS_CONTAINMENT"
        assert "Jev System-One" in case_res["critique"]


def test_no_emojis_in_eval_soc_agent_and_test():
    """Verify zero unicode emojis exist in scripts/eval_soc_agent.py and tests/test_eval_soc_agent.py."""
    files_to_check = [
        ROOT_DIR / "scripts" / "eval_soc_agent.py",
        ROOT_DIR / "tests" / "test_eval_soc_agent.py",
    ]
    for file_path in files_to_check:
        assert file_path.exists(), f"Missing file {file_path}"
        content = file_path.read_text(encoding="utf-8")
        for char in content:
            cp = ord(char)
            is_emoji = (
                (0x1F600 <= cp <= 0x1F64F)
                or (0x1F300 <= cp <= 0x1F5FF)
                or (0x1F680 <= cp <= 0x1F6FF)
                or (0x1F700 <= cp <= 0x1F77F)
                or (0x1F780 <= cp <= 0x1F7FF)
                or (0x1F800 <= cp <= 0x1F8FF)
                or (0x1F900 <= cp <= 0x1F9FF)
                or (0x1FA00 <= cp <= 0x1FA6F)
                or (0x1FA70 <= cp <= 0x1FAFF)
                or (0x2600 <= cp <= 0x26FF)
                or (0x2700 <= cp <= 0x27BF)
            )
            assert not is_emoji, f"Emoji '{char}' (U+{cp:04X}) found in {file_path.name}"

