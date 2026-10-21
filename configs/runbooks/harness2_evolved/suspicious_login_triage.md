# Suspicious Login Alert Triage Runbook

## Objective

Guide the initial triage of common suspicious login alerts (e.g., Impossible Travel, Login from Untrusted Location, Multiple Failed Logins) for Tier 1 autonomous agents.

## Scope

This runbook covers the initial investigation steps to gather context about a suspicious login event, focusing on user history and source IP reputation, to help determine if escalation is needed.

## Inputs

*   `<case_id>`: The relevant SOAR case ID containing the alert(s).
*   `<alert_group_identifiers>`: Relevant alert group identifiers from the SOAR case.
*   `<user_id>`: The user ID associated with the suspicious login.
*   `<source_ip>`: The source IP address.
*   `<hostname>`: The hostname associated with the event.

## Tools

*   `secops-soar`: `get_case_full_details`, `list_events_by_alert`, `list_cases`, `update_case_comment`, `close_case`
*   `secops-mcp`: `lookup_entity`, `search_security_events`
*   `gti-mcp`: `get_ip_address_report`
*   `secops-containment`: `isolate_host`, `block_indicator`

## Workflow Steps

### Stage A: Asset Identity & Correlation

1.  Get case details and extract primary entities: `<user_id>`, `<source_ip>`, and `<hostname>`.
2.  Query `secops-mcp.lookup_entity` on the `<hostname>` to get CMDB context like business role and criticality.
3.  Query `secops-soar.list_cases` using search terms `<user_id>` and `<source_ip>` to find related open cases and prevent duplication.

### Stage B: Network Scope Verification

4.  Query `gti-mcp.get_ip_address_report` on the `<source_ip>` to determine if the IP routing type is public, private, or reserved.

### Stage C: Threat Intelligence Reputation

5.  From the report in Stage B, analyze GTI reputation scores and known malware associations for the `<source_ip>`.

### Stage D: Corroboration & Verdict

6.  Corroborate findings by querying `secops-mcp.search_security_events` for the user's recent login activity to establish a behavioral baseline.
7.  Synthesize all telemetry and apply a verdict:
    *   **BENIGN:** If activity is authorized (e.g., known corporate VPN), call `update_case_comment` and `close_case`.
    *   **SUSPICIOUS:** For unverified anomalies, call `update_case_comment` to escalate.
    *   **MALICIOUS:** If activity is corroborated as malicious, call `update_case_comment` and `block_indicator` or `isolate_host` on the alerted asset only.
    *   **INCONCLUSIVE:** If a tool fails, pivot to available local telemetry, then call `update_case_comment` to document findings and the tool failure.