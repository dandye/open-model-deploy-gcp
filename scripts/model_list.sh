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

echo "=============================================================================="
echo " Gemma Models: Model Registry & Reference Catalog"
echo "=============================================================================="
echo "Project: $PROJECT_ID  |  Region: $REGION"
echo "=============================================================================="

echo ""
echo "=== 1. Registered Models in Vertex AI Model Registry ==="
MODELS=$(gcloud ai models list \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --format="table(name.basename():label=MODEL_ID,displayName:label=DISPLAY_NAME,createTime.date(format='%Y-%m-%d %H:%M'):label=CREATED)" 2>/dev/null || echo "")

if [[ -n "$MODELS" ]]; then
  echo "$MODELS"
else
  echo "[INFO] No models registered in project '$PROJECT_ID' ($REGION)."
fi

echo ""
echo "=== 2. Recommended Gemma Flavors & Hardware Targets ==="
cat << 'TABLE'
+--------------------+------------+-----------+-----------+--------------------+----------------------+
| MODEL FLAVOR       | PARAMETERS | PRECISION | MIN VRAM  | RECOMMENDED VM     | GPU ALLOCATION       |
+--------------------+------------+-----------+-----------+--------------------+----------------------+
| gemma-2-2b-it      | 2.6B       | bfloat16  | ~6 GB     | g2-standard-4      | 1x NVIDIA L4 (24GB)  |
| gemma-2-9b-it      | 9.2B       | bfloat16  | ~20 GB    | g2-standard-12     | 1x NVIDIA L4 (24GB)  |
| gemma-3-12b-it     | 12B        | bfloat16  | ~28 GB    | g2-standard-24     | 2x NVIDIA L4 (48GB)  |
| gemma-2-27b-it     | 27.2B      | bfloat16  | ~64 GB    | g2-standard-48     | 4x NVIDIA L4 (96GB)  |
| gemma-2-9b-it-w4a16| 9.2B       | 4-bit AWQ | ~6 GB     | g2-standard-4      | 1x NVIDIA L4 (24GB)  |
| gemma-3-12b-it-w4  | 12B        | 4-bit AWQ | ~8 GB     | g2-standard-8      | 1x NVIDIA L4 (24GB)  |
| gemma-2-27b-it-w4  | 27.2B      | 4-bit AWQ | ~18 GB    | g2-standard-16     | 1x NVIDIA L4 (24GB)  |
+--------------------+------------+-----------+-----------+--------------------+----------------------+
TABLE

echo ""
echo "=============================================================================="
