# Structured IOC Triage and Response Runbook

## Objective

To provide a mandatory, four-stage epistemic verification process for triaging an Indicator of Compromise (IOC). This runbook is designed for autonomous agents and Tier 1 analysts to systematically gather evidence, assess risk, and determine an initial response, including mandatory containment for confirmed threats.

## Scope

This runbook covers the structured investigation of a single IOC. It mandates a sequence of evidence gathering from CMDB, network intelligence, threat intelligence, and internal SIEM telemetry before a conclusion is reached. It explicitly forbids bypassing any investigation stage.

## Inputs

*   `${IOC_VALUE}`: The specific IOC value (e.g., "198.51.100.10", "evil-domain.com", "abcdef123456...").
*   `${IOC_TYPE}`: The type of IOC (e.g., "IP Address", "Domain", "File Hash", "URL").
*   `${ASSET_IDENTIFIER}`: The primary asset associated with the alert (e.g., hostname or internal IP address).
*   *(Optional) `${CASE_ID}`: The relevant case ID for documentation.
*   *(Optional) `${SIEM_SEARCH_HOURS}`: Lookback period for SIEM event search (default: 24).

## Outputs

*   `${ASSET_CONTEXT}`: Summary of CMDB findings for the asset (role, owner, criticality).
*   `${ASSET_CRITICALITY}`: The business criticality of the involved asset (e.g., Critical, High, Standard).
*   `${IOC_ROUTING_TYPE}`: The network scope of the IOC (e.g., Public, Private, Reserved).
*   `${GTI_FINDINGS}`: Summary of key findings from the GTI report, including reputation.
*   `${CORROBORATING_ACTIVITY_FOUND}`: Boolean (Yes/No) indicating if SIEM events corroborate malicious behavior.
*   `${SIEM_RECENT_EVENTS}`: Summary of correlated SIEM events involving the IOC and asset.
*   `${FOUND_CASES}`: List of potentially related open SOAR cases.
*   `${ASSESSMENT}`: Final risk assessment (High, Medium, Low, Informational).
*   `${RECOMMENDATION}`: Mandated next steps (e.g., Trigger Containment, Escalate, Close FP).
*   `${DOCUMENTATION_STATUS}`: Status of documentation attempt in SOAR.

## Tools

*   `gti-mcp`: `get_ip_address_report`, `get_domain_report`, `get_file_report`, `get_url_report`
*   `secops-mcp`: `lookup_entity`, `search_security_events`
*   `secops-soar`: `list_cases`, `post_case_comment`
*   `secops-containment`: `isolate_host`, `block_indicator`
*   `write_to_file`

## Workflow Steps & Diagram

The workflow follows a mandatory 4-stage evidence verification sequence.

### Stage A: Asset Identity & CMDB Context

1.  **Query Asset Context:**
    *   Execute `secops-mcp.lookup_entity` with `entity_name=${ASSET_IDENTIFIER}`.
    *   Store the business role, owner, and criticality in `${ASSET_CONTEXT}`.
    *   Specifically store the criticality value in `${ASSET_CRITICALITY}`.
    *   If the asset is not found, set `${ASSET_CONTEXT}` to "Asset not found in CMDB" and `${ASSET_CRITICALITY}` to "Unknown".

### Stage B: Network Routing & Scope Verification

2.  **Determine IOC Network Scope:**
    *   **If `${IOC_TYPE}` is "IP Address" or "URL":**
        *   Execute `gti-mcp.get_ip_address_report` (or parse the IP from the URL first).
        *   Based on the report's network information, determine if the IP is public, private (RFC1918), or reserved. Store the result in `${IOC_ROUTING_TYPE}`.
    *   **If `${IOC_TYPE}` is "Domain":**
        *   Execute `gti-mcp.get_domain_report`.
        *   Check resolutions. If they resolve to private IP space, set `${IOC_ROUTING_TYPE}` to "Private". Otherwise, set to "Public".
    *   **For other types (e.g., "File Hash"):** Set `${IOC_ROUTING_TYPE}` to "Not Applicable".

### Stage C: Threat Intelligence Reputation

3.  **Query GTI Reputation:**
    *   Based on `${IOC_TYPE}`, execute the relevant `gti-mcp` function (`get_ip_address_report`, `get_domain_report`, `get_file_report`, `get_url_report`) for `${IOC_VALUE}`.
    *   Extract the reputation score, known malware associations, and first/last seen dates.
    *   Store a comprehensive summary in `${GTI_FINDINGS}`.

### Stage D: Corroboration of Malicious Activity

4.  **Correlate SIEM Telemetry:**
    *   Construct a targeted SIEM query to find behavioral evidence. Example: `(ioc="${IOC_VALUE}" OR destination.ip="${IOC_VALUE}" OR file.hash="${IOC_VALUE}") AND source.hostname="${ASSET_IDENTIFIER}" AND (event.category="malware" OR event.category="C2" OR event.type="suspicious_process_execution")`.
    *   Execute `secops-mcp.search_security_events` with the constructed query and `hours_back=${SIEM_SEARCH_HOURS}`.
    *   Analyze the results. If high-fidelity events (e.g., malware execution, C2 beaconing, exploit detected) are found, set `${CORROBORATING_ACTIVITY_FOUND}` to "Yes". Otherwise, set to "No".
    *   Store a summary of found events (count, types, timestamps) in `${SIEM_RECENT_EVENTS}`.

### Synthesis, Decision, and Action

