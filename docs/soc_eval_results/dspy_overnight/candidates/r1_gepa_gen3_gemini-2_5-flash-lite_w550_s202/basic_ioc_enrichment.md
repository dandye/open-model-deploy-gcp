# Basic IOC Enrichment Runbook

## Objective

Standardize the initial enrichment process for a single Indicator of Compromise (IOC) identified in an alert or case, suitable for Tier 1 SOC Analysts.

## Scope

This runbook covers fundamental enrichment steps using readily available GTI and SIEM lookup tools, plus limited SIEM event searching. It aims to provide quick, actionable context to aid in the decision to close or escalate.

## Inputs

*   `<ioc_value>`: The specific IOC value (e.g., "198.51.100.10", "evil-domain.com", "abcdef123456...", "http://bad.url/path").
*   `<ioc_type>`: The type of IOC (e.g., "IP Address", "Domain", "File Hash", "URL").
*   *(Optional) `<alert_group_identifiers>`: Relevant alert group identifiers if needed for context in SOAR actions.*
*   *(Optional) `<case_id>`: Relevant case ID if documentation is desired.*
*   *(Optional) `<siem_search_hours>`: Lookback period for SIEM event search (default: 24).*

## Outputs

*   `<gti_findings>`: Summary of key findings from the relevant GTI report.
*   `<gti_relationships>`: Summary of key related entities found via GTI pivoting.
*   `<siem_entity_summary>`: Summary from the SIEM entity lookup.
*   `<siem_ioc_match_status>`: Boolean or indicator (Yes/No) if the IOC was found in recent SIEM IOC matches.
*   `<siem_recent_events>`: Summary of recent SIEM events involving the IOC.
*   `<found_cases>`: List of potentially related open SOAR cases.
*   `<assessment>`: Analyst's initial risk assessment (e.g., Low/Medium/High/Informational).
*   `<recommendation>`: Suggested next steps (e.g., Escalate, Monitor, Close FP, Trigger Containment).
*   `<documentation_status>`: Status of documentation attempt in SOAR.
*   `<report_generation_status>`: Status of optional report generation.

## Tools

*   `gti-mcp`: `get_ip_address_report`, `get_domain_report`, `get_file_report`, `get_url_report`, `get_entities_related_to_a_file`, `get_entities_related_to_a_domain`, `get_entities_related_to_an_ip_address`, `get_entities_related_to_an_url`
*   `secops-mcp`: `lookup_entity`, `get_ioc_matches`, `search_security_events`
*   `secops-soar`: `list_cases`, `post_case_comment`

## Workflow Steps

1.  **Stage A: Asset Identity, CMDB Context, & SOAR Case Correlation**
    *   Query `secops-mcp.lookup_entity` on the alerted asset to determine its business role, criticality, and any authorized change records (CHG-...).
    *   Query `secops-soar.list_cases` with the `<ioc_value>` and asset hostname to identify any existing or related open cases. Cite any found case ID in findings.

2.  **Stage B: Network Routing & Scope Verification**
    *   Based on `<ioc_type>`, execute `gti-mcp.get_ip_address_report` or `gti-mcp.get_domain_report`.
    *   Analyze the report to determine if the infrastructure is public, private, or reserved documentation space (e.g., RFC-5737).

3.  **Stage C: Threat Intelligence Reputation**
    *   Using the report from the previous stage, or by executing `gti-mcp.get_file_report` for a file hash, evaluate the GTI reputation score and any known malware associations for the `<ioc_value>`.

4.  **Stage D: Synthesize, Determine Verdict, and Recommend Action**
    *   Correlate all telemetry from Stages A, B, and C to determine a final verdict and execute the corresponding actions. Do not perform redundant tool calls.
    *   **MALICIOUS:** If high-severity malicious activity is corroborated by GTI and the target is the alerted asset, set verdict to MALICIOUS. Recommend `isolate_host` and/or `block_indicator`.
    *   **SUSPICIOUS:** If telemetry shows an unverified anomaly (e.g., ambiguous GTI data, duplicate SOAR cases), set verdict to SUSPICIOUS. Recommend `update_case_comment` to escalate. Only recommend `block_indicator` if a revoked-certificate binary hash is confirmed. Do not recommend `isolate_host` or `close_case`.
    *   **INCONCLUSIVE:** If an enrichment tool is unavailable, pivot once to `secops-mcp.lookup_entity` for local context. If still inconclusive, set verdict to INCONCLUSIVE. Recommend `update_case_comment` with findings. Do not recommend `isolate_host`, `block_indicator`, or `close_case`.
    *   **BENIGN:** If activity is verified as authorized (e.g., sanctioned scanner, SaaS with a CHG- record) or targets documentation space, set verdict to BENIGN. Recommend `update_case_comment` and `close_case`. Do not recommend `isolate_host` or `block_indicator`.