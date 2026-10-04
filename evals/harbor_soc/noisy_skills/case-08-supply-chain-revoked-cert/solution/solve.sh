#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI get_file_report --file_hash "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90"
$SOC_CLI block_indicator --indicator "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90"
$SOC_CLI update_case_comment --case_id "CASE-33279" --comment "Blocked supply-chain binary invoice_update.exe (a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90) signed with revoked Acme Corp certificate."

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
# SOC Tier 1 Triage Report: CASE-GEN3-08-SUPPLY-CHAIN-REVOKED-CERT

- **Binary:** invoice_update.exe
- **SHA-256:** a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90
- **Signer Status:** Revoked Acme Corp code-signing certificate (`REVOKED_BY_CA`).
- **Verdict:** MALICIOUS supply-chain anomaly. Blocked hash via `block_indicator` and documented via `update_case_comment`.
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN3-08-SUPPLY-CHAIN-REVOKED-CERT",
  "verdict": "MALICIOUS",
  "executed_actions": [
    "block_indicator",
    "update_case_comment"
  ],
  "recommended_actions": [
    "block_indicator",
    "update_case_comment"
  ]
}
EOF_DECISION
