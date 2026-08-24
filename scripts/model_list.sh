#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ -f "${ROOT_DIR}/.env" ]]; then
  set -a
  source "${ROOT_DIR}/.env"
  set +a
fi
source "${SCRIPT_DIR}/lib/model_catalog.sh"

PROJECT_ID="${GCP_PROJECT_ID:-dandye-0324-chronicle}"
REGION="${GCP_REGION:-us-central1}"

echo "========================================================================================================="
echo " Gemma Model Catalog & Sizing Matrix (configs/models.json)"
echo "========================================================================================================="
printf "%-18s | %-6s | %-16s | %-16s | %-6s | %-10s | %s\n" \
  "FLAVOR" "PARAMS" "MACHINE TYPE" "ACCELERATOR" "TP_SZ" "HOURLY" "TARGETS"
echo "---------------------------------------------------------------------------------------------------------"

for key in $(catalog_list_models); do
  PARAMS=$(catalog_get "$key" ".params")
  MACHINE=$(catalog_get_machine_type "$key")
  ACCEL_COUNT=$(catalog_get_accelerator_count "$key")
  ACCEL_TYPE=$(catalog_get_accelerator_type "$key")
  TP_SIZE=$(catalog_get_tp_size "$key")
  HOURLY=$(catalog_get "$key" ".compute.hourlyCostUsd")
  TARGETS=$(catalog_get "$key" ".supportedTargets | join(\", \")")

  printf "%-18s | %-6s | %-16s | %dx %-13s | %-6s | $%-9.2f | %s\n" \
    "$key" "$PARAMS" "$MACHINE" "$ACCEL_COUNT" "$ACCEL_TYPE" "$TP_SIZE" "$HOURLY" "$TARGETS"
done
echo "========================================================================================================="
echo ""
echo "--- Vertex AI Model Registry Registered Models ($REGION) ---"
gcloud ai models list --project="$PROJECT_ID" --region="$REGION" 2>/dev/null || echo "[INFO] No models registered yet."
echo ""