5.  **Check for Existing Investigations:**
    *   Execute `secops-soar.list_cases` with `query="${IOC_VALUE}"` and `status="Opened"`.
    *   Store the list of any found case IDs or summaries in `${FOUND_CASES}`.

6.  **Apply Decision Logic:**
    *   **Rule 1 (High Confidence - Containment Required):**
        *   **IF** (`${GTI_FINDINGS}` indicates "Malicious" OR "High-Risk") **AND** (`${CORROBORATING_ACTIVITY_FOUND}` is "Yes") **AND** (`${IOC_ROUTING_TYPE}` is "Public")
        *   **THEN** set `${ASSESSMENT}` to "High" and `${RECOMMENDATION}` to "Trigger Containment".
    *   **Rule 2 (Medium Confidence - Escalation Required):**
        *   **IF** (the conditions for Rule 1 are not met) **AND** ((`${GTI_FINDINGS}` indicates "Suspicious" OR "Malicious") **OR** (`${CORROBORATING_ACTIVITY_FOUND}` is "Yes") **OR** (`${FOUND_CASES}` is not empty))
        *   **THEN** set `${ASSESSMENT}` to "Medium" and `${RECOMMENDATION}` to "Escalate to Tier 2".
    *   **Rule 3 (Low Confidence - Benign/Informational):**
        *   **ELSE** (all other conditions)
        *   **THEN** set `${ASSESSMENT}` to "Low" and `${RECOMMENDATION}` to "Close as False Positive/Informational".

7.  **Execute Recommended Action:**
    *   **IF `${RECOMMENDATION}` is "Trigger Containment":**
        *   Execute `secops-containment.block_indicator` with `indicator_value=${IOC_VALUE}` and `indicator_type=${IOC_TYPE}`.
        *   Execute `secops-containment.isolate_host` with `asset_identifier=${ASSET_IDENTIFIER}`.
    *   **IF `${RECOMMENDATION}` is "Escalate to Tier 2" or "Close as...":**
        *   Proceed to documentation. No automated containment actions are taken.

8.  **Document Findings:**
    *   **IF `${CASE_ID}` was provided:**
        *   Prepare `COMMENT_TEXT` summarizing the findings from all four stages, the final `${ASSESSMENT}`, and the `${RECOMMENDATION}`.
        *   Execute `secops-soar.post_case_comment` with `case_id=${CASE_ID}` and `comment=${COMMENT_TEXT}`.
        *   Set `${DOCUMENTATION_STATUS}` to "Completed".
    *   **ELSE:** Set `${DOCUMENTATION_STATUS}` to "Skipped (No Case ID)".

9.  **Completion:** Conclude the runbook. Present all outputs to the analyst for final review.

```{mermaid}
sequenceDiagram
    participant Analyst
    participant Cline as Cline (Agent)
    participant SIEM as secops-mcp
    participant GTI as gti-mcp
    participant SOAR as secops-soar
    participant Containment as secops-containment

    Analyst->>Cline: Start Structured Triage\nInput: IOC_VALUE, IOC_TYPE, ASSET_IDENTIFIER, CASE_ID

    %% Stage A: Asset Context
    Cline->>SIEM: lookup_entity(entity_name=ASSET_IDENTIFIER)
    SIEM-->>Cline: ASSET_CONTEXT, ASSET_CRITICALITY

    %% Stage B: Network Scope
    alt IOC is IP/URL/Domain
        Cline->>GTI: get_ip_address_report / get_domain_report
        GTI-->>Cline: IOC_ROUTING_TYPE (Public/Private)
    else
        Note over Cline: IOC_ROUTING_TYPE = "Not Applicable"
    end

    %% Stage C: TI Reputation
    Cline->>GTI: get_*_report(ioc=IOC_VALUE)
    GTI-->>Cline: GTI_FINDINGS (Reputation, etc.)

    %% Stage D: Corroboration
    Note over Cline: Construct targeted SIEM query for behavioral evidence
    Cline->>SIEM: search_security_events(query=..., hours_back=...)
    SIEM-->>Cline: SIEM_RECENT_EVENTS
    Note over Cline: Analyze results, set CORROBORATING_ACTIVITY_FOUND (Yes/No)

    %% Synthesis & Decision
    Cline->>SOAR: list_cases(query=IOC_VALUE, status="Opened")
    SOAR-->>Cline: FOUND_CASES

    alt High Confidence: (GTI=Malicious AND SIEM=Yes AND IOC=Public)
        Note over Cline: ASSESSMENT="High", RECOMMENDATION="Trigger Containment"
        Cline->>Containment: block_indicator(indicator=IOC_VALUE)
        Cline->>Containment: isolate_host(asset=ASSET_IDENTIFIER)
    else Medium Confidence: (GTI=Suspicious OR SIEM=Yes OR Existing Case)
        Note over Cline: ASSESSMENT="Medium", RECOMMENDATION="Escalate to Tier 2"
    else Low Confidence
        Note over Cline: ASSESSMENT="Low", RECOMMENDATION="Close as FP"
    end

    %% Documentation
    alt CASE_ID provided
        Note over Cline: Prepare summary comment
        Cline->>SOAR: post_case_comment(case_id=CASE_ID, comment=...)
        SOAR-->>Cline: DOCUMENTATION_STATUS="Completed"
    else
        Note over Cline: DOCUMENTATION_STATUS="Skipped"
    end

    %% Completion
    Cline->>Analyst: attempt_completion(result="Triage complete. Assessment: ASSESSMENT. Recommendation: RECOMMENDATION. Documentation: DOCUMENTATION_STATUS.")
```