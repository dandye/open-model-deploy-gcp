"""MCP Tool Description Provider for Dynamic Model Context Protocol Integration.

Supports dynamically resolving tool descriptions from:
1. 'gepa': Pareto-optimized tool descriptions from gusto-mcp-gepa (via import or fallback registry).
2. 'default': Standard upstream mcp-security / deterministic tool docstrings.
"""

import importlib
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Canonical GEPA tool descriptions from gusto-mcp-gepa
FALLBACK_GEPA_DESCRIPTIONS: Dict[str, str] = {
    # SecOps SIEM
    "search_security_events": (
        "Search for security events in Chronicle SIEM using natural language. "
        "Allows searching Chronicle event logs using natural language queries, which are "
        "automatically translated into UDM queries for execution. "
        "Ideal for deep investigation after an initial alert, case, or entity has been prioritized."
    ),
    "get_security_alerts": (
        "Get security alerts directly from Chronicle SIEM. "
        "Retrieves a list of recent security alerts generated within Chronicle, based on "
        "detection rules or other alert sources configured in the SIEM."
    ),
    "get_security_alert_by_id": (
        "Get security alert by ID directly from Chronicle SIEM. "
        "Gets an alert by ID. "
        "Use this for direct monitoring of SIEM alert activity, potentially identifying "
        "issues before they are ingested or processed by other platforms."
    ),
    "do_update_security_alert": (
        "Update security alert attributes directly in Chronicle SIEM. "
        "Modifies specific fields of an existing security alert within Chronicle based on its ID. "
        "This function allows for updates to an alert's status, severity, verdict, assigned scores, comments, and other metadata."
    ),
    "lookup_entity": (
        "Look up an entity (IP, domain, hash, user, etc.) in Chronicle SIEM for enrichment. "
        "Provides a comprehensive summary of an entity's activity based on historical log data "
        "within Chronicle over a specified time period. This tool queries Chronicle SIEM directly."
    ),
    "list_security_rules": (
        "List security detection rules configured in Chronicle SIEM, with support for pagination. "
        "Retrieves the definitions of detection rules currently active or configured "
        "within the Chronicle SIEM instance."
    ),
    "search_security_rules": (
        "Search security detection rules configured in Chronicle SIEM. "
        "Retrieves the definitions of detection rules currently active or configured "
        "within the Chronicle SIEM instance based on a regex pattern."
    ),
    "get_ioc_matches": (
        "Get IoC matches directly from Chronicle SIEM. "
        "Retrieves recent IoC matches observed within the SIEM environment."
    ),
    "get_threat_intel": (
        "Retrieve threat intelligence from Chronicle SIEM. "
        "Queries threat intelligence data and returns detailed summaries regarding "
        "threat actors, campaigns, CVEs, or general best practices."
    ),
    "search_udm": (
        "Search UDM events using UDM query in Chronicle. "
        "Accepts raw YARA-L UDM query strings to locate underlying event records "
        "in the Chronicle database over a specified time range."
    ),
    "export_udm_search_csv": (
        "Export UDM search results as a formatted CSV string. "
        "Useful for downloading logs for external reporting or offline triage."
    ),
    "find_udm_field_values": (
        "Find UDM field values for autocomplete. "
        "Searches for values matching a query string in specified UDM fields."
    ),
    # GTI (Google Threat Intelligence)
    "get_ip_address_report": (
        "Get a comprehensive IP Address analysis report from Google Threat Intelligence. "
        "Provides geolocation, autonomous system details, and threat reputation data."
    ),
    "get_domain_report": (
        "Get a comprehensive domain analysis report from Google Threat Intelligence. "
        "Provides attributes, threat classification, and historical metadata for a domain."
    ),
    "get_url_report": (
        "Get a comprehensive URL analysis report from Google Threat Intelligence. "
        "Provides security analysis, categorizations, and threat category classifications."
    ),
    "get_file_report": (
        "Get a comprehensive file analysis report using its hash (MD5/SHA-1/SHA-256). "
        "Provides detection stats, threat classifications, and static metadata."
    ),
    "get_file_behavior_summary": (
        "Retrieve a summary of all sandbox execution reports and dynamic analysis details for a file."
    ),
    "get_file_behavior_report": (
        "Retrieve a full, detailed sandbox behavior report using a behavior ID formatted as {hash}_{sandbox}."
    ),
    "search_iocs": (
        "Search Indicators of Compromise (IOC) in the Google Threat Intelligence platform using VirusTotal query search modifiers."
    ),
    "search_threats": (
        "Search threats in the Google Threat Intelligence platform. "
        "Threats are modeled as collections. Once you get collections from this tool, "
        "you can use get_collection_report to fetch the full reports and their relationships."
    ),
    # SecOps SOAR
    "list_cases": (
        "List cases available in the Security Orchestration, Automation, and Response (SOAR) platform. "
        "In a SOAR context, a 'case' typically represents a security incident, investigation, or a "
        "container for related alerts and response actions. Listing cases provides an overview of "
        "ongoing or past security events being managed by the platform. This is useful for getting "
        "a high-level list of recent security issues or finding a specific incident to investigate further."
    ),
    "post_case_comment": (
        "Post a comment to a specific case within the SOAR platform. Cases are used to track security "
        "incidents and investigations. Adding comments is essential for documenting findings, communication "
        "between analysts, recording actions taken, or providing updates on the investigation progress."
    ),
    "get_case_full_details": (
        "Retrieve comprehensive details for a specific case by aggregating its core information, associated "
        "alerts, and comments. This tool provides a consolidated view of a security case by fetching its "
        "primary details (like status, priority, description), all linked security alerts, and the full "
        "history of comments added by analysts or automation. This aggregated information is essential for "
        "getting a complete understanding of an incident's context, scope, investigation progress, and "
        "collaborative notes without making multiple separate API calls."
    ),
    "list_alerts_by_case": (
        "List the security alerts associated with a specific case ID in the SOAR platform. Alerts are "
        "notifications generated by security tools (like SIEMs, EDRs) indicating potential security issues."
    ),
    "list_events_by_alert": (
        "List the underlying security events associated with a specific alert within a given case."
    ),
    "change_case_priority": (
        "Change the priority level of a specific case in the SOAR platform."
    ),
    "get_entity_details": (
        "Fetch detailed information about a specific entity known to the SOAR platform."
    ),
    "search_entity": (
        "Search for entities within the SOAR platform based on various criteria."
    ),
}

