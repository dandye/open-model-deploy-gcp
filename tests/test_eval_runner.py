"""Unit tests for the SOC Tier 1 agent evaluation runner and scoring logic."""

import json
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch
import pytest
from scripts.eval_soc_agent import (
    SemanticJudgeResult,
    calculate_aggregate_score,
    evaluate_assertions,
    judge_response_with_llm,
    main,
    run_evaluation,
)


def test_semantic_judge_result_model():
    res = SemanticJudgeResult(
        rubric_score=92.5,
        passed=True,
        grounding_score=0.95,
        critique="Identified Lokibot C2 and recommended isolation.",
    )
    assert res.rubric_score == 92.5
    assert res.passed is True
    assert res.grounding_score == 0.95
    assert "Lokibot" in res.critique


def test_evaluate_assertions_success():
    text = "Host DESKTOP-FIN-08 was compromised by update-service-win32.com. We must escalate to Tier 2."
    passed, failures = evaluate_assertions(
        response_text=text,
        must_contain=["DESKTOP-FIN-08", "update-service-win32.com", "escalat"],
        must_not_contain=["BENIGN"],
    )
    assert passed is True
    assert len(failures) == 0


def test_evaluate_assertions_missing_required():
    text = "Host DESKTOP-FIN-08 was compromised. We must escalate."
    passed, failures = evaluate_assertions(
        response_text=text,
        must_contain=["DESKTOP-FIN-08", "update-service-win32.com"],
        must_not_contain=["BENIGN"],
    )
    assert passed is False
    assert len(failures) == 1
    assert "update-service-win32.com" in failures[0]


def test_evaluate_assertions_contains_prohibited():
    text = "This alert for DESKTOP-FIN-08 is BENIGN and harmless."
    passed, failures = evaluate_assertions(
        response_text=text,
        must_contain=["DESKTOP-FIN-08"],
        must_not_contain=["BENIGN"],
    )
    assert passed is False
    assert len(failures) == 1
    assert "BENIGN" in failures[0]


def test_evaluate_assertions_empty_rules():
    text = "Sample response text without constraints."
    passed, failures = evaluate_assertions(
        response_text=text,
        must_contain=[],
        must_not_contain=[],
    )
    assert passed is True
    assert len(failures) == 0


def test_calculate_aggregate_score_empty():
    summary = calculate_aggregate_score([])
    assert summary["total_cases"] == 0
    assert summary["passed_cases"] == 0
    assert summary["pass_rate"] == 0.0
    assert summary["avg_rubric_score"] == 0.0
    assert summary["avg_latency_s"] == 0.0


def test_calculate_aggregate_score_mixed():
    results = [
        {"rubric_score": 90.0, "passed": True, "latency_s": 2.5},
        {"rubric_score": 70.0, "passed": False, "latency_s": 3.5},
        {"rubric_score": 85.0, "passed": True, "latency_s": 1.5},
    ]
    summary = calculate_aggregate_score(results)
    assert summary["total_cases"] == 3
    assert summary["passed_cases"] == 2
    assert summary["pass_rate"] == pytest.approx(66.666, rel=1e-2)
    assert summary["avg_rubric_score"] == pytest.approx(81.7, rel=1e-2)
    assert summary["avg_latency_s"] == pytest.approx(2.5, rel=1e-2)


def test_judge_response_with_llm():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "rubric_score": 88.0,
        "passed": True,
        "grounding_score": 0.90,
        "critique": "Solid analysis following standard triage runbooks.",
    })
    mock_client.models.generate_content.return_value = mock_response

    result = judge_response_with_llm(
        judge_client=mock_client,
        prompt="Triage alert for host DESKTOP-FIN-08",
        response="Host DESKTOP-FIN-08 shows Lokibot C2 activity. Escalate immediately.",
        rubric="100-point rubric",
        reference={"expected_verdict": "MALICIOUS"},
    )

    assert isinstance(result, SemanticJudgeResult)
    assert result.rubric_score == 88.0
    assert result.passed is True
    assert result.grounding_score == 0.90
    assert "Solid analysis" in result.critique
    mock_client.models.generate_content.assert_called_once()


