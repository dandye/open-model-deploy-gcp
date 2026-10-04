#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI get_domain_report --json '{"domain": "gateway-drive68.info"}'
$SOC_CLI lookup_entity --json '{"entity_id": "LT-LON-06"}'
$SOC_CLI get_file_report --json '{"file_hash": "61d69e089292a1c7fdb831f98fc40cc11e482fd61736dedaa9c1057838a5c02b"}'
$SOC_CLI isolate_host --json '{"hostname": "LT-LON-06"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-16547", "comment": "Confirmed Lumma infostealer C2: LT-LON-06 (10.16.0.172) beaconed 96 times to gateway-drive68.info (198.18.109.32) and ran dropper msdtc_srv.exe (61d69e089292a1c7fdb831f98fc40cc11e482fd61736dedaa9c1057838a5c02b). Host isolated, PC-LON-78 left untouched, escalated to Tier 2, case left open."}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
Confirmed Lumma infostealer C2: LT-LON-06 (10.16.0.172) beaconed 96 times to gateway-drive68.info (198.18.109.32) and ran dropper msdtc_srv.exe (61d69e089292a1c7fdb831f98fc40cc11e482fd61736dedaa9c1057838a5c02b). Host isolated, PC-LON-78 left untouched, escalated to Tier 2, case left open.
```soc_decision
{"rationale": "Reference oracle for FAM-C2-INFOSTEALER.", "recommended_actions": ["isolate_host", "update_case_comment"], "target_entity": "LT-LON-06", "verdict": "MALICIOUS"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-C2-INFOSTEALER-05",
  "rationale": "Reference oracle for FAM-C2-INFOSTEALER.",
  "recommended_actions": [
    "isolate_host",
    "update_case_comment"
  ],
  "target_entity": "LT-LON-06",
  "verdict": "MALICIOUS"
}
EOF_DECISION
