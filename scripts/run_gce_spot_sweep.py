#!/usr/bin/env python3
"""
Compute Engine (GCE) Ephemeral Spot GPU VM Sweep Orchestrator

Manages the lifecycle of ephemeral Spot GPU VMs attached to Local NVMe SSD scratch disks:
1. Dynamically generates gcloud compute instance provisioning commands with Spot pricing.
2. Attaches Local NVMe SSD scratch drives and configures startup automation.
3. Streams serial console logs and monitors job progress.
4. Collects benchmark and SOC Tier 1 evaluation outputs from Google Cloud Storage.
5. Records deletion requests and checks whether the resource is absent.
"""

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import tempfile
import hashlib
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


from scripts.experiment_run import new_run, load_run, validate_run, identity_error, write_json, now


def _artifact_evaluation_status(data: Dict[str, Any]) -> str:
    """Resolve explicit evaluator signals; cleanup and launch identity are separate."""
    evaluation = data.get("evaluation")
    evaluation = evaluation if isinstance(evaluation, dict) else {}
    provenance = data.get("provenance")
    provenance = provenance if isinstance(provenance, dict) else {}
    lifecycle = provenance.get("lifecycle")
    lifecycle = lifecycle if isinstance(lifecycle, dict) else {}
    signals = [data.get("status"), evaluation.get("status"),
               lifecycle.get("evaluation"), lifecycle.get("status")]
    statuses = [str(value).strip().upper() for value in signals if value is not None]
    for status in statuses:
        if status in {"FAILED", "ERROR", "TIMED_OUT", "STOCKOUT"}:
            return status
    exit_status = evaluation.get("evaluator_exit_status")
    if isinstance(exit_status, int) and not isinstance(exit_status, bool) and exit_status != 0:
        return "FAILED"
    if statuses and all(status == "COMPLETED" for status in statuses):
        return "COMPLETED"
    return "UNVERIFIED"


def _reject_nonfinite(value: str):
    raise ValueError(f"Non-finite JSON number: {value}")


def _benchmark_error(data: Any) -> Optional[str]:
    """The startup sample is a non-streaming OpenAI-compatible completion."""
    if not isinstance(data, dict):
        return "Benchmark sample must be a JSON object"
    if data.get("error") or data.get("errors") or str(data.get("status", "")).lower() in {"failed", "error"}:
        return "Benchmark sample contains a provider error"
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return "Benchmark sample contains no output choices"
    for choice in choices:
        if not isinstance(choice, dict) or choice.get("error") or choice.get("finish_reason") == "error":
            return "Benchmark sample contains an invalid or failed choice"
        message = choice.get("message")
        content = choice.get("text") if "text" in choice else message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            return "Benchmark sample contains no generated text"
    return None


@dataclass
class GCESpotTarget:
    """Specification of an Ephemeral Spot GPU evaluation target on GCE."""

    flavor: str
    hf_repo: str
    machine_type: str
    accelerator_type: str
    accelerator_count: int
    local_ssd_count: int
    tensor_parallel_size: int = 1
    extra_vllm_flags: str = ""
    notes: str = ""

    def get_base_flavor(self) -> str:
        """Strip optimization variant suffixes to resolve the base catalog model name."""
        base = self.flavor
        for suffix in [
            "-speculative",
            "-fp8",
            "-caching",
            "-draft-e2b",
            "-draft-e4b",
            "-draft-1b",
            "-draft-4b",
            "-draft-2b",
        ]:
            if base.endswith(suffix):
                base = base[: -len(suffix)]
        return base


