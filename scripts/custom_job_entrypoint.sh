#!/usr/bin/env bash
# ==============================================================================
# Vertex AI Custom Job Container Entrypoint
# Launches local vLLM server on port 8080, polls health, executes SOC eval
# and latency benchmarks, uploads artifacts to GCS, and terminates cleanly.
# ==============================================================================
set -euo pipefail

MODEL_FLAVOR="${1:-gemma-3-4b-it}"
HF_REPO="${2:-google/gemma-3-4b-it}"
TENSOR_PARALLEL_SIZE="${3:-1}"
EXTRA_FLAGS="${4:-}"
OUTPUT_GCS_PATH="${5:-gs://secops-eval-results/custom_jobs}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
if [[ ! -f "${ROOT_DIR}/scripts/eval_soc_agent.py" && -d "/workspace" ]]; then
    ROOT_DIR="/workspace"
fi

RESULTS_DIR="/tmp/results"
mkdir -p "${RESULTS_DIR}"

echo "=================================================================="
echo " Starting Vertex AI Custom Job Runner"
echo " Model Flavor:           ${MODEL_FLAVOR}"
echo " Hugging Face Repo:      ${HF_REPO}"
echo " Tensor Parallel Size:   ${TENSOR_PARALLEL_SIZE}"
echo " Extra Flags:            ${EXTRA_FLAGS}"
echo " Output GCS Path:        ${OUTPUT_GCS_PATH}"
echo " Working Directory:      ${ROOT_DIR}"
echo " Results Directory:      ${RESULTS_DIR}"
echo "=================================================================="

# Ensure background vLLM server is stopped on script termination
VLLM_PID=""
cleanup() {
    echo "[INFO] Cleaning up background processes..."
    if [[ -n "${VLLM_PID}" ]] && kill -0 "${VLLM_PID}" 2>/dev/null; then
        echo "[INFO] Terminating vLLM server (PID: ${VLLM_PID})..."
        kill -TERM "${VLLM_PID}" 2>/dev/null || true
        wait "${VLLM_PID}" 2>/dev/null || true
    fi
    echo "[INFO] Teardown complete."
}
trap cleanup EXIT INT TERM

# Start vLLM OpenAI-compatible server in background
echo "[INFO] Launching local vLLM API server on port 8080..."
VLLM_CMD=(
    vllm serve "${HF_REPO}"
    --port 8080
    --tensor-parallel-size "${TENSOR_PARALLEL_SIZE}"
)

if [[ -n "${EXTRA_FLAGS}" ]]; then
    # shellcheck disable=SC2206
    EXTRA_FLAGS_ARRAY=(${EXTRA_FLAGS})
    VLLM_CMD+=("${EXTRA_FLAGS_ARRAY[@]}")
fi

"${VLLM_CMD[@]}" &
VLLM_PID=$!
echo "[INFO] vLLM server started with PID: ${VLLM_PID}"

# Poll vLLM health endpoint until HTTP 200 ready
HEALTH_URL="http://127.0.0.1:8080/health"
MAX_WAIT_SECONDS=900
ELAPSED=0
READY=false

echo "[INFO] Waiting for vLLM server readiness at ${HEALTH_URL} (timeout: ${MAX_WAIT_SECONDS}s)..."
while [[ ${ELAPSED} -lt ${MAX_WAIT_SECONDS} ]]; do
    if ! kill -0 "${VLLM_PID}" 2>/dev/null; then
        echo "[ERROR] vLLM server process died unexpectedly."
        exit 1
    fi

    HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${HEALTH_URL}" 2>/dev/null || echo "000")
    if [[ "${HTTP_STATUS}" == "200" ]]; then
        READY=true
        echo "[INFO] vLLM server is healthy and ready after ${ELAPSED} seconds."
        break
    fi

    sleep 5
    ELAPSED=$((ELAPSED + 5))
    if (( ELAPSED % 30 == 0 )); then
        echo "[INFO] Still waiting for vLLM initialization (${ELAPSED}s elapsed)..."
    fi
done

if [[ "${READY}" != "true" ]]; then
    echo "[ERROR] Timed out waiting for vLLM server after ${MAX_WAIT_SECONDS} seconds."
    exit 1
fi

