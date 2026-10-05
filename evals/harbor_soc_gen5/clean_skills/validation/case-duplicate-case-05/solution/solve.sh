#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI list_cases --json '{"query": "198.18.241.119"}'
$SOC_CLI get_case --json '{"case_id": "CASE-96698"}'
$SOC_CLI lookup_entity --json '{"entity_id": "PC-SIN-23"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-96698", "comment": "Duplicate correlation: new alert CASE-67688 (PC-SIN-23 at 10.12.0.104 to 198.18.241.119, 6 connections at 2026-09-28T04:25:00Z) matches the open Tier 2 investigation in CASE-96698; appended here instead of creating a new case. LT-SIN-66 remains clear."}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
Duplicate correlation: new alert CASE-67688 (PC-SIN-23 at 10.12.0.104 to 198.18.241.119, 6 connections at 2026-09-28T04:25:00Z) matches the open Tier 2 investigation in CASE-96698; appended here instead of creating a new case. LT-SIN-66 remains clear.
```soc_decision
{"rationale": "Reference oracle for FAM-DUPLICATE-CASE.", "recommended_actions": ["update_case_comment"], "target_entity": "CASE-96698", "verdict": "SUSPICIOUS"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-DUPLICATE-CASE-05",
  "rationale": "Reference oracle for FAM-DUPLICATE-CASE.",
  "recommended_actions": [
    "update_case_comment"
  ],
  "target_entity": "CASE-96698",
  "verdict": "SUSPICIOUS"
}
EOF_DECISION
