#!/usr/bin/env python3
"""
Gemma Deployment Benchmark & Metrics Collector
Measures Latency (P50, P90, P99), TTFT, ITL, Estimated Tokens,
Tokens/Sec (TPS), and Tokens/Min (TPM) against Vertex AI Endpoints
with single-stream, concurrent multi-stream, and prefix caching evaluation modes.
"""

import os
import sys
import json
import time
import subprocess
import argparse
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Tuple


def get_adc_token() -> str:
    """Retrieve Google Cloud ADC access token."""
    res = subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        capture_output=True,
        text=True,
        check=True,
    )
    return res.stdout.strip()


def calculate_percentile(data: List[float], percentile: float) -> float:
    """
    Calculate percentile value from numeric data using linear interpolation.
    Percentile must be between 0 and 100.
    """
    if not data:
        return 0.0
    sorted_data = sorted(data)
    n = len(sorted_data)
    if n == 1:
        return float(sorted_data[0])
    if percentile <= 0:
        return float(sorted_data[0])
    if percentile >= 100:
        return float(sorted_data[-1])

    k = (n - 1) * (percentile / 100.0)
    f = int(k)
    c = f + 1
    if c >= n:
        return float(sorted_data[-1])
    d = k - f
    return float(sorted_data[f] + d * (sorted_data[c] - sorted_data[f]))


def parse_output(res_body: Optional[Dict[str, Any]]) -> Tuple[str, int]:
    """Parse generated text and estimated token count from prediction response."""
    if not res_body:
        return "", 0
    predictions = res_body.get("predictions", [])
    output_text = ""
    if predictions:
        pred = predictions[0]
        if isinstance(pred, str):
            if "Output:\n" in pred:
                output_text = pred.split("Output:\n", 1)[1]
            else:
                output_text = pred
        elif isinstance(pred, dict):
            output_text = pred.get("content", str(pred))
    est_tokens = max(1, int(len(output_text) / 3.8))
    return output_text.strip(), est_tokens


def calculate_summary(
    latencies: List[float],
    token_counts: List[int],
    ttfts: Optional[List[float]] = None,
    concurrency: int = 1,
    endpoint_id: str = "",
    region: str = "",
    sample_output: str = "",
) -> Dict[str, Any]:
    """
    Calculate summary metrics including P50, P90, P99, TPS, TPM, TTFT, and ITL.
    """
    if not latencies:
        return {
            "endpoint_id": endpoint_id,
            "region": region,
            "concurrency": concurrency,
            "total_requests": 0,
            "avg_latency_s": 0.0,
            "p50_latency_s": 0.0,
            "p90_latency_s": 0.0,
            "p99_latency_s": 0.0,
            "avg_tokens": 0.0,
            "tps": 0.0,
            "tpm": 0.0,
            "sample_output": sample_output,
        }

    total_reqs = len(latencies)
    avg_latency = sum(latencies) / total_reqs
    p50_lat = calculate_percentile(latencies, 50)
    p90_lat = calculate_percentile(latencies, 90)
    p99_lat = calculate_percentile(latencies, 99)

    avg_tokens = sum(token_counts) / total_reqs if token_counts else 0.0

    total_tokens = sum(token_counts)
    total_time = sum(latencies)
    tps = total_tokens / total_time if total_time > 0 else 0.0
    tpm = tps * 60.0

    summary: Dict[str, Any] = {
        "endpoint_id": endpoint_id,
        "region": region,
        "concurrency": concurrency,
        "total_requests": total_reqs,
        "avg_latency_s": round(avg_latency, 3),
        "p50_latency_s": round(p50_lat, 3),
        "p90_latency_s": round(p90_lat, 3),
        "p99_latency_s": round(p99_lat, 3),
        "avg_tokens": round(avg_tokens, 1),
        "tps": round(tps, 1),
        "tpm": round(tpm, 0),
        "sample_output": sample_output,
    }

    if ttfts and len(ttfts) == total_reqs:
        avg_ttft_s = sum(ttfts) / total_reqs
        summary["ttft_ms"] = round(avg_ttft_s * 1000.0, 1)

        itl_values = []
        for lat, ttft, tok in zip(latencies, ttfts, token_counts):
            if tok > 1:
                itl_s = (lat - ttft) / (tok - 1)
            else:
                itl_s = lat - ttft
            itl_values.append(itl_s * 1000.0)

        avg_itl_ms = sum(itl_values) / len(itl_values) if itl_values else 0.0
        summary["itl_ms"] = round(avg_itl_ms, 1)

    return summary


