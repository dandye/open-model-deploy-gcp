# Basic IOC Enrichment Runbook

## Objective

Standardize the initial enrichment process for a single Indicator of Compromise (IOC), optimized for autonomous agent execution. This runbook includes critical guardrails to ensure safe, context-aware decision-making.

## Scope

This runbook covers fundamental enrichment steps using GTI and SIEM tools. It is designed to gather context, apply operational guardrails, and determine an appropriate initial disposition (e.g., Close, Escalate, Contain) with high fidelity.

## Guardrails

This runbook incorporates critical safety guardrails to prevent negative operational impacts. The agent MUST adhere to these rules before proceeding with assessment or recommendations.

1.  **RFC-5737 Documentation IP Addresses:** IP addresses within `192.0.2.0/24`, `198.51.100.0/24`, and `203.0.113.0/24` are for documentation purposes. They MUST be assessed as `BENIGN` and closed as a False Positive. No containment actions are permitted.
2.  **Authorized Scanners:** If an IOC or its associated source/destination asset is identified as an "authorized vulnerability scanner" in the SIEM entity/CMDB lookup, it must not be blocked or isolated. The activity should be assessed as `INFORMATIONAL` and closed as a False Positive, unless other indicators strongly suggest a compromised scanner.
3.  **Explicit Operational Constraints:** Pay strict attention to CMDB data or alert context containing explicit warnings against containment (e.g., "Do not isolate," "High business impact"). If such a constraint exists and the threat is not confirmed as active, high-severity malware (e.g., ransomware), the mandatory recommendation is `Escalate to Tier 2` with all context. Do not perform autonomous containment.
4.  **Mandatory Containment for Confirmed Threats:** In the absence of overriding operational constraints, IOCs confirmed to be associated with active, high-severity threats (e.g., C2, ransomware, malware dropper) via high-confidence GTI intelligence or observed malicious behaviors in the SIEM MUST have a recommendation of `Trigger Containment`.

## Inputs

*   `${IOC_VALUE}`: The specific IOC value (e.g., "198.51.100.10", "evil-domain.com", "abcdef123456...", "http://bad.url/path").
*   `${IOC_TYPE}`: The type of IOC (e.g., "IP Address", "Domain", "File Hash", "URL").
*   *(Optional) `${ALERT_GROUP_IDENTIFIERS}`: Relevant alert group identifiers if needed for context in SOAR actions.*
*   *(Optional) `${CASE_ID}`: Relevant case ID if documentation is desired.*
*   *(Optional) `${SIEM_SEARCH_HOURS}`: Lookback period for SIEM event search (default: 24).*
*   *(Optional) `${ALERT_CONTEXT}`: Raw alert details or CMDB context provided with the initial trigger.*

## Outputs

*   `${GUARDRAIL_APPLIED}`: Name of the guardrail that influenced the final decision, if any (e.g., "RFC-5737", "Authorized Scanner", "Operational Constraint").
*   `${GTI_FINDINGS}`: Summary of key findings from the relevant GTI report.
*   `${GTI_RELATIONSHIPS}`: Summary of key related entities found via GTI pivoting.
*   `${SIEM_ENTITY_SUMMARY}`: Summary from the SIEM entity lookup, including any asset roles or tags.
*   `${SIEM_IOC_MATCH_STATUS}`: Boolean or indicator (Yes/No) if the IOC was found in recent SIEM IOC matches.
*   `${SIEM_RECENT_EVENTS}`: Summary of recent SIEM events involving the IOC.
*   `${FOUND_CASES}`: List of potentially related open SOAR cases.
*   `${ASSESSMENT}`: Final risk assessment (e.g., High/Medium/Low/Informational/Benign).
*   `${RECOMMENDATION}`: Suggested next steps (e.g., Escalate to Tier 2, Trigger Containment, Close FP).
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

1.  **Receive Input:** Obtain `${IOC_VALUE}`, `${IOC_TYPE}`, and optional inputs.
2.  **Pre-flight Guardrail Check (RFC-5737):**
    *   **If `${IOC_TYPE}` is "IP Address" AND `${IOC_VALUE}` is within `192.0.2.0/24`, `198.51.100.0/24`, or `203.0.113.0/24`:**
        *   Set `${ASSESSMENT}` = "Benign".
        *   Set `${RECOMMENDATION}` = "Close FP (RFC-5737 Documentation IP)".
        *   Set `${GUARDRAIL_APPLIED}` = "RFC-5737".
        *   Skip all enrichment and proceed directly to Step 9 (Conditional Documentation).
