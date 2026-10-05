#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI get_ip_report --json '{"ip": "198.19.231.80"}'
$SOC_CLI lookup_entity --json '{"entity_id": "GW-DEN-83"}'
$SOC_CLI list_cases --json '{"query": "TRV-55566"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-76948", "comment": "Impossible travel explained: the Singapore, SG event is a token refresh from the docked office workstation PC-DEN-75 (10.19.0.231), and the Denver, US login from 198.19.231.80 through GW-DEN-83 matches travel registration TRV-55566 for yara.rahimi with MFA satisfied; 198.19.231.80 is a clean hospitality egress. Verdict BENIGN, no block or isolation, closing CASE-76948."}'
$SOC_CLI close_case --json '{"case_id": "CASE-76948", "verdict": "BENIGN"}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
Impossible travel explained: the Singapore, SG event is a token refresh from the docked office workstation PC-DEN-75 (10.19.0.231), and the Denver, US login from 198.19.231.80 through GW-DEN-83 matches travel registration TRV-55566 for yara.rahimi with MFA satisfied; 198.19.231.80 is a clean hospitality egress. Verdict BENIGN, no block or isolation, closing CASE-76948.
```soc_decision
{"rationale": "Reference oracle for FAM-IMPOSSIBLE-TRAVEL-APPROVED.", "recommended_actions": ["update_case_comment", "close_case"], "target_entity": "yara.rahimi", "verdict": "BENIGN"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-IMPOSSIBLE-TRAVEL-APPROVED-02",
  "rationale": "Reference oracle for FAM-IMPOSSIBLE-TRAVEL-APPROVED.",
  "recommended_actions": [
    "update_case_comment",
    "close_case"
  ],
  "target_entity": "yara.rahimi",
  "verdict": "BENIGN"
}
EOF_DECISION
