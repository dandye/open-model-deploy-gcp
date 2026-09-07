"""CLI failure persistence tests; no model or cloud calls are made."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.eval_soc_agent import main


def test_cli_persists_failed_run_without_success_metrics(tmp_path: Path):
    evalset = tmp_path / "evalset.json"
    evalset.write_text(json.dumps({"generation": 3, "eval_cases": []}), encoding="utf-8")
    output_json = tmp_path / "artifacts" / "failed.json"
    output_report = tmp_path / "reports" / "failed.md"

    argv = [
        "eval_soc_agent.py",
        "--evalset", str(evalset),
        "--flavor", "fixture-model",
        "--output-json", str(output_json),
        "--output-report", str(output_report),
    ]
    with patch.object(sys, "argv", argv), patch("scripts.eval_soc_agent.run_evaluation", side_effect=RuntimeError("judge unavailable")):
        with pytest.raises(SystemExit) as raised:
            main()

    assert raised.value.code == 1
    failure = json.loads(output_json.read_text(encoding="utf-8"))
    assert failure["status"] == "FAILED"
    assert failure["error"] == {"type": "RuntimeError", "message": "judge unavailable"}
    assert "summary" not in failure
    assert "case_results" not in failure
    assert failure["provenance"]["lifecycle"]["status"] == "failed"
    assert failure["provenance"]["completed_at"]
    assert failure["provenance"]["lifecycle"]["cleanup"] == "unverified"

    report = output_report.read_text(encoding="utf-8")
    assert "**Status:** FAILED" in report
    assert "judge unavailable" in report
    assert "No benchmark summary or case scores were produced" in report
    assert "Pass Rate" not in report


def test_cli_report_only_also_writes_derived_failure_json(tmp_path: Path):
    evalset = tmp_path / "evalset.json"
    evalset.write_text(json.dumps({"generation": 2, "eval_cases": []}), encoding="utf-8")
    output_report = tmp_path / "reports" / "failed.md"
    output_json = output_report.with_suffix(".json")

    argv = [
        "eval_soc_agent.py",
        "--evalset", str(evalset),
        "--output-report", str(output_report),
    ]
    with patch.object(sys, "argv", argv), patch("scripts.eval_soc_agent.run_evaluation", side_effect=ValueError("invalid evaluator response")):
        with pytest.raises(SystemExit) as raised:
            main()

    assert raised.value.code == 1
    assert output_json.exists()
    failure = json.loads(output_json.read_text(encoding="utf-8"))
    assert failure["status"] == "FAILED"
    assert failure["generation"] == 2
