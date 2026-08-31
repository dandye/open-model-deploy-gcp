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
REGION="${GCP_REGION:-us-central1}"
MODEL_FLAVOR="${1:-${GEMMA_MODEL_FLAVOR:-gemma-2-9b-it}}"
SERVICE_NAME="${CLOUDRUN_SERVICE_NAME:-${MODEL_FLAVOR}-cloudrun}"
GPU_TYPE="${CLOUDRUN_GPU_TYPE:-nvidia-l4}"
GPU_COUNT="${CLOUDRUN_GPU_COUNT:-1}"
CPU="${CLOUDRUN_CPU:-4}"
MEMORY="${CLOUDRUN_MEMORY:-16Gi}"
MIN_INSTANCES="${CLOUDRUN_MIN_INSTANCES:-0}"
MAX_INSTANCES="${CLOUDRUN_MAX_INSTANCES:-1}"

# Validate model exists in catalog
if ! catalog_model_exists "$MODEL_FLAVOR"; then
  echo "[ERROR] Model flavor '$MODEL_FLAVOR' not found in configs/models.json."
  echo "Available flavors:"
  catalog_list_models | sed 's/^/  - /'
  exit 1
fi

# Guard check: target support
if ! catalog_supports_target "$MODEL_FLAVOR" "cloudrun"; then
  echo "[ERROR] Model '$MODEL_FLAVOR' requires multiple GPUs and is not supported on Cloud Run (1x GPU limit)."
  echo "Supported Cloud Run flavors:"
  for k in $(catalog_list_models); do
    if catalog_supports_target "$k" "cloudrun"; then
      echo "  - $k"
    fi
  done
  exit 1
fi

HF_REPO=$(catalog_get_hf_repo "$MODEL_FLAVOR")
HF_TOKEN="${HF_TOKEN:-}"

echo "=========================================="
echo " Cloud Run Gemma Deployment (Scale-to-Zero)"
echo "=========================================="
echo "Project:       $PROJECT_ID"
echo "Region:        $REGION"
echo "Model Flavor:  $MODEL_FLAVOR ($HF_REPO)"
echo "Service:       $SERVICE_NAME"
echo "GPU:           $GPU_COUNT x $GPU_TYPE"
echo "Min Instances: $MIN_INSTANCES (Scale-to-zero when idle)"
echo "=========================================="

ENV_VARS="MODEL_ID=${HF_REPO}"
if [[ -n "$HF_TOKEN" ]]; then
  ENV_VARS="${ENV_VARS},HF_TOKEN=${HF_TOKEN}"
fi

echo "Deploying Cloud Run service..."

gcloud run deploy "$SERVICE_NAME" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --image="vllm/vllm-openai:latest" \
  --args="--model=${HF_REPO},--port=8080,--enforce-eager,--tensor-parallel-size=1,--gpu-memory-utilization=0.90,--max-model-len=4096" \
  --set-env-vars="$ENV_VARS" \
  --gpu="$GPU_COUNT" \
  --gpu-type="$GPU_TYPE" \
  --no-gpu-zonal-redundancy \
  --cpu="$CPU" \
  --memory="$MEMORY" \
  --min-instances="$MIN_INSTANCES" \
  --max-instances="$MAX_INSTANCES" \
  --no-cpu-throttling \
  --timeout=900 \
  --startup-probe="timeoutSeconds=10,periodSeconds=10,failureThreshold=60,tcpSocket.port=8080" \
  --allow-unauthenticated

echo ""
echo "=========================================="
echo " Cloud Run Deployment Complete!"
echo "=========================================="
