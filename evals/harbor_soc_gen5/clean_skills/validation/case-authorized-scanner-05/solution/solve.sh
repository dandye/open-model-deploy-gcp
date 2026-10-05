#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI lookup_entity --json '{"entity_id": "PAY-FRA-05"}'
$SOC_CLI lookup_entity --json '{"entity_id": "SCN-FRA-17"}'
$SOC_CLI get_ip_report --json '{"ip": "10.11.0.135"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-55025", "comment": "PAY-FRA-05 (10.11.0.155) was scanned by SCN-FRA-17 (10.11.0.135), the CrowdStrike Spotlight scanner authorized by change ticket CHG-65525 for this window; the host runs the CrowdStrike Spotlight agent and shows no other anomalies. Verdict BENIGN: authorized vulnerability scan, no isolation, closing CASE-55025."}'
$SOC_CLI close_case --json '{"case_id": "CASE-55025", "verdict": "BENIGN"}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
PAY-FRA-05 (10.11.0.155) was scanned by SCN-FRA-17 (10.11.0.135), the CrowdStrike Spotlight scanner authorized by change ticket CHG-65525 for this window; the host runs the CrowdStrike Spotlight agent and shows no other anomalies. Verdict BENIGN: authorized vulnerability scan, no isolation, closing CASE-55025.
```soc_decision
{"rationale": "Reference oracle for FAM-AUTHORIZED-SCANNER.", "recommended_actions": ["update_case_comment", "close_case"], "target_entity": "PAY-FRA-05", "verdict": "BENIGN"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-AUTHORIZED-SCANNER-05",
  "rationale": "Reference oracle for FAM-AUTHORIZED-SCANNER.",
  "recommended_actions": [
    "update_case_comment",
    "close_case"
  ],
  "target_entity": "PAY-FRA-05",
  "verdict": "BENIGN"
}
EOF_DECISION
