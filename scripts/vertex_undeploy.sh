#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-dandye-0324-chronicle}"
REGION="us-central1"
ENDPOINT_NAME="gemma-endpoint-$(date +%Y%m%d)"

echo "=========================================="
echo " Vertex AI Gemma Undeploy / Cleanup Script"
echo "=========================================="

# Find endpoint
ENDPOINT_ID=$(gcloud ai endpoints list \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --filter="displayName=$ENDPOINT_NAME" \
  --format="value(name.basename())" \
  --limit=1)

if [[ -z "$ENDPOINT_ID" ]]; then
  echo "No active endpoint found with display name '$ENDPOINT_NAME'."
  exit 0
fi

echo "Found Endpoint: $ENDPOINT_NAME (ID: $ENDPOINT_ID)"

# Find deployed model ID
DEPLOYED_MODEL_IDS=$(gcloud ai endpoints describe "$ENDPOINT_ID" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --format="value(deployedModels[].id)")

if [[ -z "$DEPLOYED_MODEL_IDS" ]]; then
  echo "No deployed models attached to endpoint $ENDPOINT_ID."
else
  for DEPLOYED_ID in $DEPLOYED_MODEL_IDS; do
    echo "Undeploying model $DEPLOYED_ID to stop billing..."
    gcloud ai endpoints undeploy-model "$ENDPOINT_ID" \
      --project="$PROJECT_ID" \
      --region="$REGION" \
      --deployed-model-id="$DEPLOYED_ID"
  done
  echo "All models undeployed successfully. GPU billing stopped."
fi
