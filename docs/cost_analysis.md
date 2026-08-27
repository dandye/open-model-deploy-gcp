---
title: "Gemma & Multi-Model Serving Cost Analysis & Empirical Sizing Matrix"
description: "Comprehensive compute sizing, hardware requirements, VRAM allocations, and pricing projections for deploying Gemma, Meta Llama, and partner open-weight models on Google Cloud."
type: "analysis"
tags:
  - cost
  - gcp
  - pricing
  - gemma
  - llama
  - open-models
  - vertex-ai
  - cloud-run
created: 2026-08-24
updated: 2026-08-27
---

# Multi-Model Serving Cost Analysis & Sizing Matrix

This document provides compute specifications, hourly pricing, full/business monthly cost estimates, and **empirical throughput metrics** for serving Gemma models, Meta Llama models, and partner open-weight / OpenModels on Google Cloud Platform across **Vertex AI Online Prediction** and **Cloud Run with GPU**.

---

## 1. Summary Matrix by Model Flavor & Active Deployment Specs

> *Pricing based on standard Vertex AI on-demand rates in `us-central1` / `us-east1` / `us-west1` / `us-east5`. Monthly estimates assume 730 hours (24/7 continuous operation) and Business Hours assume 160 hours (40h/week).*

### 1.1 Google Gemma Family Sizing Matrix

| Model Flavor Key | Generation & Display Name | Parameters | Precision | Machine Type | GPU Configuration | TP Size | Context Len | Hourly Cost | Business Mo. (160h) | Full Mo. (730h) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`gemma-3-1b-it`** | **Gemma 3 1B Instruct** | 1.0B | bfloat16 | **`g2-standard-4`** | 1x NVIDIA L4 (24 GB) | 1 | 8,192 | **$0.70 / hr** | $112.00 | **$511.00** |
| **`gemma-2-2b-it`** | **Gemma 2 2B Instruct** | 2.6B | bfloat16 | **`g2-standard-4`** | 1x NVIDIA L4 (24 GB) | 1 | 4,096 | **$0.70 / hr** | $112.00 | **$511.00** |
| **`gemma-3-4b-it`** | **Gemma 3 4B Instruct** | 4.0B | bfloat16 | **`g2-standard-8`** | 1x NVIDIA L4 (24 GB) | 1 | 32,768 | **$0.76 / hr** | $121.60 | **$554.80** |
| **`gemma-2-9b-it`** | **Gemma 2 9B Instruct** | 9.2B | bfloat16 | **`g2-standard-12`** | 1x NVIDIA L4 (24 GB) | 1 | 4,096 | **$0.83 / hr** | $132.80 | **$605.90** |
| **`gemma-3-12b-it`**| **Gemma 3 12B Multimodal** | 12.0B | bfloat16 | **`g2-standard-48`** | 4x NVIDIA L4 (96 GB) | 4 | 8,192 | **$3.36 / hr** | $537.60 | **$2,452.80** |
| **`gemma-2-27b-it`**| **Gemma 2 27B Instruct** | 27.2B | bfloat16 | **`g2-standard-48`** | 4x NVIDIA L4 (96 GB) | 4 | 8,192 | **$3.36 / hr** | $537.60 | **$2,452.80** |
| **`gemma-4-e2b-it`** | **Gemma 4 E2B Instruct** | 2.3B eff | bfloat16 | **`g2-standard-4`** | 1x NVIDIA L4 (24 GB) | 1 | 8,192 | **$0.70 / hr** | $112.00 | **$511.00** |
| **`gemma-4-e4b-it`** | **Gemma 4 E4B Instruct** | 4.5B eff | bfloat16 | **`g2-standard-8`** | 1x NVIDIA L4 (24 GB) | 1 | 8,192 | **$0.76 / hr** | $121.60 | **$554.80** |
| **`gemma-4-31b-it`**| **Gemma 4 31B (1x A100 80GB)** | 31.0B | bfloat16 | **`a2-ultragpu-1g`** | 1x NVIDIA A100 (80 GB) | 1 | 8,192 | **$3.67 / hr** | $587.20 | **$2,679.10** |
| **`gemma-4-31b-it`**| **Gemma 4 31B (2x A100 NVLink)** | 31.0B | bfloat16 | **`a2-highgpu-2g`** | 2x NVIDIA A100 (80 GB NVLink) | 2 | 8,192 | **$7.34 / hr** | $1,174.40 | **$5,358.20** |
| **`gemma-4-31b-it`**| **Gemma 4 31B (4x L4 FP8)** | 31.0B | fp8 / bf16 | **`g2-standard-48`** | 4x NVIDIA L4 (96 GB) | 4 | 4,096 | **$3.36 / hr** | $537.60 | **$2,452.80** |

