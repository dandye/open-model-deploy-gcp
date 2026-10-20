# Lateral Movement Hunt (PsExec/WMI)

## Objective

Proactively hunt for signs of lateral movement using common administrative tools like PsExec or WMI abuse.

## Scope

This runbook provides a template for executing SIEM-based hunts for specific lateral movement TTPs.

## Inputs

*   `<time_frame_hours>`: Lookback period in hours for SIEM searches (default: 72).
*   *(Optional) `<target_scope_query>`*: A UDM query fragment to narrow the hunt scope.

## Tools

*   `secops-mcp`: `get_threat_intel`, `search_security_events`, `lookup_entity`.
*   `secops-soar`: `post_case_comment`.
*   **Common Steps:** `common_steps/find_relevant_soar_case.md`.

## Workflow Steps

### Stage A: Define Hunt Scope & TTPs
1.  Use `secops-mcp.get_threat_intel` on T1021.002 (Remote Services: SMB/Windows Admin Shares) and T1047 (Windows Management Instrumentation) to inform query logic.

### Stage B: Execute Hunt Queries
1.  Formulate and execute UDM hunt queries using `secops-mcp.search_security_events` with `hours_back=<time_frame_hours>` and the optional `<target_scope_query>`.
    *   *Example PsExec:* `metadata.product_event_type = "ServiceInstalled" AND target.process.file.path ENDS WITH "PSEXESVC.exe"`
    *   *Example WMI:* `metadata.event_type = "PROCESS_LAUNCH" AND principal.process.file.path ENDS WITH "WmiPrvSE.exe" AND target.process.file.name IN ("cmd.exe", "powershell.exe")`
2.  If no results are found, document the negative findings and conclude. Otherwise, let the results be `<suspicious_events>`.

### Stage C: Corroborate Findings
1.  For each event in `<suspicious_events>`, identify key entities like `<source_host>`, `<target_host>`, and `<user>`.
2.  Enrich these entities using `secops-mcp.lookup_entity`. Let the results be `<enrichment_data>`.
3.  **Degraded-Mode Pivot:** If `lookup_entity` fails, proceed with unenriched data but log the tool failure. Do not retry the call.

### Stage D: Document & Recommend Next Steps
1.  Check for existing open cases related to the involved entities via `common_steps/find_relevant_soar_case.md`.
2.  Use `secops-soar.post_case_comment` to document the hunt scope, queries, findings (`<suspicious_events>`), and `<enrichment_data>`.
3.  Based on findings, recommend follow-on actions (e.g., escalate to a full incident, trigger a deeper analysis runbook) or formally conclude the hunt.