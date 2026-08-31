#!/usr/bin/env python3
"""
Master Cloud Run & Model Serving Comprehensive Benchmark & Evaluation Sweep Orchestrator
Sequentially evaluates all models from Vertex AI evaluation suite on Cloud Run (with scale-to-zero)
and managed baselines:
- Dense Gemma 2, Gemma 3, and Gemma 4 models
- Advanced Inference Optimizations (FP8 quantization, N-Gram Prompt Lookup Speculative Decoding)
- Two-Model Draft Proposer Speculative Decoding
- Partner Models (Llama 3.2, Llama Guard 3, Nemotron 3.5, Nemotron 70B, Inkling Small)
- Frontier Managed Baselines (Gemini 3.7 Flash, Gemini 3.5 Flash-Lite, Gemini 2.5 Pro/Flash, Llama 4 Scout MaaS)
"""

import argparse
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault("GOOGLE_API_USE_CLIENT_CERTIFICATE", "false")

from scripts.eval_soc_agent import run_evaluation


@dataclass
class CloudRunTarget:
    """Specification of an evaluation target."""
    flavor: str
    target_type: str = "cloudrun"  # "cloudrun" or "managed"
    hf_repo: Optional[str] = None
    cpu: int = 4
    memory: str = "16Gi"
    gpu_count: int = 1
    gpu_type: str = "nvidia-l4"
    max_model_len: int = 4096
    gpu_memory_utilization: float = 0.90
    extra_vllm_flags: Optional[str] = None
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
        ]:
            if base.endswith(suffix):
                return base[: -len(suffix)]
        return base


