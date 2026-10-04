#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI get_file_report --json '{"file_hash": "c222725284b1dcee9ca8b2474ddc0641901316441ecf06bb42d82a805f6cde34"}'
$SOC_CLI get_domain_report --json '{"domain": "link-pool35.xyz"}'
$SOC_CLI lookup_entity --json '{"entity_id": "BLD-SAO-51"}'
$SOC_CLI isolate_host --json '{"hostname": "BLD-SAO-51"}'
$SOC_CLI block_indicator --json '{"indicator": "link-pool35.xyz"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-65402", "comment": "Confirmed cryptominer on BLD-SAO-51 (10.15.0.124, caleb.hartmann): kdevtmpfsi (c222725284b1dcee9ca8b2474ddc0641901316441ecf06bb42d82a805f6cde34) at 95 percent CPU with stratum connections to link-pool35.xyz (198.19.89.249). Host isolated, link-pool35.xyz blocked, CI-SAO-06 left running its builds, escalated to Tier 2, case left open."}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
Confirmed cryptominer on BLD-SAO-51 (10.15.0.124, caleb.hartmann): kdevtmpfsi (c222725284b1dcee9ca8b2474ddc0641901316441ecf06bb42d82a805f6cde34) at 95 percent CPU with stratum connections to link-pool35.xyz (198.19.89.249). Host isolated, link-pool35.xyz blocked, CI-SAO-06 left running its builds, escalated to Tier 2, case left open.
```soc_decision
{"rationale": "Reference oracle for FAM-CRYPTOMINER-DEV.", "recommended_actions": ["isolate_host", "block_indicator", "update_case_comment"], "target_entity": "BLD-SAO-51", "verdict": "MALICIOUS"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-CRYPTOMINER-DEV-03",
  "rationale": "Reference oracle for FAM-CRYPTOMINER-DEV.",
  "recommended_actions": [
    "isolate_host",
    "block_indicator",
    "update_case_comment"
  ],
  "target_entity": "BLD-SAO-51",
  "verdict": "MALICIOUS"
}
EOF_DECISION
