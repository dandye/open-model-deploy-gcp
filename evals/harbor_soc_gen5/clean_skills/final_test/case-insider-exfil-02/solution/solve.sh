#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI lookup_entity --json '{"entity_id": "WKS-SAO-99"}'
$SOC_CLI get_domain_report --json '{"domain": "synccache-drive.com"}'
$SOC_CLI udm_search --json '{"query": "ingrid.tanaka"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-54105", "comment": "Suspected insider exfiltration: ingrid.tanaka (Finance, resigned, last day 2026-09-15T16:56:00Z) uploaded 3412 files tagged pricing model from WKS-SAO-99 (10.15.0.142) to personal storage synccache-drive.com (198.19.214.204), a clean consumer service, so this is a data-handling matter rather than malware. Evidence preserved (DLP records and endpoint logs), escalated to HR and legal with the file inventory, legal hold requested; no action visible to the user, PC-SAO-76 not involved, case left open."}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
Suspected insider exfiltration: ingrid.tanaka (Finance, resigned, last day 2026-09-15T16:56:00Z) uploaded 3412 files tagged pricing model from WKS-SAO-99 (10.15.0.142) to personal storage synccache-drive.com (198.19.214.204), a clean consumer service, so this is a data-handling matter rather than malware. Evidence preserved (DLP records and endpoint logs), escalated to HR and legal with the file inventory, legal hold requested; no action visible to the user, PC-SAO-76 not involved, case left open.
```soc_decision
{"rationale": "Reference oracle for FAM-INSIDER-EXFIL.", "recommended_actions": ["update_case_comment"], "target_entity": "WKS-SAO-99", "verdict": "SUSPICIOUS"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-INSIDER-EXFIL-02",
  "rationale": "Reference oracle for FAM-INSIDER-EXFIL.",
  "recommended_actions": [
    "update_case_comment"
  ],
  "target_entity": "WKS-SAO-99",
  "verdict": "SUSPICIOUS"
}
EOF_DECISION