# Comprehensive Catalog of all GCE Spot GPU Models and Compute Configurations
ALL_GCE_SPOT_TARGETS: List[GCESpotTarget] = [
    # Gemma 2 Family (1x L4 / 4x L4)
    GCESpotTarget(
        flavor="gemma-2-2b-it",
        hf_repo="google/gemma-2-2b-it",
        machine_type="g2-standard-4",
        accelerator_type="nvidia-l4",
        accelerator_count=1,
        local_ssd_count=1,
        tensor_parallel_size=1,
        notes="Gemma 2 2B (1x L4, 1x NVMe SSD)",
    ),
    GCESpotTarget(
        flavor="gemma-2-2b-it-speculative",
        hf_repo="google/gemma-2-2b-it",
        machine_type="g2-standard-4",
        accelerator_type="nvidia-l4",
        accelerator_count=1,
        local_ssd_count=1,
        tensor_parallel_size=1,
        extra_vllm_flags="--speculative-model=[ngram] --num-speculative-tokens=5 --ngram-prompt-lookup-max=5 --ngram-prompt-lookup-min=2",
        notes="Gemma 2 2B Speculative (1x L4, 1x NVMe SSD)",
    ),
    GCESpotTarget(
        flavor="gemma-2-9b-it",
        hf_repo="google/gemma-2-9b-it",
        machine_type="g2-standard-16",
        accelerator_type="nvidia-l4",
        accelerator_count=1,
        local_ssd_count=1,
        tensor_parallel_size=1,
        notes="Gemma 2 9B (1x L4, 1x NVMe SSD)",
    ),
    GCESpotTarget(
        flavor="gemma-2-9b-it-fp8",
        hf_repo="google/gemma-2-9b-it",
        machine_type="g2-standard-16",
        accelerator_type="nvidia-l4",
        accelerator_count=1,
        local_ssd_count=1,
        tensor_parallel_size=1,
        extra_vllm_flags="--quantization=fp8",
        notes="Gemma 2 9B FP8 Quantized (1x L4, 1x NVMe SSD)",
    ),
    GCESpotTarget(
        flavor="gemma-2-9b-it-speculative",
        hf_repo="google/gemma-2-9b-it",
        machine_type="g2-standard-16",
        accelerator_type="nvidia-l4",
        accelerator_count=1,
        local_ssd_count=1,
        tensor_parallel_size=1,
        extra_vllm_flags="--quantization=fp8 --speculative-model=[ngram] --num-speculative-tokens=5 --ngram-prompt-lookup-max=5 --ngram-prompt-lookup-min=2",
        notes="Gemma 2 9B FP8 Speculative (1x L4, 1x NVMe SSD)",
    ),
    GCESpotTarget(
        flavor="gemma-2-27b-it",
        hf_repo="google/gemma-2-27b-it",
        machine_type="g2-standard-48",
        accelerator_type="nvidia-l4",
        accelerator_count=4,
        local_ssd_count=4,
        tensor_parallel_size=4,
        notes="Gemma 2 27B (4x L4, 4x NVMe SSD)",
    ),
    GCESpotTarget(
        flavor="gemma-2-27b-it-fp8",
        hf_repo="google/gemma-2-27b-it",
        machine_type="g2-standard-48",
        accelerator_type="nvidia-l4",
        accelerator_count=4,
        local_ssd_count=4,
        tensor_parallel_size=4,
        extra_vllm_flags="--quantization=fp8",
        notes="Gemma 2 27B FP8 Quantized (4x L4, 4x NVMe SSD)",
    ),
    GCESpotTarget(
        flavor="gemma-2-27b-it-speculative",
        hf_repo="google/gemma-2-27b-it",
        machine_type="g2-standard-48",
        accelerator_type="nvidia-l4",
        accelerator_count=4,
        local_ssd_count=4,
        tensor_parallel_size=4,
        extra_vllm_flags="--quantization=fp8 --speculative-model=[ngram] --num-speculative-tokens=5 --ngram-prompt-lookup-max=5 --ngram-prompt-lookup-min=2",
        notes="Gemma 2 27B FP8 Speculative (4x L4, 4x NVMe SSD)",
    ),

    # Gemma 3 Family (1x L4 / 4x L4)
    GCESpotTarget(
        flavor="gemma-3-1b-it",
        hf_repo="google/gemma-3-1b-it",
        machine_type="g2-standard-4",
        accelerator_type="nvidia-l4",
        accelerator_count=1,
        local_ssd_count=1,
        tensor_parallel_size=1,
        extra_vllm_flags="--max-model-len=8192",
        notes="Gemma 3 1B (1x L4, 1x NVMe SSD)",
    ),
    GCESpotTarget(
        flavor="gemma-3-1b-it-speculative",
        hf_repo="google/gemma-3-1b-it",
        machine_type="g2-standard-4",
        accelerator_type="nvidia-l4",
        accelerator_count=1,
        local_ssd_count=1,
        tensor_parallel_size=1,
        extra_vllm_flags="--max-model-len=8192 --speculative-model=[ngram] --num-speculative-tokens=5 --ngram-prompt-lookup-max=5 --ngram-prompt-lookup-min=2",
        notes="Gemma 3 1B Speculative (1x L4, 1x NVMe SSD)",
    ),
    GCESpotTarget(
        flavor="gemma-3-4b-it",
        hf_repo="google/gemma-3-4b-it",
        machine_type="g2-standard-8",
        accelerator_type="nvidia-l4",
        accelerator_count=1,
        local_ssd_count=1,
        tensor_parallel_size=1,
        extra_vllm_flags="--max-model-len=8192",
        notes="Gemma 3 4B (1x L4, 1x NVMe SSD)",
    ),
    GCESpotTarget(
        flavor="gemma-3-4b-it-speculative",
        hf_repo="google/gemma-3-4b-it",
        machine_type="g2-standard-8",
        accelerator_type="nvidia-l4",
        accelerator_count=1,
        local_ssd_count=1,
        tensor_parallel_size=1,
        extra_vllm_flags="--max-model-len=8192 --speculative-model=[ngram] --num-speculative-tokens=5 --ngram-prompt-lookup-max=5 --ngram-prompt-lookup-min=2",
        notes="Gemma 3 4B Speculative (1x L4, 1x NVMe SSD)",
    ),
    GCESpotTarget(
        flavor="gemma-3-12b-it",
        hf_repo="google/gemma-3-12b-it",
        machine_type="g2-standard-48",
        accelerator_type="nvidia-l4",
        accelerator_count=4,
        local_ssd_count=4,
        tensor_parallel_size=4,
        extra_vllm_flags="--max-model-len=8192",
        notes="Gemma 3 12B (4x L4, 4x NVMe SSD)",
    ),
    GCESpotTarget(
        flavor="gemma-3-12b-it-fp8",
        hf_repo="google/gemma-3-12b-it",
        machine_type="g2-standard-48",
        accelerator_type="nvidia-l4",
        accelerator_count=4,
        local_ssd_count=4,
        tensor_parallel_size=4,
        extra_vllm_flags="--quantization=fp8 --max-model-len=8192",
        notes="Gemma 3 12B FP8 (4x L4, 4x NVMe SSD)",
    ),
    GCESpotTarget(
        flavor="gemma-3-12b-it-speculative",
        hf_repo="google/gemma-3-12b-it",
        machine_type="g2-standard-48",
        accelerator_type="nvidia-l4",
        accelerator_count=4,
        local_ssd_count=4,
        tensor_parallel_size=4,
        extra_vllm_flags="--quantization=fp8 --speculative-model=[ngram] --num-speculative-tokens=5 --ngram-prompt-lookup-max=5 --ngram-prompt-lookup-min=2 --max-model-len=8192",
        notes="Gemma 3 12B FP8 Speculative (4x L4, 4x NVMe SSD)",
    ),
    GCESpotTarget(
        flavor="gemma-3-27b-it",
        hf_repo="google/gemma-3-27b-it",
        machine_type="g2-standard-48",
        accelerator_type="nvidia-l4",
        accelerator_count=4,
        local_ssd_count=4,
        tensor_parallel_size=4,
        extra_vllm_flags="--max-model-len=8192",
        notes="Gemma 3 27B (4x L4, 4x NVMe SSD)",
    ),
    GCESpotTarget(
        flavor="gemma-3-27b-it-fp8",
        hf_repo="google/gemma-3-27b-it",
        machine_type="g2-standard-48",
        accelerator_type="nvidia-l4",
        accelerator_count=4,
        local_ssd_count=4,
        tensor_parallel_size=4,
        extra_vllm_flags="--quantization=fp8 --max-model-len=8192",
        notes="Gemma 3 27B FP8 (4x L4, 4x NVMe SSD)",
    ),
    GCESpotTarget(
        flavor="gemma-3-27b-it-speculative",
        hf_repo="google/gemma-3-27b-it",
        machine_type="g2-standard-48",
        accelerator_type="nvidia-l4",
        accelerator_count=4,
        local_ssd_count=4,
        tensor_parallel_size=4,
        extra_vllm_flags="--quantization=fp8 --speculative-model=[ngram] --num-speculative-tokens=5 --ngram-prompt-lookup-max=5 --ngram-prompt-lookup-min=2 --max-model-len=8192",
        notes="Gemma 3 27B FP8 Speculative (4x L4, 4x NVMe SSD)",
    ),
    GCESpotTarget(
        flavor="gemma-3-27b-it-caching",
        hf_repo="google/gemma-3-27b-it",
        machine_type="g2-standard-48",
        accelerator_type="nvidia-l4",
        accelerator_count=4,
        local_ssd_count=4,
        tensor_parallel_size=4,
        extra_vllm_flags="--quantization=fp8 --enable-chunked-prefill --enable-prefix-caching --max-model-len=8192",
        notes="Gemma 3 27B FP8 Prefix Caching (4x L4, 4x NVMe SSD)",
    ),

    # Gemma 4 Family (1x L4 / 2x A100)
    GCESpotTarget(
        flavor="gemma-4-e2b-it",
        hf_repo="google/gemma-4-E2B-it",
        machine_type="g2-standard-4",
        accelerator_type="nvidia-l4",
        accelerator_count=1,
        local_ssd_count=1,
        tensor_parallel_size=1,
        extra_vllm_flags="--max-num-seqs=16",
        notes="Gemma 4 E2B (1x L4, 1x NVMe SSD)",
    ),
    GCESpotTarget(
        flavor="gemma-4-e2b-it-speculative",
        hf_repo="google/gemma-4-E2B-it",
        machine_type="g2-standard-4",
        accelerator_type="nvidia-l4",
        accelerator_count=1,
        local_ssd_count=1,
        tensor_parallel_size=1,
        extra_vllm_flags="--max-num-seqs=16 --speculative-model=[ngram] --num-speculative-tokens=5 --ngram-prompt-lookup-max=5 --ngram-prompt-lookup-min=2",
        notes="Gemma 4 E2B Speculative (1x L4, 1x NVMe SSD)",
    ),
    GCESpotTarget(
        flavor="gemma-4-e4b-it",
        hf_repo="google/gemma-4-E4B-it",
        machine_type="g2-standard-8",
        accelerator_type="nvidia-l4",
        accelerator_count=1,
        local_ssd_count=1,
        tensor_parallel_size=1,
        extra_vllm_flags="--max-num-seqs=16",
        notes="Gemma 4 E4B (1x L4, 1x NVMe SSD)",
    ),
    GCESpotTarget(
        flavor="gemma-4-e4b-it-speculative",
        hf_repo="google/gemma-4-E4B-it",
        machine_type="g2-standard-8",
        accelerator_type="nvidia-l4",
        accelerator_count=1,
        local_ssd_count=1,
        tensor_parallel_size=1,
        extra_vllm_flags="--max-num-seqs=16 --speculative-model=[ngram] --num-speculative-tokens=5 --ngram-prompt-lookup-max=5 --ngram-prompt-lookup-min=2",
        notes="Gemma 4 E4B Speculative (1x L4, 1x NVMe SSD)",
    ),
    GCESpotTarget(
        flavor="gemma-4-31b-it",
        hf_repo="google/gemma-4-31B-it",
        machine_type="a2-highgpu-2g",
        accelerator_type="nvidia-tesla-a100",
        accelerator_count=2,
        local_ssd_count=2,
        tensor_parallel_size=2,
        extra_vllm_flags="--max-num-seqs=16",
        notes="Gemma 4 31B Multimodal Reasoner (2x A100, 2x NVMe SSD)",
    ),
    GCESpotTarget(
        flavor="gemma-4-31b-it-speculative",
        hf_repo="google/gemma-4-31B-it",
        machine_type="a2-highgpu-2g",
        accelerator_type="nvidia-tesla-a100",
        accelerator_count=2,
        local_ssd_count=2,
        tensor_parallel_size=2,
        extra_vllm_flags="--max-num-seqs=16 --speculative-model=[ngram] --num-speculative-tokens=5 --ngram-prompt-lookup-max=5 --ngram-prompt-lookup-min=2",
        notes="Gemma 4 31B Speculative (2x A100, 2x NVMe SSD)",
    ),

    # Partner & Open Model Targets
    GCESpotTarget(
        flavor="inkling-small",
        hf_repo="thinkingmachines/Inkling-Small",
        machine_type="g2-standard-48",
        accelerator_type="nvidia-l4",
        accelerator_count=4,
        local_ssd_count=4,
        tensor_parallel_size=4,
        extra_vllm_flags="--tokenizer-mode=inkling",
        notes="Thinking Machines Inkling Small (4x L4, 4x NVMe SSD)",
    ),
    GCESpotTarget(
        flavor="nemotron-3.5-lightning-bf16",
        hf_repo="nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16",
        machine_type="g2-standard-48",
        accelerator_type="nvidia-l4",
        accelerator_count=4,
        local_ssd_count=4,
        tensor_parallel_size=4,
        notes="NVIDIA Nemotron 3.5 Lightning (4x L4, 4x NVMe SSD)",
    ),
    GCESpotTarget(
        flavor="qwen2.5-coder-32b-instruct",
        hf_repo="Qwen/Qwen2.5-Coder-32B-Instruct",
        machine_type="g2-standard-48",
        accelerator_type="nvidia-l4",
        accelerator_count=4,
        local_ssd_count=4,
        tensor_parallel_size=4,
        notes="Qwen 2.5 Coder 32B (4x L4, 4x NVMe SSD)",
    ),
    GCESpotTarget(
        flavor="deepseek-r1-distill-qwen-32b",
        hf_repo="deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
        machine_type="g2-standard-48",
        accelerator_type="nvidia-l4",
        accelerator_count=4,
        local_ssd_count=4,
        tensor_parallel_size=4,
        notes="DeepSeek R1 Distill Qwen 32B (4x L4, 4x NVMe SSD)",
    ),
    GCESpotTarget(
        flavor="ministral-3b-2410",
        hf_repo="mistralai/Ministral-3b-instruct-2410",
        machine_type="g2-standard-8",
        accelerator_type="nvidia-l4",
        accelerator_count=1,
        local_ssd_count=1,
        tensor_parallel_size=1,
        notes="Mistral Ministral 3B (1x L4, 1x NVMe SSD)",
    ),
    GCESpotTarget(
        flavor="phi-4",
        hf_repo="microsoft/phi-4",
        machine_type="g2-standard-16",
        accelerator_type="nvidia-l4",
        accelerator_count=1,
        local_ssd_count=1,
        tensor_parallel_size=1,
        notes="Microsoft Phi-4 14B (1x L4, 1x NVMe SSD)",
    ),
    GCESpotTarget(
        flavor="llama-3.2-3b-instruct",
        hf_repo="meta-llama/Llama-3.2-3B-Instruct",
        machine_type="g2-standard-8",
        accelerator_type="nvidia-l4",
        accelerator_count=1,
        local_ssd_count=1,
        tensor_parallel_size=1,
        notes="Meta Llama 3.2 3B (1x L4, 1x NVMe SSD)",
    ),
    GCESpotTarget(
        flavor="llama-guard-3-8b",
        hf_repo="meta-llama/Llama-Guard-3-8B",
        machine_type="g2-standard-16",
        accelerator_type="nvidia-l4",
        accelerator_count=1,
        local_ssd_count=1,
        tensor_parallel_size=1,
        notes="Meta Llama Guard 3 8B (1x L4, 1x NVMe SSD)",
    ),
    GCESpotTarget(
        flavor="llama-3.1-nemotron-70b-instruct",
        hf_repo="nvidia/Llama-3.1-Nemotron-70B-Instruct-HF",
        machine_type="g2-standard-48",
        accelerator_type="nvidia-l4",
        accelerator_count=4,
        local_ssd_count=4,
        tensor_parallel_size=4,
        notes="NVIDIA Llama 3.1 Nemotron 70B (4x L4, 4x NVMe SSD)",
    ),
]