3.  **Enrich IOC (GTI + SIEM Lookup):** Execute `common_steps/enrich_ioc.md` with `${IOC_VALUE}` and `${IOC_TYPE}`. Obtain `${GTI_FINDINGS}`, `${SIEM_ENTITY_SUMMARY}`, `${SIEM_IOC_MATCH_STATUS}`.
4.  **Asset Context Guardrail Check:**
    *   Analyze `${SIEM_ENTITY_SUMMARY}` and `${ALERT_CONTEXT}`.
    *   **If the entity summary or context indicates the asset is an "authorized vulnerability scanner":**
        *   Set `${ASSESSMENT}` = "Informational".
        *   Set `${RECOMMENDATION}` = "Close FP (Authorized Scanner Activity)".
        *   Set `${GUARDRAIL_APPLIED}` = "Authorized Scanner".
        *   Skip enrichment steps 5-7 and proceed to Step 8 (Search Relevant SOAR Cases).
    *   **If the entity summary or context contains explicit operational constraints (e.g., "Do not isolate", "critical asset"):**
        *   Set internal flag `HAS_OPERATIONAL_CONSTRAINT` = True.
5.  **Fetch Key GTI Relationships:**
    *   Determine relevant relationships based on `${IOC_TYPE}` (e.g., for File Hash: `["contacted_domains", "contacted_ips"]`). Let this be `REL_LIST`.
    *   Execute `common_steps/pivot_on_ioc_gti.md` with `${IOC_VALUE}`, `${IOC_TYPE}`, and `RELATIONSHIP_NAMES=REL_LIST`. Obtain `${GTI_RELATIONSHIPS}`.
6.  **Search Recent SIEM Events:**
    *   Construct a query for `secops-mcp.search_security_events` targeting `${IOC_VALUE}`.
    *   Execute the search with `hours_back=${SIEM_SEARCH_HOURS}`.
    *   Store a summary of findings in `${SIEM_RECENT_EVENTS}`.
7.  **Decision Logic & Synthesis:**
    *   **Threat Evaluation:**
        *   If (`${GTI_FINDINGS}` indicates "Malicious") AND (`${SIEM_IOC_MATCH_STATUS}` is "Yes" OR `${SIEM_RECENT_EVENTS}` shows clear malicious activity): Set internal `THREAT_LEVEL` = "High".
        *   Else if (`${GTI_FINDINGS}` indicates "Malicious" or "Suspicious"): Set internal `THREAT_LEVEL` = "Medium".
        *   Else: Set internal `THREAT_LEVEL` = "Low".
    *   **Recommendation Engine:**
        *   **If `THREAT_LEVEL` is "High":**
            *   Set `${ASSESSMENT}` = "High".
            *   **If `HAS_OPERATIONAL_CONSTRAINT` is True:**
                *   Set `${RECOMMENDATION}` = "Escalate to Tier 2 (High-Risk Threat on Constrained Asset)".
                *   Set `${GUARDRAIL_APPLIED}` = "Operational Constraint".
            *   **Else:**
                *   Set `${RECOMMENDATION}` = "Trigger Containment".
        *   **If `THREAT_LEVEL` is "Medium":**
            *   Set `${ASSESSMENT}` = "Medium".
            *   Set `${RECOMMENDATION}` = "Escalate to Tier 2".
        *   **If `THREAT_LEVEL` is "Low":**
            *   Set `${ASSESSMENT}` = "Low".
            *   Set `${RECOMMENDATION}` = "Close FP".
8.  **Search Relevant SOAR Cases:**
    *   Execute `common_steps/find_relevant_soar_case.md` with `SEARCH_TERMS=["${IOC_VALUE}"]` and `CASE_STATUS_FILTER="Opened"`.
    *   Store results in `${FOUND_CASES}`.
9.  **Conditional Documentation:**
    *   **If `${CASE_ID}` was provided:**
        *   Prepare `COMMENT_TEXT` summarizing all findings, guardrails, assessment, and recommendation. (e.g., "Enrichment for `${IOC_VALUE}`: Guardrail Applied: `${GUARDRAIL_APPLIED}`. GTI: [...], SIEM Events: [...], Related Cases: [...]. Assessment: `${ASSESSMENT}`. Recommendation: `${RECOMMENDATION}`.").
        *   Execute `common_steps/document_in_soar.md` with `CASE_ID=${CASE_ID}` and `COMMENT_TEXT`. Obtain `${DOCUMENTATION_STATUS}`.
    *   **Else:** Set `${DOCUMENTATION_STATUS}` = "Skipped (No Case ID)".
