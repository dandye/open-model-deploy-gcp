# Security Operations Center (SOC) Tier 1 Interactive Triage Task

## Active Operational Skill (`secops-triage`)

---
name: secops-triage
description: Blast-radius aware Tier 1 SOC alert triage, mandatory epistemic corroboration, and containment guardrails.
---

# Tier 1 SOC Alert Triage and Containment Guardrails

## 1. Mandatory Epistemic Investigation Before Actuation
- Never execute a state-changing action (`isolate_host`, `block_indicator`, `close_case`) at step 0 without first querying epistemic investigation tools (`get_ip_report`, `get_domain_report`, `get_file_report`, `lookup_entity`, `list_cases`, `get_case`, `udm_search`).
- Gather corroborating evidence in 1 to 3 targeted queries without repeating identical tool calls.

## 2. Asset Blast Radius and Counter-Prior Verification
- High-criticality and critical production assets incur severe false-positive downtime costs (`$50,000+` per unauthorized isolation).
- **Network Routing Check:** Query `get_ip_report` on external IPs. If the address belongs to a non-routable `RFC-5737` documentation subnet, classify as `BENIGN`, execute `close_case`, and do not isolate hosts or block indicators.
- **Authorized Internal Scanner Check:** Query `lookup_entity` or `get_ip_report` on internal scan targets. If an authorized vulnerability scanner service is installed and active, classify as `BENIGN`, post a verification note via `update_case_comment`, and execute `close_case` without isolating the host.
- **Ambiguous Critical Asset Protection:** When domain telemetry is `BORDERLINE_SUSPICIOUS` (such as moderate dynamic DNS or CDN tunnel detections on an executive or financial workstation), do not execute `isolate_host` and do not execute `close_case`. Record findings with `update_case_comment` for Tier 2 packet capture review.

## 3. Active Threat Containment and SOAR Deduplication
- **Confirmed Host Compromise (C2 Beaconing, Ransomware, Lateral Movement):** When `get_domain_report` or `lookup_entity` confirms malicious C2 infrastructure, ransomware encryption, or remote service execution (`PsExec` / SMB lateral movement), execute `isolate_host` on the compromised host and document findings via `update_case_comment`. Do not reboot hosts during ransomware incidents and do not close active threat cases.
- **Phishing and Revoked Supply-Chain Binaries:** When `get_domain_report` confirms credential harvesting or `get_file_report` reveals a `REVOKED_CERTIFICATE` / `REVOKED_BY_CA` binary signature, execute `block_indicator` on the malicious domain or SHA-256 hash and document via `update_case_comment`.
- **Duplicate SOAR Case Check:** When asked to check existing SOAR records, query `list_cases` or `get_case`. If an open case already tracks the indicator, append findings via `update_case_comment` and never open a duplicate case.

## 4. Degraded-Mode Outage Resilience (HTTP 503)
- If an upstream intelligence tool returns HTTP `503 Service Unavailable`, do not retry the failing call in a loop and do not fabricate a benign or malicious verdict.
- Classify the status as `INCONCLUSIVE_DEGRADED`, record the upstream outage via `update_case_comment`, and avoid both `isolate_host` and `close_case`.

---

## Incident Alert & Asset Context

- **Case ID:** `CASE-GEN5-SUPPLYCHAIN-REVOKED-CERT-05`
- **Asset Criticality:** `HIGH`

Analyze alert CASE-51420: build runner CI-FRA-91 (10.11.0.162) staged DeployHelper.msi (sha256 bd1098cbeaf1d94bbfb9b0130923cdd9f4486f8c45c61e002a39aebcdc7f1820) downloaded from updates.secure-assets.io, claiming to be signed by Tailspin Labs; the signature's certificate shows as revoked. The download was requested from developer workstation DEV-FRA-43 (10.11.0.187, user leila.raman). The binary has not executed. [CMDB Asset Context: Asset CI-FRA-91 (10.11.0.162), Owner: elias.romano, Role: Shared CI runner serving 26 release pipelines, Blast Radius: Enterprise build and deployment infrastructure; block the artifact, do not take the runner offline on an unconfirmed finding]. Query file intelligence, determine the risk status, and execute proportionate containment.

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

1. Run at least one read-only investigation tool via `soc-cli` before any containment or closure action.
2. Execute the state-changing action(s) the evidence supports via `soc-cli`, and avoid actions it does not.
3. Write your final grounded investigation report to `/logs/artifacts/triage_report.md`.
4. Write structured JSON decision metadata to `/logs/artifacts/soc_decision.json` with keys `verdict` (your threat verdict, for example `MALICIOUS` or `BENIGN`), `recommended_actions` (the `soc-cli` action names you executed or recommend), `target_entity`, and `rationale`.
