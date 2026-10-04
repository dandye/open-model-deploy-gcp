#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI get_file_report --json '{"file_hash": "26178409b81cd7f9d8d15e0cdc514e0a934d66bcb91a9aae341719f22c7e8e92"}'
$SOC_CLI lookup_entity --json '{"entity_id": "NAS-FRA-11"}'
$SOC_CLI isolate_host --json '{"hostname": "NAS-FRA-11"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-34504", "comment": "Active Play ransomware on NAS-FRA-11 (10.11.0.197): taskhostw2.exe (26178409b81cd7f9d8d15e0cdc514e0a934d66bcb91a9aae341719f22c7e8e92) is encrypting shares with .royal and dropped HOW_TO_DECRYPT.txt. Host network-isolated, no reboot to preserve volatile memory, BKP-FRA-44 left online for the restore, escalated to incident response, case left open."}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
Active Play ransomware on NAS-FRA-11 (10.11.0.197): taskhostw2.exe (26178409b81cd7f9d8d15e0cdc514e0a934d66bcb91a9aae341719f22c7e8e92) is encrypting shares with .royal and dropped HOW_TO_DECRYPT.txt. Host network-isolated, no reboot to preserve volatile memory, BKP-FRA-44 left online for the restore, escalated to incident response, case left open.
```soc_decision
{"rationale": "Reference oracle for FAM-RANSOMWARE-CRITICAL.", "recommended_actions": ["isolate_host", "update_case_comment"], "target_entity": "NAS-FRA-11", "verdict": "MALICIOUS"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-RANSOMWARE-CRITICAL-06",
  "rationale": "Reference oracle for FAM-RANSOMWARE-CRITICAL.",
  "recommended_actions": [
    "isolate_host",
    "update_case_comment"
  ],
  "target_entity": "NAS-FRA-11",
  "verdict": "MALICIOUS"
}
EOF_DECISION
