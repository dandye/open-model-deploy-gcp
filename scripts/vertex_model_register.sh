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
if [[ -n "${EXTRA_VLLM_FLAGS:-}" ]]; then
  FLAGS_SLUG=$(echo "$EXTRA_VLLM_FLAGS" | tr -cs 'a-zA-Z0-9' '-' | sed 's/^-//;s/-$//' | cut -c1-24)
  DEFAULT_DISPLAY_NAME="${MODEL_FLAVOR}-${FLAGS_SLUG}-model-garden"
else
  DEFAULT_DISPLAY_NAME="${MODEL_FLAVOR}-model-garden"
fi
MODEL_DISPLAY_NAME="${3:-${VERTEX_MODEL_DISPLAY_NAME:-$DEFAULT_DISPLAY_NAME}}"

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
HF_REPO=$(catalog_get_hf_repo "$MODEL_FLAVOR")
TP_SIZE=$(catalog_get_tp_size "$MODEL_FLAVOR")
SWAP_SPACE=$(catalog_get_swap_space "$MODEL_FLAVOR")
SHARED_MEM_MB=$(catalog_get_shared_memory_mb "$MODEL_FLAVOR")
GPU_MEM_UTIL=$(catalog_get_gpu_mem_util "$MODEL_FLAVOR")
MAX_LEN=$(catalog_get_max_len "$MODEL_FLAVOR")
EXTRA_ARGS_JSON=$(catalog_get "$MODEL_FLAVOR" ".runtime.extraArgs")

MODEL_FAMILY=$(catalog_get_family "$MODEL_FLAVOR")

ARGS_ARRAY=(
  "python"
  "-m"
  "vllm.entrypoints.api_server"
  "--host=0.0.0.0"
  "--port=8080"
  "--model=${SOURCE_URI}"
  "--tensor-parallel-size=${TP_SIZE}"
  "--gpu-memory-utilization=${GPU_MEM_UTIL}"
)

if [[ -n "$MAX_LEN" && "$MAX_LEN" != "null" && "$MAX_LEN" -gt 0 ]]; then
  ARGS_ARRAY+=("--max-model-len=${MAX_LEN}")
fi

if [[ -n "$SWAP_SPACE" && "$SWAP_SPACE" != "null" && "$SWAP_SPACE" -gt 0 ]]; then
  ARGS_ARRAY+=("--swap-space=${SWAP_SPACE}")
fi

if [[ "$MODEL_FAMILY" != "gemma4" ]]; then
  ARGS_ARRAY+=("--disable-log-stats")
fi

# Append extra arguments if present
if [[ "$EXTRA_ARGS_JSON" != "[]" && -n "$EXTRA_ARGS_JSON" && "$EXTRA_ARGS_JSON" != "null" ]]; then
  while IFS= read -r arg; do
    if [[ -n "$arg" ]]; then
      ARGS_ARRAY+=("$arg")
    fi
  done < <(echo "$EXTRA_ARGS_JSON" | jq -r '.[]')
fi

# Append dynamic runtime flags (EXTRA_VLLM_FLAGS) if provided
if [[ -n "${EXTRA_VLLM_FLAGS:-}" ]]; then
  while IFS= read -r flag; do
    if [[ -n "$flag" ]]; then
      ARGS_ARRAY+=("$flag")
    fi
  done < <(python3 -c '
import sys, shlex
flags = sys.argv[1] if len(sys.argv) > 1 else ""
for item in shlex.split(flags):
    print(item)
' "$EXTRA_VLLM_FLAGS")
fi

DELIMITER="|"
CONTAINER_ARGS=$(printf "^${DELIMITER}^%s" "$(IFS="$DELIMITER"; echo "${ARGS_ARRAY[*]}")")


CONTAINER_IMAGE=$(catalog_get_container_image "$MODEL_FLAVOR")

MODEL_DESC="${4:-${VERTEX_MODEL_DESCRIPTION:-}}"
if [[ -z "$MODEL_DESC" ]]; then
  MODEL_NAME=$(catalog_get_display_name "$MODEL_FLAVOR")
  MACHINE_TYPE=$(catalog_get_machine_type "$MODEL_FLAVOR")
  ACC_TYPE=$(catalog_get_accelerator_type "$MODEL_FLAVOR")
  ACC_COUNT=$(catalog_get_accelerator_count "$MODEL_FLAVOR")
  
  if [[ -n "${EXTRA_VLLM_FLAGS:-}" ]]; then
    MODEL_DESC="${MODEL_NAME} with extra runtime flags (${EXTRA_VLLM_FLAGS}) on ${ACC_COUNT}x ${ACC_TYPE} (${MACHINE_TYPE})."
  else
    MODEL_DESC="${MODEL_NAME} on ${ACC_COUNT}x ${ACC_TYPE} (${MACHINE_TYPE})."
  fi
fi

if [[ -n "$HF_REPO" && "$HF_REPO" != "null" ]]; then
  CONTAINER_MODEL_ID="$HF_REPO"
else
  CONTAINER_MODEL_ID="google/${MODEL_FLAVOR}"
fi

ENV_VARS="MODEL_ID=${CONTAINER_MODEL_ID},DEPLOY_SOURCE=UI_NATIVE_MODEL,VLLM_RPC_TIMEOUT=300,VLLM_TORCH_COMPILE_TIMEOUT=300"
UPLOAD_EXTRA_FLAGS=()
if [[ -n "$SHARED_MEM_MB" && "$SHARED_MEM_MB" != "null" && "$SHARED_MEM_MB" -gt 0 ]]; then
  ENV_VARS="${ENV_VARS},LOCAL_MODEL_DIR=/dev/shm/model_dir"
  UPLOAD_EXTRA_FLAGS+=("--container-shared-memory-size-mb=${SHARED_MEM_MB}")
fi

gcloud ai models upload \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --display-name="$MODEL_DISPLAY_NAME" \
  --description="$MODEL_DESC" \
  --container-image-uri="$CONTAINER_IMAGE" \
  --container-args="$CONTAINER_ARGS" \
  --container-env-vars="$ENV_VARS" \
  --container-ports="8080" \
  --container-predict-route="/generate" \
  --container-health-route="/ping" \
  "${UPLOAD_EXTRA_FLAGS[@]}" >/dev/null 2>&1 || true

gcloud ai models list \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --filter="displayName=$MODEL_DISPLAY_NAME" \
  --sort-by="~createTime" \
  --format="value(name.basename())" \
  --limit=1
