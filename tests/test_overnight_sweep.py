"""Unit tests for the master overnight model evaluation and benchmark sweep."""

import json
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.overnight_model_sweep import (
    NEW_MODELS_QUEUE,
    deploy_and_eval_dedicated_model,
    evaluate_maas_model,
)
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

    for ds_flavor in [
        "deepseek-v4.1-flash-1017",
        "deepseek-v4.1-flash-1017-maas",
        "deepseek-v4.1-flash-maas",
    ]:
        ds_target = ModelTarget(flavor=ds_flavor, target_type="managed", region="global")
        assert ds_target.get_base_flavor() == ds_flavor


def test_build_model_queue_contains_all_models():
    """Verify build_queue returns the comprehensive sequence of all dense models and optimization variants."""
    orchestrator = SweepOrchestrator(dry_run=True)
    queue = orchestrator.build_queue()
    flavors = [t.flavor for t in queue]

    # Managed & Partner Baselines
    assert "gemini-2.5-flash-lite" in flavors
    assert "gemini-2.5-flash" in flavors
    assert "gemini-2.5-pro" in flavors
    assert "gemini-3.1-flash-lite" in flavors
    assert "gemini-3.5-flash-lite" in flavors
    assert "gemini-3.7-flash" in flavors
    assert "gemma-4-26b-a4b-it-maas" in flavors
    assert "muse-spark-1.3" in flavors

    # Gemma 4 (Dense + Speculative + Two-Model Draft)
    assert "gemma-4-e2b-it" in flavors
    assert "gemma-4-e2b-it-speculative" in flavors
    assert "gemma-4-e4b-it" in flavors
    assert "gemma-4-e4b-it-speculative" in flavors
    assert "gemma-4-31b-it" in flavors
    assert "gemma-4-31b-it-speculative" in flavors
    assert "gemma-4-31b-it-draft-e2b" in flavors
    assert "gemma-4-31b-it-draft-e4b" in flavors

    # Gemma 3 (Dense + FP8 + Speculative + Caching + Two-Model Draft)
    assert "gemma-3-1b-it" in flavors
    assert "gemma-3-1b-it-speculative" in flavors
    assert "gemma-3-4b-it" in flavors
    assert "gemma-3-4b-it-speculative" in flavors
    assert "gemma-3-12b-it" in flavors
    assert "gemma-3-12b-it-fp8" in flavors
    assert "gemma-3-12b-it-speculative" in flavors
    assert "gemma-3-12b-it-draft-1b" in flavors
    assert "gemma-3-27b-it" in flavors
    assert "gemma-3-27b-it-fp8" in flavors
    assert "gemma-3-27b-it-speculative" in flavors
    assert "gemma-3-27b-it-caching" in flavors
    assert "gemma-3-27b-it-draft-1b" in flavors
    assert "gemma-3-27b-it-draft-4b" in flavors

    # Gemma 2 (Dense + FP8 + Speculative)
    assert "gemma-2-2b-it" in flavors
    assert "gemma-2-2b-it-speculative" in flavors
    assert "gemma-2-9b-it" in flavors
    assert "gemma-2-9b-it-fp8" in flavors
    assert "gemma-2-9b-it-speculative" in flavors
    assert "gemma-2-27b-it" in flavors
    assert "gemma-2-27b-it-fp8" in flavors
    assert "gemma-2-27b-it-speculative" in flavors

    # NVIDIA Nemotron 3.5 Super VL
    assert "nemotron-3.5-super-vl-nvfp4" in flavors
    assert "nemotron-3.5-super-vl-bf16" in flavors

    # DeepSeek V4.1 Flash (OpenMaaS & Curated Self-Hosted)
    assert "deepseek-v4.1-flash-1017-maas" in flavors
    assert "deepseek-v4.1-flash-maas" in flavors
    assert "deepseek-v4.1-flash-1017" in flavors

    target_by_flavor = {t.flavor: t for t in queue}
    assert target_by_flavor["deepseek-v4.1-flash-1017-maas"].target_type == "managed"
    assert target_by_flavor["deepseek-v4.1-flash-1017-maas"].region == "global"
    assert target_by_flavor["deepseek-v4.1-flash-maas"].target_type == "managed"
    assert target_by_flavor["deepseek-v4.1-flash-maas"].region == "global"

    ds_vertex = target_by_flavor["deepseek-v4.1-flash-1017"]
    assert ds_vertex.target_type == "vertex"
    assert ds_vertex.region == "us-central1"
    assert ds_vertex.machine_type == "a3-megagpu-8g"
    assert ds_vertex.gpu_count == 8
    assert ds_vertex.gpu_type == "NVIDIA_H100_MEGA_80GB"
    assert ds_vertex.max_model_len == 1048576

    assert len(queue) == 43


