---
title: "Gemma Model Flavors: Hardware Requirements & Cost Analysis"
description: "Hardware sizing, memory footprints, runtime parameters, and hourly, weekly, and monthly cost projections for Gemma 2, Gemma 3, and Gemma 4 models on Google Cloud."
type: "analysis"
tags:
  - gemma
  - gemma2
  - gemma3
  - gemma4
  - cost-analysis
  - hardware-sizing
  - gcp-pricing
  - vertex-ai
  - vram
created: 2026-08-24
updated: 2026-08-25
---

# Gemma Model Flavors: Hardware Requirements & Cost Analysis

This document provides hardware sizing, memory requirements, vLLM engine configurations, and cost estimates (Hourly, Weekly, Monthly) for deploying all supported Google Gemma models (Gemma 2, Gemma 3, Gemma 4) on Google Cloud Vertex AI and Cloud Run GPU.

---

## 1. Summary Matrix by Model Flavor & Active Deployment Specs

> *Pricing based on standard Vertex AI on-demand rates in `us-central1` / `us-east1` / `us-west1`. Monthly estimates assume 730 hours (24/7 continuous operation) and Business Hours assume 160 hours (40h/week).*

| Model Flavor Key | Generation & Display Name | Parameters | Precision | Machine Type | GPU Configuration | TP Size | Context Len | Hourly Cost | Business Mo. (160h) | Full Mo. (730h) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`gemma-3-1b-it`** | **Gemma 3 1B Instruct** | 1.0B | bfloat16 | **`g2-standard-4`** | 1x NVIDIA L4 (24 GB) | 1 | 8,192 | **$0.70 / hr** | $112.00 | **$511.00** |
| **`gemma-2-2b-it`** | **Gemma 2 2B Instruct** | 2.6B | bfloat16 | **`g2-standard-4`** | 1x NVIDIA L4 (24 GB) | 1 | 4,096 | **$0.70 / hr** | $112.00 | **$511.00** |
| **`gemma-3-4b-it`** | **Gemma 3 4B Instruct** | 4.0B | bfloat16 | **`g2-standard-8`** | 1x NVIDIA L4 (24 GB) | 1 | 32,768 | **$0.76 / hr** | $121.60 | **$554.80** |
| **`gemma-2-9b-it`** | **Gemma 2 9B Instruct** | 9.2B | bfloat16 | **`g2-standard-12`** | 1x NVIDIA L4 (24 GB) | 1 | 4,096 | **$0.83 / hr** | $132.80 | **$605.90** |
| **`gemma-3-12b-it`**| **Gemma 3 12B Multimodal** | 12.0B | bfloat16 | **`g2-standard-48`** | 4x NVIDIA L4 (96 GB) | 4 | 8,192 | **$3.36 / hr** | $537.60 | **$2,452.80** |
| **`gemma-2-27b-it`**| **Gemma 2 27B Instruct** | 27.2B | bfloat16 | **`g2-standard-48`** | 4x NVIDIA L4 (96 GB) | 4 | 8,192 | **$3.36 / hr** | $537.60 | **$2,452.80** |
| **`gemma-3-27b-it`**| **Gemma 3 27B Multimodal** | 27.0B | bfloat16 | **`g2-standard-48`** | 4x NVIDIA L4 (96 GB) | 4 | 8,192 | **$3.36 / hr** | $537.60 | **$2,452.80** |
| **`gemma-4-31b-it`**| **Gemma 4 31B Reasoner** | 31.0B | bfloat16 | **`g2-standard-48`** | 4x NVIDIA L4 (96 GB) | 4 | 8,192 | **$3.36 / hr** | $537.60 | **$2,452.80** |

---

## 2. Empirical Throughput & Token Cost-Efficiency Benchmarks

The following generation throughput and speed metrics were measured directly across live Vertex AI prediction endpoints:

