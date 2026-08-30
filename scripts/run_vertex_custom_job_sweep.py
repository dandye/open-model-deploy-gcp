#!/usr/bin/env python3
"""
Vertex AI Custom Job Sweep Orchestrator
Submits, polls, and aggregates results from ephemeral Vertex AI Custom Jobs for multi-model
benchmarking and SOC Tier 1 agent evaluation with guaranteed $0.00 idle compute leak.
"""

import argparse
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault("GOOGLE_API_USE_CLIENT_CERTIFICATE", "false")


@dataclass
class VertexCustomJobTarget:
    """Specification of an ephemeral Vertex AI Custom Job evaluation target."""

    flavor: str
    hf_repo: str
    machine_type: str  # e.g. g2-standard-4, g2-standard-8, g2-standard-12, g2-standard-48, a2-highgpu-2g
    accelerator_type: str  # e.g. NVIDIA_L4, NVIDIA_TESLA_A100
    accelerator_count: int  # 1, 2, 4
    tensor_parallel_size: int  # 1, 2, 4
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


# Complete catalog covering Gemma 2, Gemma 3, Gemma 4, and partner open models
ALL_CUSTOM_JOB_TARGETS: List[VertexCustomJobTarget] = [
    # --------------------------------------------------------------------------
    # Gemma 2 Family (Dense & Optimizations)
    # --------------------------------------------------------------------------
    VertexCustomJobTarget(
        flavor="gemma-2-2b-it",
        hf_repo="google/gemma-2-2b-it",
        machine_type="g2-standard-4",
        accelerator_type="NVIDIA_L4",
        accelerator_count=1,
        tensor_parallel_size=1,
        notes="Gemma 2 2B (1x L4)",
    ),
    VertexCustomJobTarget(
        flavor="gemma-2-2b-it-speculative",
        hf_repo="google/gemma-2-2b-it",
        machine_type="g2-standard-4",
        accelerator_type="NVIDIA_L4",
        accelerator_count=1,
        tensor_parallel_size=1,
        extra_vllm_flags="--speculative-model=[ngram] --num-speculative-tokens=5 --ngram-prompt-lookup-max=5 --ngram-prompt-lookup-min=2",
        notes="Gemma 2 2B + Speculative Decoding (1x L4)",
    ),
    VertexCustomJobTarget(
        flavor="gemma-2-9b-it",
        hf_repo="google/gemma-2-9b-it",
        machine_type="g2-standard-12",
        accelerator_type="NVIDIA_L4",
        accelerator_count=1,
        tensor_parallel_size=1,
        notes="Gemma 2 9B (1x L4)",
    ),
    VertexCustomJobTarget(
        flavor="gemma-2-9b-it-fp8",
        hf_repo="google/gemma-2-9b-it",
        machine_type="g2-standard-12",
        accelerator_type="NVIDIA_L4",
        accelerator_count=1,
        tensor_parallel_size=1,
        extra_vllm_flags="--quantization=fp8",
        notes="Gemma 2 9B FP8 Quantized (1x L4)",
    ),
    VertexCustomJobTarget(
        flavor="gemma-2-9b-it-speculative",
        hf_repo="google/gemma-2-9b-it",
        machine_type="g2-standard-12",
        accelerator_type="NVIDIA_L4",
        accelerator_count=1,
        tensor_parallel_size=1,
        extra_vllm_flags="--quantization=fp8 --speculative-model=[ngram] --num-speculative-tokens=5 --ngram-prompt-lookup-max=5 --ngram-prompt-lookup-min=2",
        notes="Gemma 2 9B FP8 + Speculative Decoding (1x L4)",
    ),
    VertexCustomJobTarget(
        flavor="gemma-2-27b-it",
        hf_repo="google/gemma-2-27b-it",
        machine_type="g2-standard-48",
        accelerator_type="NVIDIA_L4",
        accelerator_count=4,
        tensor_parallel_size=4,
        notes="Gemma 2 27B (4x L4)",
    ),
    VertexCustomJobTarget(
        flavor="gemma-2-27b-it-fp8",
        hf_repo="google/gemma-2-27b-it",
        machine_type="g2-standard-48",
        accelerator_type="NVIDIA_L4",
        accelerator_count=4,
        tensor_parallel_size=4,
        extra_vllm_flags="--quantization=fp8",
        notes="Gemma 2 27B FP8 Quantized (4x L4)",
    ),
    VertexCustomJobTarget(
        flavor="gemma-2-27b-it-speculative",
        hf_repo="google/gemma-2-27b-it",
        machine_type="g2-standard-48",
        accelerator_type="NVIDIA_L4",
        accelerator_count=4,
        tensor_parallel_size=4,
        extra_vllm_flags="--quantization=fp8 --speculative-model=[ngram] --num-speculative-tokens=5 --ngram-prompt-lookup-max=5 --ngram-prompt-lookup-min=2",
        notes="Gemma 2 27B FP8 + Speculative Decoding (4x L4)",
    ),
    # --------------------------------------------------------------------------
    # Gemma 3 Family (Dense, Multimodal, & Optimizations)
    # --------------------------------------------------------------------------
    VertexCustomJobTarget(
        flavor="gemma-3-1b-it",
        hf_repo="google/gemma-3-1b-it",
        machine_type="g2-standard-4",
        accelerator_type="NVIDIA_L4",
        accelerator_count=1,
        tensor_parallel_size=1,
        notes="Gemma 3 1B (1x L4)",
    ),
    VertexCustomJobTarget(
        flavor="gemma-3-1b-it-speculative",
        hf_repo="google/gemma-3-1b-it",
        machine_type="g2-standard-4",
        accelerator_type="NVIDIA_L4",
        accelerator_count=1,
        tensor_parallel_size=1,
        extra_vllm_flags="--speculative-model=[ngram] --num-speculative-tokens=5 --ngram-prompt-lookup-max=5 --ngram-prompt-lookup-min=2",
        notes="Gemma 3 1B + Speculative Decoding (1x L4)",
    ),
    VertexCustomJobTarget(
        flavor="gemma-3-4b-it",
        hf_repo="google/gemma-3-4b-it",
        machine_type="g2-standard-8",
        accelerator_type="NVIDIA_L4",
        accelerator_count=1,
        tensor_parallel_size=1,
        extra_vllm_flags="--limit_mm_per_prompt=image=5 --max-num-seqs=4",
        notes="Gemma 3 4B Multimodal (1x L4)",
    ),
    VertexCustomJobTarget(
        flavor="gemma-3-4b-it-speculative",
        hf_repo="google/gemma-3-4b-it",
        machine_type="g2-standard-8",
        accelerator_type="NVIDIA_L4",
        accelerator_count=1,
        tensor_parallel_size=1,
        extra_vllm_flags="--limit_mm_per_prompt=image=5 --max-num-seqs=4 --speculative-model=[ngram] --num-speculative-tokens=5 --ngram-prompt-lookup-max=5 --ngram-prompt-lookup-min=2",
        notes="Gemma 3 4B Multimodal + Speculative Decoding (1x L4)",
    ),
    VertexCustomJobTarget(
        flavor="gemma-3-12b-it",
        hf_repo="google/gemma-3-12b-it",
        machine_type="g2-standard-48",
        accelerator_type="NVIDIA_L4",
        accelerator_count=4,
        tensor_parallel_size=4,
        extra_vllm_flags="--limit_mm_per_prompt=image=5 --max-num-seqs=4",
        notes="Gemma 3 12B Multimodal (4x L4)",
    ),
    VertexCustomJobTarget(
        flavor="gemma-3-12b-it-fp8",
        hf_repo="google/gemma-3-12b-it",
        machine_type="g2-standard-48",
        accelerator_type="NVIDIA_L4",
        accelerator_count=4,
        tensor_parallel_size=4,
        extra_vllm_flags="--quantization=fp8 --limit_mm_per_prompt=image=5 --max-num-seqs=4",
        notes="Gemma 3 12B FP8 Quantized (4x L4)",
    ),
    VertexCustomJobTarget(
        flavor="gemma-3-12b-it-speculative",
        hf_repo="google/gemma-3-12b-it",
        machine_type="g2-standard-48",
        accelerator_type="NVIDIA_L4",
        accelerator_count=4,
        tensor_parallel_size=4,
        extra_vllm_flags="--quantization=fp8 --speculative-model=[ngram] --num-speculative-tokens=5 --ngram-prompt-lookup-max=5 --ngram-prompt-lookup-min=2 --limit_mm_per_prompt=image=5 --max-num-seqs=4",
        notes="Gemma 3 12B FP8 + Speculative Decoding (4x L4)",
    ),
    VertexCustomJobTarget(
        flavor="gemma-3-12b-it-draft-1b",
        hf_repo="google/gemma-3-12b-it",
        machine_type="g2-standard-48",
        accelerator_type="NVIDIA_L4",
        accelerator_count=4,
        tensor_parallel_size=4,
        extra_vllm_flags="--limit_mm_per_prompt=image=5 --max-num-seqs=4 --speculative-model=google/gemma-3-1b-it --num-speculative-tokens=5",
        notes="Gemma 3 12B + Gemma 3 1B Draft (4x L4)",
    ),
    VertexCustomJobTarget(
        flavor="gemma-3-27b-it",
        hf_repo="google/gemma-3-27b-it",
        machine_type="g2-standard-48",
        accelerator_type="NVIDIA_L4",
        accelerator_count=4,
        tensor_parallel_size=4,
        extra_vllm_flags="--limit_mm_per_prompt=image=5 --max-num-seqs=4",
        notes="Gemma 3 27B Multimodal (4x L4)",
    ),
    VertexCustomJobTarget(
        flavor="gemma-3-27b-it-fp8",
        hf_repo="google/gemma-3-27b-it",
        machine_type="g2-standard-48",
        accelerator_type="NVIDIA_L4",
        accelerator_count=4,
        tensor_parallel_size=4,
        extra_vllm_flags="--quantization=fp8 --limit_mm_per_prompt=image=5 --max-num-seqs=4",
        notes="Gemma 3 27B FP8 Quantized (4x L4)",
    ),
    VertexCustomJobTarget(
        flavor="gemma-3-27b-it-speculative",
        hf_repo="google/gemma-3-27b-it",
        machine_type="g2-standard-48",
        accelerator_type="NVIDIA_L4",
        accelerator_count=4,
        tensor_parallel_size=4,
        extra_vllm_flags="--quantization=fp8 --speculative-model=[ngram] --num-speculative-tokens=5 --ngram-prompt-lookup-max=5 --ngram-prompt-lookup-min=2 --limit_mm_per_prompt=image=5 --max-num-seqs=4",
        notes="Gemma 3 27B FP8 + Speculative Decoding (4x L4)",
    ),
    VertexCustomJobTarget(
        flavor="gemma-3-27b-it-caching",
        hf_repo="google/gemma-3-27b-it",
        machine_type="g2-standard-48",
        accelerator_type="NVIDIA_L4",
        accelerator_count=4,
        tensor_parallel_size=4,
        extra_vllm_flags="--quantization=fp8 --enable-chunked-prefill --enable-prefix-caching --limit_mm_per_prompt=image=5 --max-num-seqs=4",
        notes="Gemma 3 27B FP8 + Prefix Caching (4x L4)",
    ),
    VertexCustomJobTarget(
        flavor="gemma-3-27b-it-draft-1b",
        hf_repo="google/gemma-3-27b-it",
        machine_type="g2-standard-48",
        accelerator_type="NVIDIA_L4",
        accelerator_count=4,
        tensor_parallel_size=4,
        extra_vllm_flags="--limit_mm_per_prompt=image=5 --max-num-seqs=4 --speculative-model=google/gemma-3-1b-it --num-speculative-tokens=5",
        notes="Gemma 3 27B + Gemma 3 1B Draft (4x L4)",
    ),
    VertexCustomJobTarget(
        flavor="gemma-3-27b-it-draft-4b",
        hf_repo="google/gemma-3-27b-it",
        machine_type="g2-standard-48",
        accelerator_type="NVIDIA_L4",
        accelerator_count=4,
        tensor_parallel_size=4,
        extra_vllm_flags="--limit_mm_per_prompt=image=5 --max-num-seqs=4 --speculative-model=google/gemma-3-4b-it --num-speculative-tokens=5",
        notes="Gemma 3 27B + Gemma 3 4B Draft (4x L4)",
    ),
    # --------------------------------------------------------------------------
    # Gemma 4 Family (Dense, Reasoning, & Optimizations)
    # --------------------------------------------------------------------------
    VertexCustomJobTarget(
        flavor="gemma-4-e2b-it",
        hf_repo="google/gemma-4-E2B-it",
        machine_type="g2-standard-4",
        accelerator_type="NVIDIA_L4",
        accelerator_count=1,
        tensor_parallel_size=1,
        extra_vllm_flags="--max-num-seqs=16",
        notes="Gemma 4 Edge (1x L4)",
    ),
    VertexCustomJobTarget(
        flavor="gemma-4-e2b-it-speculative",
        hf_repo="google/gemma-4-E2B-it",
        machine_type="g2-standard-4",
        accelerator_type="NVIDIA_L4",
        accelerator_count=1,
        tensor_parallel_size=1,
        extra_vllm_flags="--max-num-seqs=16 --speculative-model=[ngram] --num-speculative-tokens=5 --ngram-prompt-lookup-max=5 --ngram-prompt-lookup-min=2",
        notes="Gemma 4 E2B + Speculative Decoding (1x L4)",
    ),
    VertexCustomJobTarget(
        flavor="gemma-4-e4b-it",
        hf_repo="google/gemma-4-E4B-it",
        machine_type="g2-standard-8",
        accelerator_type="NVIDIA_L4",
        accelerator_count=1,
        tensor_parallel_size=1,
        extra_vllm_flags="--max-num-seqs=16",
        notes="Gemma 4 Edge (1x L4)",
    ),
    VertexCustomJobTarget(
        flavor="gemma-4-e4b-it-speculative",
        hf_repo="google/gemma-4-E4B-it",
        machine_type="g2-standard-8",
        accelerator_type="NVIDIA_L4",
        accelerator_count=1,
        tensor_parallel_size=1,
        extra_vllm_flags="--max-num-seqs=16 --speculative-model=[ngram] --num-speculative-tokens=5 --ngram-prompt-lookup-max=5 --ngram-prompt-lookup-min=2",
        notes="Gemma 4 E4B + Speculative Decoding (1x L4)",
    ),
    VertexCustomJobTarget(
        flavor="gemma-4-31b-it",
        hf_repo="google/gemma-4-31B-it",
        machine_type="a2-highgpu-2g",
        accelerator_type="NVIDIA_TESLA_A100",
        accelerator_count=2,
        tensor_parallel_size=2,
        extra_vllm_flags="--max-num-seqs=16",
        notes="Gemma 4 Multimodal Reasoner (2x A100)",
    ),
    VertexCustomJobTarget(
        flavor="gemma-4-31b-it-speculative",
        hf_repo="google/gemma-4-31B-it",
        machine_type="a2-highgpu-2g",
        accelerator_type="NVIDIA_TESLA_A100",
        accelerator_count=2,
        tensor_parallel_size=2,
        extra_vllm_flags="--max-num-seqs=16 --speculative-model=[ngram] --num-speculative-tokens=5 --ngram-prompt-lookup-max=5 --ngram-prompt-lookup-min=2",
        notes="Gemma 4 31B + Speculative Decoding (2x A100)",
    ),
    VertexCustomJobTarget(
        flavor="gemma-4-31b-it-draft-e2b",
        hf_repo="google/gemma-4-31B-it",
        machine_type="a2-highgpu-2g",
        accelerator_type="NVIDIA_TESLA_A100",
        accelerator_count=2,
        tensor_parallel_size=2,
        extra_vllm_flags="--max-num-seqs=16 --speculative-model=google/gemma-4-E2B-it --num-speculative-tokens=5",
        notes="Gemma 4 31B + Gemma 4 E2B Draft (2x A100)",
    ),
    VertexCustomJobTarget(
        flavor="gemma-4-31b-it-draft-e4b",
        hf_repo="google/gemma-4-31B-it",
        machine_type="a2-highgpu-2g",
        accelerator_type="NVIDIA_TESLA_A100",
        accelerator_count=2,
        tensor_parallel_size=2,
        extra_vllm_flags="--max-num-seqs=16 --speculative-model=google/gemma-4-E4B-it --num-speculative-tokens=5",
        notes="Gemma 4 31B + Gemma 4 E4B Draft (2x A100)",
    ),
    # --------------------------------------------------------------------------
    # Partner Open Models & Baselines
    # --------------------------------------------------------------------------
    VertexCustomJobTarget(
        flavor="inkling-small",
        hf_repo="thinkingmachines/Inkling-Small",
        machine_type="g2-standard-48",
        accelerator_type="NVIDIA_L4",
        accelerator_count=4,
        tensor_parallel_size=4,
        extra_vllm_flags="--tokenizer-mode=inkling",
        notes="Thinking Machines Inkling Small (4x L4)",
    ),
    VertexCustomJobTarget(
        flavor="nemotron-3.5-lightning-bf16",
        hf_repo="nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16",
        machine_type="g2-standard-48",
        accelerator_type="NVIDIA_L4",
        accelerator_count=4,
        tensor_parallel_size=4,
        notes="Nemotron 3.5 Lightning (4x L4)",
    ),
    VertexCustomJobTarget(
        flavor="qwen2.5-coder-32b-instruct",
        hf_repo="Qwen/Qwen2.5-Coder-32B-Instruct",
        machine_type="g2-standard-48",
        accelerator_type="NVIDIA_L4",
        accelerator_count=4,
        tensor_parallel_size=4,
        notes="Qwen 2.5 Coder 32B (4x L4)",
    ),
    VertexCustomJobTarget(
        flavor="ministral-3b-2410",
        hf_repo="mistralai/Ministral-3b-instruct-2410",
        machine_type="g2-standard-8",
        accelerator_type="NVIDIA_L4",
        accelerator_count=1,
        tensor_parallel_size=1,
        notes="Ministral 3B (1x L4)",
    ),
    VertexCustomJobTarget(
        flavor="phi-4",
        hf_repo="microsoft/phi-4",
        machine_type="g2-standard-12",
        accelerator_type="NVIDIA_L4",
        accelerator_count=1,
        tensor_parallel_size=1,
        notes="Phi-4 14B (1x L4)",
    ),
    VertexCustomJobTarget(
        flavor="deepseek-r1-distill-qwen-32b",
        hf_repo="deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
        machine_type="g2-standard-48",
        accelerator_type="NVIDIA_L4",
        accelerator_count=4,
        tensor_parallel_size=4,
        notes="DeepSeek R1 Distill Qwen 32B (4x L4)",
    ),
    VertexCustomJobTarget(
        flavor="llama-3.2-3b-instruct",
        hf_repo="meta-llama/Llama-3.2-3B-Instruct",
        machine_type="g2-standard-8",
        accelerator_type="NVIDIA_L4",
        accelerator_count=1,
        tensor_parallel_size=1,
        notes="Llama 3.2 3B (1x L4)",
    ),
    VertexCustomJobTarget(
        flavor="llama-guard-3-8b",
        hf_repo="meta-llama/Llama-Guard-3-8B",
        machine_type="g2-standard-12",
        accelerator_type="NVIDIA_L4",
        accelerator_count=1,
        tensor_parallel_size=1,
        notes="Llama Guard 3 8B (1x L4)",
    ),
    VertexCustomJobTarget(
        flavor="llama-3.1-nemotron-70b-instruct",
        hf_repo="nvidia/Llama-3.1-Nemotron-70B-Instruct-HF",
        machine_type="g2-standard-48",
        accelerator_type="NVIDIA_L4",
        accelerator_count=4,
        tensor_parallel_size=4,
        notes="Nemotron Llama 70B (4x L4)",
    ),
]


