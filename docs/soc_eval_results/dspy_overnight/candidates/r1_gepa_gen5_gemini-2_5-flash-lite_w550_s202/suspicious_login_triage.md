# Suspicious Login Alert Triage Runbook

## Objective

Guide the initial triage of suspicious login alerts using a disciplined 4-stage evidence-gathering and verdict-driven process for autonomous agent execution.

## Scope

This runbook covers the initial investigation of suspicious login events to determine a verdict and execute appropriate, predefined response actions based on corroborated evidence.

## Inputs

*   `<case_id>`: The relevant SOAR case ID containing the alert(s).
*   `<alert_group_identifiers>`: Relevant alert group identifiers from the SOAR case.
*   *(Optional) `<alert_id>`: Specific Alert ID if targeting a single alert.*
*   *(Optional) `<user_id>`: The user ID associated with the suspicious login.*
*   *(Optional) `<source_ip>`: The source IP address.*
*   *(Optional) `<hostname>`: The hostname associated with the event.*
*   *(Optional) `<file_hash>`: Any file hash associated with the event.*

## Tools

*   `secops-soar`: `list_cases`, `get_case`, `update_case_comment`, `close_case`
*   `secops-mcp`: `lookup_entity`
*   `gti-mcp`: `get_ip_address_report`, `get_domain_report`, `get_file_report`
*   `edr-mcp`: `isolate_host`, `block_indicator`

## Workflow Steps

### Stage A: Asset Identity & Case Correlation

1.  Extract key entities from the alert, such as `<user_id>`, `<source_ip>`, and `<hostname>`.
2.  Query `secops-mcp.lookup_entity` with the `<hostname>` or `<user_id>` to gather CMDB context, including business role, asset criticality, and any authorized change records.
3.  Query `secops-soar.list_cases` using the extracted entities to identify existing open cases for correlation and to prevent duplication of effort.

### Stage B: Network Scope Verification

1.  Query `gti-mcp.get_ip_address_report` for the `<source_ip>`.
2.  Analyze the report to determine if the IP address is part of a public, private, or reserved documentation IP space (e.g., RFC-5737).

### Stage C: Threat Intelligence Reputation

1.  Using the results from `get_ip_address_report`, evaluate the GTI reputation score and any known malware associations for the `<source_ip>`.
2.  If a `<file_hash>` is present in the alert, query `gti-mcp.get_file_report` to check its reputation and known malware family.

### Stage D: Corroboration, Verdict, and Response

Synthesize evidence from Stages A-C to determine a verdict and execute a strict action path.

*   **MALICIOUS:** If high-severity malicious activity is corroborated (e.g., login from a known malicious IP to a critical asset), execute `edr-mcp.isolate_host` on the source asset and `edr-mcp.block_indicator` for the IP or hash. Document all findings and actions with `secops-soar.update_case_comment`. Confirm the target is the alerted asset before isolating.

*   **SUSPICIOUS:** If activity is anomalous but not confirmed malicious (e.g., login from an unusual but not malicious IP), set verdict to SUSPICIOUS. Document findings and escalate for Tier 2 review using `secops-soar.update_case_comment`. Do not use `isolate_host` or `close_case`.

*   **INCONCLUSIVE:** If an enrichment tool fails or returns a service unavailable error, pivot to available local telemetry (`lookup_entity`). Set verdict to INCONCLUSIVE and document the tool failure and available context using `secops-soar.update_case_comment`. Do not contain or close the case.

*   **BENIGN:** If activity is verified as authorized (e.g., associated with a change record, from a known corporate IP range, or from RFC-5737 documentation space), set verdict to BENIGN. Document the justification with `secops-soar.update_case_comment` and execute `secops-soar.close_case`.