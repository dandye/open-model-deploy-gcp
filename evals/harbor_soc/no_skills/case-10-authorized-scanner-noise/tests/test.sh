#!/usr/bin/env bash
set -euo pipefail

VERIFY_BIN="${SOC_VERIFY_BIN:-python3 /app/scripts/verify_harbor_soc.py}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
VERIFIER_DIR="${SOC_VERIFIER_DIR:-/logs/verifier}"
mkdir -p "$VERIFIER_DIR"

$VERIFY_BIN \
  --case-id "${SOC_CASE_ID}" \
  --state-file "${SOC_STATE_FILE:-/var/lib/soc/state.json}" \
  --trajectory-file "${SOC_TRAJECTORY_FILE:-$ARTIFACTS_DIR/trajectory.jsonl}" \
  --report-file "$ARTIFACTS_DIR/triage_report.md" \
  --decision-file "$ARTIFACTS_DIR/soc_decision.json" \
  --reward-dir "$VERIFIER_DIR"
