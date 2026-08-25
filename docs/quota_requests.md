---
title: "Google Cloud GPU Quota Requests & Experiment Unblocking Log"
description: "Tracking active and historical GPU quota requests across GCP regions to enable high-memory single-GPU experiments for Gemma models."
type: "status"
tags:
  - quota
  - gcp
  - gpu
  - a100
  - experiments
created: 2026-08-25
updated: 2026-08-25
---

# Google Cloud GPU Quota Requests & Experiment Unblocking Log

This document tracks quota increase requests submitted to Google Cloud via the Cloud Quotas API (`cloudquotas.googleapis.com`) to unblock single-GPU and high-performance experimental tracks for Gemma models.

---

## 1. Active Quota Preference Requests

| Request ID / Preference Name | Service | Metric / Quota ID | Region | Requested Accelerator | Preferred Value | Submission Timestamp | State |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| [`9ba8e4e2-5c90-4414-bf5f-3bd789e017ed`](https://console.cloud.google.com/iam-admin/quotas?project=dandye-0324-chronicle) | `compute.googleapis.com` | `NVIDIA-A100-80GB-GPUS-per-project-region` | `us-central1` | 1x NVIDIA A100 80GB (SXM4) | `1` | 2026-08-25T03:02:26Z | `RECONCILING` (Pending) |
| [`b9671985-5dde-415d-9a59-0dde0fcb5ad5`](https://console.cloud.google.com/iam-admin/quotas?project=dandye-0324-chronicle) | `compute.googleapis.com` | `NVIDIA-A100-80GB-GPUS-per-project-region` | `us-east1` | 1x NVIDIA A100 80GB (SXM4) | `1` | 2026-08-25T03:03:12Z | `RECONCILING` (Pending) |
| [`11ebd67e-a012-4979-bfd7-6f99a719bd23`](https://console.cloud.google.com/iam-admin/quotas?project=dandye-0324-chronicle) | `compute.googleapis.com` | `NVIDIA-A100-80GB-GPUS-per-project-region` | `us-west1` | 1x NVIDIA A100 80GB (SXM4) | `1` | 2026-08-25T03:03:18Z | `RECONCILING` (Pending) |

---

## 2. Unblocking Purpose & Experimental Target

### Experiment Target: EXP-03 (Single High-VRAM GPU Architecture)
* **Target Model**: **Gemma 4 31B Instruct (`gemma-4-31b-it`)**
* **Current Bottleneck on 4x L4 (`g2-standard-48`)**: Multi-GPU tensor parallelism requires 128+ host PCIe NCCL AllReduce synchronization barriers per token across 4 separate cards, creating an empirical ceiling of ~3.8 tok/s.
* **Proposed Target Architecture**: **`a2-ultragpu-1g`** (1x NVIDIA A100 80GB SXM4, 12 vCPUs, 170 GB Host RAM, 2,039 GB/s memory bandwidth).
* **Expected Improvement**:
  * **Zero Tensor Parallel Interconnect Latency**: Entire 62 GB BF16 model runs on a single unified memory die.
  * **Projected Generation Speed**: **25 to 35 tokens/second** (~1,500 to 2,100 tokens/minute).
  * **Cost Efficiency**: Reduces inference cost from **$306.01 / 1M tokens** down to **~$35.00 / 1M tokens**.

---

## 3. How to Submit or Query Quotas

### Query Active GPU Quotas Across Regions
```bash
gcloud compute regions describe us-central1 --project=dandye-0324-chronicle --format="json(quotas)" | jq '.quotas[] | select(.metric | contains("A100"))'
```

### Submit Additional A100 80GB Quota Requests via CLI
```bash
# Request 1x A100 80GB in us-central1
just vertex-quota-request-a100 us-central1 1

# Request 1x A100 80GB in us-east1
just vertex-quota-request-a100 us-east1 1
```

### Google Cloud Web Console
* [Google Cloud IAM & Admin: Quotas Dashboard](https://console.cloud.google.com/iam-admin/quotas?project=dandye-0324-chronicle)
