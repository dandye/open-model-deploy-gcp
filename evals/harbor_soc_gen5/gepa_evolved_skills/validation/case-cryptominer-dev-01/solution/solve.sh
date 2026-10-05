#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI get_file_report --json '{"file_hash": "ab2a58d07428cc7d3d17ec10891c0e38206b05d80f94ac57ad84c8581bb1e29a"}'
$SOC_CLI get_domain_report --json '{"domain": "assets-pool53.info"}'
$SOC_CLI lookup_entity --json '{"entity_id": "BLD-SYD-49"}'
$SOC_CLI isolate_host --json '{"hostname": "BLD-SYD-49"}'
$SOC_CLI block_indicator --json '{"indicator": "assets-pool53.info"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-13081", "comment": "Confirmed cryptominer on BLD-SYD-49 (10.17.0.6, imani.nwosu): kswapd0x (ab2a58d07428cc7d3d17ec10891c0e38206b05d80f94ac57ad84c8581bb1e29a) at 90 percent CPU with stratum connections to assets-pool53.info (198.18.50.115). Host isolated, assets-pool53.info blocked, CI-SYD-75 left running its builds, escalated to Tier 2, case left open."}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
Confirmed cryptominer on BLD-SYD-49 (10.17.0.6, imani.nwosu): kswapd0x (ab2a58d07428cc7d3d17ec10891c0e38206b05d80f94ac57ad84c8581bb1e29a) at 90 percent CPU with stratum connections to assets-pool53.info (198.18.50.115). Host isolated, assets-pool53.info blocked, CI-SYD-75 left running its builds, escalated to Tier 2, case left open.
```soc_decision
{"rationale": "Reference oracle for FAM-CRYPTOMINER-DEV.", "recommended_actions": ["isolate_host", "block_indicator", "update_case_comment"], "target_entity": "BLD-SYD-49", "verdict": "MALICIOUS"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-CRYPTOMINER-DEV-01",
  "rationale": "Reference oracle for FAM-CRYPTOMINER-DEV.",
  "recommended_actions": [
    "isolate_host",
    "block_indicator",
    "update_case_comment"
  ],
  "target_entity": "BLD-SYD-49",
  "verdict": "MALICIOUS"
}
EOF_DECISION
