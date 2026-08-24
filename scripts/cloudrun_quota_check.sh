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

echo "Checking Cloud Run NVIDIA L4 GPU quota in $REGION..."

# 1. Ensure Cloud Quotas API is enabled
gcloud services enable cloudquotas.googleapis.com --project="$PROJECT_ID" >/dev/null 2>&1 || true

# 2. Check current limit using Cloud Quotas API
LIMIT=$(gcloud quotas info list \
  --service="run.googleapis.com" \
  --project="$PROJECT_ID" \
  --filter="quotaId:gpu AND (dimensions.region:$REGION OR dimensions.location:$REGION)" \
  --format="value(currentLimit)" 2>/dev/null | head -n 1 || echo "")

if [[ -n "$LIMIT" && "$LIMIT" != "0" ]]; then
  echo "[OK] Cloud Run GPU Quota verified (Current limit: $LIMIT in $REGION)."
  exit 0
fi

# If limit is 0 or could not be determined
echo "[WARNING] Cloud Run NVIDIA L4 GPU quota appears to be 0 or pending approval in $REGION."
echo "If your quota was just submitted, Google Cloud may take a few minutes to process the approval."
echo ""
echo "To check or edit your quota request, visit:"
echo "  https://console.cloud.google.com/iam-admin/quotas?project=$PROJECT_ID&filter=service:run.googleapis.com"
echo ""
read -r -p "Do you want to proceed with deployment anyway? (y/N): " PROCEED
if [[ "$PROCEED" =~ ^[Yy]$ ]]; then
  exit 0
else
  echo "Deployment aborted. Re-run after quota approval is confirmed."
  exit 1
fi
