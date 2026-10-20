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

*   `secops-soar`: `get_case_full_details`, `list_events_by_alert`, `post_case_comment`
*   `secops-mcp`: `lookup_entity`, `search_security_events`
*   `gti-mcp`: `get_ip_address_report`
*   *(Optional: Identity Provider tools like `okta-mcp.lookup_okta_user`)*

## Workflow Steps & Diagram

1.  **Receive Input & Context:** Obtain `<case_id>`, `<alert_group_identifiers>` (or `<alert_id>`), and other optional inputs. Get full case details using `secops-soar.get_case_full_details`.
2.  **Extract Key Entities:**
    *   Use `secops-soar.list_events_by_alert` for the primary alert(s) in the case.
    *   Parse events to reliably extract the primary `<user_id>`, `<source_ip>`, and relevant `<hostname>`(s). Handle cases where these might be missing.
3.  **User Context (SIEM):**
    *   Use `secops-mcp.lookup_entity` with `entity_value=<user_id>`.
    *   Record summary of user's recent activity, first/last seen, related alerts (`USER_SIEM_SUMMARY`).
4.  **Source IP Enrichment:**
    *   Execute `common_steps/enrich_ioc.md` with `IOC_VALUE=<source_ip>` and `IOC_TYPE="IP Address"`.
    *   Obtain `<gti_findings>`, `<siem_entity_summary>` (for IP), `<siem_ioc_match_status>`. Let's call these `IP_GTI_FINDINGS`, `IP_SIEM_SUMMARY`, `IP_SIEM_MATCH`.
5.  **Hostname Context (SIEM):**
    *   If `<hostname>` was extracted:
        *   Use `secops-mcp.lookup_entity` with `entity_value=<hostname>`.
        *   Record summary (`HOSTNAME_SIEM_SUMMARY`).
6.  **Recent Login Activity (SIEM):**
    *   Use `secops-mcp.search_security_events` with a refined UDM query focusing on the last 24-72 hours:
        ```udm
        metadata.event_type IN ("USER_LOGIN", "AUTH_ATTEMPT") AND (
          principal.user.userid = "<user_id>" OR
          target.user.userid = "<user_id>" OR
          src.user.userid = "<user_id>"
        )
        ```
    *   Look for patterns: logins from other unusual IPs, successful logins after failures, frequency of logins from `<source_ip>` vs. others (`LOGIN_ACTIVITY_SUMMARY`).
7.  **Check Related SOAR Cases:**
    *   Execute `common_steps/find_relevant_soar_case.md` with `SEARCH_TERMS=["<user_id>", "<source_ip>", "<hostname>"]` (include hostname if available) and `CASE_STATUS_FILTER="Opened"`.
    *   Obtain `<related_soar_cases>` (list of potentially relevant open case summaries/IDs).
    *   *Note: `list_cases` filtering by entity is limited; review results carefully.*
8.  **(Optional) Identity Provider Check:**
    *   *(If `okta-mcp` or similar tool is available, use `okta-mcp.lookup_okta_user` with `<user_id>` to check account status, recent legitimate logins, MFA methods, etc. (`IDP_SUMMARY`))*
9.  **Synthesize & Document:**
    *   Combine findings: User context (`USER_SIEM_SUMMARY`), Source IP context (`IP_GTI_FINDINGS`, `IP_SIEM_SUMMARY`, `IP_SIEM_MATCH`), Hostname context (`HOSTNAME_SIEM_SUMMARY`), Login patterns (`LOGIN_ACTIVITY_SUMMARY`), Related cases (`<related_soar_cases>`), IDP check (`IDP_SUMMARY`).
    *   Prepare comment text: `COMMENT_TEXT = "Suspicious Login Triage for <user_id> from <source_ip> (Host: <hostname>): User SIEM Summary: <user_siem_summary>. Source IP GTI: <ip_gti_findings>. Source IP SIEM: <ip_siem_summary>. Source IP IOC Match: <ip_siem_match>. Hostname SIEM: <hostname_siem_summary>. Recent Login Pattern: <login_activity_summary>. Related Open Cases: <related_soar_cases>. Optional IDP Check: <idp_summary>. Recommendation: [Close as FP/Known Activity | Escalate to Tier 2 for further investigation]"`
    *   Execute `common_steps/document_in_soar.md` with `<case_id>` and `<comment_text>`. Obtain `<comment_post_status>`.
10. **(Optional) Generate Report:**
    *   **If `<report_choice>` is "Yes":**
        *   Prepare `REPORT_CONTENT` summarizing findings (similar to `<comment_text>` but formatted for a report, including the Mermaid diagram below).
    *   **Else:** Set `<report_generation_status>` = "Skipped".
11. **Completion:** Conclude the runbook execution. Tier 1 analyst acts on the recommendation in the comment. Report generation status provided if applicable.