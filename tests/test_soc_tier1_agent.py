import json
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
    assert "Evidence-Based Investigation" in SOC_TIER1_PERSONA
    assert "Grounded Threat Attribution" in SOC_TIER1_PERSONA



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
    with patch.object(agent, "_call_llm_step") as mock_step:
        mock_step.return_value = ("Final Answer: Triage complete", {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})
        result = agent.query(prompt="Analyze alert")
        mock_step.assert_called_once()
        assert "Triage complete" in result["response"]
        assert result["usage"]["total_tokens"] == 15


def test_react_loop_executes_tool_and_returns_grounded_answer():
    agent = SocTier1Agent()
    step_outputs = [
        ('Thought: I need to check IP reputation.\nAction: get_ip_address_report(ip="192.0.2.100")', {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30}),
        ('Thought: IP is benign documentation network.\nFinal Answer:\n[Context & Enrichment]\n192.0.2.100 is RFC-5737 test IP.\n\n[Analysis & Verdict]\nBENIGN documentation artifact.\n\n[Action & Escalation]\nClose alert.\n\n[SOAR Documentation]\nDocumented.', {"prompt_tokens": 40, "completion_tokens": 20, "total_tokens": 60}),
    ]
    with patch.object(agent, "_call_llm_step", side_effect=step_outputs):
        result = agent.query(prompt="Triage alert for IP 192.0.2.100")
        assert "trajectory" in result
        assert len(result["trajectory"]) == 1
        assert result["trajectory"][0]["tool"] == "get_ip_address_report"
        assert result["trajectory"][0]["args"] == {"ip": "192.0.2.100"}
        assert "RFC-5737" in result["trajectory"][0]["observation"]
        assert "BENIGN documentation artifact" in result["response"]
        assert result["usage"]["total_tokens"] == 90


def test_react_loop_handles_json_action():
    agent = SocTier1Agent()
    step_outputs = [
        ('```json\n{"tool": "lookup_entity", "args": {"entity": "10.0.4.15"}}\n```', {"prompt_tokens": 15, "completion_tokens": 5, "total_tokens": 20}),
        ('Final Answer:\n[Context & Enrichment]\nInternal workstation.\n\n[Analysis & Verdict]\nBENIGN internal.\n\n[Action & Escalation]\nNo action.\n\n[SOAR Documentation]\nLogged.', {"prompt_tokens": 25, "completion_tokens": 15, "total_tokens": 40}),
    ]
    with patch.object(agent, "_call_llm_step", side_effect=step_outputs):
        result = agent.query(prompt="Lookup 10.0.4.15")
        assert len(result["trajectory"]) == 1
        assert result["trajectory"][0]["tool"] == "lookup_entity"
        assert result["trajectory"][0]["args"] == {"entity": "10.0.4.15"}
        assert "10.0.4.15" in result["trajectory"][0]["observation"]
        assert "Internal workstation" in result["response"]
        assert result["usage"]["total_tokens"] == 60


def test_react_loop_max_iterations():
    agent = SocTier1Agent()
    step_outputs = [
        ('Action: list_cases(entity="test")', {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}),
        ('Action: list_cases(entity="test")', {"prompt_tokens": 15, "completion_tokens": 5, "total_tokens": 20}),
        ('Action: list_cases(entity="test")', {"prompt_tokens": 20, "completion_tokens": 5, "total_tokens": 25}),
    ]
    with patch.object(agent, "_call_llm_step", side_effect=step_outputs):
        result = agent.query(prompt="Loop test", max_iterations=2)
        assert len(result["trajectory"]) == 2
        assert "Reached maximum investigation iterations" in result["response"]
        assert result["usage"]["total_tokens"] == 35


def test_react_loop_handles_tool_error_gracefully():
    """Verify ReAct loop surfaces tool error JSON to agent context without crashing."""
    agent = SocTier1Agent()
    
    # 1. Verify direct execution of tool call handles error dict correctly
    res = agent._execute_tool_action("get_domain_report", {"domain": "error-503.service-unavailable.org"})
    parsed = json.loads(res)
    assert parsed["status_code"] == 503
    assert "HTTP 503" in parsed["error"]

    # 2. Verify ReAct loop carries error JSON into prompt observation
    step_outputs = [
        ('Thought: Checking domain reputation.\nAction: get_domain_report(domain="error-503.service-unavailable.org")', {"prompt_tokens": 15, "completion_tokens": 10, "total_tokens": 25}),
        ('Thought: The upstream service is unavailable with HTTP 503.\nFinal Answer:\n[Context & Enrichment]\nDomain lookup failed with HTTP 503 error.\n\n[Analysis & Verdict]\nSUSPICIOUS\n\n[Action & Escalation]\nEscalate for manual inspection.\n\n[SOAR Documentation]\nLogged upstream service failure.', {"prompt_tokens": 35, "completion_tokens": 20, "total_tokens": 55}),
    ]
    with patch.object(agent, "_call_llm_step", side_effect=step_outputs):
        result = agent.query(prompt="Triage domain error-503.service-unavailable.org")
        assert len(result["trajectory"]) == 1
        assert result["trajectory"][0]["tool"] == "get_domain_report"
        obs = result["trajectory"][0]["observation"]
        obs_parsed = json.loads(obs)
        assert obs_parsed["status_code"] == 503
        assert "HTTP 503" in obs_parsed["error"]
        assert "Domain lookup failed with HTTP 503 error" in result["response"]


def test_execute_tool_action_handles_invalid_tool_name():
    """Verify _execute_tool_action returns structured error JSON when tool is not registered."""
    agent = SocTier1Agent()
    res = agent._execute_tool_action("unknown_secops_tool", {"param": "val"})
    parsed = json.loads(res)
    assert parsed["status"] == "ERROR"
    assert "Tool 'unknown_secops_tool' not found" in parsed["error"]


def test_execute_tool_action_handles_unexpected_exception():
    """Verify _execute_tool_action wraps unexpected exceptions in structured error JSON."""
    agent = SocTier1Agent()
    def failing_tool(arg: str):
        raise RuntimeError("Simulated crash in tool execution")

    with patch.dict(agent.tools_dict, {"failing_tool": failing_tool}):
        res = agent._execute_tool_action("failing_tool", {"arg": "test"})
        parsed = json.loads(res)
        assert parsed["status"] == "ERROR"
        assert parsed["error"] == "Tool execution failed: Simulated crash in tool execution"


def test_execute_tool_action_handles_dict_or_json_output():
    """Verify _execute_tool_action returns valid JSON string payloads for standard tools."""
    agent = SocTier1Agent()
    res = agent._execute_tool_action("get_ip_address_report", {"ip": "10.0.99.50"})
    parsed = json.loads(res)
    assert parsed["ip"] == "10.0.99.50"
    assert parsed["reputation"] == "BENIGN_AUTHORIZED"


def test_execute_tool_alias_matches_execute_tool_action():
    """Verify _execute_tool delegates to _execute_tool_action."""
    agent = SocTier1Agent()
    res1 = agent._execute_tool_action("lookup_entity", {"entity_id": "10.0.8.99"})
    res2 = agent._execute_tool("lookup_entity", {"entity_id": "10.0.8.99"})
    assert res1 == res2
    parsed = json.loads(res2)
    assert parsed["entity"] == "10.0.8.99"



