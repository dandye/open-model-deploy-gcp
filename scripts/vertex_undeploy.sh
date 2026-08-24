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
echo " Vertex AI Gemma Undeploy / Cleanup Script"
echo "=========================================="

# Find all matching endpoints
ENDPOINT_IDS=$(gcloud ai endpoints list \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --filter="displayName:$ENDPOINT_PATTERN" \
  --format="value(name.basename())" 2>/dev/null || true)

if [[ -z "$ENDPOINT_IDS" ]]; then
  echo "No active endpoints found matching '$ENDPOINT_PATTERN'."
  exit 0
fi

for ENDPOINT_ID in $ENDPOINT_IDS; do
  DISPLAY_NAME=$(gcloud ai endpoints describe "$ENDPOINT_ID" \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --format="value(displayName)" 2>/dev/null || echo "$ENDPOINT_ID")

  echo ""
  echo "Processing Endpoint: $DISPLAY_NAME (ID: $ENDPOINT_ID)"

  # Find deployed model IDs
  DEPLOYED_MODEL_IDS=$(gcloud ai endpoints describe "$ENDPOINT_ID" \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --format="value(deployedModels[].id)" 2>/dev/null || true)

  if [[ -z "$DEPLOYED_MODEL_IDS" ]]; then
    echo "No deployed models attached to endpoint $ENDPOINT_ID."
  else
    for DEPLOYED_ID in $DEPLOYED_MODEL_IDS; do
      echo "Undeploying model $DEPLOYED_ID from endpoint $ENDPOINT_ID to stop billing..."
      gcloud ai endpoints undeploy-model "$ENDPOINT_ID" \
        --project="$PROJECT_ID" \
        --region="$REGION" \
        --deployed-model-id="$DEPLOYED_ID"
    done
    echo "All models undeployed from $ENDPOINT_ID. GPU billing stopped."
  fi
done

echo ""
echo "=========================================="
