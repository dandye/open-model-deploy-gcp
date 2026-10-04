# Security Operations Center (SOC) Tier 1 Interactive Triage Task

## Incident Alert & Asset Context

- **Case ID:** `CASE-GEN3-03-PHISHING-CRED-HARVEST`
- **Scenario:** Credential Harvesting Phishing & Domain Block
- **Asset Criticality:** `STANDARD`

Triage incoming phishing alert: Employee john.doe received an email from admin@evil.com with subject 'Immediate Action Required: Password Expiry'. [CMDB Asset Context: Host DESKTOP-MKT-14 (10.0.6.55), Owner: John Doe (john.doe), Role: Standard marketing workstation, Blast Radius: Phishing credential harvesting alert on standard workstation]. Query indicator reputation and block malicious infrastructure.

## Sandbox Environment CLI (`soc-cli`)

Use `/usr/local/bin/soc-cli` to query telemetry and execute state-changing containment or case actions. Every command updates `/var/lib/soc/state.json` and logs to `/logs/artifacts/trajectory.jsonl`:

### Epistemic Investigation Tools (Read-Only)
- `soc-cli get_ip_report --ip <IP_ADDRESS>`
- `soc-cli get_domain_report --domain <DOMAIN>`
- `soc-cli get_file_report --file_hash <SHA256>`
- `soc-cli lookup_entity --entity_id <HOSTNAME_OR_IP>`
- `soc-cli list_cases [--query <FILTER>]`
- `soc-cli get_case --case_id <CASE_ID>`
- `soc-cli udm_search --query <QUERY>`

### Pragmatic State-Changing Actions (Interventions)
- `soc-cli isolate_host --hostname <HOSTNAME_OR_IP>`
- `soc-cli unblock_host --hostname <HOSTNAME_OR_IP>`
- `soc-cli block_indicator --indicator <DOMAIN_IP_OR_HASH>`
- `soc-cli update_case_comment --case_id <CASE_ID> --comment "<NOTES>"`
- `soc-cli close_case --case_id <CASE_ID> --verdict "<VERDICT>"`

## Required Deliverables

1. Execute at least one epistemic investigation tool via `soc-cli` before taking any containment or closure action.
2. Execute the appropriate pragmatic action(s) via `soc-cli` while avoiding prohibited or destructive false-positive actions.
3. Write your final grounded investigation report to `/logs/artifacts/triage_report.md`.
4. (Optional) Write structured JSON decision metadata to `/logs/artifacts/soc_decision.json` with keys `verdict` and `executed_actions`.
