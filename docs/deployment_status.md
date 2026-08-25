---
title: "Gemma Model Deployment Status & Compatibility Matrix"
description: "Comprehensive deployment status, hardware validation, live test results, and operational guidelines for Gemma 2 and Gemma 3 models on Google Cloud Platform."
type: "guide"
tags:
  - gemma
  - vertex-ai
  - cloud-run
  - deployment-status
  - compatibility-matrix
  - gpu
created: 2026-08-24
updated: 2026-08-24
---

# Gemma Model Deployment Status & Compatibility Matrix

This document provides a live tracking matrix, hardware sizing guide, verified test records, and operational configurations for deploying Google Gemma models across Google Cloud Platform (Vertex AI Online Prediction and Cloud Run GPU).

---

## 1. Multi-Model Deployment Matrix

The table below summarizes the catalog status, compute profile, and environment compatibility for each model variant defined in [`configs/models.json`](../configs/models.json).

| Model Flavor | Generation | Parameters | Weights (BF16) | Target Machine | GPUs | TP Size | Context Len | Vertex AI | Cloud Run GPU | Validation Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `gemma-3-1b-it` | Gemma 3 | 1.0B | ~2.5 GB | `g2-standard-4` | 1x L4 (24GB) | 1 | 32,768 | Compatible | Compatible (Scale-to-0) | Catalog Ready |
| `gemma-3-4b-it` | Gemma 3 | 4.0B | ~8.0 GB | `g2-standard-8` | 1x L4 (24GB) | 1 | 32,768 | Compatible | Compatible (Scale-to-0) | **Live & Verified** |
| `gemma-3-12b-it` | Gemma 3 (Vision) | 12.0B | ~24.0 GB | `g2-standard-48` | 4x L4 (96GB) | 4 | 8,192 | Compatible | Incompatible (>1 GPU) | **Live & Verified** |
| `gemma-3-27b-it` | Gemma 3 | 27.0B | ~54.0 GB | `g2-standard-48` | 4x L4 (96GB) | 4 | 8,192 | Compatible | Incompatible (>1 GPU) | Catalog Ready |
| `gemma-2-2b-it` | Gemma 2 | 2.6B | ~5.2 GB | `g2-standard-4` | 1x L4 (24GB) | 1 | 8,192 | Compatible | Compatible (Scale-to-0) | Catalog Ready |
| `gemma-2-9b-it` | Gemma 2 | 9.2B | ~17.2 GB | `g2-standard-12` | 1x L4 (24GB) | 1 | 4,096 | Compatible | Compatible (Scale-to-0) | **Live & Verified** |
| `gemma-2-27b-it` | Gemma 2 | 27.2B | ~54.4 GB | `g2-standard-48` | 4x L4 (96GB) | 4 | 8,192 | Compatible | Incompatible (>1 GPU) | Catalog Ready |
| `gemma-4-31b-it` | Gemma 4 | 31.0B | ~62.0 GB | `g2-standard-48` | 4x L4 (96GB) | 4 | 16,384 | Compatible | Incompatible (>1 GPU) | Catalog Ready |

---

## 2. Empirical Benchmark & Throughput Metrics

The following metrics were measured directly on active Google Cloud Vertex AI dedicated prediction endpoints running Google Model Garden vLLM serving containers:

| Model Flavor Key | Generation & Size | Machine Type | GPU Configuration | TP Size | Avg Latency | Avg Output | Tokens / Sec (TPS) | Tokens / Min (TPM) | Hourly Cost |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`gemma-3-12b-it`** | Gemma 3 12B (Vision) | **`g2-standard-48`** | 4x NVIDIA L4 (96 GB) | 4 | **4.90 s** | 226 tokens | **46.2 tok/s** | **2,769 tok/min** | $3.36/hr |
| **`gemma-3-4b-it`** | Gemma 3 4B | **`g2-standard-8`** | 1x NVIDIA L4 (24 GB) | 1 | **5.45 s** | 246 tokens | **45.2 tok/s** | **2,710 tok/min** | $0.76/hr |
| **`gemma-2-9b-it`** | Gemma 2 9B | **`g2-standard-12`** | 1x NVIDIA L4 (24 GB) | 1 | **17.55 s** | 341 tokens | **19.5 tok/s** | **1,170 tok/min** | $0.83/hr |

---

## 3. Live Verified Deployment Records

### Gemma 2 9B (`gemma-2-9b-it`)

