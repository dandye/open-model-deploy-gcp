#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI lookup_entity --json '{"entity_id": "WKS-DUB-88"}'
$SOC_CLI get_domain_report --json '{"domain": "meshproxy-drive.io"}'
$SOC_CLI udm_search --json '{"query": "theo.ferreira"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-68370", "comment": "Suspected insider exfiltration: theo.ferreira (Finance, resigned, last day 2026-09-28T03:55:00Z) uploaded 7603 files tagged pricing model from WKS-DUB-88 (10.13.0.185) to personal storage meshproxy-drive.io (198.18.81.23), a clean consumer service, so this is a data-handling matter rather than malware. Evidence preserved (DLP records and endpoint logs), escalated to HR and legal with the file inventory, legal hold requested; no action visible to the user, WKS-DUB-32 not involved, case left open."}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
Suspected insider exfiltration: theo.ferreira (Finance, resigned, last day 2026-09-28T03:55:00Z) uploaded 7603 files tagged pricing model from WKS-DUB-88 (10.13.0.185) to personal storage meshproxy-drive.io (198.18.81.23), a clean consumer service, so this is a data-handling matter rather than malware. Evidence preserved (DLP records and endpoint logs), escalated to HR and legal with the file inventory, legal hold requested; no action visible to the user, WKS-DUB-32 not involved, case left open.
```soc_decision
{"rationale": "Reference oracle for FAM-INSIDER-EXFIL.", "recommended_actions": ["update_case_comment"], "target_entity": "WKS-DUB-88", "verdict": "SUSPICIOUS"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-INSIDER-EXFIL-04",
  "rationale": "Reference oracle for FAM-INSIDER-EXFIL.",
  "recommended_actions": [
    "update_case_comment"
  ],
  "target_entity": "WKS-DUB-88",
  "verdict": "SUSPICIOUS"
}
EOF_DECISION
