#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI get_file_report --json '{"file_hash": "cbcaa7c8c083800e3cc42848140150b64e1b134ab2daf7146d7a62656cb4f183"}'
$SOC_CLI get_domain_report --json '{"domain": "assets-pool90.xyz"}'
$SOC_CLI lookup_entity --json '{"entity_id": "BLD-SAO-41"}'
$SOC_CLI isolate_host --json '{"hostname": "BLD-SAO-41"}'
$SOC_CLI block_indicator --json '{"indicator": "assets-pool90.xyz"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-16067", "comment": "Confirmed cryptominer on BLD-SAO-41 (10.15.0.93, leila.mehta): sysupdate (cbcaa7c8c083800e3cc42848140150b64e1b134ab2daf7146d7a62656cb4f183) at 96 percent CPU with stratum connections to assets-pool90.xyz (198.19.109.42). Host isolated, assets-pool90.xyz blocked, CI-SAO-48 left running its builds, escalated to Tier 2, case left open."}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
Confirmed cryptominer on BLD-SAO-41 (10.15.0.93, leila.mehta): sysupdate (cbcaa7c8c083800e3cc42848140150b64e1b134ab2daf7146d7a62656cb4f183) at 96 percent CPU with stratum connections to assets-pool90.xyz (198.19.109.42). Host isolated, assets-pool90.xyz blocked, CI-SAO-48 left running its builds, escalated to Tier 2, case left open.
```soc_decision
{"rationale": "Reference oracle for FAM-CRYPTOMINER-DEV.", "recommended_actions": ["isolate_host", "block_indicator", "update_case_comment"], "target_entity": "BLD-SAO-41", "verdict": "MALICIOUS"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-CRYPTOMINER-DEV-05",
  "rationale": "Reference oracle for FAM-CRYPTOMINER-DEV.",
  "recommended_actions": [
    "isolate_host",
    "block_indicator",
    "update_case_comment"
  ],
  "target_entity": "BLD-SAO-41",
  "verdict": "MALICIOUS"
}
EOF_DECISION
