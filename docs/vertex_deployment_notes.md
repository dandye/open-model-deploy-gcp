---
title: "Vertex AI Gemma Deployment Guide & Troubleshooting"
description: "Operational deployment procedures, hardware configuration, and root-cause solutions for serving Gemma on Vertex AI Online Prediction."
type: "guide"
tags:
  - gemma
  - vertex-ai
  - online-prediction
  - troubleshooting
  - vllm
  - nvidia-l4
created: 2026-08-24
updated: 2026-08-24
---

# Vertex AI Gemma Deployment Guide

This guide documents the deployment process, hardware configuration, and troubleshooting solutions for serving Gemma models on Google Cloud Vertex AI Online Prediction.

---

## 1. Quick Start: Deploying to Vertex AI

Vertex AI dedicated GPU endpoints run on persistent compute instances.

### Deploy the Model
```bash
# Using Justfile:
just vertex-deploy

# Or directly using the script:
./scripts/vertex_deploy.sh
```

### Check Deployment Status
```bash
# Using Justfile:
just vertex-status

# Or directly using the script:
./scripts/vertex_status.sh
```

### Undeploy the Model (Stop GPU Billing)
Dedicated GPU endpoints do not scale to zero automatically. When testing is complete, undeploy the model to stop GPU billing immediately:
```bash
# Using Justfile:
just vertex-undeploy

# Or directly using the script:
./scripts/vertex_undeploy.sh
```

---

## 2. Configuration & Hardware Requirements

### Gemma 12B Hardware Allocation
* **Machine Type**: `g2-standard-48` (24 vCPUs, 96 GiB System RAM)
* **Accelerators**: `4x NVIDIA L4` (48 GiB total VRAM)
* **Region**: `us-central1`

```bash
gcloud ai endpoints deploy-model "$ENDPOINT_ID" \
  --project="dandye-0324-chronicle" \
  --region="us-central1" \
  --model="$MODEL_ID" \
  --display-name="gemma-3-12b-deployment" \
  --machine-type="g2-standard-48" \
  --accelerator="type=nvidia-l4,count=4" \
  --min-replica-count=1 \
  --max-replica-count=1 \
  --traffic-split=0=100
```

---

## 3. Key Troubleshooting Solutions & Lessons Learned

### A. Swap Space & System RAM Allocation
* **Error**: `ValueError: Too large swap space. 64.00 GiB out of the 15.62 GiB total CPU memory is allocated for the swap space.`
* **Root Cause**: Model Garden vLLM containers default to `--swap-space 64` (64 GiB of CPU memory for KV cache offloading). Deploying on smaller VMs (like `g2-standard-4` with 16 GiB RAM or `g2-standard-16` with ~62.5 GiB usable RAM) crashes the container during memory validation.
* **Fix**: Use `g2-standard-48` (96 GiB host RAM) to accommodate the 64 GiB swap space allocation.

### B. Machine Type & Accelerator Count Mappings
* **Error**: `INVALID_ARGUMENT: The accelerator count "1" is not allowed. The allowed numbers of accelerator "NVIDIA_L4" to use with machine type "g2-standard-48" are: [2].`
* **Root Cause**: GCP enforces fixed GPU counts per G2 machine tier:
  * `g2-standard-4`, `g2-standard-8`, `g2-standard-12`, `g2-standard-16` $\rightarrow$ exactly **1x L4** (`count=1`)
  * `g2-standard-48` $\rightarrow$ exactly **2x L4** (`count=4`)
  * `g2-standard-48` $\rightarrow$ exactly **4x L4** (`count=4`)
  * `g2-standard-96` $\rightarrow$ exactly **8x L4** (`count=8`)
* **Fix**: Ensure `--accelerator="type=nvidia-l4,count=4"` is used when selecting `g2-standard-48`.

### C. Numeric Model ID in `gcloud ai endpoints deploy-model`
* **Error**: `ERROR: (gcloud.ai.endpoints.deploy-model) There is an error while getting the model information.`
* **Root Cause**: `gcloud ai endpoints deploy-model` requires the **numeric Model ID** from Vertex AI Model Registry (e.g., `gemma-3-12b-it-1747240724884`), not a Hugging Face / Model Garden URI like `google/gemma-4-12B`.
* **Fix**: Query available model IDs with:
  ```bash
  gcloud ai models list --project="dandye-0324-chronicle" --region="us-central1"
  ```

---

## 4. Alternative: Serverless Scale-to-Zero

If you need automated scale-to-zero when idle, see:
* [`docs/cloudrun_deploy.md`](cloudrun_deploy.md) — Cloud Run GPU deployment guide.
* [`docs/vertex_cleanup_strategies.md`](vertex_cleanup_strategies.md) — Automated Cloud Scheduler / Cloud Function shutdown patterns for Vertex AI.
* [`docs/cost_analysis.md`](cost_analysis.md) — Detailed cost breakdown across Gemma model flavors.
