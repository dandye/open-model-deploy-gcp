# Lateral Movement Detection Hunt (Example: PsExec/WMI)

## Objective

Proactively hunt for signs of lateral movement using common administrative tools like PsExec or WMI abuse, which attackers often leverage.

## Scope

This runbook provides a template for hunting specific lateral movement TTPs, focusing on PsExec and WMI examples using SIEM queries.

## Inputs

*   `<time_frame_hours>`: Lookback period in hours for SIEM searches (default: 72).
*   *(Optional) `<target_scope_query>`: A UDM query fragment to narrow the scope (e.g., `principal.hostname = "server1"` or `target.hostname = "domain_controller"`).*
*   *(Optional) `<hunt_hypothesis>`: Brief description of the reason for the hunt (e.g., "Hunting for PsExec usage originating from non-admin workstations").*

## Tools

*   `secops-mcp`: `get_threat_intel` (for technique understanding), `search_security_events` (core hunting tool), `lookup_entity` (for enriching findings).
*   `secops-soar`: `post_case_comment` (for documenting hunt/findings), `list_cases` (optional, check related cases).
*   `gti-mcp`: (Used for enriching findings if IOCs are discovered).
*   *(Optional: Identity Provider tools like `okta-mcp.lookup_okta_user`)*
*   **Common Steps:** `common_steps/find_relevant_soar_case.md`

## Workflow Steps & Diagram

1.  **Receive Input & Define Scope:** Obtain `<time_frame_hours>`, optionally `<target_scope_query>` and `<hunt_hypothesis>`.
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
    *   Combine technique-specific queries with `<target_scope_query>` if provided.
4.  **Execute SIEM Searches:**
    *   Run the developed queries using `secops-mcp.search_security_events` with `hours_back=<time_frame_hours>`.
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
        *   Obtain `<related_soar_cases>` (list of potentially relevant open case summaries/IDs).
9.  **Document Hunt & Findings:**
    *   Use `secops-soar.post_case_comment` in a dedicated hunting case or relevant existing case.
    *   Document: Hunt Hypothesis/Objective, Techniques Hunted, Scope, Timeframe, Queries Used, Summary of Findings (**explicitly noting queries with negative results**), Details of suspicious activity, Enrichment results (`ENRICHMENT_RESULTS`), Related SOAR Cases (`<related_soar_cases>`).
    *   **Suggest Follow-on Actions:** Based on findings, suggest next steps like triggering `case_event_timeline_and_process_analysis.md` for suspicious processes or `compromised_user_account_response.md` for involved users.
10. **Escalate or Conclude:**
    *   If confirmed lateral movement or tool abuse is found, escalate by creating a new incident case or linking findings to an existing one.
    *   If no significant findings, conclude the hunt and document it thoroughly.
11. **Completion:** Conclude the runbook execution.