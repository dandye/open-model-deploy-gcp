#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI lookup_entity --json '{"entity_id": "WKS-FRA-01"}'
$SOC_CLI get_domain_report --json '{"domain": "cacheshield-drive.net"}'
$SOC_CLI udm_search --json '{"query": "leila.haddad"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-61996", "comment": "Suspected insider exfiltration: leila.haddad (Legal, resigned, last day 2026-09-28T11:10:00Z) uploaded 1430 files tagged pricing model from WKS-FRA-01 (10.11.0.22) to personal storage cacheshield-drive.net (198.18.111.35), a clean consumer service, so this is a data-handling matter rather than malware. Evidence preserved (DLP records and endpoint logs), escalated to HR and legal with the file inventory, legal hold requested; no action visible to the user, PC-FRA-60 not involved, case left open."}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
Suspected insider exfiltration: leila.haddad (Legal, resigned, last day 2026-09-28T11:10:00Z) uploaded 1430 files tagged pricing model from WKS-FRA-01 (10.11.0.22) to personal storage cacheshield-drive.net (198.18.111.35), a clean consumer service, so this is a data-handling matter rather than malware. Evidence preserved (DLP records and endpoint logs), escalated to HR and legal with the file inventory, legal hold requested; no action visible to the user, PC-FRA-60 not involved, case left open.
```soc_decision
{"rationale": "Reference oracle for FAM-INSIDER-EXFIL.", "recommended_actions": ["update_case_comment"], "target_entity": "WKS-FRA-01", "verdict": "SUSPICIOUS"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-INSIDER-EXFIL-03",
  "rationale": "Reference oracle for FAM-INSIDER-EXFIL.",
  "recommended_actions": [
    "update_case_comment"
  ],
  "target_entity": "WKS-FRA-01",
  "verdict": "SUSPICIOUS"
}
EOF_DECISION