* **Deployment Environment**: Vertex AI Online Prediction
* **Region**: `us-central1` (Iowa)
* **Endpoint Name**: `gemma-2-9b-it-endpoint-20260824-2335`
* **Endpoint ID**: `8720346016903069696`
* **Model ID**: `540441301133295616`
* **Container Image**: `us-docker.pkg.dev/vertex-ai/vertex-vision-model-garden-dockers/pytorch-vllm-serve:20240922_0916_RC00`
* **Machine Type**: `g2-standard-12` (12 vCPUs, 48 GB Host RAM, 1 x NVIDIA L4 GPU 24GB)
* **Hourly Cost**: $0.84/hour
* **vLLM Engine Configuration**:
  * `gpu-memory-utilization`: `0.95`
  * `max-model-len`: `4096`
  * `swap-space`: `16`

#### Verified Live Test Output

**Prompt**:
```text
What is the capital of France and what is it famous for?
```

**Vertex AI Response**:
```text
The capital of France is **Paris**.

Paris is famous for many things, including:

* **The Eiffel Tower:** An iconic wrought-iron lattice tower that offers stunning views of the city.
* **The Louvre Museum:** Home to world-renowned masterpieces such as the Mona Lisa and Venus de Milo.
* **The Arc de Triomphe:** A triumphal arch honoring French military victories.
* **Notre Dame Cathedral:** A magnificent Gothic cathedral that has been a symbol of Paris for centuries.
* **The Champs-Élysées:** A grand avenue lined with shops, restaurants, and theaters.
* **Fashion and Design:** Paris is considered a global center for fashion and design.
* **Gastronomy:** French cuisine is world-renowned, and Paris is home to some of the best restaurants in the world.
* **Romance:** Paris is often called the "City of Love" due to its charming atmosphere and romantic landmarks.
* **Art and Culture:** Paris has a rich history of art and culture, and is home to many theaters, museums, and galleries.
```

---

### Gemma 3 12B Multimodal (`gemma-3-12b-it`)

* **Deployment Environment**: Vertex AI Online Prediction
* **Region**: `us-central1` (Iowa)
* **Endpoint Name**: `gemma-3-12b-it-endpoint-20260825-0030`
* **Endpoint ID**: `6747347167649726464`
* **Deployed Model ID**: `7282826922562682880`
* **Model Registry ID**: `9027448410633928704`
* **Container Image**: `us-docker.pkg.dev/vertex-ai/vertex-vision-model-garden-dockers/pytorch-vllm-serve:20250312_0916_RC01`
* **Machine Type**: `g2-standard-48` (48 vCPUs, 192 GB Host RAM, 4 x NVIDIA L4 GPUs 96GB total VRAM)
* **Tensor Parallelism**: `tensor-parallel-size=4`
* **Hourly Cost**: $3.36/hour
* **vLLM Engine Configuration**:
  * `gpu-memory-utilization`: `0.90`
  * `max-model-len`: `8192`
  * `swap-space`: `32`

#### Verified Live Test Output

**Prompt**:
```text
What are three key features of Gemma 3 12B?
```

**Vertex AI Response**:
```text
Here are three key features of the Gemma 3 12B model:

1.  **Improved Performance:** Gemma 3 12B demonstrates significant performance gains over its predecessor, Gemma 2. It surpasses the previous model on a wide range of benchmarks, particularly in reasoning, coding, and mathematical capabilities.
2.  **Longer Context Length:** Gemma 3 12B boasts an 8,192 token context length. This allows the model to process and understand much longer inputs, enabling better performance on tasks requiring more context and memory.
3.  **Mixture-of-Experts (MoE) Architecture:** A key architectural change is the introduction of a Mixture-of-Experts (MoE) layer. This allows the model to access more parameters when needed, without increasing inference cost.
```

### Gemma 3 4B Instruct (`gemma-3-4b-it`)

* **Deployment Environment**: Vertex AI Online Prediction
* **Region**: `us-central1` (Iowa)
* **Endpoint Name**: `gemma-3-4b-it-endpoint-20260825-0048`
* **Endpoint ID**: `3800163424000802816`
* **Deployed Model ID**: `7323922269162438656`
* **Model Registry ID**: `1516570132086784000`
* **Container Image**: `us-docker.pkg.dev/vertex-ai/vertex-vision-model-garden-dockers/pytorch-vllm-serve:20250312_0916_RC01`
* **Machine Type**: `g2-standard-8` (8 vCPUs, 32 GB Host RAM, 1 x NVIDIA L4 GPU 24GB)
* **Tensor Parallelism**: `tensor-parallel-size=1`
* **Hourly Cost**: $0.76/hour
* **vLLM Engine Configuration**:
  * `gpu-memory-utilization`: `0.90`
  * `max-model-len`: `32768`
  * `swap-space`: `16`

