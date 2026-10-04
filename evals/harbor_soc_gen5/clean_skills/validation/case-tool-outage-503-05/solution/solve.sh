#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI get_domain_report --json '{"domain": "signalbeacon16.com"}'
$SOC_CLI lookup_entity --json '{"entity_id": "PC-LON-08"}'
$SOC_CLI get_ip_report --json '{"ip": "198.18.68.152"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-20662", "comment": "Inconclusive: get_domain_report for signalbeacon16.com returned HTTP 503 Service Unavailable, and the IP record for 198.18.68.152 has no reputation data. PC-LON-08 (10.16.0.58) shows 32 connections and no process anomalies. No containment taken on PRX-LON-14 or PC-LON-08; retry scheduled when the intelligence service recovers; case left open."}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
Inconclusive: get_domain_report for signalbeacon16.com returned HTTP 503 Service Unavailable, and the IP record for 198.18.68.152 has no reputation data. PC-LON-08 (10.16.0.58) shows 32 connections and no process anomalies. No containment taken on PRX-LON-14 or PC-LON-08; retry scheduled when the intelligence service recovers; case left open.
```soc_decision
{"rationale": "Reference oracle for FAM-TOOL-OUTAGE-503.", "recommended_actions": ["update_case_comment"], "target_entity": "signalbeacon16.com", "verdict": "INCONCLUSIVE"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-TOOL-OUTAGE-503-05",
  "rationale": "Reference oracle for FAM-TOOL-OUTAGE-503.",
  "recommended_actions": [
    "update_case_comment"
  ],
  "target_entity": "signalbeacon16.com",
  "verdict": "INCONCLUSIVE"
}
EOF_DECISION
