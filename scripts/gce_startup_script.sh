#!/usr/bin/env bash
set -euo pipefail

# Keep boot-time lifecycle behavior self-contained.  The VM can fail before
# the evaluation checkout (and scripts/lib) is downloaded.
run_with_tee_status() {
  local log_path="$1"
  shift
  local -a pipeline_status
  local restore_errexit=0
  case "$-" in *e*) restore_errexit=1; set +e ;; esac
  "$@" 2>&1 | tee "$log_path"
  pipeline_status=("${PIPESTATUS[@]}")
  if (( restore_errexit )); then set -e; fi
  LIFECYCLE_COMMAND_STATUS="${pipeline_status[0]:-1}"
  LIFECYCLE_LOG_STATUS="${pipeline_status[1]:-1}"
  return "${LIFECYCLE_COMMAND_STATUS}"
}

json_escape() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  value="${value//$'\n'/\\n}"
  value="${value//$'\r'/\\r}"
  value="${value//$'\t'/\\t}"
  printf '%s' "${value}"
}

write_evaluation_failure() {
  local report_path="$1" json_path="$2" flavor="$3" reason="$4"
  local evaluator_status="${5:-1}"
  local json_flavor json_reason json_run_id json_configuration_hash
  json_flavor="$(json_escape "${flavor}")"
  json_reason="$(json_escape "${reason}")"
  json_run_id="$(json_escape "${EXPERIMENT_RUN_ID:-}")"
  json_configuration_hash="$(json_escape "${EXPERIMENT_CONFIGURATION_HASH:-}")"
  if [[ -n "${json_run_id}" ]]; then json_run_id="\"${json_run_id}\""; else json_run_id="null"; fi
  if [[ -n "${json_configuration_hash}" ]]; then json_configuration_hash="\"${json_configuration_hash}\""; else json_configuration_hash="null"; fi
  local existing_failure=0
  if [[ -s "${json_path}" && -r "${json_path}" ]] && python3 - "${json_path}" <<'PY'
import json
import sys

try:
    with open(sys.argv[1], encoding="utf-8") as stream:
        value = json.load(stream)
    raise SystemExit(0 if isinstance(value, dict) and str(value.get("status", "")).upper() == "FAILED" else 1)
except (OSError, ValueError, TypeError):
    raise SystemExit(1)
PY
  then
    existing_failure=1
  fi
  if (( existing_failure )); then
    if [[ ! -s "${report_path}" || ! -r "${report_path}" ]]; then
      cat >"${report_path}" <<EOF
# SOC Tier 1 Evaluation Report: ${flavor}

- Status: FAILED
- Evaluator exit status: ${evaluator_status}
- Failure: ${reason}
- Scores: unavailable because the evaluation did not complete
EOF
    fi
    return 0
  fi
  if [[ -e "${json_path}" ]]; then cp -f "${json_path}" "${json_path}.pre_failure" 2>/dev/null || true; fi
  if [[ -e "${report_path}" ]]; then cp -f "${report_path}" "${report_path}.pre_failure" 2>/dev/null || true; fi
  cat >"${report_path}" <<EOF
# SOC Tier 1 Evaluation Report: ${flavor}

- Status: FAILED
- Evaluator exit status: ${evaluator_status}
- Failure: ${reason}
- Scores: unavailable because the evaluation did not complete
EOF
  cat >"${json_path}" <<EOF
{
  "run_id": ${json_run_id},
  "configuration_hash": ${json_configuration_hash},
  "flavor": "${json_flavor}",
  "status": "FAILED",
  "evaluation": {
    "status": "FAILED",
    "evaluator_exit_status": ${evaluator_status},
    "failure_reason": "${json_reason}"
  },
  "summary": null,
  "case_results": [],
  "benchmark": null
}
EOF
}

artifacts_preserved() {
  local path
  for path in "$@"; do
    [[ -s "${path}" && -r "${path}" ]] || return 1
  done
}

verify_delete_absent() {
  local restore_errexit=0
  local output status normalized_output
  case "$-" in *e*) restore_errexit=1; set +e ;; esac
  output="$("$@" 2>&1)"
  status=$?
  normalized_output="$(printf '%s' "${output}" | tr '[:upper:]' '[:lower:]')"
  if (( restore_errexit )); then set -e; fi
  [[ ${status} -ne 0 ]] || return 1
  printf '%s' "${normalized_output}" | grep -Eq 'not[[:space:]]+found|does[[:space:]]+not[[:space:]]+exist|resource[[:space:]].*missing'
}

