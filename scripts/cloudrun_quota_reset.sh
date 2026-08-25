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

echo "=========================================="
echo " Resetting Cloud Run GPU Quota Preference"
echo "=========================================="
echo "Project:  $PROJECT_ID"
echo "Region:   $REGION"
echo "=========================================="

echo "Step 1/2: Checking existing quota preferences for run.googleapis.com..."
PREFERENCES=$(gcloud quotas preferences list \
  --project="$PROJECT_ID" \
  --filter="quotaId~NvidiaL4GpuAlloc" \
  --format="value(name)" 2>/dev/null || true)

if [[ -n "$PREFERENCES" ]]; then
  echo "Found preferences to delete:"
  for PREF in $PREFERENCES; do
    echo "  - Deleting preference: $PREF"
    gcloud quotas preferences delete "$PREF" \
      --project="$PROJECT_ID" \
      --quiet || true
  done
else
  echo "No existing named preferences found."
fi

# Resolve contact email
CONTACT_EMAIL=$(gcloud config get-value account 2>/dev/null || echo "admin@dandye.altostrat.com")

echo ""
echo "Step 2/2: Submitting quota reset request (preferred-value=0)..."
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

echo ""
echo "=========================================="
echo " Quota reset submitted successfully."
echo "=========================================="