def format_benchmark_table(summary: Dict[str, Any]) -> str:
    """Format benchmark results into a clear ASCII metrics table."""
    lines = []
    lines.append("=" * 60)
    lines.append(" Benchmark Summary:")
    lines.append(f"   Endpoint ID:      {summary.get('endpoint_id', 'N/A')}")
    lines.append(f"   Region:           {summary.get('region', 'N/A')}")
    lines.append(f"   Concurrency:      {summary.get('concurrency', 1)}")
    lines.append(f"   Total Runs:       {summary.get('total_requests', 'N/A')}")
    lines.append("-" * 60)
    lines.append(f"   Avg Latency:      {summary.get('avg_latency_s', 0.0):.2f} s")
    lines.append(f"   P50 Latency:      {summary.get('p50_latency_s', 0.0):.2f} s")
    lines.append(f"   P90 Latency:      {summary.get('p90_latency_s', 0.0):.2f} s")
    lines.append(f"   P99 Latency:      {summary.get('p99_latency_s', 0.0):.2f} s")
    lines.append("-" * 60)
    lines.append(f"   Avg Output Len:   {summary.get('avg_tokens', 0.0):.0f} tokens")
    lines.append(f"   Avg Generation:   {summary.get('tps', 0.0):.1f} tokens/sec (TPS)")
    lines.append(f"   Avg Throughput:   {summary.get('tpm', 0.0):,.0f} tokens/min (TPM)")

    if "ttft_ms" in summary:
        lines.append("-" * 60)
        lines.append(f"   Avg TTFT:         {summary.get('ttft_ms', 0.0):.1f} ms")
    if "itl_ms" in summary:
        lines.append(f"   Avg ITL:          {summary.get('itl_ms', 0.0):.1f} ms")

    lines.append("=" * 60)
    return "\n".join(lines)


def send_single_request(
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    stream: bool = False,
) -> Tuple[float, Optional[Dict[str, Any]], Optional[str]]:
    """
    Send HTTP POST request to prediction endpoint.
    Returns (elapsed_time, response_body, error_message).
    """
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    start_time = time.perf_counter()
    try:
        with urllib.request.urlopen(req) as response:
            res_body = json.loads(response.read().decode("utf-8"))
            elapsed = time.perf_counter() - start_time
            return elapsed, res_body, None
    except Exception as e:
        elapsed = time.perf_counter() - start_time
        return elapsed, None, str(e)


def send_streaming_request(
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
) -> Tuple[float, float, Optional[Dict[str, Any]], Optional[str]]:
    """
    Send HTTP POST request with streaming measurement for Time-To-First-Token (TTFT).
    Returns (elapsed_time, ttft_time, response_body, error_message).
    """
    stream_headers = dict(headers)
    stream_headers["Accept"] = "text/event-stream, application/json"

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=stream_headers,
        method="POST",
    )
    start_time = time.perf_counter()
    ttft_time = 0.0
    first_chunk_received = False
    chunks = []

    try:
        with urllib.request.urlopen(req) as response:
            while True:
                chunk = response.read(64)
                if not chunk:
                    break
                if not first_chunk_received:
                    ttft_time = time.perf_counter() - start_time
                    first_chunk_received = True
                chunks.append(chunk)

            elapsed = time.perf_counter() - start_time
            if not first_chunk_received:
                ttft_time = elapsed

            raw_text = b"".join(chunks).decode("utf-8", errors="ignore")
            # Attempt to parse JSON response
            try:
                res_body = json.loads(raw_text)
            except Exception:
                res_body = {"predictions": [{"content": raw_text}]}

            return elapsed, ttft_time, res_body, None
    except Exception as e:
        elapsed = time.perf_counter() - start_time
        return elapsed, elapsed, None, str(e)


