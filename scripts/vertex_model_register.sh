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
HF_MODEL_NAME="${1:-google/gemma-2-9b-it}"
MODEL_DISPLAY_NAME="${2:-gemma-2-9b-it-single-l4}"
HF_TOKEN="${HF_TOKEN:-}"

echo "=============================================================================="
echo " Vertex AI Model Registration (Single-GPU 1x NVIDIA L4 Target)"
echo "=============================================================================="
echo "Project:      $PROJECT_ID"
echo "Region:       $REGION"
echo "Model:        $HF_MODEL_NAME"
echo "Display Name: $MODEL_DISPLAY_NAME"
echo "=============================================================================="

# Check if model already registered with this display name
EXISTING_MODEL_ID=$(gcloud ai models list \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --filter="displayName=$MODEL_DISPLAY_NAME" \
  --format="value(name.basename())" \
  --limit=1 2>/dev/null || true)

if [[ -n "$EXISTING_MODEL_ID" ]]; then
  echo "[INFO] Found existing registered model ID: $EXISTING_MODEL_ID"
  echo "You can deploy it directly using:"
  echo "  export VERTEX_MODEL_ID=\"$EXISTING_MODEL_ID\""
  echo "  export VERTEX_MACHINE_TYPE=\"g2-standard-12\""
  echo "  export VERTEX_ACCELERATOR_COUNT=\"1\""
  echo "  just vertex-deploy"
  exit 0
fi

echo "Registering model in Vertex AI Model Registry..."

ENV_VARS="MODEL_ID=${HF_MODEL_NAME}"
if [[ -n "$HF_TOKEN" ]]; then
  ENV_VARS="${ENV_VARS},HF_TOKEN=${HF_TOKEN}"
fi

CONTAINER_ARGS="--model=${HF_MODEL_NAME},--tensor-parallel-size=1,--swap-space=8,--gpu-memory-utilization=0.90,--max-model-len=4096,--port=8080"

REGISTER_OUTPUT=$(gcloud ai models upload \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --display-name="$MODEL_DISPLAY_NAME" \
  --container-image-uri="us-docker.pkg.dev/vertex-ai/vertex-vision-model-garden-dockers/pytorch-vllm-serve:20250312_0916_RC01" \
  --container-command="python,-m,vllm.entrypoints.api_server" \
  --container-args="$CONTAINER_ARGS" \
  --container-env-vars="$ENV_VARS" \
  --container-ports="8080" \
  --container-predict-route="/generate" \
  --container-health-route="/ping" \
  --format="value(name.basename())")

echo "[OK] Registered model successfully!"
echo "Model ID: $REGISTER_OUTPUT"
echo ""
echo "To deploy this model:"
echo "  export VERTEX_MODEL_ID=\"$REGISTER_OUTPUT\""
echo "  export VERTEX_MACHINE_TYPE=\"g2-standard-12\""
echo "  export VERTEX_ACCELERATOR_COUNT=\"1\""
echo "  just vertex-deploy"
