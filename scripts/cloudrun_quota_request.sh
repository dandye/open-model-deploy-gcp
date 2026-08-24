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
echo "Step 1/2: Enabling Cloud Quotas API..."
gcloud services enable cloudquotas.googleapis.com --project="$PROJECT_ID"

# 2. Submit Quota Preference
echo "Step 2/2: Submitting Quota Preference Request..."
gcloud quotas preferences create \
  --service="run.googleapis.com" \
  --project="$PROJECT_ID" \
  --quota-id="nvidia-l4-gpus-per-project-region" \
  --dimensions="region=$REGION" \
  --preferred-value="$DESIRED_GPUS" \
  --justification="Gemma model inference on Cloud Run" || {
    echo ""
    echo "Note: If the quota-id differs for your account type, view available quota IDs using:"
    echo "  gcloud quotas info list --service=run.googleapis.com --project=$PROJECT_ID"
    echo "Or submit directly via the web UI at: https://console.cloud.google.com/iam-admin/quotas?project=$PROJECT_ID&filter=service:run.googleapis.com"
}

echo ""
echo "Quota request submitted. Check status at: https://console.cloud.google.com/iam-admin/quotas?project=$PROJECT_ID"
