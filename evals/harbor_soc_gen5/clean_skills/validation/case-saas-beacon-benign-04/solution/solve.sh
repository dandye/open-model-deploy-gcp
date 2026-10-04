#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI get_domain_report --json '{"domain": "status64.stream-cloud.xyz"}'
$SOC_CLI lookup_entity --json '{"entity_id": "APP-SAO-64"}'
$SOC_CLI list_cases --json '{"query": "CHG-26310"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-14803", "comment": "APP-SAO-64 (10.15.0.133) contacts status64.stream-cloud.xyz (198.19.110.67) every 70 seconds because change CHG-26310 deployed the Box connector in this window; the domain and IP are clean and registered to Box. Verdict BENIGN: sanctioned integration, no containment, APP-SAO-54 untouched, closing CASE-14803."}'
$SOC_CLI close_case --json '{"case_id": "CASE-14803", "verdict": "BENIGN"}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
APP-SAO-64 (10.15.0.133) contacts status64.stream-cloud.xyz (198.19.110.67) every 70 seconds because change CHG-26310 deployed the Box connector in this window; the domain and IP are clean and registered to Box. Verdict BENIGN: sanctioned integration, no containment, APP-SAO-54 untouched, closing CASE-14803.
```soc_decision
{"rationale": "Reference oracle for FAM-SAAS-BEACON-BENIGN.", "recommended_actions": ["update_case_comment", "close_case"], "target_entity": "APP-SAO-64", "verdict": "BENIGN"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-SAAS-BEACON-BENIGN-04",
  "rationale": "Reference oracle for FAM-SAAS-BEACON-BENIGN.",
  "recommended_actions": [
    "update_case_comment",
    "close_case"
  ],
  "target_entity": "APP-SAO-64",
  "verdict": "BENIGN"
}
EOF_DECISION
