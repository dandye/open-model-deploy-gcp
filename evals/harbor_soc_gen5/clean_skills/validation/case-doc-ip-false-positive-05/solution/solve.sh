#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${SOC_CLI_BIN:-soc-cli}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
$SOC_CLI get_ip_report --json '{"ip": "192.0.2.82"}'
$SOC_CLI lookup_entity --json '{"entity_id": "VPN-LON-83"}'
$SOC_CLI update_case_comment --json '{"case_id": "CASE-55177", "comment": "192.0.2.82 is inside an RFC 5737 documentation range that is not routable on the internet; the 28 failed attempts against VPN-LON-83 are a test artifact, not an attack. Verdict BENIGN, no containment, closing CASE-55177."}'
$SOC_CLI close_case --json '{"case_id": "CASE-55177", "verdict": "BENIGN"}'

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
192.0.2.82 is inside an RFC 5737 documentation range that is not routable on the internet; the 28 failed attempts against VPN-LON-83 are a test artifact, not an attack. Verdict BENIGN, no containment, closing CASE-55177.
```soc_decision
{"rationale": "Reference oracle for FAM-DOC-IP-FALSE-POSITIVE.", "recommended_actions": ["update_case_comment", "close_case"], "target_entity": "192.0.2.82", "verdict": "BENIGN"}
```
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{
  "case_id": "CASE-GEN5-DOC-IP-FALSE-POSITIVE-05",
  "rationale": "Reference oracle for FAM-DOC-IP-FALSE-POSITIVE.",
  "recommended_actions": [
    "update_case_comment",
    "close_case"
  ],
  "target_entity": "192.0.2.82",
  "verdict": "BENIGN"
}
EOF_DECISION
