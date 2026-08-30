"""Unit tests for GKE Ray, vLLM, and Kueue manifest templates."""

import os
from pathlib import Path
from typing import Any, Dict
import pytest
import yaml

ROOT_DIR = Path(__file__).resolve().parent.parent


def test_manifest_files_exist_and_no_emojis() -> None:
    """Verify that all manifest and template files exist and contain no emojis."""
    required_files = [
        ROOT_DIR / "k8s" / "kueue_queues.yaml",
        ROOT_DIR / "k8s" / "templates" / "ray_vllm_cluster_template.yaml",
        ROOT_DIR / "k8s" / "templates" / "eval_job_template.yaml",
    ]
    for file_path in required_files:
        assert file_path.exists(), f"Missing required manifest file: {file_path}"
        content = file_path.read_text(encoding="utf-8")
        assert "apiVersion:" in content, f"Missing apiVersion in {file_path}"
        assert not any(ord(char) > 127 for char in content), (
            f"Non-ASCII/emoji character detected in {file_path}"
        )


def test_kueue_queues_manifest_structure() -> None:
    """Verify ResourceFlavor, ClusterQueue, and LocalQueue in kueue_queues.yaml."""
    kueue_path = ROOT_DIR / "k8s" / "kueue_queues.yaml"
    assert kueue_path.exists(), "k8s/kueue_queues.yaml does not exist"

    docs = list(yaml.safe_load_all(kueue_path.read_text(encoding="utf-8")))
    assert len(docs) >= 3, "Expected at least 3 YAML documents in kueue_queues.yaml"

    kinds = {doc.get("kind"): doc for doc in docs if isinstance(doc, dict)}
    assert "ResourceFlavor" in kinds or any(d.get("kind") == "ResourceFlavor" for d in docs)
    assert "ClusterQueue" in kinds
    assert "LocalQueue" in kinds

    # Verify ResourceFlavors
    resource_flavors = [d for d in docs if d.get("kind") == "ResourceFlavor"]
    flavor_names = [rf["metadata"]["name"] for rf in resource_flavors]
    assert "gpu-flavor-l4" in flavor_names, "Missing gpu-flavor-l4 ResourceFlavor"
    assert "gpu-flavor-a100" in flavor_names, "Missing gpu-flavor-a100 ResourceFlavor"

    l4_flavor = next(rf for rf in resource_flavors if rf["metadata"]["name"] == "gpu-flavor-l4")
    assert l4_flavor["spec"]["nodeLabels"].get("cloud.google.com/gke-accelerator") == "nvidia-l4"

    a100_flavor = next(rf for rf in resource_flavors if rf["metadata"]["name"] == "gpu-flavor-a100")
    assert a100_flavor["spec"]["nodeLabels"].get("cloud.google.com/gke-accelerator") in [
        "nvidia-tesla-a100",
        "nvidia-a100-80gb",
    ]

    # Verify ClusterQueue
    cluster_queue = next(d for d in docs if d.get("kind") == "ClusterQueue")
    assert cluster_queue["metadata"]["name"] == "gpu-benchmark-cluster-queue"
    resource_groups = cluster_queue["spec"]["resourceGroups"]
    covered = []
    for rg in resource_groups:
        covered.extend(rg.get("coveredResources", []))
    assert "cpu" in covered
    assert "memory" in covered
    assert "nvidia.com/gpu" in covered

    # Verify LocalQueue
    local_queue = next(d for d in docs if d.get("kind") == "LocalQueue")
    assert local_queue["metadata"]["name"] == "llm-sweep-queue"
    assert local_queue["metadata"]["namespace"] == "gemma-benchmarks"
    assert local_queue["spec"]["clusterQueue"] == "gpu-benchmark-cluster-queue"


