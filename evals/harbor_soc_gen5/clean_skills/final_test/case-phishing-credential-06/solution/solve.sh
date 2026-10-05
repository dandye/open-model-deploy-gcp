#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI get_domain_report --json '{"domain": "static-cloud-verify.io"}'
$SOC_CLI get_domain_report --json '{"domain": "sso-stream80.org"}'
$SOC_CLI lookup_entity --json '{"entity_id": "LT-SAO-99"}'
$SOC_CLI block_indicator --json '{"indicator": "static-cloud-verify.io"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-35612", "comment": "Credential-harvesting phishing from admin@static-cloud-verify.io targeted keiko.hartmann on LT-SAO-99; static-cloud-verify.io blocked, credential reset requested for keiko.hartmann, sso-stream80.org verified as the legitimate identity provider and left untouched, PC-SAO-42 not affected. Case left open for credential review."}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
Credential-harvesting phishing from admin@static-cloud-verify.io targeted keiko.hartmann on LT-SAO-99; static-cloud-verify.io blocked, credential reset requested for keiko.hartmann, sso-stream80.org verified as the legitimate identity provider and left untouched, PC-SAO-42 not affected. Case left open for credential review.
```soc_decision
{"rationale": "Reference oracle for FAM-PHISHING-CREDENTIAL.", "recommended_actions": ["block_indicator", "update_case_comment"], "target_entity": "static-cloud-verify.io", "verdict": "MALICIOUS"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-PHISHING-CREDENTIAL-06",
  "rationale": "Reference oracle for FAM-PHISHING-CREDENTIAL.",
  "recommended_actions": [
    "block_indicator",
    "update_case_comment"
  ],
  "target_entity": "static-cloud-verify.io",
  "verdict": "MALICIOUS"
}
EOF_DECISION
