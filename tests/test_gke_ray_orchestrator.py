"""Unit tests for GKE Ray & Kueue Sweep Orchestrator."""

import json
from pathlib import Path
import subprocess
from typing import Any, Dict
from unittest.mock import MagicMock, patch
import pytest
import yaml

from scripts.run_gke_ray_sweep import (
    ALL_GKE_RAY_TARGETS,
    ALL_GKE_RAY_TARGETS_MAP,
    GKERayOrchestrator,
    GKERayTarget,
    render_eval_job_manifest,
    render_ray_cluster_manifest,
)

ROOT_DIR = Path(__file__).resolve().parent.parent


def test_no_emojis_in_source_and_tests() -> None:
    """Verify that Python files contain strictly no non-ASCII or emoji characters."""
    files_to_check = [
        ROOT_DIR / "scripts" / "run_gke_ray_sweep.py",
        ROOT_DIR / "tests" / "test_gke_ray_orchestrator.py",
    ]
    for file_path in files_to_check:
        assert file_path.exists(), f"File does not exist: {file_path}"
        content = file_path.read_text(encoding="utf-8")
        non_ascii = [char for char in content if ord(char) > 127]
        assert not non_ascii, f"Non-ASCII/emoji characters detected in {file_path}: {non_ascii[:5]}"


def test_gke_ray_target_dataclass_and_base_flavor() -> None:
    """Verify GKERayTarget properties and base flavor resolution logic."""
    target = GKERayTarget(
        flavor="gemma-3-27b-it-speculative",
        hf_repo="google/gemma-3-27b-it",
        gpu_count=4,
        gpu_type="nvidia-l4",
        cpu=16,
        memory="64Gi",
        tensor_parallel_size=4,
        extra_vllm_flags="--quantization=fp8",
        notes="Gemma 3 27B Speculative",
    )
    assert target.flavor == "gemma-3-27b-it-speculative"
    assert target.hf_repo == "google/gemma-3-27b-it"
    assert target.gpu_count == 4
    assert target.gpu_type == "nvidia-l4"
    assert target.cpu == 16
    assert target.memory == "64Gi"
    assert target.tensor_parallel_size == 4
    assert target.extra_vllm_flags == "--quantization=fp8"
    assert target.notes == "Gemma 3 27B Speculative"
    assert target.get_base_flavor() == "gemma-3-27b-it"

    # Test base flavor resolution across different suffixes
    test_cases = [
        ("gemma-2-2b-it", "gemma-2-2b-it"),
        ("gemma-2-9b-it-fp8", "gemma-2-9b-it"),
        ("gemma-3-12b-it-draft-1b", "gemma-3-12b-it"),
        ("gemma-3-27b-it-caching", "gemma-3-27b-it"),
        ("gemma-3-27b-it-draft-4b", "gemma-3-27b-it"),
        ("gemma-4-e2b-it-speculative", "gemma-4-e2b-it"),
        ("gemma-4-31b-it-draft-e2b", "gemma-4-31b-it"),
        ("gemma-4-31b-it-draft-e4b", "gemma-4-31b-it"),
    ]
    for flavor_name, expected_base in test_cases:
        t = GKERayTarget(
            flavor=flavor_name,
            hf_repo=f"google/{flavor_name}",
            gpu_count=1,
            gpu_type="nvidia-l4",
        )
        assert t.get_base_flavor() == expected_base


