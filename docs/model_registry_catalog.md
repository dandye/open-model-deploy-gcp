---
title: "Vertex AI Model Registry Catalog & Construction Guide"
description: "Comprehensive registry catalog of all Gemma and custom models registered in Vertex AI Model Registry across regions, including container configurations, optimization flags, and creation commands."
type: "guide"
tags:
  - gemma
  - vertex-ai
  - model-registry
  - catalog
  - deployment
created: 2026-08-25
updated: 2026-08-25
---

# Vertex AI Model Registry Catalog & Construction Guide

This document maintains a complete, authoritative catalog of all model definitions registered in the **Google Cloud Vertex AI Model Registry** for project `dandye-0324-chronicle`.

It details the **Model IDs**, **Display Names**, **Container Image URIs**, **GCS Weights Sources**, **Optimization Flags**, and the **exact commands used to create each model**.

---

## 1. Master Model Registry Inventory

> *Note: Model definitions stored in Vertex AI Model Registry carry **\$0.00 storage cost** when not attached to an active endpoint. Compute charges only occur when a model is deployed to dedicated GPU instances.*

### Region: `us-east1` (South Carolina)

| Model ID | Display Name | Target Flavor | Machine / GPUs | Description | Created |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`6666666653670965248`** | `gemma-3-27b-it-quantization-fp8-specula-model-garden` | `gemma-3-27b-it` | `g2-standard-48` (4x L4) | Gemma 3 27B Instruct with FP8 Quantization and Prompt Lookup (N-gram) Speculative Decoding on 4x NVIDIA L4 GPUs (g2-standard-48). | 2026-08-25 22:44 |
| **`5380326010103267328`** | `gemma-3-27b-it-quantization-fp8-enable--model-garden` | `gemma-3-27b-it` | `g2-standard-48` (4x L4) | Gemma 3 27B Instruct with FP8 Quantization, Chunked Prefill, and Automatic Prefix Caching on 4x NVIDIA L4 GPUs (g2-standard-48). | 2026-08-25 20:07 |
| **`7193024860119891968`** | `gemma-3-27b-it-quantization-fp8-model-garden` | `gemma-3-27b-it` | `g2-standard-48` (4x L4) | Gemma 3 27B Instruct with Native Hardware FP8 (W8A8) Quantization on 4x NVIDIA L4 GPUs (g2-standard-48). | 2026-08-25 19:47 |
| **`7426649090789736448`** | `gemma-4-31b-it-model-garden` | `gemma-4-31b-it` | `a2-highgpu-2g` (2x A100) | Gemma 4 31B Instruct Multimodal Reasoner in Native BF16 with vLLM V1 Engine on 2x NVIDIA A100 40GB NVLink (a2-highgpu-2g). | 2026-08-25 15:42 |
| **`4643987471028191232`** | `gemma-2-27b-it-model-garden` | `gemma-2-27b-it` | `g2-standard-48` (4x L4) | Gemma 2 27B Instruct in Native BF16 on 4x NVIDIA L4 GPUs (g2-standard-48). | 2026-08-25 01:49 |

---

### Region: `us-central1` (Iowa)

| Model ID | Display Name | Target Flavor | Machine / GPUs | Description | Created |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`5612620381459316736`** | `gemma-3-27b-it-quantization-fp8-model-garden` | `gemma-3-27b-it` | `g2-standard-48` (4x L4) | Gemma 3 27B Instruct with Native Hardware FP8 (W8A8) Quantization on 4x NVIDIA L4 GPUs (g2-standard-48). | 2026-08-25 19:25 |
| **`1516570132086784000`** | `gemma-3-4b-it-model-garden` | `gemma-3-4b-it` | `g2-standard-8` (1x L4) | Gemma 3 4B Instruct Multimodal Vision with 32k Context Length on 1x NVIDIA L4 GPU (g2-standard-8). Active for SocTier1Agent evaluation. | 2026-08-25 00:48 |
| **`9027448410633928704`** | `gemma-3-12b-it-model-garden` | `gemma-3-12b-it` | `g2-standard-48` (4x L4) | Gemma 3 12B Instruct Multimodal Vision with 32k Context Length on 4x NVIDIA L4 GPUs (g2-standard-48). | 2026-08-25 00:30 |
| **`1389343442613567488`** | `gemma-3-1b-it-model-garden` | `gemma-3-1b-it` | `g2-standard-4` (1x L4) | Gemma 3 1B Instruct in Native BF16 with 8k Context Length on 1x NVIDIA L4 GPU (g2-standard-4). | 2026-08-25 01:25 |
| **`7723656318510170112`** | `gemma-2-2b-it-model-garden` | `gemma-2-2b-it` | `g2-standard-4` (1x L4) | Gemma 2 2B Instruct in Native BF16 on 1x NVIDIA L4 GPU (g2-standard-4). | 2026-08-25 01:25 |
| **`540441301133295616`**  | `gemma-2-9b-it-model-garden` | `gemma-2-9b-it` | `g2-standard-12` (1x L4) | Gemma 2 9B Instruct in Native BF16 with 4k Context Length on 1x NVIDIA L4 GPU (g2-standard-12). | 2026-08-24 23:35 |
| **`5242199312108093440`**  | `gemma-2-9b-it-model-garden-v3` | `gemma-2-9b-it` | `g2-standard-12` (1x L4) | Gemma 2 9B Instruct v3 in Native BF16 on 1x NVIDIA L4 GPU (g2-standard-12). | 2026-08-24 23:35 |

