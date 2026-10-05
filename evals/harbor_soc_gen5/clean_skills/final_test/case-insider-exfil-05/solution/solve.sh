#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI lookup_entity --json '{"entity_id": "WKS-DUB-91"}'
$SOC_CLI get_domain_report --json '{"domain": "portaledge-drive.io"}'
$SOC_CLI udm_search --json '{"query": "tobias.okafor"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-13670", "comment": "Suspected insider exfiltration: tobias.okafor (Human Resources, resigned, last day 2026-09-12T14:45:00Z) uploaded 2916 files tagged salary roster from WKS-DUB-91 (10.13.0.22) to personal storage portaledge-drive.io (198.19.41.187), a clean consumer service, so this is a data-handling matter rather than malware. Evidence preserved (DLP records and endpoint logs), escalated to HR and legal with the file inventory, legal hold requested; no action visible to the user, LT-DUB-92 not involved, case left open."}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
Suspected insider exfiltration: tobias.okafor (Human Resources, resigned, last day 2026-09-12T14:45:00Z) uploaded 2916 files tagged salary roster from WKS-DUB-91 (10.13.0.22) to personal storage portaledge-drive.io (198.19.41.187), a clean consumer service, so this is a data-handling matter rather than malware. Evidence preserved (DLP records and endpoint logs), escalated to HR and legal with the file inventory, legal hold requested; no action visible to the user, LT-DUB-92 not involved, case left open.
```soc_decision
{"rationale": "Reference oracle for FAM-INSIDER-EXFIL.", "recommended_actions": ["update_case_comment"], "target_entity": "WKS-DUB-91", "verdict": "SUSPICIOUS"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-INSIDER-EXFIL-05",
  "rationale": "Reference oracle for FAM-INSIDER-EXFIL.",
  "recommended_actions": [
    "update_case_comment"
  ],
  "target_entity": "WKS-DUB-91",
  "verdict": "SUSPICIOUS"
}
EOF_DECISION