# Aliases between local/remote MCP tools and canonical GEPA descriptions
TOOL_ALIASES: Dict[str, str] = {
    "get_case": "get_case_full_details",
    "create_case_comment": "post_case_comment",
    "update_case_comment": "post_case_comment",
    "summarize_entity": "lookup_entity",
    "udm_search": "search_udm",
    "fetch_alert_data": "get_security_alert_by_id",
}


def _try_load_gusto_gepa_defaults() -> Dict[str, str]:
    """Attempts to dynamically load GEPA defaults from gusto-mcp-gepa."""
    candidate_paths = []
    env_path = os.environ.get("GUSTO_MCP_GEPA_DIR")
    if env_path:
        candidate_paths.append(Path(env_path) / "src")

    # Common relative worktree paths
    base_repo_dir = Path(__file__).resolve().parent.parent
    candidate_paths.extend([
        base_repo_dir.parent.parent / "gusto-mcp-gepa__worktrees" / "feat-gepa-default" / "src",
        base_repo_dir.parent / "gusto-mcp-gepa" / "src",
        base_repo_dir.parent / "feat-gepa-default" / "src",
    ])

    for p in candidate_paths:
        if p.exists() and str(p) not in sys.path:
            sys.path.insert(0, str(p))
            break

    try:
        from gusto_mcp_gepa.defaults import ALL_GEPA_DESCRIPTIONS  # type: ignore
        logger.debug("Successfully loaded %d GEPA descriptions from gusto_mcp_gepa", len(ALL_GEPA_DESCRIPTIONS))
        return dict(ALL_GEPA_DESCRIPTIONS)
    except Exception as e:
        logger.debug("Using built-in fallback GEPA descriptions (reason: %s)", e)
        return dict(FALLBACK_GEPA_DESCRIPTIONS)


class McpToolProvider:
    """Manages dynamic retrieval and formatting of MCP tool descriptions."""

    def __init__(
        self,
        provider: str = "default",
        custom_descriptions: Optional[Dict[str, str]] = None,
    ):
        """Initializes the MCP tool provider.

        Args:
            provider: Tool description source ('default' or 'gepa').
            custom_descriptions: Optional overrides for specific tools.
        """
        self.provider = (provider or "default").lower().strip()
        self.custom_descriptions = dict(custom_descriptions or {})
        self._gepa_cache: Optional[Dict[str, str]] = None

    @property
    def gepa_descriptions(self) -> Dict[str, str]:
        """Lazy-loaded GEPA descriptions."""
        if self._gepa_cache is None:
            self._gepa_cache = _try_load_gusto_gepa_defaults()
        return self._gepa_cache

    def get_description(self, tool_name: str, default_doc: Optional[str] = None) -> str:
        """Retrieves the tool description according to the active provider.

        Args:
            tool_name: Canonical or aliased name of the tool.
            default_doc: Fallback docstring to use if provider is default or tool unmapped.

        Returns:
            Formatted tool description string.
        """
        if tool_name in self.custom_descriptions:
            return self.custom_descriptions[tool_name]

        if self.provider == "gepa":
            # Check direct name
            if tool_name in self.gepa_descriptions:
                return self.gepa_descriptions[tool_name]
            # Check aliased name
            alias = TOOL_ALIASES.get(tool_name)
            if alias and alias in self.gepa_descriptions:
                return self.gepa_descriptions[alias]

        # Default provider: return default_doc
        if default_doc:
            # Strip extra whitespace but keep first line or paragraph
            lines = [line.strip() for line in default_doc.strip().splitlines() if line.strip()]
            return lines[0] if lines else "No description available."

        return "No description available."

    def get_all_descriptions(self) -> Dict[str, str]:
        """Returns all available descriptions under the current provider."""
        if self.provider == "gepa":
            merged = dict(self.gepa_descriptions)
            for k, v in TOOL_ALIASES.items():
                if v in merged and k not in merged:
                    merged[k] = merged[v]
            merged.update(self.custom_descriptions)
            return merged
        return dict(self.custom_descriptions)


def get_tool_description(
    tool_name: str,
    provider: str = "default",
    default_doc: Optional[str] = None,
) -> str:
    """Convenience function to get a single tool's description."""
    mcp_provider = McpToolProvider(provider=provider)
    return mcp_provider.get_description(tool_name, default_doc=default_doc)
