# Suspicious Login Alert Triage Runbook

## Objective

Guide the initial triage of common suspicious login alerts (e.g., Impossible Travel, Login from Untrusted Location, Multiple Failed Logins) for Tier 1 SOC Analysts.

## Scope

This runbook covers the initial investigation steps to gather context about a suspicious login event, focusing on user history and source IP reputation, to help determine if escalation is needed.

## Inputs

*   `<case_id>`: The relevant SOAR case ID containing the alert(s).
*   `<alert_group_identifiers>`: Relevant alert group identifiers from the SOAR case.
*   *(Optional) `<alert_id>`: Specific Alert ID if targeting a single alert.*
*   *(Optional) `<user_id>`: The user ID associated with the suspicious login (if known upfront).*
*   *(Optional) `<source_ip>`: The source IP address (if known upfront).*
*   *(Optional) `<alert_details>`: Specific details from the alert (e.g., alert name, timestamp).*

## Tools

*   `secops-soar`: `get_case_full_details`, `list_events_by_alert`
*   `secops-mcp`: `lookup_entity`, `search_security_events`
*   `gti-mcp`: `get_ip_address_report`
*   `common_steps`: `find_relevant_soar_case.md`, `document_in_soar.md`

## Workflow Steps

This runbook follows a four-stage epistemic verification sequence to triage suspicious login alerts.

### Stage A: Asset Identity, CMDB Context, & SOAR Case Correlation

1.  **Ingest and Parse:** Receive `<case_id>` and use `secops-soar.get_case_full_details` to retrieve alert data. Parse the events to extract primary entities: `<user_id>`, `<source_ip>`, and any associated `<hostname>`.
2.  **Establish Asset Context:** Query `secops-mcp.lookup_entity` for the `<user_id>` and `<hostname>`. Document the asset's business role, owner, and criticality from CMDB data.
3.  **Correlate Existing Cases:** Use `common_steps/find_relevant_soar_case.md` with search terms including `<user_id>` and `<source_ip>` to identify any pre-existing, open SOAR cases involving these entities.

### Stage B: Network Routing & Scope Verification

1.  **Enrich Source IP:** Query `gti-mcp.get_ip_address_report` using the `<source_ip>`.
2.  **Determine Network Profile:** Analyze the report to determine if the IP is part of a public, private, or reserved address space. Note its geolocation and ASN information.

### Stage C: Threat Intelligence Reputation

1.  **Assess IP Reputation:** From the `gti-mcp.get_ip_address_report` results obtained in Stage B, extract and record the GTI reputation score, any known malware or threat associations, and overall threat assessment.

### Stage D: Corroboration, Verdict, and Documentation

1.  **Analyze Login History:** Query `secops-mcp.search_security_events` for the `<user_id>` over the last 24-72 hours. Analyze the results for patterns: Is this a first-time login from this IP/region? Are there successful logins following a series of failures? How does this login compare to the user's typical activity?
2.  **Synthesize and Decide:** Combine all evidence from Stages A, B, and C with the behavioral analysis.
    *   **BENIGN:** If activity is confirmed as authorized (e.g., known travel, sanctioned corporate VPN, documented change record), prepare to close the case.
    *   **SUSPICIOUS:** If telemetry shows an unverified anomaly (e.g., impossible travel, access from a malicious IP, login patterns indicative of credential stuffing), prepare to escalate to Tier 2.
    *   **INCONCLUSIVE:** If a primary enrichment tool fails, document the failure and the results from any available local telemetry. Prepare to escalate for manual review.
3.  **Document and Conclude:** Use `common_steps/document_in_soar.md` to post a concise summary of the findings, the final verdict, and the recommended next step (e.g., "Escalate to Tier 2 for user contact and device review" or "Close as Benign; activity corresponds to known travel."). Do not close the case if the verdict is Suspicious or Inconclusive.