### 1.2 Non-Gemma Models Matrix (Meta Llama, Partner Models & OpenModels)

| Model Flavor Key | Provider & Architecture | Parameters / Shape | Serving Mode | Machine Type | GPU Hardware | Host RAM | Hourly Cost | Business Mo. (160h) | Full Mo. (730h) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`llama-4-scout-17b-16e-instruct-maas`** | Meta (Llama 4) | 17B active (16e MoE) | Serverless MaaS (`us-east5`) | Serverless | Serverless GPU Pool | N/A | **Pay-per-token** | Usage-based | Usage-based |
| **`llama-4-maverick-17b-128e-instruct-maas`**| Meta (Llama 4) | 17B active (128e MoE)| Serverless MaaS (`us-east5`) | Serverless | Serverless GPU Pool | N/A | **Pay-per-token** | Usage-based | Usage-based |
| **`llama-3.1-405b-instruct-maas`** | Meta (Llama 3.1) | 405B Dense | Serverless MaaS (`us-central1`) | Serverless | Serverless GPU Pool | N/A | **Pay-per-token** | Usage-based | Usage-based |
| **`llama-3.3-70b-instruct-maas`** | Meta (Llama 3.3) | 70B Dense | Serverless MaaS (`us-central1`) | Serverless | Serverless GPU Pool | N/A | **Pay-per-token** | Usage-based | Usage-based |
| **`llama-3.2-11b-vision-instruct-maas`** | Meta (Llama 3.2) | 11B Multimodal | Serverless MaaS (`us-central1`) | Serverless | Serverless GPU Pool | N/A | **Pay-per-token** | Usage-based | Usage-based |
| **`llama-3.1-8b-instruct-maas`** | Meta (Llama 3.1) | 8.0B Dense | Serverless MaaS (`us-central1`) | Serverless | Serverless GPU Pool | N/A | **Pay-per-token** | Usage-based | Usage-based |
| **`llama-3.2-3b-instruct`** | Meta (Llama 3.2) | 3.2B Dense | Dedicated Model Garden | **`g2-standard-8`** | 1x NVIDIA L4 (24 GB) | 32 GB | **$0.83 / hr** | $132.80 | **$605.90** |
| **`llama-guard-3-8b`** | Meta (Llama Guard) | 8.0B Safety Classifier | Dedicated Model Garden | **`g2-standard-12`**| 1x NVIDIA L4 (24 GB) | 48 GB | **$1.01 / hr** | $161.60 | **$737.30** |
| **`llama-3.1-nemotron-70b-instruct`** | NVIDIA / Meta | 70B Reward Tuned | Dedicated Model Garden | **`g2-standard-48`**| 4x NVIDIA L4 (96 GB) | 192 GB | **$3.32 / hr** | $531.20 | **$2,423.60** |
| **`inkling-small`** | Thinking Machines | Dense OpenModel | Dedicated Model Garden | **`g2-standard-48`**| 4x NVIDIA L4 (96 GB) | 192 GB | **$3.32 / hr** | $531.20 | **$2,423.60** |
| **`nemotron-3.5-lightning-bf16`** | NVIDIA | 30B MoE | Dedicated Model Garden | **`g2-standard-48`**| 4x NVIDIA L4 (96 GB) | 192 GB | **$3.32 / hr** | $531.20 | **$2,423.60** |
| **`qwen3.8-27b`** | Qwen / Alibaba | 27B Dense OpenModel | Dedicated OpenModel | **`g4-standard-48`**| 1x RTX PRO 6000 (96 GB)| 192 GB | **$3.85 / hr** | $616.00 | **$2,810.50** |
| **`qwen3.8-flash-next`** | Qwen / Alibaba | Dense OpenModel | Dedicated OpenModel | **`g2-standard-12`**| 1x NVIDIA L4 (24 GB) | 48 GB | **$1.01 / hr** | $161.60 | **$737.30** |
| **`qwen3.8-flash-next-fp8`** | Qwen / Alibaba | FP8 Quantized OpenModel| Dedicated OpenModel | **`g2-standard-8`** | 1x NVIDIA L4 (24 GB) | 32 GB | **$0.83 / hr** | $132.80 | **$605.90** |
| **`qwen3.8-2.4t-a95b-fp8`** | Qwen / Alibaba | 2.4T / A95B MoE FP8 | Dedicated OpenModel | **`g4-standard-48`**| 1x RTX PRO 6000 (96 GB)| 192 GB | **$3.85 / hr** | $616.00 | **$2,810.50** |
| **`glm-5.3-flash`** | Zhipu AI / THUDM | Dense OpenModel | Dedicated OpenModel | **`g2-standard-12`**| 1x NVIDIA L4 (24 GB) | 48 GB | **$1.01 / hr** | $161.60 | **$737.30** |
| **`deepseek-v4-pro`** | DeepSeek | MoE / Reasoner OpenModel| Dedicated OpenModel | **`g4-standard-48`**| 1x RTX PRO 6000 (96 GB)| 192 GB | **$3.85 / hr** | $616.00 | **$2,810.50** |
| **`kimi-k3`** | Moonshot AI | Long-Context OpenModel | Dedicated OpenModel | **`g4-standard-48`**| 1x RTX PRO 6000 (96 GB)| 192 GB | **$3.85 / hr** | $616.00 | **$2,810.50** |
| **`qwen2.5-coder-32b-instruct`** | Qwen / Alibaba | 32B Code Specialist | Dedicated OpenModel | **`g2-standard-48`**| 4x NVIDIA L4 (96 GB) | 192 GB | **$3.32 / hr** | $531.20 | **$2,423.60** |
| **`ministral-3b-2410`** | Mistral AI | 3.0B Dense OpenModel | Dedicated OpenModel | **`g2-standard-8`** | 1x NVIDIA L4 (24 GB) | 32 GB | **$0.83 / hr** | $132.80 | **$605.90** |
| **`phi-4`** | Microsoft | 14.0B Dense OpenModel | Dedicated OpenModel | **`g2-standard-12`**| 1x NVIDIA L4 (24 GB) | 48 GB | **$1.01 / hr** | $161.60 | **$737.30** |

