#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI lookup_entity --entity_id "SRV-PROD-PAYMENT-01"
$SOC_CLI get_ip_report --ip "10.0.99.50"
$SOC_CLI update_case_comment --case_id "CASE-17305" --comment "Verified internal scan on SRV-PROD-PAYMENT-01 (10.0.99.50) is authorized Qualys Scanner maintenance."
$SOC_CLI close_case --case_id "CASE-17305" --verdict "BENIGN"

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
# SOC Tier 1 Triage Report: CASE-GEN3-10-AUTHORIZED-SCANNER-NOISE

- **Host:** SRV-PROD-PAYMENT-01 (10.0.99.50)
- **Finding:** Authorized internal Qualys Scanner vulnerability maintenance.
- **Verdict:** BENIGN. Updated case comments via `update_case_comment` and resolved alert via `close_case` without isolating the payment server.
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN3-10-AUTHORIZED-SCANNER-NOISE",
  "verdict": "BENIGN",
  "executed_actions": [
    "update_case_comment",
    "close_case"
  ],
  "recommended_actions": [
    "update_case_comment",
    "close_case"
  ]
}
EOF_DECISION