def test_run_evaluation_mocked(tmp_path: Path):
    evalset_file = tmp_path / "test_evalset.json"
    evalset_data = {
        "evalset_id": "test_suite",
        "name": "Test Suite",
        "eval_cases": [
            {
                "eval_id": "CASE-TEST-01",
                "name": "Test Case 1",
                "prompt": "Investigate DESKTOP-FIN-08",
                "reference": {
                    "expected_verdict": "MALICIOUS",
                    "grading_rubric": "Score 100 for proper containment.",
                },
                "assertions": {
                    "must_contain": ["DESKTOP-FIN-08"],
                    "must_not_contain": ["BENIGN"],
                },
            }
        ],
    }
    evalset_file.write_text(json.dumps(evalset_data), encoding="utf-8")

    with patch("scripts.eval_soc_agent.SocTier1Agent") as mock_agent_cls, \
         patch("scripts.eval_soc_agent.genai.Client") as mock_genai_cls, \
         patch("scripts.eval_soc_agent.judge_response_with_llm") as mock_judge:

        mock_agent = MagicMock()
        mock_agent.query.return_value = {
            "response": "Host DESKTOP-FIN-08 is infected. Escalate.",
            "backend": "MockBackend",
        }
        mock_agent_cls.return_value = mock_agent

        mock_judge.return_value = SemanticJudgeResult(
            rubric_score=95.0,
            passed=True,
            grounding_score=1.0,
            critique="Perfect triage response.",
        )

        eval_result = run_evaluation(
            evalset_path=evalset_file,
            flavor="gemma-3-4b-it",
            project_id="test-proj",
            region="us-central1",
        )

        assert eval_result["flavor"] == "gemma-3-4b-it"
        assert eval_result["summary"]["total_cases"] == 1
        assert eval_result["summary"]["passed_cases"] == 1
        assert eval_result["summary"]["pass_rate"] == 100.0
        assert eval_result["summary"]["avg_rubric_score"] == 95.0
        assert len(eval_result["case_results"]) == 1
        assert eval_result["case_results"][0]["eval_id"] == "CASE-TEST-01"
        assert eval_result["case_results"][0]["passed"] is True


def test_cli_main_markdown_report_generation(tmp_path: Path):
    report_output_file = tmp_path / "reports" / "eval_report.md"
    mock_eval_data = {
        "flavor": "gemma-3-4b-it",
        "summary": {
            "total_cases": 1,
            "passed_cases": 1,
            "pass_rate": 100.0,
            "avg_rubric_score": 95.0,
            "avg_latency_s": 2.15,
        },
        "case_results": [
            {
                "eval_id": "CASE-01-LOKIBOT-C2",
                "name": "Lokibot C2 Triage",
                "rubric_score": 95.0,
                "grounding_score": 1.0,
                "passed": True,
                "latency_s": 2.15,
            }
        ],
    }

    test_argv = [
        "eval_soc_agent.py",
        "--flavor=gemma-3-4b-it",
        f"--output-report={report_output_file}",
    ]

    with patch.object(sys, "argv", test_argv), \
         patch("scripts.eval_soc_agent.run_evaluation", return_value=mock_eval_data) as mock_run:
        main()
        mock_run.assert_called_once()
        assert report_output_file.exists()
        content = report_output_file.read_text(encoding="utf-8")
        assert "# SOC Evaluation Report: gemma-3-4b-it" in content
        assert "- **Pass Rate:** 100.0%" in content
        assert "CASE-01-LOKIBOT-C2" in content
        assert "PASS" in content


def test_no_emojis_in_eval_runner_file():
    eval_script_path = Path(__file__).resolve().parent.parent / "scripts" / "eval_soc_agent.py"
    content = eval_script_path.read_text(encoding="utf-8")
    for char in content:
        code_point = ord(char)
        is_emoji = (
            (0x1F600 <= code_point <= 0x1F64F)
            or (0x1F300 <= code_point <= 0x1F5FF)
            or (0x1F680 <= code_point <= 0x1F6FF)
            or (0x2600 <= code_point <= 0x26FF)
            or (0x2700 <= code_point <= 0x27BF)
            or (0x1F900 <= code_point <= 0x1F9FF)
            or (0x1FA70 <= code_point <= 0x1FAFF)
        )
        assert not is_emoji, f"Found emoji '{char}' (code {code_point:#x}) in scripts/eval_soc_agent.py"