#### Verified Live Test Output

**Prompt**:
```text
List 3 benefits of the Gemma 3 4B model.
```

**Vertex AI Response**:
```text
Here are 3 benefits of the Gemma 3 4B model:

1.  **Open and Accessible:** Gemma is an open-weights model, meaning its weights are publicly available. This allows researchers, developers, and anyone interested to download, study, modify, and use the model freely, fostering innovation and transparency.
2.  **Relatively Small Size:** With 4 billion parameters, Gemma 3 4B is smaller than many other large language models. This smaller size makes it more practical to run on consumer-grade hardware, reducing the computational resources required for inference.
3.  **Strong Performance for its Size:** Despite its relatively small size, Gemma 3 4B demonstrates competitive performance on a range of benchmarks and tasks, often outperforming larger models in certain areas.
```

---

## 3. Parallel Deployment Records

### Gemma 4 31B Multimodal Reasoner (`gemma-4-31b-it`)

* **Deployment Environment**: Vertex AI Online Prediction
* **Region**: `us-west1` (Oregon)
* **Model Size**: 31.0B parameters (multimodal text, image, video reasoning, tool calling)
* **Source URI**: `gs://vertex-model-garden-restricted-us/gemma4/gemma-4-31B-it`
* **Container Image**: `us-docker.pkg.dev/vertex-ai/vertex-vision-model-garden-dockers/pytorch-vllm-serve:gemma4`
* **Machine Type**: `g2-standard-48` (48 vCPUs, 192 GB Host RAM, 4 x NVIDIA L4 GPUs 96GB total VRAM)
* **Tensor Parallelism**: `tensor-parallel-size=4`
* **Hourly Cost**: $3.36/hour
* **vLLM Engine Configuration**:
  * `gpu-memory-utilization`: `0.90`
  * `max-model-len`: `16384`
  * `extraArgs`: `["--limit-mm-per-prompt.image=4", "--limit-mm-per-prompt.video=1", "--enable-auto-tool-choice", "--tool-call-parser=gemma4", "--reasoning-parser=gemma4"]`
* **Status**: Registering & deploying in parallel.

---

## 4. Key Architectural Constraints & Proven Resolutions

### 1. KV Cache Exhaustion on Single L4 GPU (24GB)
* **Symptom**: Model server exits during startup with `ValueError: The model's max seq len (8192) is larger than the maximum number of tokens that can be stored in KV cache (576)`.
* **Root Cause**: Gemma 2 9B weights require 17.22 GB of VRAM. With the default `gpu-memory-utilization=0.90` (21.6 GB budget), only ~4.3 GB remains for KV cache and activations. An 8192 sequence length context requires more memory than available.
* **Resolution**: 
  1. Increase `gpu-memory-utilization` from `0.90` to `0.95` (22.8 GB budget).
  2. Set `max-model-len` to `4096`. This frees sufficient VRAM for high-throughput batching and stable serving.

### 2. Host RAM & Swap Space Configuration
* **Symptom**: Startup failure with `ValueError: Too large swap space`.
* **Root Cause**: Custom Model Garden container specifications must set `--swap-space` in proportion to host RAM:
  * `<= 32 GB` Host RAM (`g2-standard-4`): `--swap-space=8`
  * `48 GB` Host RAM (`g2-standard-12`): `--swap-space=16`
  * `192 GB` Host RAM (`g2-standard-48`): `--swap-space=32`

### 3. Container Entrypoint Wrapper
* **Rule**: When registering Model Garden images (`pytorch-vllm-serve`), do **not** override `command` in `gcloud ai models upload`. The default Model Garden wrapper script downloads the weights from Cloud Storage and sets required environment variables before starting vLLM.

---

## 5. Verification & Testing Commands

To test any active deployment across Vertex AI or Cloud Run:

```bash
# Query the active Gemma 2 9B endpoint
just predict "Explain quantum computing in simple terms."

# Query a specific model flavor
just predict "What are the primary colors?" gemma-2-9b-it

# Check status of all Vertex AI and Cloud Run resources
just status

# Check Vertex AI endpoints and active operations
just vertex-status
```
