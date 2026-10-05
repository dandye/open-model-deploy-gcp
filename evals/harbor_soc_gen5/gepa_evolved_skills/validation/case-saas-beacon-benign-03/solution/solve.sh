#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI get_domain_report --json '{"domain": "metrics31.status-cloud.info"}'
$SOC_CLI lookup_entity --json '{"entity_id": "APP-LON-60"}'
$SOC_CLI list_cases --json '{"query": "CHG-99478"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-17750", "comment": "APP-LON-60 (10.16.0.196) contacts metrics31.status-cloud.info (198.19.84.202) every 252 seconds because change CHG-99478 deployed the Box connector in this window; the domain and IP are clean and registered to Box. Verdict BENIGN: sanctioned integration, no containment, APP-LON-62 untouched, closing CASE-17750."}'
$SOC_CLI close_case --json '{"case_id": "CASE-17750", "verdict": "BENIGN"}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
APP-LON-60 (10.16.0.196) contacts metrics31.status-cloud.info (198.19.84.202) every 252 seconds because change CHG-99478 deployed the Box connector in this window; the domain and IP are clean and registered to Box. Verdict BENIGN: sanctioned integration, no containment, APP-LON-62 untouched, closing CASE-17750.
```soc_decision
{"rationale": "Reference oracle for FAM-SAAS-BEACON-BENIGN.", "recommended_actions": ["update_case_comment", "close_case"], "target_entity": "APP-LON-60", "verdict": "BENIGN"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-SAAS-BEACON-BENIGN-03",
  "rationale": "Reference oracle for FAM-SAAS-BEACON-BENIGN.",
  "recommended_actions": [
    "update_case_comment",
    "close_case"
  ],
  "target_entity": "APP-LON-60",
  "verdict": "BENIGN"
}
EOF_DECISION
