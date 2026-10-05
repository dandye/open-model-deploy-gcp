#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI lookup_entity --json '{"entity_id": "PC-TOR-76"}'
$SOC_CLI get_file_report --json '{"file_hash": "76994261523c0724f3dd7ef5e4f344409cbc7a8de8f0f710770f1834d527bcd7"}'
$SOC_CLI lookup_entity --json '{"entity_id": "DC-TOR-69"}'
$SOC_CLI isolate_host --json '{"hostname": "PC-TOR-76"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-78439", "comment": "Lateral movement confirmed: theo.haddad on PC-TOR-76 (10.14.0.70) ran smbexec.py (76994261523c0724f3dd7ef5e4f344409cbc7a8de8f0f710770f1834d527bcd7) and opened 95 admin-share connections to DC-TOR-69, where EDR blocked the service start. PC-TOR-76 isolated, credential revocation requested for theo.haddad, DC-TOR-69 left online, escalated to Tier 2, case left open."}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
Lateral movement confirmed: theo.haddad on PC-TOR-76 (10.14.0.70) ran smbexec.py (76994261523c0724f3dd7ef5e4f344409cbc7a8de8f0f710770f1834d527bcd7) and opened 95 admin-share connections to DC-TOR-69, where EDR blocked the service start. PC-TOR-76 isolated, credential revocation requested for theo.haddad, DC-TOR-69 left online, escalated to Tier 2, case left open.
```soc_decision
{"rationale": "Reference oracle for FAM-LATERAL-PSEXEC.", "recommended_actions": ["isolate_host", "update_case_comment"], "target_entity": "PC-TOR-76", "verdict": "MALICIOUS"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-LATERAL-PSEXEC-05",
  "rationale": "Reference oracle for FAM-LATERAL-PSEXEC.",
  "recommended_actions": [
    "isolate_host",
    "update_case_comment"
  ],
  "target_entity": "PC-TOR-76",
  "verdict": "MALICIOUS"
}
EOF_DECISION
