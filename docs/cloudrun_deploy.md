---
title: "Deploying Gemma to Cloud Run with GPU (Scale-to-Zero)"
description: "Comprehensive guide for deploying Gemma models on Google Cloud Run with NVIDIA L4 GPUs and true serverless scale-to-zero."
type: "guide"
tags:
  - gemma
  - cloud-run
  - serverless-gpu
  - scale-to-zero
  - vllm
  - nvidia-l4
created: 2026-08-24
updated: 2026-08-24
---

# Deploying Gemma to Cloud Run with GPU (Scale-to-Zero)

This guide covers deploying Gemma models to Google Cloud Run with an NVIDIA L4 GPU to enable true **scale-to-zero** (0 instances when idle, $0 cost).

---

## 1. Prerequisites: Cloud Run GPU Quota

Cloud Run GPU requires a quota allocation for `run.googleapis.com` in your region (`us-central1`).

### Verify Quota
```bash
# Check quota status using Justfile:
just cloudrun-quota-check

# Or directly:
./scripts/cloudrun_quota_check.sh
```

### Request Quota

#### Option A: Via `gcloud` CLI / Justfile
```bash
just cloudrun-quota-request
```
Or directly:
```bash
gcloud services enable cloudquotas.googleapis.com --project="dandye-0324-chronicle"

gcloud quotas preferences create \
  --service="run.googleapis.com" \
  --project="dandye-0324-chronicle" \
  --quota-id="nvidia-l4-gpus-per-project-region" \
  --dimensions="region=us-central1" \
  --preferred-value=1 \
  --justification="Gemma model inference on Cloud Run"
```

#### Option B: Via Web Console
1. Open the [Cloud Run Quotas Console](https://console.cloud.google.com/iam-admin/quotas?project=dandye-0324-chronicle&filter=service:run.googleapis.com).
2. Filter for:
   * **Service**: `Cloud Run Admin API` (`run.googleapis.com`)
   * **Metric**: `NVIDIA L4 GPUs` (or `Total Nvidia L4 GPU allocation without zonal redundancy`)
   * **Dimensions**: `us-central1`
3. Click **Edit Quotas**, enter `1` (or `2`), and click **Submit Request**.

---

## 2. Deploying the Service

Once quota is approved, run the deployment:

```bash
# Using Justfile (automatically checks quota first):
just cloudrun-deploy

# Or directly using the script:
./scripts/cloudrun_deploy.sh
```

To check service status, revisions, and URL after deployment:
```bash
just cloudrun-status
```

---

## 3. Testing the Endpoint

Call the OpenAI-compatible `/v1/chat/completions` route:

```bash
SERVICE_URL=$(gcloud run services describe gemma-cloudrun-service \
  --project="dandye-0324-chronicle" \
  --region="us-central1" \
  --format="value(status.url)")

curl "$SERVICE_URL/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "google/gemma-2-9b-it",
    "messages": [
      {"role": "user", "content": "Explain quantum computing in 2 sentences."}
    ]
  }'
```

---

## 4. Resetting Quota (Optional)

To tear down or reset the GPU quota preference back to 0:

```bash
just cloudrun-quota-reset
```
