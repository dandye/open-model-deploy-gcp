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
SERVICE_NAME="${CLOUDRUN_SERVICE_NAME:-gemma-cloudrun-service}"
MODEL_NAME="${CLOUDRUN_MODEL_NAME:-google/gemma-2-9b-it}"
CONTAINER_IMAGE="${CLOUDRUN_CONTAINER_IMAGE:-vllm/vllm-openai:latest}"

CPU="${CLOUDRUN_CPU:-8}"
MEMORY="${CLOUDRUN_MEMORY:-32Gi}"
GPU_COUNT="${CLOUDRUN_GPU_COUNT:-1}"
GPU_TYPE="${CLOUDRUN_GPU_TYPE:-nvidia-l4}"
MIN_INSTANCES="${CLOUDRUN_MIN_INSTANCES:-0}"
MAX_INSTANCES="${CLOUDRUN_MAX_INSTANCES:-1}"
TIMEOUT="${CLOUDRUN_TIMEOUT:-900}"
SWAP_SPACE="${CLOUDRUN_SWAP_SPACE:-4}"
GPU_MEMORY_UTIL="${CLOUDRUN_GPU_MEMORY_UTILIZATION:-0.90}"
MAX_MODEL_LEN="${CLOUDRUN_MAX_MODEL_LEN:-4096}"

echo "=========================================="
echo " Cloud Run Gemma Deployment (Scale-to-Zero)"
echo "=========================================="
echo "Project:        $PROJECT_ID"
echo "Region:         $REGION"
echo "Service:        $SERVICE_NAME"
echo "Model:          $MODEL_NAME"
echo "Hardware:       $CPU vCPUs, $MEMORY RAM, $GPU_COUNT x $GPU_TYPE"
echo "Scale-to-Zero:  min-instances=$MIN_INSTANCES, max-instances=$MAX_INSTANCES"
echo "=========================================="

# 1. Enable required GCP services
echo "Step 1/3: Ensuring Cloud Run & Artifact Registry APIs are enabled..."
gcloud services enable \
  run.googleapis.com \
  compute.googleapis.com \
  --project="$PROJECT_ID"

# 2. Deploy service to Cloud Run with GPU and scale-to-zero
echo ""
echo "Step 2/3: Deploying $SERVICE_NAME to Cloud Run with ${GPU_COUNT}x ${GPU_TYPE}..."

gcloud beta run deploy "$SERVICE_NAME" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --image="$CONTAINER_IMAGE" \
  --cpu="$CPU" \
  --memory="$MEMORY" \
  --gpu="$GPU_COUNT" \
  --gpu-type="$GPU_TYPE" \
  --no-cpu-throttling \
  --execution-environment="gen2" \
  --min-instances="$MIN_INSTANCES" \
  --max-instances="$MAX_INSTANCES" \
  --timeout="${TIMEOUT}s" \
  --port=8000 \
  --args="--model=${MODEL_NAME},--swap-space=${SWAP_SPACE},--gpu-memory-utilization=${GPU_MEMORY_UTIL},--max-model-len=${MAX_MODEL_LEN},--port=8000" \
  --set-env-vars="HF_TOKEN=${HF_TOKEN:-},VLLM_LOGGING_LEVEL=INFO" \
  --allow-unauthenticated

# 3. Retrieve service URL
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --format="value(status.url)")

echo ""
echo "=========================================="
echo " Deployment Complete!"
echo " Service URL: $SERVICE_URL"
echo " Scale-to-Zero: Active (0 instances running when idle)"
echo "=========================================="
echo ""
echo "Test endpoint with curl:"
echo "curl $SERVICE_URL/v1/chat/completions \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"model\": \"$MODEL_NAME\", \"messages\": [{\"role\": \"user\", \"content\": \"Hello Gemma!\"}]}'"