---

## 2. Empirical Throughput & Token Cost-Efficiency Benchmarks

The following generation throughput and speed metrics were measured directly across live Vertex AI prediction endpoints:

### 2.1 Google Gemma Empirical Throughput & Cost per Token

| Model Flavor Key | Generation & Size | Machine Type | GPU Configuration | TP Size | Generation Speed (TPS) | Throughput (TPM) | Hourly Cost | Cost / Million Tokens | Verified Deployment Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`gemma-3-1b-it`** | Gemma 3 1.0B | `g2-standard-4` | 1x NVIDIA L4 (24 GB) | 1 | **107.9 tok/s** | **6,471 tok/min** | $0.70/hr | **$1.80 / 1M tok** | **Verified on Live Hardware** |
| **`gemma-2-2b-it`** | Gemma 2 2.6B | `g2-standard-4` | 1x NVIDIA L4 (24 GB) | 1 | **59.3 tok/s** | **3,556 tok/min** | $0.70/hr | **$3.28 / 1M tok** | **Verified on Live Hardware** |
| **`gemma-3-12b-it`** | Gemma 3 12B (Vision) | `g2-standard-48` | 4x NVIDIA L4 (96 GB) | 4 | **46.2 tok/s** | **2,769 tok/min** | $3.36/hr | **$20.22 / 1M tok** | **Verified on Live Hardware** |
| **`gemma-3-4b-it`** | Gemma 3 4B | `g2-standard-8` | 1x NVIDIA L4 (24 GB) | 1 | **45.2 tok/s** | **2,710 tok/min** | $0.76/hr | **$4.67 / 1M tok** | **Verified on Live Hardware** |
| **`gemma-2-27b-it`** | Gemma 2 27.2B | `g2-standard-48` | 4x NVIDIA L4 (96 GB) | 4 | **26.3 tok/s** | **1,576 tok/min** | $3.36/hr | **$35.59 / 1M tok** | **Verified on Live Hardware** |
| **`gemma-3-27b-it`** | Gemma 3 27B (4x L4 8 Streams Concurrency)| `g2-standard-48` | 4x NVIDIA L4 (96 GB) | 4 | **93.6 – 96.2 tok/s** | **5,614 – 5,773 tok/min**| $3.36/hr | **$9.97 / 1M tok** | **Verified on Live Hardware (EXP-11)** |
| **`gemma-3-27b-it`** | Gemma 3 27B (4x L4 4 Streams Concurrency)| `g2-standard-48` | 4x NVIDIA L4 (96 GB) | 4 | **94.1 – 94.8 tok/s** | **5,647 – 5,690 tok/min**| $3.36/hr | **$9.92 / 1M tok** | **Verified on Live Hardware (EXP-11)** |
| **`gemma-3-27b-it`** | Gemma 3 27B (4x L4 2 Streams Concurrency)| `g2-standard-48` | 4x NVIDIA L4 (96 GB) | 4 | **47.8 – 48.4 tok/s** | **2,866 – 2,907 tok/min**| $3.36/hr | **$19.54 / 1M tok** | **Verified on Live Hardware (EXP-11)** |
| **`gemma-3-27b-it`** | Gemma 3 27.0B (Vision Single Stream)    | `g2-standard-48` | 4x NVIDIA L4 (96 GB) | 4 | **25.6 – 26.8 tok/s** | **1,538 – 1,611 tok/min**| $3.36/hr | **$36.41 / 1M tok** | **Verified on Live Hardware** |
| **`gemma-2-9b-it`** | Gemma 2 9.2B | `g2-standard-12` | 1x NVIDIA L4 (24 GB) | 1 | **19.5 tok/s** | **1,170 tok/min** | $0.83/hr | **$11.82 / 1M tok** | **Verified on Live Hardware** |
| **`gemma-4-31b-it`** | Gemma 4 31B (2x A100 NVLink 8 Streams)| `a2-highgpu-2g` | 2x NVIDIA A100 (80 GB NVLink) | 2 | **77.9 – 90.1 tok/s** | **4,676 – 5,403 tok/min**| $7.34/hr | **$26.15 / 1M tok** | **Verified on Live Hardware (EXP-10)** |
| **`gemma-4-31b-it`** | Gemma 4 31B (2x A100 NVLink 4 Streams)| `a2-highgpu-2g` | 2x NVIDIA A100 (80 GB NVLink) | 2 | **40.4 tok/s** | **2,422 tok/min** | $7.34/hr | **$50.51 / 1M tok** | **Verified on Live Hardware (EXP-10)** |
| **`gemma-4-31b-it`** | Gemma 4 31B (2x A100 NVLink Single)   | `a2-highgpu-2g` | 2x NVIDIA A100 (80 GB NVLink) | 2 | **12.4 – 23.0 tok/s** | **745 – 1,382 tok/min** | $7.34/hr | **$164.20 / 1M tok** | **Verified on Live Hardware** |
| **`gemma-4-31b-it`** | Gemma 4 31B (4x L4 FP8) | `g2-standard-48` | 4x NVIDIA L4 (96 GB) | 4 | **7.1 tok/s** | **424 tok/min** | $3.36/hr | **$132.08 / 1M tok** | **Verified on Live Hardware** |
| **`gemma-4-31b-it`** | Gemma 4 31B (1x A100 80GB) | `a2-ultragpu-1g` | 1x NVIDIA A100 (80 GB) | 1 | **6.1 tok/s** | **368 tok/min** | $3.67/hr | **$166.21 / 1M tok** | **Verified on Live Hardware** |
| **`gemma-4-31b-it`** | Gemma 4 31B (4x L4 Graphs) | `g2-standard-48` | 4x NVIDIA L4 (96 GB) | 4 | **3.8 tok/s** | **230 tok/min** | $3.36/hr | **$243.48 / 1M tok** | **Verified on Live Hardware** |
| **`gemma-4-31b-it`** | Gemma 4 31B (4x L4 Eager) | `g2-standard-48` | 4x NVIDIA L4 (96 GB) | 4 | **3.1 tok/s** | **183 tok/min** | $3.36/hr | **$306.01 / 1M tok** | **Verified on Live Hardware** |

