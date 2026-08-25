"""Unit tests for SocTier1Agent class."""

from unittest.mock import patch
from agent.soc_tier1_agent import SOC_TIER1_PERSONA, SocTier1Agent
from agent.soc_tools import (
    get_domain_report,
    get_file_report,
    get_ip_address_report,
    list_cases,
    lookup_entity,
    post_case_comment,
)


def test_soc_agent_init():
    agent = SocTier1Agent(project_id="test-project", region="us-central1")
    assert agent.name == "soc_analyst_tier1"
    assert agent.project_id == "test-project"
    assert agent.region == "us-central1"
    assert "Tier 1 Security Operations Center" in agent.system_instruction
    assert len(agent.tools) == 6
    expected_tools = [
        lookup_entity,
        get_ip_address_report,
        get_domain_report,
        get_file_report,
        list_cases,
        post_case_comment,
    ]
    for tool in expected_tools:
        assert tool in agent.tools


def test_soc_agent_custom_backend_args():
    agent = SocTier1Agent(
        endpoint_id="1234567890",
        cloudrun_url="https://gemma-run.a.run.app",
        managed_model="gemma-4-26b-a4b-it",
    )
    assert agent.endpoint_id == "1234567890"
    assert agent.cloudrun_url == "https://gemma-run.a.run.app"
    assert agent.managed_model == "gemma-4-26b-a4b-it"


def test_soc_persona_sections():
    assert "Context & Enrichment" in SOC_TIER1_PERSONA
    assert "Analysis & Verdict" in SOC_TIER1_PERSONA
    assert "Action & Escalation" in SOC_TIER1_PERSONA
    assert "SOAR Documentation" in SOC_TIER1_PERSONA
    assert "RFC-5737" in SOC_TIER1_PERSONA


def test_format_soc_prompt_with_context():
    agent = SocTier1Agent()
    formatted = agent.format_triage_prompt(
        query="Triage alert for IP 192.0.2.100",
        context={"case_id": "CASE-101", "source": "Firewall"},
    )
    assert "Operational Triage Request:" in formatted
    assert "192.0.2.100" in formatted
    assert "- case_id: CASE-101" in formatted
    assert "- source: Firewall" in formatted
    assert "Perform initial investigation" in formatted


def test_format_soc_prompt_without_context():
    agent = SocTier1Agent()
    assert agent.format_triage_prompt("Direct query with no context") == "Direct query with no context"
    assert agent.format_triage_prompt("Direct query with empty context", context={}) == "Direct query with empty context"


def test_query_default_temperature_and_tokens():
    agent = SocTier1Agent()
    with patch("agent.gemma_agent.GemmaAgent.query") as mock_super_query:
        mock_super_query.return_value = {"response": "Triage complete", "backend": "Mock"}
        result = agent.query(prompt="Analyze alert")
        mock_super_query.assert_called_once_with(
            prompt="Analyze alert",
            max_tokens=1024,
            temperature=0.2,
        )
        assert result["response"] == "Triage complete"
