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
PROMPT="${1:-Hello Gemma! Explain quantum computing in two sentences.}"
ENDPOINT_PATTERN="${VERTEX_ENDPOINT_NAME:-gemma-endpoint*}"
CLOUDRUN_SERVICE_NAME="${CLOUDRUN_SERVICE_NAME:-gemma-cloudrun-service}"

echo "=========================================="
echo " Gemma Prediction Test"
echo "=========================================="
echo "Prompt: \"$PROMPT\""
echo "=========================================="

# 1. Check if Cloud Run service is active
SERVICE_URL=$(gcloud run services describe "$CLOUDRUN_SERVICE_NAME" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --format="value(status.url)" 2>/dev/null || true)

if [[ -n "$SERVICE_URL" ]]; then
  echo "[TARGET] Querying Cloud Run service at $SERVICE_URL..."
  echo ""
  RESPONSE=$(curl -s -X POST "$SERVICE_URL/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d "{
      \"model\": \"${CLOUDRUN_MODEL_NAME:-google/gemma-2-9b-it}\",
      \"messages\": [{\"role\": \"user\", \"content\": \"$PROMPT\"}],
      \"temperature\": 0.7,
      \"max_tokens\": 256
    }" 2>/dev/null || true)

  if [[ -n "$RESPONSE" ]]; then
    echo "--- Response ---"
    echo "$RESPONSE" | grep -o '"content":"[^"]*' | sed 's/"content":"//g' || echo "$RESPONSE"
    echo ""
    exit 0
  fi
fi

# 2. Check for active Vertex AI endpoint with deployed model
ENDPOINT_ID=$(gcloud ai endpoints list \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --filter="displayName:$ENDPOINT_PATTERN" \
  --sort-by="~createTime" \
  --format="value(name.basename())" \
  --limit=1 2>/dev/null || true)

if [[ -n "$ENDPOINT_ID" ]]; then
  ENDPOINT_INFO=$(gcloud ai endpoints describe "$ENDPOINT_ID" \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --format="yaml(displayName,deployedModels)" 2>/dev/null || true)

  DISPLAY_NAME=$(echo "$ENDPOINT_INFO" | grep "displayName:" | awk '{print $2}' || echo "$ENDPOINT_ID")

  if ! echo "$ENDPOINT_INFO" | grep -q "deployedModels:"; then
    echo "[INFO] Found Endpoint '$DISPLAY_NAME' ($ENDPOINT_ID), but the model is still deploying (no traffic split yet)."
    echo "Check deployment progress with: just vertex-status"
    exit 0
  fi

  echo "[TARGET] Querying Vertex AI Endpoint '$DISPLAY_NAME' ($ENDPOINT_ID)..."
  echo ""
  AUTH_TOKEN=$(gcloud auth print-access-token 2>/dev/null || true)

  PREDICT_URL="https://${REGION}-aiplatform.googleapis.com/v1/projects/${PROJECT_ID}/locations/${REGION}/endpoints/${ENDPOINT_ID}:rawPredict"

  RESPONSE=$(curl -s -X POST "$PREDICT_URL" \
    -H "Authorization: Bearer $AUTH_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{
      \"model\": \"${VERTEX_MODEL_ID:-gemma-3-12b-it-1747240724884}\",
      \"messages\": [{\"role\": \"user\", \"content\": \"$PROMPT\"}],
      \"temperature\": 0.7,
      \"max_tokens\": 256
    }" 2>/dev/null || true)

  if [[ -n "$RESPONSE" ]]; then
    echo "--- Response ---"
    echo "$RESPONSE" | grep -o '"content":"[^"]*' | sed 's/"content":"//g' || echo "$RESPONSE"
    echo ""
    exit 0
  fi
fi

echo "[ERROR] No active Vertex AI Endpoint or Cloud Run service found to query."
echo "Deploy a model first using 'just vertex-deploy' or 'just cloudrun-deploy'."
exit 1
