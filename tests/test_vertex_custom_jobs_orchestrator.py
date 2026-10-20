"""Unit tests for the Vertex AI Custom Job Sweep Orchestrator."""

import json
import os
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.run_vertex_custom_job_sweep import (
    ALL_CUSTOM_JOB_TARGETS,
    VertexCustomJobOrchestrator,
    VertexCustomJobTarget,
    build_worker_pool_spec,
)


def test_vertex_custom_job_target_initialization():
    """Verifies VertexCustomJobTarget fields and default values."""
    target = VertexCustomJobTarget(
        flavor="gemma-3-4b-it",
        hf_repo="google/gemma-3-4b-it",
        machine_type="g2-standard-8",
        accelerator_type="NVIDIA_L4",
        accelerator_count=1,
        tensor_parallel_size=1,
        extra_vllm_flags="--limit_mm_per_prompt=image=5 --max-num-seqs=4",
        notes="Gemma 3 4B (1x L4)",
    )
    assert target.flavor == "gemma-3-4b-it"
    assert target.hf_repo == "google/gemma-3-4b-it"
    assert target.machine_type == "g2-standard-8"
    assert target.accelerator_type == "NVIDIA_L4"
    assert target.accelerator_count == 1
    assert target.tensor_parallel_size == 1
    assert target.extra_vllm_flags == "--limit_mm_per_prompt=image=5 --max-num-seqs=4"
    assert target.notes == "Gemma 3 4B (1x L4)"
    assert target.get_base_flavor() == "gemma-3-4b-it"


def test_vertex_custom_job_target_base_flavor_resolution():
    """Verifies base flavor extraction for optimization variants."""
    target_fp8 = VertexCustomJobTarget(
        flavor="gemma-3-27b-it-fp8",
        hf_repo="google/gemma-3-27b-it",
        machine_type="g2-standard-48",
        accelerator_type="NVIDIA_L4",
        accelerator_count=4,
        tensor_parallel_size=4,
    )
    assert target_fp8.get_base_flavor() == "gemma-3-27b-it"

    target_spec = VertexCustomJobTarget(
        flavor="gemma-4-31b-it-speculative",
        hf_repo="google/gemma-4-31B-it",
        machine_type="a2-highgpu-2g",
        accelerator_type="NVIDIA_TESLA_A100",
        accelerator_count=2,
        tensor_parallel_size=2,
    )
    assert target_spec.get_base_flavor() == "gemma-4-31b-it"

    target_draft = VertexCustomJobTarget(
        flavor="gemma-4-31b-it-draft-e2b",
        hf_repo="google/gemma-4-31B-it",
        machine_type="a2-highgpu-2g",
        accelerator_type="NVIDIA_TESLA_A100",
        accelerator_count=2,
        tensor_parallel_size=2,
    )
    assert target_draft.get_base_flavor() == "gemma-4-31b-it"


def test_build_worker_pool_spec_for_1x_l4():
    """Verifies worker pool dictionary specification for single L4 GPU instance."""
    target = VertexCustomJobTarget(
        flavor="gemma-3-4b-it",
        hf_repo="google/gemma-3-4b-it",
        machine_type="g2-standard-8",
        accelerator_type="NVIDIA_L4",
        accelerator_count=1,
        tensor_parallel_size=1,
        extra_vllm_flags="--limit_mm_per_prompt=image=5 --max-num-seqs=4",
    )
    specs = build_worker_pool_spec(
        target=target,
        container_image_uri="us-docker.pkg.dev/dandye-0324-chronicle/gemma-benchmarks/runner:latest",
        output_gcs_uri="gs://secops-eval-results/custom_jobs",
        hf_token="hf_mock_token_123",
    )

    assert isinstance(specs, list)
    assert len(specs) == 1
    spec = specs[0]

    assert spec["replica_count"] == 1
    machine_spec = spec["machine_spec"]
    assert machine_spec["machine_type"] == "g2-standard-8"
    assert machine_spec["accelerator_type"] == "NVIDIA_L4"
    assert machine_spec["accelerator_count"] == 1

    container_spec = spec["container_spec"]
    assert container_spec["image_uri"] == "us-docker.pkg.dev/dandye-0324-chronicle/gemma-benchmarks/runner:latest"
    assert container_spec["args"] == [
        "gemma-3-4b-it",
        "google/gemma-3-4b-it",
        "1",
        "--limit_mm_per_prompt=image=5 --max-num-seqs=4",
        "gs://secops-eval-results/custom_jobs",
    ]
    assert container_spec["env"] == [{"name": "HF_TOKEN", "value": "hf_mock_token_123"}]


