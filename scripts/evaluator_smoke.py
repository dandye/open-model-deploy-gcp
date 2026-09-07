"""Offline compatibility smoke test for the evaluator entrypoint."""

import argparse
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import contextlib
import io
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _blocked(*args, **kwargs):
    raise RuntimeError("network disabled by offline evaluator smoke")


def _report(status, checks, error_type=None):
    result = {"schema_version": 1, "status": status, "synthetic": True,
              "scope": "offline_evaluator_compatibility", "checks": checks,
              "python_version": sys.version.split()[0]}
    if error_type:
        result["error_type"] = error_type
    return result


def _execute_smoke() -> dict:
    import json as json_module
    import tempfile as tempfile_module
    with tempfile_module.TemporaryDirectory() as temp:
        temp_path = Path(temp)
        dataset = temp_path / "synthetic.json"
        dataset.write_text(json_module.dumps({
            "generation": 1, "eval_cases": [{
                "eval_id": "SMOKE-001", "name": "Synthetic benign", "prompt": "Check benign test alert",
                "ground_truth_label": "BENIGN", "expected_actions": [], "prohibited_actions": [],
                "reference": {"grading_rubric": "Return a grounded benign triage."},
                "assertions": {"must_contain": ["BENIGN"], "must_not_contain": []},
            }],
        }))
        report = temp_path / "report.md"
        result_json = temp_path / "result.json"
        response = "[Analysis & Verdict]\nBENIGN\n```soc_decision\n{\"verdict\": \"BENIGN\", \"recommended_actions\": []}\n```"

        class ProbeAgent:
            def __init__(self, **kwargs): pass
            def set_up(self): pass
            def query(self, prompt, **kwargs):
                return {"response": response, "trajectory": [],
                        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                        "backend": "synthetic"}

        with patch.dict(os.environ, {}, clear=False), \
             patch("socket.socket.connect", _blocked), patch("socket.create_connection", _blocked), \
             patch("socket.socket.connect_ex", _blocked), \
             patch("socket.getaddrinfo", _blocked):
            for name in list(os.environ):
                if name.startswith(("EXPERIMENT_", "GOOGLE_", "GCP_", "CHRONICLE_", "HF_", "HUGGING_FACE_")):
                    os.environ.pop(name)
            import scripts.eval_soc_agent as evaluator
            judge = evaluator.SemanticJudgeResult(rubric_score=90, passed=True,
                                                   grounding_score=1, critique="synthetic")
            with patch.object(evaluator, "SocTier1Agent", ProbeAgent), \
                 patch.object(evaluator.genai, "Client", return_value=object()), \
                 patch.object(evaluator, "judge_response_with_llm", return_value=judge), \
                 patch.object(sys, "argv", ["eval_soc_agent.py", "--gen", "1", "--evalset", str(dataset), "--flavor", "synthetic",
                                             "--output-report", str(report), "--output-json", str(result_json)]):
                try:
                    with contextlib.redirect_stdout(io.StringIO()):
                        evaluator.main()
                except SystemExit as exc:
                    if exc.code not in (None, 0):
                        raise RuntimeError(f"evaluator exited {exc.code}")
        payload = json_module.loads(result_json.read_text())
        if payload.get("status") != "COMPLETED" or payload.get("summary", {}).get("total_cases") != 1:
            raise ValueError("unexpected evaluator result schema")
        if not payload.get("case_results", [{}])[0].get("passed") or not report.exists():
            raise ValueError("synthetic evaluator case did not pass")
        provenance = payload.get("provenance", {})
        if (not provenance.get("dataset", {}).get("sha256") or provenance.get("launch_configuration_hash") is not None
                or provenance.get("source_bundle") is not None or provenance.get("serving_runtime") is not None):
            raise ValueError("smoke provenance is missing or claims a deployment identity")
        return _report("PASS", {"evaluator_completed": True, "total_cases": 1,
                                "case_passed": True, "json_output": True, "markdown_output": True,
                                "provenance_without_launch_claim": True})


def run_smoke(output: Path) -> dict:
    from scripts.experiment_run import write_json
    write_json(output, _report("FAIL", {}, "IncompleteSmoke"))
    try:
        result = _execute_smoke()
    except Exception as exc:
        result = _report("FAIL", {"evaluator_completed": False}, type(exc).__name__)
    write_json(output, result)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = run_smoke(args.output)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
