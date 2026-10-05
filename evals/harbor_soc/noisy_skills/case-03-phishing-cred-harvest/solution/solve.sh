#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI get_domain_report --domain "evil.com"
$SOC_CLI lookup_entity --entity_id "john.doe" --entity_type "user"
$SOC_CLI block_indicator --indicator "evil.com"
$SOC_CLI update_case_comment --case_id "CASE-33279" --comment "Blocked credential harvesting domain evil.com targeted at john.doe."

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
# SOC Tier 1 Triage Report: CASE-GEN3-03-PHISHING-CRED-HARVEST

- **Targeted User:** john.doe on DESKTOP-MKT-14
- **Malicious Domain:** evil.com
- **Verdict:** MALICIOUS phishing credential harvesting campaign.
- **Actions Executed:** Blocked `evil.com` via `block_indicator` and updated case documentation via `update_case_comment`.
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN3-03-PHISHING-CRED-HARVEST",
  "verdict": "MALICIOUS",
  "executed_actions": [
    "block_indicator",
    "update_case_comment"
  ],
  "recommended_actions": [
    "block_indicator",
    "update_case_comment"
  ]
}
EOF_DECISION