def test_catalog_completeness_and_shapes() -> None:
    """Verify catalog coverage for Gemma 2, Gemma 3, Gemma 4, and partner models."""
    assert len(ALL_GKE_RAY_TARGETS) >= 30
    assert len(ALL_GKE_RAY_TARGETS_MAP) == len(ALL_GKE_RAY_TARGETS)

    # Check key models exist
    required_flavors = [
        "gemma-2-2b-it",
        "gemma-2-9b-it",
        "gemma-2-27b-it",
        "gemma-3-1b-it",
        "gemma-3-4b-it",
        "gemma-3-12b-it",
        "gemma-3-27b-it",
        "gemma-4-e2b-it",
        "gemma-4-e4b-it",
        "gemma-4-31b-it",
        "inkling-small",
        "nemotron-3.5-lightning-bf16",
        "nemotron-3.5-super-vl-nvfp4",
        "nemotron-3.5-super-vl-bf16",
        "qwen2.5-coder-32b-instruct",
        "ministral-3b-2410",
        "phi-4",
        "deepseek-r1-distill-qwen-32b",
        "qwen3.8-flash-next",
        "glm-5.3-flash",
        "llama-3.2-3b-instruct",
        "llama-guard-3-8b",
        "llama-3.1-nemotron-70b-instruct",
    ]
    for flavor in required_flavors:
        assert flavor in ALL_GKE_RAY_TARGETS_MAP, f"Missing {flavor} in ALL_GKE_RAY_TARGETS"

    # Verify accelerator shapes and configurations
    for target in ALL_GKE_RAY_TARGETS:
        assert target.flavor, "Target flavor must not be empty"
        assert target.hf_repo, f"Target {target.flavor} must have a non-empty hf_repo"
        assert target.gpu_count in [1, 2, 4], f"Target {target.flavor} has invalid gpu_count: {target.gpu_count}"
        assert target.gpu_type in ["nvidia-l4", "nvidia-tesla-a100", "nvidia-a100-80gb", "nvidia-rtx-pro-6000"], (
            f"Target {target.flavor} has unexpected gpu_type: {target.gpu_type}"
        )
        assert target.tensor_parallel_size in [1, 2, 4], (
            f"Target {target.flavor} has unexpected tp size: {target.tensor_parallel_size}"
        )


def test_render_ray_cluster_manifest_1x_l4() -> None:
    """Verify RayCluster manifest rendering for 1x L4 single-GPU model."""
    target = ALL_GKE_RAY_TARGETS_MAP["gemma-3-4b-it"]
    manifest = render_ray_cluster_manifest(
        target=target,
        namespace="gemma-benchmarks",
        cluster_name="ray-gemma-3-4b-custom",
        queue_name="llm-sweep-queue",
    )

    assert manifest["apiVersion"] == "ray.io/v1"
    assert manifest["kind"] == "RayCluster"
    assert manifest["metadata"]["name"] == "ray-gemma-3-4b-custom"
    assert manifest["metadata"]["namespace"] == "gemma-benchmarks"
    assert manifest["metadata"]["labels"]["kueue.x-k8s.io/queue-name"] == "llm-sweep-queue"
    assert manifest["metadata"]["labels"]["model.gemma.io/flavor"] == "gemma-3-4b-it"

    worker_group = manifest["spec"]["workerGroupSpecs"][0]
    worker_spec = worker_group["template"]["spec"]
    assert worker_spec["nodeSelector"]["cloud.google.com/gke-accelerator"] == "nvidia-l4"

    worker_container = worker_spec["containers"][0]
    assert worker_container["resources"]["limits"]["nvidia.com/gpu"] == 1
    assert worker_container["resources"]["requests"]["nvidia.com/gpu"] == 1
    assert worker_container["resources"]["limits"]["cpu"] == "8"
    assert worker_container["resources"]["limits"]["memory"] == "32Gi"
    assert "--tensor-parallel-size 1" in " ".join(worker_container["command"])


def test_render_ray_cluster_manifest_4x_l4() -> None:
    """Verify RayCluster manifest rendering for 4x L4 multi-GPU model."""
    target = ALL_GKE_RAY_TARGETS_MAP["gemma-3-27b-it"]
    manifest = render_ray_cluster_manifest(
        target=target,
        namespace="gemma-benchmarks",
        queue_name="llm-sweep-queue",
    )

    assert manifest["metadata"]["name"] == "ray-gemma-3-27b-it"
    assert manifest["metadata"]["labels"]["model.gemma.io/flavor"] == "gemma-3-27b-it"

    worker_group = manifest["spec"]["workerGroupSpecs"][0]
    worker_spec = worker_group["template"]["spec"]
    assert worker_spec["nodeSelector"]["cloud.google.com/gke-accelerator"] == "nvidia-l4"

    worker_container = worker_spec["containers"][0]
    assert worker_container["resources"]["limits"]["nvidia.com/gpu"] == 4
    assert worker_container["resources"]["requests"]["nvidia.com/gpu"] == 4
    assert worker_container["resources"]["limits"]["cpu"] == "16"
    assert worker_container["resources"]["limits"]["memory"] == "64Gi"
    assert "--tensor-parallel-size 4" in " ".join(worker_container["command"])


