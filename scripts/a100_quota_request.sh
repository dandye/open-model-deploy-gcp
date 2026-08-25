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
REGION="${1:-${GCP_REGION:-us-central1}}"
DESIRED_GPUS="${2:-1}"

echo "=========================================="
echo " Requesting NVIDIA A100 80GB GPU Quota"
echo "=========================================="
echo "Project:      $PROJECT_ID"
echo "Region:       $REGION"
echo "Requested:    $DESIRED_GPUS x NVIDIA A100 80GB GPU"
echo "=========================================="

# 1. Ensure Cloud Quotas API is enabled
echo "Step 1/2: Ensuring Cloud Quotas API is enabled..."
gcloud services enable cloudquotas.googleapis.com --project="$PROJECT_ID"

# Resolve contact email
CONTACT_EMAIL=$(gcloud config get-value account 2>/dev/null || echo "admin@dandye.altostrat.com")

# 2. Submit Quota Preference
echo "Step 2/2: Submitting Quota Preference Request for $CONTACT_EMAIL..."
gcloud quotas preferences create \
  --service="compute.googleapis.com" \
  --project="$PROJECT_ID" \
  --quota-id="NVIDIA-A100-80GB-GPUS-per-project-region" \
  --dimensions="region=$REGION" \
  --preferred-value="$DESIRED_GPUS" \
  --email="$CONTACT_EMAIL" \
  --justification="Deploying and benchmarking Gemma 4 31B on single-GPU A100 80GB dedicated endpoint" || {
    echo ""
    echo "Note: If the CLI request requires approval or manual submission, visit:"
    echo "  https://console.cloud.google.com/iam-admin/quotas?project=$PROJECT_ID&filter=metric:compute.googleapis.com%2Fnvidia_a100_80gb_gpus"
}

echo ""
echo "Quota request submitted. Check status at: https://console.cloud.google.com/iam-admin/quotas?project=$PROJECT_ID"
