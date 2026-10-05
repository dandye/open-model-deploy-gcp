#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI get_ip_report --json '{"ip": "198.19.214.177"}'
$SOC_CLI lookup_entity --json '{"entity_id": "GW-SIN-86"}'
$SOC_CLI list_cases --json '{"query": "TRV-56791"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-66847", "comment": "Impossible travel explained: the Sydney, AU event is a token refresh from the docked office workstation PC-SIN-78 (10.12.0.187), and the Austin, US login from 198.19.214.177 through GW-SIN-86 matches travel registration TRV-56791 for yara.volkov with MFA satisfied; 198.19.214.177 is a clean hospitality egress. Verdict BENIGN, no block or isolation, closing CASE-66847."}'
$SOC_CLI close_case --json '{"case_id": "CASE-66847", "verdict": "BENIGN"}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
Impossible travel explained: the Sydney, AU event is a token refresh from the docked office workstation PC-SIN-78 (10.12.0.187), and the Austin, US login from 198.19.214.177 through GW-SIN-86 matches travel registration TRV-56791 for yara.volkov with MFA satisfied; 198.19.214.177 is a clean hospitality egress. Verdict BENIGN, no block or isolation, closing CASE-66847.
```soc_decision
{"rationale": "Reference oracle for FAM-IMPOSSIBLE-TRAVEL-APPROVED.", "recommended_actions": ["update_case_comment", "close_case"], "target_entity": "yara.volkov", "verdict": "BENIGN"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-IMPOSSIBLE-TRAVEL-APPROVED-01",
  "rationale": "Reference oracle for FAM-IMPOSSIBLE-TRAVEL-APPROVED.",
  "recommended_actions": [
    "update_case_comment",
    "close_case"
  ],
  "target_entity": "yara.volkov",
  "verdict": "BENIGN"
}
EOF_DECISION
