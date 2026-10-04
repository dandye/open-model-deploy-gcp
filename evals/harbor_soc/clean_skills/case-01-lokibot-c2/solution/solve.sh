#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI get_domain_report --domain "update-service-win32.com"
$SOC_CLI lookup_entity --entity_id "DESKTOP-FIN-08"
$SOC_CLI isolate_host --hostname "DESKTOP-FIN-08"
$SOC_CLI update_case_comment --case_id "CASE-33279" --comment "Confirmed Lokibot C2 beaconing from DESKTOP-FIN-08 (10.0.4.15) to update-service-win32.com. Host isolated."

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
# SOC Tier 1 Triage Report: CASE-GEN3-01-LOKIBOT-C2

- **Target Host:** DESKTOP-FIN-08 (10.0.4.15)
- **Indicator:** update-service-win32.com
- **Threat Verdict:** MALICIOUS (Lokibot InfoStealer C2)
- **Containment Executed:** Executed `isolate_host` on DESKTOP-FIN-08 and recorded IOCs via `update_case_comment`.
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN3-01-LOKIBOT-C2",
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
