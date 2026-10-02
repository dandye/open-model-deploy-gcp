#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI lookup_entity --entity_id "DESKTOP-FIN-08"
$SOC_CLI get_ip_report --ip "10.0.5.23"
$SOC_CLI isolate_host --hostname "DESKTOP-FIN-08"
$SOC_CLI update_case_comment --case_id "CASE-33279" --comment "Critical ransomware outbreak on DESKTOP-FIN-08 (10.0.5.23). Isolated host immediately; do not reboot."

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
# SOC Tier 1 Triage Report: CASE-GEN3-05-RANSOMWARE-ESCALATION

- **Compromised Asset:** DESKTOP-FIN-08 (10.0.5.23)
- **Verdict:** MALICIOUS active ransomware infection.
- **Containment Executed:** Immediately isolated DESKTOP-FIN-08 (10.0.5.23) via `isolate_host`, instructed against rebooting, and escalated via `update_case_comment`.
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN3-05-RANSOMWARE-ESCALATION",
  "verdict": "MALICIOUS",
  "executed_actions": [
    "isolate_host",
    "update_case_comment"
  ],
  "recommended_actions": [
    "isolate_host",
    "update_case_comment"
  ]
}
EOF_DECISION
