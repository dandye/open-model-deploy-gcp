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

echo "=============================================================================="
echo " Requesting Cloud Run GPU Quota Increase"
echo "=============================================================================="
echo "Project:      $PROJECT_ID"
echo "Region:       $REGION"
echo "Requested:    $DESIRED_GPUS x NVIDIA L4 GPU"
echo "=============================================================================="

# 1. Enable Cloud Quotas API
echo "Step 1/2: Ensuring Cloud Quotas API is enabled..."
gcloud services enable cloudquotas.googleapis.com --project="$PROJECT_ID"

# Resolve contact email
CONTACT_EMAIL=$(gcloud config get-value account 2>/dev/null || echo "dandye@google.com")
if [[ -z "$CONTACT_EMAIL" ]]; then
  CONTACT_EMAIL="dandye@google.com"
fi

# 2. Check for existing preference
echo "Step 2/2: Submitting Quota Preference for $CONTACT_EMAIL..."
EXISTING_PREF_ID=$(gcloud quotas preferences list \
  --project="$PROJECT_ID" \
  --filter="quotaId:NvidiaL4GpuAllocNoZonalRedundancyPerProjectRegion AND dimensions.region:$REGION" \
  --format="value(name)" 2>/dev/null | sed 's|.*/||' | head -n 1 || echo "")

if [[ -n "$EXISTING_PREF_ID" ]]; then
  echo "Found existing quota preference '$EXISTING_PREF_ID'. Updating preference parameters..."
  gcloud quotas preferences update "$EXISTING_PREF_ID" \
    --project="$PROJECT_ID" \
    --service="run.googleapis.com" \
    --quota-id="NvidiaL4GpuAllocNoZonalRedundancyPerProjectRegion" \
    --dimensions="region=$REGION" \
    --preferred-value="$DESIRED_GPUS" \
    --email="$CONTACT_EMAIL" \
    --justification="Gemma model inference evaluation on Cloud Run with scale-to-zero"
else
  echo "Creating new quota preference..."
  gcloud quotas preferences create \
    --service="run.googleapis.com" \
    --project="$PROJECT_ID" \
    --quota-id="NvidiaL4GpuAllocNoZonalRedundancyPerProjectRegion" \
    --dimensions="region=$REGION" \
    --preferred-value="$DESIRED_GPUS" \
    --email="$CONTACT_EMAIL" \
    --justification="Gemma model inference evaluation on Cloud Run with scale-to-zero"
fi

echo ""
echo "=============================================================================="
echo "Quota preference submitted / updated successfully."
echo "View or manage status in Google Cloud Console:"
echo "  https://console.cloud.google.com/iam-admin/quotas?project=$PROJECT_ID&filter=service:run.googleapis.com"
echo "=============================================================================="