# ==============================================================================
# GCE Ephemeral Spot GPU VM Self-Terminating Startup Script
#
# Performs NVMe formatting, containerized vLLM deployment, SOC evaluation,
# benchmark execution, GCS artifact upload, and automatic instance self-deletion.
# ==============================================================================

# Metadata server helper
METADATA_URL="http://metadata.google.internal/computeMetadata/v1/"

get_metadata() {
  local path="$1"
  local default_val="${2:-}"
  local val
  val="$(curl -s -f -H "Metadata-Flavor: Google" "${METADATA_URL}${path}" 2>/dev/null || true)"
  if [[ -n "${val}" ]]; then
    echo "${val}"
  else
    echo "${default_val}"
  fi
}

# 1. Read Instance Metadata & Runtime Parameters
INSTANCE_NAME="$(get_metadata "instance/name" "$(hostname)")"
ZONE_PATH="$(get_metadata "instance/zone" "projects/_/zones/us-central1-a")"
ZONE="$(basename "${ZONE_PATH}")"

MODEL_FLAVOR="$(get_metadata "instance/attributes/model_flavor" "gemma-2-9b-it")"
HF_REPO="$(get_metadata "instance/attributes/hf_repo" "google/gemma-2-9b-it")"
TP_SIZE="$(get_metadata "instance/attributes/tp_size" "1")"
EXTRA_FLAGS="$(get_metadata "instance/attributes/extra_flags" "")"
OUTPUT_BUCKET="$(get_metadata "instance/attributes/output_bucket" "")"
HF_TOKEN="$(get_metadata "instance/attributes/hf_token" "")"
GCS_MODEL_PATH="$(get_metadata "instance/attributes/gcs_model_path" "")"
EXPERIMENT_RUN_ID="$(get_metadata "instance/attributes/run_id" "")"
EXPERIMENT_CONFIGURATION_HASH="$(get_metadata "instance/attributes/configuration_hash" "")"
SOURCE_COMMIT="$(get_metadata "instance/attributes/source_commit" "")"
if [[ -n "${EXPERIMENT_RUN_ID}" || -n "${EXPERIMENT_CONFIGURATION_HASH}" ]]; then
  export EXPERIMENT_RUN_ID EXPERIMENT_CONFIGURATION_HASH
else
  export -n EXPERIMENT_RUN_ID EXPERIMENT_CONFIGURATION_HASH
fi

CONTAINER_NAME="vllm-server"

OUTPUT_DIR="/tmp/eval_results/${MODEL_FLAVOR}"
if [[ -n "${EXPERIMENT_RUN_ID}" ]]; then
  OUTPUT_DIR="/tmp/eval_results/${EXPERIMENT_RUN_ID}/${MODEL_FLAVOR}"
fi
REPORT_PATH="${OUTPUT_DIR}/soc_tier1_eval_report_${MODEL_FLAVOR}.md"
JSON_PATH="${OUTPUT_DIR}/soc_tier1_eval_results_${MODEL_FLAVOR}.json"
BENCHMARK_LOG="${OUTPUT_DIR}/benchmark_${MODEL_FLAVOR}.log"
LIFECYCLE_PATH="${OUTPUT_DIR}/lifecycle_status.json"
EVALUATION_STATUS="NOT_STARTED"
EVALUATOR_EXIT_STATUS="null"
EVALUATION_FAILURE_REASON=""
BENCHMARK_STATUS="NOT_STARTED"
ARTIFACT_STATUS="NOT_COLLECTED"
ARTIFACT_UPLOAD_STATUS="NOT_REQUESTED"
CLEANUP_DELETE_REQUESTED=false
CLEANUP_DELETE_VERIFIED=false