### 2.2 Non-Gemma Empirical Throughput & Token Cost-Efficiency Benchmarks

The following throughput and unit economic metrics were measured across partner, open-weight, and Llama model evaluations:

| Model Flavor Key | Architecture & Size | Machine Type / Tier | GPU Configuration | Generation Speed (TPS) | Total Throughput (TPS) | Hourly Compute Cost | Dedicated Cost / 1M Tokens | Evaluation Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`llama-4-scout-17b-16e-instruct-maas`** | 17B active MoE | Serverless MaaS (`us-east5`) | Serverless GPU Pool | **66.70 tok/s** | **332.76 tok/s** | Pay-per-token | Usage-based | **Verified on Live Hardware** |
| **`llama-4-maverick-17b-128e-instruct-maas`**| 17B active MoE | Serverless MaaS (`us-east5`) | Serverless GPU Pool | **58.73 tok/s** | **124.25 tok/s** | Pay-per-token | Usage-based | **Verified on Live Hardware** |
| **`llama-3.2-3b-instruct`** | 3.2B Dense | `g2-standard-8` | 1x NVIDIA L4 (24 GB) | **44.96 tok/s** | **250.51 tok/s** | $0.83/hr | **$5.13 / 1M tok** | **Verified on Live Hardware** |
| **`llama-guard-3-8b`** | 8.0B Safety Classifier | `g2-standard-12` | 1x NVIDIA L4 (24 GB) | **48.36 tok/s** | **201.15 tok/s** | $1.01/hr | **$5.80 / 1M tok** | **Verified on Live Hardware** |
| **`inkling-small`** | Dense OpenModel | `g2-standard-48` | 4x NVIDIA L4 (96 GB) | **51.22 tok/s** | **214.50 tok/s** | $3.32/hr | **$18.00 / 1M tok** | **Verified on Live Hardware** |
| **`llama-3.1-nemotron-70b-instruct`** | 70B Aligned Dense | `g2-standard-48` | 4x NVIDIA L4 (96 GB) | **43.93 tok/s** | **190.58 tok/s** | $3.32/hr | **$21.00 / 1M tok** | **Verified on Live Hardware** |
| **`nemotron-3.5-lightning-bf16`** | 30B MoE | `g2-standard-48` | 4x NVIDIA L4 (96 GB) | **37.02 tok/s** | **186.45 tok/s** | $3.32/hr | **$24.91 / 1M tok** | **Verified on Live Hardware** |
| **`qwen3.8-27b`** | 27B Dense OpenModel | `g4-standard-48` | 1x RTX PRO 6000 (96 GB)| **26.50 tok/s** | **101.02 tok/s** | $3.85/hr | **$40.35 / 1M tok** | **Verified on Live Hardware** |

