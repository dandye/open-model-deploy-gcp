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

echo "=============================================================================="
echo " Resetting Cloud Run GPU Quota Preference"
echo "=============================================================================="
echo "Project:  $PROJECT_ID"
echo "Region:   $REGION"
echo "=============================================================================="

CONTACT_EMAIL=$(gcloud config get-value account 2>/dev/null || echo "dandye@google.com")
if [[ -z "$CONTACT_EMAIL" ]]; then
  CONTACT_EMAIL="dandye@google.com"
fi

EXISTING_PREF_ID=$(gcloud quotas preferences list \
  --project="$PROJECT_ID" \
  --filter="quotaId:NvidiaL4GpuAllocNoZonalRedundancyPerProjectRegion AND dimensions.region:$REGION" \
  --format="value(name)" 2>/dev/null | sed 's|.*/||' | head -n 1 || echo "")

if [[ -n "$EXISTING_PREF_ID" ]]; then
  echo "Updating existing quota preference '$EXISTING_PREF_ID' (preferred-value=0)..."
  gcloud quotas preferences update "$EXISTING_PREF_ID" \
    --project="$PROJECT_ID" \
    --service="run.googleapis.com" \
    --quota-id="NvidiaL4GpuAllocNoZonalRedundancyPerProjectRegion" \
    --dimensions="region=$REGION" \
    --preferred-value=0 \
    --email="$CONTACT_EMAIL" \
    --allow-high-percentage-quota-decrease \
    --justification="Resetting test Cloud Run GPU quota back to 0"
else
  echo "Submitting quota reset request (preferred-value=0)..."
  gcloud quotas preferences create \
    --service="run.googleapis.com" \
    --project="$PROJECT_ID" \
    --quota-id="NvidiaL4GpuAllocNoZonalRedundancyPerProjectRegion" \
    --dimensions="region=$REGION" \
    --preferred-value=0 \
    --email="$CONTACT_EMAIL" \
    --allow-high-percentage-quota-decrease \
    --justification="Resetting test Cloud Run GPU quota back to 0" || {
      echo "Note: Quota limit can also be adjusted via console at:"
      echo "  https://console.cloud.google.com/iam-admin/quotas?project=$PROJECT_ID&filter=service:run.googleapis.com"
  }
fi

echo ""
echo "=============================================================================="
echo "Quota reset submitted successfully."
echo "=============================================================================="
