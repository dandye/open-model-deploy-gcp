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
SERVICE_NAME="${CLOUDRUN_SERVICE_NAME:-gemma-cloudrun-service}"

echo "=============================================================================="
echo " Cloud Run Status & Resources"
echo "=============================================================================="
echo "Project:  $PROJECT_ID"
echo "Region:   $REGION"
echo "Service:  $SERVICE_NAME"
echo "=============================================================================="

# 1. Check GPU Quota
echo "--- GPU Quota Status ($REGION) ---"
GRANTED=$(gcloud quotas preferences list \
  --project="$PROJECT_ID" \
  --filter="quotaId:NvidiaL4GpuAllocNoZonalRedundancyPerProjectRegion AND dimensions.region:$REGION" \
  --format="value(quotaConfig.grantedValue)" 2>/dev/null | head -n 1 || echo "")

RECONCILING=$(gcloud quotas preferences list \
  --project="$PROJECT_ID" \
  --filter="quotaId:NvidiaL4GpuAllocNoZonalRedundancyPerProjectRegion AND dimensions.region:$REGION" \
  --format="value(reconciling)" 2>/dev/null | head -n 1 || echo "")

if [[ -n "$GRANTED" && "$GRANTED" != "0" ]]; then
  echo "[OK] NVIDIA L4 GPU Quota Limit: $GRANTED"
elif [[ "$RECONCILING" == "True" || "$RECONCILING" == "true" ]]; then
  echo "[INFO] NVIDIA L4 GPU Quota: 0 (Request pending / reconciling in GCP)"
else
  echo "[WARNING] NVIDIA L4 GPU Quota: 0 (Unrequested)"
fi

echo ""
# 2. Check Service Status
echo "--- Cloud Run Services ---"
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --format="value(status.url)" 2>/dev/null || echo "")

if [[ -n "$SERVICE_URL" ]]; then
  echo "[OK] Service '$SERVICE_NAME' is active."
  echo "URL: $SERVICE_URL"
  gcloud run services describe "$SERVICE_NAME" \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --format="table(status.conditions[0].type:label=CONDITION,status.conditions[0].status:label=STATUS,spec.template.spec.containers[0].resources.limits.cpu:label=CPU,spec.template.spec.containers[0].resources.limits.memory:label=MEMORY,spec.template.metadata.annotations['autoscaling.knative.dev/minScale']:label=MIN_INSTANCES)"
else
  echo "[INFO] Service '$SERVICE_NAME' not found in $REGION."
  echo ""
  echo "All Cloud Run services in $REGION:"
  gcloud run services list --project="$PROJECT_ID" --region="$REGION" 2>/dev/null || true
fi

echo ""
echo "=============================================================================="
