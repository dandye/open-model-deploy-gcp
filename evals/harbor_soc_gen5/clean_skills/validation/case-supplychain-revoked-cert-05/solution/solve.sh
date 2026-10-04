#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI get_file_report --json '{"file_hash": "bd1098cbeaf1d94bbfb9b0130923cdd9f4486f8c45c61e002a39aebcdc7f1820"}'
$SOC_CLI lookup_entity --json '{"entity_id": "CI-FRA-91"}'
$SOC_CLI get_domain_report --json '{"domain": "updates.secure-assets.io"}'
$SOC_CLI block_indicator --json '{"indicator": "bd1098cbeaf1d94bbfb9b0130923cdd9f4486f8c45c61e002a39aebcdc7f1820"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-51420", "comment": "Supply chain anomaly: DeployHelper.msi (bd1098cbeaf1d94bbfb9b0130923cdd9f4486f8c45c61e002a39aebcdc7f1820) staged on CI-FRA-91 carries a Tailspin Labs code-signing certificate revoked on 2026-09-24T11:00:00Z; 9 of 72 engines flag it. Hash blocked and staged copy quarantined, vendor inquiry opened with Tailspin Labs, CI-FRA-91 and updates.secure-assets.io left in service, escalated to Tier 2, case left open."}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
Supply chain anomaly: DeployHelper.msi (bd1098cbeaf1d94bbfb9b0130923cdd9f4486f8c45c61e002a39aebcdc7f1820) staged on CI-FRA-91 carries a Tailspin Labs code-signing certificate revoked on 2026-09-24T11:00:00Z; 9 of 72 engines flag it. Hash blocked and staged copy quarantined, vendor inquiry opened with Tailspin Labs, CI-FRA-91 and updates.secure-assets.io left in service, escalated to Tier 2, case left open.
```soc_decision
{"rationale": "Reference oracle for FAM-SUPPLYCHAIN-REVOKED-CERT.", "recommended_actions": ["block_indicator", "update_case_comment"], "target_entity": "bd1098cbeaf1d94bbfb9b0130923cdd9f4486f8c45c61e002a39aebcdc7f1820", "verdict": "SUSPICIOUS"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-SUPPLYCHAIN-REVOKED-CERT-05",
  "rationale": "Reference oracle for FAM-SUPPLYCHAIN-REVOKED-CERT.",
  "recommended_actions": [
    "block_indicator",
    "update_case_comment"
  ],
  "target_entity": "bd1098cbeaf1d94bbfb9b0130923cdd9f4486f8c45c61e002a39aebcdc7f1820",
  "verdict": "SUSPICIOUS"
}
EOF_DECISION
