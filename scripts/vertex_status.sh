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
ENDPOINT_NAME="${VERTEX_ENDPOINT_NAME:-gemma-endpoint-$(date +%Y%m%d)}"

echo "=========================================="
echo " Vertex AI Deployment Status"
echo "=========================================="
echo "Project:   $PROJECT_ID"
echo "Region:    $REGION"
echo "Endpoint:  $ENDPOINT_NAME"
echo "=========================================="

# 1. Find Endpoint ID
ENDPOINT_ID=$(gcloud ai endpoints list \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --filter="display_name=$ENDPOINT_NAME" \
  --format="value(name.basename())" \
  --limit=1 2>/dev/null || true)

if [[ -z "$ENDPOINT_ID" ]]; then
  echo "[INFO] No endpoint found with display name '$ENDPOINT_NAME'."
  echo ""
  echo "All endpoints in $REGION:"
  gcloud ai endpoints list --project="$PROJECT_ID" --region="$REGION"
  exit 0
fi

echo "[INFO] Found Endpoint ID: $ENDPOINT_ID"
echo ""

# 2. Check Deployed Models
echo "--- Endpoint Status & Deployed Models ---"
gcloud ai endpoints describe "$ENDPOINT_ID" \
  --project="$PROJECT_ID" \
  --region="$REGION"

echo ""
# 3. Check Recent Operations
echo "--- Recent Endpoint Operations ---"
OPERATIONS=$(gcloud ai operations list \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --filter="name:endpoints/$ENDPOINT_ID" \
  --format="table(name.basename():label=OPERATION_ID,done,metadata.deploymentStage:label=STAGE,error.message:label=ERROR)" \
  --limit=5 2>/dev/null || true)

if [[ -n "$OPERATIONS" ]]; then
  echo "$OPERATIONS"
else
  echo "[INFO] No recent operations found for endpoint $ENDPOINT_ID."
fi

echo ""
echo "=========================================="
