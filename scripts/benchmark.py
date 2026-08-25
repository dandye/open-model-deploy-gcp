#!/usr/bin/env python3
"""
Gemma Deployment Benchmark & Metrics Collector
Measures Latency, Estimated Tokens, Tokens/Sec (TPS), and Tokens/Min (TPM)
against Vertex AI Endpoints.
"""

import sys
import json
import time
import subprocess
import argparse
import urllib.request

def get_adc_token():
    res = subprocess.run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True, check=True)
    return res.stdout.strip()

def run_benchmark(project_id, region, endpoint_id, prompt, max_tokens=150, runs=3):
    token = get_adc_token()
    url = f"https://{region}-aiplatform.googleapis.com/v1/projects/{project_id}/locations/{region}/endpoints/{endpoint_id}:predict"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload = {
        "instances": [
            {
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": 0.2,
                "top_p": 0.95
            }
        ]
    }

    latencies = []
    token_counts = []
    tps_rates = []

    print(f"==================================================", flush=True)
    print(f" Benchmarking Endpoint: {endpoint_id} ({region})", flush=True)
    print(f" Prompt: \"{prompt}\"", flush=True)
    print(f" Requested Max Tokens: {max_tokens} | Repetitions: {runs}", flush=True)
    print(f"==================================================", flush=True)

    sample_output = ""
    for i in range(runs):
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        
        start_time = time.perf_counter()
        try:
            with urllib.request.urlopen(req) as response:
                end_time = time.perf_counter()
                res_body = json.loads(response.read().decode("utf-8"))
        except Exception as e:
            print(f"[ERROR] Request {i+1} failed: {e}", flush=True)
            continue

        elapsed = end_time - start_time
        latencies.append(elapsed)

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

        if not sample_output and output_text:
            sample_output = output_text.strip()

        words = len(output_text.split())
        est_tokens = max(1, int(len(output_text) / 3.8))
        token_counts.append(est_tokens)

        tps = est_tokens / elapsed if elapsed > 0 else 0
        tps_rates.append(tps)

        print(f"  Run {i+1}: Latency = {elapsed:.2f}s | Est. Tokens = {est_tokens} | TPS = {tps:.1f} tok/s | TPM = {tps*60:,.0f} tok/min", flush=True)

    if not latencies:
        print("[ERROR] No successful benchmark runs.", flush=True)
        return None

    avg_latency = sum(latencies) / len(latencies)
    avg_tokens = sum(token_counts) / len(token_counts)
    avg_tps = sum(tps_rates) / len(tps_rates)
    avg_tpm = avg_tps * 60

    print(f"--------------------------------------------------", flush=True)
    print(f" Benchmark Summary:", flush=True)
    print(f"   Avg Latency:      {avg_latency:.2f} s", flush=True)
    print(f"   Avg Output Len:   {avg_tokens:.0f} tokens", flush=True)
    print(f"   Avg Generation:   {avg_tps:.1f} tokens/sec (TPS)", flush=True)
    print(f"   Avg Throughput:   {avg_tpm:,.0f} tokens/min (TPM)", flush=True)
    print(f"==================================================", flush=True)

    return {
        "endpoint_id": endpoint_id,
        "region": region,
        "avg_latency_sec": round(avg_latency, 2),
        "avg_tokens": round(avg_tokens, 1),
        "tps": round(avg_tps, 1),
        "tpm": round(avg_tpm, 0),
        "sample_output": sample_output
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default="dandye-0324-chronicle")
    parser.add_argument("--region", default="us-central1")
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--prompt", default="Explain the core principles of quantum computing in 3 concise paragraphs.")
    parser.add_argument("--max-tokens", type=int, default=150)
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()

    run_benchmark(args.project, args.region, args.endpoint, args.prompt, args.max_tokens, args.runs)
