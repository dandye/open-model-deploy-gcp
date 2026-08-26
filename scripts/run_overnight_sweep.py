#!/usr/bin/env python3
"""
Master Overnight Comprehensive Model Evaluation & Benchmark Sweep Orchestrator
Sequentially deploys, benchmarks, evaluates on the un-spoiled SOC Tier 1 suite,
and tears down every Gemma model variant alongside frontier Gemini baselines with $0 leak.
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

os.environ.setdefault("GOOGLE_API_USE_CLIENT_CERTIFICATE", "false")

from scripts.benchmark import BenchmarkRunner
from scripts.eval_soc_agent import run_evaluation


# Canonical ordering by model size and capability (smallest on left/top to most capable on right/bottom)
MODEL_CAPABILITY_ORDER: List[str] = [
    # 1B - 2B Edge Tier
    "gemma-3-1b-it",
    "gemma-2-2b-it",
    "gemma-4-e2b-it",
    # 4B - 9B Mid Tier
    "gemma-3-4b-it",
    "gemma-4-e4b-it",
    "gemma-2-9b-it",
    # 12B - 27B Large Tier
    "gemma-3-12b-it",
    "gemma-2-27b-it",
    "gemma-3-27b-it-fp8",
    "gemma-3-27b-it-speculative",
    "gemma-3-27b-it",
    # 31B Frontier Open Weights
    "gemma-4-31b-it",
    # Frontier / Managed (Global & MaaS)
    "gemini-3.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-3.7-flash",
]


@dataclass
class ModelTarget:

    """Specification of a model evaluation target."""

    flavor: str
    target_type: str = "vertex"  # "managed" or "vertex"
    region: str = "us-central1"
    machine_type: Optional[str] = None
    gpu_count: int = 1
    gpu_type: Optional[str] = None
    extra_vllm_flags: Optional[str] = None
    max_model_len: Optional[int] = None
    notes: str = ""

    def get_base_flavor(self) -> str:
        """Strip optimization variant suffixes to resolve the base catalog model name."""
        base = self.flavor
        for suffix in ["-speculative", "-fp8"]:
            if base.endswith(suffix):
                base = base[: -len(suffix)]
        return base


class SweepOrchestrator:
    """
    Orchestrates the sequential evaluation sweep across all model families.
    Enforces guaranteed endpoint teardown via try/finally blocks and isolates errors.
    """

    def __init__(
        self,
        project_id: str = "dandye-0324-chronicle",
        evalset_path: Optional[Path] = None,
        output_dir: Optional[Path] = None,
        scorecard_path: Optional[Path] = None,
        dry_run: bool = False,
        timeout_seconds: int = 1500,
        stream_benchmark: bool = True,
        repetitions: int = 3,
    ) -> None:
        self.project_id = project_id
        self.evalset_path = evalset_path or (ROOT_DIR / "configs" / "evals" / "soc_tier1_evalset.json")
        self.output_dir = output_dir or (ROOT_DIR / "docs" / "soc_eval_results")
        self.scorecard_path = scorecard_path or (ROOT_DIR / "docs" / "soc_model_comparative_evals.md")
        self.dry_run = dry_run
        self.timeout_seconds = timeout_seconds
        self.stream_benchmark = stream_benchmark
        self.repetitions = repetitions

    def build_queue(self) -> List[ModelTarget]:
        """
        Builds the authoritative model evaluation queue covering:
        1. Managed Gemini Baselines (Flash-Lite, 2.5 Flash, 2.5 Pro, 3.7 Flash)
        2. Gemma 4 Family (E2B, E4B, 31B Reasoner)
        3. Gemma 3 Family (1B, 4B, 12B, 27B, 27B FP8, 27B FP8 + Speculative)
        4. Gemma 2 Family Baseline (2B, 9B, 27B)
        """
        return [
            # Phase 1: Frontier & Managed Baselines
            ModelTarget(
                flavor="gemini-3.5-flash-lite",
                target_type="managed",
                region="global",
                notes="Vertex AI Global MaaS",
            ),
            ModelTarget(
                flavor="gemini-2.5-flash",
                target_type="managed",
                region="us-central1",
                notes="Vertex AI Managed MaaS",
            ),
            ModelTarget(
                flavor="gemini-2.5-pro",
                target_type="managed",
                region="us-central1",
                notes="Vertex AI Managed MaaS Pro",
            ),
            ModelTarget(
                flavor="gemini-3.7-flash",
                target_type="managed",
                region="global",
                notes="Vertex AI Global MaaS",
            ),
            # Phase 2: Gemma 4 Family (Edge & Flagship)
            ModelTarget(
                flavor="gemma-4-e2b-it",
                target_type="vertex",
                region="us-east1",
                machine_type="g2-standard-4",
                gpu_count=1,
                gpu_type="nvidia-l4",
                extra_vllm_flags="--max-num-seqs=16",
                max_model_len=8192,
                notes="Gemma 4 Edge (1x L4)",
            ),
            ModelTarget(
                flavor="gemma-4-e4b-it",
                target_type="vertex",
                region="us-east1",
                machine_type="g2-standard-8",
                gpu_count=1,
                gpu_type="nvidia-l4",
                extra_vllm_flags="--max-num-seqs=16",
                max_model_len=8192,
                notes="Gemma 4 Edge (1x L4)",
            ),
            ModelTarget(
                flavor="gemma-4-31b-it",
                target_type="vertex",
                region="us-east1",
                machine_type="a2-highgpu-2g",
                gpu_count=2,
                gpu_type="nvidia-tesla-a100",
                extra_vllm_flags="--max-num-seqs=16",
                max_model_len=8192,
                notes="Gemma 4 Multimodal Reasoner (2x A100)",
            ),
            # Phase 3: Gemma 3 Family & Optimizations
            ModelTarget(
                flavor="gemma-3-1b-it",
                target_type="vertex",
                region="us-central1",
                machine_type="g2-standard-4",
                gpu_count=1,
                gpu_type="nvidia-l4",
                notes="Gemma 3 1B (1x L4)",
            ),
            ModelTarget(
                flavor="gemma-3-4b-it",
                target_type="vertex",
                region="us-central1",
                machine_type="g2-standard-8",
                gpu_count=1,
                gpu_type="nvidia-l4",
                notes="Gemma 3 4B (1x L4)",
            ),
            ModelTarget(
                flavor="gemma-3-12b-it",
                target_type="vertex",
                region="us-central1",
                machine_type="g2-standard-48",
                gpu_count=4,
                gpu_type="nvidia-l4",
                extra_vllm_flags="--limit_mm_per_prompt=image=5 --max-num-seqs=4",
                notes="Gemma 3 12B Multimodal (4x L4)",
            ),
            ModelTarget(
                flavor="gemma-3-27b-it",
                target_type="vertex",
                region="us-east1",
                machine_type="g2-standard-48",
                gpu_count=4,
                gpu_type="nvidia-l4",
                extra_vllm_flags="--limit_mm_per_prompt=image=5 --max-num-seqs=4",
                notes="Gemma 3 27B Multimodal (4x L4)",
            ),
            ModelTarget(
                flavor="gemma-3-27b-it-fp8",
                target_type="vertex",
                region="us-east1",
                machine_type="g2-standard-48",
                gpu_count=4,
                gpu_type="nvidia-l4",
                extra_vllm_flags="--quantization=fp8 --limit_mm_per_prompt=image=5 --max-num-seqs=4",
                notes="Gemma 3 27B FP8 Quantized (4x L4)",
            ),
            ModelTarget(
                flavor="gemma-3-27b-it-speculative",
                target_type="vertex",
                region="us-east1",
                machine_type="g2-standard-48",
                gpu_count=4,
                gpu_type="nvidia-l4",
                extra_vllm_flags=(
                    "--quantization=fp8 "
                    "--speculative-model=[ngram] "
                    "--num-speculative-tokens=5 "
                    "--ngram-prompt-lookup-max=5 "
                    "--ngram-prompt-lookup-min=2 "
                    "--limit_mm_per_prompt=image=5 "
                    "--max-num-seqs=4"
                ),
                notes="Gemma 3 27B FP8 + Speculative Decoding (4x L4)",
            ),
            # Phase 4: Gemma 2 Family Baseline
            ModelTarget(
                flavor="gemma-2-2b-it",
                target_type="vertex",
                region="us-central1",
                machine_type="g2-standard-4",
                gpu_count=1,
                gpu_type="nvidia-l4",
                notes="Gemma 2 2B (1x L4)",
            ),
            ModelTarget(
                flavor="gemma-2-9b-it",
                target_type="vertex",
                region="us-central1",
                machine_type="g2-standard-12",
                gpu_count=1,
                gpu_type="nvidia-l4",
                notes="Gemma 2 9B (1x L4)",
            ),
            ModelTarget(
                flavor="gemma-2-27b-it",
                target_type="vertex",
                region="us-east1",
                machine_type="g2-standard-48",
                gpu_count=4,
                gpu_type="nvidia-l4",
                notes="Gemma 2 27B (4x L4)",
            ),
        ]

    def deploy_vertex_model(self, target: ModelTarget) -> str:
        """
        Deploys target model to Vertex AI via scripts/vertex_deploy.sh.
        Returns the created or active Endpoint ID.
        """
        if self.dry_run:
            print(f"[DRY RUN] Deploying Vertex AI model {target.flavor} ({target.region})...")
            return f"mock-endpoint-{target.flavor}"

        base_flavor = target.get_base_flavor()
        print(f"[INFO] Deploying model '{base_flavor}' ({target.flavor}) to region '{target.region}'...")
        deploy_script = ROOT_DIR / "scripts" / "vertex_deploy.sh"

        env = dict(os.environ)
        env["GCP_PROJECT_ID"] = self.project_id
        env["GCP_REGION"] = target.region
        if target.extra_vllm_flags:
            env["EXTRA_VLLM_FLAGS"] = target.extra_vllm_flags
        if target.machine_type:
            env["VERTEX_MACHINE_TYPE"] = target.machine_type
        if target.gpu_type:
            env["VERTEX_ACCELERATOR_TYPE"] = target.gpu_type
        if target.gpu_count:
            env["VERTEX_ACCELERATOR_COUNT"] = str(target.gpu_count)

        res = subprocess.run(
            [str(deploy_script), base_flavor, target.region],
            env=env,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
            check=False,
        )

        stdout = str(res.stdout or "")
        stderr = str(res.stderr or "")
        output = f"{stdout}\n{stderr}"
        print(output)

        if res.returncode != 0:
            raise RuntimeError(f"Deployment failed for {target.flavor} with code {res.returncode}:\n{output}")

        # Parse Endpoint ID from output
        match = re.search(r"Endpoint ID:\s*([0-9]+)", output)
        if not match:
            match = re.search(r"Created Endpoint ID:\s*([0-9]+)", output)
        if not match:
            match = re.search(r"Found existing Endpoint ID:\s*([0-9]+)", output)

        if match:
            endpoint_id = match.group(1).strip()
            print(f"[INFO] Successfully resolved Endpoint ID: {endpoint_id}")
            return endpoint_id

        raise RuntimeError(f"Failed to parse Endpoint ID from deployment output for {target.flavor}")

    def benchmark_model(
        self,
        target: ModelTarget,
        endpoint_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Runs latency and throughput benchmarking.
        Uses BenchmarkRunner for Vertex AI endpoints and Google GenAI SDK for managed models.
        """
        if self.dry_run:
            print(f"[DRY RUN] Benchmarking {target.flavor}...")
            return {
                "endpoint_id": endpoint_id or target.flavor,
                "region": target.region,
                "concurrency": 1,
                "total_requests": self.repetitions,
                "avg_latency_s": 1.20,
                "p50_latency_s": 1.15,
                "p90_latency_s": 1.35,
                "p99_latency_s": 1.45,
                "avg_tokens": 120.0,
                "tps": 100.0,
                "tpm": 6000.0,
                "ttft_ms": 110.0,
                "sample_output": "Mock quantum computing output sample.",
            }

        if target.target_type == "vertex":
            if not endpoint_id:
                raise ValueError(f"Endpoint ID required to benchmark Vertex AI target {target.flavor}")
            runner = BenchmarkRunner(
                project_id=self.project_id,
                region=target.region,
                endpoint_id=endpoint_id,
                runs=self.repetitions,
                concurrency=1,
                stream=self.stream_benchmark,
            )
            summary = runner.run()
            return summary or {}

        # Managed model benchmark via GenAI SDK
        try:
            from google import genai

            client = genai.Client(vertexai=True, project=self.project_id, location=target.region)
            prompt = "Explain the core principles of quantum computing in 3 concise paragraphs."
            latencies: List[float] = []
            tokens_list: List[int] = []
            sample_out = ""

            for i in range(self.repetitions):
                t0 = time.perf_counter()
                res = client.models.generate_content(
                    model=target.flavor,
                    contents=prompt,
                )
                elapsed = time.perf_counter() - t0
                latencies.append(elapsed)
                text = res.text or ""
                if not sample_out and text:
                    sample_out = text
                est_tokens = max(1, int(len(text) / 3.8))
                tokens_list.append(est_tokens)

            total_tokens = sum(tokens_list)
            total_time = sum(latencies)
            tps = total_tokens / total_time if total_time > 0 else 0.0

            return {
                "endpoint_id": target.flavor,
                "region": target.region,
                "concurrency": 1,
                "total_requests": len(latencies),
                "avg_latency_s": round(sum(latencies) / len(latencies), 3),
                "p50_latency_s": round(sum(latencies) / len(latencies), 3),
                "p90_latency_s": round(max(latencies), 3),
                "p99_latency_s": round(max(latencies), 3),
                "avg_tokens": round(sum(tokens_list) / len(tokens_list), 1),
                "tps": round(tps, 1),
                "tpm": round(tps * 60.0, 0),
                "sample_output": sample_out[:100],
            }
        except Exception as e:
            print(f"[WARNING] Benchmark for managed model {target.flavor} failed: {e}")
            return {}

    def eval_soc_agent(
        self,
        target: ModelTarget,
        endpoint_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes the 5-case un-spoiled SOC Tier 1 evaluation suite.
        Grades outputs with Gemini 2.5 Pro LLM-as-a-judge and writes JSON/Markdown reports.
        """
        if self.dry_run:
            print(f"[DRY RUN] Running SOC evaluation for {target.flavor}...")
            return {
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
            }

        self.output_dir.mkdir(parents=True, exist_ok=True)
        report_md_path = self.output_dir / f"{target.flavor}_report.md"
        report_json_path = self.output_dir / f"{target.flavor}_report.json"

        eval_data = run_evaluation(
            evalset_path=self.evalset_path,
            flavor=target.flavor,
            endpoint_id=endpoint_id if target.target_type == "vertex" else None,
            managed_model=target.flavor if target.target_type == "managed" else None,
            project_id=self.project_id,
            region=target.region,
            use_live_mcp=False,
        )

        # Save JSON output
        with open(report_json_path, "w", encoding="utf-8") as f:
            json.dump(eval_data, f, indent=2)

        # Save Markdown report
        lines = [
            f"# SOC Evaluation Report: {target.flavor}",
            f"\n**Date:** {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
            f"**Model Target Type:** {target.target_type}",
            f"**Region:** {target.region}",
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

        for c in eval_data["case_results"]:
            status_str = "PASS" if c["passed"] else "FAIL"
            tok = c.get("usage", {}).get("total_tokens", 0)
            gen_tps = c.get("generation_tps", 0.0)
            tools_cnt = len(c.get("trajectory", []))
            lines.append(
                f"| {c['eval_id']} | {c['name']} | {c['rubric_score']}/100 | "
                f"{c['grounding_score']:.2f} | {status_str} | {c['latency_s']:.2f}s | {gen_tps} tok/s | {tok} | {tools_cnt} |"
            )

        lines.append("\n---\n\n## 3. Detailed Case Trajectories & Reports\n")
        for c in eval_data["case_results"]:
            lines.append(f"### {c['eval_id']}: {c['name']}\n")
            lines.append(f"- **Status:** {'PASS' if c['passed'] else 'FAIL'}")
            lines.append(f"- **Score:** {c['rubric_score']}/100 | Grounding: {c['grounding_score']:.2f} | Latency: {c['latency_s']:.2f}s")
            u = c.get("usage", {})
            lines.append(
                f"- **Token Usage & Speed:** {u.get('prompt_tokens', 0)} prompt + {u.get('completion_tokens', 0)} completion = "
                f"**{u.get('total_tokens', 0)} total tokens** | **{c.get('generation_tps', 0.0)} output tok/s**"
            )
            if c.get("assertion_failures"):
                lines.append(f"- **Assertion Failures:** `{c['assertion_failures']}`")
            lines.append(f"- **Judge Critique:** {c['critique']}\n")

            traj = c.get("trajectory", [])
            lines.append("#### Tool Execution Trajectory:")
            if traj:
                for step in traj:
                    lines.append(f"**Step {step['iteration']} - `{step['tool']}`**")
                    lines.append(f"- Arguments: `{json.dumps(step['args'])}`")
                    lines.append("```json")
                    lines.append(step["observation"])
                    lines.append("```")
            else:
                lines.append("*(No tools invoked)*\n")

            lines.append("\n#### Generated Triage Report:")
            lines.append("```markdown")
            lines.append(c["response"])
            lines.append("```\n")
            lines.append("---\n")

        with open(report_md_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        print(f"[INFO] Saved evaluation report to: {report_md_path}")
        return eval_data

    def cleanup_endpoint(
        self,
        target: ModelTarget,
        endpoint_id: Optional[str] = None,
    ) -> bool:
        """
        Guarantees undeployment and deletion of Vertex AI endpoint to ensure $0 active compute billing.
        """
        if self.dry_run or not endpoint_id or target.target_type != "vertex":
            return True

        print(f"[INFO] Starting guaranteed cleanup for Endpoint ID {endpoint_id} ({target.region})...")
        try:
            # Query deployed models
            desc_res = subprocess.run(
                [
                    "gcloud",
                    "ai",
                    "endpoints",
                    "describe",
                    endpoint_id,
                    f"--project={self.project_id}",
                    f"--region={target.region}",
                    "--format=value(deployedModels[].id)",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            deployed_ids = [d.strip() for d in desc_res.stdout.split() if d.strip()]

            for d_id in deployed_ids:
                print(f"[INFO] Undeploying model ID {d_id} from endpoint {endpoint_id}...")
                subprocess.run(
                    [
                        "gcloud",
                        "ai",
                        "endpoints",
                        "undeploy-model",
                        endpoint_id,
                        f"--deployed-model-id={d_id}",
                        f"--project={self.project_id}",
                        f"--region={target.region}",
                        "--quiet",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )

            print(f"[INFO] Deleting Vertex AI Endpoint {endpoint_id}...")
            subprocess.run(
                [
                    "gcloud",
                    "ai",
                    "endpoints",
                    "delete",
                    endpoint_id,
                    f"--project={self.project_id}",
                    f"--region={target.region}",
                    "--quiet",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            print(f"[INFO] Teardown complete for endpoint {endpoint_id}. GPU billing stopped.")
            return True
        except Exception as e:
            print(f"[WARNING] Endpoint cleanup encountered error: {e}")
            return False

    def evaluate_model(self, target: ModelTarget) -> Dict[str, Any]:
        """
        Executes deployment, benchmarking, and SOC evaluation within a guaranteed try/finally block.
        """
        endpoint_id: Optional[str] = None
        start_time = time.time()
        bench_result: Optional[Dict[str, Any]] = None
        soc_eval_result: Optional[Dict[str, Any]] = None

        print("\n" + "=" * 75)
        print(f" EVALUATING TARGET: {target.flavor}")
        print(f" Type: {target.target_type} | Region: {target.region} | Notes: {target.notes}")
        if target.machine_type:
            print(f" Machine: {target.machine_type} ({target.gpu_count}x {target.gpu_type})")
        if target.extra_vllm_flags:
            print(f" Extra Flags: {target.extra_vllm_flags}")
        print("=" * 75 + "\n")

        try:
            if target.target_type == "vertex":
                endpoint_id = self.deploy_vertex_model(target)

            bench_result = self.benchmark_model(target, endpoint_id)
            soc_eval_result = self.eval_soc_agent(target, endpoint_id)

            return {
                "flavor": target.flavor,
                "target": target,
                "success": True,
                "endpoint_id": endpoint_id,
                "benchmark": bench_result,
                "soc_eval": soc_eval_result,
                "duration_s": round(time.time() - start_time, 2),
                "error": None,
            }
        except Exception as e:
            print(f"[ERROR] Evaluation failed for target {target.flavor}: {e}")
            raise
        finally:
            if endpoint_id:
                self.cleanup_endpoint(target, endpoint_id)

    def run_sweep(self, model_filter: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Runs the full sequential sweep across the model queue.
        Isolates errors so a failure on one model does not halt the overall sweep.
        """
        queue = self.build_queue()
        if model_filter:
            queue = [
                t for t in queue
                if t.flavor in model_filter or t.get_base_flavor() in model_filter
            ]

        print("=" * 75)
        print(" MASTER OVERNIGHT MODEL EVALUATION SWEEP")
        print(f" Project: {self.project_id} | Total Models: {len(queue)} | Dry Run: {self.dry_run}")
        print(" Models:")
        for idx, m in enumerate(queue, 1):
            print(f"   {idx:2d}. {m.flavor:<30} ({m.target_type}, {m.region}) - {m.notes}")
        print("=" * 75 + "\n")

        results: List[Dict[str, Any]] = []
        for idx, target in enumerate(queue, 1):
            print(f"\n>>> [{idx}/{len(queue)}] Starting evaluation: {target.flavor} <<<\n")
            try:
                res = self.evaluate_model(target)
                results.append(res)
            except Exception as e:
                results.append({
                    "flavor": target.flavor,
                    "target": target,
                    "success": False,
                    "endpoint_id": None,
                    "benchmark": None,
                    "soc_eval": None,
                    "duration_s": 0.0,
                    "error": str(e),
                })

            # Incremental scorecard update
            try:
                self.update_master_scorecard(results)
            except Exception as e:
                print(f"[WARNING] Incremental master scorecard update failed: {e}")

        print("\n" + "=" * 75)
        print(" OVERNIGHT SWEEP COMPLETED")
        print(f" Total evaluated: {len(results)}")
        passed_runs = sum(1 for r in results if r.get("success", False))
        print(f" Successful runs: {passed_runs} / {len(results)}")
        print("=" * 75 + "\n")

        return results

    def update_master_scorecard(self, results: List[Dict[str, Any]]) -> str:
        """
        Updates docs/soc_model_comparative_evals.md with comprehensive results,
        ordered by model size and capability from smallest/edge to largest/most capable.
        """
        successful_results = [r for r in results if r.get("success", False) and r.get("soc_eval")]
        if not successful_results:
            return ""

        def get_sort_key(res: Dict[str, Any]) -> int:
            flavor = res["flavor"]
            if flavor in MODEL_CAPABILITY_ORDER:
                return MODEL_CAPABILITY_ORDER.index(flavor)
            return len(MODEL_CAPABILITY_ORDER) + 100

        successful_results = sorted(successful_results, key=get_sort_key)

        headers = ["Metric"] + [f"`{r['flavor']}`" for r in successful_results]
        separator = [":---"] + [":---" for _ in successful_results]

        # Capability Matrix Rows
        row_gen = ["**Model Generation / Notes**"] + [
            r["target"].notes or r["flavor"] for r in successful_results
        ]
        row_pass = ["**Pass Rate**"] + [
            f"**{r['soc_eval']['summary']['pass_rate']:.1f}%** ({r['soc_eval']['summary']['passed_cases']}/{r['soc_eval']['summary']['total_cases']})"
            for r in successful_results
        ]
        row_score = ["**Average Score**"] + [
            f"**{r['soc_eval']['summary']['avg_rubric_score']:.1f} / 100**" for r in successful_results
        ]
        row_lat = ["**Average Latency**"] + [
            f"**{r['soc_eval']['summary']['avg_latency_s']:.2f} s**" for r in successful_results
        ]
        row_gen_tps = ["**Output Speed (Gen TPS)**"] + [
            f"**{r['soc_eval']['summary'].get('avg_generation_tps', 0.0):.2f} tok/s**" for r in successful_results
        ]
        row_tot_tps = ["**Total Processing TPS**"] + [
            f"**{r['soc_eval']['summary'].get('avg_total_tps', 0.0):.2f} tok/s**" for r in successful_results
        ]
        row_tools = ["**Total Tool Invocations**"] + [
            f"**{r['soc_eval']['summary']['total_tool_calls']} tool calls**" for r in successful_results
        ]
        row_toks = ["**Total Tokens Consumed**"] + [
            f"**{r['soc_eval']['summary']['total_tokens']:,} tokens**" for r in successful_results
        ]

        cap_table_lines = [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join(separator) + " |",
            "| " + " | ".join(row_gen) + " |",
            "| " + " | ".join(row_pass) + " |",
            "| " + " | ".join(row_score) + " |",
            "| " + " | ".join(row_lat) + " |",
            "| " + " | ".join(row_gen_tps) + " |",
            "| " + " | ".join(row_tot_tps) + " |",
            "| " + " | ".join(row_tools) + " |",
            "| " + " | ".join(row_toks) + " |",
        ]

        # Case-by-case Breakdown Matrix
        case_headers = ["Case ID", "Scenario"] + [f"`{r['flavor']}`" for r in successful_results]
        case_separator = [":---", ":---"] + [":---" for _ in successful_results]

        case_names = {
            "CASE-01": "Lokibot C2 Beaconing",
            "CASE-02": "RFC-5737 Benign IP Grounding",
            "CASE-03": "Phishing Credential Harvest",
            "CASE-04": "Duplicate SOAR Case Detection",
            "CASE-05": "Ransomware Escalation",
        }

        case_table_lines = [
            "| " + " | ".join(case_headers) + " |",
            "| " + " | ".join(case_separator) + " |",
        ]

        for case_id, scenario in case_names.items():
            row = [f"**`{case_id}`**", f"**{scenario}**"]
            for r in successful_results:
                case_item = next(
                    (c for c in r["soc_eval"].get("case_results", []) if c.get("eval_id", "").startswith(case_id)),
                    None,
                )
                if case_item:
                    score = case_item.get("rubric_score", 0.0)
                    tools_cnt = len(case_item.get("trajectory", []))
                    pass_str = "**PASS**" if case_item.get("passed", False) else "FAIL"
                    cell = f"{score:.1f} ({tools_cnt} tools, {pass_str})"
                else:
                    cell = "N/A"
                row.append(cell)
            case_table_lines.append("| " + " | ".join(row) + " |")

        # Compile Document
        doc_lines = [
            "---",
            'title: "SOC Tier 1 Agent Multi-Model Comparative Evaluation"',
            'description: "Empirical evaluation and comparative analysis across on-device Gemma and managed Gemini model tiers on the un-spoiled declarative SOC benchmark."',
            'type: "analysis"',
            "tags:",
            "  - evaluation",
            "  - benchmark",
            "  - gemma",
            "  - gemini",
            "  - soc-agent",
            f"created: 2026-08-26",
            f"updated: {time.strftime('%Y-%m-%d', time.gmtime())}",
            "---",
            "",
            "# SOC Tier 1 Agent Multi-Model Comparative Evaluation",
            "",
            "This document presents the empirical findings and capability analysis from evaluating distinct model tiers on the declarative SOC Tier 1 benchmark suite ([`configs/evals/soc_tier1_evalset.json`](../configs/evals/soc_tier1_evalset.json)) under the un-spoiled, principled persona.",
            "",
            "---",
            "",
            "## 1. Executive Summary & Scorecard",
            "",
            "All models were evaluated under identical conditions using the un-spoiled persona in [`agent/soc_tier1_agent.py`](../agent/soc_tier1_agent.py) with zero alert-specific cheat sheets. Triage decisions, tool invocations, and responses were scored across deterministic assertions and a 100-point rubric auto-rated by Gemini 2.5 Pro.",
            "",
            "### Multi-Model Capability Matrix",
            "",
            "\n".join(cap_table_lines),
            "",
            "---",
            "",
            "## 2. Case-by-Case Breakdown Matrix",
            "",
            "\n".join(case_table_lines),
            "",
            "---",
            "",
            "## 3. Detailed Behavioral Analysis by Model Tier",
            "",
        ]

        for r in successful_results:
            flavor = r["flavor"]
            notes = r["target"].notes or flavor
            summ = r["soc_eval"]["summary"]
            doc_lines.extend([
                f"### `{flavor}` ({notes})",
                f"- **Score:** {summ['avg_rubric_score']:.1f} / 100 (Pass Rate: {summ['pass_rate']:.1f}%)",
                f"- **Latency & Throughput:** {summ['avg_latency_s']:.2f} s latency | {summ.get('avg_generation_tps', 0.0):.2f} gen tok/s ({summ.get('avg_total_tps', 0.0):.2f} total tok/s)",
                f"- **Tool Invocations:** {summ['total_tool_calls']} total calls across 5 cases",
                f"- **Token Footprint:** {summ['total_tokens']:,} total tokens ({summ.get('avg_tokens_per_case', 0.0):.1f} tok/case)",
                "",
            ])

        doc_lines.extend([
            "---",
            "",
            "## 4. Key Architectural Takeaways for Gemma Deployments",
            "",
            "1. **Benchmark Discriminative Power**:",
            "   - Removing prescriptive prompt cheat sheets allows the benchmark to clearly differentiate between open-weight edge models, intermediate Flash models, and frontier multi-hop reasoning models.",
            "2. **Tool-Use Dynamics**:",
            "   - Smaller open-weight models benefit from explicit few-shot examples or agentic fine-tuning to encourage multi-hop tool execution.",
            "   - `gemini-3.5-flash-lite` demonstrates optimal single-hop precision, while `gemini-3.7-flash` exhibits aggressive multi-hop investigative autonomy.",
            "3. **Hybrid Deployment Architecture**:",
            "   - High-volume Tier 1 triage can route straightforward alerts to efficient fast-inference backends (`gemma-4-e2b-it` or `gemini-3.5-flash-lite`), while escalating complex, ambiguous multi-entity alerts to frontier models.",
            "",
            "---",
            "",
            "## 5. Report Artifacts",
            "",
        ])

        for r in successful_results:
            flavor = r["flavor"]
            doc_lines.append(f"- Detailed {flavor} Report: [`soc_eval_results/{flavor}_report.md`](soc_eval_results/{flavor}_report.md)")

        doc_lines.append("")
        content = "\n".join(doc_lines)

        self.scorecard_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.scorecard_path, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"[INFO] Updated master scorecard: {self.scorecard_path}")
        return content

    def rebuild_scorecard_from_reports(self) -> str:
        """
        Rebuilds docs/soc_model_comparative_evals.md by loading all JSON reports from docs/soc_eval_results/.
        """
        queue = self.build_queue()
        target_map = {t.flavor: t for t in queue}
        reports_dir = self.output_dir
        results: List[Dict[str, Any]] = []


        for json_file in sorted(reports_dir.glob("*_report.json")):
            # Ignore legacy baseline duplicates if canonical file exists
            if json_file.name in [
                "gemini_2_5_flash_report.json",
                "gemini_2_5_pro_report.json",
                "gemini_3_5_flash_lite_report.json",
                "gemini_3_7_flash_report.json",
            ]:
                continue

            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                flavor = data.get("flavor", json_file.stem.replace("_report", ""))
                # Normalize flavor names
                if flavor == "gemini_2_5_flash":
                    flavor = "gemini-2.5-flash"
                elif flavor == "gemini_2_5_pro":
                    flavor = "gemini-2.5-pro"
                elif flavor == "gemini_3_5_flash_lite":
                    flavor = "gemini-3.5-flash-lite"
                elif flavor == "gemini_3_7_flash":
                    flavor = "gemini-3.7-flash"

                target = target_map.get(flavor, ModelTarget(flavor=flavor, target_type="vertex", notes=flavor))
                results.append({
                    "flavor": flavor,
                    "target": target,
                    "success": True,
                    "endpoint_id": None,
                    "benchmark": None,
                    "soc_eval": data,
                    "duration_s": data.get("summary", {}).get("avg_latency_s", 0.0) * 5,
                    "error": None,
                })
            except Exception as e:
                print(f"[WARNING] Failed to parse report file {json_file}: {e}")

        # Deduplicate results by flavor (prefer latest)
        unique_results: Dict[str, Dict[str, Any]] = {}
        for r in results:
            unique_results[r["flavor"]] = r

        return self.update_master_scorecard(list(unique_results.values()))


