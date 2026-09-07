#!/usr/bin/env bash

# Helpers shared by the GCE startup scripts and their offline tests.  The
# startup scripts are intentionally self-contained because a VM can fail
# before the evaluation checkout is downloaded; callers may source this file
# when it is available, but must not depend on it at boot time.

# Run a command while teeing combined output to a log.  PIPESTATUS is copied
# before any other command runs so the evaluator's status is never replaced by
# tee's status.
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

# Emit a machine-readable failed evaluation result.  Missing or failed
# evaluators have no score, so no benchmark numbers are invented here.
write_evaluation_failure() {
  local report_path="$1"
  local json_path="$2"
  local flavor="$3"
  local reason="$4"
  local evaluator_status="${5:-1}"

  local json_flavor json_reason json_run_id json_configuration_hash
  json_flavor="$(json_escape "${flavor}")"
  json_reason="$(json_escape "${reason}")"
  json_run_id="$(json_escape "${EXPERIMENT_RUN_ID:-}")"
  json_configuration_hash="$(json_escape "${EXPERIMENT_CONFIGURATION_HASH:-}")"
  if [[ -n "${json_run_id}" ]]; then json_run_id="\"${json_run_id}\""; else json_run_id="null"; fi
  if [[ -n "${json_configuration_hash}" ]]; then json_configuration_hash="\"${json_configuration_hash}\""; else json_configuration_hash="null"; fi

  # The evaluator can persist a rich FAILED artifact before exiting nonzero.
  # Keep that diagnostic as the authoritative result.  If an older success,
  # malformed output, or only one half of the artifact set exists, retain the
  # original beside the replacement so it remains available for forensics.
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

# Test whether a set of local artifacts exists and is readable.  This is
# deliberately separate from upload status: preserving a local failure report
# remains useful when a bucket is unavailable.
artifacts_preserved() {
  local path
  for path in "$@"; do
    [[ -s "${path}" && -r "${path}" ]] || return 1
  done
}

# Verify deletion with a fresh describe operation.  A successful delete
# request records intent only; verification requires the resource to be
# observed absent.  The caller supplies the command so tests need no GCP.
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