---

## 2. Detailed Model Records & Registration Commands

---

### Model `6666666653670965248`: Gemma 3 27B FP8 + Speculative Decoding (N-gram Prompt Lookup)
* **Model ID**: `6666666653670965248`
* **Display Name**: `gemma-3-27b-it-quantization-fp8-specula-model-garden`
* **Description**: `Gemma 3 27B Instruct with FP8 Quantization and Prompt Lookup (N-gram) Speculative Decoding on 4x NVIDIA L4 GPUs (g2-standard-48).`
* **Region**: `us-east1`

* **GCS Weights Source**: `gs://vertex-model-garden-restricted-us/gemma3/gemma-3-27b-it`
* **Container Image**: `us-docker.pkg.dev/vertex-ai/vertex-vision-model-garden-dockers/pytorch-vllm-serve:20250312_0916_RC01`
* **Target Hardware**: `g2-standard-48` (4x NVIDIA L4, 96GB VRAM, Tensor Parallelism TP=4)
* **Container Arguments**:
  ```text
  python -m vllm.entrypoints.api_server \
    --host=0.0.0.0 --port=8080 \
    --model=gs://vertex-model-garden-restricted-us/gemma3/gemma-3-27b-it \
    --tensor-parallel-size=4 \
    --gpu-memory-utilization=0.90 \
    --max-model-len=8192 \
    --swap-space=4 \
    --disable-log-stats \
    --limit_mm_per_prompt=image=5 \
    --max-num-seqs=4 \
    --quantization=fp8 \
    --speculative-model=[ngram] \
    --num-speculative-tokens=5 \
    --ngram-prompt-lookup-max=5 \
    --ngram-prompt-lookup-min=2
  ```
* **Exact Creation Command**:
  ```bash
  GCP_REGION=us-east1 \
  EXTRA_VLLM_FLAGS="--quantization=fp8 --speculative-model=[ngram] --num-speculative-tokens=5 --ngram-prompt-lookup-max=5 --ngram-prompt-lookup-min=2" \
  ./scripts/vertex_model_register.sh gemma-3-27b-it us-east1
  ```
* **Performance / Benchmark Summary**:
  * Evaluated in **`EXP-08b`**: Delivered **25.5 tokens/sec (28.2 tok/s peak)** on analytical queries and **19.4 tokens/sec** on structured JSON translation with **0 MB extra VRAM overhead**.

---

### Model `5380326010103267328`: Gemma 3 27B FP8 + Chunked Prefill & Prefix Caching
* **Model ID**: `5380326010103267328`
* **Display Name**: `gemma-3-27b-it-quantization-fp8-enable--model-garden`
* **Description**: `Gemma 3 27B Instruct with FP8 Quantization, Chunked Prefill, and Automatic Prefix Caching on 4x NVIDIA L4 GPUs (g2-standard-48).`
* **Region**: `us-east1`
* **GCS Weights Source**: `gs://vertex-model-garden-restricted-us/gemma3/gemma-3-27b-it`
* **Container Image**: `us-docker.pkg.dev/vertex-ai/vertex-vision-model-garden-dockers/pytorch-vllm-serve:20250312_0916_RC01`
* **Target Hardware**: `g2-standard-48` (4x NVIDIA L4, 96GB VRAM, Tensor Parallelism TP=4)
* **Container Arguments**:
  ```text
  python -m vllm.entrypoints.api_server \
    --host=0.0.0.0 --port=8080 \
    --model=gs://vertex-model-garden-restricted-us/gemma3/gemma-3-27b-it \
    --tensor-parallel-size=4 \
    --gpu-memory-utilization=0.90 \
    --max-model-len=8192 \
    --swap-space=4 \
    --disable-log-stats \
    --limit_mm_per_prompt=image=5 \
    --max-num-seqs=4 \
    --quantization=fp8 \
    --enable-chunked-prefill \
    --enable-prefix-caching
  ```