class BenchmarkRunner:
    """
    Orchestrates latency, throughput, streaming, concurrency sweeps,
    and prefix caching benchmarks against Vertex AI endpoints.
    """

    def __init__(
        self,
        project_id: str = "dandye-0324-chronicle",
        region: str = "us-central1",
        endpoint_id: Optional[str] = None,
        prompt: str = "Explain the core principles of quantum computing in 3 concise paragraphs.",
        max_tokens: int = 150,
        runs: int = 3,
        concurrency: int = 1,
        stream: bool = False,
        prefix_prompt: Optional[str] = None,
    ):
        self.project_id = project_id
        self.region = region
        self.endpoint_id = endpoint_id or os.environ.get("VERTEX_ENDPOINT_ID", "")
        self.prompt = prompt
        self.max_tokens = max_tokens
        self.runs = runs
        self.concurrency = concurrency
        self.stream = stream
        self.prefix_prompt = prefix_prompt
        self._token: Optional[str] = None

    def get_token(self) -> str:
        """Get or refresh ADC access token."""
        if not self._token:
            self._token = get_adc_token()
        return self._token

    def discover_endpoint_id(self) -> str:
        """Discover active Vertex AI Endpoint ID if not explicitly specified."""
        if self.endpoint_id:
            return self.endpoint_id

        env_id = os.environ.get("VERTEX_ENDPOINT_ID", "").strip()
        if env_id:
            self.endpoint_id = env_id
            return self.endpoint_id

        print(f"[INFO] Discovering active Vertex AI endpoint in {self.region}...", flush=True)
        try:
            res = subprocess.run(
                [
                    "gcloud",
                    "ai",
                    "endpoints",
                    "list",
                    f"--region={self.region}",
                    f"--project={self.project_id}",
                    "--format=value(name.basename())",
                    "--limit=1",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            found = res.stdout.strip()
            if found:
                self.endpoint_id = found.split()[0]
                print(f"[INFO] Auto-discovered Endpoint ID: {self.endpoint_id}", flush=True)
                return self.endpoint_id
        except Exception as e:
            print(f"[WARNING] Endpoint auto-discovery failed: {e}", flush=True)

        return ""

    def calculate_summary(
        self,
        token_counts: List[int],
        latencies: List[float],
        ttfts: Optional[List[float]] = None,
        sample_output: str = "",
    ) -> Dict[str, Any]:
        """Calculate summary metrics for current runner configuration."""
        return calculate_summary(
            latencies=latencies,
            token_counts=token_counts,
            ttfts=ttfts,
            concurrency=self.concurrency,
            endpoint_id=self.endpoint_id or "",
            region=self.region,
            sample_output=sample_output,
        )

    def calculate_prefix_caching_summary(
        self,
        cold_run: Dict[str, Any],
        warm_runs: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Compute comparative metrics for Cold (uncached) vs Warm (prefix cached) runs.
        """
        cold_lat = cold_run.get("latency", 0.0)
        cold_ttft_s = cold_run.get("ttft", cold_run.get("ttft_ms", 0.0) / 1000.0 if "ttft_ms" in cold_run else cold_lat)
        cold_ttft_ms = cold_ttft_s * 1000.0 if cold_ttft_s < 50 else cold_ttft_s
        cold_tps = cold_run.get("tps", 0.0)

        warm_lats = [w.get("latency", 0.0) for w in warm_runs]
        warm_ttfts_ms = []
        for w in warm_runs:
            t = w.get("ttft", w.get("ttft_ms", 0.0) / 1000.0 if "ttft_ms" in w else w.get("latency", 0.0))
            warm_ttfts_ms.append(t * 1000.0 if t < 50 else t)
        warm_tps_list = [w.get("tps", 0.0) for w in warm_runs]

        warm_avg_lat = sum(warm_lats) / len(warm_lats) if warm_lats else 0.0
        warm_avg_ttft_ms = sum(warm_ttfts_ms) / len(warm_ttfts_ms) if warm_ttfts_ms else 0.0
        warm_avg_tps = sum(warm_tps_list) / len(warm_tps_list) if warm_tps_list else 0.0

        latency_speedup = cold_lat / warm_avg_lat if warm_avg_lat > 0 else 1.0
        ttft_reduction_pct = (
            ((cold_ttft_ms - warm_avg_ttft_ms) / cold_ttft_ms) * 100.0 if cold_ttft_ms > 0 else 0.0
        )
        tps_improvement_pct = (
            ((warm_avg_tps - cold_tps) / cold_tps) * 100.0 if cold_tps > 0 else 0.0
        )

        return {
            "cold_latency_s": round(cold_lat, 3),
            "warm_avg_latency_s": round(warm_avg_lat, 3),
            "latency_speedup_ratio": round(latency_speedup, 2),
            "cold_ttft_ms": round(cold_ttft_ms, 1),
            "warm_avg_ttft_ms": round(warm_avg_ttft_ms, 1),
            "ttft_reduction_pct": round(ttft_reduction_pct, 1),
            "cold_tps": round(cold_tps, 1),
            "warm_avg_tps": round(warm_avg_tps, 1),
            "tps_improvement_pct": round(tps_improvement_pct, 1),
        }

    def run(
        self,
        concurrency: Optional[int] = None,
        runs: Optional[int] = None,
        prompt: Optional[str] = None,
        stream: Optional[bool] = None,
    ) -> Optional[Dict[str, Any]]:
        """Run benchmark execution with given concurrency and repetitions."""
        c = concurrency or self.concurrency
        r = runs or self.runs
        p = prompt or self.prompt
        use_stream = self.stream if stream is None else stream

        endpoint_id = self.discover_endpoint_id()
        if not endpoint_id:
            print("[ERROR] No Vertex AI Endpoint specified or discovered.", flush=True)
            return None

        token = self.get_token()
        url = f"https://{self.region}-aiplatform.googleapis.com/v1/projects/{self.project_id}/locations/{self.region}/endpoints/{endpoint_id}:predict"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        payload = {
            "instances": [
                {
                    "prompt": p,
                    "max_tokens": self.max_tokens,
                    "temperature": 0.2,
                    "top_p": 0.95,
                }
            ]
        }

        print("=" * 60, flush=True)
        print(f" Benchmarking Endpoint: {endpoint_id} ({self.region})", flush=True)
        print(f' Prompt: "{p[:80]}..."' if len(p) > 80 else f' Prompt: "{p}"', flush=True)
        print(f" Max Tokens: {self.max_tokens} | Repetitions: {r} | Concurrency: {c} | Streaming: {use_stream}", flush=True)
        print("=" * 60, flush=True)

        latencies: List[float] = []
        token_counts: List[int] = []
        ttfts: List[float] = []
        sample_output = ""

        if c == 1:
            for i in range(r):
                if use_stream:
                    elapsed, ttft, res_body, err = send_streaming_request(url, headers, payload)
                else:
                    elapsed, res_body, err = send_single_request(url, headers, payload)
                    ttft = elapsed / 2.0  # Estimate TTFT for non-streaming

                if err:
                    print(f"  Run {i+1}: [ERROR] {err}", flush=True)
                    continue

                output_text, est_tokens = parse_output(res_body)
                if not sample_output and output_text:
                    sample_output = output_text

                tps = est_tokens / elapsed if elapsed > 0 else 0
                latencies.append(elapsed)
                token_counts.append(est_tokens)
                ttfts.append(ttft)

                ttft_str = f" | TTFT = {ttft*1000:.0f}ms" if use_stream else ""
                print(
                    f"  Run {i+1}: Latency = {elapsed:.2f}s{ttft_str} | Est. Tokens = {est_tokens} | TPS = {tps:.1f} tok/s | TPM = {tps*60:,.0f} tok/min",
                    flush=True,
                )
        else:
            for iteration in range(r):
                print(f"\n--- Concurrency Test (Batch {iteration+1}/{r} with {c} parallel streams) ---", flush=True)
                batch_start = time.perf_counter()
                with ThreadPoolExecutor(max_workers=c) as executor:
                    if use_stream:
                        futures = [executor.submit(send_streaming_request, url, headers, payload) for _ in range(c)]
                    else:
                        futures = [executor.submit(send_single_request, url, headers, payload) for _ in range(c)]

                    batch_tokens = 0
                    stream_latencies = []
                    stream_ttfts = []
                    for f in as_completed(futures):
                        res = f.result()
                        if use_stream:
                            elapsed, ttft, res_body, err = res
                        else:
                            elapsed, res_body, err = res
                            ttft = elapsed / 2.0

                        if err:
                            print(f"    Stream failed: {err}", flush=True)
                            continue

                        output_text, est_tokens = parse_output(res_body)
                        if not sample_output and output_text:
                            sample_output = output_text
                        batch_tokens += est_tokens
                        stream_latencies.append(elapsed)
                        stream_ttfts.append(ttft)

                batch_total_time = time.perf_counter() - batch_start
                batch_tps = batch_tokens / batch_total_time if batch_total_time > 0 else 0
                avg_stream_lat = sum(stream_latencies) / len(stream_latencies) if stream_latencies else 0
                avg_stream_ttft = sum(stream_ttfts) / len(stream_ttfts) if stream_ttfts else 0

                latencies.append(avg_stream_lat)
                token_counts.append(batch_tokens)
                ttfts.append(avg_stream_ttft)

                print(f"  Total Batch Time: {batch_total_time:.2f}s | Avg Stream Latency: {avg_stream_lat:.2f}s")
                print(f"  Batch Output:     {batch_tokens} total tokens across {len(stream_latencies)} streams")
                print(f"  Aggregate Rate:   {batch_tps:.1f} tokens/sec (TPS) | {batch_tps*60:,.0f} tokens/min (TPM)")

        if not latencies:
            print("[ERROR] No successful benchmark runs.", flush=True)
            return None

        summary = calculate_summary(
            latencies=latencies,
            token_counts=token_counts,
            ttfts=ttfts if use_stream else None,
            concurrency=c,
            endpoint_id=endpoint_id,
            region=self.region,
            sample_output=sample_output,
        )

        print(format_benchmark_table(summary), flush=True)
        return summary

    def run_concurrency_sweep(
        self,
        stream_counts: Tuple[int, ...] = (1, 2, 4, 8),
        runs: int = 3,
        prompt: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Run benchmark sweep over multiple concurrency stream counts."""
        results = []
        print("\n" + "=" * 70)
        print(" STARTING MULTI-STREAM CONCURRENCY SWEEP")
        print(f" Stream counts: {stream_counts}")
        print("=" * 70 + "\n")

        for c in stream_counts:
            summary = self.run(concurrency=c, runs=runs, prompt=prompt)
            if summary:
                results.append(summary)

        # Print consolidated comparison table
        print("\n" + "=" * 78)
        print(" CONCURRENCY SWEEP SUMMARY TABLE")
        print("=" * 78)
        print(f"{'Streams':<10}{'Avg Lat (s)':<14}{'P50 (s)':<10}{'P90 (s)':<10}{'P99 (s)':<10}{'TPS':<12}{'TPM':<12}")
        print("-" * 78)
        for r in results:
            print(
                f"{r.get('concurrency', 1):<10}"
                f"{r.get('avg_latency_s', 0.0):<14.2f}"
                f"{r.get('p50_latency_s', 0.0):<10.2f}"
                f"{r.get('p90_latency_s', 0.0):<10.2f}"
                f"{r.get('p99_latency_s', 0.0):<10.2f}"
                f"{r.get('tps', 0.0):<12.1f}"
                f"{r.get('tpm', 0.0):<12,.0f}"
            )
        print("=" * 78 + "\n")
        return results

    def run_prefix_caching_test(
        self,
        prefix_prompt: Optional[str] = None,
        user_prompts: Optional[List[str]] = None,
        runs: int = 3,
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluate vLLM Prefix Caching efficiency.
        Runs a Cold Request (large shared system prefix), followed by Warm Requests
        sharing the identical prefix to quantify TTFT reduction and TPS gains.
        """
        endpoint_id = self.discover_endpoint_id()
        if not endpoint_id:
            print("[ERROR] No Vertex AI Endpoint specified or discovered.", flush=True)
            return None

        # Long shared prefix (~1,200 tokens / 4.5KB text) simulating realistic multi-turn system prompt
        default_prefix = (
            prefix_prompt
            or self.prefix_prompt
            or """System Context & Security Operations Runbook:
You are an expert AI Cloud Security Architect specializing in enterprise Google Cloud Platform environments.
Reference Specifications:
1. Zero Trust Architecture: All network flows must verify explicit identity, continuous posture assessment, and least-privilege RBAC.
2. Perimeter Controls: VPC Service Controls (VPC-SC) enforce cryptographic service perimeters around sensitive BigQuery datasets and GCS buckets.
3. Cryptographic Keys: Customer-Managed Encryption Keys (CMEK) backed by Cloud HSM with 90-day automatic key rotation policies.
4. Logging & Telemetry: All administrative, data access, and system event logs stream in real-time via Pub/Sub to Google SecOps Chronicle SIEM.
5. Incident Response Protocol: Sev-1 data exfiltration alerts trigger automated Chronicle SOAR playbooks to revoke IAM credentials and isolate target Compute Engine instances.
Operational Guidelines: Provide concise, technically rigorous, step-by-step diagnostic and remediation instructions formatted in structured markdown.
"""
        )

        test_queries = user_prompts or [
            "Query 1: Explain the step-by-step remediation procedure for an anomalous CMEK key access pattern alert in Chronicle SIEM.",
            "Query 2: Describe how VPC Service Controls perimeters prevent unauthorized exfiltration from Vertex AI custom endpoints.",
            "Query 3: Outline the automated containment workflow when a compromised service account token is detected accessing BigQuery.",
        ]

        token = self.get_token()
        url = f"https://{self.region}-aiplatform.googleapis.com/v1/projects/{self.project_id}/locations/{self.region}/endpoints/{endpoint_id}:predict"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        print("=" * 70, flush=True)
        print(" PREFIX CACHING EVALUATION BENCHMARK", flush=True)
        print(f" Endpoint: {endpoint_id} ({self.region})", flush=True)
        print(f" Shared Prefix Length: {len(default_prefix)} characters (~{int(len(default_prefix)/3.8)} tokens)", flush=True)
        print("=" * 70, flush=True)

        # Run 1: Cold Request (Prefix not cached yet)
        cold_query = test_queries[0]
        cold_full_prompt = f"{default_prefix}\n\n{cold_query}"
        cold_payload = {
            "instances": [
                {
                    "prompt": cold_full_prompt,
                    "max_tokens": self.max_tokens,
                    "temperature": 0.0,
                    "top_p": 1.0,
                }
            ]
        }

        print("\n[Phase 1] Executing Cold Request (Uncached System Prefix)...", flush=True)
        cold_elapsed, cold_ttft, cold_res, cold_err = send_streaming_request(url, headers, cold_payload)
        if cold_err:
            print(f"[ERROR] Cold request failed: {cold_err}", flush=True)
            return None

        _, cold_tokens = parse_output(cold_res)
        cold_tps = cold_tokens / cold_elapsed if cold_elapsed > 0 else 0.0
        cold_run = {
            "latency": cold_elapsed,
            "ttft": cold_ttft,
            "tokens": cold_tokens,
            "tps": cold_tps,
        }
        print(f"  Cold Run Result: Latency = {cold_elapsed:.2f}s | TTFT = {cold_ttft*1000:.0f}ms | Tokens = {cold_tokens} | TPS = {cold_tps:.1f} tok/s")

        # Phase 2: Warm Requests (Prefix should hit KV cache in vLLM)
        print("\n[Phase 2] Executing Warm Requests (Reusing Cached System Prefix)...", flush=True)
        warm_runs = []
        for idx in range(1, len(test_queries)):
            warm_query = test_queries[idx]
            warm_full_prompt = f"{default_prefix}\n\n{warm_query}"
            warm_payload = {
                "instances": [
                    {
                        "prompt": warm_full_prompt,
                        "max_tokens": self.max_tokens,
                        "temperature": 0.0,
                        "top_p": 1.0,
                    }
                ]
            }
            w_elapsed, w_ttft, w_res, w_err = send_streaming_request(url, headers, warm_payload)
            if w_err:
                print(f"  Warm Run {idx}: [ERROR] {w_err}", flush=True)
                continue
            _, w_tokens = parse_output(w_res)
            w_tps = w_tokens / w_elapsed if w_elapsed > 0 else 0.0
            warm_runs.append({
                "latency": w_elapsed,
                "ttft": w_ttft,
                "tokens": w_tokens,
                "tps": w_tps,
            })
            print(f"  Warm Run {idx} Result: Latency = {w_elapsed:.2f}s | TTFT = {w_ttft*1000:.0f}ms | Tokens = {w_tokens} | TPS = {w_tps:.1f} tok/s")

        if not warm_runs:
            print("[ERROR] No successful warm runs completed.", flush=True)
            return None

        comparison = self.calculate_prefix_caching_summary(cold_run=cold_run, warm_runs=warm_runs)

        print("\n" + "=" * 70)
        print(" PREFIX CACHING EFFICIENCY SUMMARY")
        print("=" * 70)
        print(f"   Cold Latency:            {comparison['cold_latency_s']:.2f} s")
        print(f"   Warm Avg Latency:        {comparison['warm_avg_latency_s']:.2f} s")
        print(f"   Latency Speedup:         {comparison['latency_speedup_ratio']:.2f}x")
        print("-" * 70)
        print(f"   Cold TTFT:               {comparison['cold_ttft_ms']:.0f} ms")
        print(f"   Warm Avg TTFT:           {comparison['warm_avg_ttft_ms']:.0f} ms")
        print(f"   TTFT Reduction:          {comparison['ttft_reduction_pct']:.1f}%")
        print("-" * 70)
        print(f"   Cold TPS:                {comparison['cold_tps']:.1f} tok/s")
        print(f"   Warm Avg TPS:            {comparison['warm_avg_tps']:.1f} tok/s")
        print(f"   TPS Improvement:         {comparison['tps_improvement_pct']:.1f}%")
        print("=" * 70 + "\n")

        return comparison


def run_benchmark(
    project_id: str,
    region: str,
    endpoint_id: str,
    prompt: str,
    max_tokens: int = 150,
    runs: int = 3,
    concurrency: int = 1,
    stream: bool = False,
) -> Optional[Dict[str, Any]]:
    """Convenience function maintaining backwards compatibility."""
    runner = BenchmarkRunner(
        project_id=project_id,
        region=region,
        endpoint_id=endpoint_id,
        prompt=prompt,
        max_tokens=max_tokens,
        runs=runs,
        concurrency=concurrency,
        stream=stream,
    )
    return runner.run()


def main():
    parser = argparse.ArgumentParser(description="Gemma Latency & Throughput Benchmark Suite")
    parser.add_argument("--project", default="dandye-0324-chronicle", help="Google Cloud project ID")
    parser.add_argument("--region", default="us-central1", help="Vertex AI region")
    parser.add_argument("--endpoint", default="", help="Vertex AI Endpoint ID (auto-discovered if omitted)")
    parser.add_argument("--prompt", default="Explain the core principles of quantum computing in 3 concise paragraphs.")
    parser.add_argument("--max-tokens", type=int, default=150, help="Maximum generated tokens")
    parser.add_argument("--runs", type=int, default=3, help="Benchmark repetition count")
    parser.add_argument("--concurrency", "-c", type=int, default=1, help="Concurrent parallel streams count")
    parser.add_argument("--streams", type=str, default="", help="Comma-separated stream counts for sweep, e.g. '1,2,4,8'")
    parser.add_argument("--stream", "--streaming", action="store_true", help="Measure streaming TTFT metrics")
    parser.add_argument("--prefix-caching-test", action="store_true", help="Run prefix caching evaluation test")
    parser.add_argument("--prefix-prompt", type=str, default=None, help="Custom prefix text for prefix caching test")
    args = parser.parse_args()

    runner = BenchmarkRunner(
        project_id=args.project,
        region=args.region,
        endpoint_id=args.endpoint,
        prompt=args.prompt,
        max_tokens=args.max_tokens,
        runs=args.runs,
        concurrency=args.concurrency,
        stream=args.stream,
        prefix_prompt=args.prefix_prompt,
    )

    if args.prefix_caching_test:
        runner.run_prefix_caching_test(prefix_prompt=args.prefix_prompt, runs=args.runs)
    elif args.streams:
        stream_counts = tuple(int(x.strip()) for x in args.streams.split(",") if x.strip())
        runner.run_concurrency_sweep(stream_counts=stream_counts, runs=args.runs, prompt=args.prompt)
    else:
        runner.run()


if __name__ == "__main__":
    main()