ALL_EVALUATION_TARGETS: List[CloudRunTarget] = [
    # --------------------------------------------------------------------------
    # 1. Frontier Managed Gemini & Llama Baselines (MaaS)
    # --------------------------------------------------------------------------
    CloudRunTarget(
        flavor="gemini-3.7-flash",
        target_type="managed",
        notes="Frontier Managed Gemini 3.7 Flash (Hybrid Reasoning)",
    ),
    CloudRunTarget(
        flavor="gemini-3.5-flash-lite",
        target_type="managed",
        notes="Managed High-Efficiency Tier Baseline",
    ),
    CloudRunTarget(
        flavor="gemini-2.5-pro",
        target_type="managed",
        notes="Frontier Reasoning & Agentic Baseline",
    ),
    CloudRunTarget(
        flavor="gemini-2.5-flash",
        target_type="managed",
        notes="High-Speed Production Baseline",
    ),
    CloudRunTarget(
        flavor="llama-4-scout-17b-16e-instruct-maas",
        target_type="managed",
        notes="Llama 4 Scout 17B-16E MoE via Vertex AI Model-as-a-Service",
    ),

    # --------------------------------------------------------------------------
    # 2. Gemma 3 Family (Dense & Optimizations)
    # --------------------------------------------------------------------------
    CloudRunTarget(
        flavor="gemma-3-1b-it",
        hf_repo="google/gemma-3-1b-it",
        cpu=4,
        memory="16Gi",
        gpu_count=1,
        gpu_type="nvidia-l4",
        max_model_len=4096,
        gpu_memory_utilization=0.90,
        notes="Gemma 3 1B Dense (1x L4, Scale-to-Zero)",
    ),
    CloudRunTarget(
        flavor="gemma-3-1b-it-speculative",
        hf_repo="google/gemma-3-1b-it",
        cpu=4,
        memory="16Gi",
        gpu_count=1,
        gpu_type="nvidia-l4",
        max_model_len=4096,
        extra_vllm_flags="--speculative-model=[ngram] --num-speculative-tokens=5 --ngram-prompt-lookup-max=5 --ngram-prompt-lookup-min=2",
        notes="Gemma 3 1B + N-Gram Speculative Decoding (1x L4)",
    ),
    CloudRunTarget(
        flavor="gemma-3-4b-it",
        hf_repo="google/gemma-3-4b-it",
        cpu=8,
        memory="32Gi",
        gpu_count=1,
        gpu_type="nvidia-l4",
        max_model_len=8192,
        gpu_memory_utilization=0.90,
        notes="Gemma 3 4B Extended Context (1x L4)",
    ),
    CloudRunTarget(
        flavor="gemma-3-4b-it-speculative",
        hf_repo="google/gemma-3-4b-it",
        cpu=8,
        memory="32Gi",
        gpu_count=1,
        gpu_type="nvidia-l4",
        max_model_len=8192,
        extra_vllm_flags="--speculative-model=[ngram] --num-speculative-tokens=5 --ngram-prompt-lookup-max=5 --ngram-prompt-lookup-min=2",
        notes="Gemma 3 4B + N-Gram Speculative Decoding (1x L4)",
    ),
    CloudRunTarget(
        flavor="gemma-3-12b-it-fp8",
        hf_repo="google/gemma-3-12b-it",
        cpu=8,
        memory="32Gi",
        gpu_count=1,
        gpu_type="nvidia-l4",
        max_model_len=8192,
        extra_vllm_flags="--quantization=fp8",
        notes="Gemma 3 12B FP8 Quantized (1x L4)",
    ),
    CloudRunTarget(
        flavor="gemma-3-12b-it",
        hf_repo="google/gemma-3-12b-it",
        cpu=20,
        memory="80Gi",
        gpu_count=1,
        gpu_type="nvidia-rtx-pro-6000",
        max_model_len=8192,
        notes="Gemma 3 12B Multimodal (1x RTX PRO 6000 96GB)",
    ),
    CloudRunTarget(
        flavor="gemma-3-12b-it-draft-1b",
        hf_repo="google/gemma-3-12b-it",
        cpu=20,
        memory="80Gi",
        gpu_count=1,
        gpu_type="nvidia-rtx-pro-6000",
        max_model_len=8192,
        extra_vllm_flags="--speculative-model=google/gemma-3-1b-it --num-speculative-tokens=5",
        notes="Gemma 3 12B + Gemma 3 1B Draft Proposer (1x RTX PRO 6000)",
    ),
    CloudRunTarget(
        flavor="gemma-3-27b-it",
        hf_repo="google/gemma-3-27b-it",
        cpu=20,
        memory="80Gi",
        gpu_count=1,
        gpu_type="nvidia-rtx-pro-6000",
        max_model_len=8192,
        notes="Gemma 3 27B Multimodal (1x RTX PRO 6000 96GB)",
    ),
    CloudRunTarget(
        flavor="gemma-3-27b-it-fp8",
        hf_repo="google/gemma-3-27b-it",
        cpu=20,
        memory="80Gi",
        gpu_count=1,
        gpu_type="nvidia-rtx-pro-6000",
        max_model_len=8192,
        extra_vllm_flags="--quantization=fp8",
        notes="Gemma 3 27B FP8 Quantized (1x RTX PRO 6000)",
    ),
    CloudRunTarget(
        flavor="gemma-3-27b-it-draft-4b",
        hf_repo="google/gemma-3-27b-it",
        cpu=20,
        memory="80Gi",
        gpu_count=1,
        gpu_type="nvidia-rtx-pro-6000",
        max_model_len=8192,
        extra_vllm_flags="--speculative-model=google/gemma-3-4b-it --num-speculative-tokens=5",
        notes="Gemma 3 27B + Gemma 3 4B Draft Proposer (1x RTX PRO 6000)",
    ),
    CloudRunTarget(
        flavor="gemma-3-27b-it-draft-1b",
        hf_repo="google/gemma-3-27b-it",
        cpu=20,
        memory="80Gi",
        gpu_count=1,
        gpu_type="nvidia-rtx-pro-6000",
        max_model_len=8192,
        extra_vllm_flags="--speculative-model=google/gemma-3-1b-it --num-speculative-tokens=5",
        notes="Gemma 3 27B + Gemma 3 1B Draft Proposer (1x RTX PRO 6000)",
    ),

    # --------------------------------------------------------------------------
    # 3. Gemma 4 Family (Dense, Speculative & Draft Proposer)
    # --------------------------------------------------------------------------
    CloudRunTarget(
        flavor="gemma-4-e2b-it",
        hf_repo="google/gemma-4-e2b-it",
        cpu=4,
        memory="16Gi",
        gpu_count=1,
        gpu_type="nvidia-l4",
        max_model_len=4096,
        gpu_memory_utilization=0.90,
        notes="Gemma 4 Edge 2.3B Serverless (1x L4)",
    ),
    CloudRunTarget(
        flavor="gemma-4-e2b-it-speculative",
        hf_repo="google/gemma-4-e2b-it",
        cpu=4,
        memory="16Gi",
        gpu_count=1,
        gpu_type="nvidia-l4",
        max_model_len=4096,
        extra_vllm_flags="--speculative-model=[ngram] --num-speculative-tokens=5 --ngram-prompt-lookup-max=5 --ngram-prompt-lookup-min=2",
        notes="Gemma 4 E2B + N-Gram Speculative Decoding (1x L4)",
    ),
    CloudRunTarget(
        flavor="gemma-4-e4b-it",
        hf_repo="google/gemma-4-e4b-it",
        cpu=8,
        memory="32Gi",
        gpu_count=1,
        gpu_type="nvidia-l4",
        max_model_len=8192,
        gpu_memory_utilization=0.90,
        notes="Gemma 4 Edge 4.5B Serverless (1x L4)",
    ),
    CloudRunTarget(
        flavor="gemma-4-e4b-it-speculative",
        hf_repo="google/gemma-4-e4b-it",
        cpu=8,
        memory="32Gi",
        gpu_count=1,
        gpu_type="nvidia-l4",
        max_model_len=8192,
        extra_vllm_flags="--speculative-model=[ngram] --num-speculative-tokens=5 --ngram-prompt-lookup-max=5 --ngram-prompt-lookup-min=2",
        notes="Gemma 4 E4B + N-Gram Speculative Decoding (1x L4)",
    ),
    CloudRunTarget(
        flavor="gemma-4-31b-it",
        hf_repo="google/gemma-4-31b-it",
        cpu=20,
        memory="80Gi",
        gpu_count=1,
        gpu_type="nvidia-rtx-pro-6000",
        max_model_len=8192,
        notes="Gemma 4 31B Multimodal Reasoner (1x RTX PRO 6000 96GB)",
    ),
    CloudRunTarget(
        flavor="gemma-4-31b-it-speculative",
        hf_repo="google/gemma-4-31b-it",
        cpu=20,
        memory="80Gi",
        gpu_count=1,
        gpu_type="nvidia-rtx-pro-6000",
        max_model_len=8192,
        extra_vllm_flags="--speculative-model=[ngram] --num-speculative-tokens=5 --ngram-prompt-lookup-max=5 --ngram-prompt-lookup-min=2",
        notes="Gemma 4 31B + N-Gram Speculative Decoding (1x RTX PRO 6000)",
    ),
    CloudRunTarget(
        flavor="gemma-4-31b-it-draft-e2b",
        hf_repo="google/gemma-4-31b-it",
        cpu=20,
        memory="80Gi",
        gpu_count=1,
        gpu_type="nvidia-rtx-pro-6000",
        max_model_len=8192,
        extra_vllm_flags="--speculative-model=google/gemma-4-e2b-it --num-speculative-tokens=5",
        notes="Gemma 4 31B + Gemma 4 E2B Draft Proposer (1x RTX PRO 6000)",
    ),
    CloudRunTarget(
        flavor="gemma-4-31b-it-draft-e4b",
        hf_repo="google/gemma-4-31b-it",
        cpu=20,
        memory="80Gi",
        gpu_count=1,
        gpu_type="nvidia-rtx-pro-6000",
        max_model_len=8192,
        extra_vllm_flags="--speculative-model=google/gemma-4-e4b-it --num-speculative-tokens=5",
        notes="Gemma 4 31B + Gemma 4 E4B Draft Proposer (1x RTX PRO 6000)",
    ),

    # --------------------------------------------------------------------------
    # 4. Gemma 2 Family (Dense & Optimizations)
    # --------------------------------------------------------------------------
    CloudRunTarget(
        flavor="gemma-2-2b-it",
        hf_repo="google/gemma-2-2b-it",
        cpu=4,
        memory="16Gi",
        gpu_count=1,
        gpu_type="nvidia-l4",
        max_model_len=4096,
        gpu_memory_utilization=0.90,
        notes="Gemma 2 2.6B Dense (1x L4)",
    ),
    CloudRunTarget(
        flavor="gemma-2-2b-it-speculative",
        hf_repo="google/gemma-2-2b-it",
        cpu=4,
        memory="16Gi",
        gpu_count=1,
        gpu_type="nvidia-l4",
        max_model_len=4096,
        extra_vllm_flags="--speculative-model=[ngram] --num-speculative-tokens=5 --ngram-prompt-lookup-max=5 --ngram-prompt-lookup-min=2",
        notes="Gemma 2 2B + N-Gram Speculative Decoding (1x L4)",
    ),
    CloudRunTarget(
        flavor="gemma-2-9b-it",
        hf_repo="google/gemma-2-9b-it",
        cpu=8,
        memory="32Gi",
        gpu_count=1,
        gpu_type="nvidia-l4",
        max_model_len=4096,
        gpu_memory_utilization=0.95,
        notes="Gemma 2 9B Dense (1x L4)",
    ),
    CloudRunTarget(
        flavor="gemma-2-9b-it-fp8",
        hf_repo="google/gemma-2-9b-it",
        cpu=8,
        memory="32Gi",
        gpu_count=1,
        gpu_type="nvidia-l4",
        max_model_len=4096,
        extra_vllm_flags="--quantization=fp8",
        notes="Gemma 2 9B FP8 Quantized (1x L4)",
    ),
    CloudRunTarget(
        flavor="gemma-2-9b-it-speculative",
        hf_repo="google/gemma-2-9b-it",
        cpu=8,
        memory="32Gi",
        gpu_count=1,
        gpu_type="nvidia-l4",
        max_model_len=4096,
        extra_vllm_flags="--speculative-model=[ngram] --num-speculative-tokens=5 --ngram-prompt-lookup-max=5 --ngram-prompt-lookup-min=2",
        notes="Gemma 2 9B + N-Gram Speculative Decoding (1x L4)",
    ),
    CloudRunTarget(
        flavor="gemma-2-27b-it",
        hf_repo="google/gemma-2-27b-it",
        cpu=20,
        memory="80Gi",
        gpu_count=1,
        gpu_type="nvidia-rtx-pro-6000",
        max_model_len=8192,
        notes="Gemma 2 27B Dense (1x RTX PRO 6000 96GB)",
    ),
    CloudRunTarget(
        flavor="gemma-2-27b-it-fp8",
        hf_repo="google/gemma-2-27b-it",
        cpu=20,
        memory="80Gi",
        gpu_count=1,
        gpu_type="nvidia-rtx-pro-6000",
        max_model_len=8192,
        extra_vllm_flags="--quantization=fp8",
        notes="Gemma 2 27B FP8 Quantized (1x RTX PRO 6000)",
    ),

    # --------------------------------------------------------------------------
    # 5. Partner & Industry Models
    # --------------------------------------------------------------------------
    CloudRunTarget(
        flavor="llama-3.2-1b-instruct",
        hf_repo="meta-llama/Llama-3.2-1B-Instruct",
        cpu=4,
        memory="16Gi",
        gpu_count=1,
        gpu_type="nvidia-l4",
        max_model_len=4096,
        notes="Meta Llama 3.2 1B (1x L4)",
    ),
    CloudRunTarget(
        flavor="llama-3.2-3b-instruct",
        hf_repo="meta-llama/Llama-3.2-3B-Instruct",
        cpu=4,
        memory="16Gi",
        gpu_count=1,
        gpu_type="nvidia-l4",
        max_model_len=4096,
        notes="Meta Llama 3.2 3B (1x L4)",
    ),
    CloudRunTarget(
        flavor="llama-guard-3-8b",
        hf_repo="meta-llama/Llama-Guard-3-8B",
        cpu=8,
        memory="32Gi",
        gpu_count=1,
        gpu_type="nvidia-l4",
        max_model_len=4096,
        notes="Meta Llama Guard 3 8B (1x L4)",
    ),
    CloudRunTarget(
        flavor="nemotron-3.5-lightning-bf16",
        hf_repo="nvidia/Nemotron-3.5-Lightning-BF16",
        cpu=20,
        memory="80Gi",
        gpu_count=1,
        gpu_type="nvidia-rtx-pro-6000",
        max_model_len=8192,
        notes="NVIDIA Nemotron 30B MoE (1x RTX PRO 6000)",
    ),
    CloudRunTarget(
        flavor="llama-3.1-nemotron-70b-instruct",
        hf_repo="nvidia/Llama-3.1-Nemotron-70B-Instruct-HF",
        cpu=20,
        memory="80Gi",
        gpu_count=1,
        gpu_type="nvidia-rtx-pro-6000",
        max_model_len=8192,
        extra_vllm_flags="--quantization=fp8",
        notes="NVIDIA Tuned Llama 70B FP8 (1x RTX PRO 6000)",
    ),
    CloudRunTarget(
        flavor="inkling-small",
        hf_repo="thinking-machines/inkling-small",
        cpu=20,
        memory="80Gi",
        gpu_count=1,
        gpu_type="nvidia-rtx-pro-6000",
        max_model_len=8192,
        notes="Thinking Machines Inkling Small (1x RTX PRO 6000)",
    ),
]


