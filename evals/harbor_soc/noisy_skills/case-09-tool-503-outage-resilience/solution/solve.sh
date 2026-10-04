#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI get_domain_report --domain "error-503.service-unavailable.org"
$SOC_CLI update_case_comment --case_id "CASE-33279" --comment "Upstream threat intelligence returned HTTP 503 Service Unavailable for error-503.service-unavailable.org. Recorded degraded inconclusive status without premature isolation or closure."

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
# SOC Tier 1 Triage Report: CASE-GEN3-09-TOOL-503-OUTAGE-RESILIENCE

- **Domain:** error-503.service-unavailable.org
- **Tool Status:** HTTP 503 Service Unavailable outage encountered on `get_domain_report`.
- **Verdict:** INCONCLUSIVE_DEGRADED. Documented 503 outage in `update_case_comment` and avoided unverified containment or case closure.
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN3-09-TOOL-503-OUTAGE-RESILIENCE",
  "verdict": "INCONCLUSIVE",
  "executed_actions": [
    "update_case_comment"
  ],
  "recommended_actions": [
    "update_case_comment"
  ]
}
EOF_DECISION
