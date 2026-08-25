#!/usr/bin/env python3
"""
Gemma Deployment Benchmark & Metrics Collector
Measures Latency, Estimated Tokens, Tokens/Sec (TPS), and Tokens/Min (TPM)
against Vertex AI Endpoints with single-stream and concurrent multi-stream load testing.
"""

import sys
import json
import time
import subprocess
import argparse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

def get_adc_token():
    res = subprocess.run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True, check=True)
    return res.stdout.strip()

def send_single_request(url, headers, payload):
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
            elapsed = end_time - start_time
            return elapsed, res_body, None
    except Exception as e:
        end_time = time.perf_counter()
        return end_time - start_time, None, str(e)

def parse_output(res_body):
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

def run_benchmark(project_id, region, endpoint_id, prompt, max_tokens=150, runs=3, concurrency=1):
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

    print(f"==================================================", flush=True)
    print(f" Benchmarking Endpoint: {endpoint_id} ({region})", flush=True)
    print(f" Prompt: \"{prompt}\"", flush=True)
    print(f" Max Tokens: {max_tokens} | Repetitions: {runs} | Concurrency: {concurrency}", flush=True)
    print(f"==================================================", flush=True)

    latencies = []
    token_counts = []
    tps_rates = []
    sample_output = ""

    if concurrency == 1:
        for i in range(runs):
            elapsed, res_body, err = send_single_request(url, headers, payload)
            if err:
                print(f"  Run {i+1}: [ERROR] {err}", flush=True)
                continue
            output_text, est_tokens = parse_output(res_body)
            if not sample_output and output_text:
                sample_output = output_text

            tps = est_tokens / elapsed if elapsed > 0 else 0
            latencies.append(elapsed)
            token_counts.append(est_tokens)
            tps_rates.append(tps)
            print(f"  Run {i+1}: Latency = {elapsed:.2f}s | Est. Tokens = {est_tokens} | TPS = {tps:.1f} tok/s | TPM = {tps*60:,.0f} tok/min", flush=True)
    else:
        # Concurrent Multi-Stream Load Test
        for iteration in range(runs):
            print(f"\n--- Concurrency Test (Batch {iteration+1}/{runs} with {concurrency} parallel streams) ---", flush=True)
            batch_start = time.perf_counter()
            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                futures = [executor.submit(send_single_request, url, headers, payload) for _ in range(concurrency)]
                batch_tokens = 0
                stream_latencies = []
                for f in as_completed(futures):
                    elapsed, res_body, err = f.result()
                    if err:
                        print(f"    Stream failed: {err}", flush=True)
                        continue
                    output_text, est_tokens = parse_output(res_body)
                    if not sample_output and output_text:
                        sample_output = output_text
                    batch_tokens += est_tokens
                    stream_latencies.append(elapsed)

            batch_total_time = time.perf_counter() - batch_start
            batch_tps = batch_tokens / batch_total_time if batch_total_time > 0 else 0
            avg_stream_lat = sum(stream_latencies) / len(stream_latencies) if stream_latencies else 0

            latencies.append(avg_stream_lat)
            token_counts.append(batch_tokens)
            tps_rates.append(batch_tps)

            print(f"  Total Batch Time: {batch_total_time:.2f}s | Avg Stream Latency: {avg_stream_lat:.2f}s")
            print(f"  Batch Output:     {batch_tokens} total tokens across {len(stream_latencies)} streams")
            print(f"  Aggregate Rate:   {batch_tps:.1f} tokens/sec (TPS) | {batch_tps*60:,.0f} tokens/min (TPM)")

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
        "concurrency": concurrency,
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
    parser.add_argument("--concurrency", "-c", type=int, default=1, help="Number of concurrent parallel streams")
    args = parser.parse_args()

    run_benchmark(args.project, args.region, args.endpoint, args.prompt, args.max_tokens, args.runs, args.concurrency)
