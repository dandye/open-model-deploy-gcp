#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI get_domain_report --json '{"domain": "telemetry-link-verify.org"}'
$SOC_CLI get_domain_report --json '{"domain": "sso-assets15.net"}'
$SOC_CLI lookup_entity --json '{"entity_id": "WKS-LON-29"}'
$SOC_CLI block_indicator --json '{"indicator": "telemetry-link-verify.org"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-26427", "comment": "Credential-harvesting phishing from admin@telemetry-link-verify.org targeted rafael.mensah on WKS-LON-29; telemetry-link-verify.org blocked, credential reset requested for rafael.mensah, sso-assets15.net verified as the legitimate identity provider and left untouched, LT-LON-73 not affected. Case left open for credential review."}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
Credential-harvesting phishing from admin@telemetry-link-verify.org targeted rafael.mensah on WKS-LON-29; telemetry-link-verify.org blocked, credential reset requested for rafael.mensah, sso-assets15.net verified as the legitimate identity provider and left untouched, LT-LON-73 not affected. Case left open for credential review.
```soc_decision
{"rationale": "Reference oracle for FAM-PHISHING-CREDENTIAL.", "recommended_actions": ["block_indicator", "update_case_comment"], "target_entity": "telemetry-link-verify.org", "verdict": "MALICIOUS"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-PHISHING-CREDENTIAL-05",
  "rationale": "Reference oracle for FAM-PHISHING-CREDENTIAL.",
  "recommended_actions": [
    "block_indicator",
    "update_case_comment"
  ],
  "target_entity": "telemetry-link-verify.org",
  "verdict": "MALICIOUS"
}
EOF_DECISION
