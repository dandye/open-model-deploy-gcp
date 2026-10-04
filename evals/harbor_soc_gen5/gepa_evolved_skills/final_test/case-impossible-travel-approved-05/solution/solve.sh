#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI get_ip_report --json '{"ip": "198.19.192.199"}'
$SOC_CLI lookup_entity --json '{"entity_id": "GW-FRA-96"}'
$SOC_CLI list_cases --json '{"query": "TRV-52274"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-39729", "comment": "Impossible travel explained: the Sao Paulo, BR event is a token refresh from the docked office workstation WKS-FRA-78 (10.11.0.97), and the Toronto, CA login from 198.19.192.199 through GW-FRA-96 matches travel registration TRV-52274 for theo.solberg with MFA satisfied; 198.19.192.199 is a clean hospitality egress. Verdict BENIGN, no block or isolation, closing CASE-39729."}'
$SOC_CLI close_case --json '{"case_id": "CASE-39729", "verdict": "BENIGN"}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
Impossible travel explained: the Sao Paulo, BR event is a token refresh from the docked office workstation WKS-FRA-78 (10.11.0.97), and the Toronto, CA login from 198.19.192.199 through GW-FRA-96 matches travel registration TRV-52274 for theo.solberg with MFA satisfied; 198.19.192.199 is a clean hospitality egress. Verdict BENIGN, no block or isolation, closing CASE-39729.
```soc_decision
{"rationale": "Reference oracle for FAM-IMPOSSIBLE-TRAVEL-APPROVED.", "recommended_actions": ["update_case_comment", "close_case"], "target_entity": "theo.solberg", "verdict": "BENIGN"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-IMPOSSIBLE-TRAVEL-APPROVED-05",
  "rationale": "Reference oracle for FAM-IMPOSSIBLE-TRAVEL-APPROVED.",
  "recommended_actions": [
    "update_case_comment",
    "close_case"
  ],
  "target_entity": "theo.solberg",
  "verdict": "BENIGN"
}
EOF_DECISION