---

## 3. Key Runtime & Architectural Constraints Learned

### A. Interconnect Speed: 600 GB/s NVLink vs Single Die vs PCIe Gen4
1. **PCIe Barrier Bottleneck (4x L4)**: On `g2-standard-48` (4x L4), GPUs communicate over PCIe Gen4 (~32 GB/s). Because custom peer-to-peer AllReduce is disabled on >2 PCIe GPUs, every forward pass incurs 128+ host synchronization barriers across 64 layers, placing an empirical ceiling at ~3.8 tok/s.
2. **Native FP8 on Ada Lovelace (4x L4)**: Ada Lovelace 4th-Gen Tensor Cores accelerate FP8 GEMMs natively, cutting weight memory streaming in half and pushing 4x L4 speed to **7.1 tok/s**.
3. **Single-Die A100 80GB (`a2-ultragpu-1g`)**: Deploying on a single 80GB GPU eliminates tensor parallelism barriers completely, delivering **6.1 tok/s** and cutting latency by **50%** (12.76s down to 6.36s).
4. **600 GB/s NVLink Mesh (`a2-highgpu-2g`, 2x A100 40GB)**: 2-way NVLink mesh removes PCIe synchronization barriers, dropping response latency to **4.29s** (-66%) and driving generation throughput to **12.4 – 23.0 tokens/second** (up to **1,382 tokens/minute**).