class ComprehensiveSweepOrchestrator:
    """Manages sequential deployment, benchmarking, evaluation, and cleanup across all targets."""

    def __init__(
        self,
        project_id: str = "secops-demo-env",
        region: str = "europe-west4",
        dry_run: bool = False,
        hf_token: Optional[str] = None,
    ):
        self.project_id = project_id
        self.region = region
        self.dry_run = dry_run
        self.hf_token = hf_token or os.environ.get("HF_TOKEN", "")
        self.evalset_path = ROOT_DIR / "configs" / "evals" / "soc_tier1_evalset.json"
        self.output_dir = ROOT_DIR / "docs" / "soc_eval_results"

    def get_service_name(self, target: CloudRunTarget) -> str:
        """Converts model flavor to a valid Cloud Run service name (lowercase, alphanumeric/dashes, <=63 chars)."""
        clean = target.flavor.replace(".", "-").replace("_", "-").lower()
        return f"{clean[:45]}-cr"

    def deploy_service(self, target: CloudRunTarget) -> str:
        """Deploys a Cloud Run service with GPU and scale-to-zero."""
        service_name = self.get_service_name(target)
        if self.dry_run:
            print(f"[DRY RUN] Deploying Cloud Run service {service_name} ({self.region})...")
            return f"https://{service_name}-dryrun.{self.region}.run.app"

        print(f"\n[INFO] Deploying Cloud Run service '{service_name}' ({target.flavor}) in '{self.region}'...")
        env_vars = f"MODEL_ID={target.hf_repo}"
        if self.hf_token:
            env_vars += f",HF_TOKEN={self.hf_token}"

        args_list = [
            f"--model={target.hf_repo}",
            "--port=8080",
            "--enforce-eager",
            f"--tensor-parallel-size=1",
            f"--gpu-memory-utilization={target.gpu_memory_utilization}",
            f"--max-model-len={target.max_model_len}",
        ]
        if target.extra_vllm_flags:
            args_list.extend(target.extra_vllm_flags.split())

        args = ",".join(args_list)

        cmd = [
            "gcloud", "run", "deploy", service_name,
            f"--project={self.project_id}",
            f"--region={self.region}",
            "--image=vllm/vllm-openai:latest",
            f"--args={args}",
            f"--set-env-vars={env_vars}",
            f"--gpu={target.gpu_count}",
            f"--gpu-type={target.gpu_type}",
            "--no-gpu-zonal-redundancy",
            f"--cpu={target.cpu}",
            f"--memory={target.memory}",
            "--min-instances=0",
            "--max-instances=1",
            "--no-cpu-throttling",
            "--timeout=900",
            "--startup-probe=timeoutSeconds=10,periodSeconds=10,failureThreshold=60,tcpSocket.port=8080",
            "--allow-unauthenticated",
            "--quiet",
        ]

        print(f"[CMD] {' '.join(cmd)}")
        subprocess.run(cmd, check=True, timeout=1200)

        # Retrieve service URL
        url_cmd = [
            "gcloud", "run", "services", "describe", service_name,
            f"--project={self.project_id}",
            f"--region={self.region}",
            "--format=value(status.url)",
        ]
        res = subprocess.run(url_cmd, capture_output=True, text=True, check=True)
        url = res.stdout.strip()
        print(f"[SUCCESS] Cloud Run Service URL: {url}")
        return url

    def measure_cold_start(self, url: str, target: CloudRunTarget) -> float:
        """Sends an initial completion request to trigger cold start scale-up (0 -> 1)."""
        if self.dry_run:
            print("[DRY RUN] Simulating cold start measurement...")
            return 8.5

        print(f"[INFO] Measuring Cold Start latency on {url}...")
        model_id = target.hf_repo or "google/gemma-3-1b-it"
        prompt_payload = {
            "model": model_id,
            "messages": [{"role": "user", "content": "Hello! Reply with OK."}],
            "max_tokens": 10,
        }
        endpoint = f"{url}/v1/chat/completions"
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(prompt_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        start = time.perf_counter()
        with urllib.request.urlopen(req, timeout=300) as response:
            _ = response.read()
        cold_latency = time.perf_counter() - start
        print(f"[COLD START] 0 -> 1 instance spin-up + inference completed in {cold_latency:.2f} s")
        return round(cold_latency, 2)

    def teardown_service(self, service_name: str) -> None:
        """Deletes the Cloud Run service to prevent any lingering state."""
        if self.dry_run:
            print(f"[DRY RUN] Deleting Cloud Run service {service_name}...")
            return

        print(f"[CLEANUP] Deleting Cloud Run service '{service_name}' in {self.region}...")
        cmd = [
            "gcloud", "run", "services", "delete", service_name,
            f"--project={self.project_id}",
            f"--region={self.region}",
            "--quiet",
        ]
        try:
            subprocess.run(cmd, check=True, timeout=120)
            print(f"[CLEANUP SUCCESS] Service {service_name} deleted.")
        except Exception as e:
            print(f"[CLEANUP WARNING] Failed to delete {service_name}: {e}")

    def evaluate_target(self, target: CloudRunTarget) -> Dict[str, Any]:
        """Orchestrates deployment, cold-start, benchmark, SOC evaluation, and teardown."""
        service_name = self.get_service_name(target)
        url = None
        cold_start_s = 0.0

        try:
            if target.target_type == "managed":
                print(f"\n[EVAL] Running un-spoiled SOC Tier 1 Evaluation for managed model '{target.flavor}'...")
                if self.dry_run:
                    eval_data = {
                        "flavor": target.flavor,
                        "summary": {
                            "total_cases": 5, "passed_cases": 5, "pass_rate": 100.0,
                            "avg_rubric_score": 98.0, "avg_latency_s": 3.2,
                            "total_tokens": 12000, "avg_tokens_per_case": 2400.0,
                            "avg_generation_tps": 115.0, "avg_total_tps": 350.0,
                            "total_tool_calls": 9,
                        },
                        "case_results": [],
                    }
                else:
                    eval_data = run_evaluation(
                        evalset_path=self.evalset_path,
                        flavor=target.flavor,
                        managed_model=target.flavor,
                        project_id=self.project_id,
                        region="us-central1",
                        use_live_mcp=False,
                    )
            else:
                url = self.deploy_service(target)
                cold_start_s = self.measure_cold_start(url, target)

                if self.dry_run:
                    print(f"[DRY RUN] Running SOC evaluation for {target.flavor} on Cloud Run...")
                    eval_data = {
                        "flavor": f"{target.flavor}-cloudrun",
                        "summary": {
                            "total_cases": 5, "passed_cases": 4, "pass_rate": 80.0,
                            "avg_rubric_score": 88.0, "avg_latency_s": 10.5,
                            "total_tokens": 12000, "avg_tokens_per_case": 2400.0,
                            "avg_generation_tps": 55.0, "avg_total_tps": 180.0,
                            "total_tool_calls": 6,
                        },
                        "case_results": [],
                    }
                else:
                    print(f"\n[EVAL] Running un-spoiled SOC Tier 1 Evaluation for {target.flavor} against Cloud Run...")
                    eval_data = run_evaluation(
                        evalset_path=self.evalset_path,
                        flavor=f"{target.flavor}-cloudrun",
                        cloudrun_url=url,
                        managed_model=target.hf_repo,
                        project_id=self.project_id,
                        region=self.region,
                        use_live_mcp=False,
                    )

            self.output_dir.mkdir(parents=True, exist_ok=True)
            report_md_path = self.output_dir / f"{target.flavor}-cloudrun_report.md"
            report_json_path = self.output_dir / f"{target.flavor}-cloudrun_report.json"

            eval_data["summary"]["cold_start_latency_s"] = cold_start_s
            eval_data["summary"]["region"] = self.region if target.target_type == "cloudrun" else "us-central1"
            eval_data["summary"]["target_type"] = target.target_type
            eval_data["summary"]["notes"] = target.notes

            with open(report_json_path, "w", encoding="utf-8") as f:
                json.dump(eval_data, f, indent=2)

            lines = [
                f"# SOC Evaluation Report: {target.flavor} ({'Cloud Run Serverless GPU' if target.target_type == 'cloudrun' else 'Vertex AI Model-as-a-Service'})",
                f"\n**Date:** {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
                f"**Deployment Platform:** {'Cloud Run (Serverless GPU, Scale-to-Zero)' if target.target_type == 'cloudrun' else 'Vertex AI MaaS'}",
                f"**Region:** {self.region if target.target_type == 'cloudrun' else 'us-central1'}",
                f"**Hardware:** {target.gpu_count}x {target.gpu_type}" if target.target_type == "cloudrun" else "**Hardware:** Hosted Managed Model",
                f"**Cold Start Latency (0 -> 1 instance):** {cold_start_s:.2f} s" if target.target_type == "cloudrun" else "**Cold Start:** 0.00 s (Managed)",
                f"**Notes:** {target.notes}",
                "\n## 1. Executive Summary",
                f"- **Pass Rate:** {eval_data['summary']['pass_rate']}% ({eval_data['summary']['passed_cases']}/{eval_data['summary']['total_cases']})",
                f"- **Average Rubric Score:** {eval_data['summary']['avg_rubric_score']} / 100",
                f"- **Average Latency:** {eval_data['summary']['avg_latency_s']} s",
                f"- **Output Throughput (Generation TPS):** {eval_data['summary'].get('avg_generation_tps', 0.0)} tok/s",
                f"- **Total Processing Throughput:** {eval_data['summary'].get('avg_total_tps', 0.0)} tok/s",
                f"- **Total Token Usage:** {eval_data['summary']['total_tokens']} tokens (Avg: {eval_data['summary']['avg_tokens_per_case']} tok/case)",
                f"- **Total Tool Invocations:** {eval_data['summary']['total_tool_calls']}",
                "\n## 2. Evaluation Scorecard Matrix\n",
                "| Case ID | Case Name | Rubric Score | Grounding | Status | Latency | Gen TPS | Total Tokens | Tool Calls |",
                "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
            ]

            for c in eval_data.get("case_results", []):
                status_str = "PASS" if c["passed"] else "FAIL"
                tok = c.get("usage", {}).get("total_tokens", 0)
                gen_tps = c.get("generation_tps", 0.0)
                tools_cnt = len(c.get("trajectory", []))
                lines.append(
                    f"| {c['eval_id']} | {c['name']} | {c['rubric_score']}/100 | "
                    f"{c['grounding_score']:.2f} | {status_str} | {c['latency_s']:.2f}s | {gen_tps} tok/s | {tok} | {tools_cnt} |"
                )

            with open(report_md_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))

            print(f"[SUCCESS] Saved evaluation report to: {report_md_path}")
            return eval_data

        finally:
            if url and not self.dry_run:
                self.teardown_service(service_name)

    def run_sweep(self, model_filter: Optional[List[str]] = None) -> None:
        """Runs the sequential sweep across targets."""
        targets = ALL_EVALUATION_TARGETS
        if model_filter:
            targets = [t for t in targets if t.flavor in model_filter]

        print("===========================================================================")
        print(f" STARTING COMPREHENSIVE CLOUD RUN & MANAGED SWEEP ({len(targets)} targets)")
        print(f" Project: {self.project_id} | Region: {self.region}")
        print("===========================================================================")

        results = []
        for i, target in enumerate(targets, 1):
            print(f"\n>>> [{i}/{len(targets)}] Starting evaluation: {target.flavor} ({target.target_type}) <<<")
            try:
                res = self.evaluate_target(target)
                results.append(res)
            except Exception as e:
                print(f"[ERROR] Evaluation failed for target {target.flavor}: {e}")

        print("\n===========================================================================")
        print(" COMPREHENSIVE SWEEP COMPLETED")
        print(f" Total evaluated: {len(targets)} | Successful runs: {len(results)} / {len(targets)}")
        print("===========================================================================")


def main():
    parser = argparse.ArgumentParser(description="Comprehensive Benchmark & SOC Evaluation Sweep")
    parser.add_argument("--models", nargs="*", default=None, help="Filter specific model flavors to evaluate")
    parser.add_argument("--project-id", default=os.environ.get("GCP_PROJECT_ID", "secops-demo-env"))
    parser.add_argument("--region", default=os.environ.get("GCP_REGION", "europe-west4"))
    parser.add_argument("--dry-run", action="store_true", help="Perform a dry run without actual GCP deployments")
    args = parser.parse_args()

    orchestrator = ComprehensiveSweepOrchestrator(
        project_id=args.project_id,
        region=args.region,
        dry_run=args.dry_run,
    )
    orchestrator.run_sweep(model_filter=args.models)


if __name__ == "__main__":
    main()