def test_ray_vllm_cluster_template_rendering() -> None:
    """Verify RayCluster template placeholders and YAML rendering."""
    template_path = ROOT_DIR / "k8s" / "templates" / "ray_vllm_cluster_template.yaml"
    assert template_path.exists(), "k8s/templates/ray_vllm_cluster_template.yaml does not exist"

    template_content = template_path.read_text(encoding="utf-8")
    required_placeholders = [
        "{{CLUSTER_NAME}}",
        "{{NAMESPACE}}",
        "{{QUEUE_NAME}}",
        "{{MODEL_FLAVOR}}",
        "{{HF_REPO}}",
        "{{GPU_COUNT}}",
        "{{GPU_TYPE}}",
        "{{CPU}}",
        "{{MEMORY}}",
        "{{TP_SIZE}}",
        "{{EXTRA_FLAGS}}",
    ]
    for ph in required_placeholders:
        assert ph in template_content, f"Missing placeholder {ph} in ray cluster template"

    # Test substitution and parsing
    replacements: Dict[str, str] = {
        "{{CLUSTER_NAME}}": "ray-gemma-3-27b",
        "{{NAMESPACE}}": "gemma-benchmarks",
        "{{QUEUE_NAME}}": "llm-sweep-queue",
        "{{MODEL_FLAVOR}}": "gemma-3-27b-it",
        "{{HF_REPO}}": "google/gemma-3-27b-it",
        "{{GPU_COUNT}}": "4",
        "{{GPU_TYPE}}": "nvidia-l4",
        "{{CPU}}": "16",
        "{{MEMORY}}": "64Gi",
        "{{TP_SIZE}}": "4",
        "{{EXTRA_FLAGS}}": "--max-model-len 4096",
    }
    rendered_yaml = template_content
    for key, val in replacements.items():
        rendered_yaml = rendered_yaml.replace(key, val)

    manifest = yaml.safe_load(rendered_yaml)
    assert manifest["apiVersion"] == "ray.io/v1"
    assert manifest["kind"] == "RayCluster"
    assert manifest["metadata"]["name"] == "ray-gemma-3-27b"
    assert manifest["metadata"]["namespace"] == "gemma-benchmarks"
    assert manifest["metadata"]["labels"]["kueue.x-k8s.io/queue-name"] == "llm-sweep-queue"

    # Check Head Group Spec
    head_group = manifest["spec"]["headGroupSpec"]
    head_containers = head_group["template"]["spec"]["containers"]
    assert len(head_containers) >= 1
    assert any(vm["name"] == "dshm" for vm in head_containers[0]["volumeMounts"])

    # Check Worker Group Spec
    worker_groups = manifest["spec"]["workerGroupSpecs"]
    assert len(worker_groups) >= 1
    worker_template = worker_groups[0]["template"]
    worker_spec = worker_template["spec"]
    assert worker_spec["nodeSelector"]["cloud.google.com/gke-accelerator"] == "nvidia-l4"
    assert any(
        t.get("key") == "nvidia.com/gpu" for t in worker_spec.get("tolerations", [])
    )

    worker_container = worker_spec["containers"][0]
    assert worker_container["image"] == "vllm/vllm-openai:latest"
    assert worker_container["resources"]["limits"]["nvidia.com/gpu"] == 4
    assert worker_container["resources"]["requests"]["nvidia.com/gpu"] == 4
    assert any(vm["name"] == "dshm" for vm in worker_container["volumeMounts"])


def test_eval_job_template_rendering() -> None:
    """Verify batch Job template placeholders and YAML rendering."""
    template_path = ROOT_DIR / "k8s" / "templates" / "eval_job_template.yaml"
    assert template_path.exists(), "k8s/templates/eval_job_template.yaml does not exist"

    template_content = template_path.read_text(encoding="utf-8")
    required_placeholders = [
        "{{JOB_NAME}}",
        "{{NAMESPACE}}",
        "{{QUEUE_NAME}}",
        "{{MODEL_FLAVOR}}",
        "{{HF_REPO}}",
        "{{VLLM_SERVICE_URL}}",
        "{{OUTPUT_GCS_PATH}}",
    ]
    for ph in required_placeholders:
        assert ph in template_content, f"Missing placeholder {ph} in eval job template"

    replacements: Dict[str, str] = {
        "{{JOB_NAME}}": "eval-job-gemma-3-27b",
        "{{NAMESPACE}}": "gemma-benchmarks",
        "{{QUEUE_NAME}}": "llm-sweep-queue",
        "{{MODEL_FLAVOR}}": "gemma-3-27b-it",
        "{{HF_REPO}}": "google/gemma-3-27b-it",
        "{{VLLM_SERVICE_URL}}": "http://ray-gemma-3-27b-serve-svc:8000/v1",
        "{{OUTPUT_GCS_PATH}}": "gs://benchmarks-bucket/results/gemma-3-27b",
    }
    rendered_yaml = template_content
    for key, val in replacements.items():
        rendered_yaml = rendered_yaml.replace(key, val)

    manifest = yaml.safe_load(rendered_yaml)
    assert manifest["apiVersion"] == "batch/v1"
    assert manifest["kind"] == "Job"
    assert manifest["metadata"]["name"] == "eval-job-gemma-3-27b"
    assert manifest["metadata"]["namespace"] == "gemma-benchmarks"
    assert manifest["metadata"]["labels"]["kueue.x-k8s.io/queue-name"] == "llm-sweep-queue"

    job_spec = manifest["spec"]["template"]["spec"]
    assert job_spec["restartPolicy"] == "Never"
    container = job_spec["containers"][0]
    assert "eval_soc_agent.py" in " ".join(container["command"])
    assert "http://ray-gemma-3-27b-serve-svc:8000/v1" in " ".join(container["command"])
    assert "gs://benchmarks-bucket/results/gemma-3-27b" in " ".join(container["command"])
