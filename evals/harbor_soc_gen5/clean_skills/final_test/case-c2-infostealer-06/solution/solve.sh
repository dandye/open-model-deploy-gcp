#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI get_domain_report --json '{"domain": "portal-signal18.info"}'
$SOC_CLI lookup_entity --json '{"entity_id": "PC-TOR-16"}'
$SOC_CLI get_file_report --json '{"file_hash": "42b7a021552cb9b437f792798b8bc54ecb02b256c659644d93524a6be1a88a98"}'
$SOC_CLI isolate_host --json '{"hostname": "PC-TOR-16"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-97581", "comment": "Confirmed Rhadamanthys infostealer C2: PC-TOR-16 (10.14.0.10) beaconed 24 times to portal-signal18.info (198.19.13.24) and ran dropper winlogon_helper.exe (42b7a021552cb9b437f792798b8bc54ecb02b256c659644d93524a6be1a88a98). Host isolated, LT-TOR-94 left untouched, escalated to Tier 2, case left open."}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
Confirmed Rhadamanthys infostealer C2: PC-TOR-16 (10.14.0.10) beaconed 24 times to portal-signal18.info (198.19.13.24) and ran dropper winlogon_helper.exe (42b7a021552cb9b437f792798b8bc54ecb02b256c659644d93524a6be1a88a98). Host isolated, LT-TOR-94 left untouched, escalated to Tier 2, case left open.
```soc_decision
{"rationale": "Reference oracle for FAM-C2-INFOSTEALER.", "recommended_actions": ["isolate_host", "update_case_comment"], "target_entity": "PC-TOR-16", "verdict": "MALICIOUS"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-C2-INFOSTEALER-06",
  "rationale": "Reference oracle for FAM-C2-INFOSTEALER.",
  "recommended_actions": [
    "isolate_host",
    "update_case_comment"
  ],
  "target_entity": "PC-TOR-16",
  "verdict": "MALICIOUS"
}
EOF_DECISION
