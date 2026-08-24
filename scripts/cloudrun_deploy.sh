#!/usr/bin/env bash
set -euo pipefail

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-dandye-0324-chronicle}"
REGION="us-central1"
SERVICE_NAME="gemma-cloudrun-service"
MODEL_NAME="${MODEL_NAME:-google/gemma-2-9b-it}"
CONTAINER_IMAGE="vllm/vllm-openai:latest"

# Cloud Run GPU & Hardware Allocation
# (Cloud Run supports 1x NVIDIA L4 per instance)
CPU="8"
MEMORY="32Gi"
GPU_COUNT="1"
GPU_TYPE="nvidia-l4"
MIN_INSTANCES="0"    # 0 = True Scale-To-Zero when idle
MAX_INSTANCES="1"
TIMEOUT="900"        # 15 min timeout to allow cold start weight loading

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
echo "Step 2/3: Deploying $SERVICE_NAME to Cloud Run with 1x NVIDIA L4..."

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
  --args="--model=${MODEL_NAME},--swap-space=4,--gpu-memory-utilization=0.90,--max-model-len=4096,--port=8000" \
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