* **Exact Creation Command**:
  ```bash
  GCP_REGION=us-east1 \
  EXTRA_VLLM_FLAGS="--quantization=fp8 --enable-chunked-prefill --enable-prefix-caching" \
  ./scripts/vertex_model_register.sh gemma-3-27b-it us-east1
  ```
* **Performance / Benchmark Summary**:
  * Evaluated in **`EXP-13`**: Delivered **1.02x latency speedup**, **-1.6% TTFT reduction**, and **+9.9% token generation speedup** (28.0 tok/s vs 25.5 tok/s) on cached KV prefix blocks.

---

### Model `7193024860119891968`: Gemma 3 27B Native Hardware FP8 (us-east1)
* **Model ID**: `7193024860119891968`
* **Display Name**: `gemma-3-27b-it-quantization-fp8-model-garden`
* **Description**: `Gemma 3 27B Instruct with Native Hardware FP8 (W8A8) Quantization on 4x NVIDIA L4 GPUs (g2-standard-48).`
* **Region**: `us-east1` (Iowa counterpart: `5612620381459316736` in `us-central1`)
* **GCS Weights Source**: `gs://vertex-model-garden-restricted-us/gemma3/gemma-3-27b-it`
* **Container Image**: `us-docker.pkg.dev/vertex-ai/vertex-vision-model-garden-dockers/pytorch-vllm-serve:20250312_0916_RC01`
* **Target Hardware**: `g2-standard-48` (4x NVIDIA L4, 96GB VRAM, Tensor Parallelism TP=4)
* **Container Arguments**:
  ```text
  python -m vllm.entrypoints.api_server \
    --host=0.0.0.0 --port=8080 \
    --model=gs://vertex-model-garden-restricted-us/gemma3/gemma-3-27b-it \
    --tensor-parallel-size=4 \
    --gpu-memory-utilization=0.90 \
    --max-model-len=8192 \
    --swap-space=4 \
    --disable-log-stats \
    --limit_mm_per_prompt=image=5 \
    --max-num-seqs=4 \
    --quantization=fp8
  ```
* **Exact Creation Command**:
  ```bash
  GCP_REGION=us-east1 \
  EXTRA_VLLM_FLAGS="--quantization=fp8" \
  ./scripts/vertex_model_register.sh gemma-3-27b-it us-east1
  ```
* **Performance / Benchmark Summary**:
  * Evaluated in **`EXP-12`**: Reached **148.8 tokens/sec peak throughput (8,926 TPM)** at $N=8$ streams (**+54.6% increase** over BF16 baseline), **6.53s single-stream latency (-33.6%)**, and reduced serving cost to **\$6.27 per 1M output tokens**.

---

### Model `7426649090789736448`: Gemma 4 31B Instruct Reasoner (us-east1)
* **Model ID**: `7426649090789736448`
* **Display Name**: `gemma-4-31b-it-model-garden`
* **Description**: `Gemma 4 31B Instruct Multimodal Reasoner in Native BF16 with vLLM V1 Engine on 2x NVIDIA A100 40GB NVLink (a2-highgpu-2g).`
* **Region**: `us-east1`
* **GCS Weights Source**: `gs://vertex-model-garden-restricted-us/gemma4/gemma-4-31B-it`
* **Container Image**: `us-docker.pkg.dev/vertex-ai/vertex-vision-model-garden-dockers/pytorch-vllm-serve:gemma4`
* **Target Hardware**: `a2-highgpu-2g` (2x NVIDIA A100 40GB NVLink, TP=2) or `a2-ultragpu-1g` (1x A100 80GB)
* **Container Arguments**:
  ```text
  python -m vllm.entrypoints.api_server \
    --host=0.0.0.0 --port=8080 \
    --model=gs://vertex-model-garden-restricted-us/gemma4/gemma-4-31B-it \
    --tensor-parallel-size=2 \
    --gpu-memory-utilization=0.90 \
    --max-model-len=8192 \
    --max-num-seqs=16
  ```
* **Exact Creation Command**:
  ```bash
  GCP_REGION=us-east1 ./scripts/vertex_model_register.sh gemma-4-31b-it us-east1
  ```
* **Performance / Benchmark Summary**:
  * Evaluated in **`EXP-07b` & `EXP-10`**: Reached **90.1 tokens/sec peak throughput (5,403 TPM)** and **4.29s latency** over 600 GB/s NVLink.

---

### Model `1516570132086784000`: Gemma 3 4B Instruct Multimodal (us-central1)
* **Model ID**: `1516570132086784000`
* **Display Name**: `gemma-3-4b-it-model-garden`
* **Description**: `Gemma 3 4B Instruct Multimodal Vision with 32k Context Length on 1x NVIDIA L4 GPU (g2-standard-8). Active for SocTier1Agent evaluation.`
* **Region**: `us-central1`

