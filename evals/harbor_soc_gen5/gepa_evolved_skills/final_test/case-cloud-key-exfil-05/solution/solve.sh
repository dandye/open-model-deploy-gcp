#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI get_ip_report --json '{"ip": "198.18.62.254"}'
$SOC_CLI udm_search --json '{"query": "CKEY-197BD3879EB7143B"}'
$SOC_CLI lookup_entity --json '{"entity_id": "CI-DUB-08"}'
$SOC_CLI block_indicator --json '{"indicator": "198.18.62.254"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-83480", "comment": "Compromised credential: service account key CKEY-197BD3879EB7143B (project customer-vault) was used from 198.18.62.254, an anonymizing exit with a malicious reputation, to download 149 GB tagged pricing model; its only expected callers are CI-DUB-08 and BAS-DUB-28. 198.18.62.254 blocked, immediate rotation and revocation of CKEY-197BD3879EB7143B requested from the cloud platform team, audit log preserved, escalated to incident response and privacy; BAS-DUB-28 and CI-DUB-08 left online, case left open."}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
Compromised credential: service account key CKEY-197BD3879EB7143B (project customer-vault) was used from 198.18.62.254, an anonymizing exit with a malicious reputation, to download 149 GB tagged pricing model; its only expected callers are CI-DUB-08 and BAS-DUB-28. 198.18.62.254 blocked, immediate rotation and revocation of CKEY-197BD3879EB7143B requested from the cloud platform team, audit log preserved, escalated to incident response and privacy; BAS-DUB-28 and CI-DUB-08 left online, case left open.
```soc_decision
{"rationale": "Reference oracle for FAM-CLOUD-KEY-EXFIL.", "recommended_actions": ["block_indicator", "update_case_comment"], "target_entity": "CKEY-197BD3879EB7143B", "verdict": "MALICIOUS"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-CLOUD-KEY-EXFIL-05",
  "rationale": "Reference oracle for FAM-CLOUD-KEY-EXFIL.",
  "recommended_actions": [
    "block_indicator",
    "update_case_comment"
  ],
  "target_entity": "CKEY-197BD3879EB7143B",
  "verdict": "MALICIOUS"
}
EOF_DECISION
