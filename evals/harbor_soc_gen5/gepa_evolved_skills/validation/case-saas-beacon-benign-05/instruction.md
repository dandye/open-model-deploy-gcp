# Security Operations Center (SOC) Tier 1 Interactive Triage Task

## Security Operations GEPA Evolved Runbooks

Four runbooks follow. Pick whichever fits the alert; none is marked as the right one.

### Runbook: basic_ioc_enrichment.md

# Basic IOC Enrichment Runbook

## Objective

Standardize the initial enrichment process for a single Indicator of Compromise (IOC) identified in an alert or case, suitable for Tier 1 SOC Analysts.

## Scope

This runbook covers fundamental enrichment steps using readily available GTI and SIEM lookup tools, plus limited SIEM event searching. It aims to provide quick, actionable context to aid in the decision to close or escalate.

## Inputs

*   `${IOC_VALUE}`: The specific IOC value (e.g., "198.51.100.10", "evil-domain.com", "abcdef123456...", "http://bad.url/path").
*   `${IOC_TYPE}`: The type of IOC (e.g., "IP Address", "Domain", "File Hash", "URL").
*   *(Optional) `${ALERT_GROUP_IDENTIFIERS}`: Relevant alert group identifiers if needed for context in SOAR actions.*
*   *(Optional) `${CASE_ID}`: Relevant case ID if documentation is desired.*
*   *(Optional) `${SIEM_SEARCH_HOURS}`: Lookback period for SIEM event search (default: 24).*

## Outputs

*   `${GTI_FINDINGS}`: Summary of key findings from the relevant GTI report.
*   `${GTI_RELATIONSHIPS}`: Summary of key related entities found via GTI pivoting.
*   `${SIEM_ENTITY_SUMMARY}`: Summary from the SIEM entity lookup.
*   `${SIEM_IOC_MATCH_STATUS}`: Boolean or indicator (Yes/No) if the IOC was found in recent SIEM IOC matches.
*   `${SIEM_RECENT_EVENTS}`: Summary of recent SIEM events involving the IOC.
*   `${FOUND_CASES}`: List of potentially related open SOAR cases.
*   `${ASSESSMENT}`: Analyst's initial risk assessment (e.g., Low/Medium/High/Informational).
*   `${RECOMMENDATION}`: Suggested next steps (e.g., Escalate, Monitor, Close FP, Trigger Containment).
*   `${DOCUMENTATION_STATUS}`: Status of documentation attempt in SOAR.
*   `${REPORT_GENERATION_STATUS}`: Status of optional report generation.

## Tools

*   `gti-mcp`: `get_ip_address_report`, `get_domain_report`, `get_file_report`, `get_url_report`, `get_entities_related_to_a_file`, `get_entities_related_to_a_domain`, `get_entities_related_to_an_ip_address`, `get_entities_related_to_an_url`
*   `secops-mcp`: `lookup_entity`, `get_ioc_matches`, `search_security_events`
*   `secops-soar`: `list_cases`, `post_case_comment`
*   `ask_followup_question`
*   `write_to_file`
*   **Common Steps:** `common_steps/enrich_ioc.md`, `common_steps/pivot_on_ioc_gti.md`, `common_steps/find_relevant_soar_case.md`, `common_steps/document_in_soar.md`, `common_steps/generate_report_file.md`

## Workflow Steps & Diagram

1.  **Receive Input:** Obtain `${IOC_VALUE}`, `${IOC_TYPE}`, and optional inputs like `${CASE_ID}`, `${ALERT_GROUP_IDENTIFIERS}`, `${SIEM_SEARCH_HOURS}` (default 24).
2.  **Enrich IOC (GTI + SIEM Lookup):** Execute `common_steps/enrich_ioc.md` with `${IOC_VALUE}` and `${IOC_TYPE}`. Obtain `${GTI_FINDINGS}`, `${SIEM_ENTITY_SUMMARY}`, `${SIEM_IOC_MATCH_STATUS}`.
3.  **Fetch Key GTI Relationships:**
    *   Determine relevant relationships based on `${IOC_TYPE}` (e.g., for File Hash: `["contacted_domains", "contacted_ips"]`; for Domain: `["resolutions"]`). Let this be `REL_LIST`.
    *   Execute `common_steps/pivot_on_ioc_gti.md` with `${IOC_VALUE}`, `${IOC_TYPE}`, and `RELATIONSHIP_NAMES=REL_LIST`. Obtain `${GTI_RELATIONSHIPS}`.
4.  **Search Recent SIEM Events:**
    *   Construct a basic query for `secops-mcp.search_security_events` targeting `${IOC_VALUE}` (e.g., `text="${IOC_VALUE}"`).
    *   Execute the search with `hours_back=${SIEM_SEARCH_HOURS}`.
    *   Store a summary of findings (e.g., count, key event types, involved hosts/users) in `${SIEM_RECENT_EVENTS}`.
