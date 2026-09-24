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

run_partner_model() {
  local flavor="$1"
  local deploy_method="$2" # "sdk" or "shell"

  local report_file="${OUTPUT_DIR}/${flavor}_discovery_report.md"
  if [[ -f "${report_file}" ]]; then
    echo "[$(date +'%T')] Report already exists for ${flavor} at ${report_file}. Skipping."
    return 0
  fi

  echo ""
  echo "================================================================================"
  echo " Starting Partner Open-Model Discovery Benchmark: ${flavor}"
  echo " Deployment Method: ${deploy_method}"
  echo "================================================================================"

  local endpoint_name=""

  if [[ "${deploy_method}" == "sdk" ]]; then
    echo "[$(date +'%T')] Deploying via vertexai.model_garden.OpenModel SDK..."
    local ep_file="/tmp/deployed_endpoint_${flavor}.txt"
    rm -f "${ep_file}"
    "${PYTHON_BIN}" "${SCRIPT_DIR}/deploy_open_model.py" \
      --flavor "${flavor}" \
      --project-id "${PROJECT_ID}" \
      --region "${REGION}" \
      --output-file "${ep_file}"
    if [[ -f "${ep_file}" ]]; then
      endpoint_name=$(cat "${ep_file}" | tr -d '[:space:]')
    fi
  else
    echo "[$(date +'%T')] Deploying via vertex_deploy.sh..."
    "${SCRIPT_DIR}/vertex_deploy.sh" "${flavor}" "${REGION}"
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

echo "================================================================================"
echo " Launching Partner Open-Weights Discovery Sweep"
echo " Suite: evals/gemma-deploy/evals.json (12 scenarios)"
echo " Project: ${PROJECT_ID}"
echo "================================================================================"

# 1. Qwen 3.8 27B via OpenModel SDK (4x L4 on g2-standard-48)
run_partner_model "qwen3.8-27b" "sdk" || echo "[WARNING] qwen3.8-27b failed, continuing."

# 2. Qwen 2.5 Coder 32B via OpenModel SDK (4x L4 on g2-standard-48)
run_partner_model "qwen2.5-coder-32b-instruct" "sdk" || echo "[WARNING] qwen2.5-coder-32b-instruct failed, continuing."

# 3. DeepSeek R1 Distill Qwen 32B via OpenModel SDK (4x L4 on g2-standard-48)
run_partner_model "deepseek-r1-distill-qwen-32b" "sdk" || echo "[WARNING] deepseek-r1-distill-qwen-32b failed, continuing."

# 4. Thinking Machines Inkling Small via verified GCS Model Garden weights (4x L4 on g2-standard-48)
run_partner_model "inkling-small" "shell" || echo "[WARNING] inkling-small failed, continuing."

# 5. NVIDIA Nemotron 3.5 Lightning 30B MoE via verified GCS Model Garden weights (4x L4 on g2-standard-48)
run_partner_model "nemotron-3.5-lightning-bf16" "shell" || echo "[WARNING] nemotron-3.5-lightning-bf16 failed, continuing."

echo ""
echo "================================================================================"
echo " All partner open-weights evaluations completed!"
"${PYTHON_BIN}" "${SCRIPT_DIR}/aggregate_sweep_results.py"
echo " Master report: ${OUTPUT_DIR}/master_open_model_sweep_report.md"
echo "================================================================================"
