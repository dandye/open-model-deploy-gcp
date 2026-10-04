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
