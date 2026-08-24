# Deploying Gemma to Cloud Run with GPU (Scale-to-Zero)

This guide covers deploying Gemma to Google Cloud Run with an NVIDIA L4 GPU to enable true **scale-to-zero** (0 instances when idle, $0 cost).

---

## 1. Prerequisites: Cloud Run GPU Quota

Cloud Run GPU requires a quota allocation for `run.googleapis.com` in your region (`us-central1`).

### Option A: Request Quota via `gcloud` CLI (Programmatic)

First, enable the Cloud Quotas API:
```bash
gcloud services enable cloudquotas.googleapis.com --project="dandye-0324-chronicle"
```

List available Cloud Run GPU quota metrics:
```bash
gcloud quotas info list \
  --service="run.googleapis.com" \
  --project="dandye-0324-chronicle" \
  --filter="quotaId:gpu"
```

Submit a quota increase request for NVIDIA L4 GPUs in `us-central1`:
```bash
# Request 1x NVIDIA L4 GPU allocation for Cloud Run in us-central1
gcloud quotas preferences create \
  --service="run.googleapis.com" \
  --project="dandye-0324-chronicle" \
  --quota-id="nvidia-l4-gpus-per-project-region" \
  --dimensions="region=us-central1" \
  --preferred-value=1 \
  --justification="Gemma model inference on Cloud Run"
```

---

### Option B: Request Quota via Web Console (Fastest / UI)

1. Open the [**Cloud Run Quotas Console**](https://console.cloud.google.com/iam-admin/quotas?project=dandye-0324-chronicle&filter=service:run.googleapis.com).
2. Filter for:
   - **Service**: `Cloud Run Admin API` (`run.googleapis.com`)
   - **Metric**: `NVIDIA L4 GPUs` (or `GPUs per project region`)
   - **Dimensions**: `us-central1`
3. Click **Edit Quotas**, enter `1` (or `2`), and click **Submit Request**.
4. Quota increases are typically reviewed and approved within minutes to a few hours.

---

## 2. Deploying the Service

Once quota is approved, run the deployment script:

```bash
# Set your Hugging Face token (if using gated models)
export HF_TOKEN="<YOUR_HF_TOKEN>"

# Deploy to Cloud Run
./scripts/cloudrun_deploy.sh
```

---

## 3. Testing the Endpoint

After deployment, call the OpenAI-compatible `/v1/chat/completions` route:

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
