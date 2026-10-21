# Proactive GTI Collection & Campaign Threat Hunt

## Objective

Sweep enterprise telemetry for indicators and execution chains linked to a GTI collection or threat hypothesis to identify Patient Zero, scope, and detection gaps.

## Scope

Covers fleet-wide CTI collection sweeps (GTI reports, C2 domains, and MITRE ATT&CK execution chains) across SIEM, GTI, and SOAR.

## Inputs

*   `<collection_id>`: Target GTI collection, report ID, or seed C2 domain.
*   `<time_frame_hours>`: SIEM lookback in hours (default `72`; widen to `168` on zero hits).
*   `<target_scope_query>`: Optional UDM host-group filter.

## Tools

*   GTI: `get_collection_report`, `get_entities_related_to_a_collection`, `get_entities_related_to_a_domain`, `get_domain_report`, `get_file_report`, `get_ip_address_report`
*   SIEM: `get_ioc_matches`, `search_security_events`, `lookup_entity`, `get_security_alerts`
*   SOAR: `list_cases`, `update_case_comment`, `isolate_host`, `block_indicator`, `close_case`

## Workflow Steps

### Stage A: CTI Collection & Multi-Horizon SIEM Sweep (`72h` to `168h`)

1.  Call `get_collection_report` and `get_entities_related_to_a_collection` (or `get_domain_report` and `get_entities_related_to_a_domain`) to extract indicators.
2.  Call `get_ioc_matches` and `search_security_events` for extracted indicators, starting with `hours_back=72`.
3.  If the `72h` sweep returns zero matches, widen the lookback to `168h` and repeat searches across DNS, network, `PROCESS_LAUNCH`, and `PROCESS_MODULE_LOAD` events.

### Stage B: Second-Hop Pivot, Verification, & Correlation

4.  For matched C2 domains, call `get_entities_related_to_a_domain` (`relationship_name="communicating_files"`) to find second-hop file hashes.
5.  **Mandatory:** For **every** file hash from CTI or SIEM results, call `get_file_report`. Verify `cert_status` to separate unsigned malware from signed OS LOLBins (`rundll32.exe`) before containment.
6.  On any `<matched_hostname>`, call `lookup_entity` and `list_cases` to check for authorized `CHG-...` maintenance records and existing SOAR cases (`<case_id>`).

### Stage C: Hunt Verdict, Containment, & Detection-Gap Handoff

7.  Apply a verdict on `<case_id>`:
    *   **MALICIOUS:** Campaign C2 or unsigned payload execution confirmed. Call `isolate_host` on `<matched_hostname>`, `block_indicator` on verified C2s, IPs, and hashes (never block files with a `VALID_CERTIFICATE` status), and `update_case_comment`.
    *   **SUSPICIOUS:** Unconfirmed LOLBin/TTP outlier or activity on a critical asset where isolation is prohibited. Call `update_case_comment` with YL2 criteria. Never `isolate_host` or `close_case`.
    *   **INCONCLUSIVE:** Tool outage (`HTTP 503`). Call `list_cases` to get context, then `update_case_comment` to document the outage. Never `isolate_host`, `block_indicator`, or `close_case`.
    *   **BENIGN:** Zero malicious hits, or activity is explained by an authorized `CHG-...` record. Call `update_case_comment` and `close_case`.