#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI lookup_entity --json '{"entity_id": "WKS-LON-37"}'
$SOC_CLI get_file_report --json '{"file_hash": "7db264fb0dc7c4b6b47c668cdca3ec58f805f593c737102adab3240c9ab16190"}'
$SOC_CLI lookup_entity --json '{"entity_id": "DC-LON-34"}'
$SOC_CLI isolate_host --json '{"hostname": "WKS-LON-37"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-61577", "comment": "Lateral movement confirmed: anika.becker on WKS-LON-37 (10.16.0.61) ran PsExec64.exe (7db264fb0dc7c4b6b47c668cdca3ec58f805f593c737102adab3240c9ab16190) and opened 43 admin-share connections to DC-LON-34, where EDR blocked the service start. WKS-LON-37 isolated, credential revocation requested for anika.becker, DC-LON-34 left online, escalated to Tier 2, case left open."}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
Lateral movement confirmed: anika.becker on WKS-LON-37 (10.16.0.61) ran PsExec64.exe (7db264fb0dc7c4b6b47c668cdca3ec58f805f593c737102adab3240c9ab16190) and opened 43 admin-share connections to DC-LON-34, where EDR blocked the service start. WKS-LON-37 isolated, credential revocation requested for anika.becker, DC-LON-34 left online, escalated to Tier 2, case left open.
```soc_decision
{"rationale": "Reference oracle for FAM-LATERAL-PSEXEC.", "recommended_actions": ["isolate_host", "update_case_comment"], "target_entity": "WKS-LON-37", "verdict": "MALICIOUS"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-LATERAL-PSEXEC-06",
  "rationale": "Reference oracle for FAM-LATERAL-PSEXEC.",
  "recommended_actions": [
    "isolate_host",
    "update_case_comment"
  ],
  "target_entity": "WKS-LON-37",
  "verdict": "MALICIOUS"
}
EOF_DECISION
