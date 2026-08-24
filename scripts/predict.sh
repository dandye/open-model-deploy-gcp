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

# 1. Check for Active Cloud Run Service
CLOUDRUN_URL=""
if [[ -n "$TARGET_MODEL" ]]; then
  CLOUDRUN_SERVICE_MATCH="${TARGET_MODEL}-cloudrun"
  CLOUDRUN_URL=$(gcloud run services describe "$CLOUDRUN_SERVICE_MATCH" \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --format="value(status.url)" 2>/dev/null || true)
else
  CLOUDRUN_URL=$(gcloud run services list \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --filter="status.url:*" \
    --format="value(status.url)" \
    --limit=1 2>/dev/null || true)
fi

if [[ -n "$CLOUDRUN_URL" ]]; then
  echo "[TARGET] Querying Cloud Run Service ($CLOUDRUN_URL)..."
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

# 2. Check for Active Vertex AI Endpoint
FILTER_PATTERN="displayName:gemma*"
if [[ -n "$TARGET_MODEL" ]]; then
  FILTER_PATTERN="displayName:${TARGET_MODEL}*"
fi

ENDPOINT_INFO=$(gcloud ai endpoints list \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --filter="$FILTER_PATTERN" \
  --sort-by="~createTime" \
  --format="value(name.basename(), displayName)" \
  --limit=1 2>/dev/null || true)

if [[ -n "$ENDPOINT_INFO" ]]; then
  ENDPOINT_ID=$(echo "$ENDPOINT_INFO" | awk '{print $1}')
  DISPLAY_NAME=$(echo "$ENDPOINT_INFO" | awk '{print $2}')

  # Check if model is actually deployed
  DEPLOYED_MODELS=$(gcloud ai endpoints describe "$ENDPOINT_ID" \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --format="value(deployedModels)" 2>/dev/null || true)

  if [[ -z "$DEPLOYED_MODELS" ]]; then
    echo "[INFO] Found Endpoint '$DISPLAY_NAME' ($ENDPOINT_ID), but the model is still deploying (no traffic split yet)."
    echo "Check deployment progress with: just vertex-status"
    exit 0
  fi

  echo "[TARGET] Querying Vertex AI Endpoint '$DISPLAY_NAME' ($ENDPOINT_ID)..."
  AUTH_TOKEN=$(gcloud auth print-access-token)

  PAYLOAD=$(jq -n \
    --arg prompt "$PROMPT" \
    '{
      instances: [
        {
          prompt: $prompt,
          max_tokens: 256,
          temperature: 0.7
        }
      ]
    }')

  RESPONSE=$(curl -s -X POST \
    -H "Authorization: Bearer $AUTH_TOKEN" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD" \
    "https://${REGION}-aiplatform.googleapis.com/v1/projects/${PROJECT_ID}/locations/${REGION}/endpoints/${ENDPOINT_ID}:predict" || true)

  echo ""
  echo "--- Response ---"
  echo "$RESPONSE" | jq . 2>/dev/null || echo "$RESPONSE"
  echo ""
  echo "=========================================="
  exit 0
fi

echo "[ERROR] No active Vertex AI Endpoint or Cloud Run service found to query."
echo "Deploy a model first using: just vertex-deploy <model> or just cloudrun-deploy <model>"
exit 1
