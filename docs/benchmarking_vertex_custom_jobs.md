# Vertex AI Custom Jobs: Ephemeral Multi-Model Benchmarking & Evaluation

This document outlines the architecture, automation recipes, hardware configurations, and operational workflows for running multi-model LLM benchmarking and autonomous SOC agent evaluation sweeps using ephemeral Vertex AI Custom Jobs.

---

## 1. Executive Summary & Cost Architecture

Traditional model benchmarking and evaluation on Vertex AI requires deploying persistent endpoints (`gcloud ai endpoints deploy-model`). While endpoints provide low-latency online serving, they introduce significant cost overhead during development, evaluation sweeps, and overnight batch runs:
* Dedicated GPU endpoints do **not** support scale-to-zero (`min-replica-count >= 1`).
* Idle endpoints continuously incur GPU VM billing ($0.56/hr for 1x L4, $2.24/hr for 4x L4, $7.86/hr for 2x A100).
* Uncaught exceptions or script crashes during overnight batch sweeps can leave multiple GPU endpoints active indefinitely.

### The Ephemeral Custom Job Solution
Vertex AI Custom Jobs (`aiplatform.CustomJob`) execute single-tenant containerized workloads on dedicated GPU compute nodes with **guaranteed zero idle compute leak**:
1. **Dynamic Provisioning**: Vertex AI provisions the exact requested accelerator hardware profile (e.g. 1x L4, 4x L4, 2x A100) upon job submission.
2. **Local Inference Execution**: The container launches an ephemeral vLLM server on `localhost:8080`, polls for readiness, and executes the SOC Tier 1 evaluation suite and latency benchmarks locally.
3. **Artifact Persistence**: Evaluation reports (`soc_eval_report.md`), assertion scores (`eval_results.json`), and performance metrics (`benchmark_metrics.json`) are uploaded directly to Google Cloud Storage (`gs://secops-eval-results/custom_jobs/<model_flavor>/`).
4. **Guaranteed Termination ($0.00 Idle)**: When the evaluation script completes (or errors), the container exits. Vertex AI immediately deprovisions the VM instance, ensuring zero billing post-run.

---

## 2. Container Architecture & Entrypoint Flow

The benchmark runner is packaged in a self-contained container image based on `vllm/vllm-openai:latest` (`docker/Dockerfile.custom_job`).

### Execution Flow Diagram

```
+-----------------------------------------------------------------------------------+
| Vertex AI Ephemeral Compute Node (e.g. g2-standard-12 with 1x NVIDIA L4)          |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  | Custom Job Container (/workspace/scripts/custom_job_entrypoint.sh)          |  |
|  |                                                                             |  |
|  |  1. Parse Model & Hardware Args (MODEL_FLAVOR, HF_REPO, TP_SIZE, FLAGS)     |  |
|  |                                                                             |  |
|  |  2. Launch Background vLLM Server:                                          |  |
|  |     vllm serve ${HF_REPO} --port 8080 --tensor-parallel-size ${TP_SIZE} &   |  |
|  |                                                                             |  |
|  |  3. Health Check Polling: Loop until http://127.0.0.1:8080/health returns 200|
|  |                                                                             |  |
|  |  4. Execute SOC Agent Evaluation:                                           |  |
|  |     python3 scripts/eval_soc_agent.py --flavor ${MODEL} --cloudrun-url 8080 |  |
|  |                                                                             |  |
|  |  5. Execute Latency & Throughput Benchmark Suite:                           |  |
|  |     python3 scripts/benchmark.py --flavor ${MODEL} --endpoint-url 8080     |  |
|  |                                                                             |  |
|  |  6. Signal Trap / Cleanup: Terminate background vLLM PID                    |  |
|  |                                                                             |  |
|  |  7. Upload Artifacts to Cloud Storage:                                       |  |
|  |     gcloud storage cp /tmp/results/* ${OUTPUT_GCS_PATH}/${MODEL_FLAVOR}/    |  |
|  +-----------------------------------------------------------------------------+  |
|                                                                                   |
|  8. Container Exits -> Vertex AI Deprovisions Compute Node ($0 Idle Cost)         |
+-----------------------------------------------------------------------------------+
```

