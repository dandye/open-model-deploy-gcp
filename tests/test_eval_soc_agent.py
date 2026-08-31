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
    summary = calculate_aggregate_score(results)

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


def test_run_evaluation_10_cases_mocked():
    """Verify run_evaluation executes all 10 cases and compiles summary output."""
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
        )

        assert eval_result["flavor"] == "gemma-3-4b-it"
        assert eval_result["summary"]["total_cases"] == 10
        assert len(eval_result["case_results"]) == 10
        assert eval_result["summary"]["total_prompt_tokens"] == 1200
        assert eval_result["summary"]["total_completion_tokens"] == 600
        assert eval_result["summary"]["total_tokens"] == 1800
        assert eval_result["summary"]["total_tool_calls"] == 10


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
        "summary": calculate_aggregate_score(mock_case_results),
        "case_results": mock_case_results,
    }

    test_argv = [
        "eval_soc_agent.py",
        "--flavor=gemma-3-12b-it",
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
        assert "## 3. Detailed Case Trajectories & Reports" in content


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