5.  **Search Relevant SOAR Cases:**
    *   Execute `common_steps/find_relevant_soar_case.md` with `SEARCH_TERMS=["${IOC_VALUE}"]` and `CASE_STATUS_FILTER="Opened"`.
    *   Obtain `${RELEVANT_CASE_IDS}` and `${RELEVANT_CASE_SUMMARIES}`. Let `${FOUND_CASES}` = `${RELEVANT_CASE_SUMMARIES}` (or `${RELEVANT_CASE_IDS}` if summaries aren't needed/available).
6.  **Synthesize Findings & Assess Risk:**
    *   Combine all findings: `${GTI_FINDINGS}`, `${GTI_RELATIONSHIPS}`, `${SIEM_ENTITY_SUMMARY}`, `${SIEM_IOC_MATCH_STATUS}`, `${SIEM_RECENT_EVENTS}`, `${FOUND_CASES}`.
    *   Guide the analyst (via output prompt or internal logic) to make an initial risk assessment (`${ASSESSMENT}`) based on the combined data (e.g., GTI reputation, SIEM activity presence/volume, relation to existing cases).
    *   Suggest potential next steps (`${RECOMMENDATION}`) based on the assessment (e.g., Escalate, Monitor, Close FP, Trigger IOC Containment).
7.  **Conditional Documentation:**
    *   **If `${CASE_ID}` was provided:**
        *   Prepare `COMMENT_TEXT` summarizing all findings, the assessment, and recommendation (e.g., "Basic IOC Enrichment for `${IOC_VALUE}` (`${IOC_TYPE}`): GTI Rep: [...], GTI Relations: [...], SIEM Summary: [...], SIEM Match: [...], Recent Events: [...], Related Cases: [...]. Assessment: `${ASSESSMENT}`. Recommendation: `${RECOMMENDATION}`.").
        *   Execute `common_steps/document_in_soar.md` with `CASE_ID=${CASE_ID}` and `COMMENT_TEXT`. Obtain `${DOCUMENTATION_STATUS}`.
    *   **Else (`${CASE_ID}` not provided):** Set `${DOCUMENTATION_STATUS}` = "Skipped (No Case ID)".
8.  **Optional Report Generation:**
    *   Use `ask_followup_question` to ask the user: "Generate a markdown report file for this enrichment?". Obtain `${REPORT_CHOICE}`.
    *   **If `${REPORT_CHOICE}` is "Yes":**
        *   Prepare `REPORT_CONTENT` similar to `COMMENT_TEXT` but formatted for a standalone report.
        *   Execute `common_steps/generate_report_file.md` with `REPORT_CONTENT`, `REPORT_TYPE="ioc_enrichment"`, `REPORT_NAME_SUFFIX=${IOC_VALUE}`. Obtain `${REPORT_GENERATION_STATUS}`.
    *   **Else:** Set `${REPORT_GENERATION_STATUS}` = "Skipped".
9.  **Completion:** Conclude the runbook execution. Present the key findings, assessment, recommendation, documentation status, and report generation status to the analyst.

```{mermaid}
sequenceDiagram
    participant Analyst
    participant Cline as Cline (MCP Client)
    participant EnrichIOC as common_steps/enrich_ioc.md
    participant PivotGTI as common_steps/pivot_on_ioc_gti.md
    participant FindCase as common_steps/find_relevant_soar_case.md
    participant DocumentInSOAR as common_steps/document_in_soar.md
    participant GenerateReport as common_steps/generate_report_file.md
    participant SIEM as secops-mcp
    participant GTI as gti-mcp
    participant SOAR as secops-soar
    participant User

    Analyst->>Cline: Start Basic IOC Enrichment v2\nInput: IOC_VALUE, IOC_TYPE, CASE_ID (opt), ...

    %% Step 2: Enrich IOC (GTI Report + SIEM Lookup + SIEM Match)
    Cline->>EnrichIOC: Execute(Input: IOC_VALUE, IOC_TYPE)
    EnrichIOC-->>Cline: Results: GTI_FINDINGS, SIEM_ENTITY_SUMMARY, SIEM_IOC_MATCH_STATUS

    %% Step 3: Fetch Key GTI Relationships
    Note over Cline: Determine relevant RELATIONSHIP_NAMES (REL_LIST)
    Cline->>PivotGTI: Execute(Input: IOC_VALUE, IOC_TYPE, RELATIONSHIP_NAMES=REL_LIST)
    PivotGTI-->>Cline: Results: GTI_RELATIONSHIPS

    %% Step 4: Search Recent SIEM Events
    Cline->>SIEM: search_security_events(text=IOC_VALUE, hours_back=SIEM_SEARCH_HOURS)
    SIEM-->>Cline: Recent SIEM Events Summary (SIEM_RECENT_EVENTS)

    %% Step 5: Search Relevant SOAR Cases
    Cline->>FindCase: Execute(Input: SEARCH_TERMS=[IOC_VALUE], CASE_STATUS_FILTER="Opened")
    FindCase-->>Cline: Results: RELEVANT_CASE_IDS, RELEVANT_CASE_SUMMARIES (FOUND_CASES)

    %% Step 6: Synthesize Findings & Assess Risk
    Note over Cline: Combine all findings (incl. FOUND_CASES). Guide analyst assessment (ASSESSMENT) & recommendation (RECOMMENDATION).

    %% Step 7: Conditional Documentation
    alt CASE_ID provided
        Note over Cline: Prepare COMMENT_TEXT with all findings, assessment, recommendation
        Cline->>DocumentInSOAR: Execute(Input: CASE_ID, COMMENT_TEXT)
        DocumentInSOAR-->>Cline: Results: DOCUMENTATION_STATUS
    else CASE_ID not provided
        Note over Cline: DOCUMENTATION_STATUS = "Skipped"
    end

    %% Step 8: Optional Report Generation
    Cline->>User: ask_followup_question(question="Generate markdown report?")
    User-->>Cline: Report Choice (REPORT_CHOICE)
    alt REPORT_CHOICE is "Yes"
        Note over Cline: Prepare REPORT_CONTENT
        Cline->>GenerateReport: Execute(Input: REPORT_CONTENT, REPORT_TYPE="ioc_enrichment", REPORT_NAME_SUFFIX=IOC_VALUE)
        GenerateReport-->>Cline: Results: REPORT_GENERATION_STATUS
    else REPORT_CHOICE is "No"
        Note over Cline: REPORT_GENERATION_STATUS = "Skipped"
    end

    %% Step 9: Completion
    Cline->>Analyst: attempt_completion(result="Basic IOC enrichment v2 complete for IOC_VALUE. Assessment: ASSESSMENT. Recommendation: RECOMMENDATION. Documentation: DOCUMENTATION_STATUS. Report: REPORT_GENERATION_STATUS.")

### Runbook: suspicious_login_triage.md

# Suspicious Login Alert Triage Runbook

## Objective

Guide the initial triage of common suspicious login alerts (e.g., Impossible Travel, Login from Untrusted Location, Multiple Failed Logins) for Tier 1 SOC Analysts.

## Scope

This runbook covers the initial investigation steps to gather context about a suspicious login event, focusing on user history and source IP reputation, to help determine if escalation is needed.

## Inputs

*   `${CASE_ID}`: The relevant SOAR case ID containing the alert(s).
*   `${ALERT_GROUP_IDENTIFIERS}`: Relevant alert group identifiers from the SOAR case.
*   *(Optional) `${ALERT_ID}`: Specific Alert ID if targeting a single alert.*
*   *(Optional) `${USER_ID}`: The user ID associated with the suspicious login (if known upfront).*
*   *(Optional) `${SOURCE_IP}`: The source IP address (if known upfront).*
*   *(Optional) `${ALERT_DETAILS}`: Specific details from the alert (e.g., alert name, timestamp).*

## Tools

*   `secops-soar`: `get_case_full_details`, `list_events_by_alert`, `post_case_comment`
*   `secops-mcp`: `lookup_entity`, `search_security_events`
*   `gti-mcp`: `get_ip_address_report`
*   *(Optional: Identity Provider tools like `okta-mcp.lookup_okta_user`)*
*   `ask_followup_question`
*   **Common Steps:** `common_steps/enrich_ioc.md`, `common_steps/find_relevant_soar_case.md`, `common_steps/document_in_soar.md`, `common_steps/generate_report_file.md`

## Workflow Steps & Diagram

1.  **Receive Input & Context:** Obtain `${CASE_ID}`, `${ALERT_GROUP_IDENTIFIERS}` (or `${ALERT_ID}`), and other optional inputs. Get full case details using `secops-soar.get_case_full_details`.
2.  **Extract Key Entities:**
    *   Use `secops-soar.list_events_by_alert` for the primary alert(s) in the case.
    *   Parse events to reliably extract the primary `${USER_ID}`, `${SOURCE_IP}`, and relevant `${HOSTNAME}`(s). Handle cases where these might be missing.
3.  **User Context (SIEM):**
    *   Use `secops-mcp.lookup_entity` with `entity_value=${USER_ID}`.
    *   Record summary of user's recent activity, first/last seen, related alerts (`USER_SIEM_SUMMARY`).
4.  **Source IP Enrichment:**
    *   Execute `common_steps/enrich_ioc.md` with `IOC_VALUE=${SOURCE_IP}` and `IOC_TYPE="IP Address"`.
    *   Obtain `${GTI_FINDINGS}`, `${SIEM_ENTITY_SUMMARY}` (for IP), `${SIEM_IOC_MATCH_STATUS}`. Let's call these `IP_GTI_FINDINGS`, `IP_SIEM_SUMMARY`, `IP_SIEM_MATCH`.
5.  **Hostname Context (SIEM):**
    *   If `${HOSTNAME}` was extracted:
        *   Use `secops-mcp.lookup_entity` with `entity_value=${HOSTNAME}`.
        *   Record summary (`HOSTNAME_SIEM_SUMMARY`).
6.  **Recent Login Activity (SIEM):**
    *   Use `secops-mcp.search_security_events` with a refined UDM query focusing on the last 24-72 hours:
        ```udm
        metadata.event_type IN ("USER_LOGIN", "AUTH_ATTEMPT") AND (
          principal.user.userid = "${USER_ID}" OR
          target.user.userid = "${USER_ID}" OR
          src.user.userid = "${USER_ID}"
        )
        ```
    *   Look for patterns: logins from other unusual IPs, successful logins after failures, frequency of logins from `${SOURCE_IP}` vs. others (`LOGIN_ACTIVITY_SUMMARY`).
7.  **Check Related SOAR Cases:**
    *   Execute `common_steps/find_relevant_soar_case.md` with `SEARCH_TERMS=["${USER_ID}", "${SOURCE_IP}", "${HOSTNAME}"]` (include hostname if available) and `CASE_STATUS_FILTER="Opened"`.
    *   Obtain `${RELATED_SOAR_CASES}` (list of potentially relevant open case summaries/IDs).
    *   *Note: `list_cases` filtering by entity is limited; review results carefully.*
8.  **(Optional) Identity Provider Check:**
    *   *(If `okta-mcp` or similar tool is available, use `okta-mcp.lookup_okta_user` with `${USER_ID}` to check account status, recent legitimate logins, MFA methods, etc. (`IDP_SUMMARY`))*
9.  **Synthesize & Document:**
    *   Combine findings: User context (`USER_SIEM_SUMMARY`), Source IP context (`IP_GTI_FINDINGS`, `IP_SIEM_SUMMARY`, `IP_SIEM_MATCH`), Hostname context (`HOSTNAME_SIEM_SUMMARY`), Login patterns (`LOGIN_ACTIVITY_SUMMARY`), Related cases (`${RELATED_SOAR_CASES}`), IDP check (`IDP_SUMMARY`).
    *   Prepare comment text: `COMMENT_TEXT = "Suspicious Login Triage for ${USER_ID} from ${SOURCE_IP} (Host: ${HOSTNAME}): User SIEM Summary: ${USER_SIEM_SUMMARY}. Source IP GTI: ${IP_GTI_FINDINGS}. Source IP SIEM: ${IP_SIEM_SUMMARY}. Source IP IOC Match: ${IP_SIEM_MATCH}. Hostname SIEM: ${HOSTNAME_SIEM_SUMMARY}. Recent Login Pattern: ${LOGIN_ACTIVITY_SUMMARY}. Related Open Cases: ${RELATED_SOAR_CASES}. Optional IDP Check: ${IDP_SUMMARY}. Recommendation: [Close as FP/Known Activity | Escalate to Tier 2 for further investigation]"`
    *   Execute `common_steps/document_in_soar.md` with `${CASE_ID}` and `${COMMENT_TEXT}`. Obtain `${COMMENT_POST_STATUS}`.
10. **(Optional) Generate Report:**
    *   Use `ask_followup_question` to ask the user: "Generate a markdown report file for this triage?". Obtain `${REPORT_CHOICE}`.
    *   **If `${REPORT_CHOICE}` is "Yes":**
        *   Prepare `REPORT_CONTENT` summarizing findings (similar to `${COMMENT_TEXT}` but formatted for a report, including the Mermaid diagram below).
        *   Execute `common_steps/generate_report_file.md` with `REPORT_CONTENT`, `REPORT_TYPE="suspicious_login_triage"`, `REPORT_NAME_SUFFIX=${CASE_ID}`. Obtain `${REPORT_GENERATION_STATUS}`.
    *   **Else:** Set `${REPORT_GENERATION_STATUS}` = "Skipped".
11. **Completion:** Conclude the runbook execution. Tier 1 analyst acts on the recommendation in the comment. Report generation status provided if applicable.

```{mermaid}
sequenceDiagram
    participant Analyst
    participant Cline as Cline (MCP Client)
    participant SOAR as secops-soar
    participant SIEM as secops-mcp
    participant EnrichIOC as common_steps/enrich_ioc.md
    participant FindCase as common_steps/find_relevant_soar_case.md
    participant DocumentInSOAR as common_steps/document_in_soar.md
    participant AskReport as ask_followup_question (Cline Tool)
    participant GenerateReport as common_steps/generate_report_file.md
    participant IDP as Identity Provider (Optional)

    Analyst->>Cline: Start Suspicious Login Triage\nInput: CASE_ID, ALERT_GROUP_IDS/ALERT_ID

    %% Step 1: Context
    Cline->>SOAR: get_case_full_details(case_id=CASE_ID)
    SOAR-->>Cline: Case Details

    %% Step 2: Extract Key Entities
    Cline->>SOAR: list_events_by_alert(case_id=CASE_ID, alert_id=...)
    SOAR-->>Cline: Events
    Note over Cline: Extract USER_ID, SOURCE_IP, HOSTNAME

    %% Step 3: User Context
    Cline->>SIEM: lookup_entity(entity_value=USER_ID)
    SIEM-->>Cline: User SIEM Summary (USER_SIEM_SUMMARY)

    %% Step 4: Source IP Enrichment
    Cline->>EnrichIOC: Execute(Input: IOC_VALUE=SOURCE_IP, IOC_TYPE="IP Address")
    EnrichIOC-->>Cline: Results: IP_GTI_FINDINGS, IP_SIEM_SUMMARY, IP_SIEM_MATCH

    %% Step 5: Hostname Context
    opt HOSTNAME extracted
        Cline->>SIEM: lookup_entity(entity_value=HOSTNAME)
        SIEM-->>Cline: Hostname SIEM Summary (HOSTNAME_SIEM_SUMMARY)
    end

    %% Step 6: Recent Login Activity
    Note over Cline: Use refined UDM query
    Cline->>SIEM: search_security_events(text="Refined Login Query for USER_ID", hours_back=72)
    SIEM-->>Cline: Recent Login Events (LOGIN_ACTIVITY_SUMMARY)

    %% Step 7: Check Related SOAR Cases
    Cline->>FindCase: Execute(Input: SEARCH_TERMS=[USER_ID, SOURCE_IP, HOSTNAME], CASE_STATUS_FILTER="Opened")
    FindCase-->>Cline: Results: RELATED_SOAR_CASES

    %% Step 8: Optional IDP Check
    opt IDP Tool Available (e.g., okta-mcp)
        Cline->>IDP: lookup_okta_user(user=USER_ID)
        IDP-->>Cline: User Account Details from IDP (IDP_SUMMARY)
    end

    %% Step 9: Synthesize & Document
    Note over Cline: Synthesize findings (incl. related cases, hostname) and prepare COMMENT_TEXT with Recommendation
    Cline->>DocumentInSOAR: Execute(Input: CASE_ID, COMMENT_TEXT)
    DocumentInSOAR-->>Cline: Results: COMMENT_POST_STATUS

    %% Step 10: Optional Report Generation
    Cline->>AskReport: ask_followup_question(question="Generate markdown report?")
    AskReport-->>Cline: User Response (REPORT_CHOICE)
    alt REPORT_CHOICE is "Yes"
        Note over Cline: Prepare REPORT_CONTENT (incl. Mermaid diagram)
        Cline->>GenerateReport: Execute(Input: REPORT_CONTENT, REPORT_TYPE="suspicious_login_triage", REPORT_NAME_SUFFIX=CASE_ID)
        GenerateReport-->>Cline: Results: REPORT_GENERATION_STATUS
    else REPORT_CHOICE is "No"
        Note over Cline: REPORT_GENERATION_STATUS = "Skipped"
    end

    %% Step 11: Completion
    Cline->>Analyst: attempt_completion(result="Suspicious Login Triage complete for USER_ID from SOURCE_IP. Findings documented in case CASE_ID. Report Status: REPORT_GENERATION_STATUS.")

### Runbook: malware_triage.md

# Malware Triage Runbook

## Objective

Perform initial analysis and context gathering for a suspected malicious file hash identified during an investigation or alert triage. This helps determine the nature of the file and its potential impact.

## Scope

This runbook covers the initial triage steps for a file hash using GTI and SIEM tools. It does not include full reverse engineering or deep forensic analysis of the affected host.

## Inputs

*   `${FILE_HASH}`: The MD5, SHA1, or SHA256 hash of the suspected malicious file.
*   `${CASE_ID}`: The relevant SOAR case ID for documentation.
*   `${ALERT_GROUP_IDENTIFIERS}`: Relevant alert group identifiers from the SOAR case.
*   *(Optional) `${TIME_FRAME_HOURS}`: Lookback period in hours for SIEM searches (default: 72).*

## Tools

*   `gti-mcp`: `get_file_report`, `get_file_behavior_summary`, `get_entities_related_to_a_file` (for contacted IPs/domains), `get_ip_address_report`, `get_domain_report`.
*   `secops-mcp`: `search_security_events`, `lookup_entity`.
*   `secops-soar`: `post_case_comment`, `get_case_full_details`, `list_cases`.
*   `ask_followup_question`
*   `write_to_file`
*   **Common Steps:** `common_steps/enrich_ioc.md`, `common_steps/find_relevant_soar_case.md`, `common_steps/document_in_soar.md`, `common_steps/generate_report_file.md`
*   **Basic Endpoint Triage & Isolation Runbook:** `.clinerules/run_books/basic_endpoint_triage_isolation.md` (Potentially triggered).

## Workflow Steps & Diagram

1.  **Receive Input & Context:** Obtain `${FILE_HASH}`, `${CASE_ID}`, `${ALERT_GROUP_IDENTIFIERS}`, and optionally `${TIME_FRAME_HOURS}`. Get case details via `secops-soar.get_case_full_details`.
2.  **GTI File Report:**
    *   Use `gti-mcp.get_file_report` with `hash=${FILE_HASH}`.
    *   Record key details (`${GTI_REPORT_DETAILS}`): detection ratio, malware family classification, first/last seen, associated threats.
3.  **GTI Behavior Summary:**
    *   Use `gti-mcp.get_file_behavior_summary` with `hash=${FILE_HASH}`.
    *   Record key behavioral indicators (`${GTI_BEHAVIOR_SUMMARY}`): network connections (contacted IPs/domains - `NETWORK_IOCs_GTI`), dropped files, registry keys modified, MITRE TTPs observed in sandbox.
4.  **SIEM Execution Check:**
    *   Use `secops-mcp.search_security_events` with `hours_back=${TIME_FRAME_HOURS}` and queries like:
        *   `target.file.sha256 = "${FILE_HASH}" OR target.file.md5 = "${FILE_HASH}" OR target.file.sha1 = "${FILE_HASH}"`
        *   Look for `PROCESS_LAUNCH`, `FILE_CREATION`, `FILE_MODIFICATION` events (`${SIEM_EXECUTION_EVENTS}`).
    *   Identify hosts (`AFFECTED_HOSTS`) and users (`AFFECTED_USERS`) associated with these events.
5.  **SIEM Network Activity Check:**
    *   Use `secops-mcp.search_security_events` to check for network connections (`NETWORK_CONNECTION`, `NETWORK_DNS`) originating from processes associated with `${FILE_HASH}` (using `principal.process.file.sha256 = "${FILE_HASH}"` or similar). Let these be `${SIEM_NETWORK_EVENTS}`.
    *   Extract contacted IPs/domains (`NETWORK_IOCs_SIEM`) from these events.
6.  **Enrich Network IOCs:**
    *   Combine unique IOCs from `NETWORK_IOCs_GTI` and `NETWORK_IOCs_SIEM` into `ALL_NETWORK_IOCs`.
    *   Initialize `NETWORK_IOC_ENRICHMENT`. For each IOC `Ni` in `ALL_NETWORK_IOCs`:
        *   Execute `common_steps/enrich_ioc.md` with `IOC_VALUE=Ni` and appropriate `IOC_TYPE`.
        *   Store results in `NETWORK_IOC_ENRICHMENT[Ni]`.
7.  **Check Related SOAR Cases:**
    *   Prepare list of key entities to search: `SEARCH_TERMS = AFFECTED_HOSTS + AFFECTED_USERS + ALL_NETWORK_IOCs`.
    *   Execute `common_steps/find_relevant_soar_case.md` with `SEARCH_TERMS` and `CASE_STATUS_FILTER="Opened"`.
    *   Obtain `${RELATED_SOAR_CASES}` (list of potentially relevant open case summaries/IDs).
8.  **Synthesize & Document:**
    *   Combine findings: `${GTI_REPORT_DETAILS}`, `${GTI_BEHAVIOR_SUMMARY}`, `${SIEM_EXECUTION_EVENTS}`, `${SIEM_NETWORK_EVENTS}`, `NETWORK_IOC_ENRICHMENT`, `AFFECTED_HOSTS`, `${RELATED_SOAR_CASES}`.
    *   Assess the severity based on GTI classification, behavior, observed activity, and relation to other cases.
    *   Prepare `COMMENT_TEXT`: "Malware Triage for Hash `${FILE_HASH}`: GTI Class: [...], Behavior Summary: [...]. Observed on Hosts: [`${AFFECTED_HOSTS}`]. Network Activity: [...]. Network IOC Enrichment: [...]. Related Open Cases: [`${RELATED_SOAR_CASES}`]. Assessment: [...]. Recommendation: [Trigger Endpoint Triage/Isolation for affected hosts] | [Block related Network IOCs (Trigger IOC Containment)] | [Escalate to Tier 3/IR for deeper analysis] | [Monitor]".
    *   Execute `common_steps/document_in_soar.md` with `${CASE_ID}` and `${COMMENT_TEXT}`. Obtain `${COMMENT_POST_STATUS}`.
9.  **(Optional) Generate Report:**
    *   Use `ask_followup_question` to ask the user: "Generate a markdown report file for this triage?". Obtain `${REPORT_CHOICE}`.
    *   **If `${REPORT_CHOICE}` is "Yes":**
        *   Prepare `REPORT_CONTENT` summarizing findings (similar to `${COMMENT_TEXT}` but formatted for a report, including a Mermaid diagram).
        *   Execute `common_steps/generate_report_file.md` with `REPORT_CONTENT`, `REPORT_TYPE="malware_triage"`, `REPORT_NAME_SUFFIX=${FILE_HASH}`. Obtain `${REPORT_GENERATION_STATUS}`.
    *   **Else:** Set `${REPORT_GENERATION_STATUS}` = "Skipped".
10. **Completion:** Conclude the runbook execution. Inform analyst of completion status and report generation status (if applicable).

```{mermaid}
sequenceDiagram
    participant Analyst
    participant Cline as Cline (MCP Client)
    participant GTI as gti-mcp
    participant SIEM as secops-mcp
    participant SOAR as secops-soar
    participant EnrichIOC as common_steps/enrich_ioc.md
    participant FindCase as common_steps/find_relevant_soar_case.md
    participant DocumentInSOAR as common_steps/document_in_soar.md
    participant AskReport as ask_followup_question (Cline Tool)
    participant GenerateReport as common_steps/generate_report_file.md
    participant Endpoint_Triage as Endpoint Triage Runbook %% Still potentially triggered

    Analyst->>Cline: Start Malware Triage\nInput: FILE_HASH, CASE_ID, ALERT_GROUP_IDS, TIME_FRAME_HOURS (opt)

    %% Step 1: Context
    Cline->>SOAR: get_case_full_details(case_id=CASE_ID)
    SOAR-->>Cline: Case Details

    %% Step 2: GTI File Report
    Cline->>GTI: get_file_report(hash=FILE_HASH)
    GTI-->>Cline: Detailed File Report (GTI_REPORT_DETAILS)

    %% Step 3: GTI Behavior Summary
    Cline->>GTI: get_file_behavior_summary(hash=FILE_HASH)
    GTI-->>Cline: Behavior Summary (NETWORK_IOCs_GTI)

    %% Step 4: SIEM Execution Check
    Cline->>SIEM: search_security_events(text="Events for hash FILE_HASH", hours_back=TIME_FRAME_HOURS)
    SIEM-->>Cline: Execution Events (SIEM_EXECUTION_EVENTS, AFFECTED_HOSTS, AFFECTED_USERS)

    %% Step 5: SIEM Network Activity Check
    Cline->>SIEM: search_security_events(text="Network activity from process hash FILE_HASH", hours_back=TIME_FRAME_HOURS)
    SIEM-->>Cline: Network Events (SIEM_NETWORK_EVENTS, NETWORK_IOCs_SIEM)

    %% Step 6: Enrich Network IOCs
    Note over Cline: Combine NETWORK_IOCs_GTI and NETWORK_IOCs_SIEM into ALL_NETWORK_IOCs
    loop For each key Network IOC Ni in ALL_NETWORK_IOCs
        Cline->>EnrichIOC: Execute(Input: IOC_VALUE=Ni, IOC_TYPE=...)
        EnrichIOC-->>Cline: Results: Store in NETWORK_IOC_ENRICHMENT[Ni]
    end

    %% Step 7: Check Related SOAR Cases
    Note over Cline: Prepare SEARCH_TERMS list (Hosts, Users, Network IOCs)
    Cline->>FindCase: Execute(Input: SEARCH_TERMS, CASE_STATUS_FILTER="Opened")
    FindCase-->>Cline: Results: RELATED_SOAR_CASES

    %% Step 8: Synthesize, Document & Recommend
    Note over Cline: Synthesize findings (incl. related cases), assess severity, prepare COMMENT_TEXT with Recommendation
    Cline->>DocumentInSOAR: Execute(Input: CASE_ID, COMMENT_TEXT)
    DocumentInSOAR-->>Cline: Results: COMMENT_POST_STATUS

    %% Step 9: Optional Report Generation
    Cline->>AskReport: ask_followup_question(question="Generate markdown report?")
    AskReport-->>Cline: User Response (REPORT_CHOICE)
    alt REPORT_CHOICE is "Yes"
        Note over Cline: Prepare REPORT_CONTENT (incl. Mermaid diagram)
        Cline->>GenerateReport: Execute(Input: REPORT_CONTENT, REPORT_TYPE="malware_triage", REPORT_NAME_SUFFIX=FILE_HASH)
        GenerateReport-->>Cline: Results: REPORT_GENERATION_STATUS
    else REPORT_CHOICE is "No"
        Note over Cline: REPORT_GENERATION_STATUS = "Skipped"
    end

    %% Step 10: Completion
    Cline->>Analyst: attempt_completion(result="Malware Triage complete for FILE_HASH. Findings documented in case CASE_ID. Report Status: REPORT_GENERATION_STATUS.")

### Runbook: lateral_movement_hunt_psexec_wmi.md

# Lateral Movement Detection Hunt (Example: PsExec/WMI)

## Objective

Proactively hunt for signs of lateral movement using common administrative tools like PsExec or WMI abuse, which attackers often leverage.

## Scope

This runbook provides a template for hunting specific lateral movement TTPs, focusing on PsExec and WMI examples using SIEM queries.

## Inputs

*   `${TIME_FRAME_HOURS}`: Lookback period in hours for SIEM searches (default: 72).
*   *(Optional) `${TARGET_SCOPE_QUERY}`: A UDM query fragment to narrow the scope (e.g., `principal.hostname = "server1"` or `target.hostname = "domain_controller"`).*
*   *(Optional) `${HUNT_HYPOTHESIS}`: Brief description of the reason for the hunt (e.g., "Hunting for PsExec usage originating from non-admin workstations").*

## Tools

*   `secops-mcp`: `get_threat_intel` (for technique understanding), `search_security_events` (core hunting tool), `lookup_entity` (for enriching findings).
*   `secops-soar`: `post_case_comment` (for documenting hunt/findings), `list_cases` (optional, check related cases).
*   `gti-mcp`: (Used for enriching findings if IOCs are discovered).
*   *(Optional: Identity Provider tools like `okta-mcp.lookup_okta_user`)*
*   **Common Steps:** `common_steps/find_relevant_soar_case.md`

## Workflow Steps & Diagram

1.  **Receive Input & Define Scope:** Obtain `${TIME_FRAME_HOURS}`, optionally `${TARGET_SCOPE_QUERY}` and `${HUNT_HYPOTHESIS}`.
2.  **Research Techniques (SIEM/External):**
    *   Use `secops-mcp.get_threat_intel` for TTPs like T1570 (Lateral Tool Transfer - PsExec often copied), T1021.002 (Remote Services: SMB/Windows Admin Shares - PsExec uses this), T1047 (Windows Management Instrumentation - WMI abuse).
    *   *(Manual Step: Review MITRE ATT&CK website for detailed procedures and detection guidance for these techniques).*
3.  **Develop SIEM Hunt Queries:**
    *   Based on research, formulate specific `secops-mcp.search_security_events` UDM queries targeting indicators. Examples:
        *   **PsExec Service Installation:** `metadata.product_event_type = "ServiceInstalled" AND target.process.file.full_path CONTAINS "PSEXESVC.exe"` (Requires appropriate Windows Event Log source - System Log Event ID 7045).
        *   **PsExec Execution (Indirect):** Look for `services.exe` spawning unusual processes, especially on remote machines shortly after potential SMB connection. `metadata.event_type = "PROCESS_LAUNCH" AND principal.process.file.full_path = "C:\Windows\System32\services.exe" AND target.process.file.full_path NOT IN ("standard_service_process1.exe", "standard_service_process2.exe")` (Needs significant tuning based on environment).
        *   **WMI Process Creation:** `metadata.event_type = "PROCESS_LAUNCH" AND principal.process.file.full_path = "C:\Windows\System32\wbem\WmiPrvSE.exe"` (Look for `WmiPrvSE.exe` spawning suspicious child processes like `cmd.exe`, `powershell.exe`).
        *   **WMI Command-Line Execution:** `metadata.event_type = "PROCESS_LAUNCH" AND principal.process.file.full_path = "C:\Windows\System32\cmd.exe" AND principal.process.command_line CONTAINS "wmic"` AND `principal.process.command_line CONTAINS "/node:"` AND `principal.process.command_line CONTAINS "process call create"`
        *   **WMI Event Subscription (Persistence T1546.003):** Search for events related to `__EventFilter`, `__EventConsumer`, `__FilterToConsumerBinding` creation/modification (Requires specific WMI event logging or EDR visibility). Example: `metadata.event_type = "WMI_ACTIVITY" AND description CONTAINS "__EventFilter"`
        *   **PowerShell WMI Methods:** Search for PowerShell scripts (`.ps1`) or command lines using `Invoke-WmiMethod`, `Get-WmiObject`, or `Invoke-CimMethod` for remote interaction. Example: `metadata.event_type = "PROCESS_LAUNCH" AND target.process.file.full_path CONTAINS "powershell.exe" AND target.process.command_line CONTAINS "Invoke-WmiMethod"`
    *   Combine technique-specific queries with `${TARGET_SCOPE_QUERY}` if provided.
4.  **Execute SIEM Searches:**
    *   Run the developed queries using `secops-mcp.search_security_events` with `hours_back=${TIME_FRAME_HOURS}`.
5.  **Network Correlation (Optional but Recommended):**
    *   If suspicious process activity is found on a target host, search for corresponding network connections (especially SMB port 445) originating from potential source hosts around the same time.
    *   Example Query: `metadata.event_type = "NETWORK_CONNECTION" AND target.port = 445 AND target.ip = "TARGET_IP" AND principal.ip = "SOURCE_IP"` (Adjust IPs and timeframe based on findings).
6.  **Analyze Results:**
    *   Review results for anomalous patterns: PsExec/WMI usage originating from unexpected sources (e.g., user workstations instead of admin servers), execution targeting a large number of hosts, execution of suspicious commands via WMI, correlation between network connections and remote process execution.
7.  **Enrich Findings:**
    *   If suspicious activity is found:
            *   Use `secops-mcp.lookup_entity` for involved source/destination hosts, users. Let these be `SUSPICIOUS_ENTITIES`.
            *   *(Optional)* If an Identity Provider tool is available (e.g., `okta-mcp.lookup_okta_user`), gather context on involved user accounts.
            *   Use `gti-mcp` tools to enrich any associated IPs, domains, or hashes if applicable. Let combined enrichment be `ENRICHMENT_RESULTS`.
8.  **Check Related SOAR Cases:**
    *   If `SUSPICIOUS_ENTITIES` were identified:
        *   Execute `common_steps/find_relevant_soar_case.md` with `SEARCH_TERMS=SUSPICIOUS_ENTITIES` and `CASE_STATUS_FILTER="Opened"`.
        *   Obtain `${RELATED_SOAR_CASES}` (list of potentially relevant open case summaries/IDs).
9.  **Document Hunt & Findings:**
    *   Use `secops-soar.post_case_comment` in a dedicated hunting case or relevant existing case.
    *   Document: Hunt Hypothesis/Objective, Techniques Hunted, Scope, Timeframe, Queries Used, Summary of Findings (**explicitly noting queries with negative results**), Details of suspicious activity, Enrichment results (`ENRICHMENT_RESULTS`), Related SOAR Cases (`${RELATED_SOAR_CASES}`).
    *   **Suggest Follow-on Actions:** Based on findings, suggest next steps like triggering `case_event_timeline_and_process_analysis.md` for suspicious processes or `compromised_user_account_response.md` for involved users.
10. **Escalate or Conclude:**
    *   If confirmed lateral movement or tool abuse is found, escalate by creating a new incident case or linking findings to an existing one.
    *   If no significant findings, conclude the hunt and document it thoroughly.
11. **Completion:** Conclude the runbook execution.

```{mermaid}
sequenceDiagram
    participant Analyst
    participant Cline as Cline (MCP Client)
    participant SecOpsMCP as secops-mcp
    participant SOAR as secops-soar
    participant MITRE as MITRE ATT&CK (External)
    participant IDP as Identity Provider (Optional)
    participant GTI as gti-mcp
    participant FindCase as common_steps/find_relevant_soar_case.md

    Analyst->>Cline: Start Lateral Movement Hunt (PsExec/WMI)\nInput: TIME_FRAME_HOURS, TARGET_SCOPE_QUERY (opt), HUNT_HYPOTHESIS (opt)

    %% Step 2: Research Techniques
    Cline->>SecOpsMCP: get_threat_intel(query="MITRE T1021.002")
    SecOpsMCP-->>Cline: Technique Context
    Cline->>SecOpsMCP: get_threat_intel(query="MITRE T1047")
    SecOpsMCP-->>Cline: Technique Context
    Cline->>MITRE: (Manual) Review ATT&CK Website
    MITRE-->>Cline: Detailed Procedures/Detections

    %% Step 3: Develop SIEM Queries
    Note over Cline: Formulate UDM queries for PsExec/WMI indicators (incl. new WMI examples)

    %% Step 4: Execute SIEM Searches
    loop For each developed Query Qi
        Cline->>SecOpsMCP: search_security_events(text=Qi, hours_back=TIME_FRAME_HOURS)
        SecOpsMCP-->>Cline: Search Results for Qi
    end

    %% Step 5: Network Correlation (Optional)
    opt Suspicious Activity Found
        Note over Cline: Construct Network Correlation Query Qn
        Cline->>SecOpsMCP: search_security_events(text=Qn, hours_back=...)
        SecOpsMCP-->>Cline: Network Correlation Results
    end

    %% Step 6: Analyze Results
    Note over Cline: Analyze results for anomalous PsExec/WMI usage & correlations

    %% Step 7: Enrich Findings
    opt Suspicious Activity Found
        Note over Cline: Identify SUSPICIOUS_ENTITIES (H1, U1...)
        loop For each Suspicious Entity Ei
            Cline->>SecOpsMCP: lookup_entity(entity_value=Ei)
            SecOpsMCP-->>Cline: SIEM Summary for Ei
            opt IDP Tool Available and Ei is User
                Cline->>IDP: lookup_user(user=Ei)
                IDP-->>Cline: User IDP Context
            end
            %% Potentially enrich related IOCs if found
            opt IOCs Found (I1, I2...)
                 loop For each IOC Ii
                     Cline->>GTI: get_..._report(ioc=Ii)
                     GTI-->>Cline: GTI Report for Ii
                 end
            end
        end
        Note over Cline: Store combined enrichment (ENRICHMENT_RESULTS)
    end

    %% Step 8: Check Related SOAR Cases
    opt Suspicious Activity Found
        Cline->>FindCase: Execute(Input: SEARCH_TERMS=SUSPICIOUS_ENTITIES, CASE_STATUS_FILTER="Opened")
        FindCase-->>Cline: Results: RELATED_SOAR_CASES
    end

    %% Step 9: Document Hunt
    Note over Cline: Prepare hunt summary comment (incl. negative results, related cases & suggested follow-ons)
    Cline->>SOAR: post_case_comment(case_id=[Hunt Case/Relevant Case], comment="Lateral Movement Hunt (PsExec/WMI) Summary: Scope [...], Queries [...], Findings [...], Enrichment [...], Related Cases: [...], Follow-on: [...]")
    SOAR-->>Cline: Comment Confirmation

    %% Step 10 & 11: Escalate or Conclude
    alt Confirmed Malicious Activity Found
        Note over Cline: Escalate findings (Create new case or link to existing)
        Cline->>Analyst: attempt_completion(result="Lateral Movement Hunt complete. Findings escalated.")
    else No Significant Findings
        Cline->>Analyst: attempt_completion(result="Lateral Movement Hunt complete. No significant findings. Hunt documented.")
    end

---

## Incident Alert & Asset Context

- **Case ID:** `CASE-GEN5-SAAS-BEACON-BENIGN-05`
- **Asset Criticality:** `STANDARD`

Triage alert CASE-64791: application server APP-DUB-48 (10.13.0.75) began contacting the previously unseen domain cdn82.stream-cloud.net every 124 seconds at 2026-09-27T01:57:00Z, which the network detection flagged as beaconing. Database server APP-DUB-09 (10.13.0.57) is listed as a connected asset. [CMDB Asset Context: Host APP-DUB-48 (10.13.0.75), Owner: elias.iyer, Role: Integration application server, Blast Radius: Customer-facing integrations; check the change calendar before containing]. Query domain intelligence and the change record, determine whether the traffic is sanctioned, and resolve the alert.

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
