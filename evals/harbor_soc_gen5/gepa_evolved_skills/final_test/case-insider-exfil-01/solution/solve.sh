#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI lookup_entity --json '{"entity_id": "LT-SYD-76"}'
$SOC_CLI get_domain_report --json '{"domain": "telemetrystatus-drive.io"}'
$SOC_CLI udm_search --json '{"query": "sofia.qureshi"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-95577", "comment": "Suspected insider exfiltration: sofia.qureshi (Finance, resigned, last day 2026-09-16T05:31:00Z) uploaded 8874 files tagged pricing model from LT-SYD-76 (10.17.0.206) to personal storage telemetrystatus-drive.io (198.18.37.214), a clean consumer service, so this is a data-handling matter rather than malware. Evidence preserved (DLP records and endpoint logs), escalated to HR and legal with the file inventory, legal hold requested; no action visible to the user, WKS-SYD-71 not involved, case left open."}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
Suspected insider exfiltration: sofia.qureshi (Finance, resigned, last day 2026-09-16T05:31:00Z) uploaded 8874 files tagged pricing model from LT-SYD-76 (10.17.0.206) to personal storage telemetrystatus-drive.io (198.18.37.214), a clean consumer service, so this is a data-handling matter rather than malware. Evidence preserved (DLP records and endpoint logs), escalated to HR and legal with the file inventory, legal hold requested; no action visible to the user, WKS-SYD-71 not involved, case left open.
```soc_decision
{"rationale": "Reference oracle for FAM-INSIDER-EXFIL.", "recommended_actions": ["update_case_comment"], "target_entity": "LT-SYD-76", "verdict": "SUSPICIOUS"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-INSIDER-EXFIL-01",
  "rationale": "Reference oracle for FAM-INSIDER-EXFIL.",
  "recommended_actions": [
    "update_case_comment"
  ],
  "target_entity": "LT-SYD-76",
  "verdict": "SUSPICIOUS"
}
EOF_DECISION
