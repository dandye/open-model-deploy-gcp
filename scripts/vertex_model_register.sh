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
MODEL_DISPLAY_NAME="${3:-${MODEL_FLAVOR}-model-garden}"

# Validate model exists in catalog
if ! catalog_model_exists "$MODEL_FLAVOR"; then
  echo "[ERROR] Model flavor '$MODEL_FLAVOR' not found in configs/models.json."
  echo "Available flavors:"
  catalog_list_models | sed 's/^/  - /'
  exit 1
fi

# Check if model already registered with this display name in the target region
EXISTING_MODEL_ID=$(gcloud ai models list \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --filter="displayName=$MODEL_DISPLAY_NAME" \
  --sort-by="~createTime" \
  --format="value(name.basename())" \
  --limit=1 2>/dev/null || true)

if [[ -n "$EXISTING_MODEL_ID" ]]; then
  echo "$EXISTING_MODEL_ID"
  exit 0
fi

# Load parameters from catalog
SOURCE_URI=$(catalog_get_source_uri "$MODEL_FLAVOR")
TP_SIZE=$(catalog_get_tp_size "$MODEL_FLAVOR")
SWAP_SPACE=$(catalog_get_swap_space "$MODEL_FLAVOR")
GPU_MEM_UTIL=$(catalog_get_gpu_mem_util "$MODEL_FLAVOR")
MAX_LEN=$(catalog_get_max_len "$MODEL_FLAVOR")
EXTRA_ARGS_JSON=$(catalog_get "$MODEL_FLAVOR" ".runtime.extraArgs")

CONTAINER_ARGS="python,-m,vllm.entrypoints.api_server,--host=0.0.0.0,--port=8080,--model=${SOURCE_URI},--tensor-parallel-size=${TP_SIZE},--swap-space=${SWAP_SPACE},--gpu-memory-utilization=${GPU_MEM_UTIL},--max-model-len=${MAX_LEN},--disable-log-stats"

# Append extra arguments if present
if [[ "$EXTRA_ARGS_JSON" != "[]" && -n "$EXTRA_ARGS_JSON" ]]; then
  EXTRA_ARGS_CSV=$(echo "$EXTRA_ARGS_JSON" | jq -r 'join(",")')
  CONTAINER_ARGS="${CONTAINER_ARGS},${EXTRA_ARGS_CSV}"
fi

REGISTER_OUTPUT=$(gcloud ai models upload \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --display-name="$MODEL_DISPLAY_NAME" \
  --container-image-uri="us-docker.pkg.dev/vertex-ai/vertex-vision-model-garden-dockers/pytorch-vllm-serve:20250312_0916_RC01" \
  --container-args="$CONTAINER_ARGS" \
  --container-env-vars="MODEL_ID=google/${MODEL_FLAVOR},DEPLOY_SOURCE=UI_NATIVE_MODEL" \
  --container-ports="8080" \
  --container-predict-route="/generate" \
  --container-health-route="/ping" \
  --format="value(name.basename())")

echo "$REGISTER_OUTPUT"