write_lifecycle_status() {
  local json_flavor json_reason json_run_id json_configuration_hash json_source_commit
  mkdir -p "${OUTPUT_DIR}"
  json_flavor="$(json_escape "${MODEL_FLAVOR}")"
  json_reason="$(json_escape "${EVALUATION_FAILURE_REASON}")"
  json_run_id="$(json_escape "${EXPERIMENT_RUN_ID}")"
  json_configuration_hash="$(json_escape "${EXPERIMENT_CONFIGURATION_HASH}")"
  json_source_commit="$(json_escape "${SOURCE_COMMIT}")"
  [[ -n "${json_run_id}" ]] || json_run_id="null"
  [[ -n "${json_configuration_hash}" ]] || json_configuration_hash="null"
  [[ -n "${json_source_commit}" ]] || json_source_commit="null"
  [[ "${json_run_id}" == "null" ]] || json_run_id="\"${json_run_id}\""
  [[ "${json_configuration_hash}" == "null" ]] || json_configuration_hash="\"${json_configuration_hash}\""
  [[ "${json_source_commit}" == "null" ]] || json_source_commit="\"${json_source_commit}\""
  cat >"${LIFECYCLE_PATH}" <<EOF
{
  "run_id": ${json_run_id},
  "configuration_hash": ${json_configuration_hash},
  "requested_source_commit": ${json_source_commit},
  "flavor": "${json_flavor}",
  "evaluation": {
    "status": "${EVALUATION_STATUS}",
    "evaluator_exit_status": ${EVALUATOR_EXIT_STATUS},
    "failure_reason": "${json_reason}",
    "benchmark_status": "${BENCHMARK_STATUS}"
  },
  "artifacts": {
    "local_status": "${ARTIFACT_STATUS}",
    "upload_status": "${ARTIFACT_UPLOAD_STATUS}"
  },
  "cleanup": {
    "delete_requested": ${CLEANUP_DELETE_REQUESTED},
    "delete_verified": ${CLEANUP_DELETE_VERIFIED}
  }
}
EOF
}