### B. Microarchitecture FP8 Support (Ada Lovelace vs Ampere)
* **Ada Lovelace (L4)**: Supports native hardware FP8 (`fp8e4nv` / `fp8e5`).
* **Ampere (A100)**: Does **not** support standard `fp8e4nv` Tensor Core ops. When compiling on A100, use native **BF16 weights and KV cache** (or BitsAndBytes INT8).

---

## 4. Cost Comparison: 24/7 vs On-Demand Schedules

| Deployment Schedule | 1x L4 Models (`g2-standard-4/8/12`) | 4x L4 Models (`g2-standard-48`) | 1x RTX PRO 6000 (`g4-standard-48`) | 2x A100 NVLink (`a2-highgpu-2g`) | Serverless MaaS (Llama 4 / Gemini) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **24/7 Continuous (1 Month / 730h)** | **$511.00 – $737.30** | **$2,423.60 – $2,452.80** | **$2,810.50** | **$5,358.20** | Pay only for tokens consumed |
| **Business Hours Only (40h/wk = 160h/mo)**| **$112.00 – $161.60** | **$531.20 – $537.60** | **$616.00** | **$1,174.40** | Pay only for tokens consumed |
| **Test Sessions (10h/wk = 40h/mo)** | **$28.00 – $40.40** | **$132.80 – $134.40** | **$154.00** | **$293.60** | Pay only for tokens consumed |
| **Cloud Run GPU (Scale-to-Zero)** | **$0.00 idle** (pay per active request second) | Not supported (>1 GPU required) | Not supported | Not supported | **$0.00 idle** |

---

## 5. Lifecycle Mechanics: Startup Latency, Shutdown Economics & Fast Restart Strategies

Managing serving costs across large models requires balancing **idle cost elimination** against **cold startup latency**.

### 5.1 The Vertex AI Online Prediction Lifecycle

When a dedicated GPU endpoint is undeployed (`just vertex-undeploy`), active GPU billing stops immediately (\$0.00/hr). However, restoring the endpoint (`just vertex-deploy`) is not an instant container launch because Vertex AI completely deprovisions the underlying Google Compute Engine (GCE) hardware.

