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

## Workflow Steps & Diagram

1.  **Receive Input:** Obtain `<ioc_value>`, `<ioc_type>`, and optional inputs like `<case_id>`, `<alert_group_identifiers>`, `<siem_search_hours>` (default 24).
2.  **Enrich IOC (GTI + SIEM Lookup):** Execute `common_steps/enrich_ioc.md` with `<ioc_value>` and `<ioc_type>`. Obtain `<gti_findings>`, `<siem_entity_summary>`, `<siem_ioc_match_status>`.
3.  **Fetch Key GTI Relationships:**
    *   Determine relevant relationships based on `<ioc_type>` (e.g., for File Hash: `["contacted_domains", "contacted_ips"]`; for Domain: `["resolutions"]`). Let this be `REL_LIST`.
    *   Execute `common_steps/pivot_on_ioc_gti.md` with `<ioc_value>`, `<ioc_type>`, and `RELATIONSHIP_NAMES=REL_LIST`. Obtain `<gti_relationships>`.
4.  **Search Recent SIEM Events:**
    *   Construct a basic query for `secops-mcp.search_security_events` targeting `<ioc_value>` (e.g., `text="<ioc_value>"`).
    *   Execute the search with `hours_back=<siem_search_hours>`.
    *   Store a summary of findings (e.g., count, key event types, involved hosts/users) in `<siem_recent_events>`.
5.  **Search Relevant SOAR Cases:**
    *   Execute `common_steps/find_relevant_soar_case.md` with `SEARCH_TERMS=["<ioc_value>"]` and `CASE_STATUS_FILTER="Opened"`.
    *   Obtain `<relevant_case_ids>` and `<relevant_case_summaries>`. Let `<found_cases>` = `<relevant_case_summaries>` (or `<relevant_case_ids>` if summaries aren't needed/available).
6.  **Synthesize Findings & Assess Risk:**
    *   Combine all findings: `<gti_findings>`, `<gti_relationships>`, `<siem_entity_summary>`, `<siem_ioc_match_status>`, `<siem_recent_events>`, `<found_cases>`.
    *   Guide the analyst (via output prompt or internal logic) to make an initial risk assessment (`<assessment>`) based on the combined data (e.g., GTI reputation, SIEM activity presence/volume, relation to existing cases).
    *   Suggest potential next steps (`<recommendation>`) based on the assessment (e.g., Escalate, Monitor, Close FP, Trigger IOC Containment).
7.  **Conditional Documentation:**
    *   **If `<case_id>` was provided:**
        *   Prepare `COMMENT_TEXT` summarizing all findings, the assessment, and recommendation (e.g., "Basic IOC Enrichment for `<ioc_value>` (`<ioc_type>`): GTI Rep: [...], GTI Relations: [...], SIEM Summary: [...], SIEM Match: [...], Recent Events: [...], Related Cases: [...]. Assessment: `<assessment>`. Recommendation: `<recommendation>`.").
        *   Execute `common_steps/document_in_soar.md` with `CASE_ID=<case_id>` and `COMMENT_TEXT`. Obtain `<documentation_status>`.
    *   **Else (`<case_id>` not provided):** Set `<documentation_status>` = "Skipped (No Case ID)".
8.  **Optional Report Generation:**
    *   **If `<report_choice>` is "Yes":**
        *   Prepare `REPORT_CONTENT` similar to `COMMENT_TEXT` but formatted for a standalone report.
    *   **Else:** Set `<report_generation_status>` = "Skipped".
9.  **Completion:** Conclude the runbook execution. Present the key findings, assessment, recommendation, documentation status, and report generation status to the analyst.