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
ENDPOINT_PATTERN="${VERTEX_ENDPOINT_NAME:-gemma-endpoint*}"

echo "=========================================="
echo " Vertex AI Deployment Status"
echo "=========================================="
echo "Project:  $PROJECT_ID"
echo "Region:   $REGION"
echo "Pattern:  $ENDPOINT_PATTERN"
echo "=========================================="

# 1. Find Most Recent Endpoint ID matching pattern
ENDPOINT_ID=$(gcloud ai endpoints list \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --filter="displayName:$ENDPOINT_PATTERN" \
  --sort-by="~createTime" \
  --format="value(name.basename())" \
  --limit=1 2>/dev/null || true)

if [[ -z "$ENDPOINT_ID" ]]; then
  echo "[INFO] No endpoint found matching '$ENDPOINT_PATTERN'."
  echo ""
  echo "All endpoints in $REGION:"
  gcloud ai endpoints list --project="$PROJECT_ID" --region="$REGION"
  exit 0
fi

DISPLAY_NAME=$(gcloud ai endpoints describe "$ENDPOINT_ID" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --format="value(displayName)" 2>/dev/null || echo "$ENDPOINT_ID")

echo "[INFO] Active Endpoint: $DISPLAY_NAME (ID: $ENDPOINT_ID)"
echo ""

# 2. Check Deployed Models
echo "--- Endpoint Status & Deployed Models ---"
gcloud ai endpoints describe "$ENDPOINT_ID" \
  --project="$PROJECT_ID" \
  --region="$REGION"

echo ""
# 3. Check Active Operation Details
echo "--- Active Deployment Operations ---"
OPERATION_ID="${1:-}"

if [[ -z "$OPERATION_ID" && -f "${ROOT_DIR}/.vertex_active_operation" ]]; then
  OPERATION_ID=$(cat "${ROOT_DIR}/.vertex_active_operation" | tr -d '[:space:]')
fi

if [[ -n "$OPERATION_ID" ]]; then
  OP_DETAILS=$(gcloud ai operations describe "$OPERATION_ID" \
    --project="$PROJECT_ID" \
    --region="$REGION" 2>/dev/null || true)

  if [[ -n "$OP_DETAILS" ]]; then
    echo "Operation ID: $OPERATION_ID"
    STAGE=$(echo "$OP_DETAILS" | grep "deploymentStage:" | awk '{print $2}' || echo "UNKNOWN")
    DONE=$(echo "$OP_DETAILS" | grep "^done:" | awk '{print $2}' || echo "false")
    echo "Deployment Stage: $STAGE"
    echo "Operation Done:   $DONE"
    echo ""
    echo "$OP_DETAILS"
  fi
else
  echo "[INFO] No operation ID specified. Pass as: just vertex-status <OPERATION_ID>"
fi

echo ""
echo "=========================================="
