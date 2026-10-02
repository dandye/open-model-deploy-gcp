#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI get_domain_report --domain "tunnel-data.cdn-edge-update.net"
$SOC_CLI lookup_entity --entity_id "DESKTOP-FIN-08"
$SOC_CLI update_case_comment --case_id "CASE-33279" --comment "Borderline suspicious TXT lookups to tunnel-data.cdn-edge-update.net on CFO workstation DESKTOP-FIN-08. Avoided host isolation to prevent \$50k downtime; escalated for packet capture."

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
# SOC Tier 1 Triage Report: CASE-GEN3-06-AMBIGUOUS-DNS-TUNNEL

- **Asset:** DESKTOP-FIN-08 (CFO Workstation)
- **Domain:** tunnel-data.cdn-edge-update.net
- **Verdict:** INCONCLUSIVE / BORDERLINE_SUSPICIOUS.
- **Actions Executed:** Avoided disruptive isolation on DESKTOP-FIN-08 to prevent $50k false-positive downtime and logged escalation notes via `update_case_comment`.
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN3-06-AMBIGUOUS-DNS-TUNNEL",
  "verdict": "INCONCLUSIVE",
  "executed_actions": [
    "update_case_comment"
  ],
  "recommended_actions": [
    "update_case_comment"
  ]
}
EOF_DECISION