upload_artifacts() {
  if ! artifacts_preserved "${REPORT_PATH}" "${JSON_PATH}" "${BENCHMARK_LOG}"; then
    ARTIFACT_STATUS="PARTIAL"
  else
    ARTIFACT_STATUS="PRESERVED"
  fi
  write_lifecycle_status
  if [[ -z "${OUTPUT_BUCKET}" ]]; then
    ARTIFACT_UPLOAD_STATUS="NOT_REQUESTED"
    return 0
  fi
  ARTIFACT_UPLOAD_STATUS="REQUESTED"
  write_lifecycle_status
  local target_gcs_uri="${OUTPUT_BUCKET%/}/${MODEL_FLAVOR}/"
  local upload_status=0
  echo "[INFO] Uploading artifacts to ${target_gcs_uri}..."
  if command -v gcloud >/dev/null 2>&1; then
    gcloud storage cp -r "${OUTPUT_DIR}"/* "${target_gcs_uri}" || upload_status=$?
  elif command -v gsutil >/dev/null 2>&1; then
    gsutil -m cp -r "${OUTPUT_DIR}"/* "${target_gcs_uri}" || upload_status=$?
  else
    upload_status=127
  fi
  if [[ ${upload_status} -eq 0 ]]; then
    # A successful copy command records transport success.  It does not prove
    # that every object is visible in the bucket, so avoid claiming verified
    # remote persistence here.
    ARTIFACT_UPLOAD_STATUS="COMMAND_SUCCEEDED"
    write_lifecycle_status
    if command -v gcloud >/dev/null 2>&1; then
      gcloud storage cp "${LIFECYCLE_PATH}" "${target_gcs_uri}lifecycle_status.json" || upload_status=$?
    elif command -v gsutil >/dev/null 2>&1; then
      gsutil cp "${LIFECYCLE_PATH}" "${target_gcs_uri}lifecycle_status.json" || upload_status=$?
    else
      upload_status=127
    fi
    if [[ ${upload_status} -ne 0 ]]; then
      ARTIFACT_UPLOAD_STATUS="FAILED"
      write_lifecycle_status
      echo "[ERROR] Final lifecycle marker upload failed (status ${upload_status})."
      return "${upload_status}"
    fi
  else
    ARTIFACT_UPLOAD_STATUS="FAILED"
    echo "[ERROR] Artifact upload failed (status ${upload_status}); local artifacts remain at ${OUTPUT_DIR}."
  fi
  write_lifecycle_status
  if [[ ${upload_status} -ne 0 ]]; then
    return "${upload_status}"
  fi
  return 0
}

echo "=================================================================="
echo " Starting Ephemeral Spot VM Workflow for ${MODEL_FLAVOR}"
echo " Instance:      ${INSTANCE_NAME}"
echo " Zone:          ${ZONE}"
echo " HF Repo:       ${HF_REPO}"
echo " Tensor Parallel Size: ${TP_SIZE}"
echo " Output Bucket: ${OUTPUT_BUCKET}"
echo "=================================================================="

# 2. Self-Deletion Cleanup Trap
cleanup_and_self_delete() {
  local exit_code=$?
  trap - EXIT ERR INT TERM
  echo "[INFO] Initiating teardown routine (exit code: ${exit_code})..."

  # Preserve reports before tearing down the serving container. A failed
  # evaluator still leaves an explicit result and its log available.
  upload_artifacts || true

  # Stop and remove container
  if docker ps -q --filter "name=${CONTAINER_NAME}" | grep -q .; then
    echo "[INFO] Stopping vLLM container..."
    docker stop "${CONTAINER_NAME}" || true
    docker rm -f "${CONTAINER_NAME}" || true
  fi

  # Execute self-deletion
  if [[ -n "${INSTANCE_NAME}" && -n "${ZONE}" ]] && command -v gcloud >/dev/null 2>&1; then
    echo "[INFO] Deleting GCE instance ${INSTANCE_NAME} in zone ${ZONE} to prevent idle billing..."
    if gcloud compute instances delete "${INSTANCE_NAME}" --zone="${ZONE}" --quiet; then
      CLEANUP_DELETE_REQUESTED=true
      if verify_delete_absent gcloud compute instances describe "${INSTANCE_NAME}" --zone="${ZONE}"; then
        CLEANUP_DELETE_VERIFIED=true
      fi
    else
      echo "[ERROR] Instance delete request failed; cleanup is not verified."
    fi
  fi

  write_lifecycle_status
  upload_artifacts || true
  echo "[INFO] Cleanup outcome: delete_requested=${CLEANUP_DELETE_REQUESTED}, delete_verified=${CLEANUP_DELETE_VERIFIED}."
  exit "${exit_code}"
}
trap cleanup_and_self_delete EXIT ERR INT TERM

# 2.5 Ensure Docker, gcloud, and NVIDIA Container Toolkit are installed and running
if ! command -v docker >/dev/null 2>&1; then
  echo "[INFO] Installing Docker..."
  curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
  sh /tmp/get-docker.sh
fi

if ! command -v gcloud >/dev/null 2>&1; then
  echo "[INFO] Installing google-cloud-cli..."
  echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | tee -a /etc/apt/sources.list.d/google-cloud-sdk.list
  curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg | gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg
  apt-get update -y && apt-get install -y google-cloud-cli || true
fi

if ! command -v nvidia-smi >/dev/null 2>&1; then
  echo "[INFO] Installing NVIDIA binary driver packages matching running kernel $(uname -r)..."
  apt-get update -y || true
  KVER=$(uname -r)
  DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    "linux-modules-nvidia-535-server-${KVER}" \
    linux-modules-nvidia-535-server-gcp \
    nvidia-headless-535-server \
    nvidia-utils-535-server || \
  DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    nvidia-driver-535-server \
    nvidia-utils-535-server || true
  modprobe nvidia || true
fi

if ! command -v nvidia-ctk >/dev/null 2>&1; then
  echo "[INFO] Installing NVIDIA Container Toolkit..."
  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
  curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
  apt-get update -y || true
  apt-get install -y nvidia-container-toolkit || true
  nvidia-ctk runtime configure --runtime=docker || true
  systemctl restart docker || service docker restart || true
fi
systemctl start docker || service docker start || true

# 3. Mount and Format Local NVMe SSD Scratch Storage
MOUNT_DIR="/mnt/disks/nvme"
mkdir -p "${MOUNT_DIR}"

NVME_DEV=""
if [[ -e "/dev/disk/by-id/google-local-nvme-ssd-0" ]]; then
  NVME_DEV="/dev/disk/by-id/google-local-nvme-ssd-0"
elif [[ -e "/dev/nvme0n1" ]]; then
  NVME_DEV="/dev/nvme0n1"
elif compgen -G "/dev/disk/by-id/google-local-ssd-*" > /dev/null; then
  NVME_DEV="$(ls -1 /dev/disk/by-id/google-local-ssd-* | head -n 1)"
fi

if [[ -n "${NVME_DEV}" ]]; then
  echo "[INFO] Detected Local NVMe SSD device at ${NVME_DEV}."
  if ! blkid "${NVME_DEV}" | grep -q "ext4"; then
    echo "[INFO] Formatting ${NVME_DEV} with ext4 filesystem..."
    mkfs.ext4 -F -m 0 -T largefile4 -E lazy_itable_init=0,lazy_journal_init=0 "${NVME_DEV}"
  fi
  if ! mountpoint -q "${MOUNT_DIR}"; then
    echo "[INFO] Mounting ${NVME_DEV} to ${MOUNT_DIR}..."
    mount -o discard,defaults,noatime "${NVME_DEV}" "${MOUNT_DIR}"
    chmod a+rw "${MOUNT_DIR}"
  fi
  export HF_HOME="${MOUNT_DIR}/hf_cache"
else
  echo "[INFO] No Local NVMe SSD detected. Falling back to /tmp/hf_cache."
  export HF_HOME="/tmp/hf_cache"
fi

mkdir -p "${HF_HOME}"
chmod a+rw "${HF_HOME}"

# 4. Sync Model Weights from GCS (if specified)
if [[ -n "${GCS_MODEL_PATH}" && "${GCS_MODEL_PATH}" == gs://* ]]; then
  echo "[INFO] Syncing cached model weights from ${GCS_MODEL_PATH} to ${HF_HOME}..."
  if command -v gcloud >/dev/null 2>&1; then
    gcloud storage cp -r "${GCS_MODEL_PATH}/*" "${HF_HOME}/" || true
  elif command -v gsutil >/dev/null 2>&1; then
    gsutil -m cp -r "${GCS_MODEL_PATH}/*" "${HF_HOME}/" || true
  fi
fi

# 4.5 Wait for NVIDIA GPU Drivers to become ready
echo "[INFO] Waiting for NVIDIA GPU driver to initialize..."
DRIVER_READY=0
for i in $(seq 1 180); do
  if nvidia-smi >/dev/null 2>&1; then
    echo "[INFO] NVIDIA GPU driver initialized successfully:"
    nvidia-smi
    DRIVER_READY=1
    break
  fi
  echo "[INFO] NVIDIA driver not ready yet (${i}/180). Sleeping 5s..."
  sleep 5
done

if [[ ${DRIVER_READY} -eq 0 ]]; then
  echo "[ERROR] Timed out waiting for NVIDIA driver initialization."
  exit 1
fi

echo "[INFO] Configuring NVIDIA Container Toolkit and restarting Docker daemon..."
nvidia-ctk runtime configure --runtime=docker || true
systemctl restart docker || service docker restart || true
sleep 3

# 5. Launch Containerized vLLM Server
echo "[INFO] Launching vLLM container (vllm/vllm-openai:latest) on port 8080..."

DOCKER_CMD=(
  docker run -d
  --name "${CONTAINER_NAME}"
  --gpus all
  --ipc=host
  --net=host
  -v "${HF_HOME}:/root/.cache/huggingface"
)

if [[ -n "${HF_TOKEN}" ]]; then
  DOCKER_CMD+=(-e "HUGGING_FACE_HUB_TOKEN=${HF_TOKEN}" -e "HF_TOKEN=${HF_TOKEN}")
fi

DOCKER_CMD+=(
  vllm/vllm-openai:latest
  --model "${HF_REPO}"
  --tensor-parallel-size "${TP_SIZE}"
  --host 0.0.0.0
  --port 8080
  --trust-remote-code
  --gpu-memory-utilization 0.90
)

if [[ -n "${EXTRA_FLAGS}" ]]; then
  # shellcheck disable=SC2086
  DOCKER_CMD+=(${EXTRA_FLAGS})
fi

"${DOCKER_CMD[@]}"

# 6. Poll Health Endpoint
echo "[INFO] Waiting for vLLM API server to become ready on http://127.0.0.1:8080..."
MAX_WAIT_SECONDS=900
ELAPSED=0
SERVER_READY=0

while [[ ${ELAPSED} -lt ${MAX_WAIT_SECONDS} ]]; do
  if curl -s -f "http://127.0.0.1:8080/health" > /dev/null 2>&1 || curl -s -f "http://127.0.0.1:8080/v1/models" > /dev/null 2>&1; then
    echo "[INFO] vLLM server is healthy and responding on port 8080."
    SERVER_READY=1
    break
  fi
  IS_RUNNING=$(docker ps -q --filter "name=${CONTAINER_NAME}" | grep -q . && echo "true" || echo "false")
  if [[ "${IS_RUNNING}" != "true" && ${ELAPSED} -gt 15 ]]; then
    echo "[ERROR] vLLM container stopped prematurely. Container logs:"
    docker logs "${CONTAINER_NAME}" || true
    break
  fi
  sleep 5
  ELAPSED=$((ELAPSED + 5))
  if (( ELAPSED % 30 == 0 )); then
    echo "[INFO] Still waiting for vLLM server (${ELAPSED}s / ${MAX_WAIT_SECONDS}s)..."
  fi
done

if [[ ${SERVER_READY} -eq 0 ]]; then
  echo "[ERROR] vLLM server failed to start within ${MAX_WAIT_SECONDS} seconds."
  docker logs "${CONTAINER_NAME}" || true
  exit 1
fi

# 7. Execute SOC Tier 1 Evaluation and Benchmark Tests
mkdir -p "${OUTPUT_DIR}"

echo "[INFO] Syncing evaluation suite from GCS..."
mkdir -p /workspace
cd /workspace
if command -v gcloud >/dev/null 2>&1; then
  gcloud storage cp -r "gs://secops-demo-env-evals/code/*" /workspace/ || true
elif command -v gsutil >/dev/null 2>&1; then
  gsutil -m cp -r "gs://secops-demo-env-evals/code/*" /workspace/ || true
fi

if ! command -v pip3 >/dev/null 2>&1; then
  apt-get update -y && apt-get install -y python3-pip || true
fi
pip3 install httpx openai google-genai tenacity 2>/dev/null || true

echo "[INFO] Executing SOC Tier 1 Evaluation suite..."
if [[ -f "/workspace/scripts/eval_soc_agent.py" ]]; then
  cd /workspace
  if run_with_tee_status "${BENCHMARK_LOG}" python3 scripts/eval_soc_agent.py \
      --flavor "${MODEL_FLAVOR}" \
      --cloudrun-url "http://127.0.0.1:8080" \
      --output-report "${REPORT_PATH}" \
      --output-json "${JSON_PATH}"; then
    EVALUATION_STATUS="COMPLETED"
    EVALUATOR_EXIT_STATUS=0
  else
    EVALUATOR_EXIT_STATUS="${LIFECYCLE_COMMAND_STATUS}"
    EVALUATION_STATUS="FAILED"
    EVALUATION_FAILURE_REASON="Evaluator exited with status ${EVALUATOR_EXIT_STATUS}"
    echo "[ERROR] SOC Evaluation failed with status ${EVALUATOR_EXIT_STATUS}."
    write_evaluation_failure "${REPORT_PATH}" "${JSON_PATH}" "${MODEL_FLAVOR}" "${EVALUATION_FAILURE_REASON}" "${EVALUATOR_EXIT_STATUS}"
  fi
else
  EVALUATOR_EXIT_STATUS=127
  EVALUATION_STATUS="FAILED"
  EVALUATION_FAILURE_REASON="Evaluator script not found at /workspace/scripts/eval_soc_agent.py"
  echo "[ERROR] ${EVALUATION_FAILURE_REASON}."
  printf '[ERROR] %s\n' "${EVALUATION_FAILURE_REASON}" >"${BENCHMARK_LOG}"
  write_evaluation_failure "${REPORT_PATH}" "${JSON_PATH}" "${MODEL_FLAVOR}" "${EVALUATION_FAILURE_REASON}" "${EVALUATOR_EXIT_STATUS}"
fi

echo "[INFO] Running benchmark latency and throughput checks..."
BENCH_PAYLOAD="{\"model\": \"${HF_REPO}\", \"messages\": [{\"role\": \"user\", \"content\": \"Summarize standard alert triage in 2 paragraphs.\"}], \"max_tokens\": 256}"
if curl -s -f -X POST "http://127.0.0.1:8080/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d "${BENCH_PAYLOAD}" > "${OUTPUT_DIR}/benchmark_sample_output.json"; then
  BENCHMARK_STATUS="COMPLETED"
else
  BENCHMARK_STATUS="FAILED"
  echo "[ERROR] Benchmark request failed; evaluation artifact records benchmark failure."
fi

# 8. Preserve and upload artifacts before teardown.
if ! upload_artifacts; then
  UPLOAD_FAILED=true
else
  UPLOAD_FAILED=false
fi

if [[ "${EVALUATION_STATUS}" != "COMPLETED" || "${ARTIFACT_STATUS}" != "PRESERVED" || "${UPLOAD_FAILED}" == "true" ]]; then
  echo "[ERROR] Ephemeral Spot VM workload did not produce a complete evaluation artifact set."
  exit 1
fi
echo "[INFO] Ephemeral Spot VM workload completed successfully."
