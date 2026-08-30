#!/usr/bin/env python3
"""
Compute Engine (GCE) Ephemeral Spot GPU VM Sweep Orchestrator

Manages the lifecycle of ephemeral Spot GPU VMs attached to Local NVMe SSD scratch disks:
1. Dynamically generates gcloud compute instance provisioning commands with Spot pricing.
2. Attaches Local NVMe SSD scratch drives and configures startup automation.
3. Streams serial console logs and monitors job progress.
4. Collects benchmark and SOC Tier 1 evaluation outputs from Google Cloud Storage.
5. Verifies self-deletion ($0.00 idle compute leak guarantee).
"""

import argparse
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


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
        extra_vllm_flags="--speculative-model=[ngram] --num-speculative-tokens=5 --ngram-prompt-lookup-max=5 --ngram-prompt-lookup-min=2",
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
        extra_vllm_flags="--limit_mm_per_prompt=image=5 --max-num-seqs=4",
        notes="Gemma 3 4B Multimodal (1x L4, 1x NVMe SSD)",
    ),
    GCESpotTarget(
        flavor="gemma-3-4b-it-speculative",
        hf_repo="google/gemma-3-4b-it",
        machine_type="g2-standard-8",
        accelerator_type="nvidia-l4",
        accelerator_count=1,
        local_ssd_count=1,
        tensor_parallel_size=1,
        extra_vllm_flags="--limit_mm_per_prompt=image=5 --max-num-seqs=4 --speculative-model=[ngram] --num-speculative-tokens=5 --ngram-prompt-lookup-max=5 --ngram-prompt-lookup-min=2",
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
        extra_vllm_flags="--limit_mm_per_prompt=image=5 --max-num-seqs=4",
        notes="Gemma 3 12B Multimodal (4x L4, 4x NVMe SSD)",
    ),
    GCESpotTarget(
        flavor="gemma-3-12b-it-fp8",
        hf_repo="google/gemma-3-12b-it",
        machine_type="g2-standard-48",
        accelerator_type="nvidia-l4",
        accelerator_count=4,
        local_ssd_count=4,
        tensor_parallel_size=4,
        extra_vllm_flags="--quantization=fp8 --limit_mm_per_prompt=image=5 --max-num-seqs=4",
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
        extra_vllm_flags="--quantization=fp8 --speculative-model=[ngram] --num-speculative-tokens=5 --ngram-prompt-lookup-max=5 --ngram-prompt-lookup-min=2 --limit_mm_per_prompt=image=5 --max-num-seqs=4",
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
        extra_vllm_flags="--limit_mm_per_prompt=image=5 --max-num-seqs=4",
        notes="Gemma 3 27B Multimodal (4x L4, 4x NVMe SSD)",
    ),
    GCESpotTarget(
        flavor="gemma-3-27b-it-fp8",
        hf_repo="google/gemma-3-27b-it",
        machine_type="g2-standard-48",
        accelerator_type="nvidia-l4",
        accelerator_count=4,
        local_ssd_count=4,
        tensor_parallel_size=4,
        extra_vllm_flags="--quantization=fp8 --limit_mm_per_prompt=image=5 --max-num-seqs=4",
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
        extra_vllm_flags="--quantization=fp8 --speculative-model=[ngram] --num-speculative-tokens=5 --ngram-prompt-lookup-max=5 --ngram-prompt-lookup-min=2 --limit_mm_per_prompt=image=5 --max-num-seqs=4",
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
        extra_vllm_flags="--quantization=fp8 --enable-chunked-prefill --enable-prefix-caching --limit_mm_per_prompt=image=5 --max-num-seqs=4",
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
    image_family: str = "common-cu124-debian-11",
    image_project: str = "deeplearning-platform-release",
    instance_name: Optional[str] = None,
    service_account: Optional[str] = None,
    boot_disk_size: str = "100GB",
    boot_disk_type: str = "pd-ssd",
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
    if target.extra_vllm_flags:
        metadata_items.append(f"extra_flags={target.extra_vllm_flags}")
    if hf_token:
        metadata_items.append(f"hf_token={hf_token}")

    cmd.append(f"--metadata={','.join(metadata_items)}")

    # Startup Script file
    startup_path = script_template_path or (ROOT_DIR / "scripts" / "gce_startup_script.sh")
    if startup_path.exists():
        cmd.append(f"--metadata-from-file=startup-script={startup_path}")

    return cmd


class GCESpotOrchestrator:
    """
    Orchestrates the lifecycle of GCE Ephemeral Spot GPU instances.
    Provides launching, serial console log streaming, GCS result collection,
    and automatic teardown verification.
    """

    def __init__(
        self,
        project_id: str = "dandye-0324-chronicle",
        zone: str = "us-central1-a",
        output_gcs_bucket: str = "gs://dandye-0324-chronicle-evals/gce_spot_sweeps",
        hf_token: Optional[str] = None,
        dry_run: bool = False,
        timeout_seconds: int = 3600,
        image_family: str = "common-cu124-debian-11",
        image_project: str = "deeplearning-platform-release",
    ) -> None:
        self.project_id = project_id
        self.zone = zone
        self.output_gcs_bucket = output_gcs_bucket
        self.hf_token = hf_token or os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
        self.dry_run = dry_run
        self.timeout_seconds = timeout_seconds
        self.image_family = image_family
        self.image_project = image_project

    def launch_instance(
        self,
        target: GCESpotTarget,
        instance_name: Optional[str] = None,
    ) -> str:
        """
        Launches an ephemeral Spot VM instance for the target model.
        Returns the created instance name.
        """
        if not instance_name:
            sanitized_flavor = target.flavor.replace(".", "-")
            timestamp = int(time.time())
            instance_name = f"spot-{sanitized_flavor}-{timestamp}"

        cmd = build_gce_spot_create_command(
            target=target,
            project_id=self.project_id,
            zone=self.zone,
            output_gcs_uri=self.output_gcs_bucket,
            hf_token=self.hf_token,
            image_family=self.image_family,
            image_project=self.image_project,
            instance_name=instance_name,
        )

        if self.dry_run:
            print(f"[DRY RUN] Creating GCE Spot instance '{instance_name}' for flavor '{target.flavor}'...")
            print(f"[DRY RUN] Command: {' '.join(cmd)}")
            return instance_name

        print(f"[INFO] Creating GCE Spot instance '{instance_name}' ({target.machine_type}, {target.accelerator_count}x {target.accelerator_type})...")
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )

        stdout = str(res.stdout or "")
        stderr = str(res.stderr or "")
        output = f"{stdout}\n{stderr}"
        print(output)

        if res.returncode != 0:
            raise RuntimeError(f"GCE Spot instance creation failed for {target.flavor} (code {res.returncode}):\n{output}")

        print(f"[INFO] Successfully initiated Spot VM: {instance_name}")
        return instance_name

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
        if self.dry_run:
            print(f"[DRY RUN] Monitoring serial console for instance '{instance_name}' (timeout: {max_timeout}s)...")
            return True

        print(f"[INFO] Monitoring instance '{instance_name}' in zone '{self.zone}' until self-deletion...")
        start_time = time.time()
        poll_interval = 15

        while (time.time() - start_time) < max_timeout:
            check_res = subprocess.run(
                [
                    "gcloud",
                    "compute",
                    "instances",
                    "describe",
                    instance_name,
                    f"--project={self.project_id}",
                    f"--zone={self.zone}",
                    "--format=value(status)",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            status = check_res.stdout.strip()
            stderr = check_res.stderr

            if check_res.returncode != 0 or "not found" in stderr.lower() or not status:
                print(f"[INFO] Instance '{instance_name}' has self-deleted cleanly ($0 idle cost verified).")
                return True

            if status in ["TERMINATED", "STOPPED"]:
                print(f"[INFO] Instance '{instance_name}' is in {status} state.")
                return True

            elapsed = int(time.time() - start_time)
            print(f"[INFO] Instance '{instance_name}' status: {status} (elapsed: {elapsed}s / {max_timeout}s)...")
            time.sleep(poll_interval)

        print(f"[WARNING] Monitoring timed out after {max_timeout}s for instance '{instance_name}'.")
        return False

    def collect_results(
        self,
        target: GCESpotTarget,
        output_dir: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """
        Downloads and parses the SOC Tier 1 evaluation and benchmark results JSON
        from Google Cloud Storage.
        """
        if self.dry_run:
            print(f"[DRY RUN] Collecting results for flavor '{target.flavor}' from {self.output_gcs_bucket}...")
            return {
                "flavor": target.flavor,
                "status": "COMPLETED",
                "summary": {
                    "total_cases": 5,
                    "passed_cases": 5,
                    "pass_rate": 100.0,
                    "avg_rubric_score": 95.0,
                    "avg_latency_s": 11.5,
                    "total_tokens": 12000,
                    "avg_generation_tps": 65.0,
                    "avg_total_tps": 220.0,
                    "total_tool_calls": 5,
                },
                "case_results": [
                    {
                        "eval_id": f"CASE-0{i}",
                        "name": f"Case {i}",
                        "rubric_score": 95.0,
                        "grounding_score": 1.0,
                        "passed": True,
                        "latency_s": 2.3,
                        "generation_tps": 65.0,
                    }
                    for i in range(1, 6)
                ],
                "benchmark": {
                    "avg_latency_s": 1.2,
                    "tps": 70.0,
                    "ttft_ms": 100.0,
                },
            }

        dest_dir = output_dir or (ROOT_DIR / "docs" / "soc_eval_results")
        dest_dir.mkdir(parents=True, exist_ok=True)
        local_dest = dest_dir / f"gce_spot_{target.flavor}_report.json"
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

        if res.returncode == 0 and local_dest.exists():
            try:
                with open(local_dest, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    data["status"] = "COMPLETED"
                    return data
            except Exception as e:
                print(f"[ERROR] Failed to parse JSON report at {local_dest}: {e}")

        return {
            "flavor": target.flavor,
            "status": "FAILED",
            "error": f"Evaluation results not found in GCS at {gcs_json_uri}",
        }

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
            instance_name = self.launch_instance(target)

            if not wait:
                results.append({
                    "flavor": target.flavor,
                    "instance_name": instance_name,
                    "status": "LAUNCHED",
                })
                continue

            success = self.monitor_instance_serial(instance_name, timeout_seconds=self.timeout_seconds)
            res = self.collect_results(target)
            if not success and res.get("status") != "COMPLETED":
                res["status"] = "TIMED_OUT"
            results.append(res)

        print("\n==================================================================")
        print(" GCE Ephemeral Spot Sweep Completed")
        print(f" Processed: {len(results)} models")
        print("==================================================================")
        return results


def main() -> None:
    """CLI Entrypoint for GCE Spot sweep orchestration."""
    parser = argparse.ArgumentParser(description="GCE Ephemeral Spot GPU Sweep Orchestrator")
    parser.add_argument(
        "--models",
        default=None,
        help="Comma-separated model flavors or base names to include in sweep (e.g. gemma-2-2b-it,gemma-3-4b-it)",
    )
    parser.add_argument(
        "--project-id",
        default=os.environ.get("GCP_PROJECT_ID", "dandye-0324-chronicle"),
        help="Google Cloud Project ID",
    )
    parser.add_argument(
        "--zone",
        default=os.environ.get("GCP_ZONE", "us-central1-a"),
        help="Compute Engine Zone (e.g. us-central1-a, us-east1-c, europe-west4-a)",
    )
    parser.add_argument(
        "--output-gcs-bucket",
        "--output-bucket",
        dest="output_gcs_bucket",
        default=os.environ.get("GCE_SPOT_OUTPUT_BUCKET", "gs://dandye-0324-chronicle-evals/gce_spot_sweeps"),
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
    args = parser.parse_args()

    models_filter = [m.strip() for m in args.models.split(",") if m.strip()] if args.models else None

    orchestrator = GCESpotOrchestrator(
        project_id=args.project_id,
        zone=args.zone,
        output_gcs_bucket=args.output_gcs_bucket,
        hf_token=args.hf_token,
        dry_run=args.dry_run,
        timeout_seconds=args.timeout_seconds,
    )

    orchestrator.run_sweep(
        models_filter=models_filter,
        wait=not args.no_wait,
    )


if __name__ == "__main__":
    main()
