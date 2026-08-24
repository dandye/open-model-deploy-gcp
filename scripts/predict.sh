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
VERTEX_ENDPOINT_NAME="${VERTEX_ENDPOINT_NAME:-gemma-endpoint-$(date +%Y%m%d)}"
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

# 2. Check if Vertex AI endpoint is active
ENDPOINT_ID=$(gcloud ai endpoints list \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --filter="display_name=$VERTEX_ENDPOINT_NAME" \
  --format="value(name.basename())" \
  --limit=1 2>/dev/null || true)

if [[ -n "$ENDPOINT_ID" ]]; then
  echo "[TARGET] Querying Vertex AI Endpoint $ENDPOINT_ID..."
  echo ""
  AUTH_TOKEN=$(gcloud auth print-access-token 2>/dev/null || true)

  # Model Garden vLLM containers serve rawPredict on port 7080/8080
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
