#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI get_domain_report --json '{"domain": "proxy-hub.mesh-edge17.com"}'
$SOC_CLI lookup_entity --json '{"entity_id": "LT-SIN-47"}'
$SOC_CLI get_ip_report --json '{"ip": "198.18.122.186"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-76801", "comment": "Suspicious but unconfirmed: LT-SIN-47 (10.12.0.99, jonas.tanaka) sent 1343 TXT queries to proxy-hub.mesh-edge17.com (198.18.122.186), which 3 of 72 engines flag and which sits on shared Northwind Tools CDN space. No process or command-and-control corroboration. Requesting packet capture and enhanced DNS monitoring, escalating to Tier 2; host left online given the quarterly close, LT-SIN-04 unaffected, case left open."}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
Suspicious but unconfirmed: LT-SIN-47 (10.12.0.99, jonas.tanaka) sent 1343 TXT queries to proxy-hub.mesh-edge17.com (198.18.122.186), which 3 of 72 engines flag and which sits on shared Northwind Tools CDN space. No process or command-and-control corroboration. Requesting packet capture and enhanced DNS monitoring, escalating to Tier 2; host left online given the quarterly close, LT-SIN-04 unaffected, case left open.
```soc_decision
{"rationale": "Reference oracle for FAM-DNS-TUNNEL-AMBIGUOUS.", "recommended_actions": ["update_case_comment"], "target_entity": "proxy-hub.mesh-edge17.com", "verdict": "SUSPICIOUS"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-DNS-TUNNEL-AMBIGUOUS-05",
  "rationale": "Reference oracle for FAM-DNS-TUNNEL-AMBIGUOUS.",
  "recommended_actions": [
    "update_case_comment"
  ],
  "target_entity": "proxy-hub.mesh-edge17.com",
  "verdict": "SUSPICIOUS"
}
EOF_DECISION