def test_build_worker_pool_spec_for_4x_l4():
    """Verifies worker pool dictionary specification for 4x L4 GPU instance."""
    target = VertexCustomJobTarget(
        flavor="gemma-3-27b-it",
        hf_repo="google/gemma-3-27b-it",
        machine_type="g2-standard-48",
        accelerator_type="NVIDIA_L4",
        accelerator_count=4,
        tensor_parallel_size=4,
        extra_vllm_flags="--limit_mm_per_prompt=image=5 --max-num-seqs=4",
    )
    specs = build_worker_pool_spec(
        target=target,
        container_image_uri="us-docker.pkg.dev/dandye-0324-chronicle/gemma-benchmarks/runner:latest",
        output_gcs_uri="gs://secops-eval-results/custom_jobs",
    )

    assert isinstance(specs, list)
    assert len(specs) == 1
    spec = specs[0]
    assert spec["machine_spec"]["machine_type"] == "g2-standard-48"
    assert spec["machine_spec"]["accelerator_type"] == "NVIDIA_L4"
    assert spec["machine_spec"]["accelerator_count"] == 4
    assert spec["container_spec"]["args"][2] == "4"
    assert "env" not in spec["container_spec"] or len(spec["container_spec"]["env"]) == 0


def test_build_worker_pool_spec_for_2x_a100():
    """Verifies worker pool dictionary specification for 2x A100 GPU instance."""
    target = VertexCustomJobTarget(
        flavor="gemma-4-31b-it",
        hf_repo="google/gemma-4-31B-it",
        machine_type="a2-highgpu-2g",
        accelerator_type="NVIDIA_TESLA_A100",
        accelerator_count=2,
        tensor_parallel_size=2,
        extra_vllm_flags="--max-num-seqs=16",
    )
    specs = build_worker_pool_spec(
        target=target,
        container_image_uri="us-docker.pkg.dev/dandye-0324-chronicle/gemma-benchmarks/runner:latest",
        output_gcs_uri="gs://secops-eval-results/custom_jobs",
    )

    assert isinstance(specs, list)
    assert len(specs) == 1
    spec = specs[0]
    assert spec["machine_spec"]["machine_type"] == "a2-highgpu-2g"
    assert spec["machine_spec"]["accelerator_type"] == "NVIDIA_TESLA_A100"
    assert spec["machine_spec"]["accelerator_count"] == 2
    assert spec["container_spec"]["args"][2] == "2"


