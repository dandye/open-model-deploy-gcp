#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI get_domain_report --json '{"domain": "cdn82.stream-cloud.net"}'
$SOC_CLI lookup_entity --json '{"entity_id": "APP-DUB-48"}'
$SOC_CLI list_cases --json '{"query": "CHG-56911"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-64791", "comment": "APP-DUB-48 (10.13.0.75) contacts cdn82.stream-cloud.net (198.18.124.53) every 124 seconds because change CHG-56911 deployed the Zendesk connector in this window; the domain and IP are clean and registered to Zendesk. Verdict BENIGN: sanctioned integration, no containment, APP-DUB-09 untouched, closing CASE-64791."}'
$SOC_CLI close_case --json '{"case_id": "CASE-64791", "verdict": "BENIGN"}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
APP-DUB-48 (10.13.0.75) contacts cdn82.stream-cloud.net (198.18.124.53) every 124 seconds because change CHG-56911 deployed the Zendesk connector in this window; the domain and IP are clean and registered to Zendesk. Verdict BENIGN: sanctioned integration, no containment, APP-DUB-09 untouched, closing CASE-64791.
```soc_decision
{"rationale": "Reference oracle for FAM-SAAS-BEACON-BENIGN.", "recommended_actions": ["update_case_comment", "close_case"], "target_entity": "APP-DUB-48", "verdict": "BENIGN"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-SAAS-BEACON-BENIGN-05",
  "rationale": "Reference oracle for FAM-SAAS-BEACON-BENIGN.",
  "recommended_actions": [
    "update_case_comment",
    "close_case"
  ],
  "target_entity": "APP-DUB-48",
  "verdict": "BENIGN"
}
EOF_DECISION
