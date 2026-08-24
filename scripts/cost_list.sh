#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
source "${SCRIPT_DIR}/lib/model_catalog.sh"

echo "========================================================================================================="
echo " Gemma Infrastructure Pricing & Cost Projections (us-central1)"
echo "========================================================================================================="
printf "%-18s | %-23s | %-10s | %-12s | %-12s | %-12s\n" \
  "FLAVOR" "MACHINE (GPU)" "HOURLY" "8H TEST" "160H BIZ MO" "730H FULL MO"
echo "---------------------------------------------------------------------------------------------------------"

for key in $(catalog_list_models); do
  MACHINE=$(catalog_get_machine_type "$key")
  ACCEL_COUNT=$(catalog_get_accelerator_count "$key")
  HOURLY=$(catalog_get "$key" ".compute.hourlyCostUsd")

  COST_8H=$(awk "BEGIN {printf \"%.2f\", $HOURLY * 8}")
  COST_BIZ=$(awk "BEGIN {printf \"%.2f\", $HOURLY * 160}")
  COST_FULL=$(awk "BEGIN {printf \"%.2f\", $HOURLY * 730}")

  printf "%-18s | %-23s | $%-9.2f | $%-11s | $%-11s | $%-11s\n" \
    "$key" "${MACHINE} (${ACCEL_COUNT}xL4)" "$HOURLY" "$COST_8H" "$COST_BIZ" "$COST_FULL"
done
echo "========================================================================================================="
printf "* Cloud Run with GPU (Scale-to-Zero): \$0.00 / hr when idle (billed only per active inference second).\n\n"
