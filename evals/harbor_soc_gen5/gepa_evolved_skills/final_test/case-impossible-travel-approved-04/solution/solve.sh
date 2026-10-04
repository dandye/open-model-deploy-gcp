#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI get_ip_report --json '{"ip": "198.19.43.249"}'
$SOC_CLI lookup_entity --json '{"entity_id": "VPN-DEN-74"}'
$SOC_CLI list_cases --json '{"query": "TRV-23389"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-43309", "comment": "Impossible travel explained: the Austin, US event is a token refresh from the docked office workstation LT-DEN-79 (10.19.0.128), and the Sao Paulo, BR login from 198.19.43.249 through VPN-DEN-74 matches travel registration TRV-23389 for freya.kowalski with MFA satisfied; 198.19.43.249 is a clean hospitality egress. Verdict BENIGN, no block or isolation, closing CASE-43309."}'
$SOC_CLI close_case --json '{"case_id": "CASE-43309", "verdict": "BENIGN"}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
Impossible travel explained: the Austin, US event is a token refresh from the docked office workstation LT-DEN-79 (10.19.0.128), and the Sao Paulo, BR login from 198.19.43.249 through VPN-DEN-74 matches travel registration TRV-23389 for freya.kowalski with MFA satisfied; 198.19.43.249 is a clean hospitality egress. Verdict BENIGN, no block or isolation, closing CASE-43309.
```soc_decision
{"rationale": "Reference oracle for FAM-IMPOSSIBLE-TRAVEL-APPROVED.", "recommended_actions": ["update_case_comment", "close_case"], "target_entity": "freya.kowalski", "verdict": "BENIGN"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-IMPOSSIBLE-TRAVEL-APPROVED-04",
  "rationale": "Reference oracle for FAM-IMPOSSIBLE-TRAVEL-APPROVED.",
  "recommended_actions": [
    "update_case_comment",
    "close_case"
  ],
  "target_entity": "freya.kowalski",
  "verdict": "BENIGN"
}
EOF_DECISION
