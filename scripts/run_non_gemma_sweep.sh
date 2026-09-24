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

  # Test probe with rawPredict or standard predict
  local token
  token=$(gcloud auth print-access-token)
  for attempt in {1..15}; do
    # Try rawPredict first
    local resp
    resp=$(curl -s -X POST \
      "https://${REGION}-aiplatform.googleapis.com/v1/projects/${PROJECT_ID}/locations/${REGION}/endpoints/${endpoint_id}:rawPredict" \
      -H "Authorization: Bearer ${token}" \
      -H "Content-Type: application/json" \
      -d '{
        "prompt": "Respond with HELLO",
        "max_tokens": 10,
        "temperature": 0.0
      }' 2>/dev/null || true)
    if [[ "$resp" == *"Output:"* ]] || [[ "$resp" == *"predictions"* ]] || [[ "$resp" == *"HELLO"* ]]; then
      echo "[$(date +'%T')] Inference health check passed on endpoint ${endpoint_id} via rawPredict!"
      return 0
    fi

    # Try standard predict fallback
    resp=$(curl -s -X POST \
      "https://${REGION}-aiplatform.googleapis.com/v1/projects/${PROJECT_ID}/locations/${REGION}/endpoints/${endpoint_id}:predict" \
      -H "Authorization: Bearer ${token}" \
      -H "Content-Type: application/json" \
      -d '{
        "instances": [{"prompt": "Respond with HELLO"}],
        "parameters": {"maxOutputTokens": 10}
      }' 2>/dev/null || true)
    if [[ "$resp" == *"predictions"* ]]; then
      echo "[$(date +'%T')] Inference health check passed on endpoint ${endpoint_id} via standard predict!"
      return 0
    fi

    echo "[$(date +'%T')] Inference probe attempt $attempt failed, retrying in 15s..."
    sleep 15
  done
  return 1
}

run_model_suite() {
  local flavor="$1"
  local report_file="${OUTPUT_DIR}/${flavor}_discovery_report.md"

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

  # Regenerate master sweep report
  "${PYTHON_BIN}" "${SCRIPT_DIR}/aggregate_sweep_results.py"

  # Commit progress
  git add "${OUTPUT_DIR}/${flavor}_discovery_report.md" "${OUTPUT_DIR}/${flavor}_discovery_results.json" "${OUTPUT_DIR}/master_open_model_sweep_report.md" 2>/dev/null || true
  git commit -m "feat(eval): record ${flavor} two-stage skill discovery results" 2>/dev/null || true
  git push gh skill_discovery_eval_v0001 2>/dev/null || true
}

MODELS=(
  "llama-3.2-3b-instruct"
  "llama-guard-3-8b"
  "inkling-small"
  "nemotron-3.5-lightning-bf16"
  "llama-3.1-nemotron-70b-instruct"
)

echo "================================================================================"
echo " Launching Non-Gemma Open-Weights Discovery Sweep"
echo " Target Models (${#MODELS[@]}): ${MODELS[*]}"
echo " Suite: evals/gemma-deploy/evals.json (12 scenarios)"
echo " Output Directory: ${OUTPUT_DIR}"
echo "================================================================================"

for model in "${MODELS[@]}"; do
  echo ""
  echo ">>> [$(date +'%T')] Processing model: ${model} <<<"
  run_model_suite "${model}" || echo "[WARNING] Model ${model} encountered an error, proceeding to next model."
done

echo ""
echo "================================================================================"
echo " All non-Gemma open-weights evaluations completed!"
"${PYTHON_BIN}" "${SCRIPT_DIR}/aggregate_sweep_results.py"
echo " Master report: ${OUTPUT_DIR}/master_open_model_sweep_report.md"
echo "================================================================================"