def test_all_custom_job_targets_catalog_completeness():
    """Verifies that the catalog includes Gemma 2, 3, 4, and partner model families."""
    flavors = [t.flavor for t in ALL_CUSTOM_JOB_TARGETS]

    # Gemma 2 Family
    assert "gemma-2-2b-it" in flavors
    assert "gemma-2-2b-it-speculative" in flavors
    assert "gemma-2-9b-it" in flavors
    assert "gemma-2-9b-it-fp8" in flavors
    assert "gemma-2-9b-it-speculative" in flavors
    assert "gemma-2-27b-it" in flavors
    assert "gemma-2-27b-it-fp8" in flavors
    assert "gemma-2-27b-it-speculative" in flavors

    # Gemma 3 Family
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

    # Gemma 4 Family
    assert "gemma-4-e2b-it" in flavors
    assert "gemma-4-e2b-it-speculative" in flavors
    assert "gemma-4-e4b-it" in flavors
    assert "gemma-4-e4b-it-speculative" in flavors
    assert "gemma-4-31b-it" in flavors
    assert "gemma-4-31b-it-speculative" in flavors
    assert "gemma-4-31b-it-draft-e2b" in flavors
    assert "gemma-4-31b-it-draft-e4b" in flavors

    # Partner / Open Models
    assert "nemotron-3.5-lightning-bf16" in flavors
    assert "nemotron-3.5-super-vl-nvfp4" in flavors
    assert "nemotron-3.5-super-vl-bf16" in flavors
    assert "qwen2.5-coder-32b-instruct" in flavors
    assert "ministral-3b-2410" in flavors
    assert "phi-4" in flavors
    assert "deepseek-r1-distill-qwen-32b" in flavors
    assert "llama-3.2-3b-instruct" in flavors
    assert "llama-guard-3-8b" in flavors
    assert "llama-3.1-nemotron-70b-instruct" in flavors

    # Unique flavors check
    assert len(flavors) == len(set(flavors)), "Duplicate flavor detected in ALL_CUSTOM_JOB_TARGETS"

    # Validate target attributes
    for t in ALL_CUSTOM_JOB_TARGETS:
        assert t.machine_type in [
            "g2-standard-4",
            "g2-standard-8",
            "g2-standard-12",
            "g2-standard-48",
            "g4-standard-48",
            "g4-standard-192",
            "a2-highgpu-2g",
        ]
        assert t.accelerator_type in ["NVIDIA_L4", "NVIDIA_TESLA_A100", "NVIDIA_RTX_PRO_6000"]
        assert t.accelerator_count in [1, 2, 4]
        assert t.tensor_parallel_size in [1, 2, 4]
        assert t.hf_repo.strip() != ""


def test_dry_run_orchestrator_execution():
    """Verifies that dry-run mode executes end-to-end without live GCP API calls."""
    orchestrator = VertexCustomJobOrchestrator(
        project_id="test-project",
        region="us-central1",
        container_image_uri="image:latest",
        output_gcs_bucket="gs://test-bucket",
        dry_run=True,
    )

    target = VertexCustomJobTarget(
        flavor="gemma-3-4b-it",
        hf_repo="google/gemma-3-4b-it",
        machine_type="g2-standard-8",
        accelerator_type="NVIDIA_L4",
        accelerator_count=1,
        tensor_parallel_size=1,
    )

    # Submit job
    job = orchestrator.submit_job(target)
    assert job is not None

    # Poll job
    poll_res = orchestrator.poll_job(job)
    assert poll_res is True

    # Collect results
    res = orchestrator.collect_results(target)
    assert res["flavor"] == "gemma-3-4b-it"
    assert res["success"] is True
    assert "soc_eval" in res
    assert res["soc_eval"]["summary"]["total_cases"] == 5
    assert "benchmark" in res


def test_model_filtering_in_run_sweep():
    """Verifies that model filtering correctly restricts the executed sweep targets."""
    orchestrator = VertexCustomJobOrchestrator(dry_run=True)
    results = orchestrator.run_sweep(models_filter=["gemma-4-e2b-it", "gemma-3-1b-it"])

    assert len(results) == 2
    flavors = [r["flavor"] for r in results]
    assert "gemma-4-e2b-it" in flavors
    assert "gemma-3-1b-it" in flavors


def test_submit_job_live_invokes_vertex_ai():
    """Verifies that submit_job initializes and calls Vertex AI CustomJob in live mode."""
    mock_custom_job_instance = MagicMock()
    mock_custom_job_cls = MagicMock(return_value=mock_custom_job_instance)
    mock_init = MagicMock()

    with patch("google.cloud.aiplatform.init", mock_init), \
         patch("google.cloud.aiplatform.CustomJob", mock_custom_job_cls):
        orchestrator = VertexCustomJobOrchestrator(
            project_id="live-project",
            region="us-central1",
            dry_run=False,
        )

        target = VertexCustomJobTarget(
            flavor="gemma-3-4b-it",
            hf_repo="google/gemma-3-4b-it",
            machine_type="g2-standard-8",
            accelerator_type="NVIDIA_L4",
            accelerator_count=1,
            tensor_parallel_size=1,
        )

        job = orchestrator.submit_job(target)
        mock_init.assert_called_once_with(
            project="live-project",
            location="us-central1",
            staging_bucket="gs://secops-eval-results/custom_jobs",
        )
        mock_custom_job_cls.assert_called_once()
        mock_custom_job_instance.submit.assert_called_once()
        assert job == mock_custom_job_instance


