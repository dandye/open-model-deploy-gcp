# IOC Enrichment and Triage Runbook

## Objective

Standardize autonomous agent triage for a single Indicator of Compromise (IOC) using a disciplined, four-stage evidence-gathering and response procedure.

## Scope

This runbook covers the analysis of a single IOC to determine a verdict and execute an initial response action. It applies to IP addresses, domains, and file hashes.

## Inputs

*   `<ioc_value>`: The specific IOC value.
*   `<ioc_type>`: The type of IOC (IP Address, Domain, File Hash).
*   `<asset_identifier>`: The primary host or asset involved.
*   `<case_id>`: The associated SOAR case identifier.

## Outputs

*   `<verdict>`: The final assessment (MALICIOUS, SUSPICIOUS, INCONCLUSIVE, BENIGN).
*   `<recommended_actions>`: A list of executed actions (e.g., isolate_host, update_case_comment).
*   `<documentation_status>`: Status of case documentation.

## Tools

*   `gti-mcp`: `get_ip_address_report`, `get_domain_report`, `get_file_report`
*   `secops-mcp`: `lookup_entity`
*   `secops-soar`: `list_cases`, `update_case_comment`, `isolate_host`, `block_indicator`, `close_case`

## Procedural Flow

1.  **Stage A: Asset Identity & Case Correlation**
    *   Query `secops-mcp.lookup_entity` on the `<asset_identifier>` to find its business role and criticality.
    *   Query `secops-soar.list_cases` with `<ioc_value>` to identify existing related incidents.

2.  **Stage B: Network Scope Verification**
    *   For an IP or Domain, query `gti-mcp.get_ip_address_report` or `gti-mcp.get_domain_report` to determine if the target is public, private, or reserved (e.g., RFC-5737) infrastructure.

3.  **Stage C: Threat Intelligence Reputation**
    *   Using the appropriate `gti-mcp` tool based on `<ioc_type>`, retrieve the IOC's reputation score and known malware associations.

4.  **Stage D: Synthesize, Decide, and Act**
    *   Correlate all findings.
    *   **MALICIOUS:** If high-severity malicious activity is corroborated on the alerted asset, execute `isolate_host` and/or `block_indicator`.
    *   **SUSPICIOUS:** If telemetry is anomalous but unverified, call `update_case_comment` to escalate. Do not isolate the host.
    *   **INCONCLUSIVE:** If a primary enrichment tool fails, pivot to available local telemetry (`lookup_entity`), set verdict, and call `update_case_comment`. Do not contain or close.
    *   **BENIGN:** If activity is confirmed authorized or targets documentation space, call `close_case`.
    *   Always document the verdict, findings, and actions via `update_case_comment`.