def test_partner_sweep_queue_maas_routing_and_publisher_timeout():
    """Verify overnight_model_sweep routes DeepSeek MaaS to global and passes 7200s deploy timeout."""
    assert "deepseek-v4.1-flash-1017-maas" in NEW_MODELS_QUEUE
    assert "deepseek-v4.1-flash-maas" in NEW_MODELS_QUEUE
    assert "deepseek-v4.1-flash-1017" in NEW_MODELS_QUEUE

    maas_spec = {
        "type": "maas",
        "maasModelId": "deepseek-ai/deepseek-v4.1-flash-1017-maas",
        "modelId": "deepseek-ai/deepseek-v4.1-flash-1017-maas",
        "region": "global",
        "supportedTargets": ["vertex_maas"],
    }
    mock_ok = MagicMock(returncode=0)
    with patch("scripts.overnight_model_sweep.run_cmd", return_value=mock_ok) as mock_cmd:
        ok = evaluate_maas_model(
            "deepseek-v4.1-flash-1017-maas",
            project_id="secops-demo-env",
            region="us-central1",
            dry_run=False,
            spec=maas_spec,
        )
        assert ok is True
        called_cmd = mock_cmd.call_args[0][0]
        assert "--managed-model" in called_cmd
        assert called_cmd[called_cmd.index("--managed-model") + 1] == "deepseek-ai/deepseek-v4.1-flash-1017-maas"
        assert called_cmd[called_cmd.index("--region") + 1] == "global"

    # Even if deploy_and_eval_dedicated_model is called on a MaaS entry, it must redirect without GPU deploy
    with patch("scripts.overnight_model_sweep.evaluate_maas_model", return_value=True) as mock_eval_maas:
        assert deploy_and_eval_dedicated_model(
            "deepseek-v4.1-flash-1017-maas",
            maas_spec,
            project_id="secops-demo-env",
            region="us-central1",
            dry_run=False,
        ) is True
        mock_eval_maas.assert_called_once()

    # Publisher open_model passes 7200s timeout and 40960 MB shared memory without custom image URI override
    dedicated_spec = {
        "type": "open_model",
        "openModelId": "publishers/deepseek-ai/models/deepseek-v4.1@deepseek-v4.1-flash-1017",
        "compute": {
            "machineType": "a3-megagpu-8g",
            "acceleratorType": "NVIDIA_H100_MEGA_80GB",
            "acceleratorCount": 8,
        },
        "runtime": {
            "deploymentTimeoutSeconds": 7200,
            "sharedMemorySizeMb": 40960,
        },
    }
    fake_endpoint = MagicMock()
    fake_endpoint.resource_name = "projects/secops-demo-env/locations/us-central1/endpoints/987654321"
    fake_open_model = MagicMock()
    fake_open_model.deploy.return_value = fake_endpoint
    fake_mg = MagicMock()
    fake_mg.OpenModel.return_value = fake_open_model
    fake_vertexai = MagicMock()
    fake_vertexai.model_garden = fake_mg

    with patch.dict(sys.modules, {"vertexai": fake_vertexai, "vertexai.model_garden": fake_mg}), \
         patch("scripts.overnight_model_sweep.run_cmd", return_value=mock_ok):
        assert deploy_and_eval_dedicated_model(
            "deepseek-v4.1-flash-1017",
            dedicated_spec,
            project_id="secops-demo-env",
            region="us-central1",
            dry_run=False,
        ) is True
        _, deploy_kwargs = fake_open_model.deploy.call_args
        assert deploy_kwargs["machine_type"] == "a3-megagpu-8g"
        assert deploy_kwargs["accelerator_type"] == "NVIDIA_H100_MEGA_80GB"
        assert deploy_kwargs["accelerator_count"] == 8
        assert deploy_kwargs["deploy_request_timeout"] == 7200
        assert deploy_kwargs["serving_container_deployment_timeout"] == 7200
        assert deploy_kwargs["serving_container_shared_memory_size_mb"] == 40960
        assert "serving_container_image_uri" not in deploy_kwargs




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
    for filename in [
        "scripts/overnight_model_sweep.py",
        "scripts/run_overnight_sweep.py",
        "tests/test_overnight_sweep.py",
    ]:
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
