"""Unit tests for McpToolProvider and dynamic GEPA tool description resolution."""

import pytest
from agent.mcp_provider import McpToolProvider, get_tool_description
from agent.soc_tier1_agent import SocTier1Agent
from agent.soc_tools import lookup_entity, get_ip_address_report


def test_mcp_provider_default():
    """Default provider should return fallback or original docstring."""
    provider = McpToolProvider(provider="default")
    desc = provider.get_description("lookup_entity", default_doc="Original default docstring.")
    assert "Original default docstring." in desc


def test_mcp_provider_gepa():
    """GEPA provider should return optimized prompt descriptions from gusto-mcp-gepa."""
    provider = McpToolProvider(provider="gepa")
    desc = provider.get_description("lookup_entity", default_doc="Original default docstring.")
    assert "Look up an entity (IP, domain, hash, user, etc.) in Chronicle SIEM for enrichment." in desc
    assert "This tool queries Chronicle SIEM directly." in desc

    ip_desc = provider.get_description("get_ip_address_report", default_doc="Original IP doc.")
    assert "Google Threat Intelligence" in ip_desc
    assert "Provides geolocation, autonomous system details" in ip_desc


def test_mcp_provider_aliases():
    """GEPA provider should resolve aliases for live MCP tool names."""
    provider = McpToolProvider(provider="gepa")
    
    # udm_search -> search_udm
    udm_desc = provider.get_description("udm_search", default_doc="Old UDM search.")
    assert "Search UDM events using UDM query in Chronicle." in udm_desc

    # get_case -> get_case_full_details
    case_desc = provider.get_description("get_case", default_doc="Old get case.")
    assert "Retrieve comprehensive details for a specific case" in case_desc

    # fetch_alert_data -> get_security_alert_by_id
    alert_desc = provider.get_description("fetch_alert_data", default_doc="Old fetch alert.")
    assert "Get security alert by ID directly from Chronicle SIEM." in alert_desc


def test_soc_tier1_agent_build_tools_description_default():
    """SocTier1Agent with default provider should use standard docstrings."""
    agent = SocTier1Agent(mcp_provider="default")
    tools_desc = agent._build_tools_description()
    assert "lookup_entity" in tools_desc
    assert "Looks up SIEM telemetry and event history for a user, host, or IP." in tools_desc


def test_soc_tier1_agent_build_tools_description_gepa():
    """SocTier1Agent with gepa provider should dynamically inject GEPA descriptions."""
    agent = SocTier1Agent(mcp_provider="gepa")
    tools_desc = agent._build_tools_description()
    assert "lookup_entity" in tools_desc
    assert "Look up an entity (IP, domain, hash, user, etc.) in Chronicle SIEM for enrichment." in tools_desc
    assert "get_ip_address_report" in tools_desc
    assert "Google Threat Intelligence" in tools_desc
