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

*   `secops-mcp`: `lookup_entity`, `search_security_events`
*   `secops-soar`: `list_cases`, `get_case`, `post_case_comment`
*   `gti-mcp`: `get_ip_address_report`, `get_domain_report`, `get_file_report`

## Workflow Steps

The investigation must follow this four-stage procedural flow to ensure evidence is gathered and verified in a structured manner.

### Stage A: Asset Identity, CMDB Context, & SOAR Case Correlation

1.  For any involved entities (e.g., `<source_hostname>`, `<target_hostname>`), use `secops-mcp.lookup_entity` to gather CMDB context. Note the asset's business role, owner, and criticality.
2.  Query `secops-soar.list_cases` using entity names or other potential indicators to find related open cases. This prevents duplicate effort and provides historical context.

### Stage B: Network Routing & Scope Verification

1.  For any external IP addresses or domains involved in the hunt, use `gti-mcp.get_ip_address_report` or `gti-mcp.get_domain_report`.
2.  Determine if the infrastructure is public, private, or reserved documentation space to understand the nature of the communication (e.g., internal-to-internal vs. internal-to-external).

### Stage C: Threat Intelligence Reputation

1.  Using `gti-mcp` tools, check the reputation scores and any known malware associations for all external indicators (IPs, domains, hashes) identified during the hunt.
2.  Document any high-risk reputation findings.

### Stage D: Corroboration, Verdict, and Action

1.  Synthesize findings from Stages A-C. Correlate the entity context and threat intelligence with behavioral evidence of lateral movement by executing targeted queries with `secops-mcp.search_security_events`.
2.  **Example Corroboration Queries:**
    *   **PsExec Service:** `metadata.product_event_type = "ServiceInstalled" AND target.process.file.full_path CONTAINS "PSEXESVC.exe"`
    *   **WMI Process Creation:** `metadata.event_type = "PROCESS_LAUNCH" AND principal.process.file.full_path CONTAINS "WmiPrvSE.exe" AND target.process.file.full_path IN ("cmd.exe", "powershell.exe")`
    *   **WMI Remote Command-Line:** `principal.process.command_line CONTAINS "wmic" AND principal.process.command_line CONTAINS "/node:"`
3.  **Verdict & Action:**
    *   If queries confirm unauthorized administrative tool usage (e.g., PsExec from a standard workstation to a server), set the verdict to `SUSPICIOUS`.
    *   If no supporting evidence is found for the hunt hypothesis, the result is `INCONCLUSIVE`.
    *   Document all steps, queries, and findings using `secops-soar.post_case_comment`. For `SUSPICIOUS` findings, escalate for Tier 2 review. Do not perform containment actions like `isolate_host` during a hunt.