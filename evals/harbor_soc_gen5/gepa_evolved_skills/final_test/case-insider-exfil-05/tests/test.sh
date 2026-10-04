#!/usr/bin/env bash
set -euo pipefail

TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
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
  --metrics-file "$ARTIFACTS_DIR/metrics.json" \
  --evalset-file "$TESTS_DIR/case.json" \
  --manifest-file "$TESTS_DIR/manifest.json" \
  --split "${SOC_SPLIT:?SOC_SPLIT must be set by task.toml [verifier.env]}" \
  --reward-dir "$VERIFIER_DIR"
