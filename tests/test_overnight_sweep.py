"""Unit tests for the master overnight model evaluation and benchmark sweep."""

import json
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.run_overnight_sweep import ModelTarget, SweepOrchestrator


def test_model_target_initialization():
    """Verify ModelTarget field initialization and defaults."""
    target = ModelTarget(
        flavor="gemma-4-e2b-it",
        target_type="vertex",
        region="us-east1",
        machine_type="g2-standard-4",
        gpu_count=1,
        gpu_type="nvidia-l4",
        extra_vllm_flags="--max-num-seqs=16",
        max_model_len=8192,
        notes="Gemma 4 Edge (1x L4)",
    )
    assert target.flavor == "gemma-4-e2b-it"
    assert target.target_type == "vertex"
    assert target.region == "us-east1"
    assert target.machine_type == "g2-standard-4"
    assert target.gpu_count == 1
    assert target.gpu_type == "nvidia-l4"
    assert target.extra_vllm_flags == "--max-num-seqs=16"
    assert target.max_model_len == 8192
    assert target.notes == "Gemma 4 Edge (1x L4)"
    assert target.get_base_flavor() == "gemma-4-e2b-it"


def test_model_target_base_flavor_resolution():
    """Verify base flavor stripping for optimization variants."""
    target_fp8 = ModelTarget(
        flavor="gemma-3-27b-it-fp8",
        target_type="vertex",
        region="us-east1",
        extra_vllm_flags="--quantization=fp8",
    )
    assert target_fp8.get_base_flavor() == "gemma-3-27b-it"

    target_spec = ModelTarget(
        flavor="gemma-3-27b-it-speculative",
        target_type="vertex",
        region="us-east1",
        extra_vllm_flags="--quantization=fp8 --speculative-model=[ngram]",
    )
    assert target_spec.get_base_flavor() == "gemma-3-27b-it"


def test_build_model_queue_contains_all_models():
    """Verify build_queue returns the comprehensive sequence of 16 targets."""
    orchestrator = SweepOrchestrator(dry_run=True)
    queue = orchestrator.build_queue()
    flavors = [t.flavor for t in queue]

    # Managed Baselines
    assert "gemini-3.5-flash-lite" in flavors
    assert "gemini-2.5-flash" in flavors
    assert "gemini-2.5-pro" in flavors
    assert "gemini-3.7-flash" in flavors

    # Gemma 4
    assert "gemma-4-e2b-it" in flavors
    assert "gemma-4-e4b-it" in flavors
    assert "gemma-4-31b-it" in flavors

    # Gemma 3
    assert "gemma-3-1b-it" in flavors
    assert "gemma-3-4b-it" in flavors
    assert "gemma-3-12b-it" in flavors
    assert "gemma-3-27b-it" in flavors
    assert "gemma-3-27b-it-fp8" in flavors
    assert "gemma-3-27b-it-speculative" in flavors

    # Gemma 2
    assert "gemma-2-2b-it" in flavors
    assert "gemma-2-9b-it" in flavors
    assert "gemma-2-27b-it" in flavors

    assert len(queue) == 16


def test_dry_run_single_model_evaluation():
    """Verify single model evaluation in dry_run mode."""
    orchestrator = SweepOrchestrator(dry_run=True)
    target = ModelTarget(flavor="gemini-3.5-flash-lite", target_type="managed", region="global")
    result = orchestrator.evaluate_model(target)

    assert result["flavor"] == "gemini-3.5-flash-lite"
    assert result["success"] is True
    assert "soc_eval" in result
    assert "summary" in result["soc_eval"]
    assert result["soc_eval"]["summary"]["total_cases"] == 5
    assert "benchmark" in result


def test_guaranteed_cleanup_on_benchmark_exception():
    """Verify cleanup_endpoint is invoked even if benchmark raises an exception."""
    orchestrator = SweepOrchestrator(dry_run=False)
    target = ModelTarget(flavor="gemma-4-e2b-it", target_type="vertex", region="us-east1")

    with patch.object(orchestrator, "deploy_vertex_model", return_value="endpoint-test-12345"), \
         patch.object(orchestrator, "benchmark_model", side_effect=RuntimeError("Benchmark connection failed")), \
         patch.object(orchestrator, "cleanup_endpoint") as mock_clean:

        with pytest.raises(RuntimeError, match="Benchmark connection failed"):
            orchestrator.evaluate_model(target)

        mock_clean.assert_called_once_with(target, "endpoint-test-12345")


