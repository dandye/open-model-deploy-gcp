#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI get_ip_report --json '{"ip": "198.19.169.245"}'
$SOC_CLI udm_search --json '{"query": "CKEY-12D47068CA043025"}'
$SOC_CLI lookup_entity --json '{"entity_id": "CI-DEN-33"}'
$SOC_CLI block_indicator --json '{"indicator": "198.19.169.245"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-32478", "comment": "Compromised credential: service account key CKEY-12D47068CA043025 (project ledger-prod) was used from 198.19.169.245, an anonymizing exit with a malicious reputation, to download 874 GB tagged pricing model; its only expected callers are CI-DEN-33 and BAS-DEN-57. 198.19.169.245 blocked, immediate rotation and revocation of CKEY-12D47068CA043025 requested from the cloud platform team, audit log preserved, escalated to incident response and privacy; BAS-DEN-57 and CI-DEN-33 left online, case left open."}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
Compromised credential: service account key CKEY-12D47068CA043025 (project ledger-prod) was used from 198.19.169.245, an anonymizing exit with a malicious reputation, to download 874 GB tagged pricing model; its only expected callers are CI-DEN-33 and BAS-DEN-57. 198.19.169.245 blocked, immediate rotation and revocation of CKEY-12D47068CA043025 requested from the cloud platform team, audit log preserved, escalated to incident response and privacy; BAS-DEN-57 and CI-DEN-33 left online, case left open.
```soc_decision
{"rationale": "Reference oracle for FAM-CLOUD-KEY-EXFIL.", "recommended_actions": ["block_indicator", "update_case_comment"], "target_entity": "CKEY-12D47068CA043025", "verdict": "MALICIOUS"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-CLOUD-KEY-EXFIL-02",
  "rationale": "Reference oracle for FAM-CLOUD-KEY-EXFIL.",
  "recommended_actions": [
    "block_indicator",
    "update_case_comment"
  ],
  "target_entity": "CKEY-12D47068CA043025",
  "verdict": "MALICIOUS"
}
EOF_DECISION