| Model Flavor Key | Generation & Size | Machine Type | GPU Configuration | TP Size | Generation Speed (TPS) | Throughput (TPM) | Hourly Cost | Cost / Million Tokens |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`gemma-3-1b-it`** | Gemma 3 1.0B | `g2-standard-4` | 1x NVIDIA L4 (24 GB) | 1 | **107.9 tok/s** | **6,471 tok/min** | $0.70/hr | **$1.80 / 1M tok** |
| **`gemma-2-2b-it`** | Gemma 2 2.6B | `g2-standard-4` | 1x NVIDIA L4 (24 GB) | 1 | **59.3 tok/s** | **3,556 tok/min** | $0.70/hr | **$3.28 / 1M tok** |
| **`gemma-3-12b-it`** | Gemma 3 12B (Vision) | `g2-standard-48` | 4x NVIDIA L4 (96 GB) | 4 | **46.2 tok/s** | **2,769 tok/min** | $3.36/hr | **$20.22 / 1M tok** |
| **`gemma-3-4b-it`** | Gemma 3 4B | `g2-standard-8` | 1x NVIDIA L4 (24 GB) | 1 | **45.2 tok/s** | **2,710 tok/min** | $0.76/hr | **$4.67 / 1M tok** |
| **`gemma-3-27b-it`** | Gemma 3 27B (Vision) | `g2-standard-48` | 4x NVIDIA L4 (96 GB) | 4 | **23.7 tok/s** | **1,423 tok/min** | $3.36/hr | **$39.35 / 1M tok** |
| **`gemma-2-9b-it`** | Gemma 2 9B | `g2-standard-12` | 1x NVIDIA L4 (24 GB) | 1 | **19.5 tok/s** | **1,170 tok/min** | $0.83/hr | **$11.82 / 1M tok** |
| **`gemma-4-31b-it`** | Gemma 4 31B (Reasoner) | `g2-standard-48` | 4x NVIDIA L4 (96 GB) | 4 | **3.1 tok/s** | **183 tok/min** | $3.36/hr | **$306.01 / 1M tok** |

---

## 3. Key Runtime & Architectural Constraints Learned

### A. Host RAM & vLLM Swap Allocation Rules
1. **Tensor Parallel Swap Multiplier**: vLLM multiplies `--swap-space` by the number of tensor-parallel workers. On `g2-standard-48` (192GB RAM, TP=4), setting `--swap-space=32` instructs vLLM to allocate 128GB of host swap space, leading to CPU memory exhaustion and KV cache warnings. Setting `--swap-space=4` (16GB total) prevents host OOM while maintaining memory safety.
2. **Small VM Host Memory Guard**: `g2-standard-4` has only 16GB total Host RAM. Reserving `--swap-space=8` leaves only ~7.6GB for Python runtime and CUDA graph capture. Use `--swap-space=2` for all single-GPU instances on `g2-standard-4`.

### B. Gemma 4 Engine Initialization Rules
1. **`torch.compile` Broadcast Timeout**: On 4x NVIDIA L4 GPUs, `torch.compile` during initial graph compilation takes ~68 seconds. This exceeds the default 60s shared memory broadcast timeout between vLLM EngineCore and APIServer. Passing `--enforce-eager` bypasses compilation and enables instantaneous, reliable initialization.
2. **Strict CLI Flag Validation**: The Model Garden `pytorch-vllm-serve:gemma4` container wrapper strictly checks supported CLI flags and fails if unknown flags (`--swap-space`, `--disable-log-stats`) are passed. These flags are conditionally omitted for Gemma 4.

### C. Multimodal Parameter Filtering
* `--limit_mm_per_prompt` arguments must only be passed to multimodal model variants (`gemma-3-12b-it`, `gemma-3-27b-it`, `gemma-4-31b-it`). Text-only architectures (`gemma-3-1b-it`, `gemma-3-4b-it`) reject multimodal flags during vLLM argument validation.

---

## 4. Cost Comparison: 24/7 vs On-Demand Schedules

| Deployment Schedule | Gemma 2 9B (`g2-standard-12`, 1x L4) | Gemma 3 12B / 27B / Gemma 4 (`g2-standard-48`, 4x L4) |
| :--- | :--- | :--- |
| **24/7 Continuous (1 Month / 730h)** | **$605.90** | **$2,452.80** |
| **Business Hours Only (40h / week = 160h / month)** | **$132.80** | **$537.60** |
| **Test Sessions (10h / week = 40h / month)** | **$33.20** | **$134.40** |
| **Cloud Run GPU (Scale-to-Zero)** | Pay only per request second | Not supported (>1 GPU required) |
