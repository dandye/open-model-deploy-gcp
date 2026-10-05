#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI get_ip_report --json '{"ip": "198.18.54.77"}'
$SOC_CLI udm_search --json '{"query": "CKEY-C5E517155EC19535"}'
$SOC_CLI lookup_entity --json '{"entity_id": "CI-FRA-95"}'
$SOC_CLI block_indicator --json '{"indicator": "198.18.54.77"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-22750", "comment": "Compromised credential: service account key CKEY-C5E517155EC19535 (project ledger-prod) was used from 198.18.54.77, an anonymizing exit with a malicious reputation, to download 626 GB tagged contract archive; its only expected callers are CI-FRA-95 and BAS-FRA-57. 198.18.54.77 blocked, immediate rotation and revocation of CKEY-C5E517155EC19535 requested from the cloud platform team, audit log preserved, escalated to incident response and privacy; BAS-FRA-57 and CI-FRA-95 left online, case left open."}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
Compromised credential: service account key CKEY-C5E517155EC19535 (project ledger-prod) was used from 198.18.54.77, an anonymizing exit with a malicious reputation, to download 626 GB tagged contract archive; its only expected callers are CI-FRA-95 and BAS-FRA-57. 198.18.54.77 blocked, immediate rotation and revocation of CKEY-C5E517155EC19535 requested from the cloud platform team, audit log preserved, escalated to incident response and privacy; BAS-FRA-57 and CI-FRA-95 left online, case left open.
```soc_decision
{"rationale": "Reference oracle for FAM-CLOUD-KEY-EXFIL.", "recommended_actions": ["block_indicator", "update_case_comment"], "target_entity": "CKEY-C5E517155EC19535", "verdict": "MALICIOUS"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-CLOUD-KEY-EXFIL-01",
  "rationale": "Reference oracle for FAM-CLOUD-KEY-EXFIL.",
  "recommended_actions": [
    "block_indicator",
    "update_case_comment"
  ],
  "target_entity": "CKEY-C5E517155EC19535",
  "verdict": "MALICIOUS"
}
EOF_DECISION