Every cold deployment undergoes a 5-stage infrastructure lifecycle:

```
[1. PREPARING_MODEL] (~0.2 min)
  └── IAM resolution, container parameter parsing, and registry lookup
[2. CREATING_SERVING_CLUSTER] (~5.0 - 12.0 min)
  └── Dynamic allocation of physical GCE VMs with attached GPUs (e.g. 4x NVIDIA L4)
[3. ADDING_NODES_TO_CLUSTER] (~2.0 - 3.0 min)
  └── Node joining to Vertex AI internal serving cluster & NVIDIA driver attachment
[4. GETTING_CONTAINER_IMAGE] (~2.0 - 4.0 min)
  └── Pulling multi-gigabyte vLLM Model Garden container image from Artifact Registry
[5. CONTAINER_STARTING & WEIGHT DOWNLOAD] (~2.0 - 4.5 min)
  └── Streaming 50+ GB weights from gs://, VRAM loading, and CUDA graph pre-compilation
```

#### Empirical Provisioning Latencies Measured on Live Hardware:
* **Fresh Multi-GPU Allocation (`EXP-12`, 4x L4)**: **16.9 minutes**
* **Reused Serving Cluster Pool (`EXP-13`, 4x L4)**: **7.8 minutes**
* **Speculative Decoding Allocation (`EXP-08b`, 4x L4)**: **18.4 minutes**
* **Single A100 80GB (`EXP-04`, 1x A100)**: **12.1 minutes**
* **2x A100 NVLink Mesh (`EXP-07b`, 2x A100)**: **10.3 minutes**

---

### 5.2 Comparative Deployment Paradigms

Depending on whether sub-minute cold starts or serverless scale-to-zero are required, three primary operational models exist:

| Operational Pattern | Idle Hourly Cost | Cold Start Time | Supported Models | Operational Complexity |
| :--- | :--- | :--- | :--- | :--- |
| **Vertex AI Dedicated Endpoint** | **$0.00 / hr** (when undeployed) | **10 – 18 minutes** (full GCE cluster spin-up) | All models (1B to 70B, multi-GPU TP=1/2/4) | Low (Fully managed endpoint API) |
| **Cloud Run GPU (Scale-to-Zero)** | **$0.00 / hr** (automatic when idle) | **30 – 90 seconds** (serverless microVM boot) | Single-GPU only (1B, 2B, 4B, 9B) | Minimal (Fully managed serverless) |
| **Stopped GCE Compute Instance** | **$0.00 / hr** (pay only ~$0.04/GB/mo disk) | **~45 – 60 seconds** (cached local SSD boot) | All models (1B to 70B, multi-GPU TP=1/2/4) | Moderate (Self-managed VM scripts) |

---

### 5.3 Fast Restart Strategy for Multi-GPU Workloads

For multi-GPU models that exceed Cloud Run single-GPU limits (e.g. `gemma-3-27b-it`, `llama-3.1-nemotron-70b-instruct`, or `gemma-4-31b-it`), running a self-managed GCE instance (`g2-standard-48` or `a2-highgpu-2g`) with stopped-state economics provides near-instant spin-up without 24/7 compute billing:

1. **Pre-Cache Weights on Local Disk**: Download model weights and container images once to an attached Persistent Disk / Hyperdisk (e.g. 200 GB disk = ~\$8.00/month).
2. **Stop Instance When Idle**:
   ```bash
   gcloud compute instances stop model-serving-node --zone=us-central1-a
   ```
   *Active GPU and vCPU compute billing drops to \$0.00/hr immediately.*
3. **Fast Boot on Demand**:
   ```bash
   gcloud compute instances start model-serving-node --zone=us-central1-a
   ```
   *The VM boots, loads weights directly from local NVMe/SSD into VRAM, and accepts inference requests within **45 to 60 seconds**.*