def build_gce_spot_create_command(
    target: GCESpotTarget,
    project_id: str,
    zone: str,
    output_gcs_uri: str,
    hf_token: Optional[str] = None,
    script_template_path: Optional[Path] = None,
    image_family: str = "ubuntu-2204-lts",
    image_project: str = "ubuntu-os-cloud",
    instance_name: Optional[str] = None,
    service_account: Optional[str] = None,
    boot_disk_size: str = "100GB",
    boot_disk_type: str = "pd-ssd",
    run_id: Optional[str] = None,
    configuration_hash: Optional[str] = None,
    source_bundle: Optional[Dict[str, str]] = None,
) -> List[str]:
    """
    Constructs the exact gcloud compute instances create command arguments.

    Enforces Spot VM provisioning (--provisioning-model=SPOT), programmatic
    self-deletion (--instance-termination-action=DELETE), maintenance policy
    (--maintenance-policy=TERMINATE), attached local NVMe SSDs, and startup
    metadata configuration.
    """
    if not instance_name:
        sanitized_flavor = target.flavor.replace(".", "-")
        instance_name = f"spot-{sanitized_flavor}"

    cmd: List[str] = [
        "gcloud",
        "compute",
        "instances",
        "create",
        instance_name,
        f"--project={project_id}",
        f"--zone={zone}",
        f"--machine-type={target.machine_type}",
        "--provisioning-model=SPOT",
        "--instance-termination-action=DELETE",
        "--maintenance-policy=TERMINATE",
    ]

    # Accelerators
    if target.accelerator_count > 0 and target.accelerator_type:
        cmd.append(f"--accelerator=type={target.accelerator_type},count={target.accelerator_count}")

    # Local NVMe SSD scratch disks
    for _ in range(target.local_ssd_count):
        cmd.append("--local-ssd=interface=NVME")

    # Base Deep Learning VM OS image
    cmd.append(f"--image-family={image_family}")
    cmd.append(f"--image-project={image_project}")
    cmd.append(f"--boot-disk-size={boot_disk_size}")
    cmd.append(f"--boot-disk-type={boot_disk_type}")
    cmd.append("--scopes=cloud-platform")

    if service_account:
        cmd.append(f"--service-account={service_account}")

    # Metadata attributes
    metadata_items = [
        f"model_flavor={target.flavor}",
        f"hf_repo={target.hf_repo}",
        f"tp_size={target.tensor_parallel_size}",
        f"output_bucket={output_gcs_uri}",
    ]
    if run_id is not None or configuration_hash is not None:
        if not re.fullmatch(r"[0-9a-f]{32}", run_id or "") or not re.fullmatch(r"[0-9a-f]{64}", configuration_hash or ""):
            raise ValueError("A valid run ID and configuration hash are required together")
        metadata_items.extend([f"run_id={run_id}", f"configuration_hash={configuration_hash}"])
    if source_bundle:
        metadata_items.extend([
            f"source_bundle_uri={source_bundle['uri']}",
            f"source_bundle_sha256={source_bundle['sha256']}",
            f"source_commit={source_bundle['source_commit']}",
            f"source_verifier_sha256={source_bundle['verifier_sha256']}",
        ])
    if target.extra_vllm_flags:
        metadata_items.append(f"extra_flags={target.extra_vllm_flags}")
    if hf_token:
        metadata_items.append(f"hf_token={hf_token}")

    delimiter = "|~|"
    if any(delimiter in item for item in metadata_items):
        raise ValueError("Metadata contains reserved delimiter")
    cmd.append(f"--metadata=^{delimiter}^{delimiter.join(metadata_items)}")

    # Startup Script file
    startup_path = script_template_path or (ROOT_DIR / "scripts" / "gce_startup_script.sh")
    if startup_path.exists():
        file_metadata = f"startup-script={startup_path}"
        if source_bundle:
            file_metadata += f",source-verifier={ROOT_DIR / 'scripts/source_bundle.py'}"
        cmd.append(f"--metadata-from-file={file_metadata}")

    return cmd


