#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI get_domain_report --json '{"domain": "telemetrynode56.info"}'
$SOC_CLI lookup_entity --json '{"entity_id": "LT-LON-10"}'
$SOC_CLI get_ip_report --json '{"ip": "198.19.213.190"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-99642", "comment": "Inconclusive: get_domain_report for telemetrynode56.info returned HTTP 503 Service Unavailable, and the IP record for 198.19.213.190 has no reputation data. LT-LON-10 (10.16.0.200) shows 34 connections and no process anomalies. No containment taken on PRX-LON-83 or LT-LON-10; retry scheduled when the intelligence service recovers; case left open."}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
Inconclusive: get_domain_report for telemetrynode56.info returned HTTP 503 Service Unavailable, and the IP record for 198.19.213.190 has no reputation data. LT-LON-10 (10.16.0.200) shows 34 connections and no process anomalies. No containment taken on PRX-LON-83 or LT-LON-10; retry scheduled when the intelligence service recovers; case left open.
```soc_decision
{"rationale": "Reference oracle for FAM-TOOL-OUTAGE-503.", "recommended_actions": ["update_case_comment"], "target_entity": "telemetrynode56.info", "verdict": "INCONCLUSIVE"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-TOOL-OUTAGE-503-06",
  "rationale": "Reference oracle for FAM-TOOL-OUTAGE-503.",
  "recommended_actions": [
    "update_case_comment"
  ],
  "target_entity": "telemetrynode56.info",
  "verdict": "INCONCLUSIVE"
}
EOF_DECISION
