#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Source environment variables if present
if [[ -f "${ROOT_DIR}/.env" ]]; then
  set -a
  source "${ROOT_DIR}/.env"
  set +a
fi
source "${SCRIPT_DIR}/lib/model_catalog.sh"

PROJECT_ID="${GCP_PROJECT_ID:-dandye-0324-chronicle}"
REGION="${GCP_REGION:-us-central1}"
PROMPT="${1:-Hello Gemma! Explain quantum computing in two sentences.}"
TARGET_MODEL="${2:-}"

echo "=========================================="
echo " Gemma Prediction Test"
echo "=========================================="
echo "Prompt: \"$PROMPT\""
if [[ -n "$TARGET_MODEL" ]]; then
  echo "Target Model: $TARGET_MODEL"
fi
echo "=========================================="

# 1. Check for Active Cloud Run Gemma Service
CLOUDRUN_FILTER="status.url:* AND metadata.name:*gemma*"
if [[ -n "$TARGET_MODEL" ]]; then
  CLOUDRUN_FILTER="status.url:* AND metadata.name:*${TARGET_MODEL}*"
fi

CLOUDRUN_URL=$(gcloud run services list \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --filter="$CLOUDRUN_FILTER" \
  --format="value(status.url)" \
  --limit=1 2>/dev/null || true)

if [[ -n "$CLOUDRUN_URL" ]]; then
  echo "[TARGET] Querying Cloud Run Gemma Service ($CLOUDRUN_URL)..."
  AUTH_TOKEN=$(gcloud auth print-identity-token 2>/dev/null || gcloud auth print-access-token)

  PAYLOAD=$(jq -n \
    --arg model "default" \
    --arg prompt "$PROMPT" \
    '{
      model: $model,
      messages: [
        {role: "user", content: $prompt}
      ],
      max_tokens: 256,
      temperature: 0.7
    }')

  RESPONSE=$(curl -s -X POST \
    -H "Authorization: Bearer $AUTH_TOKEN" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD" \
    "${CLOUDRUN_URL}/v1/chat/completions" || true)

  echo ""
  echo "--- Response ---"
  echo "$RESPONSE" | jq . 2>/dev/null || echo "$RESPONSE"
  echo ""
  echo "=========================================="
  exit 0
fi

# 2. Check for Active Vertex AI Endpoint across regions
VERTEX_REGIONS=("$REGION" "us-east4" "us-west1" "europe-west4")
ENDPOINT_INFO=""
FOUND_REGION=""

for r in "${VERTEX_REGIONS[@]}"; do
  FILTER_PATTERN="displayName:gemma*"
  if [[ -n "$TARGET_MODEL" ]]; then
    FILTER_PATTERN="displayName:${TARGET_MODEL}*"
  fi

  EP_RES=$(gcloud ai endpoints list \
    --project="$PROJECT_ID" \
    --region="$r" \
    --filter="$FILTER_PATTERN" \
    --sort-by="~createTime" \
    --format="value(name.basename(), displayName)" \
    --limit=1 2>/dev/null || true)

  if [[ -n "$EP_RES" ]]; then
    ENDPOINT_INFO="$EP_RES"
    FOUND_REGION="$r"
    break
  fi
done

if [[ -n "$ENDPOINT_INFO" ]]; then
  ENDPOINT_ID=$(echo "$ENDPOINT_INFO" | awk '{print $1}')
  DISPLAY_NAME=$(echo "$ENDPOINT_INFO" | awk '{print $2}')

  # Check if model is actually deployed
  DEPLOYED_MODELS=$(gcloud ai endpoints describe "$ENDPOINT_ID" \
    --project="$PROJECT_ID" \
    --region="$FOUND_REGION" \
    --format="value(deployedModels)" 2>/dev/null || true)

  if [[ -z "$DEPLOYED_MODELS" ]]; then
    echo "[INFO] Found Endpoint '$DISPLAY_NAME' ($ENDPOINT_ID in $FOUND_REGION), but the model is still deploying (no traffic split yet)."
    echo "Check deployment progress with: just vertex-status"
    exit 0
  fi

  echo "[TARGET] Querying Vertex AI Endpoint '$DISPLAY_NAME' ($ENDPOINT_ID in $FOUND_REGION)..."

  TMP_REQ=$(mktemp /tmp/gemma_req.XXXXXX.json)
  jq -n --arg prompt "$PROMPT" \
    '{"instances": [{"prompt": $prompt, "max_tokens": 256, "temperature": 0.7}]}' > "$TMP_REQ"

  echo ""
  echo "--- Response ---"
  gcloud ai endpoints predict "$ENDPOINT_ID" \
    --project="$PROJECT_ID" \
    --region="$FOUND_REGION" \
    --json-request="$TMP_REQ"
  rm -f "$TMP_REQ"

  echo ""
  echo "=========================================="
  exit 0
fi

echo "[ERROR] No active Vertex AI Endpoint or Cloud Run service found to query."
echo "Deploy a model first using: just vertex-deploy <model> or just cloudrun-deploy <model>"
exit 1
