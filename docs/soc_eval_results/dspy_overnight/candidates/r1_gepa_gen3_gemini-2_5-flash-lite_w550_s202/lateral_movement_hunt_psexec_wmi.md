# Lateral Movement Detection Hunt (Example: PsExec/WMI)

## Objective

Proactively hunt for signs of lateral movement using common administrative tools like PsExec or WMI abuse.

## Scope

This runbook provides a template for hunting specific lateral movement TTPs, focusing on PsExec and WMI examples using SIEM queries.

## Inputs

*   `<time_frame_hours>`: Lookback period in hours for SIEM searches (default: 72).
*   *(Optional) `<target_scope_query>`: A UDM query fragment to narrow the scope (e.g., `principal.hostname = "server1"`).*
*   *(Optional) `<hunt_hypothesis>`: Brief description of the reason for the hunt.

## Tools

*   `secops-mcp`: `search_security_events`, `lookup_entity`
*   `gti-mcp`: `get_file_report`, `get_ip_address_report`
*   `secops-soar`: `post_case_comment`, `list_cases`

## Workflow Steps

### 1. Stage A: Asset & Case Context
First, establish the operational context. If a `<target_scope_query>` is provided, use `secops-mcp.lookup_entity` on the specified hosts or users to gather business role and criticality. Then, use `secops-soar.list_cases` with the names of any initial entities of interest to identify and review existing, related open cases. Document any relevant case IDs found.

### 2. Stage B: Hunt for Lateral Movement Telemetry
Execute focused hunt queries using `secops-mcp.search_security_events` with the specified `<time_frame_hours>`. Combine with `<target_scope_query>` if provided.

*   **PsExec Service Installation:** Search for Windows events indicating the PsExec service was installed.
    *   Query: `metadata.product_event_type = "ServiceInstalled" AND target.process.file.full_path CONTAINS "PSEXESVC.exe"`
*   **WMI Remote Process Creation:** Search for processes spawned by the WMI Provider Host, focusing on unusual children like command shells or scripting engines.
    *   Query: `metadata.event_type = "PROCESS_LAUNCH" AND principal.process.file.full_path CONTAINS "WmiPrvSE.exe"`
*   **WMI Command-Line Execution:** Search for command-line evidence of remote WMI execution.
    *   Query: `metadata.event_type = "PROCESS_LAUNCH" AND principal.process.command_line CONTAINS "wmic" AND principal.process.command_line CONTAINS "/node:" AND principal.process.command_line CONTAINS "process call create"`

### 3. Stage C: Enrich Findings with Threat & Network Intel
For any suspicious file hashes, process names, or IP addresses discovered in Stage B, enrich them using `gti-mcp` tools (`get_file_report`, `get_ip_address_report`) to check for known malicious indicators. For any identified source-to-target lateral movement events, correlate with network connection logs to verify a corresponding network path (e.g., over TCP port 445 for SMB) exists between the principal and target hosts.

### 4. Stage D: Analyze, Document, and Escalate
Synthesize findings from all stages. Analyze results for anomalous patterns, such as activity originating from non-administrative workstations or targeting an unusual number of hosts. Use `secops-soar.post_case_comment` to document the complete hunt process in a relevant SOAR case. The comment must include the hunt hypothesis, scope, queries used, a summary of findings (including queries with no results), and all enrichment data. If suspicious activity is found, state this clearly and recommend follow-on actions. If no significant findings are made, document the hunt as complete.