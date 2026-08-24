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
MODEL_FLAVOR="${1:-gemma-2-9b-it}"
MODEL_DISPLAY_NAME="${2:-gemma-2-9b-it-model-garden}"

echo "=============================================================================="
echo " Vertex AI Model Registration (Google Model Garden Direct)"
echo "=============================================================================="
echo "Project:      $PROJECT_ID"
echo "Region:       $REGION"
echo "Model:        $MODEL_FLAVOR"
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
  echo ""
  echo "To deploy this model:"
  echo "  export VERTEX_MODEL_ID=\"$EXISTING_MODEL_ID\""
  echo "  export VERTEX_MACHINE_TYPE=\"g2-standard-12\""
  echo "  export VERTEX_ACCELERATOR_COUNT=\"1\""
  echo "  just vertex-deploy"
  exit 0
fi

# Determine GCS Model Garden path
case "$MODEL_FLAVOR" in
  gemma-2-2b-it|google/gemma-2-2b-it)
    GCS_PATH="gs://vertex-model-garden-restricted-us/gemma2/gemma-2-2b-it"
    TP_SIZE=1
    ;;
  gemma-2-9b-it|google/gemma-2-9b-it)
    GCS_PATH="gs://vertex-model-garden-restricted-us/gemma2/gemma-2-9b-it"
    TP_SIZE=1
    ;;
  gemma-3-12b-it|google/gemma-3-12b-it)
    GCS_PATH="gs://vertex-model-garden-restricted-us/gemma3/gemma-3-12b-it"
    TP_SIZE=4
    ;;
  *)
    GCS_PATH="gs://vertex-model-garden-restricted-us/gemma2/gemma-2-9b-it"
    TP_SIZE=1
    ;;
esac

echo "Uploading Model Garden container specification..."

REGISTER_OUTPUT=$(gcloud ai models upload \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --display-name="$MODEL_DISPLAY_NAME" \
  --container-image-uri="us-docker.pkg.dev/vertex-ai/vertex-vision-model-garden-dockers/pytorch-vllm-serve:20250312_0916_RC01" \
  --container-command="python,-m,vllm.entrypoints.api_server" \
  --container-args="--host=0.0.0.0,--port=8080,--model=${GCS_PATH},--tensor-parallel-size=${TP_SIZE},--swap-space=16,--gpu-memory-utilization=0.90,--max-model-len=8192,--disable-log-stats" \
  --container-env-vars="MODEL_ID=google/${MODEL_FLAVOR},DEPLOY_SOURCE=UI_NATIVE_MODEL" \
  --container-ports="8080" \
  --container-predict-route="/generate" \
  --container-health-route="/ping" \
  --format="value(name.basename())")

echo "[OK] Registered model successfully!"
echo "Model ID: $REGISTER_OUTPUT"
echo ""
echo "To deploy this model:"
echo "  export VERTEX_MODEL_ID=\"$REGISTER_OUTPUT\""
echo "  just vertex-deploy"
