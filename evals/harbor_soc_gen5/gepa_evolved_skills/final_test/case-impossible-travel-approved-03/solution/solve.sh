#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI get_ip_report --json '{"ip": "198.18.125.172"}'
$SOC_CLI lookup_entity --json '{"entity_id": "VPN-FRA-54"}'
$SOC_CLI list_cases --json '{"query": "TRV-34038"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-93329", "comment": "Impossible travel explained: the Dublin, IE event is a token refresh from the docked office workstation LT-FRA-70 (10.11.0.17), and the Denver, US login from 198.18.125.172 through VPN-FRA-54 matches travel registration TRV-34038 for kwame.hartmann with MFA satisfied; 198.18.125.172 is a clean hospitality egress. Verdict BENIGN, no block or isolation, closing CASE-93329."}'
$SOC_CLI close_case --json '{"case_id": "CASE-93329", "verdict": "BENIGN"}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
Impossible travel explained: the Dublin, IE event is a token refresh from the docked office workstation LT-FRA-70 (10.11.0.17), and the Denver, US login from 198.18.125.172 through VPN-FRA-54 matches travel registration TRV-34038 for kwame.hartmann with MFA satisfied; 198.18.125.172 is a clean hospitality egress. Verdict BENIGN, no block or isolation, closing CASE-93329.
```soc_decision
{"rationale": "Reference oracle for FAM-IMPOSSIBLE-TRAVEL-APPROVED.", "recommended_actions": ["update_case_comment", "close_case"], "target_entity": "kwame.hartmann", "verdict": "BENIGN"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-IMPOSSIBLE-TRAVEL-APPROVED-03",
  "rationale": "Reference oracle for FAM-IMPOSSIBLE-TRAVEL-APPROVED.",
  "recommended_actions": [
    "update_case_comment",
    "close_case"
  ],
  "target_entity": "kwame.hartmann",
  "verdict": "BENIGN"
}
EOF_DECISION