---

## 3. Hardware Profiles & Model Catalog

The sweep orchestrator (`scripts/run_vertex_custom_job_sweep.py`) dynamically maps each model flavor to its required GPU architecture and machine type:

| Model Flavor | Parameters | GPU Config | Machine Type | Memory / Notes |
| :--- | :--- | :--- | :--- | :--- |
| `gemma-2-2b-it` | 2.6B | 1x NVIDIA L4 (24GB) | `g2-standard-4` | Base dense model |
| `gemma-2-2b-it-speculative` | 2.6B | 1x NVIDIA L4 (24GB) | `g2-standard-4` | N-gram prompt lookup (k=5) |
| `gemma-2-9b-it` | 9.2B | 1x NVIDIA L4 (24GB) | `g2-standard-12` | Base dense model |
| `gemma-2-9b-it-fp8` | 9.2B | 1x NVIDIA L4 (24GB) | `g2-standard-12` | FP8 quantized weights |
| `gemma-2-9b-it-speculative` | 9.2B | 1x NVIDIA L4 (24GB) | `g2-standard-12` | N-gram prompt lookup (k=5) |
| `gemma-2-27b-it` | 27.2B | 4x NVIDIA L4 (96GB) | `g2-standard-48` | Tensor Parallelism = 4 |
| `gemma-3-1b-it` | 1.0B | 1x NVIDIA L4 (24GB) | `g2-standard-4` | Compact edge model |
| `gemma-3-4b-it` | 4.3B | 1x NVIDIA L4 (24GB) | `g2-standard-8` | Balanced agent model |
| `gemma-3-4b-it-fp8` | 4.3B | 1x NVIDIA L4 (24GB) | `g2-standard-8` | FP8 quantized weights |
| `gemma-3-4b-it-speculative` | 4.3B | 1x NVIDIA L4 (24GB) | `g2-standard-8` | N-gram prompt lookup (k=5) |
| `gemma-3-4b-it-caching` | 4.3B | 1x NVIDIA L4 (24GB) | `g2-standard-8` | Automatic prefix caching |
| `gemma-3-12b-it` | 12.1B | 1x NVIDIA L4 (24GB) | `g2-standard-12` | Multimodal support |
| `gemma-3-27b-it` | 27.2B | 4x NVIDIA L4 (96GB) | `g2-standard-48` | Tensor Parallelism = 4 |
| `gemma-4-e2b-it` | 2.0B | 1x NVIDIA L4 (24GB) | `g2-standard-4` | Efficient architecture |
| `gemma-4-e4b-it` | 4.0B | 1x NVIDIA L4 (24GB) | `g2-standard-8` | Efficient architecture |
| `gemma-4-31b-it` | 30.7B | 4x NVIDIA L4 (96GB) | `g2-standard-48` | Tensor Parallelism = 4 |
| `llama-3.2-3b-instruct` | 3.2B | 1x NVIDIA L4 (24GB) | `g2-standard-8` | Meta Llama 3.2 baseline |
| `qwen-2.5-coder-7b-instruct` | 7.6B | 1x NVIDIA L4 (24GB) | `g2-standard-12` | Code generation baseline |
| `mistral-nemo-12b-instruct` | 12.2B | 1x NVIDIA L4 (24GB) | `g2-standard-12` | Mistral AI baseline |
| `deepseek-r1-distill-qwen-14b` | 14.8B | 1x NVIDIA L4 (24GB) | `g2-standard-16` | Reasoning model |
| `llama-3.3-70b-instruct` | 70.6B | 2x NVIDIA A100 (160GB) | `a2-highgpu-2g` | 70B partner flagship |

---

## 4. Automation Commands (`Justfile`)

The repository provides high-level `Justfile` recipes for container building, single-job dispatch, multi-model batch sweeps, and status inspection:

### 1. Build and Push Runner Container Image
```bash
just custom-job-build [tag] [region]
```
* Builds `docker/Dockerfile.custom_job`.
* Tags and pushes image to `${REGION}-docker.pkg.dev/${PROJECT_ID}/gemma-benchmarks/runner:${TAG:-latest}`.

