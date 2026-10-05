#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI get_file_report --json '{"file_hash": "339042aa127bf3e671c641b941e40f1935984b1f2dda8cca3e822bdf8c8f4273"}'
$SOC_CLI get_domain_report --json '{"domain": "portal-pool26.info"}'
$SOC_CLI lookup_entity --json '{"entity_id": "DEV-BLR-53"}'
$SOC_CLI isolate_host --json '{"hostname": "DEV-BLR-53"}'
$SOC_CLI block_indicator --json '{"indicator": "portal-pool26.info"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-43044", "comment": "Confirmed cryptominer on DEV-BLR-53 (10.18.0.60, sofia.iyer): sysupdate (339042aa127bf3e671c641b941e40f1935984b1f2dda8cca3e822bdf8c8f4273) at 86 percent CPU with stratum connections to portal-pool26.info (198.19.170.246). Host isolated, portal-pool26.info blocked, CI-BLR-44 left running its builds, escalated to Tier 2, case left open."}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
Confirmed cryptominer on DEV-BLR-53 (10.18.0.60, sofia.iyer): sysupdate (339042aa127bf3e671c641b941e40f1935984b1f2dda8cca3e822bdf8c8f4273) at 86 percent CPU with stratum connections to portal-pool26.info (198.19.170.246). Host isolated, portal-pool26.info blocked, CI-BLR-44 left running its builds, escalated to Tier 2, case left open.
```soc_decision
{"rationale": "Reference oracle for FAM-CRYPTOMINER-DEV.", "recommended_actions": ["isolate_host", "block_indicator", "update_case_comment"], "target_entity": "DEV-BLR-53", "verdict": "MALICIOUS"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-CRYPTOMINER-DEV-02",
  "rationale": "Reference oracle for FAM-CRYPTOMINER-DEV.",
  "recommended_actions": [
    "isolate_host",
    "block_indicator",
    "update_case_comment"
  ],
  "target_entity": "DEV-BLR-53",
  "verdict": "MALICIOUS"
}
EOF_DECISION
