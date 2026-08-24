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
VERTEX_ENDPOINT_NAME="${VERTEX_ENDPOINT_NAME:-gemma-endpoint-$(date +%Y%m%d)}"
CLOUDRUN_SERVICE_NAME="${CLOUDRUN_SERVICE_NAME:-gemma-cloudrun-service}"

echo "=============================================================================="
echo " GCP Gemma Deployment State Dashboard"
echo "=============================================================================="
echo "Project: $PROJECT_ID  |  Region: $REGION"
echo "Timestamp: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "=============================================================================="

# ------------------------------------------------------------------------------
# 1. Vertex AI State
# ------------------------------------------------------------------------------
echo ""
echo "=== 1. Vertex AI Online Prediction ==="
echo ""
echo "[1.1 Registered Models in Model Registry]"
gcloud ai models list \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --format="table(name.basename():label=MODEL_ID,displayName:label=DISPLAY_NAME,createTime.date(format='%Y-%m-%d %H:%M'):label=CREATED)" 2>/dev/null || echo "[INFO] No models registered."

echo ""
echo "[1.2 Active Endpoints & Deployed Models]"
ENDPOINTS=$(gcloud ai endpoints list \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --format="table(name.basename():label=ENDPOINT_ID,displayName:label=DISPLAY_NAME,deployedModels[0].id:label=DEPLOYED_MODEL,deployedModels[0].model.basename():label=BASE_MODEL)" 2>/dev/null || echo "")

if [[ -n "$ENDPOINTS" ]]; then
  echo "$ENDPOINTS"
else
  echo "[INFO] No endpoints found."
fi

echo ""
echo "[1.3 Recent Vertex AI Operations]"
OPERATIONS=$(gcloud ai operations list \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --format="table(name.basename():label=OPERATION_ID,done:label=DONE,metadata.deploymentStage:label=STAGE,error.message:label=ERROR)" \
  --limit=5 2>/dev/null || echo "")

if [[ -n "$OPERATIONS" ]]; then
  echo "$OPERATIONS"
else
  echo "[INFO] No active operations."
fi

# ------------------------------------------------------------------------------
# 2. Cloud Run State
# ------------------------------------------------------------------------------
echo ""
echo "=== 2. Cloud Run Serverless GPU ==="
echo ""
echo "[2.1 NVIDIA L4 GPU Quota]"
GPU_LIMIT=$(gcloud quotas info list \
  --service="run.googleapis.com" \
  --project="$PROJECT_ID" \
  --filter="quotaId:gpu AND (dimensions.region:$REGION OR dimensions.location:$REGION)" \
  --format="value(currentLimit)" 2>/dev/null | head -n 1 || echo "0")

if [[ -n "$GPU_LIMIT" && "$GPU_LIMIT" != "0" ]]; then
  echo "Current Quota Limit: $GPU_LIMIT L4 GPU(s) in $REGION [OK]"
else
  echo "Current Quota Limit: 0 (or pending approval) [WARNING]"
fi

echo ""
echo "[2.2 Cloud Run Services]"
SERVICES=$(gcloud run services list \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --format="table(SERVICE:label=SERVICE,REGION:label=REGION,URL:label=URL,LAST_DEPLOYED_BY:label=DEPLOYED_BY)" 2>/dev/null || echo "")

if [[ -n "$SERVICES" ]]; then
  echo "$SERVICES"
else
  echo "[INFO] No Cloud Run services found in $REGION."
fi

# ------------------------------------------------------------------------------
# 3. Environment Export Snippet
# ------------------------------------------------------------------------------
echo ""
echo "=============================================================================="
echo " Current Resource Identifiers (Copy/Paste into Shell)"
echo "=============================================================================="

FOUND_ENDPOINT_ID=$(gcloud ai endpoints list \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --filter="display_name=$VERTEX_ENDPOINT_NAME" \
  --format="value(name.basename())" \
  --limit=1 2>/dev/null || true)

FOUND_SERVICE_URL=$(gcloud run services describe "$CLOUDRUN_SERVICE_NAME" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --format="value(status.url)" 2>/dev/null || true)

echo "export GCP_PROJECT_ID=\"$PROJECT_ID\""
echo "export GCP_REGION=\"$REGION\""
if [[ -n "$FOUND_ENDPOINT_ID" ]]; then
  echo "export VERTEX_ENDPOINT_ID=\"$FOUND_ENDPOINT_ID\""
fi
if [[ -n "$FOUND_SERVICE_URL" ]]; then
  echo "export CLOUDRUN_SERVICE_URL=\"$FOUND_SERVICE_URL\""
fi
echo "=============================================================================="