10. **Optional Report Generation:**
    *   Use `ask_followup_question` to ask: "Generate a markdown report file for this enrichment?". Obtain `${REPORT_CHOICE}`.
    *   **If `${REPORT_CHOICE}` is "Yes":**
        *   Prepare `REPORT_CONTENT` similar to `COMMENT_TEXT`.
        *   Execute `common_steps/generate_report_file.md` with `REPORT_CONTENT`, `REPORT_TYPE="ioc_enrichment"`, `REPORT_NAME_SUFFIX=${IOC_VALUE}`. Obtain `${REPORT_GENERATION_STATUS}`.
    *   **Else:** Set `${REPORT_GENERATION_STATUS}` = "Skipped".
11. **Completion:** Conclude the runbook. Present the key findings, assessment, recommendation, and status of documentation and reporting.

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
    participant User

    Analyst->>Cline: Start Basic IOC Enrichment\nInput: IOC_VALUE, IOC_TYPE, ...

    %% Step 2: Pre-flight Guardrail Check
    alt IOC is RFC-5737 IP
        Note over Cline: ASSESSMENT="Benign", RECOMMENDATION="Close FP".
        Note over Cline: Skip to Documentation.
    else Not RFC-5737
        %% Step 3: Enrich IOC
        Cline->>EnrichIOC: Execute(Input: IOC_VALUE, IOC_TYPE)
        EnrichIOC-->>Cline: Results: GTI_FINDINGS, SIEM_ENTITY_SUMMARY, SIEM_IOC_MATCH_STATUS

        %% Step 4: Asset Context Guardrail Check
        alt Asset is Authorized Scanner
            Note over Cline: ASSESSMENT="Informational", RECOMMENDATION="Close FP".
            Note over Cline: Skip to SOAR Case Search.
        else Asset has Operational Constraint
            Note over Cline: Set HAS_OPERATIONAL_CONSTRAINT flag.
        end

        %% Step 5-7: Full Enrichment & Decision Logic
        Note right of Cline: (If no guardrails triggered early exit)
        Cline->>PivotGTI: Execute(Input: IOC_VALUE, IOC_TYPE, ...)
        PivotGTI-->>Cline: Results: GTI_RELATIONSHIPS
        Cline->>SIEM: search_security_events(text=IOC_VALUE, ...)
        SIEM-->>Cline: Recent SIEM Events Summary (SIEM_RECENT_EVENTS)
        Note over Cline: Apply Decision Logic: Evaluate threat, check constraints, set ASSESSMENT & RECOMMENDATION.
    end

    %% Step 8: Search Relevant SOAR Cases
    Cline->>FindCase: Execute(Input: SEARCH_TERMS=[IOC_VALUE], ...)
    FindCase-->>Cline: Results: FOUND_CASES

    %% Step 9: Conditional Documentation
    alt CASE_ID provided
        Note over Cline: Prepare COMMENT_TEXT with all findings & decisions.
        Cline->>DocumentInSOAR: Execute(Input: CASE_ID, COMMENT_TEXT)
        DocumentInSOAR-->>Cline: Results: DOCUMENTATION_STATUS
    else CASE_ID not provided
        Note over Cline: DOCUMENTATION_STATUS = "Skipped"
    end

    %% Step 10: Optional Report Generation
    Cline->>User: ask_followup_question(question="Generate markdown report?")
    User-->>Cline: Report Choice (REPORT_CHOICE)
    alt REPORT_CHOICE is "Yes"
        Note over Cline: Prepare REPORT_CONTENT
        Cline->>GenerateReport: Execute(Input: REPORT_CONTENT, ...)
        GenerateReport-->>Cline: Results: REPORT_GENERATION_STATUS
    else REPORT_CHOICE is "No"
        Note over Cline: REPORT_GENERATION_STATUS = "Skipped"
    end

    %% Step 11: Completion
    Cline->>Analyst: attempt_completion(result="Enrichment complete for IOC_VALUE. Assessment: ASSESSMENT. Recommendation: RECOMMENDATION.")
```