def test_render_ray_cluster_manifest_2x_a100() -> None:
    """Verify RayCluster manifest rendering for 2x A100 multi-GPU model."""
    target = ALL_GKE_RAY_TARGETS_MAP["gemma-4-31b-it"]
    manifest = render_ray_cluster_manifest(
        target=target,
        namespace="gemma-benchmarks",
        queue_name="llm-sweep-queue",
    )

    assert manifest["metadata"]["name"] == "ray-gemma-4-31b-it"
    assert manifest["metadata"]["labels"]["model.gemma.io/flavor"] == "gemma-4-31b-it"

    worker_group = manifest["spec"]["workerGroupSpecs"][0]
    worker_spec = worker_group["template"]["spec"]
    assert worker_spec["nodeSelector"]["cloud.google.com/gke-accelerator"] == "nvidia-tesla-a100"

    worker_container = worker_spec["containers"][0]
    assert worker_container["resources"]["limits"]["nvidia.com/gpu"] == 2
    assert worker_container["resources"]["requests"]["nvidia.com/gpu"] == 2
    assert worker_container["resources"]["limits"]["cpu"] == "16"
    assert worker_container["resources"]["limits"]["memory"] == "64Gi"
    assert "--tensor-parallel-size 2" in " ".join(worker_container["command"])


def test_render_eval_job_manifest() -> None:
    """Verify batch Job manifest rendering and parameter substitution."""
    target = ALL_GKE_RAY_TARGETS_MAP["gemma-3-12b-it"]
    manifest = render_eval_job_manifest(
        target=target,
        namespace="gemma-benchmarks",
        job_name="custom-eval-job",
        queue_name="llm-sweep-queue",
        vllm_url="http://ray-gemma-3-12b-serve-svc:8000/v1",
        output_gcs_path="gs://my-bucket/results/gemma-3-12b-it",
    )

    assert manifest["apiVersion"] == "batch/v1"
    assert manifest["kind"] == "Job"
    assert manifest["metadata"]["name"] == "custom-eval-job"
    assert manifest["metadata"]["namespace"] == "gemma-benchmarks"
    assert manifest["metadata"]["labels"]["kueue.x-k8s.io/queue-name"] == "llm-sweep-queue"
    assert manifest["metadata"]["labels"]["model.gemma.io/flavor"] == "gemma-3-12b-it"

    job_spec = manifest["spec"]["template"]["spec"]
    assert job_spec["restartPolicy"] == "Never"

    container = job_spec["containers"][0]
    command_str = " ".join(container["command"])
    assert "eval_soc_agent.py" in command_str
    assert "http://ray-gemma-3-12b-serve-svc:8000/v1" in command_str
    assert "gs://my-bucket/results/gemma-3-12b-it" in command_str

    env_map = {item["name"]: item["value"] for item in container["env"]}
    assert env_map["MODEL_FLAVOR"] == "gemma-3-12b-it"
    assert env_map["HF_REPO"] == "google/gemma-3-12b-it"
    assert env_map["VLLM_SERVICE_URL"] == "http://ray-gemma-3-12b-serve-svc:8000/v1"
    assert env_map["OUTPUT_GCS_PATH"] == "gs://my-bucket/results/gemma-3-12b-it"