class GCESpotOrchestrator:
    """
    Orchestrates the lifecycle of GCE Ephemeral Spot GPU instances.
    Provides launching, serial console log streaming, GCS result collection,
    and automatic teardown verification.
    """

    def __init__(
        self,
        project_id: str = "secops-demo-env",
        zone: str = "europe-west4-a",
        output_gcs_bucket: str = "gs://secops-demo-env-evals/gce_spot_sweeps",
        hf_token: Optional[str] = None,
        dry_run: bool = False,
        timeout_seconds: int = 3600,
        image_family: str = "ubuntu-2204-lts",
        image_project: str = "ubuntu-os-cloud",
        evidence_dir: Optional[Path] = None,
        source_bundle_uri: Optional[str] = None,
        source_bundle_sha256: Optional[str] = None,
        source_commit: Optional[str] = None,
    ) -> None:
        self.project_id = project_id
        self.zone = zone
        self.output_gcs_bucket = output_gcs_bucket
        self.hf_token = hf_token or os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
        self.dry_run = dry_run
        self.timeout_seconds = timeout_seconds
        self.image_family = image_family
        self.image_project = image_project
        self.active_instance_zone: str = zone
        self.evidence_dir = Path(evidence_dir) if evidence_dir else ROOT_DIR / "logs" / "experiment_runs"
        self.current_run: Optional[Dict[str, Any]] = None
        self.source_bundle = None
        supplied = (source_bundle_uri, source_bundle_sha256, source_commit)
        if any(value is not None for value in supplied):
            if not all(isinstance(value, str) and value for value in supplied):
                raise ValueError("Source bundle URI, SHA-256, and commit are required together")
            if not re.fullmatch(r"gs://[a-z0-9][a-z0-9._-]*/[^\s*?\[\]#]+", source_bundle_uri) or "|~|" in source_bundle_uri:
                raise ValueError("Source bundle URI must name one gs:// object without wildcards")
            if not re.fullmatch(r"[0-9a-f]{64}", source_bundle_sha256):
                raise ValueError("Source bundle SHA-256 must be 64 lowercase hex characters")
            if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
                raise ValueError("Source commit must be a full lowercase Git commit hash")
            self.source_bundle = {"uri": source_bundle_uri, "sha256": source_bundle_sha256,
                                  "source_commit": source_commit}


    def launch_instance(
        self,
        target: GCESpotTarget,
        instance_name: Optional[str] = None,
    ) -> str:
        """
        Launches an ephemeral Spot VM instance for the target model.
        Returns the created instance name.
        """
        base_zone = self.zone
        candidate_zones = [base_zone]
        if "-" in base_zone:
            region = "-".join(base_zone.split("-")[:-1])
            for suffix in ["a", "b", "c"]:
                z = f"{region}-{suffix}"
                if z not in candidate_zones:
                    candidate_zones.append(z)

        last_error = ""
        for zone in candidate_zones:
            configuration = {
                "target": asdict(target), "project_id": self.project_id, "zone": zone,
                "image_family": self.image_family, "image_project": self.image_project,
                "startup_sha256": hashlib.sha256((ROOT_DIR / "scripts/gce_startup_script.sh").read_bytes()).hexdigest(),
                "source_identity": "unverified_mutable_gcs_code",
            }
            if self.source_bundle:
                configuration["source_bundle"] = {
                    **self.source_bundle,
                    "verifier_sha256": hashlib.sha256((ROOT_DIR / "scripts/source_bundle.py").read_bytes()).hexdigest(),
                }
                configuration["source_identity"] = "pinned_bundle_requested"
            run = new_run(configuration, self.output_gcs_bucket, instance_name)
            self.current_run = run
            self.active_instance_zone = zone
            name = run["instance_name"]
            self._save_launch(run)
            cmd = build_gce_spot_create_command(
                target=target,
                project_id=self.project_id,
                zone=zone,
                output_gcs_uri=run["artifact_uri"].rsplit("/", 1)[0],
                hf_token=self.hf_token,
                image_family=self.image_family,
                image_project=self.image_project,
                instance_name=name,
                run_id=run["run_id"], configuration_hash=run["configuration_hash"],
                source_bundle=configuration.get("source_bundle"),
            )

            if self.dry_run:
                run["launch_status"] = "SYNTHETIC"
                print(f"[DRY RUN] Creating GCE Spot instance '{name}' for flavor '{target.flavor}' in zone '{zone}'...")
                safe_cmd = [re.sub(r"hf_token=.*?(?=\|~\||$)", "hf_token=<redacted>", arg) for arg in cmd]
                print(f"[DRY RUN] Command: {' '.join(safe_cmd)}")
                self.active_instance_zone = zone
                return name

            print(f"[INFO] Creating GCE Spot instance '{name}' ({target.machine_type}, {target.accelerator_count}x {target.accelerator_type}) in {zone}...")
            run["launch_status"] = "CREATE_REQUESTED"
            self._save_launch(run)
            try:
                res = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=60)
            except BaseException as exc:
                run["launch_status"] = "CREATE_OUTCOME_UNKNOWN"
                self._save_launch(run)
                if isinstance(exc, Exception):
                    # Subprocess exceptions include argv, which may contain an HF token.
                    raise RuntimeError(f"Create outcome unknown ({type(exc).__name__}); recover using the saved launch manifest") from None
                raise

            stdout = str(res.stdout or "")
            stderr = str(res.stderr or "")
            output = f"{stdout}\n{stderr}"
            output = output.replace(self.hf_token, "<redacted>") if self.hf_token else output
            print(output)

            if res.returncode == 0:
                run["launch_status"] = "LAUNCHED"
                self._save_launch(run)
                print(f"[INFO] Successfully initiated Spot VM: {name} in {zone}")
                self.active_instance_zone = zone
                return name

            last_error = output
            run["launch_status"] = "CREATE_OUTCOME_UNKNOWN"
            self._save_launch(run)
            if "ZONE_RESOURCE_POOL_EXHAUSTED" in output or "not have enough resources" in output:
                run["launch_status"] = "STOCKOUT"
                self._save_launch(run)
                print(f"[WARN] Zone '{zone}' exhausted for {target.machine_type}. Trying next candidate zone...")
                continue
            else:
                break

        raise RuntimeError(f"GCE Spot instance creation failed for {target.flavor} across candidate zones:\n{last_error}")

    def monitor_instance_serial(
        self,
        instance_name: str,
        timeout_seconds: Optional[int] = None,
    ) -> bool:
        """
        Monitors instance execution status and serial output until the instance
        terminates and self-deletes or the timeout is reached.
        """
        max_timeout = timeout_seconds or self.timeout_seconds
        zone = getattr(self, "active_instance_zone", self.zone)
        if self.dry_run:
            print(f"[DRY RUN] Monitoring serial console for instance '{instance_name}' in zone '{zone}' (timeout: {max_timeout}s)...")
            self.last_monitor_outcome = "SYNTHETIC"
            return True

        print(f"[INFO] Monitoring instance '{instance_name}' in zone '{zone}' until self-deletion...")
        start_time = time.monotonic()
        poll_interval = 15

        while (time.monotonic() - start_time) < max_timeout:
            try:
                check_res = subprocess.run(
                    [
                        "gcloud",
                        "compute",
                        "instances",
                        "describe",
                        instance_name,
                        f"--project={self.project_id}",
                        f"--zone={zone}",
                        "--format=value(status)",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=min(60, max(0.01, max_timeout - (time.monotonic() - start_time))),
                )
            except (OSError, subprocess.SubprocessError) as exc:
                self.last_monitor_outcome = "STATE_CHECK_FAILED"
                print(f"[ERROR] Instance status check failed: {type(exc).__name__}")
                return False

            status = check_res.stdout.strip()
            stderr = check_res.stderr

            if check_res.returncode != 0:
                if re.search(r"(?:the resource(?: .*?)? was not found|notfound:.*instances/)", stderr, re.I | re.S):
                    print(f"[INFO] Instance '{instance_name}' is absent after cleanup request.")
                    self.last_monitor_outcome = "ABSENT_OBSERVED"
                    return True
                print(f"[ERROR] Could not verify instance '{instance_name}' state: {stderr.strip()}")
                self.last_monitor_outcome = "STATE_CHECK_FAILED"
                return False

            if not status:
                print(f"[ERROR] Instance '{instance_name}' returned no status; cleanup is unverified.")
                self.last_monitor_outcome = "STATE_UNAVAILABLE"
                return False

            if status in ["TERMINATED", "STOPPED"]:
                print(f"[INFO] Instance '{instance_name}' is in {status} state.")
                self.last_monitor_outcome = f"{status}_NOT_DELETED"
                return True

            elapsed = int(time.monotonic() - start_time)
            print(f"[INFO] Instance '{instance_name}' status: {status} (elapsed: {elapsed}s / {max_timeout}s)...")
            time.sleep(min(poll_interval, max(0, max_timeout - (time.monotonic() - start_time))))

        print(f"[WARNING] Monitoring timed out after {max_timeout}s for instance '{instance_name}'.")
        self.last_monitor_outcome = "TIMED_OUT"
        return False

    def collect_results(
        self,
        target: GCESpotTarget,
        output_dir: Optional[Path] = None,
        run: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Downloads and parses the SOC Tier 1 evaluation and benchmark results JSON
        from Google Cloud Storage.
        """
        if self.dry_run:
            print(f"[DRY RUN] Collecting results for flavor '{target.flavor}' from {self.output_gcs_bucket}...")
            return {
                "flavor": target.flavor,
                "status": "SYNTHETIC",
                "synthetic": True,
                "summary": None,
                "case_results": [],
                "benchmark": None,
                "artifact_collection": {"status": "NOT_REQUESTED", "run_identity_verified": False},
                "error": "Dry run does not execute an evaluator or collect measured artifacts",
            }

        run = run or self.current_run
        if run is not None:
            validate_run(run)
            if target.flavor != run["configuration"]["target"]["flavor"]:
                raise ValueError("Target does not match saved launch")
            return self._collect_run(run, output_dir)

        dest_dir = output_dir or (ROOT_DIR / "docs" / "soc_eval_results")
        dest_dir.mkdir(parents=True, exist_ok=True)
        local_dest = dest_dir / f"gce_spot_{target.flavor}_report.json"
        local_dest.unlink(missing_ok=True)
        gcs_json_uri = f"{self.output_gcs_bucket.rstrip('/')}/{target.flavor}/soc_tier1_eval_results_{target.flavor}.json"

        print(f"[INFO] Fetching evaluation artifacts from '{gcs_json_uri}'...")
        res = subprocess.run(
            ["gcloud", "storage", "cp", gcs_json_uri, str(local_dest)],
            capture_output=True,
            text=True,
            check=False,
        )

        if res.returncode != 0:
            # Fallback to gsutil
            res = subprocess.run(
                ["gsutil", "cp", gcs_json_uri, str(local_dest)],
                capture_output=True,
                text=True,
                check=False,
            )

        collection_error = f"Evaluation results not found in GCS at {gcs_json_uri}"
        if res.returncode == 0 and local_dest.exists():
            try:
                with open(local_dest, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, dict):
                    raise ValueError("evaluation artifact must contain a JSON object")
                data.setdefault("flavor", target.flavor)
                status = _artifact_evaluation_status(data)
                data["status"] = status
                if status in {"FAILED", "ERROR", "TIMED_OUT", "STOCKOUT"}:
                    print(f"[WARN] Evaluation artifact reports status {status}; preserving it.")
                    data["artifact_collection"] = {
                        "status": "COLLECTED",
                        "source_uri": gcs_json_uri,
                        "run_identity_verified": False,
                        "verification_note": "The fixed per-flavor GCS path cannot prove this artifact belongs to the current launch",
                    }
                    return data
                if status == "COMPLETED":
                    data["artifact_collection"] = {
                        "status": "COLLECTED",
                        "source_uri": gcs_json_uri,
                        "run_identity_verified": False,
                        "verification_note": "The fixed per-flavor GCS path cannot prove this artifact belongs to the current launch",
                    }
                    return data
                data["status"] = "UNVERIFIED"
                data["error"] = "Artifact has missing, conflicting, or incomplete evaluation status signals"
                data["artifact_collection"] = {
                    "status": "UNVERIFIED",
                    "source_uri": gcs_json_uri,
                    "run_identity_verified": False,
                }
                return data
            except Exception as e:
                print(f"[ERROR] Failed to parse JSON report at {local_dest}: {e}")
                collection_error = f"Failed to parse evaluation artifact at {local_dest}: {e}"

        return {
            "flavor": target.flavor,
            "status": "FAILED",
            "error": collection_error,
            "artifact_collection": {
                "status": "MISSING_OR_INVALID",
                "source_uri": gcs_json_uri,
                "run_identity_verified": False,
            },
        }

    def _run_dir(self, run):
        return self.evidence_dir / run["run_id"]

    def _save_launch(self, run):
        if not self.dry_run:
            write_json(self._run_dir(run) / "launch.json", run)

    def _download(self, uri, destination):
        """Each transport attempt gets a fresh file; partial copies never get reused."""
        destination.parent.mkdir(parents=True, exist_ok=True)
        errors = []
        for prefix in (["gcloud", "storage", "cp"], ["gsutil", "cp"]):
            with tempfile.TemporaryDirectory(dir=destination.parent) as scratch:
                temporary = Path(scratch) / "download"
                try:
                    response = subprocess.run([*prefix, uri, str(temporary)],
                                              capture_output=True, text=True, check=False, timeout=60)
                    if response.returncode == 0 and temporary.is_file():
                        raw = temporary.read_bytes()
                        temporary.replace(destination)
                        return {"status": "COLLECTED", "source_uri": uri,
                                "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
                    errors.append(f"{prefix[0]} exit {response.returncode}; file present: {temporary.is_file()}")
                except (OSError, subprocess.SubprocessError) as exc:
                    errors.append(f"{prefix[0]}: {type(exc).__name__}")
        return {"status": "MISSING_OR_INVALID", "source_uri": uri, "errors": errors}

    def _collect_run(self, run, output_dir=None):
        # Snapshot directories preserve earlier collection attempts and their diagnostics.
        base = Path(output_dir) if output_dir else self._run_dir(run)
        base.mkdir(parents=True, exist_ok=True)
        snapshot = Path(tempfile.mkdtemp(prefix="collection-", dir=base))
        flavor = run["configuration"]["target"]["flavor"]
        names = {"evaluation": f"soc_tier1_eval_results_{flavor}.json",
                 "lifecycle": "lifecycle_status.json", "logs": f"benchmark_{flavor}.log",
                 "benchmark": "benchmark_sample_output.json"}
        records, artifacts = {}, {}
        for kind, filename in names.items():
            destination = snapshot / filename
            record = self._download(f"{run['artifact_uri']}/{filename}", destination)
            records[kind] = record
            if record["status"] != "COLLECTED":
                continue
            record["local_path"] = str(destination)
            if record["bytes"] == 0:
                record.update(status="REJECTED", error="Artifact is empty")
                continue
            if kind in {"evaluation", "lifecycle", "benchmark"}:
                try:
                    data = json.loads(destination.read_text(), parse_constant=_reject_nonfinite)
                    error = _benchmark_error(data) if kind == "benchmark" else identity_error(data, run)
                    if error:
                        record.update(status="REJECTED", error=error)
                    else:
                        artifacts[kind] = data
                        if kind == "benchmark":
                            record["identity_scope"] = "dedicated_run_path_only"
                        else:
                            record["run_identity_verified"] = True
                except (ValueError, OSError) as exc:
                    record.update(status="REJECTED", error=f"Invalid JSON: {exc}")
            else:
                record["identity_scope"] = "dedicated_run_path_only"

        evaluation = artifacts.get("evaluation")
        lifecycle = artifacts.get("lifecycle")
        data = dict(evaluation) if evaluation else {
            "flavor": flavor, "status": "UNVERIFIED", "summary": None, "case_results": [],
            "error": "Evaluation artifact missing or rejected; see artifact_collection.records",
        }
        data["status"] = _artifact_evaluation_status(data)
        data["evaluation_status"] = data["status"]
        data["launch"] = run
        data["collected_at"] = now()
        data["collection_directory"] = str(snapshot)
        data["artifact_collection"] = {
            "status": "COLLECTED" if evaluation else "MISSING_OR_REJECTED",
            "run_identity_verified": evaluation is not None,
            "lifecycle_identity_verified": lifecycle is not None,
            "identity_scope": "launch_binding_only", "records": records,
        }
        data["startup_lifecycle"] = lifecycle
        expected_source = run["configuration"].get("source_bundle")
        source_verified = False
        if expected_source:
            provenance = (evaluation or {}).get("provenance", {})
            evaluator_source = provenance.get("source_bundle") if isinstance(provenance, dict) else None
            startup_source = (lifecycle or {}).get("source_bundle")
            source_verified = all(
                isinstance(observed, dict) and observed.get("status") == "VERIFIED"
                and observed.get("sha256") == expected_source["sha256"]
                and observed.get("source_commit") == expected_source["source_commit"]
                for observed in (evaluator_source, startup_source)
            )
        data["source_verification"] = {
            "status": "VERIFIED" if source_verified else "UNVERIFIED" if expected_source else "NOT_REQUESTED",
            "scope": "source_bundle_bytes_at_startup", "expected": expected_source,
        }
        # A completed evaluator alone does not prove successful upload, benchmark, or cleanup.
        lifecycle_artifacts = (lifecycle or {}).get("artifacts")
        lifecycle_evaluation = (lifecycle or {}).get("evaluation")
        lifecycle_ok = (lifecycle is not None
                        and isinstance(lifecycle_artifacts, dict)
                        and isinstance(lifecycle_evaluation, dict)
                        and _artifact_evaluation_status(lifecycle) == "COMPLETED"
                        and lifecycle_artifacts.get("upload_status") == "COMMAND_SUCCEEDED"
                        and lifecycle_evaluation.get("benchmark_status") == "COMPLETED")
        data["artifact_evidence_status"] = "COMPLETE" if (
            evaluation and lifecycle_ok and (not expected_source or source_verified)
            and all(r["status"] == "COLLECTED" for r in records.values())
        ) else "PARTIAL"
        data["cleanup"] = {"status": "UNVERIFIED", "resource": {
            "project_id": run["configuration"]["project_id"], "zone": run["configuration"]["zone"],
            "instance_name": run["instance_name"]}}
        data["verification_status"] = "partial_launch_evidence"
        write_json(snapshot / "evidence.json", data)
        write_json(base / "evidence.json", data)
        return data

    def recover_run(self, manifest_path, cleanup=False):
        """Collect and observe an existing launch without creating a resource."""
        run = load_run(manifest_path)
        if run.get("launch_status") in {"SYNTHETIC", "PREPARED", "STOCKOUT"}:
            raise ValueError("Manifest does not describe a possibly created resource")
        if self.dry_run:
            raise ValueError("Recovery requires read-only cloud access; do not combine with dry-run")
        self.current_run = run
        evidence = self._collect_run(run, Path(manifest_path).parent)
        evidence["cleanup"] = self.observe_cleanup(run, request_delete=cleanup)
        write_json(Path(evidence["collection_directory"]) / "evidence.json", evidence)
        write_json(Path(manifest_path).parent / "evidence.json", evidence)
        return evidence

    def observe_cleanup(self, run, request_delete=False):
        """Delete only a VM whose metadata matches the launch, then verify absence."""
        validate_run(run)
        config = run["configuration"]
        resource = {"project_id": config["project_id"], "zone": config["zone"],
                    "instance_name": run["instance_name"]}
        result = {"status": "UNVERIFIED", "resource": resource, "observed_at": now(),
                  "delete_requested": False}
        args = [run["instance_name"], f"--project={config['project_id']}", f"--zone={config['zone']}"]
        try:
            response = subprocess.run(["gcloud", "compute", "instances", "describe", *args, "--format=json"],
                                      capture_output=True, text=True, check=False, timeout=60)
            if response.returncode != 0:
                # Require provider's resource error, not generic 'not found' (e.g. missing account).
                if re.search(r"(?:the resource(?: .*?)? was not found|notfound:.*instances/)", response.stderr, re.I | re.S):
                    result["status"] = "ABSENT_OBSERVED"
                else:
                    result["status"] = "STATE_CHECK_FAILED"
                return result
            instance = json.loads(response.stdout)
            metadata = {item["key"]: item.get("value") for item in instance.get("metadata", {}).get("items", [])}
            result["resource"]["provider_id"] = instance.get("id")
            if metadata.get("run_id") != run["run_id"] or metadata.get("configuration_hash") != run["configuration_hash"]:
                result["status"] = "IDENTITY_MISMATCH"
                return result
            result["status"] = "PRESENT"
            result["instance_status"] = instance.get("status")
            if request_delete:
                result["delete_requested"] = True
                result["delete_command_succeeded"] = None
                deleted = subprocess.run(["gcloud", "compute", "instances", "delete", *args, "--quiet"],
                                         capture_output=True, text=True, check=False, timeout=60)
                observed = self.observe_cleanup(run)
                observed["resource"]["provider_id"] = instance.get("id")
                observed["delete_requested"] = True
                observed["delete_command_succeeded"] = deleted.returncode == 0
                return observed
        except (OSError, ValueError, KeyError, TypeError, AttributeError, subprocess.SubprocessError) as exc:
            result.update(status="DELETE_OUTCOME_UNKNOWN" if result["delete_requested"] else "STATE_CHECK_FAILED",
                          error=type(exc).__name__)
        return result

    def run_sweep(
        self,
        models_filter: Optional[List[str]] = None,
        wait: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Executes the Ephemeral Spot VM sweep across all or filtered targets.
        """
        targets: List[GCESpotTarget] = []
        if models_filter:
            for item in models_filter:
                matched = [t for t in ALL_GCE_SPOT_TARGETS if t.flavor == item]
                if not matched:
                    matched = [t for t in ALL_GCE_SPOT_TARGETS if t.get_base_flavor() == item]
                for m in matched:
                    if m not in targets:
                        targets.append(m)
        else:
            targets = list(ALL_GCE_SPOT_TARGETS)

        print("==================================================================")
        print(" Starting Compute Engine (GCE) Ephemeral Spot GPU Sweep")
        print(f" Total Target Models: {len(targets)}")
        print(f" Project ID:          {self.project_id}")
        print(f" Zone:                {self.zone}")
        print(f" Output GCS Bucket:   {self.output_gcs_bucket}")
        print(f" Mode:                {'DRY RUN' if self.dry_run else 'LIVE SPOT'}")
        print(f" Wait & Collect:      {wait}")
        print("==================================================================")

        results: List[Dict[str, Any]] = []

        for target in targets:
            print(f"\n[Target: {target.flavor}] {target.notes}...")
            self.current_run = None
            try:
                instance_name = self.launch_instance(target)
            except Exception as e:
                print(f"[WARN] Unable to launch Spot instance for {target.flavor}: {e}")
                results.append({
                    "flavor": target.flavor,
                    "status": (self.current_run or {}).get("launch_status", "LAUNCH_FAILED"),
                    "launch": self.current_run,
                    "error": str(e),
                })
                continue

            if not wait:
                results.append({
                    "flavor": target.flavor,
                    "instance_name": instance_name,
                    "status": "SYNTHETIC" if self.dry_run else "LAUNCHED",
                    "launch": self.current_run,
                })
                continue

            try:
                success = self.monitor_instance_serial(instance_name, timeout_seconds=self.timeout_seconds)
                res = self.collect_results(target)
            except BaseException as exc:
                if self.current_run and not self.dry_run:
                    write_json(self._run_dir(self.current_run) / "interruption.json", {
                        "run_id": self.current_run["run_id"], "configuration_hash": self.current_run["configuration_hash"],
                        "status": "INTERRUPTED", "error_type": type(exc).__name__, "at": now(),
                        "cleanup_status": "UNVERIFIED",
                    })
                raise
            res["monitoring"] = {
                "status": getattr(self, "last_monitor_outcome", "UNKNOWN"),
                "completed": success,
            }
            if success and res["monitoring"]["status"] in {"TERMINATED_NOT_DELETED", "STOPPED_NOT_DELETED"}:
                res["evaluation_status"] = res.get("status")
                res["cleanup_status"] = "UNVERIFIED"
                res["monitoring"]["error"] = "Instance reached a terminal state but absence was not verified"
                if res.get("status") not in {"FAILED", "ERROR", "TIMED_OUT", "STOCKOUT"}:
                    res["status"] = "CLEANUP_UNVERIFIED"
            if not success:
                monitor_status = res["monitoring"]["status"]
                if monitor_status == "TIMED_OUT":
                    res["monitoring"]["error"] = f"Instance did not reach a verified terminal state within {self.timeout_seconds}s"
                else:
                    res["monitoring"]["error"] = "Instance state could not be verified because the status check failed"
                if res.get("status") not in {"FAILED", "ERROR", "TIMED_OUT", "STOCKOUT"}:
                    res["status"] = "TIMED_OUT" if monitor_status == "TIMED_OUT" else "MONITORING_FAILED"
            if self.current_run and not self.dry_run:
                res["cleanup"] = self.observe_cleanup(self.current_run)
                res["cleanup_status"] = res["cleanup"]["status"]
                write_json(Path(res["collection_directory"]) / "evidence.json", res)
                write_json(self._run_dir(self.current_run) / "evidence.json", res)
            results.append(res)

        print("\n==================================================================")
        print(" GCE Ephemeral Spot Sweep Completed")
        print(f" Processed: {len(results)} models")
        print("==================================================================")
        return results


def main() -> int:
    """CLI Entrypoint for GCE Spot sweep orchestration."""
    parser = argparse.ArgumentParser(description="GCE Ephemeral Spot GPU Sweep Orchestrator")
    parser.add_argument(
        "--models",
        default=None,
        help="Comma-separated model flavors or base names to include in sweep (e.g. gemma-2-2b-it,gemma-3-4b-it)",
    )
    parser.add_argument(
        "--project-id",
        default=os.environ.get("GCP_PROJECT_ID", "secops-demo-env"),
        help="Google Cloud Project ID",
    )
    parser.add_argument(
        "--zone",
        default=os.environ.get("GCP_ZONE", "europe-west4-a"),
        help="Compute Engine Zone (e.g. europe-west4-a, us-central1-a)",
    )
    parser.add_argument(
        "--output-gcs-bucket",
        "--output-bucket",
        dest="output_gcs_bucket",
        default=os.environ.get("GCE_SPOT_OUTPUT_BUCKET", "gs://secops-demo-env-evals/gce_spot_sweeps"),
        help="Target Google Cloud Storage bucket for test artifacts",
    )
    parser.add_argument(
        "--hf-token",
        default=None,
        help="HuggingFace API token for gated model weight access",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Simulate commands and workflows without provisioning GCE resources",
    )
    parser.add_argument(
        "--no-wait",
        action="store_true",
        default=False,
        help="Launch Spot instances asynchronously without waiting for completion",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=3600,
        help="Maximum duration in seconds to wait per Spot VM instance",
    )
    parser.add_argument("--evidence-dir", type=Path, default=None,
                        help="Local launch records and evidence (default: logs/experiment_runs)")
    parser.add_argument("--recover", type=Path, default=None,
                        help="Saved launch.json to collect and inspect; never creates a VM")
    parser.add_argument("--cleanup", action="store_true",
                        help="With --recover, request deletion only after checking VM run metadata")
    parser.add_argument("--source-bundle-uri", help="Exact GCS object containing the committed source bundle")
    parser.add_argument("--source-bundle-sha256", help="Expected SHA-256 of the source archive")
    parser.add_argument("--source-commit", help="Full source commit recorded in the bundle manifest")
    args = parser.parse_args()
    if not args.recover:
        # Existing Just recipes inherit these pins without changing their arguments.
        args.source_bundle_uri = args.source_bundle_uri or os.environ.get("GCE_SOURCE_BUNDLE_URI")
        args.source_bundle_sha256 = args.source_bundle_sha256 or os.environ.get("GCE_SOURCE_BUNDLE_SHA256")
        args.source_commit = args.source_commit or os.environ.get("GCE_SOURCE_COMMIT")
    if not args.recover and not args.dry_run and not all(
        (args.source_bundle_uri, args.source_bundle_sha256, args.source_commit)
    ):
        parser.error("Live launches require --source-bundle-uri, --source-bundle-sha256, and --source-commit")
    if args.recover and any((args.source_bundle_uri, args.source_bundle_sha256, args.source_commit)):
        parser.error("Recovery uses the saved source identity; source overrides are not allowed")
    if args.cleanup and not args.recover:
        parser.error("--cleanup requires --recover")
    if args.recover and (args.models or args.no_wait or args.dry_run):
        parser.error("--recover cannot be combined with --models, --no-wait, or --dry-run")

    models_filter = [m.strip() for m in args.models.split(",") if m.strip()] if args.models else None

    orchestrator = GCESpotOrchestrator(
        project_id=args.project_id,
        zone=args.zone,
        output_gcs_bucket=args.output_gcs_bucket,
        hf_token=args.hf_token,
        dry_run=args.dry_run,
        timeout_seconds=args.timeout_seconds,
        evidence_dir=args.evidence_dir,
        source_bundle_uri=args.source_bundle_uri,
        source_bundle_sha256=args.source_bundle_sha256,
        source_commit=args.source_commit,
    )

    if args.recover:
        result = orchestrator.recover_run(args.recover, cleanup=args.cleanup)
        print(json.dumps(result, indent=2))
        return 0 if (result.get("evaluation_status") == "COMPLETED"
                     and result.get("artifact_evidence_status") == "COMPLETE"
                     and result["cleanup"]["status"] == "ABSENT_OBSERVED") else 1

    results = orchestrator.run_sweep(
        models_filter=models_filter,
        wait=not args.no_wait,
    )

    return 0 if results and all(
        item.get("status") in {"SYNTHETIC", "LAUNCHED"} or (
            item.get("evaluation_status") == "COMPLETED"
            and item.get("artifact_evidence_status") == "COMPLETE"
            and item.get("cleanup", {}).get("status") == "ABSENT_OBSERVED"
        ) for item in results
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
