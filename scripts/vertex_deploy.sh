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

# Configuration with environment fallbacks
PROJECT_ID="${GCP_PROJECT_ID:-dandye-0324-chronicle}"
REGION="${GCP_REGION:-us-central1}"
MODEL_ID="${VERTEX_MODEL_ID:-gemma-3-12b-it-1747240724884}"
ENDPOINT_NAME="${VERTEX_ENDPOINT_NAME:-gemma-endpoint-$(date +%Y%m%d)}"
DEPLOYMENT_DISPLAY_NAME="${VERTEX_DEPLOYMENT_NAME:-gemma-3-12b-deployment}"
MACHINE_TYPE="${VERTEX_MACHINE_TYPE:-g2-standard-24}"
ACCELERATOR_TYPE="${VERTEX_ACCELERATOR_TYPE:-nvidia-l4}"
ACCELERATOR_COUNT="${VERTEX_ACCELERATOR_COUNT:-2}"

echo "=========================================="
echo " Vertex AI Gemma Deployment Script"
echo "=========================================="
echo "Project:      $PROJECT_ID"
echo "Region:       $REGION"
echo "Model ID:     $MODEL_ID"
echo "Endpoint:     $ENDPOINT_NAME"
echo "Machine Type: $MACHINE_TYPE ($ACCELERATOR_COUNT x $ACCELERATOR_TYPE)"
echo "=========================================="

# 1. Create or retrieve Endpoint
echo "Step 1/2: Checking/creating Vertex AI Endpoint..."
ENDPOINT_ID=$(gcloud ai endpoints list \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --filter="displayName=$ENDPOINT_NAME" \
  --format="value(name.basename())" \
  --limit=1)

if [[ -z "$ENDPOINT_ID" ]]; then
  echo "Creating new endpoint '$ENDPOINT_NAME'..."
  ENDPOINT_ID=$(gcloud ai endpoints create \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --display-name="$ENDPOINT_NAME" \
    --format="value(name.basename())")
  echo "Created Endpoint ID: $ENDPOINT_ID"
else
  echo "Found existing Endpoint ID: $ENDPOINT_ID"
fi

# 2. Deploy Model to Endpoint
echo ""
echo "Step 2/2: Deploying model $MODEL_ID to endpoint $ENDPOINT_ID..."
echo "Note: Deployment typically takes 10-15 minutes to spin up GPUs and initialize the container."

gcloud ai endpoints deploy-model "$ENDPOINT_ID" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --model="$MODEL_ID" \
  --display-name="$DEPLOYMENT_DISPLAY_NAME" \
  --machine-type="$MACHINE_TYPE" \
  --accelerator="type=$ACCELERATOR_TYPE,count=$ACCELERATOR_COUNT" \
  --min-replica-count=1 \
  --max-replica-count=1 \
  --traffic-split=0=100

echo ""
echo "=========================================="
echo " Deployment Successfully Started / Complete!"
echo " Endpoint ID: $ENDPOINT_ID"
echo "=========================================="
