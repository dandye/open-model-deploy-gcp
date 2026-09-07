import json
from unittest.mock import MagicMock, patch
from agent.gemma_agent import GemmaAgent
from agent.soc_tier1_agent import (
    SOC_ANALYST_PERSONA,
    SOC_TIER1_PERSONA,
    SocDecision,
    SocTier1Agent,
    extract_soc_decision,
)
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
    assert "soc_decision" in SOC_TIER1_PERSONA
    assert "soc_decision" in SOC_ANALYST_PERSONA
    assert SOC_ANALYST_PERSONA == SOC_TIER1_PERSONA



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


def test_soc_agent_query_unbounded_max_tokens_default():
    """Verify SocTier1Agent.query defaults max_tokens to None and passes explicit max_tokens."""
    agent = SocTier1Agent()
    with patch.object(agent, "_call_llm_step") as mock_step:
        mock_step.return_value = (
            "Final Answer: Done",
            {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        )

        # Default invocation should pass max_tokens=None
        agent.query(prompt="Analyze alert")
        mock_step.assert_called_once()
        prompt_arg, = mock_step.call_args[0]
        assert "Analyze alert" in prompt_arg
        assert mock_step.call_args[1]["max_tokens"] is None

        # Explicit invocation should pass explicit max_tokens
        mock_step.reset_mock()
        agent.query(prompt="Analyze alert", max_tokens=2048)
        mock_step.assert_called_once()
        assert mock_step.call_args[1]["max_tokens"] == 2048


def test_soc_agent_call_llm_step_unbounded_max_tokens_default():
    """Verify SocTier1Agent._call_llm_step delegates max_tokens=None to super().query."""
    agent = SocTier1Agent()
    with patch("agent.gemma_agent.GemmaAgent.query") as mock_super_query:
        mock_super_query.return_value = {
            "response": "Step reasoning output",
            "backend": "MockBackend",
            "usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
        }

        # Default invocation should delegate max_tokens=None
        resp, usage = agent._call_llm_step(prompt="Step instruction")
        assert resp == "Step reasoning output"
        mock_super_query.assert_called_once_with(
            prompt="Step instruction",
            max_tokens=None,
            temperature=0.2,
        )

        # Explicit invocation should delegate explicit max_tokens
        mock_super_query.reset_mock()
        resp2, usage2 = agent._call_llm_step(prompt="Step instruction", max_tokens=512)
        assert resp2 == "Step reasoning output"
        mock_super_query.assert_called_once_with(
            prompt="Step instruction",
            max_tokens=512,
            temperature=0.2,
        )


def test_gemma_agent_query_cloudrun_unbounded_token_headroom():
    """Verify GemmaAgent uses 8192 headroom on Cloud Run when max_tokens is None."""
    agent = GemmaAgent(cloudrun_url="https://mock-cloudrun-service.a.run.app")
    captured_payloads = []

    def mock_urlopen(req, timeout=600):
        body = json.loads(req.data.decode("utf-8"))
        captured_payloads.append(body)
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "choices": [{"message": {"content": "Cloud Run response"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
        }).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        return mock_resp

    mock_creds = MagicMock()
    mock_creds.valid = True
    mock_creds.token = "mock-bearer-token"

    with patch("google.auth.default", return_value=(mock_creds, "test-project")), \
         patch("urllib.request.urlopen", side_effect=mock_urlopen):
        # Default max_tokens=None should produce 8192 in payload
        res_default = agent.query(prompt="Test prompt")
        assert res_default["backend"] == "Cloud Run GPU"
        assert captured_payloads[-1]["max_tokens"] == 8192

        # Explicit max_tokens should produce explicit value in payload
        res_explicit = agent.query(prompt="Test prompt", max_tokens=1024)
        assert captured_payloads[-1]["max_tokens"] == 1024


def test_gemma_agent_query_vertex_unbounded_token_headroom():
    """Verify GemmaAgent uses 8192 headroom on Vertex AI Prediction when max_tokens is None."""
    agent = GemmaAgent(endpoint_id="1234567890", region="us-central1")
    captured_instances = []

    mock_endpoint_obj = MagicMock()

    def mock_predict(instances):
        captured_instances.append(instances)
        mock_res = MagicMock()
        mock_res.predictions = ["Vertex response text"]
        return mock_res

    mock_endpoint_obj.predict.side_effect = mock_predict

    with patch("google.cloud.aiplatform.Endpoint", return_value=mock_endpoint_obj):
        # Default max_tokens=None should produce 8192 in instances payload
        res_default = agent.query(prompt="Test Vertex prompt")
        assert res_default["backend"] == "Vertex AI Online Prediction"
        assert captured_instances[-1][0]["max_tokens"] == 8192

        # Explicit max_tokens should produce explicit value in instances payload
        res_explicit = agent.query(prompt="Test Vertex prompt", max_tokens=512)
        assert captured_instances[-1][0]["max_tokens"] == 512


def test_gemma_agent_query_maas_unbounded_token_budgeting():
    """Verify GemmaAgent omits max_output_tokens when max_tokens is None for MaaS."""
    agent = GemmaAgent(managed_model="gemini-2.5-pro")
    captured_configs = []

    mock_client = MagicMock()
    mock_chat = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "MaaS frontier response"
    mock_response.usage_metadata = MagicMock(
        prompt_token_count=15,
        candidates_token_count=20,
        total_token_count=35,
    )
    mock_chat.send_message.return_value = mock_response

    def mock_create(model, config):
        captured_configs.append(config)
        return mock_chat

    mock_client.chats.create.side_effect = mock_create

    mock_creds = MagicMock()
    mock_creds.valid = True

    with patch("google.auth.default", return_value=(mock_creds, "test-project")), \
         patch("google.genai.Client", return_value=mock_client), \
         patch.object(agent, "discover_active_vertex_endpoint", side_effect=AssertionError("Explicit managed model must not discover another backend")) as discover:
        # Default max_tokens=None should omit max_output_tokens (None)
        res_default = agent.query(prompt="Complex multi-step reasoning prompt")
        assert "MaaS" in res_default["backend"]
        assert captured_configs[-1].max_output_tokens is None

        # Explicit max_tokens should set max_output_tokens
        res_explicit = agent.query(prompt="Targeted prompt", max_tokens=4096)
        assert captured_configs[-1].max_output_tokens == 4096
        discover.assert_not_called()


def test_parse_action_react_syntax():
    """Verify _parse_action parses standard ReAct function call syntax."""
    agent = SocTier1Agent()
    parsed = agent._parse_action('Action: isolate_host(hostname="DESKTOP-FIN-08")')
    assert parsed is not None
    tool_name, args = parsed
    assert tool_name == "isolate_host"
    assert args == {"hostname": "DESKTOP-FIN-08"}

    # Multiple keyword arguments
    parsed_multi = agent._parse_action(
        'Action: update_case_comment(case_id="CASE-101", comment="Host isolated.")'
    )
    assert parsed_multi is not None
    tool_name, args = parsed_multi
    assert tool_name == "update_case_comment"
    assert args == {"case_id": "CASE-101", "comment": "Host isolated."}

    # Positional argument with known fallback
    parsed_pos = agent._parse_action('Action: isolate_host("DESKTOP-FIN-08")')
    assert parsed_pos is not None
    tool_name, args = parsed_pos
    assert tool_name == "isolate_host"
    assert args == {"hostname": "DESKTOP-FIN-08"}


def test_parse_action_json_name_arguments():
    """Verify _parse_action parses JSON payload with name and arguments."""
    agent = SocTier1Agent()
    parsed = agent._parse_action(
        'Action: {"name": "get_ip_address_report", "arguments": {"ip": "192.0.2.100"}}'
    )
    assert parsed is not None
    tool_name, args = parsed
    assert tool_name == "get_ip_address_report"
    assert args == {"ip": "192.0.2.100"}

    # Standalone JSON object without Action: prefix
    parsed_standalone = agent._parse_action(
        '{"name": "get_ip_address_report", "arguments": {"ip": "192.0.2.100"}}'
    )
    assert parsed_standalone is not None
    tool_name, args = parsed_standalone
    assert tool_name == "get_ip_address_report"
    assert args == {"ip": "192.0.2.100"}


def test_parse_action_json_tool_args():
    """Verify _parse_action parses JSON payload with tool and args or parameters."""
    agent = SocTier1Agent()
    parsed = agent._parse_action(
        'Action: {"tool": "block_indicator", "args": {"indicator": "evil.com"}}'
    )
    assert parsed is not None
    tool_name, args = parsed
    assert tool_name == "block_indicator"
    assert args == {"indicator": "evil.com"}

    # JSON with parameters key
    parsed_param = agent._parse_action(
        '{"tool": "get_domain_report", "parameters": {"domain": "phishing.xyz"}}'
    )
    assert parsed_param is not None
    tool_name, args = parsed_param
    assert tool_name == "get_domain_report"
    assert args == {"domain": "phishing.xyz"}


def test_parse_action_fenced_blocks():
    """Verify _parse_action parses fenced tool_call and call:<tool_name> blocks."""
    agent = SocTier1Agent()
    # tool_call fenced block
    fenced_tool_call = '```tool_call\n{"name": "close_case", "args": {"case_id": "CASE-01"}}\n```'
    parsed = agent._parse_action(fenced_tool_call)
    assert parsed is not None
    tool_name, args = parsed
    assert tool_name == "close_case"
    assert args == {"case_id": "CASE-01"}

    # call:<tool_name> fenced block
    fenced_call = '```call:isolate_host\n{"hostname": "DESKTOP-FIN-08"}\n```'
    parsed_call = agent._parse_action(fenced_call)
    assert parsed_call is not None
    tool_name, args = parsed_call
    assert tool_name == "isolate_host"
    assert args == {"hostname": "DESKTOP-FIN-08"}


def test_parse_action_ignores_soc_decision_and_non_actions():
    """Verify _parse_action does not parse soc_decision or non-action strings."""
    agent = SocTier1Agent()
    soc_decision_str = (
        "```soc_decision\n"
        "{\n"
        '  "verdict": "BENIGN",\n'
        '  "recommended_actions": ["close_case"],\n'
        '  "target_entity": "10.0.1.5",\n'
        '  "rationale": "Benign entity"\n'
        "}\n"
        "```"
    )
    assert agent._parse_action(soc_decision_str) is None
    assert agent._parse_action("Thought: I am analyzing the alert.") is None
    assert agent._parse_action("") is None


def test_react_loop_handles_json_action_full_investigation():
    """Verify full ReAct loop handles JSON action and produces grounded final triage report."""
    agent = SocTier1Agent()
    step_outputs = [
        (
            'Thought: I need to query the IP address report.\n'
            'Action: {"name": "get_ip_address_report", "arguments": {"ip": "192.0.2.100"}}',
            {"prompt_tokens": 25, "completion_tokens": 15, "total_tokens": 40},
        ),
        (
            'Thought: The IP address is in the documentation test range and is benign.\n'
            'Final Answer:\n'
            '[Context & Enrichment]\n'
            '- IP: 192.0.2.100 (TEST-NET-1)\n\n'
            '[Analysis & Verdict]\n'
            'Verdict: BENIGN\n'
            'Documentation network address with no adversary association.\n\n'
            '[Action & Escalation]\n'
            'Close case without further containment.\n\n'
            '[SOAR Documentation]\n'
            'Alert closed as benign documentation artifact.\n\n'
            '```soc_decision\n'
            '{\n'
            '  "verdict": "BENIGN",\n'
            '  "recommended_actions": ["close_case"],\n'
            '  "target_entity": "192.0.2.100",\n'
            '  "rationale": "Documentation test address."\n'
            '}\n'
            '```',
            {"prompt_tokens": 45, "completion_tokens": 30, "total_tokens": 75},
        ),
    ]

    with patch.object(agent, "_call_llm_step", side_effect=step_outputs):
        result = agent.query(prompt="Triage alert for 192.0.2.100")
        assert len(result["trajectory"]) == 1
        assert result["trajectory"][0]["tool"] == "get_ip_address_report"
        assert result["trajectory"][0]["args"] == {"ip": "192.0.2.100"}
        assert "RFC-5737" in result["trajectory"][0]["observation"]

        resp = result["response"]
        assert "[Context & Enrichment]" in resp
        assert "BENIGN" in resp
        assert "[Action & Escalation]" in resp
        assert "[SOAR Documentation]" in resp

        decision = extract_soc_decision(resp)
        assert decision is not None
        assert decision.verdict == "BENIGN"
        assert "close_case" in decision.recommended_actions
        assert decision.target_entity == "192.0.2.100"


def test_soc_persona_exemplar_present():
    """Verify SOC_TIER1_PERSONA contains the few-shot interaction exemplar."""
    assert "Investigation Cycle Exemplar" in SOC_TIER1_PERSONA
    assert "Thought: The alert references external IP" in SOC_TIER1_PERSONA
    assert "Action: get_ip_address_report" in SOC_TIER1_PERSONA
    assert "Observation:" in SOC_TIER1_PERSONA
    assert "Final Answer:" in SOC_TIER1_PERSONA
    assert "soc_decision" in SOC_TIER1_PERSONA


def test_react_step0_reflection_on_missing_tools():
    # Setup mock agent that tries to output final answer in step 0, then calls tool in step 1
    agent = SocTier1Agent()
    step0_resp = """Final Answer:
[Context & Enrichment]
Host isolated.
    ```soc_decision
{"verdict": "MALICIOUS", "recommended_actions": ["isolate_host"]}
    ```"""
    step1_resp = """Thought: I need to query threat intelligence.
Action: get_domain_report(domain="evil.com")"""
    step2_resp = """Thought: Domain confirmed malicious.
Action: isolate_host(hostname="DESKTOP-01")"""
    step3_resp = """Final Answer:
[Context & Enrichment]
Confirmed malware.
    ```soc_decision
{"verdict": "MALICIOUS", "recommended_actions": ["isolate_host"]}
    ```"""

    agent._call_llm_step = MagicMock(side_effect=[
        (step0_resp, {}),
        (step1_resp, {}),
        (step2_resp, {}),
        (step3_resp, {}),
    ])
    agent._execute_tool_action = MagicMock(return_value='{"status": "SUCCESS"}')

    result = agent.query("Triage alert for host DESKTOP-01 connecting to evil.com. Query threat intelligence.")
    assert len(result["trajectory"]) >= 1
    assert agent._call_llm_step.call_count >= 2


def test_react_step0_reflection_skipped_when_prompt_not_investigative():
    agent = SocTier1Agent()
    step0_resp = """Final Answer:
This is a general summary of past policies."""
    agent._call_llm_step = MagicMock(return_value=(step0_resp, {}))

    result = agent.query("Summarize past policies and architecture principles.")
    assert len(result["trajectory"]) == 0
    assert agent._call_llm_step.call_count == 1
    assert "This is a general summary" in result["response"]


def test_react_step0_reflection_triggered_on_direct_structured_report():
    agent = SocTier1Agent()
    step0_resp = """[Context & Enrichment]
Host 10.0.0.5 seen.
[Analysis & Verdict]
Verdict: BENIGN
[Action & Escalation]
Close alert.
[SOAR Documentation]
Clean."""
    step1_resp = """Thought: Let me check IP report.
Action: get_ip_address_report(ip="10.0.0.5")"""
    step2_resp = """Final Answer:
[Context & Enrichment]
Host 10.0.0.5 verified benign internal IP.
[Analysis & Verdict]
Verdict: BENIGN
```soc_decision
{"verdict": "BENIGN", "recommended_actions": ["close_case"]}
```"""

    agent._call_llm_step = MagicMock(side_effect=[
        (step0_resp, {}),
        (step1_resp, {}),
        (step2_resp, {}),
    ])
    agent._execute_tool_action = MagicMock(return_value='{"status": "CLEAN"}')

    result = agent.query("Investigate suspicious traffic from host 10.0.0.5.")
    assert len(result["trajectory"]) == 1
    assert agent._call_llm_step.call_count == 3
    assert result["trajectory"][0]["tool"] == "get_ip_address_report"


def test_react_step0_reflection_max_iterations_one():
    agent = SocTier1Agent()
    step0_resp = """Final Answer:
Triage done directly."""
    agent._call_llm_step = MagicMock(return_value=(step0_resp, {}))

    result = agent.query("Triage alert for host 10.0.0.5.", max_iterations=1)
    assert len(result["trajectory"]) == 0
    assert agent._call_llm_step.call_count == 1
    assert "Triage done directly" in result["response"]


def test_soc_persona_investigation_tool_requirement():
    assert "You must invoke at least one investigation tool" in SOC_TIER1_PERSONA






