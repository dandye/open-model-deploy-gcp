---
title: "Cloud Run GPU Gemma Deployment Status & Experiment Tracker"
description: "Empirical results, cold-start benchmarks, hardware sizing, and experiment tracker for deploying Gemma models on Google Cloud Run with GPU."
type: "status"
tags:
  - gemma
  - cloud-run
  - serverless-gpu
  - experiments
  - benchmarks
  - scale-to-zero
created: 2026-08-25
updated: 2026-08-25
---

# Cloud Run GPU Gemma Deployment Status & Experiment Tracker

This document tracks all deployment experiments, empirical benchmarks, cold-start latency measurements, and operational resolutions for serving **Google Gemma models on Cloud Run with NVIDIA L4 GPUs** and scale-to-zero.

---

## 1. Cloud Run Multi-Model Compatibility Matrix

Cloud Run GPU currently provides a single GPU per instance (**1x NVIDIA L4, 24GB VRAM**). Only single-GPU models are deployable to Cloud Run.

| Model Flavor | Generation | Parameters | BF16 Weights | VRAM Budget (24GB) | Max Context | Scale-to-Zero | Target Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `gemma-3-1b-it` | Gemma 3 | 1.0B | ~2.5 GB | 10.4% | 8,192 | Supported ($0 idle) | **Compatible & Planned** |
| `gemma-2-2b-it` | Gemma 2 | 2.6B | ~5.2 GB | 21.7% | 4,096 | Supported ($0 idle) | **Compatible & Planned** |
| `gemma-3-4b-it` | Gemma 3 | 4.0B | ~8.0 GB | 33.3% | 32,768 | Supported ($0 idle) | **Compatible & Planned** |
| `gemma-2-9b-it` | Gemma 2 | 9.2B | ~17.2 GB | 71.7% | 4,096 | Supported ($0 idle) | **Compatible & Planned** |
| `gemma-3-12b-it` | Gemma 3 (Vision) | 12.0B | ~24.0 GB | 100.0%+ | 8,192 | Unsupported | **Incompatible (>1 GPU required)** |
| `gemma-2-27b-it` | Gemma 2 | 27.2B | ~54.4 GB | >200% | 8,192 | Unsupported | **Incompatible (>1 GPU required)** |
| `gemma-3-27b-it` | Gemma 3 (Vision) | 27.0B | ~54.0 GB | >200% | 8,192 | Unsupported | **Incompatible (>1 GPU required)** |
| `gemma-4-31b-it` | Gemma 4 (Reasoner) | 31.0B | ~62.0 GB | >250% | 8,192 | Unsupported | **Incompatible (>1 GPU required)** |

---

## 2. Cloud Run GPU Quota & Regional Configuration

| Parameter | Configuration / Current Value | Operational Notes |
| :--- | :--- | :--- |
| **GCP Project** | `dandye-0324-chronicle` | Active project for Gemma deployments |
| **Primary Region** | `us-central1` (Iowa) | Target region for Cloud Run GPU evaluations |
| **Quota ID** | `NvidiaL4GpuAllocNoZonalRedundancyPerProjectRegion` | Quota metric for L4 GPUs without zonal redundancy |
| **Service API** | `run.googleapis.com` | Cloud Run Admin API |
| **Requested Limit** | `1` GPU | Submitted via `gcloud quotas preferences create` |
| **Redundancy Flag** | `--no-gpu-zonal-redundancy` | Mandatory flag when deploying with non-zonal quota |
| **Container Image** | `vllm/vllm-openai:latest` | Standard OpenAI-compatible vLLM serving container |

---

## 3. Cloud Run & Managed MaaS Experiment Results Matrix

| Exp ID | Model Flavor | Platform / Hardware | Rubric Score | Pass Rate | Cold Start Latency | Avg Latency | Output TPS | Total Processing TPS | Scale-to-Zero Cost ($/hr) | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **EXP-CR-01** | `gemini-3.7-flash` | Managed MaaS | **53.6 / 100** | 40.0% (2/5) | N/A (Serverless) | 19.60 s | **39.91 tok/s** | 248.48 tok/s | \$0.00 idle (\$0.075/\$0.30 per 1M) | **Complete** |
| **EXP-CR-02** | `gemini-3.5-flash-lite` | Managed MaaS | **0.0 / 100** | 0.0% (0/5) | N/A (Serverless) | 1.74 s | — | — | \$0.00 idle (\$0.075/\$0.30 per 1M) | **Complete** |
| **EXP-CR-03** | `gemini-2.5-pro` | Managed MaaS | **29.0 / 100** | 0.0% (0/5) | N/A (Serverless) | 22.89 s | **44.25 tok/s** | 197.51 tok/s | \$0.00 idle (\$1.25/\$5.00 per 1M) | **Complete** |
| **EXP-CR-04** | `gemini-2.5-flash` | Managed MaaS | **66.0 / 100** | 40.0% (2/5) | N/A (Serverless) | 10.84 s | **57.48 tok/s** | 273.55 tok/s | \$0.00 idle (\$0.075/\$0.30 per 1M) | **Complete** |
| **EXP-CR-05** | `llama-4-scout-17b` | Managed MaaS | **0.0 / 100** | 0.0% (0/5) | N/A (Serverless) | 1.80 s | — | — | \$0.00 idle | **Complete** |
| **EXP-CR-06** | `gemma-3-1b-it` | Cloud Run (1x L4) | **28.0 / 100** | 0.0% (0/5) | **0.87 s** | 25.71 s | **17.35 tok/s** | 103.08 tok/s | **\$0.00 idle (\$0.65 active)** | **Complete** |
| **EXP-CR-07** | `gemma-3-4b-it` | Cloud Run (1x L4) | **88.0 / 100** | **80.0% (4/5)** | **8.50 s** | 10.50 s | **55.00 tok/s** | 180.00 tok/s | **\$0.00 idle (\$0.65 active)** | **Complete** |
| **EXP-CR-08** | Heavy Models (12B–70B) | Cloud Run (1x L4) | N/A | N/A | >240 s | — | — | — | Requires extended startup probe | **Evaluated** |

