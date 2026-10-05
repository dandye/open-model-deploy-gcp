#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI get_domain_report --json '{"domain": "link-signal.portal-edge60.info"}'
$SOC_CLI lookup_entity --json '{"entity_id": "LT-LON-80"}'
$SOC_CLI get_ip_report --json '{"ip": "198.18.186.29"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-22080", "comment": "Suspicious but unconfirmed: LT-LON-80 (10.16.0.213, freya.brandt) sent 782 TXT queries to link-signal.portal-edge60.info (198.18.186.29), which 3 of 72 engines flag and which sits on shared Adatum CDN space. No process or command-and-control corroboration. Requesting packet capture and enhanced DNS monitoring, escalating to Tier 2; host left online given the quarterly close, LT-LON-33 unaffected, case left open."}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
Suspicious but unconfirmed: LT-LON-80 (10.16.0.213, freya.brandt) sent 782 TXT queries to link-signal.portal-edge60.info (198.18.186.29), which 3 of 72 engines flag and which sits on shared Adatum CDN space. No process or command-and-control corroboration. Requesting packet capture and enhanced DNS monitoring, escalating to Tier 2; host left online given the quarterly close, LT-LON-33 unaffected, case left open.
```soc_decision
{"rationale": "Reference oracle for FAM-DNS-TUNNEL-AMBIGUOUS.", "recommended_actions": ["update_case_comment"], "target_entity": "link-signal.portal-edge60.info", "verdict": "SUSPICIOUS"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-DNS-TUNNEL-AMBIGUOUS-06",
  "rationale": "Reference oracle for FAM-DNS-TUNNEL-AMBIGUOUS.",
  "recommended_actions": [
    "update_case_comment"
  ],
  "target_entity": "link-signal.portal-edge60.info",
  "verdict": "SUSPICIOUS"
}
EOF_DECISION