def test_poll_job_live_success_and_failure():
    """Verifies polling logic handles completed and failed states."""
    orchestrator = VertexCustomJobOrchestrator(dry_run=False)

    # Success case
    mock_success_job = MagicMock()
    mock_success_job.state.name = "JOB_STATE_SUCCEEDED"
    mock_success_job.wait = MagicMock()
    assert orchestrator.poll_job(mock_success_job) is True

    # Failure case
    mock_failed_job = MagicMock()
    mock_failed_job.state.name = "JOB_STATE_FAILED"
    mock_failed_job.wait = MagicMock(side_effect=RuntimeError("Job failed on worker"))
    assert orchestrator.poll_job(mock_failed_job) is False


def test_collect_results_from_gcs_mocked(tmp_path: Path):
    """Verifies collecting and parsing results from Google Cloud Storage."""
    orchestrator = VertexCustomJobOrchestrator(
        project_id="test-project",
        output_gcs_bucket="gs://test-bucket/results",
        dry_run=False,
    )
    target = VertexCustomJobTarget(
        flavor="gemma-3-4b-it",
        hf_repo="google/gemma-3-4b-it",
        machine_type="g2-standard-8",
        accelerator_type="NVIDIA_L4",
        accelerator_count=1,
        tensor_parallel_size=1,
    )

    mock_soc_eval = {
        "flavor": "gemma-3-4b-it",
        "summary": {"pass_rate": 100.0, "avg_rubric_score": 95.0, "total_cases": 5},
        "case_results": [],
    }
    mock_bench = {
        "flavor": "gemma-3-4b-it",
        "avg_latency_s": 1.1,
        "tps": 80.0,
    }

    mock_storage_client = MagicMock()
    mock_bucket = MagicMock()
    mock_soc_blob = MagicMock()
    mock_soc_blob.download_as_text.return_value = json.dumps(mock_soc_eval)
    mock_bench_blob = MagicMock()
    mock_bench_blob.download_as_text.return_value = json.dumps(mock_bench)

    def mock_get_blob(blob_name):
        if "soc_eval_report.json" in blob_name:
            return mock_soc_blob
        if "benchmark.json" in blob_name:
            return mock_bench_blob
        return None

    mock_bucket.get_blob.side_effect = mock_get_blob
    mock_storage_client.bucket.return_value = mock_bucket

    with patch("google.cloud.storage.Client", return_value=mock_storage_client):
        res = orchestrator.collect_results(target)
        assert res["flavor"] == "gemma-3-4b-it"
        assert res["success"] is True
        assert res["soc_eval"] == mock_soc_eval
        assert res["benchmark"] == mock_bench


def test_orchestrator_default_container_image_uri():
    """Verifies that the orchestrator uses the standardized Artifact Registry image URI default."""
    orchestrator = VertexCustomJobOrchestrator()
    assert orchestrator.container_image_uri == "us-docker.pkg.dev/dandye-0324-chronicle/gemma-benchmarks/runner:latest"


def test_no_emojis_in_custom_jobs_orchestrator():
    """Verifies that no emojis exist in orchestrator or test files."""
    files_to_check = [
        ROOT_DIR / "scripts" / "run_vertex_custom_job_sweep.py",
        Path(__file__),
    ]

    for file_path in files_to_check:
        if file_path.exists():
            content = file_path.read_text(encoding="utf-8")
            for line_idx, line in enumerate(content.splitlines(), start=1):
                for char in line:
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
                    assert not is_emoji, (
                        f"Emoji character '{char}' (ord {code_point}) "
                        f"found at {file_path}:{line_idx}"
                    )
