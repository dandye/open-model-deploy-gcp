#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI get_domain_report --json '{"domain": "assets47.mesh-cloud.org"}'
$SOC_CLI lookup_entity --json '{"entity_id": "APP-SAO-97"}'
$SOC_CLI list_cases --json '{"query": "CHG-97787"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-17475", "comment": "APP-SAO-97 (10.15.0.135) contacts assets47.mesh-cloud.org (198.19.100.155) every 72 seconds because change CHG-97787 deployed the Slack connector in this window; the domain and IP are clean and registered to Slack. Verdict BENIGN: sanctioned integration, no containment, APP-SAO-41 untouched, closing CASE-17475."}'
$SOC_CLI close_case --json '{"case_id": "CASE-17475", "verdict": "BENIGN"}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
APP-SAO-97 (10.15.0.135) contacts assets47.mesh-cloud.org (198.19.100.155) every 72 seconds because change CHG-97787 deployed the Slack connector in this window; the domain and IP are clean and registered to Slack. Verdict BENIGN: sanctioned integration, no containment, APP-SAO-41 untouched, closing CASE-17475.
```soc_decision
{"rationale": "Reference oracle for FAM-SAAS-BEACON-BENIGN.", "recommended_actions": ["update_case_comment", "close_case"], "target_entity": "APP-SAO-97", "verdict": "BENIGN"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-SAAS-BEACON-BENIGN-02",
  "rationale": "Reference oracle for FAM-SAAS-BEACON-BENIGN.",
  "recommended_actions": [
    "update_case_comment",
    "close_case"
  ],
  "target_entity": "APP-SAO-97",
  "verdict": "BENIGN"
}
EOF_DECISION
