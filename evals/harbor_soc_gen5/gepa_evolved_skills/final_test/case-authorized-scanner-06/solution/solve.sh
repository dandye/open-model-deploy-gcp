#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI lookup_entity --json '{"entity_id": "PAY-SYD-64"}'
$SOC_CLI lookup_entity --json '{"entity_id": "SCN-SYD-48"}'
$SOC_CLI get_ip_report --json '{"ip": "10.17.0.200"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-66247", "comment": "PAY-SYD-64 (10.17.0.252) was scanned by SCN-SYD-48 (10.17.0.200), the Tenable Nessus scanner authorized by change ticket CHG-45245 for this window; the host runs the Tenable Nessus agent and shows no other anomalies. Verdict BENIGN: authorized vulnerability scan, no isolation, closing CASE-66247."}'
$SOC_CLI close_case --json '{"case_id": "CASE-66247", "verdict": "BENIGN"}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
PAY-SYD-64 (10.17.0.252) was scanned by SCN-SYD-48 (10.17.0.200), the Tenable Nessus scanner authorized by change ticket CHG-45245 for this window; the host runs the Tenable Nessus agent and shows no other anomalies. Verdict BENIGN: authorized vulnerability scan, no isolation, closing CASE-66247.
```soc_decision
{"rationale": "Reference oracle for FAM-AUTHORIZED-SCANNER.", "recommended_actions": ["update_case_comment", "close_case"], "target_entity": "PAY-SYD-64", "verdict": "BENIGN"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-AUTHORIZED-SCANNER-06",
  "rationale": "Reference oracle for FAM-AUTHORIZED-SCANNER.",
  "recommended_actions": [
    "update_case_comment",
    "close_case"
  ],
  "target_entity": "PAY-SYD-64",
  "verdict": "BENIGN"
}
EOF_DECISION
