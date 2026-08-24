#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Source environment and catalog library
if [[ -f "${ROOT_DIR}/.env" ]]; then
  set -a
  source "${ROOT_DIR}/.env"
  set +a
fi
source "${SCRIPT_DIR}/lib/model_catalog.sh"

PROJECT_ID="${GCP_PROJECT_ID:-dandye-0324-chronicle}"
MODEL_FLAVOR="${1:-${GEMMA_MODEL_FLAVOR:-gemma-2-9b-it}}"
REGION="${2:-${GCP_REGION:-us-central1}}"

# Validate model exists in catalog
if ! catalog_model_exists "$MODEL_FLAVOR"; then
  echo "[ERROR] Model flavor '$MODEL_FLAVOR' not found in configs/models.json."
  echo "Available flavors:"
  catalog_list_models | sed 's/^/  - /'
  exit 1
fi

# Retrieve compute configuration from catalog
MACHINE_TYPE="${VERTEX_MACHINE_TYPE:-$(catalog_get_machine_type "$MODEL_FLAVOR")}"
ACCELERATOR_TYPE="${VERTEX_ACCELERATOR_TYPE:-$(catalog_get_accelerator_type "$MODEL_FLAVOR")}"
ACCELERATOR_COUNT="${VERTEX_ACCELERATOR_COUNT:-$(catalog_get_accelerator_count "$MODEL_FLAVOR")}"
ENDPOINT_NAME="${VERTEX_ENDPOINT_NAME:-${MODEL_FLAVOR}-endpoint-$(date +%Y%m%d-%H%M)}"
DEPLOYMENT_DISPLAY_NAME="${VERTEX_DEPLOYMENT_NAME:-${MODEL_FLAVOR}-deployment}"

# Step 1: Ensure Model is Registered in Model Registry
echo "=========================================="
echo " Vertex AI Gemma Deployment Script"
echo "=========================================="
echo "Project:      $PROJECT_ID"
echo "Region:       $REGION"
echo "Model Flavor: $MODEL_FLAVOR"
echo "Endpoint:     $ENDPOINT_NAME"
echo "Machine Type: $MACHINE_TYPE ($ACCELERATOR_COUNT x $ACCELERATOR_TYPE)"
echo "=========================================="

echo "Step 1/3: Resolving Model ID from Model Registry..."
MODEL_ID="${VERTEX_MODEL_ID:-}"
if [[ -z "$MODEL_ID" ]]; then
  MODEL_ID=$("${SCRIPT_DIR}/vertex_model_register.sh" "$MODEL_FLAVOR" "$REGION" | tail -n 1)
fi
echo "Using Model ID: $MODEL_ID"
echo ""

# Step 2: Create or retrieve Endpoint
echo "Step 2/3: Checking/creating Vertex AI Endpoint..."
ENDPOINT_ID=$(gcloud ai endpoints list \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --filter="displayName:$ENDPOINT_NAME" \
  --sort-by="~createTime" \
  --format="value(name.basename())" \
  --limit=1 2>/dev/null || true)

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

# Step 3: Deploy Model to Endpoint
echo ""
echo "Step 3/3: Deploying model $MODEL_ID to endpoint $ENDPOINT_ID..."
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
  --traffic-split=0=100 2>&1 | tee /tmp/vertex_deploy.log || true

# Extract and save operation ID
OP_ID=$(grep -oE 'Waiting for operation \[[0-9]+\]' /tmp/vertex_deploy.log | head -n 1 | grep -oE '[0-9]+' || true)
if [[ -n "$OP_ID" ]]; then
  echo "$OP_ID" > "${ROOT_DIR}/.vertex_active_operation"
fi

echo ""
echo "=========================================="
echo " Deployment Successfully Started / Complete!"
echo " Endpoint ID: $ENDPOINT_ID"
echo "=========================================="
