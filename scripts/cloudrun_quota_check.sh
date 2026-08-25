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

# 2. Check current limit or preference using Cloud Quotas API
GRANTED=$(gcloud quotas preferences list \
  --project="$PROJECT_ID" \
  --filter="quotaId:NvidiaL4GpuAllocNoZonalRedundancyPerProjectRegion AND dimensions.region:$REGION" \
  --format="value(quotaConfig.grantedValue)" 2>/dev/null | head -n 1 || echo "")

RECONCILING=$(gcloud quotas preferences list \
  --project="$PROJECT_ID" \
  --filter="quotaId:NvidiaL4GpuAllocNoZonalRedundancyPerProjectRegion AND dimensions.region:$REGION" \
  --format="value(reconciling)" 2>/dev/null | head -n 1 || echo "")

if [[ -n "$GRANTED" && "$GRANTED" != "0" ]]; then
  echo "[OK] Cloud Run GPU Quota verified (Granted limit: $GRANTED in $REGION)."
  exit 0
fi

if [[ "$RECONCILING" == "True" || "$RECONCILING" == "true" ]]; then
  echo "[INFO] Cloud Run GPU quota request is currently reconciling/pending in $REGION."
else
  echo "[WARNING] Cloud Run NVIDIA L4 GPU quota appears to be 0 or unrequested in $REGION."
fi
echo ""
echo "To check or edit your quota request, visit:"
echo "  https://console.cloud.google.com/iam-admin/quotas?project=$PROJECT_ID&filter=service:run.googleapis.com"
echo ""

# Non-interactive or auto-prompt
if [[ ! -t 0 ]]; then
  echo "Non-interactive shell detected. Continuing..."
  exit 0
fi

read -r -p "Do you want to proceed with deployment anyway? (y/N): " PROCEED
if [[ "$PROCEED" =~ ^[Yy]$ ]]; then
  exit 0
else
  echo "Deployment aborted. Re-run after quota approval is confirmed."
  exit 1
fi
