# Lateral Movement Detection Hunt (Example: PsExec/WMI)

## Objective

Proactively hunt for signs of lateral movement using common administrative tools like PsExec or WMI abuse, which attackers often leverage.

## Scope

This runbook provides a template for hunting specific lateral movement TTPs, focusing on PsExec and WMI examples.

## Inputs

*   `<time_frame_hours>`: Lookback period in hours for SIEM searches.
*   `<target_scope_query>`: A UDM query fragment to narrow the scope.
*   `<hunt_hypothesis>`: Brief description of the reason for the hunt.

## Tools

*   `secops-mcp`: `lookup_entity`, `search_security_events`
*   `secops-soar`: `list_cases`, `update_case_comment`, `isolate_host`, `block_indicator`, `close_case`
*   `gti-mcp`: `get_ip_address_report`, `get_file_report`

## Workflow Steps

### Stage A: Asset Identity, CMDB Context, & SOAR Case Correlation

1.  Use `secops-mcp.lookup_entity` on involved hosts or users to determine business role, owner, and criticality.
2.  Query `secops-soar.list_cases` using key entities (e.g., <hostname>, <user_account>) to identify any pre-existing, related cases. Document findings to avoid duplication.

### Stage B: Network Routing & Scope Verification

1.  For any involved IP addresses, use `gti-mcp.get_ip_address_report` to determine if the routing is public, private, or reserved documentation space.

### Stage C: Threat Intelligence Reputation

1.  Check the GTI reputation of involved IP addresses or file hashes using `gti-mcp.get_ip_address_report` or `gti-mcp.get_file_report`.

### Stage D: Corroboration of Malicious Activity & Verdict

1.  Synthesize context from Stages A-C. Execute `secops-mcp.search_security_events` to find corroborating evidence. Focus queries on:
    *   PsExec service installation (`PSEXESVC.exe`).
    *   Remote WMI process creation (`WmiPrvSE.exe` spawning `cmd.exe` or `powershell.exe`).
    *   WMI command-line execution (`wmic /node:`).
2.  Apply a verdict based on evidence:
    *   **MALICIOUS:** If high-confidence lateral movement from an unauthorized source is confirmed, call `isolate_host` on the source asset and `update_case_comment`.
    *   **SUSPICIOUS:** If anomalous but unconfirmed administrative tool usage is found, call `update_case_comment` to escalate for human review. Never call `isolate_host`.
    *   **INCONCLUSIVE:** If a tool returns a service error, pivot to available local telemetry, set verdict to INCONCLUSIVE, and call `update_case_comment`.
    *   **BENIGN:** If activity is verified as authorized, call `update_case_comment` and `close_case`.
