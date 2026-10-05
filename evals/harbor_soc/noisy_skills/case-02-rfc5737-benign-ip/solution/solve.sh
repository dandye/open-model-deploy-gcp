#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI get_ip_report --ip "192.0.2.100"
$SOC_CLI close_case --case_id "CASE-33279" --verdict "BENIGN"

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
# SOC Tier 1 Triage Report: CASE-GEN3-02-RFC5737-BENIGN-IP

- **Source IP:** 192.0.2.100
- **Target Gateway:** GW-CORE-VPN-01
- **Routing Classification:** Reserved RFC-5737 TEST-NET-1 non-routable documentation subnet.
- **Verdict:** BENIGN. Closed case via `close_case` without host isolation or indicator blocking.
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN3-02-RFC5737-BENIGN-IP",
  "verdict": "BENIGN",
  "executed_actions": [
    "close_case"
  ],
  "recommended_actions": [
    "close_case"
  ]
}
EOF_DECISION
