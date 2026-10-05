#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI get_ip_report --json '{"ip": "198.18.112.126"}'
$SOC_CLI udm_search --json '{"query": "CKEY-127FD7992EC7D9F0"}'
$SOC_CLI lookup_entity --json '{"entity_id": "CI-DUB-61"}'
$SOC_CLI block_indicator --json '{"indicator": "198.18.112.126"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-48409", "comment": "Compromised credential: service account key CKEY-127FD7992EC7D9F0 (project customer-vault) was used from 198.18.112.126, an anonymizing exit with a malicious reputation, to download 114 GB tagged pricing model; its only expected callers are CI-DUB-61 and BAS-DUB-86. 198.18.112.126 blocked, immediate rotation and revocation of CKEY-127FD7992EC7D9F0 requested from the cloud platform team, audit log preserved, escalated to incident response and privacy; BAS-DUB-86 and CI-DUB-61 left online, case left open."}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
Compromised credential: service account key CKEY-127FD7992EC7D9F0 (project customer-vault) was used from 198.18.112.126, an anonymizing exit with a malicious reputation, to download 114 GB tagged pricing model; its only expected callers are CI-DUB-61 and BAS-DUB-86. 198.18.112.126 blocked, immediate rotation and revocation of CKEY-127FD7992EC7D9F0 requested from the cloud platform team, audit log preserved, escalated to incident response and privacy; BAS-DUB-86 and CI-DUB-61 left online, case left open.
```soc_decision
{"rationale": "Reference oracle for FAM-CLOUD-KEY-EXFIL.", "recommended_actions": ["block_indicator", "update_case_comment"], "target_entity": "CKEY-127FD7992EC7D9F0", "verdict": "MALICIOUS"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-CLOUD-KEY-EXFIL-03",
  "rationale": "Reference oracle for FAM-CLOUD-KEY-EXFIL.",
  "recommended_actions": [
    "block_indicator",
    "update_case_comment"
  ],
  "target_entity": "CKEY-127FD7992EC7D9F0",
  "verdict": "MALICIOUS"
}
EOF_DECISION