# Execute SOC Tier 1 Agent Evaluation
REPORT_MD="${RESULTS_DIR}/${MODEL_FLAVOR}_soc_eval_report.md"
REPORT_JSON="${RESULTS_DIR}/${MODEL_FLAVOR}_soc_eval_report.json"
EVALSET_FILE="${ROOT_DIR}/configs/evals/soc_tier1_evalset.json"

echo "=================================================================="
echo " Executing SOC Tier 1 Evaluation Suite"
echo "=================================================================="
python3 "${ROOT_DIR}/scripts/eval_soc_agent.py" \
    --flavor "${MODEL_FLAVOR}" \
    --cloudrun-url "http://127.0.0.1:8080" \
    --evalset "${EVALSET_FILE}" \
    --output-report "${REPORT_MD}" \
    --output-json "${REPORT_JSON}" || {
    echo "[WARNING] SOC evaluation reported non-zero status or partial failure."
}

# Execute Latency & Throughput Benchmark
# The inline Python benchmark script directly queries localhost:8080 vLLM chat completions
# (http://127.0.0.1:8080/v1/chat/completions) to evaluate token generation latency, total tokens,
# and throughput (tokens/sec) without requiring external network dependencies.
BENCHMARK_JSON="${RESULTS_DIR}/${MODEL_FLAVOR}_benchmark.json"
echo "=================================================================="
echo " Executing Latency and Throughput Benchmark Suite"
echo "=================================================================="
python3 -c "
import json
import os
import sys
import time
import urllib.request

prompt = 'Explain the core principles of quantum computing in 3 concise paragraphs.'
url = 'http://127.0.0.1:8080/v1/chat/completions'
headers = {'Content-Type': 'application/json'}
payload = {
    'model': '${HF_REPO}',
    'messages': [{'role': 'user', 'content': prompt}],
    'max_tokens': 150,
    'temperature': 0.2
}

latencies = []
tokens = []
for i in range(3):
    t0 = time.perf_counter()
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers)
    with urllib.request.urlopen(req) as resp:
        body = json.loads(resp.read().decode('utf-8'))
    elapsed = time.perf_counter() - t0
    latencies.append(elapsed)
    comp_tokens = body.get('usage', {}).get('completion_tokens', 0)
    tokens.append(comp_tokens)

avg_lat = sum(latencies) / len(latencies) if latencies else 0.0
tot_tokens = sum(tokens)
tps = (tot_tokens / sum(latencies)) if sum(latencies) > 0 else 0.0

bench_data = {
    'flavor': '${MODEL_FLAVOR}',
    'hf_repo': '${HF_REPO}',
    'avg_latency_s': round(avg_lat, 3),
    'latencies': [round(l, 3) for l in latencies],
    'completion_tokens': tokens,
    'tps': round(tps, 2)
}
with open('${BENCHMARK_JSON}', 'w') as f:
    json.dump(bench_data, f, indent=2)
print(f'Benchmark completed: {bench_data}')
" || {
    echo "[WARNING] Benchmark run completed with warning."
}

# Upload Results to Google Cloud Storage
DEST_GCS_URI="${OUTPUT_GCS_PATH%/}/${MODEL_FLAVOR}/"
echo "=================================================================="
echo " Uploading Evaluation Results to GCS: ${DEST_GCS_URI}"
echo "=================================================================="
if command -v gsutil &>/dev/null; then
    gsutil -m cp -r "${RESULTS_DIR}"/* "${DEST_GCS_URI}"
elif command -v gcloud &>/dev/null; then
    gcloud storage cp --recursive "${RESULTS_DIR}"/* "${DEST_GCS_URI}"
else
    python3 -c "
from google.cloud import storage
import os
from pathlib import Path

gcs_path = '${DEST_GCS_URI}'.replace('gs://', '')
bucket_name, *prefix_parts = gcs_path.split('/')
prefix = '/'.join(prefix_parts).rstrip('/')

client = storage.Client()
bucket = client.bucket(bucket_name)

results_dir = Path('${RESULTS_DIR}')
for f in results_dir.glob('*'):
    if f.is_file():
        blob_name = f'{prefix}/{f.name}' if prefix else f.name
        blob = bucket.blob(blob_name)
        blob.upload_from_filename(str(f))
        print(f'Uploaded {f.name} -> gs://{bucket_name}/{blob_name}')
"
fi

echo "=================================================================="
echo " Custom Job Finished Successfully"
echo "=================================================================="
exit 0
