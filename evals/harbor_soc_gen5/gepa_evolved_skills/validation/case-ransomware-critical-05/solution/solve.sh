#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI get_file_report --json '{"file_hash": "b4c0fd552aad679240349e338ef75f2c1863e8246318240db09bf4b071fff018"}'
$SOC_CLI lookup_entity --json '{"entity_id": "FS-SIN-94"}'
$SOC_CLI isolate_host --json '{"hostname": "FS-SIN-94"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-70440", "comment": "Active LockBit ransomware on FS-SIN-94 (10.12.0.223): taskhostw2.exe (b4c0fd552aad679240349e338ef75f2c1863e8246318240db09bf4b071fff018) is encrypting shares with .crypt and dropped RESTORE_DATA.hta. Host network-isolated, no reboot to preserve volatile memory, BKP-SIN-13 left online for the restore, escalated to incident response, case left open."}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
Active LockBit ransomware on FS-SIN-94 (10.12.0.223): taskhostw2.exe (b4c0fd552aad679240349e338ef75f2c1863e8246318240db09bf4b071fff018) is encrypting shares with .crypt and dropped RESTORE_DATA.hta. Host network-isolated, no reboot to preserve volatile memory, BKP-SIN-13 left online for the restore, escalated to incident response, case left open.
```soc_decision
{"rationale": "Reference oracle for FAM-RANSOMWARE-CRITICAL.", "recommended_actions": ["isolate_host", "update_case_comment"], "target_entity": "FS-SIN-94", "verdict": "MALICIOUS"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-RANSOMWARE-CRITICAL-05",
  "rationale": "Reference oracle for FAM-RANSOMWARE-CRITICAL.",
  "recommended_actions": [
    "isolate_host",
    "update_case_comment"
  ],
  "target_entity": "FS-SIN-94",
  "verdict": "MALICIOUS"
}
EOF_DECISION
