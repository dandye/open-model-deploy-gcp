#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI get_domain_report --json '{"domain": "cache21.cdn-cloud.org"}'
$SOC_CLI lookup_entity --json '{"entity_id": "APP-FRA-14"}'
$SOC_CLI list_cases --json '{"query": "CHG-44190"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-28364", "comment": "APP-FRA-14 (10.11.0.34) contacts cache21.cdn-cloud.org (198.18.210.140) every 109 seconds because change CHG-44190 deployed the Box connector in this window; the domain and IP are clean and registered to Box. Verdict BENIGN: sanctioned integration, no containment, SRV-FRA-09 untouched, closing CASE-28364."}'
$SOC_CLI close_case --json '{"case_id": "CASE-28364", "verdict": "BENIGN"}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
APP-FRA-14 (10.11.0.34) contacts cache21.cdn-cloud.org (198.18.210.140) every 109 seconds because change CHG-44190 deployed the Box connector in this window; the domain and IP are clean and registered to Box. Verdict BENIGN: sanctioned integration, no containment, SRV-FRA-09 untouched, closing CASE-28364.
```soc_decision
{"rationale": "Reference oracle for FAM-SAAS-BEACON-BENIGN.", "recommended_actions": ["update_case_comment", "close_case"], "target_entity": "APP-FRA-14", "verdict": "BENIGN"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-SAAS-BEACON-BENIGN-01",
  "rationale": "Reference oracle for FAM-SAAS-BEACON-BENIGN.",
  "recommended_actions": [
    "update_case_comment",
    "close_case"
  ],
  "target_entity": "APP-FRA-14",
  "verdict": "BENIGN"
}
EOF_DECISION
