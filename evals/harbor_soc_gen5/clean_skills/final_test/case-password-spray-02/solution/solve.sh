#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI get_ip_report --json '{"ip": "198.18.188.96"}'
$SOC_CLI lookup_entity --json '{"entity_id": "GW-DEN-67"}'
$SOC_CLI udm_search --json '{"query": "198.18.188.96"}'
$SOC_CLI block_indicator --json '{"indicator": "198.18.188.96"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-53427", "comment": "Password spray confirmed: 198.18.188.96 made 2277 failed logins across 225 accounts (including freya.hartmann and zara.hartmann) against GW-DEN-67 (10.19.0.14), validated by DC-DEN-90; the source carries a malicious brute-force reputation and no login succeeded. 198.18.188.96 blocked at the perimeter, GW-DEN-67 and DC-DEN-90 left online, escalated to Tier 2 for account monitoring, case left open."}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
Password spray confirmed: 198.18.188.96 made 2277 failed logins across 225 accounts (including freya.hartmann and zara.hartmann) against GW-DEN-67 (10.19.0.14), validated by DC-DEN-90; the source carries a malicious brute-force reputation and no login succeeded. 198.18.188.96 blocked at the perimeter, GW-DEN-67 and DC-DEN-90 left online, escalated to Tier 2 for account monitoring, case left open.
```soc_decision
{"rationale": "Reference oracle for FAM-PASSWORD-SPRAY.", "recommended_actions": ["block_indicator", "update_case_comment"], "target_entity": "198.18.188.96", "verdict": "MALICIOUS"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-PASSWORD-SPRAY-02",
  "rationale": "Reference oracle for FAM-PASSWORD-SPRAY.",
  "recommended_actions": [
    "block_indicator",
    "update_case_comment"
  ],
  "target_entity": "198.18.188.96",
  "verdict": "MALICIOUS"
}
EOF_DECISION