def test_guaranteed_cleanup_on_eval_exception():
    """Verify cleanup_endpoint is invoked even if SOC evaluation raises an exception."""
    orchestrator = SweepOrchestrator(dry_run=False)
    target = ModelTarget(flavor="gemma-4-e2b-it", target_type="vertex", region="us-east1")

    with patch.object(orchestrator, "deploy_vertex_model", return_value="endpoint-test-99999"), \
         patch.object(orchestrator, "benchmark_model", return_value={"avg_latency_s": 1.2}), \
         patch.object(orchestrator, "eval_soc_agent", side_effect=ValueError("Eval scoring failure")), \
         patch.object(orchestrator, "cleanup_endpoint") as mock_clean:

        with pytest.raises(ValueError, match="Eval scoring failure"):
            orchestrator.evaluate_model(target)

        mock_clean.assert_called_once_with(target, "endpoint-test-99999")


def test_run_sweep_continues_on_model_failure():
    """Verify run_sweep processes all models despite failures in earlier models."""
    orchestrator = SweepOrchestrator(dry_run=False)
    targets = [
        ModelTarget(flavor="gemini-3.5-flash-lite", target_type="managed", region="global"),
        ModelTarget(flavor="failing-model", target_type="vertex", region="us-central1"),
        ModelTarget(flavor="gemini-2.5-flash", target_type="managed", region="us-central1"),
    ]

    def mock_eval_side_effect(target):
        if target.flavor == "failing-model":
            raise RuntimeError("Model deploy failed")
        return {
            "flavor": target.flavor,
            "success": True,
            "target": target,
            "soc_eval": {
                "flavor": target.flavor,
                "summary": {
                    "pass_rate": 100.0,
                    "avg_rubric_score": 95.0,
                    "avg_latency_s": 10.0,
                    "avg_generation_tps": 65.0,
                    "avg_total_tps": 220.0,
                    "total_tool_calls": 5,
                    "total_tokens": 12000,
                    "total_cases": 5,
                    "passed_cases": 5,
                },
                "case_results": [],
            },
            "benchmark": {"avg_latency_s": 1.5, "tps": 70.0, "ttft_ms": 120.0},
        }

    with patch.object(orchestrator, "build_queue", return_value=targets), \
         patch.object(orchestrator, "evaluate_model", side_effect=mock_eval_side_effect), \
         patch.object(orchestrator, "update_master_scorecard") as mock_update_scorecard:

        results = orchestrator.run_sweep()
        assert len(results) == 3
        assert results[0]["success"] is True
        assert results[0]["flavor"] == "gemini-3.5-flash-lite"
        assert results[1]["success"] is False
        assert "Model deploy failed" in results[1]["error"]
        assert results[2]["success"] is True
        assert results[2]["flavor"] == "gemini-2.5-flash"
        mock_update_scorecard.assert_called()


def test_model_filtering(tmp_path: Path):
    """Verify run_sweep filters models when model_filter is specified."""
    doc_path = tmp_path / "test_scorecard.md"
    orchestrator = SweepOrchestrator(dry_run=True, scorecard_path=doc_path)
    results = orchestrator.run_sweep(model_filter=["gemini-2.5-flash", "gemini-3.5-flash-lite"])
    assert len(results) == 2
    flavors = [r["flavor"] for r in results]
    assert "gemini-2.5-flash" in flavors
    assert "gemini-3.5-flash-lite" in flavors