* **GCS Weights Source**: `gs://vertex-model-garden-restricted-us/gemma3/gemma-3-4b-it`
* **Container Image**: `us-docker.pkg.dev/vertex-ai/vertex-vision-model-garden-dockers/pytorch-vllm-serve:20250312_0916_RC01`
* **Target Hardware**: `g2-standard-8` (1x NVIDIA L4 GPU 24GB, TP=1, 32GB Host RAM)
* **Container Arguments**:
  ```text
  python -m vllm.entrypoints.api_server \
    --host=0.0.0.0 --port=8080 \
    --model=gs://vertex-model-garden-restricted-us/gemma3/gemma-3-4b-it \
    --tensor-parallel-size=1 \
    --swap-space=16 \
    --gpu-memory-utilization=0.90 \
    --max-model-len=32768 \
    --disable-log-stats \
    --limit_mm_per_prompt=image=5 \
    --max-num-seqs=4
  ```
* **Exact Creation Command**:
  ```bash
  GCP_REGION=us-central1 ./scripts/vertex_model_register.sh gemma-3-4b-it us-central1
  ```
* **Active Status**:
  * Actively deployed to Endpoint `4868079485641031680` supporting the live `SocTier1Agent` evaluation suite in `agent_engine`.

---

## 3. How Models Are Registered & Managed

All model registration in this repository is centralized and automated through [`scripts/vertex_model_register.sh`](../scripts/vertex_model_register.sh) and the model catalog at [`configs/models.json`](../configs/models.json).

```
                      ┌──────────────────────┐
                      │ configs/models.json  │
                      └──────────┬───────────┘
                                 │
                                 ▼
                   ┌────────────────────────────┐
                   │ scripts/lib/model_catalog  │
                   └─────────────┬──────────────┘
                                 │ (Extract compute, TP size, swap space, image)
                                 ▼
                   ┌────────────────────────────┐
                   │ vertex_model_register.sh   │
                   └─────────────┬──────────────┘
                                 │ (Constructs ^|^ custom delimiter container args)
                                 ▼
             ┌────────────────────────────────────────┐
             │ gcloud ai models upload                │
             │   --project=dandye-0324-chronicle      │
             │   --region=<us-central1 | us-east1>    │
             │   --display-name=<flavor-slug>         │
             │   --container-image-uri=<image>        │
             │   --container-args=^|^python|-m|...    │
             └───────────────────┬────────────────────┘
                                 │
                                 ▼
             ┌────────────────────────────────────────┐
             │ Vertex AI Model Registry               │
             │   (Assigned Numeric Model ID)          │
             └────────────────────────────────────────┘
```

### Idempotency & Unique Slug Generation
1. **Dynamic Slug Naming**: When optimization flags are passed (e.g. `EXTRA_VLLM_FLAGS="--quantization=fp8"`), the script generates a unique display name (e.g., `gemma-3-27b-it-quantization-fp8-model-garden`).
2. **Registry Deduplication**: If a model with that display name already exists in the target region, the script reuses the existing numeric Model ID rather than creating duplicates.
3. **Delimiter Escaping (`^|^`)**: Arguments with spaces or JSON parameters are safely passed into the Google Model Garden container without shell token fragmentation.

---

## 4. Quick Reference: Deploying Any Registered Model

To deploy any registered model from this catalog directly by its **numeric Model ID**, run:

```bash
# 1. Create an endpoint
ENDPOINT_ID=$(gcloud ai endpoints create \
  --project="dandye-0324-chronicle" \
  --region="us-east1" \
  --display-name="gemma-3-27b-speculative-endpoint" \
  --format="value(name.basename())")

# 2. Deploy the registered Model ID (e.g. 6666666653670965248)
gcloud ai endpoints deploy-model "$ENDPOINT_ID" \
  --project="dandye-0324-chronicle" \
  --region="us-east1" \
  --model="6666666653670965248" \
  --display-name="gemma-3-27b-speculative-deployed" \
  --machine-type="g2-standard-48" \
  --accelerator="type=nvidia-l4,count=4" \
  --min-replica-count=1 \
  --max-replica-count=1
```

To deploy via the automated CLI:
```bash
GCP_REGION=us-east1 \
EXTRA_VLLM_FLAGS="--quantization=fp8 --speculative-model=[ngram] --num-speculative-tokens=5 --ngram-prompt-lookup-max=5 --ngram-prompt-lookup-min=2" \
./scripts/vertex_deploy.sh gemma-3-27b-it
```