### 2. Submit a Single Model CustomJob
```bash
just custom-job-run [flavor] [dry_run]
```
* Submits a single evaluation job to Vertex AI Custom Jobs.
* Example: `just custom-job-run gemma-3-4b-it`
* Dry-run simulation: `just custom-job-run gemma-3-4b-it true`

### 3. Run CustomJob Multi-Model Evaluation Sweep
```bash
just custom-job-sweep [models] [dry_run]
```
* Executes evaluation sweep across all models (or a comma-separated subset).
* Example: `just custom-job-sweep "gemma-3-1b-it,gemma-3-4b-it,gemma-2-9b-it"`
* Dry-run full sweep: `just custom-job-sweep "" true`

### 4. Monitor Active CustomJobs
```bash
just custom-job-status [region]
```
* Queries `gcloud ai custom-jobs list` for the active project and region, displaying state, creation time, and completion status.

---

## 5. Sweep Orchestrator CLI (`scripts/run_vertex_custom_job_sweep.py`)

For advanced pipelines or headless automation, the Python sweep orchestrator can be invoked directly:

```bash
uv run python3 scripts/run_vertex_custom_job_sweep.py [OPTIONS]
```

### Supported CLI Flags

* `--models <CSV>`: Comma-separated list of model flavors to evaluate (default: evaluates all models in catalog).
* `--project-id <PROJECT_ID>`: Google Cloud project ID (default: active gcloud project).
* `--region <REGION>`: Vertex AI region (default: `us-central1`).
* `--image-uri <IMAGE_URI>`: Artifact Registry container image URI for benchmark runner.
* `--output-gcs-bucket <URI>`: Target GCS bucket for results (default: `gs://secops-eval-results/custom_jobs`).
* `--hf-token <TOKEN>`: Hugging Face API token for downloading gated model weights (reads `HF_TOKEN` from environment if unset).
* `--dry-run`: Validate worker pool specs and configuration without submitting live Vertex AI jobs.
* `--no-wait`: Submit jobs asynchronously to Vertex AI without blocking on job completion.
* `--timeout-seconds <SEC>`: Maximum allowable runtime per CustomJob before termination (default: `3600`).

---

## 6. Output Artifacts & GCS Schema

Each completed CustomJob persists evaluation artifacts to Google Cloud Storage at `${OUTPUT_GCS_PATH}/${MODEL_FLAVOR}/`:

```
gs://secops-eval-results/custom_jobs/gemma-3-4b-it/
|-- soc_eval_report.md          # Comprehensive Markdown report with case scores & rationale
|-- eval_results.json           # Raw JSON test cases, model outputs, and assertion results
|-- benchmark_metrics.json      # TTFT, TPS, decode latency, and concurrency metrics
+-- custom_job_execution.log    # Console logs, vLLM startup traces, and health check output
```

### JSON Metrics Format Example (`benchmark_metrics.json`)
```json
{
  "flavor": "gemma-3-4b-it",
  "hardware": {
    "machine_type": "g2-standard-8",
    "accelerator_type": "NVIDIA_L4",
    "accelerator_count": 1
  },
  "metrics": {
    "time_to_first_token_ms": 42.15,
    "decode_latency_per_token_ms": 14.82,
    "tokens_per_second": 67.48,
    "total_eval_duration_sec": 128.4
  },
  "soc_eval_summary": {
    "total_cases": 10,
    "passed_cases": 9,
    "accuracy_pct": 90.0,
    "aggregate_score": 0.92
  }
}
```

---

## 7. Operational Best Practices & Guardrails

1. **Strict Cost Control**: Because CustomJobs terminate compute automatically, they are the preferred mechanism for overnight sweeps and large comparative evaluation batches.
2. **Quota Verification**: Ensure adequate Compute Engine GPU quotas (`NVIDIA_L4_GPUS`, `NVIDIA_A100_80GB_GPUS`) exist in the target region before running large concurrent sweeps.
3. **Container Pre-Warming**: Keep the runner container image updated in the local Artifact Registry region to minimize image pull latency during job startup.
4. **Token Security**: Always pass `HF_TOKEN` via environment variable or Google Secret Manager rather than hardcoding in command lines or Dockerfiles.
