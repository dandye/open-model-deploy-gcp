#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI list_cases --json '{"query": "198.18.97.87"}'
$SOC_CLI get_case --json '{"case_id": "CASE-22642"}'
$SOC_CLI lookup_entity --json '{"entity_id": "PC-SYD-18"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-22642", "comment": "Duplicate correlation: new alert CASE-39225 (PC-SYD-18 at 10.17.0.134 to 198.18.97.87, 12 connections at 2026-09-03T20:08:00Z) matches the open Tier 2 investigation in CASE-22642; appended here instead of creating a new case. PC-SYD-49 remains clear."}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
Duplicate correlation: new alert CASE-39225 (PC-SYD-18 at 10.17.0.134 to 198.18.97.87, 12 connections at 2026-09-03T20:08:00Z) matches the open Tier 2 investigation in CASE-22642; appended here instead of creating a new case. PC-SYD-49 remains clear.
```soc_decision
{"rationale": "Reference oracle for FAM-DUPLICATE-CASE.", "recommended_actions": ["update_case_comment"], "target_entity": "CASE-22642", "verdict": "SUSPICIOUS"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-DUPLICATE-CASE-06",
  "rationale": "Reference oracle for FAM-DUPLICATE-CASE.",
  "recommended_actions": [
    "update_case_comment"
  ],
  "target_entity": "CASE-22642",
  "verdict": "SUSPICIOUS"
}
EOF_DECISION
