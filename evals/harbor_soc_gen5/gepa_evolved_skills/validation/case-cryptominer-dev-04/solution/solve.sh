#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI get_file_report --json '{"file_hash": "c55ee0b7e8b137b0aa6f7f2d101d0aef6c68cc72284350bae2cdfc3d4c794eed"}'
$SOC_CLI get_domain_report --json '{"domain": "pulse-pool83.io"}'
$SOC_CLI lookup_entity --json '{"entity_id": "BLD-SIN-57"}'
$SOC_CLI isolate_host --json '{"hostname": "BLD-SIN-57"}'
$SOC_CLI block_indicator --json '{"indicator": "pulse-pool83.io"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-75383", "comment": "Confirmed cryptominer on BLD-SIN-57 (10.12.0.69, yara.okafor): xmrig (c55ee0b7e8b137b0aa6f7f2d101d0aef6c68cc72284350bae2cdfc3d4c794eed) at 98 percent CPU with stratum connections to pulse-pool83.io (198.19.89.170). Host isolated, pulse-pool83.io blocked, CI-SIN-73 left running its builds, escalated to Tier 2, case left open."}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
Confirmed cryptominer on BLD-SIN-57 (10.12.0.69, yara.okafor): xmrig (c55ee0b7e8b137b0aa6f7f2d101d0aef6c68cc72284350bae2cdfc3d4c794eed) at 98 percent CPU with stratum connections to pulse-pool83.io (198.19.89.170). Host isolated, pulse-pool83.io blocked, CI-SIN-73 left running its builds, escalated to Tier 2, case left open.
```soc_decision
{"rationale": "Reference oracle for FAM-CRYPTOMINER-DEV.", "recommended_actions": ["isolate_host", "block_indicator", "update_case_comment"], "target_entity": "BLD-SIN-57", "verdict": "MALICIOUS"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-CRYPTOMINER-DEV-04",
  "rationale": "Reference oracle for FAM-CRYPTOMINER-DEV.",
  "recommended_actions": [
    "isolate_host",
    "block_indicator",
    "update_case_comment"
  ],
  "target_entity": "BLD-SIN-57",
  "verdict": "MALICIOUS"
}
EOF_DECISION