def test_deploy_vertex_model_command_execution():
    """Verify deploy_vertex_model invokes vertex_deploy.sh with correct arguments."""
    orchestrator = SweepOrchestrator(dry_run=False, project_id="test-project")
    target = ModelTarget(
        flavor="gemma-4-e2b-it",
        target_type="vertex",
        region="us-east1",
        extra_vllm_flags="--max-num-seqs=16",
    )

    mock_process = MagicMock()
    mock_process.stdout = "Deployment completed.\nEndpoint ID: 1234567890123456789\n"
    mock_process.returncode = 0

    with patch("subprocess.run", return_value=mock_process) as mock_sub:
        endpoint_id = orchestrator.deploy_vertex_model(target)
        assert endpoint_id == "1234567890123456789"
        mock_sub.assert_called_once()
        args, kwargs = mock_sub.call_args
        cmd = args[0]
        assert "vertex_deploy.sh" in cmd[0]
        assert cmd[1] == "gemma-4-e2b-it"
        assert cmd[2] == "us-east1"
        assert kwargs["env"]["EXTRA_VLLM_FLAGS"] == "--max-num-seqs=16"


def test_cleanup_endpoint_command_execution():
    """Verify cleanup_endpoint invokes gcloud undeploy and delete."""
    orchestrator = SweepOrchestrator(dry_run=False, project_id="test-project")
    target = ModelTarget(flavor="gemma-4-e2b-it", target_type="vertex", region="us-east1")

    mock_describe = MagicMock()
    mock_describe.stdout = "deployed-model-987\n"
    mock_describe.returncode = 0

    mock_action = MagicMock()
    mock_action.stdout = "Success\n"
    mock_action.returncode = 0

    with patch("subprocess.run", side_effect=[mock_describe, mock_action, mock_action]) as mock_sub:
        success = orchestrator.cleanup_endpoint(target, "endpoint-123")
        assert success is True
        assert mock_sub.call_count == 3


def test_update_master_scorecard(tmp_path: Path):
    """Verify master scorecard markdown compilation."""
    doc_path = tmp_path / "soc_model_comparative_evals.md"
    orchestrator = SweepOrchestrator(dry_run=True, scorecard_path=doc_path)

    sample_results = [
        {
            "flavor": "gemini-3.5-flash-lite",
            "success": True,
            "target": ModelTarget(flavor="gemini-3.5-flash-lite", target_type="managed", region="global", notes="Managed Global"),
            "soc_eval": {
                "flavor": "gemini-3.5-flash-lite",
                "summary": {
                    "pass_rate": 100.0,
                    "avg_rubric_score": 97.0,
                    "avg_latency_s": 11.36,
                    "avg_generation_tps": 70.22,
                    "avg_total_tps": 241.65,
                    "total_tool_calls": 5,
                    "total_tokens": 13723,
                    "total_cases": 5,
                    "passed_cases": 5,
                },
                "case_results": [
                    {"eval_id": "CASE-01", "name": "Lokibot", "rubric_score": 90.0, "passed": True, "trajectory": [{}]},
                    {"eval_id": "CASE-02", "name": "RFC-5737", "rubric_score": 100.0, "passed": True, "trajectory": [{}]},
                    {"eval_id": "CASE-03", "name": "Phishing", "rubric_score": 100.0, "passed": True, "trajectory": [{}]},
                    {"eval_id": "CASE-04", "name": "Duplicate", "rubric_score": 100.0, "passed": True, "trajectory": [{}]},
                    {"eval_id": "CASE-05", "name": "Ransomware", "rubric_score": 95.0, "passed": True, "trajectory": [{}]},
                ],
            },
            "benchmark": {"avg_latency_s": 1.2, "tps": 70.0, "ttft_ms": 95.0},
        }
    ]

    content = orchestrator.update_master_scorecard(sample_results)
    assert doc_path.exists()
    assert "SOC Tier 1 Agent Multi-Model Comparative Evaluation" in content
    assert "gemini-3.5-flash-lite" in content
    assert "100.0%" in content
    assert "97.0 / 100" in content
    assert "CASE-01" in content


def test_no_emojis_in_overnight_sweep_files():
    """Verify zero emojis in sweep script and test file."""
    for filename in ["scripts/run_overnight_sweep.py", "tests/test_overnight_sweep.py"]:
        path = ROOT_DIR / filename
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
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
            assert not is_emoji, f"Found emoji '{char}' (code {code_point:#x}) in {filename}"
