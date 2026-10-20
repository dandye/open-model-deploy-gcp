#!/usr/bin/env python3
"""
GKE Ray & Kueue Model Evaluation Sweep Orchestrator

Manages rendering of RayCluster and batch Job manifests, submits workloads
to Kueue queues on GKE, monitors execution lifecycle, and collects evaluation results.
"""

import argparse
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Sequence
import yaml

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


@dataclass
class GKERayTarget:
    """Specification of a GKE Ray serving and evaluation target."""

    flavor: str
    hf_repo: str
    gpu_count: int
    gpu_type: str
    cpu: int = 4
    memory: str = "16Gi"
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
                base = base[:-len(suffix)]
        return base


ALL_GKE_RAY_TARGETS: List[GKERayTarget] = [
    # Gemma 2 Family (Dense & Optimizations)
    GKERayTarget(
        flavor="gemma-2-2b-it",
        hf_repo="google/gemma-2-2b-it",
        gpu_count=1,
        gpu_type="nvidia-l4",
        cpu=4,
        memory="16Gi",
        tensor_parallel_size=1,
        extra_vllm_flags="",
        notes="Gemma 2 2B (1x L4)",
    ),
    GKERayTarget(
        flavor="gemma-2-2b-it-speculative",
        hf_repo="google/gemma-2-2b-it",
        gpu_count=1,
        gpu_type="nvidia-l4",
        cpu=4,
        memory="16Gi",
        tensor_parallel_size=1,
        extra_vllm_flags="--speculative-model=[ngram] --num-speculative-tokens=5 --ngram-prompt-lookup-max=5 --ngram-prompt-lookup-min=2",
        notes="Gemma 2 2B Speculative Decoding (1x L4)",
    ),
    GKERayTarget(
        flavor="gemma-2-9b-it",
        hf_repo="google/gemma-2-9b-it",
        gpu_count=1,
        gpu_type="nvidia-l4",
        cpu=8,
        memory="32Gi",
        tensor_parallel_size=1,
        extra_vllm_flags="",
        notes="Gemma 2 9B (1x L4)",
    ),
    GKERayTarget(
        flavor="gemma-2-9b-it-fp8",
        hf_repo="google/gemma-2-9b-it",
        gpu_count=1,
        gpu_type="nvidia-l4",
        cpu=8,
        memory="32Gi",
        tensor_parallel_size=1,
        extra_vllm_flags="--quantization=fp8",
        notes="Gemma 2 9B FP8 Quantized (1x L4)",
    ),
    GKERayTarget(
        flavor="gemma-2-9b-it-speculative",
        hf_repo="google/gemma-2-9b-it",
        gpu_count=1,
        gpu_type="nvidia-l4",
        cpu=8,
        memory="32Gi",
        tensor_parallel_size=1,
        extra_vllm_flags="--quantization=fp8 --speculative-model=[ngram] --num-speculative-tokens=5 --ngram-prompt-lookup-max=5 --ngram-prompt-lookup-min=2",
        notes="Gemma 2 9B FP8 Speculative Decoding (1x L4)",
    ),
    GKERayTarget(
        flavor="gemma-2-27b-it",
        hf_repo="google/gemma-2-27b-it",
        gpu_count=4,
        gpu_type="nvidia-l4",
        cpu=16,
        memory="64Gi",
        tensor_parallel_size=4,
        extra_vllm_flags="",
        notes="Gemma 2 27B (4x L4)",
    ),
    GKERayTarget(
        flavor="gemma-2-27b-it-fp8",
        hf_repo="google/gemma-2-27b-it",
        gpu_count=4,
        gpu_type="nvidia-l4",
        cpu=16,
        memory="64Gi",
        tensor_parallel_size=4,
        extra_vllm_flags="--quantization=fp8",
        notes="Gemma 2 27B FP8 Quantized (4x L4)",
    ),
    GKERayTarget(
        flavor="gemma-2-27b-it-speculative",
        hf_repo="google/gemma-2-27b-it",
        gpu_count=4,
        gpu_type="nvidia-l4",
        cpu=16,
        memory="64Gi",
        tensor_parallel_size=4,
        extra_vllm_flags="--quantization=fp8 --speculative-model=[ngram] --num-speculative-tokens=5 --ngram-prompt-lookup-max=5 --ngram-prompt-lookup-min=2",
        notes="Gemma 2 27B FP8 Speculative Decoding (4x L4)",
    ),
    # Gemma 3 Family (Dense & Optimizations)
    GKERayTarget(
        flavor="gemma-3-1b-it",
        hf_repo="google/gemma-3-1b-it",
        gpu_count=1,
        gpu_type="nvidia-l4",
        cpu=4,
        memory="16Gi",
        tensor_parallel_size=1,
        extra_vllm_flags="",
        notes="Gemma 3 1B (1x L4)",
    ),
    GKERayTarget(
        flavor="gemma-3-1b-it-speculative",
        hf_repo="google/gemma-3-1b-it",
        gpu_count=1,
        gpu_type="nvidia-l4",
        cpu=4,
        memory="16Gi",
        tensor_parallel_size=1,
        extra_vllm_flags="--speculative-model=[ngram] --num-speculative-tokens=5 --ngram-prompt-lookup-max=5 --ngram-prompt-lookup-min=2",
        notes="Gemma 3 1B Speculative Decoding (1x L4)",
    ),
    GKERayTarget(
        flavor="gemma-3-4b-it",
        hf_repo="google/gemma-3-4b-it",
        gpu_count=1,
        gpu_type="nvidia-l4",
        cpu=8,
        memory="32Gi",
        tensor_parallel_size=1,
        extra_vllm_flags="--limit_mm_per_prompt=image=5 --max-num-seqs=4",
        notes="Gemma 3 4B Multimodal (1x L4)",
    ),
    GKERayTarget(
        flavor="gemma-3-4b-it-speculative",
        hf_repo="google/gemma-3-4b-it",
        gpu_count=1,
        gpu_type="nvidia-l4",
        cpu=8,
        memory="32Gi",
        tensor_parallel_size=1,
        extra_vllm_flags="--limit_mm_per_prompt=image=5 --max-num-seqs=4 --speculative-model=[ngram] --num-speculative-tokens=5 --ngram-prompt-lookup-max=5 --ngram-prompt-lookup-min=2",
        notes="Gemma 3 4B Speculative Decoding (1x L4)",
    ),
    GKERayTarget(
        flavor="gemma-3-12b-it",
        hf_repo="google/gemma-3-12b-it",
        gpu_count=4,
        gpu_type="nvidia-l4",
        cpu=16,
        memory="64Gi",
        tensor_parallel_size=4,
        extra_vllm_flags="--limit_mm_per_prompt=image=5 --max-num-seqs=4",
        notes="Gemma 3 12B Multimodal (4x L4)",
    ),
    GKERayTarget(
        flavor="gemma-3-12b-it-fp8",
        hf_repo="google/gemma-3-12b-it",
        gpu_count=4,
        gpu_type="nvidia-l4",
        cpu=16,
        memory="64Gi",
        tensor_parallel_size=4,
        extra_vllm_flags="--quantization=fp8 --limit_mm_per_prompt=image=5 --max-num-seqs=4",
        notes="Gemma 3 12B FP8 Quantized (4x L4)",
    ),
    GKERayTarget(
        flavor="gemma-3-12b-it-speculative",
        hf_repo="google/gemma-3-12b-it",
        gpu_count=4,
        gpu_type="nvidia-l4",
        cpu=16,
        memory="64Gi",
        tensor_parallel_size=4,
        extra_vllm_flags="--quantization=fp8 --speculative-model=[ngram] --num-speculative-tokens=5 --ngram-prompt-lookup-max=5 --ngram-prompt-lookup-min=2 --limit_mm_per_prompt=image=5 --max-num-seqs=4",
        notes="Gemma 3 12B FP8 Speculative Decoding (4x L4)",
    ),
    GKERayTarget(
        flavor="gemma-3-12b-it-draft-1b",
        hf_repo="google/gemma-3-12b-it",
        gpu_count=4,
        gpu_type="nvidia-l4",
        cpu=16,
        memory="64Gi",
        tensor_parallel_size=4,
        extra_vllm_flags="--limit_mm_per_prompt=image=5 --max-num-seqs=4 --speculative-model=google/gemma-3-1b-it --num-speculative-tokens=5",
        notes="Gemma 3 12B + Gemma 3 1B Draft (4x L4)",
    ),
    GKERayTarget(
        flavor="gemma-3-27b-it",
        hf_repo="google/gemma-3-27b-it",
        gpu_count=4,
        gpu_type="nvidia-l4",
        cpu=16,
        memory="64Gi",
        tensor_parallel_size=4,
        extra_vllm_flags="--limit_mm_per_prompt=image=5 --max-num-seqs=4",
        notes="Gemma 3 27B Multimodal (4x L4)",
    ),
    GKERayTarget(
        flavor="gemma-3-27b-it-fp8",
        hf_repo="google/gemma-3-27b-it",
        gpu_count=4,
        gpu_type="nvidia-l4",
        cpu=16,
        memory="64Gi",
        tensor_parallel_size=4,
        extra_vllm_flags="--quantization=fp8 --limit_mm_per_prompt=image=5 --max-num-seqs=4",
        notes="Gemma 3 27B FP8 Quantized (4x L4)",
    ),
    GKERayTarget(
        flavor="gemma-3-27b-it-speculative",
        hf_repo="google/gemma-3-27b-it",
        gpu_count=4,
        gpu_type="nvidia-l4",
        cpu=16,
        memory="64Gi",
        tensor_parallel_size=4,
        extra_vllm_flags="--quantization=fp8 --speculative-model=[ngram] --num-speculative-tokens=5 --ngram-prompt-lookup-max=5 --ngram-prompt-lookup-min=2 --limit_mm_per_prompt=image=5 --max-num-seqs=4",
        notes="Gemma 3 27B FP8 Speculative Decoding (4x L4)",
    ),
    GKERayTarget(
        flavor="gemma-3-27b-it-caching",
        hf_repo="google/gemma-3-27b-it",
        gpu_count=4,
        gpu_type="nvidia-l4",
        cpu=16,
        memory="64Gi",
        tensor_parallel_size=4,
        extra_vllm_flags="--quantization=fp8 --enable-chunked-prefill --enable-prefix-caching --limit_mm_per_prompt=image=5 --max-num-seqs=4",
        notes="Gemma 3 27B FP8 Prefix Caching (4x L4)",
    ),
    GKERayTarget(
        flavor="gemma-3-27b-it-draft-1b",
        hf_repo="google/gemma-3-27b-it",
        gpu_count=4,
        gpu_type="nvidia-l4",
        cpu=16,
        memory="64Gi",
        tensor_parallel_size=4,
        extra_vllm_flags="--limit_mm_per_prompt=image=5 --max-num-seqs=4 --speculative-model=google/gemma-3-1b-it --num-speculative-tokens=5",
        notes="Gemma 3 27B + Gemma 3 1B Draft (4x L4)",
    ),
    GKERayTarget(
        flavor="gemma-3-27b-it-draft-4b",
        hf_repo="google/gemma-3-27b-it",
        gpu_count=4,
        gpu_type="nvidia-l4",
        cpu=16,
        memory="64Gi",
        tensor_parallel_size=4,
        extra_vllm_flags="--limit_mm_per_prompt=image=5 --max-num-seqs=4 --speculative-model=google/gemma-3-4b-it --num-speculative-tokens=5",
        notes="Gemma 3 27B + Gemma 3 4B Draft (4x L4)",
    ),
    # Gemma 4 Family (Dense & Optimizations)
    GKERayTarget(
        flavor="gemma-4-e2b-it",
        hf_repo="google/gemma-4-E2B-it",
        gpu_count=1,
        gpu_type="nvidia-l4",
        cpu=4,
        memory="16Gi",
        tensor_parallel_size=1,
        extra_vllm_flags="--max-num-seqs=16",
        notes="Gemma 4 E2B Edge (1x L4)",
    ),
    GKERayTarget(
        flavor="gemma-4-e2b-it-speculative",
        hf_repo="google/gemma-4-E2B-it",
        gpu_count=1,
        gpu_type="nvidia-l4",
        cpu=4,
        memory="16Gi",
        tensor_parallel_size=1,
        extra_vllm_flags="--max-num-seqs=16 --speculative-model=[ngram] --num-speculative-tokens=5 --ngram-prompt-lookup-max=5 --ngram-prompt-lookup-min=2",
        notes="Gemma 4 E2B Speculative Decoding (1x L4)",
    ),
    GKERayTarget(
        flavor="gemma-4-e4b-it",
        hf_repo="google/gemma-4-E4B-it",
        gpu_count=1,
        gpu_type="nvidia-l4",
        cpu=8,
        memory="32Gi",
        tensor_parallel_size=1,
        extra_vllm_flags="--max-num-seqs=16",
        notes="Gemma 4 E4B Edge (1x L4)",
    ),
    GKERayTarget(
        flavor="gemma-4-e4b-it-speculative",
        hf_repo="google/gemma-4-E4B-it",
        gpu_count=1,
        gpu_type="nvidia-l4",
        cpu=8,
        memory="32Gi",
        tensor_parallel_size=1,
        extra_vllm_flags="--max-num-seqs=16 --speculative-model=[ngram] --num-speculative-tokens=5 --ngram-prompt-lookup-max=5 --ngram-prompt-lookup-min=2",
        notes="Gemma 4 E4B Speculative Decoding (1x L4)",
    ),
    GKERayTarget(
        flavor="gemma-4-31b-it",
        hf_repo="google/gemma-4-31B-it",
        gpu_count=2,
        gpu_type="nvidia-tesla-a100",
        cpu=16,
        memory="64Gi",
        tensor_parallel_size=2,
        extra_vllm_flags="--max-num-seqs=16",
        notes="Gemma 4 31B Multimodal Reasoner (2x A100)",
    ),
    GKERayTarget(
        flavor="gemma-4-31b-it-speculative",
        hf_repo="google/gemma-4-31B-it",
        gpu_count=2,
        gpu_type="nvidia-tesla-a100",
        cpu=16,
        memory="64Gi",
        tensor_parallel_size=2,
        extra_vllm_flags="--max-num-seqs=16 --speculative-model=[ngram] --num-speculative-tokens=5 --ngram-prompt-lookup-max=5 --ngram-prompt-lookup-min=2",
        notes="Gemma 4 31B Speculative Decoding (2x A100)",
    ),
    GKERayTarget(
        flavor="gemma-4-31b-it-draft-e2b",
        hf_repo="google/gemma-4-31B-it",
        gpu_count=2,
        gpu_type="nvidia-tesla-a100",
        cpu=16,
        memory="64Gi",
        tensor_parallel_size=2,
        extra_vllm_flags="--max-num-seqs=16 --speculative-model=google/gemma-4-E2B-it --num-speculative-tokens=5",
        notes="Gemma 4 31B + Gemma 4 E2B Draft (2x A100)",
    ),
    GKERayTarget(
        flavor="gemma-4-31b-it-draft-e4b",
        hf_repo="google/gemma-4-31B-it",
        gpu_count=2,
        gpu_type="nvidia-tesla-a100",
        cpu=16,
        memory="64Gi",
        tensor_parallel_size=2,
        extra_vllm_flags="--max-num-seqs=16 --speculative-model=google/gemma-4-E4B-it --num-speculative-tokens=5",
        notes="Gemma 4 31B + Gemma 4 E4B Draft (2x A100)",
    ),
    # Partner & Open Model Targets
    GKERayTarget(
        flavor="inkling-small",
        hf_repo="thinkingmachines/Inkling-Small",
        gpu_count=4,
        gpu_type="nvidia-l4",
        cpu=16,
        memory="64Gi",
        tensor_parallel_size=4,
        extra_vllm_flags="--tokenizer-mode=inkling",
        notes="Thinking Machines Inkling Small (4x L4)",
    ),
    GKERayTarget(
        flavor="nemotron-3.5-lightning-bf16",
        hf_repo="nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16",
        gpu_count=4,
        gpu_type="nvidia-l4",
        cpu=16,
        memory="64Gi",
        tensor_parallel_size=4,
        extra_vllm_flags="",
        notes="NVIDIA Nemotron 3.5 Lightning (4x L4)",
    ),
    GKERayTarget(
        flavor="nemotron-3.5-super-vl-nvfp4",
        hf_repo="nvidia/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-NVFP4",
        gpu_count=1,
        gpu_type="nvidia-rtx-pro-6000",
        cpu=32,
        memory="160Gi",
        tensor_parallel_size=1,
        extra_vllm_flags="--trust-remote-code --enable-auto-tool-choice --tool-call-parser=qwen3_coder --reasoning-parser=nemotron_v3 --mamba-backend=flashinfer --speculative_config.method=mtp --speculative_config.num_speculative_tokens=3",
        notes="NVIDIA Nemotron 3.5 Super VL 120B-A12B NVFP4 (1x RTX PRO 6000)",
    ),
    GKERayTarget(
        flavor="nemotron-3.5-super-vl-bf16",
        hf_repo="nvidia/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-BF16",
        gpu_count=4,
        gpu_type="nvidia-rtx-pro-6000",
        cpu=64,
        memory="512Gi",
        tensor_parallel_size=4,
        extra_vllm_flags="--trust-remote-code --enable-auto-tool-choice --tool-call-parser=qwen3_coder --reasoning-parser=nemotron_v3 --mamba-backend=flashinfer --speculative_config.method=mtp --speculative_config.num_speculative_tokens=3",
        notes="NVIDIA Nemotron 3.5 Super VL 120B-A12B BF16 (4x RTX PRO 6000)",
    ),
    GKERayTarget(
        flavor="qwen2.5-coder-32b-instruct",
        hf_repo="Qwen/Qwen2.5-Coder-32B-Instruct",
        gpu_count=4,
        gpu_type="nvidia-l4",
        cpu=16,
        memory="64Gi",
        tensor_parallel_size=4,
        extra_vllm_flags="",
        notes="Qwen 2.5 Coder 32B (4x L4)",
    ),
    GKERayTarget(
        flavor="ministral-3b-2410",
        hf_repo="mistralai/Ministral-3b-instruct-2410",
        gpu_count=1,
        gpu_type="nvidia-l4",
        cpu=8,
        memory="32Gi",
        tensor_parallel_size=1,
        extra_vllm_flags="",
        notes="Mistral Ministral 3B (1x L4)",
    ),
    GKERayTarget(
        flavor="phi-4",
        hf_repo="microsoft/phi-4",
        gpu_count=1,
        gpu_type="nvidia-l4",
        cpu=8,
        memory="32Gi",
        tensor_parallel_size=1,
        extra_vllm_flags="",
        notes="Microsoft Phi-4 (1x L4)",
    ),
    GKERayTarget(
        flavor="deepseek-r1-distill-qwen-32b",
        hf_repo="deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
        gpu_count=4,
        gpu_type="nvidia-l4",
        cpu=16,
        memory="64Gi",
        tensor_parallel_size=4,
        extra_vllm_flags="",
        notes="DeepSeek R1 Distill Qwen 32B (4x L4)",
    ),
    GKERayTarget(
        flavor="qwen3.8-flash-next",
        hf_repo="Qwen/Qwen3.8-Flash-Next",
        gpu_count=1,
        gpu_type="nvidia-l4",
        cpu=8,
        memory="32Gi",
        tensor_parallel_size=1,
        extra_vllm_flags="",
        notes="Qwen 3.8 Flash Next (1x L4)",
    ),
    GKERayTarget(
        flavor="qwen3.8-flash-next-fp8",
        hf_repo="Qwen/Qwen3.8-Flash-Next-FP8",
        gpu_count=1,
        gpu_type="nvidia-l4",
        cpu=8,
        memory="32Gi",
        tensor_parallel_size=1,
        extra_vllm_flags="--quantization=fp8",
        notes="Qwen 3.8 Flash Next FP8 (1x L4)",
    ),
    GKERayTarget(
        flavor="glm-5.3-flash",
        hf_repo="zai-org/GLM-5.3-Flash",
        gpu_count=1,
        gpu_type="nvidia-l4",
        cpu=8,
        memory="32Gi",
        tensor_parallel_size=1,
        extra_vllm_flags="",
        notes="GLM 5.3 Flash (1x L4)",
    ),
    GKERayTarget(
        flavor="llama-3.2-3b-instruct",
        hf_repo="meta-llama/Llama-3.2-3B-Instruct",
        gpu_count=1,
        gpu_type="nvidia-l4",
        cpu=8,
        memory="32Gi",
        tensor_parallel_size=1,
        extra_vllm_flags="",
        notes="Llama 3.2 3B Instruct (1x L4)",
    ),
    GKERayTarget(
        flavor="llama-guard-3-8b",
        hf_repo="meta-llama/Llama-Guard-3-8B",
        gpu_count=1,
        gpu_type="nvidia-l4",
        cpu=8,
        memory="32Gi",
        tensor_parallel_size=1,
        extra_vllm_flags="",
        notes="Llama Guard 3 8B (1x L4)",
    ),
    GKERayTarget(
        flavor="llama-3.1-nemotron-70b-instruct",
        hf_repo="nvidia/Llama-3.1-Nemotron-70B-Instruct-HF",
        gpu_count=4,
        gpu_type="nvidia-l4",
        cpu=16,
        memory="64Gi",
        tensor_parallel_size=4,
        extra_vllm_flags="",
        notes="Llama 3.1 Nemotron 70B (4x L4)",
    ),
]