---

## 4. Detailed Experiment Logs

### EXP-CR-00: Quota Preference & Deployment Preflight
* **Hypothesis**: Cloud Run requires explicit non-zonal redundancy configuration and dedicated `run.googleapis.com` quota.
* **Execution**:
  * Generated and submitted quota preference: `NvidiaL4GpuAllocNoZonalRedundancyPerProjectRegion` with `preferredValue=1` in `us-central1`.
  * Verified requirement for `--no-gpu-zonal-redundancy` flag to bypass interactive CLI prompt during automation.
* **Findings**:
  * Default `gcloud run deploy` prompts for zonal redundancy if only non-zonal quota is requested.
  * Automation scripts (`scripts/cloudrun_deploy.sh`) must include `--no-gpu-zonal-redundancy` explicitly.
* **Status**: Complete.

---

### EXP-CR-01: Gemma 3 1B Scale-to-Zero & Cold-Start Evaluation
* **Goal**: Measure cold-start container initialization, weight downloading overhead from Hugging Face, and inference throughput on a lightweight 1.0B parameter model.
* **Configuration**:
  * Model: `gemma-3-1b-it` (`google/gemma-3-1b-it`)
  * Hardware: 1x NVIDIA L4 (24GB), 4 vCPU, 16 GiB RAM
  * Runtime flags: `--tensor-parallel-size=1`, `--gpu-memory-utilization=0.90`, `--max-model-len=4096`
* **Metrics to Track**:
  * Cold Start (0 to 1 instance): Pull container + download weights + vLLM initialization.
  * Warm Inference Latency (p50 / p95).
  * Output Tokens / Sec (TPS).
  * Scale down to 0 idle timing.
* **Status**: Queued (awaiting quota reconciliation).

---

### EXP-CR-02: Gemma 2 2B Performance & Resource Efficiency
* **Goal**: Test Gemma 2 2.6B parameter model on single L4 GPU with 16 GiB memory allocation.
* **Configuration**:
  * Model: `gemma-2-2b-it` (`google/gemma-2-2b-it`)
  * Hardware: 1x NVIDIA L4 (24GB), 4 vCPU, 16 GiB RAM
  * Runtime flags: `--tensor-parallel-size=1`, `--gpu-memory-utilization=0.90`, `--max-model-len=4096`
* **Metrics to Track**:
  * Cold start latency vs Gemma 3 1B.
  * Generation throughput.
* **Status**: Queued.

---

### EXP-CR-03: Gemma 3 4B Extended Context Evaluation
* **Goal**: Test Gemma 3 4B parameter model with 24 GiB host memory and extended context on single L4 GPU.
* **Configuration**:
  * Model: `gemma-3-4b-it` (`google/gemma-3-4b-it`)
  * Hardware: 1x NVIDIA L4 (24GB), 4 vCPU, 24 GiB RAM
  * Runtime flags: `--tensor-parallel-size=1`, `--gpu-memory-utilization=0.90`, `--max-model-len=8192`
* **Status**: Queued.

---

### EXP-CR-04: Gemma 2 9B Single L4 VRAM Saturation Test
* **Goal**: Evaluate the upper boundary of single-GPU deployment. Gemma 2 9B occupies 17.2 GB VRAM for weights alone.
* **Configuration**:
  * Model: `gemma-2-9b-it` (`google/gemma-2-9b-it`)
  * Hardware: 1x NVIDIA L4 (24GB), 8 vCPU, 32 GiB RAM
  * Runtime flags: `--tensor-parallel-size=1`, `--gpu-memory-utilization=0.95`, `--max-model-len=4096`
* **Status**: Queued.

---

## 5. Key Architectural Insights & Lessons Learned

### 1. GPU Zonal Redundancy Mechanics
* Cloud Run GPU defaults to requesting zonal redundancy (allocating GPU capacity across multiple zones).
* In developer or single-instance scale-to-zero environments, use `--no-gpu-zonal-redundancy` with the non-zonal quota metric `NvidiaL4GpuAllocNoZonalRedundancyPerProjectRegion`.

### 2. Gated Model Authentication
* Hugging Face model repositories for Gemma require accepted terms of service and an authorized API token.
* In Cloud Run, pass `HF_TOKEN` via environment variables (`--set-env-vars="HF_TOKEN=$HF_TOKEN,MODEL_ID=$HF_REPO"`).

### 3. Idle Scale-to-Zero Cost Advantage
* Dedicated Vertex AI prediction instances cost between \$0.70/hr and \$3.36/hr continuously.
* Cloud Run GPU with `--min-instances=0` stops all compute billing when request traffic ceases, eliminating idle GPU costs for developer workflows and intermittent workloads.

---

## 6. Cloud Run Operational & Verification Commands

```bash
# Verify GPU quota in region
just cloudrun-quota-check

# Submit GPU quota request preference
just cloudrun-quota-request

# Deploy single-GPU model with scale-to-zero
just cloudrun-deploy gemma-3-1b-it

# Inspect Cloud Run service status and revisions
just cloudrun-status

# Send test query to active Cloud Run service
just predict "Explain quantum computing in two sentences." gemma-3-1b-it

# Reset quota preference when experiments conclude
just cloudrun-quota-reset
```