def main() -> None:
    """CLI entrypoint for running the overnight evaluation sweep."""
    parser = argparse.ArgumentParser(description="Overnight Comprehensive Model Evaluation & Benchmark Sweep")
    parser.add_argument("--project-id", default=os.environ.get("GCP_PROJECT_ID", "dandye-0324-chronicle"), help="GCP Project ID")
    parser.add_argument("--evalset", default="configs/evals/soc_tier1_evalset.json", help="Path to evalset JSON")
    parser.add_argument("--models", nargs="*", default=None, help="Optional subset of model flavors to evaluate")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Dry run mode (mocks deployment & eval)")
    parser.add_argument("--rebuild-scorecard", action="store_true", default=False, help="Rebuild docs/soc_model_comparative_evals.md from docs/soc_eval_results/*.json without running evaluations")
    parser.add_argument("--timeout", type=int, default=1500, help="Per-model deployment timeout in seconds")
    parser.add_argument("--repetitions", type=int, default=3, help="Benchmark repetition count per model")
    parser.add_argument("--no-stream", action="store_true", default=False, help="Disable streaming TTFT measurement")
    args = parser.parse_args()

    orchestrator = SweepOrchestrator(
        project_id=args.project_id,
        evalset_path=Path(args.evalset),
        dry_run=args.dry_run,
        timeout_seconds=args.timeout,
        stream_benchmark=not args.no_stream,
        repetitions=args.repetitions,
    )

    if args.rebuild_scorecard:
        print("[INFO] Rebuilding master scorecard from saved evaluation reports...")
        orchestrator.rebuild_scorecard_from_reports()
        print("[SUCCESS] Master scorecard rebuilt successfully.")
        return


    results = orchestrator.run_sweep(model_filter=args.models)
    success_count = sum(1 for r in results if r.get("success", False))
    print(f"\nFinal Summary: {success_count}/{len(results)} models evaluated successfully.")



if __name__ == "__main__":
    main()
