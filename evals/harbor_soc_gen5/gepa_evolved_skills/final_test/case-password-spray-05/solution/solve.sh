#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI get_ip_report --json '{"ip": "198.18.196.194"}'
$SOC_CLI lookup_entity --json '{"entity_id": "VPN-SYD-12"}'
$SOC_CLI udm_search --json '{"query": "198.18.196.194"}'
$SOC_CLI block_indicator --json '{"indicator": "198.18.196.194"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-51008", "comment": "Password spray confirmed: 198.18.196.194 made 1035 failed logins across 55 accounts (including oscar.nilsen and noor.alvarez) against VPN-SYD-12 (10.17.0.10), validated by DC-SYD-97; the source carries a malicious brute-force reputation and no login succeeded. 198.18.196.194 blocked at the perimeter, VPN-SYD-12 and DC-SYD-97 left online, escalated to Tier 2 for account monitoring, case left open."}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
Password spray confirmed: 198.18.196.194 made 1035 failed logins across 55 accounts (including oscar.nilsen and noor.alvarez) against VPN-SYD-12 (10.17.0.10), validated by DC-SYD-97; the source carries a malicious brute-force reputation and no login succeeded. 198.18.196.194 blocked at the perimeter, VPN-SYD-12 and DC-SYD-97 left online, escalated to Tier 2 for account monitoring, case left open.
```soc_decision
{"rationale": "Reference oracle for FAM-PASSWORD-SPRAY.", "recommended_actions": ["block_indicator", "update_case_comment"], "target_entity": "198.18.196.194", "verdict": "MALICIOUS"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-PASSWORD-SPRAY-05",
  "rationale": "Reference oracle for FAM-PASSWORD-SPRAY.",
  "recommended_actions": [
    "block_indicator",
    "update_case_comment"
  ],
  "target_entity": "198.18.196.194",
  "verdict": "MALICIOUS"
}
EOF_DECISION
