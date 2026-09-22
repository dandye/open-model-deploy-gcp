#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Source environment
if [[ -f "${ROOT_DIR}/.env" ]]; then
  set -a
  source "${ROOT_DIR}/.env"
  set +a
fi

PROJECT_ID="${GCP_PROJECT_ID:-secops-demo-env}"
REGION="${GCP_REGION:-us-central1}"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python3"
EVALSET="${ROOT_DIR}/evals/gemma-deploy/evals.json"
SKILLS_DIR="${ROOT_DIR}/skills"
OUTPUT_DIR="${ROOT_DIR}/docs/eval_results/discovery"

CURRENT_ENDPOINT=""

cleanup() {
  if [[ -n "${CURRENT_ENDPOINT}" ]]; then
    echo "[$(date +'%T')] Cleaning up active endpoint: ${CURRENT_ENDPOINT}..."
    local deployed_models
    deployed_models=$(gcloud ai endpoints describe "${CURRENT_ENDPOINT}" --region="${REGION}" --project="${PROJECT_ID}" --format="value(deployedModels[].id)" 2>/dev/null || true)
    for dm in $deployed_models; do
      echo "  Undeploying model $dm..."
      gcloud ai endpoints undeploy-model "${CURRENT_ENDPOINT}" --deployed-model-id="$dm" --region="${REGION}" --project="${PROJECT_ID}" --quiet 2>/dev/null || true
    done
    echo "  Deleting endpoint ${CURRENT_ENDPOINT}..."
    gcloud ai endpoints delete "${CURRENT_ENDPOINT}" --region="${REGION}" --project="${PROJECT_ID}" --quiet 2>/dev/null || true
    CURRENT_ENDPOINT=""
  fi
}
trap cleanup EXIT INT TERM

wait_for_endpoint() {
  local endpoint_id="$1"
  local timeout_seconds="${2:-1800}"
  local start_time=$(date +%s)
  echo "[$(date +'%T')] Waiting for endpoint ${endpoint_id} to become healthy..."
  while true; do
    local deployed_id
    deployed_id=$(gcloud ai endpoints describe "${endpoint_id}" --region="${REGION}" --project="${PROJECT_ID}" --format="value(deployedModels[0].id)" 2>/dev/null || true)
    if [[ -n "${deployed_id}" ]]; then
      echo "[$(date +'%T')] Model deployed with ID: ${deployed_id}"
      break
    fi
    local current_time=$(date +%s)
    if (( current_time - start_time > timeout_seconds )); then
      echo "[ERROR] Timeout waiting for endpoint ${endpoint_id} deployment"
      return 1
    fi
    sleep 20
  done

  # Test probe with rawPredict
  local token
  token=$(gcloud auth print-access-token)
  for attempt in {1..12}; do
    local resp
    resp=$(curl -s -X POST \
      "https://${REGION}-aiplatform.googleapis.com/v1/projects/${PROJECT_ID}/locations/${REGION}/endpoints/${endpoint_id}:rawPredict" \
      -H "Authorization: Bearer ${token}" \
      -H "Content-Type: application/json" \
      -d '{
        "prompt": "<start_of_turn>user\nRespond with HELLO<end_of_turn>\n<start_of_turn>model\n",
        "max_tokens": 10,
        "temperature": 0.0
      }' 2>/dev/null || true)
    if [[ "$resp" == *"Output:"* ]] || [[ "$resp" == *"predictions"* ]]; then
      echo "[$(date +'%T')] Inference health check passed on endpoint ${endpoint_id}!"
      return 0
    fi
    echo "[$(date +'%T')] Inference probe attempt $attempt failed, retrying in 15s..."
    sleep 15
  done
  return 1
}

run_model_suite() {
  local flavor="$1"
  echo ""
  echo "================================================================================"
  echo " Starting Two-Stage Discovery Benchmark: ${flavor}"
  echo "================================================================================"

  # Deploy model
  echo "[$(date +'%T')] Deploying ${flavor}..."
  "${SCRIPT_DIR}/vertex_deploy.sh" "${flavor}" "${REGION}"

  # Get endpoint ID
  local endpoint_name
  endpoint_name=$(gcloud ai endpoints list \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --filter="displayName:${flavor}-endpoint" \
    --sort-by="~createTime" \
    --format="value(name.basename())" \
    --limit=1 2>/dev/null || true)

  if [[ -z "${endpoint_name}" ]]; then
    endpoint_name=$(gcloud ai endpoints list \
      --project="${PROJECT_ID}" \
      --region="${REGION}" \
      --sort-by="~createTime" \
      --format="value(name.basename())" \
      --limit=1 2>/dev/null || true)
  fi

  if [[ -z "${endpoint_name}" ]]; then
    echo "[ERROR] Could not resolve endpoint for ${flavor}"
    return 1
  fi

  CURRENT_ENDPOINT="${endpoint_name}"
  echo "[$(date +'%T')] Tracking Endpoint ID: ${CURRENT_ENDPOINT}"

  # Wait for deployment and health check
  wait_for_endpoint "${CURRENT_ENDPOINT}"

  # Execute evaluation
  echo "[$(date +'%T')] Running discovery benchmark against ${flavor}..."
  "${PYTHON_BIN}" "${SCRIPT_DIR}/eval_skill_discovery.py" \
    --evalset "${EVALSET}" \
    --skills-dir "${SKILLS_DIR}" \
    --model "vertex_endpoint/${CURRENT_ENDPOINT}" \
    --model-name "${flavor}" \
    --judge-model "vertex_ai/gemini-2.5-flash" \
    --project-id "${PROJECT_ID}" \
    --output-dir "${OUTPUT_DIR}"

  echo "[$(date +'%T')] Benchmark completed for ${flavor}."

  # Teardown endpoint
  cleanup
}

# Main execution loop
echo "================================================================================"
echo " Launching Gemma 3 Multi-Model Discovery Evaluation Suite"
echo " Targets: gemma-3-1b-it, gemma-3-12b-it"
echo " Suite: evals/gemma-deploy/evals.json (12 scenarios)"
echo "================================================================================"

# Run 1B
run_model_suite "gemma-3-1b-it"

# Run 12B
run_model_suite "gemma-3-12b-it"

echo ""
echo "================================================================================"
echo " All Gemma 3 discovery evaluations completed successfully!"
echo " Results written to: ${OUTPUT_DIR}"
echo "================================================================================"
