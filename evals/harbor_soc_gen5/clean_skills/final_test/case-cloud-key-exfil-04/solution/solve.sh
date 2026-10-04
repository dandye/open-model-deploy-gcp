#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI get_ip_report --json '{"ip": "198.18.124.21"}'
$SOC_CLI udm_search --json '{"query": "CKEY-7DE5AC4082AD1585"}'
$SOC_CLI lookup_entity --json '{"entity_id": "CI-LON-62"}'
$SOC_CLI block_indicator --json '{"indicator": "198.18.124.21"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-72677", "comment": "Compromised credential: service account key CKEY-7DE5AC4082AD1585 (project analytics-core) was used from 198.18.124.21, an anonymizing exit with a malicious reputation, to download 773 GB tagged customer export; its only expected callers are CI-LON-62 and BAS-LON-07. 198.18.124.21 blocked, immediate rotation and revocation of CKEY-7DE5AC4082AD1585 requested from the cloud platform team, audit log preserved, escalated to incident response and privacy; BAS-LON-07 and CI-LON-62 left online, case left open."}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
Compromised credential: service account key CKEY-7DE5AC4082AD1585 (project analytics-core) was used from 198.18.124.21, an anonymizing exit with a malicious reputation, to download 773 GB tagged customer export; its only expected callers are CI-LON-62 and BAS-LON-07. 198.18.124.21 blocked, immediate rotation and revocation of CKEY-7DE5AC4082AD1585 requested from the cloud platform team, audit log preserved, escalated to incident response and privacy; BAS-LON-07 and CI-LON-62 left online, case left open.
```soc_decision
{"rationale": "Reference oracle for FAM-CLOUD-KEY-EXFIL.", "recommended_actions": ["block_indicator", "update_case_comment"], "target_entity": "CKEY-7DE5AC4082AD1585", "verdict": "MALICIOUS"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-CLOUD-KEY-EXFIL-04",
  "rationale": "Reference oracle for FAM-CLOUD-KEY-EXFIL.",
  "recommended_actions": [
    "block_indicator",
    "update_case_comment"
  ],
  "target_entity": "CKEY-7DE5AC4082AD1585",
  "verdict": "MALICIOUS"
}
EOF_DECISION
