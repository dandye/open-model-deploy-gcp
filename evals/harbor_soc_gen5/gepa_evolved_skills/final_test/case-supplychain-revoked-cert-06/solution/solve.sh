#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI get_file_report --json '{"file_hash": "f9c8802639ae5bf2b76654cfd32738c30adc46e9f63e29690f8807ce689ca5ad"}'
$SOC_CLI lookup_entity --json '{"entity_id": "CI-TOR-27"}'
$SOC_CLI get_domain_report --json '{"domain": "updates.gateway-proxy.io"}'
$SOC_CLI block_indicator --json '{"indicator": "f9c8802639ae5bf2b76654cfd32738c30adc46e9f63e29690f8807ce689ca5ad"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-48832", "comment": "Supply chain anomaly: BuildAgentUpdate.exe (f9c8802639ae5bf2b76654cfd32738c30adc46e9f63e29690f8807ce689ca5ad) staged on CI-TOR-27 carries a Adatum code-signing certificate revoked on 2026-09-16T08:20:00Z; 9 of 72 engines flag it. Hash blocked and staged copy quarantined, vendor inquiry opened with Adatum, CI-TOR-27 and updates.gateway-proxy.io left in service, escalated to Tier 2, case left open."}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
Supply chain anomaly: BuildAgentUpdate.exe (f9c8802639ae5bf2b76654cfd32738c30adc46e9f63e29690f8807ce689ca5ad) staged on CI-TOR-27 carries a Adatum code-signing certificate revoked on 2026-09-16T08:20:00Z; 9 of 72 engines flag it. Hash blocked and staged copy quarantined, vendor inquiry opened with Adatum, CI-TOR-27 and updates.gateway-proxy.io left in service, escalated to Tier 2, case left open.
```soc_decision
{"rationale": "Reference oracle for FAM-SUPPLYCHAIN-REVOKED-CERT.", "recommended_actions": ["block_indicator", "update_case_comment"], "target_entity": "f9c8802639ae5bf2b76654cfd32738c30adc46e9f63e29690f8807ce689ca5ad", "verdict": "SUSPICIOUS"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-SUPPLYCHAIN-REVOKED-CERT-06",
  "rationale": "Reference oracle for FAM-SUPPLYCHAIN-REVOKED-CERT.",
  "recommended_actions": [
    "block_indicator",
    "update_case_comment"
  ],
  "target_entity": "f9c8802639ae5bf2b76654cfd32738c30adc46e9f63e29690f8807ce689ca5ad",
  "verdict": "SUSPICIOUS"
}
EOF_DECISION
