#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI get_case --case_id "CASE-33279"
$SOC_CLI get_ip_report --ip "198.51.100.42"
$SOC_CLI update_case_comment --case_id "CASE-33279" --comment "Correlated IP 198.51.100.42 with existing open SOAR case CASE-33279 on DESKTOP-ENG-22."

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
# SOC Tier 1 Triage Report: CASE-GEN3-04-DUPLICATE-SOAR-CASE

- **Existing SOAR Ticket:** CASE-33279
- **Correlated Indicator:** 198.51.100.42
- **Verdict:** SUSPICIOUS duplicate correlation.
- **Actions Executed:** Appended correlation notes to open ticket 33279 via `update_case_comment` without creating a duplicate case.
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN3-04-DUPLICATE-SOAR-CASE",
  "verdict": "SUSPICIOUS",
  "executed_actions": [
    "update_case_comment"
  ],
  "recommended_actions": [
    "update_case_comment"
  ]
}
EOF_DECISION
