#!/usr/bin/env bash
# ==============================================================================
# Model Catalog Helper Functions
# ==============================================================================

SCRIPT_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_LIB_DIR}/../.." && pwd)"
CATALOG_FILE="${ROOT_DIR}/configs/models.json"

if [[ ! -f "$CATALOG_FILE" ]]; then
  echo "[ERROR] Model catalog not found at: $CATALOG_FILE" >&2
  exit 1
fi

# List all available model keys
catalog_list_models() {
  jq -r 'keys[]' "$CATALOG_FILE"
}

# Check if model exists in catalog
catalog_model_exists() {
  local model_key="$1"
  jq -e "has(\"$model_key\")" "$CATALOG_FILE" >/dev/null 2>&1
}

# Query arbitrary field from catalog for a given model
catalog_get() {
  local model_key="$1"
  local json_path="$2"
  jq -r ".[\"$model_key\"]${json_path}" "$CATALOG_FILE"
}

# Get compute attributes
catalog_get_machine_type() {
  catalog_get "$1" ".compute.machineType"
}

catalog_get_accelerator_type() {
  catalog_get "$1" ".compute.acceleratorType"
}

catalog_get_accelerator_count() {
  catalog_get "$1" ".compute.acceleratorCount"
}

catalog_get_source_uri() {
  catalog_get "$1" ".sourceUri"
}

catalog_get_hf_repo() {
  catalog_get "$1" ".hfRepo"
}

catalog_get_tp_size() {
  catalog_get "$1" ".runtime.tensorParallelSize"
}

catalog_get_swap_space() {
  catalog_get "$1" ".runtime.swapSpaceGb"
}

catalog_get_max_len() {
  catalog_get "$1" ".runtime.maxModelLen"
}

catalog_get_gpu_mem_util() {
  catalog_get "$1" ".runtime.gpuMemoryUtilization"
}

catalog_supports_target() {
  local model_key="$1"
  local target="$2"
  jq -e ".[\"$model_key\"].supportedTargets | index(\"$target\") != null" "$CATALOG_FILE" >/dev/null 2>&1
}