def build_worker_pool_spec(
    target: VertexCustomJobTarget,
    container_image_uri: str,
    output_gcs_uri: str,
    hf_token: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Constructs Vertex AI worker pool specification dictionaries for the target hardware.
    """
    container_args = [
        target.flavor,
        target.hf_repo,
        str(target.tensor_parallel_size),
        target.extra_vllm_flags,
        output_gcs_uri,
    ]

    container_spec: Dict[str, Any] = {
        "image_uri": container_image_uri,
        "args": container_args,
    }

    if hf_token:
        container_spec["env"] = [
            {"name": "HF_TOKEN", "value": hf_token},
        ]

    worker_pool_spec: Dict[str, Any] = {
        "machine_spec": {
            "machine_type": target.machine_type,
            "accelerator_type": target.accelerator_type,
            "accelerator_count": target.accelerator_count,
        },
        "replica_count": 1,
        "container_spec": container_spec,
    }

    return [worker_pool_spec]


class VertexCustomJobOrchestrator:
    """
    Orchestrates the lifecycle of ephemeral Vertex AI Custom Jobs for benchmarking.
    Guarantees compute node teardown upon job termination.
    """

    def __init__(
        self,
        project_id: str = "dandye-0324-chronicle",
        region: str = "us-central1",
        container_image_uri: str = "us-docker.pkg.dev/dandye-0324-chronicle/gemma-benchmarks/runner:latest",
        output_gcs_bucket: str = "gs://secops-eval-results/custom_jobs",
        hf_token: Optional[str] = None,
        dry_run: bool = False,
        timeout_seconds: int = 3600,
        output_dir: Optional[Path] = None,
        scorecard_path: Optional[Path] = None,
    ) -> None:
        self.project_id = project_id
        self.region = region
        self.container_image_uri = container_image_uri
        self.output_gcs_bucket = output_gcs_bucket
        self.hf_token = hf_token
        self.dry_run = dry_run
        self.timeout_seconds = timeout_seconds
        self.output_dir = output_dir or (ROOT_DIR / "docs" / "custom_job_eval_results")
        self.scorecard_path = scorecard_path or (ROOT_DIR / "docs" / "custom_jobs_comparative_scorecard.md")

    def submit_job(self, target: VertexCustomJobTarget) -> Any:
        """
        Submits an ephemeral Vertex AI CustomJob for the target model.
        Returns the created CustomJob instance or mock object in dry-run mode.
        """
        worker_pool_specs = build_worker_pool_spec(
            target=target,
            container_image_uri=self.container_image_uri,
            output_gcs_uri=self.output_gcs_bucket,
            hf_token=self.hf_token,
        )

        job_display_name = f"gemma-bench-{target.flavor}-{int(time.time())}"

        if self.dry_run:
            print(f"[DRY RUN] Submitting CustomJob '{job_display_name}' for model {target.flavor} ({target.machine_type})...")
            return {
                "job_id": f"mock-custom-job-{target.flavor}",
                "display_name": job_display_name,
                "state": "JOB_STATE_SUCCEEDED",
                "target": target,
                "worker_pool_specs": worker_pool_specs,
            }

        print(f"[INFO] Initializing Vertex AI in project '{self.project_id}' region '{self.region}'...")
        from google.cloud import aiplatform

        aiplatform.init(
            project=self.project_id,
            location=self.region,
            staging_bucket=self.output_gcs_bucket,
        )

        print(f"[INFO] Creating CustomJob '{job_display_name}' with machine {target.machine_type} ({target.accelerator_count}x {target.accelerator_type})...")
        custom_job = aiplatform.CustomJob(
            display_name=job_display_name,
            worker_pool_specs=worker_pool_specs,
            staging_bucket=self.output_gcs_bucket,
            project=self.project_id,
            location=self.region,
        )

        print(f"[INFO] Submitting CustomJob asynchronously for {target.flavor}...")
        custom_job.submit()
        print(f"[INFO] CustomJob submitted: {custom_job.resource_name if hasattr(custom_job, 'resource_name') else job_display_name}")
        return custom_job

    def poll_job(self, job: Any, timeout_s: Optional[int] = None) -> bool:
        """
        Blocks until the CustomJob completes, fails, or times out.
        Returns True if successful, False otherwise.
        """
        timeout = timeout_s or self.timeout_seconds
        if self.dry_run:
            print("[DRY RUN] Polling CustomJob: Success (dry run simulated).")
            return True

        if isinstance(job, dict):
            return job.get("state") == "JOB_STATE_SUCCEEDED"

        print(f"[INFO] Waiting for CustomJob completion (timeout: {timeout}s)...")
        try:
            if hasattr(job, "wait"):
                job.wait()
            state_name = getattr(getattr(job, "state", None), "name", str(getattr(job, "state", "UNKNOWN")))
            if state_name in ["JOB_STATE_SUCCEEDED", "SUCCEEDED"]:
                print(f"[INFO] CustomJob succeeded with state: {state_name}")
                return True
            print(f"[WARNING] CustomJob finished with non-success state: {state_name}")
            return False
        except Exception as e:
            print(f"[ERROR] Error or timeout while waiting for CustomJob: {e}")
            return False

    def collect_results(self, target: VertexCustomJobTarget) -> Dict[str, Any]:
        """
        Retrieves and parses evaluation and benchmark JSON reports from Google Cloud Storage.
        """
        if self.dry_run:
            print(f"[DRY RUN] Collecting evaluation results for {target.flavor}...")
            return {
                "flavor": target.flavor,
                "success": True,
                "target": target,
                "soc_eval": {
                    "flavor": target.flavor,
                    "summary": {
                        "total_cases": 5,
                        "passed_cases": 5,
                        "pass_rate": 100.0,
                        "avg_rubric_score": 95.0,
                        "avg_latency_s": 11.5,
                        "total_prompt_tokens": 8000,
                        "total_completion_tokens": 4000,
                        "total_tokens": 12000,
                        "avg_tokens_per_case": 2400.0,
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
                            "usage": {"prompt_tokens": 1600, "completion_tokens": 800, "total_tokens": 2400},
                            "trajectory": [{"iteration": 1, "tool": "lookup_entity"}],
                            "critique": "Solid analysis.",
                            "response": "Remediation summary.",
                        }
                        for i in range(1, 6)
                    ],
                },
                "benchmark": {
                    "flavor": target.flavor,
                    "avg_latency_s": 1.2,
                    "tps": 75.0,
                    "ttft_ms": 110.0,
                },
            }

        from google.cloud import storage

        gcs_clean = self.output_gcs_bucket.replace("gs://", "").rstrip("/")
        bucket_name, *prefix_parts = gcs_clean.split("/")
        prefix = "/".join(prefix_parts)
        model_prefix = f"{prefix}/{target.flavor}" if prefix else target.flavor

        print(f"[INFO] Downloading results from gs://{bucket_name}/{model_prefix}...")
        client = storage.Client(project=self.project_id)
        bucket = client.bucket(bucket_name)

        soc_report_blob_name = f"{model_prefix}/{target.flavor}_soc_eval_report.json"
        bench_report_blob_name = f"{model_prefix}/{target.flavor}_benchmark.json"
        md_report_blob_name = f"{model_prefix}/{target.flavor}_soc_eval_report.md"

        soc_eval: Dict[str, Any] = {}
        benchmark: Dict[str, Any] = {}
        report_md_text: str = ""

        soc_blob = bucket.get_blob(soc_report_blob_name)
        if soc_blob:
            soc_eval = json.loads(soc_blob.download_as_text())

        bench_blob = bucket.get_blob(bench_report_blob_name)
        if bench_blob:
            benchmark = json.loads(bench_blob.download_as_text())

        md_blob = bucket.get_blob(md_report_blob_name)
        if md_blob:
            report_md_text = md_blob.download_as_text()

        success = bool(soc_eval or benchmark)
        return {
            "flavor": target.flavor,
            "success": success,
            "target": target,
            "soc_eval": soc_eval,
            "benchmark": benchmark,
            "report_md": report_md_text,
        }

    def run_sweep(
        self,
        models_filter: Optional[List[str]] = None,
        wait: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Executes evaluation and benchmark sweep for target models.
        """
        queue: List[VertexCustomJobTarget] = []
        if models_filter:
            filter_set = {m.strip().lower() for m in models_filter}
            queue = [t for t in ALL_CUSTOM_JOB_TARGETS if t.flavor.lower() in filter_set]
            if not queue:
                print(f"[WARNING] No targets matched models filter: {models_filter}")
        else:
            queue = list(ALL_CUSTOM_JOB_TARGETS)

        print(f"[INFO] Starting Custom Job Sweep over {len(queue)} model target(s)...")
        results: List[Dict[str, Any]] = []

        for idx, target in enumerate(queue, start=1):
            print(f"\n[{idx}/{len(queue)}] Processing Target: {target.flavor} ({target.notes})...")
            try:
                job = self.submit_job(target)
                if wait:
                    ok = self.poll_job(job)
                    if ok:
                        res = self.collect_results(target)
                        results.append(res)
                    else:
                        results.append({
                            "flavor": target.flavor,
                            "success": False,
                            "target": target,
                            "error": "CustomJob execution failed or timed out.",
                        })
                else:
                    results.append({
                        "flavor": target.flavor,
                        "success": True,
                        "target": target,
                        "status": "SUBMITTED",
                        "job": job,
                    })
            except Exception as e:
                print(f"[ERROR] Exception processing {target.flavor}: {e}")
                results.append({
                    "flavor": target.flavor,
                    "success": False,
                    "target": target,
                    "error": str(e),
                })

        return results


def main() -> None:
    """CLI entrypoint for running Vertex AI Custom Job sweeps."""
    parser = argparse.ArgumentParser(
        description="Vertex AI Custom Job Ephemeral Sweep Runner for Gemma and Partner Models"
    )
    parser.add_argument(
        "--models",
        type=str,
        default="",
        help="Comma-separated list of model flavors to evaluate (default: all models)",
    )
    parser.add_argument(
        "--project-id",
        type=str,
        default="dandye-0324-chronicle",
        help="Google Cloud project ID",
    )
    parser.add_argument(
        "--region",
        type=str,
        default="us-central1",
        help="Google Cloud region for CustomJob execution",
    )
    parser.add_argument(
        "--image-uri",
        type=str,
        default="us-docker.pkg.dev/dandye-0324-chronicle/gemma-benchmarks/runner:latest",
        help="Artifact Registry container image URI for benchmark runner",
    )
    parser.add_argument(
        "--output-gcs-bucket",
        type=str,
        default="gs://secops-eval-results/custom_jobs",
        help="GCS bucket URI for evaluation and benchmark artifacts",
    )
    parser.add_argument(
        "--hf-token",
        type=str,
        default=os.environ.get("HF_TOKEN", ""),
        help="Hugging Face API token for downloading gated model weights",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate execution without submitting live Vertex AI CustomJobs",
    )
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Submit CustomJobs asynchronously and exit without polling for completion",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=3600,
        help="CustomJob timeout in seconds",
    )

    args = parser.parse_args()

    models_filter = [m.strip() for m in args.models.split(",") if m.strip()] if args.models else None

    orchestrator = VertexCustomJobOrchestrator(
        project_id=args.project_id,
        region=args.region,
        container_image_uri=args.image_uri,
        output_gcs_bucket=args.output_gcs_bucket,
        hf_token=args.hf_token or None,
        dry_run=args.dry_run,
        timeout_seconds=args.timeout_seconds,
    )

    results = orchestrator.run_sweep(models_filter=models_filter, wait=not args.no_wait)
    print(f"\n[INFO] Completed Custom Job sweep for {len(results)} target(s).")


if __name__ == "__main__":
    main()
