#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI lookup_entity --entity_id "DESKTOP-HR-04"
$SOC_CLI get_ip_report --ip "10.0.8.99"
$SOC_CLI isolate_host --hostname "DESKTOP-HR-04"
$SOC_CLI update_case_comment --case_id "CASE-33279" --comment "Confirmed PsExec lateral movement by mwilson on DESKTOP-HR-04 (10.0.8.99). Isolated host."

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
# SOC Tier 1 Triage Report: CASE-GEN3-07-LATERAL-MOVEMENT-PSEXEC

- **Compromised Host:** DESKTOP-HR-04 (10.0.8.99)
- **Account:** mwilson
- **Verdict:** MALICIOUS PsExec SMB lateral movement (MITRE T1021.002).
- **Containment Executed:** Isolated DESKTOP-HR-04 (10.0.8.99) via `isolate_host` and documented via `update_case_comment`.
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN3-07-LATERAL-MOVEMENT-PSEXEC",
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
