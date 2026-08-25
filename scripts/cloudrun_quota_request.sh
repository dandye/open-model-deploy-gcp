#!/usr/bin/env bash
set -euo pipefail

# Load environment variables from .env if present
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
if [[ -f "${ROOT_DIR}/.env" ]]; then
  set -a
  source "${ROOT_DIR}/.env"
  set +a
fi

PROJECT_ID="${GCP_PROJECT_ID:-dandye-0324-chronicle}"
REGION="${GCP_REGION:-us-central1}"
DESIRED_GPUS="${CLOUDRUN_GPU_COUNT:-1}"

echo "=========================================="
echo " Requesting Cloud Run GPU Quota Increase"
echo "=========================================="
echo "Project:      $PROJECT_ID"
echo "Region:       $REGION"
echo "Requested:    $DESIRED_GPUS x NVIDIA L4 GPU"
echo "=========================================="

# 1. Enable Cloud Quotas API
echo "Step 1/2: Ensuring Cloud Quotas API is enabled..."
gcloud services enable cloudquotas.googleapis.com --project="$PROJECT_ID"

# Resolve contact email
CONTACT_EMAIL=$(gcloud config get-value account 2>/dev/null || echo "admin@dandye.altostrat.com")

# 2. Submit Quota Preference
echo "Step 2/2: Submitting Quota Preference Request for $CONTACT_EMAIL..."
gcloud quotas preferences create \
  --service="run.googleapis.com" \
  --project="$PROJECT_ID" \
  --quota-id="NvidiaL4GpuAllocNoZonalRedundancyPerProjectRegion" \
  --dimensions="region=$REGION" \
  --preferred-value="$DESIRED_GPUS" \
  --email="$CONTACT_EMAIL" \
  --justification="Gemma model inference on Cloud Run" || {
    echo ""
    echo "Note: If the quota request fails, view available quota IDs using:"
    echo "  gcloud quotas info list --service=run.googleapis.com --project=$PROJECT_ID"
    echo "Or submit directly via the web UI at: https://console.cloud.google.com/iam-admin/quotas?project=$PROJECT_ID&filter=service:run.googleapis.com"
}

echo ""
echo "Quota request submitted. Check status at: https://console.cloud.google.com/iam-admin/quotas?project=$PROJECT_ID"