def test_orchestrator_filter_targets() -> None:
    """Verify target filtering logic in GKERayOrchestrator."""
    orchestrator = GKERayOrchestrator()

    # Empty filter returns all
    all_targets = orchestrator._filter_targets(None)
    assert len(all_targets) == len(ALL_GKE_RAY_TARGETS)

    # Filter by exact flavors
    matched = orchestrator._filter_targets(["gemma-3-4b-it", "gemma-3-12b-it"])
    assert len(matched) == 2
    assert {t.flavor for t in matched} == {"gemma-3-4b-it", "gemma-3-12b-it"}

    # Filter by wildcard pattern matching variants
    matched_wildcard = orchestrator._filter_targets(["gemma-2-9b*"])
    matched_flavors = {t.flavor for t in matched_wildcard}
    assert "gemma-2-9b-it" in matched_flavors
    assert "gemma-2-9b-it-fp8" in matched_flavors
    assert "gemma-2-9b-it-speculative" in matched_flavors


def test_orchestrator_dry_run_lifecycle() -> None:
    """Verify full end-to-end dry-run execution without active cluster."""
    orchestrator = GKERayOrchestrator(
        namespace="gemma-benchmarks",
        queue_name="llm-sweep-queue",
        dry_run=True,
    )
    target = ALL_GKE_RAY_TARGETS_MAP["gemma-3-4b-it"]

    # Dry run deploy
    cluster_name = orchestrator.deploy_ray_cluster(target)
    assert cluster_name == "ray-gemma-3-4b-it"

    # Dry run submit
    job_name = orchestrator.submit_eval_job(target)
    assert job_name == "eval-job-gemma-3-4b-it"

    # Dry run wait
    completed = orchestrator.wait_for_job_completion(job_name)
    assert completed is True

    # Dry run collect
    results = orchestrator.collect_results(target)
    assert results["flavor"] == "gemma-3-4b-it"
    assert results["status"] == "COMPLETED"
    assert results["dry_run"] is True

    # Dry run teardown
    orchestrator.teardown_ray_cluster(cluster_name)

    # Dry run sweep
    sweep_results = orchestrator.run_sweep(models_filter=["gemma-3-4b-it"], wait=True)
    assert len(sweep_results) == 1
    assert sweep_results[0]["flavor"] == "gemma-3-4b-it"
    assert sweep_results[0]["job_success"] is True


def test_orchestrator_mocked_kubectl_and_gcs() -> None:
    """Verify orchestrator interactions with mocked kubectl subprocesses."""
    orchestrator = GKERayOrchestrator(
        namespace="gemma-benchmarks",
        dry_run=False,
        timeout_seconds=5,
        poll_interval_seconds=0.01,
    )
    target = ALL_GKE_RAY_TARGETS_MAP["gemma-3-1b-it"]

    # Mock deploy_ray_cluster
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="raycluster.ray.io/ray-gemma-3-1b-it configured\n", returncode=0)
        c_name = orchestrator.deploy_ray_cluster(target)
        assert c_name == "ray-gemma-3-1b-it"
        assert mock_run.called

    # Mock submit_eval_job
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="job.batch/eval-job-gemma-3-1b-it created\n", returncode=0)
        j_name = orchestrator.submit_eval_job(target)
        assert j_name == "eval-job-gemma-3-1b-it"
        assert mock_run.called

    # Mock wait_for_job_completion with success
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout=json.dumps({"status": {"succeeded": 1}}),
            returncode=0,
        )
        assert orchestrator.wait_for_job_completion("eval-job-gemma-3-1b-it") is True

    # Mock wait_for_job_completion with failure condition
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout=json.dumps({
                "status": {
                    "conditions": [{"type": "Failed", "status": "True", "reason": "DeadlineExceeded"}]
                }
            }),
            returncode=0,
        )
        assert orchestrator.wait_for_job_completion("eval-job-gemma-3-1b-it") is False

    # Mock teardown_ray_cluster
    with patch("subprocess.run") as mock_run:
        orchestrator.teardown_ray_cluster("ray-gemma-3-1b-it")
        assert mock_run.called