ALL_GKE_RAY_TARGETS_MAP: Dict[str, GKERayTarget] = {t.flavor: t for t in ALL_GKE_RAY_TARGETS}


def render_ray_cluster_manifest(
    target: GKERayTarget,
    namespace: str = "gemma-benchmarks",
    cluster_name: Optional[str] = None,
    queue_name: str = "llm-sweep-queue",
    template_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Renders RayCluster Kubernetes manifest dictionary from template."""
    path = template_path or (ROOT_DIR / "k8s" / "templates" / "ray_vllm_cluster_template.yaml")
    if not path.exists():
        raise FileNotFoundError(f"RayCluster template not found at {path}")

    content = path.read_text(encoding="utf-8")
    c_name = cluster_name or f"ray-{target.flavor}"

    replacements: Dict[str, str] = {
        "{{CLUSTER_NAME}}": c_name,
        "{{NAMESPACE}}": namespace,
        "{{QUEUE_NAME}}": queue_name,
        "{{MODEL_FLAVOR}}": target.flavor,
        "{{HF_REPO}}": target.hf_repo,
        "{{GPU_COUNT}}": str(target.gpu_count),
        "{{GPU_TYPE}}": target.gpu_type,
        "{{CPU}}": str(target.cpu),
        "{{MEMORY}}": target.memory,
        "{{TP_SIZE}}": str(target.tensor_parallel_size),
        "{{EXTRA_FLAGS}}": target.extra_vllm_flags,
    }

    for placeholder, value in replacements.items():
        content = content.replace(placeholder, value)

    manifest = yaml.safe_load(content)
    if not isinstance(manifest, dict):
        raise ValueError(f"Failed to parse rendered RayCluster manifest into dictionary: {manifest}")
    return manifest


def render_eval_job_manifest(
    target: GKERayTarget,
    namespace: str = "gemma-benchmarks",
    job_name: Optional[str] = None,
    queue_name: str = "llm-sweep-queue",
    vllm_url: Optional[str] = None,
    output_gcs_path: Optional[str] = None,
    template_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Renders batch Job Kubernetes manifest dictionary from template."""
    path = template_path or (ROOT_DIR / "k8s" / "templates" / "eval_job_template.yaml")
    if not path.exists():
        raise FileNotFoundError(f"Eval Job template not found at {path}")

    content = path.read_text(encoding="utf-8")
    j_name = job_name or f"eval-job-{target.flavor}"
    v_url = vllm_url or f"http://ray-{target.flavor}-serve-svc:8000/v1"
    gcs_path = output_gcs_path if output_gcs_path is not None else ""

    replacements: Dict[str, str] = {
        "{{JOB_NAME}}": j_name,
        "{{NAMESPACE}}": namespace,
        "{{QUEUE_NAME}}": queue_name,
        "{{MODEL_FLAVOR}}": target.flavor,
        "{{HF_REPO}}": target.hf_repo,
        "{{VLLM_SERVICE_URL}}": v_url,
        "{{OUTPUT_GCS_PATH}}": gcs_path,
    }

    for placeholder, value in replacements.items():
        content = content.replace(placeholder, value)

    manifest = yaml.safe_load(content)
    if not isinstance(manifest, dict):
        raise ValueError(f"Failed to parse rendered Eval Job manifest into dictionary: {manifest}")
    return manifest


class GKERayOrchestrator:
    """
    Orchestrates RayCluster deployments and Kueue evaluation jobs on GKE.
    Handles manifest rendering, kubectl application, lifecycle monitoring, and GCS metric collection.
    """

    def __init__(
        self,
        project_id: str = "dandye-0324-chronicle",
        namespace: str = "gemma-benchmarks",
        queue_name: str = "llm-sweep-queue",
        output_gcs_bucket: str = "dandye-0324-chronicle-soc-benchmarks",
        dry_run: bool = False,
        timeout_seconds: int = 3600,
        poll_interval_seconds: int = 10,
    ) -> None:
        self.project_id = project_id
        self.namespace = namespace
        self.queue_name = queue_name
        self.output_gcs_bucket = output_gcs_bucket
        self.dry_run = dry_run
        self.timeout_seconds = timeout_seconds
        self.poll_interval_seconds = poll_interval_seconds

    def deploy_ray_cluster(self, target: GKERayTarget) -> str:
        """
        Deploys a RayCluster for the target model via kubectl.
        Returns cluster name.
        """
        cluster_name = f"ray-{target.flavor}"
        manifest = render_ray_cluster_manifest(
            target=target,
            namespace=self.namespace,
            cluster_name=cluster_name,
            queue_name=self.queue_name,
        )

        if self.dry_run:
            print(f"[DRY RUN] Deploying RayCluster '{cluster_name}' in namespace '{self.namespace}'...")
            return cluster_name

        print(f"[INFO] Deploying RayCluster '{cluster_name}' in namespace '{self.namespace}'...")
        manifest_yaml = yaml.safe_dump(manifest)
        cmd = ["kubectl", "apply", "-f", "-", "-n", self.namespace]
        result = subprocess.run(
            cmd,
            input=manifest_yaml,
            text=True,
            capture_output=True,
            check=True,
        )
        print(f"[INFO] kubectl apply output: {result.stdout.strip()}")
        return cluster_name

    def submit_eval_job(self, target: GKERayTarget, vllm_url: Optional[str] = None) -> str:
        """
        Submits an evaluation Job to Kueue queue.
        Returns job name.
        """
        job_name = f"eval-job-{target.flavor}"
        if vllm_url is None:
            vllm_url = f"http://ray-{target.flavor}-serve-svc.{self.namespace}.svc.cluster.local:8000/v1"

        gcs_bucket = self.output_gcs_bucket.strip("/")
        if not gcs_bucket.startswith("gs://"):
            output_gcs_path = f"gs://{gcs_bucket}/results/{target.flavor}"
        else:
            output_gcs_path = f"{gcs_bucket}/results/{target.flavor}"

        manifest = render_eval_job_manifest(
            target=target,
            namespace=self.namespace,
            job_name=job_name,
            queue_name=self.queue_name,
            vllm_url=vllm_url,
            output_gcs_path=output_gcs_path,
        )

        if self.dry_run:
            print(f"[DRY RUN] Submitting evaluation Job '{job_name}' in namespace '{self.namespace}'...")
            return job_name

        print(f"[INFO] Submitting evaluation Job '{job_name}' in namespace '{self.namespace}'...")
        manifest_yaml = yaml.safe_dump(manifest)
        cmd = ["kubectl", "apply", "-f", "-", "-n", self.namespace]
        result = subprocess.run(
            cmd,
            input=manifest_yaml,
            text=True,
            capture_output=True,
            check=True,
        )
        print(f"[INFO] kubectl apply output: {result.stdout.strip()}")
        return job_name

    def wait_for_job_completion(
        self,
        job_name: str,
        namespace: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
    ) -> bool:
        """
        Monitors Job execution until completion, failure, or timeout.
        Returns True if job succeeded.
        """
        ns = namespace or self.namespace
        timeout = timeout_seconds if timeout_seconds is not None else self.timeout_seconds

        if self.dry_run:
            print(f"[DRY RUN] Monitoring Job '{job_name}' in namespace '{ns}' (timeout: {timeout}s)...")
            return True

        print(f"[INFO] Waiting for Job '{job_name}' in namespace '{ns}' (timeout: {timeout}s)...")
        start_time = time.time()
        while time.time() - start_time < timeout:
            cmd = ["kubectl", "get", "job", job_name, "-n", ns, "-o", "json"]
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
                job_data = json.loads(proc.stdout)
                status = job_data.get("status", {})

                if status.get("succeeded", 0) > 0:
                    print(f"[INFO] Job '{job_name}' completed successfully.")
                    return True

                if status.get("failed", 0) > 0:
                    print(f"[ERROR] Job '{job_name}' failed.")
                    return False

                for cond in status.get("conditions", []):
                    if cond.get("type") == "Complete" and cond.get("status") == "True":
                        print(f"[INFO] Job '{job_name}' completed successfully.")
                        return True
                    if cond.get("type") == "Failed" and cond.get("status") == "True":
                        print(f"[ERROR] Job '{job_name}' failed: {cond.get('reason', 'Unknown reason')}")
                        return False

            except subprocess.CalledProcessError as e:
                print(f"[WARN] Failed to inspect Job '{job_name}': {e}")

            time.sleep(self.poll_interval_seconds)

        print(f"[ERROR] Timed out waiting for Job '{job_name}' after {timeout} seconds.")
        return False

    def collect_results(self, target: GKERayTarget) -> Dict[str, Any]:
        """
        Downloads and parses evaluation results JSON from GCS.
        Returns result dictionary.
        """
        gcs_bucket = self.output_gcs_bucket.strip("/")
        if not gcs_bucket.startswith("gs://"):
            gcs_path = f"gs://{gcs_bucket}/results/{target.flavor}/eval_results.json"
        else:
            gcs_path = f"{gcs_bucket}/results/{target.flavor}/eval_results.json"

        if self.dry_run:
            return {
                "flavor": target.flavor,
                "status": "COMPLETED",
                "dry_run": True,
                "gcs_path": gcs_path,
                "metrics": {
                    "total_samples": 10,
                    "accuracy": 1.0,
                    "pass_rate": 1.0,
                },
            }

        try:
            from google.cloud import storage
            parts = gcs_path[5:].split("/", 1)
            bucket_name = parts[0]
            blob_name = parts[1] if len(parts) > 1 else ""

            client = storage.Client(project=self.project_id)
            bucket = client.bucket(bucket_name)
            blob = bucket.blob(blob_name)

            if blob.exists():
                content = blob.download_as_text()
                data = json.loads(content)
                return {
                    "flavor": target.flavor,
                    "status": "COMPLETED",
                    "gcs_path": gcs_path,
                    "data": data,
                }
            else:
                return {
                    "flavor": target.flavor,
                    "status": "NOT_FOUND",
                    "gcs_path": gcs_path,
                    "error": "Results blob does not exist in GCS",
                }
        except Exception as e:
            return {
                "flavor": target.flavor,
                "status": "ERROR",
                "gcs_path": gcs_path,
                "error": str(e),
            }

    def teardown_ray_cluster(self, cluster_name: str, namespace: Optional[str] = None) -> None:
        """Deletes RayCluster deployment via kubectl."""
        ns = namespace or self.namespace
        if self.dry_run:
            print(f"[DRY RUN] Tearing down RayCluster '{cluster_name}' in namespace '{ns}'...")
            return

        print(f"[INFO] Tearing down RayCluster '{cluster_name}' in namespace '{ns}'...")
        cmd = ["kubectl", "delete", "raycluster", cluster_name, "-n", ns, "--ignore-not-found=true"]
        subprocess.run(cmd, check=False)

    def run_sweep(
        self,
        models_filter: Optional[Sequence[str]] = None,
        wait: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Runs evaluation sweep over selected models.
        """
        targets = self._filter_targets(models_filter)
        results: List[Dict[str, Any]] = []

        print(f"[INFO] Starting GKE Ray sweep across {len(targets)} target models...")
        for target in targets:
            cluster_name = f"ray-{target.flavor}"
            job_name = f"eval-job-{target.flavor}"
            try:
                self.deploy_ray_cluster(target)
                vllm_url = f"http://ray-{target.flavor}-serve-svc.{self.namespace}.svc.cluster.local:8000/v1"
                self.submit_eval_job(target, vllm_url=vllm_url)

                if wait:
                    success = self.wait_for_job_completion(job_name, self.namespace)
                    res = self.collect_results(target)
                    res["job_success"] = success
                    results.append(res)
                else:
                    results.append({
                        "flavor": target.flavor,
                        "status": "SUBMITTED",
                        "job_name": job_name,
                        "cluster_name": cluster_name,
                    })
            finally:
                if wait and not self.dry_run:
                    self.teardown_ray_cluster(cluster_name, self.namespace)

        return results

    def _filter_targets(self, models_filter: Optional[Sequence[str]] = None) -> List[GKERayTarget]:
        """Filters catalog targets according to requested model names."""
        if not models_filter:
            return list(ALL_GKE_RAY_TARGETS)

        filter_items = [m.strip() for m in models_filter if m.strip()]
        matched: List[GKERayTarget] = []

        for item in filter_items:
            if item in ALL_GKE_RAY_TARGETS_MAP:
                target = ALL_GKE_RAY_TARGETS_MAP[item]
                if target not in matched:
                    matched.append(target)
            else:
                for target in ALL_GKE_RAY_TARGETS:
                    if (
                        target.get_base_flavor() == item
                        or target.flavor.startswith(item)
                        or (item.endswith("*") and target.flavor.startswith(item[:-1]))
                    ):
                        if target not in matched:
                            matched.append(target)

        return matched


def parse_args() -> argparse.Namespace:
    """Parses command line arguments."""
    parser = argparse.ArgumentParser(
        description="GKE Ray & Kueue Model Evaluation Sweep Orchestrator"
    )
    parser.add_argument(
        "--models",
        nargs="*",
        help="Specific model flavor(s) to evaluate (e.g. gemma-3-4b-it, gemma-3-12b-it)",
    )
    parser.add_argument(
        "--namespace",
        default="gemma-benchmarks",
        help="Kubernetes namespace (default: gemma-benchmarks)",
    )
    parser.add_argument(
        "--queue-name",
        default="llm-sweep-queue",
        help="Kueue local queue name (default: llm-sweep-queue)",
    )
    parser.add_argument(
        "--output-gcs-bucket",
        default="dandye-0324-chronicle-soc-benchmarks",
        help="GCS bucket for evaluation artifacts",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform dry run without applying Kubernetes manifests",
    )
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Submit jobs asynchronously without waiting for completion",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=3600,
        help="Per-job timeout in seconds (default: 3600)",
    )
    return parser.parse_args()


def main() -> None:
    """Main entrypoint for CLI invocation."""
    args = parse_args()
    models: Optional[List[str]] = None
    if args.models:
        models = []
        for item in args.models:
            for piece in item.split(","):
                piece = piece.strip()
                if piece:
                    models.append(piece)

    orchestrator = GKERayOrchestrator(
        namespace=args.namespace,
        queue_name=args.queue_name,
        output_gcs_bucket=args.output_gcs_bucket,
        dry_run=args.dry_run,
        timeout_seconds=args.timeout_seconds,
    )
    results = orchestrator.run_sweep(models_filter=models, wait=not args.no_wait)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
