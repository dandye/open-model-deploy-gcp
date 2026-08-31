#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
if [[ -f "${ROOT_DIR}/.env" ]]; then
  set -a
  source "${ROOT_DIR}/.env"
  set +a
fi

PROJECT_ID="${GCP_PROJECT_ID:-dandye-0324-chronicle}"
REGION="${GCP_REGION:-us-central1}"
MODE="${1:-check}"

echo "=============================================================================="
echo " Cloud Run GPU Quota Status Check ($REGION)"
echo "=============================================================================="

# 1. Ensure Cloud Quotas API is enabled
gcloud services enable cloudquotas.googleapis.com --project="$PROJECT_ID" >/dev/null 2>&1 || true

# 2. Check current preference and limit using Cloud Quotas API
GRANTED=$(gcloud quotas preferences list \
  --project="$PROJECT_ID" \
  --filter="quotaId:NvidiaL4GpuAllocNoZonalRedundancyPerProjectRegion AND dimensions.region:$REGION" \
  --format="value(quotaConfig.grantedValue)" 2>/dev/null | head -n 1 || echo "")

PREFERRED=$(gcloud quotas preferences list \
  --project="$PROJECT_ID" \
  --filter="quotaId:NvidiaL4GpuAllocNoZonalRedundancyPerProjectRegion AND dimensions.region:$REGION" \
  --format="value(quotaConfig.preferredValue)" 2>/dev/null | head -n 1 || echo "")

RECONCILING=$(gcloud quotas preferences list \
  --project="$PROJECT_ID" \
  --filter="quotaId:NvidiaL4GpuAllocNoZonalRedundancyPerProjectRegion AND dimensions.region:$REGION" \
  --format="value(reconciling)" 2>/dev/null | head -n 1 || echo "")

PREF_ID=$(gcloud quotas preferences list \
  --project="$PROJECT_ID" \
  --filter="quotaId:NvidiaL4GpuAllocNoZonalRedundancyPerProjectRegion AND dimensions.region:$REGION" \
  --format="value(name)" 2>/dev/null | sed 's|.*/||' | head -n 1 || echo "")

echo "Project:               $PROJECT_ID"
echo "Region:                $REGION"
echo "Quota Metric:          run.googleapis.com/nvidia_l4_gpu_allocation_no_zonal_redundancy"
echo "Quota ID:              NvidiaL4GpuAllocNoZonalRedundancyPerProjectRegion"
if [[ -n "$PREF_ID" ]]; then
  echo "Preference Request ID: $PREF_ID"
fi
echo "Preferred Value:       ${PREFERRED:-1}"
echo "Granted Value:         ${GRANTED:-0}"
echo "Reconciling (Pending): ${RECONCILING:-False}"
echo "=============================================================================="

if [[ -n "$GRANTED" && "$GRANTED" != "0" ]]; then
  echo "[OK] Cloud Run GPU quota is active and granted ($GRANTED x NVIDIA L4 GPU in $REGION)."
  exit 0
fi

if [[ "$RECONCILING" == "True" || "$RECONCILING" == "true" ]]; then
  echo "[INFO] Cloud Run GPU quota request is currently pending / reconciling in $REGION."
  echo "  Preference ID: ${PREF_ID}"
  echo "  Status: Submitted to Google Cloud; awaiting quota fulfillment/approval."
  echo ""
  echo "Manage or view status in Google Cloud Console:"
  echo "  https://console.cloud.google.com/iam-admin/quotas?project=$PROJECT_ID&filter=service:run.googleapis.com"
else
  echo "[WARNING] Cloud Run NVIDIA L4 GPU quota is 0 (unrequested) in $REGION."
  echo "  To submit a quota increase request, run:"
  echo "    just cloudrun-quota-request"
  echo ""
  echo "Or manage directly in Google Cloud Console:"
  echo "  https://console.cloud.google.com/iam-admin/quotas?project=$PROJECT_ID&filter=service:run.googleapis.com"
fi
echo ""

if [[ "$MODE" == "--pre-deploy" || "$MODE" == "--deploy-gate" ]]; then
  if [[ ! -t 0 ]]; then
    echo "[ERROR] Cannot deploy: Cloud Run GPU quota is not granted ($GRANTED) and shell is non-interactive."
    exit 1
  fi
  read -r -p "Do you want to proceed with deployment anyway? (y/N): " PROCEED
  if [[ "$PROCEED" =~ ^[Yy]$ ]]; then
    echo "Proceeding with deployment..."
    exit 0
  else
    echo "Deployment aborted. Re-run after quota approval is confirmed."
    exit 1
  fi
fi

exit 0
