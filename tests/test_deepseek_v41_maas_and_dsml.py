"""Hermetic unit tests for DeepSeek-V4.1-Flash Vertex OpenMaaS transport,
deepseek_v41 reasoning/tool-call bridging, DSML fallback parsing, and OpenMaaS benchmarking.
"""

import base64
from concurrent.futures import Future
from http.client import HTTPResponse
from io import BufferedReader, BytesIO, RawIOBase
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Tuple
from unittest.mock import MagicMock, patch
import urllib.error

import pytest

from agent.gemma_agent import (
    GemmaAgent,
    _build_open_maas_url,
    _extract_openai_chat_message,
    _is_open_maas_model,
    _resolve_managed_model_and_region,
)
from agent.soc_tier1_agent import (
    SocTier1Agent,
    extract_soc_decision,
    parse_dsml_tool_call,
)
from scripts.benchmark import (
    BenchmarkRunner,
    main as benchmark_main,
    resolve_open_maas_target,
)


def _mock_http_response(payload: Dict[str, Any], status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status = status
    raw = json.dumps(payload).encode("utf-8")
    resp.read.return_value = raw
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    return resp


def _http_error(url: str, code: int, body_obj: Any) -> urllib.error.HTTPError:
    raw = (
        body_obj.encode("utf-8")
        if isinstance(body_obj, str)
        else json.dumps(body_obj).encode("utf-8")
    )
    return urllib.error.HTTPError(
        url=url,
        code=code,
        msg=f"HTTP Error {code}",
        hdrs=None,
        fp=BytesIO(raw),
    )


# ---------------------------------------------------------------------------
# 1. OpenMaaS URL Routing, Catalog Resolution, and Non-Regression Tests
# ---------------------------------------------------------------------------


def test_open_maas_url_routing_global_vs_regional():
    assert _build_open_maas_url("proj-123", "global") == (
        "https://aiplatform.googleapis.com/v1/projects/proj-123"
        "/locations/global/endpoints/openapi/chat/completions"
    )
    assert _build_open_maas_url("proj-123", "europe-west4") == (
        "https://europe-west4-aiplatform.googleapis.com/v1/projects/proj-123"
        "/locations/europe-west4/endpoints/openapi/chat/completions"
    )


def test_resolve_managed_model_bare_and_prefixed_deepseek_and_catalog():
    mock_catalog = {
        "deepseek-v4.1-flash-1017-maas": {
            "type": "maas",
            "provider": "deepseek-ai",
            "maasModelId": "deepseek-ai/deepseek-v4.1-flash-1017-maas",
            "modelId": "deepseek-ai/deepseek-v4.1-flash-1017-maas",
            "region": "global",
        },
        "deepseek-v4.1-flash-maas": {
            "type": "maas",
            "provider": "deepseek-ai",
            "maasModelId": "deepseek-ai/deepseek-v4.1-flash-maas",
            "modelId": "deepseek-ai/deepseek-v4.1-flash-maas",
            "region": "global",
        },
    }
    # Bare catalog key with default us-central1 -> resolves to slash-prefixed ID on global
    m1, r1 = _resolve_managed_model_and_region(
        "deepseek-v4.1-flash-1017-maas", "us-central1", catalog=mock_catalog
    )
    assert m1 == "deepseek-ai/deepseek-v4.1-flash-1017-maas"
    assert r1 == "global"

    # Bare deepseek-*-maas even WITHOUT catalog entry (pre-merge isolation) -> auto-prefixes & global
    m2, r2 = _resolve_managed_model_and_region(
        "deepseek-v4.1-flash-1017-maas", "us-central1", catalog={}
    )
    assert m2 == "deepseek-ai/deepseek-v4.1-flash-1017-maas"
    assert r2 == "global"

    # Already prefixed deepseek-ai/*-maas with default us-central1 -> global
    m3, r3 = _resolve_managed_model_and_region(
        "deepseek-ai/deepseek-v4.1-flash-maas", "us-central1", catalog={}
    )
    assert m3 == "deepseek-ai/deepseek-v4.1-flash-maas"
    assert r3 == "global"

    # Regional partner OpenMaaS model with explicit non-default region
    m4, r4 = _resolve_managed_model_and_region(
        "mistralai/codestral-2-maas", "europe-west4", catalog={}
    )
    assert m4 == "mistralai/codestral-2-maas"
    assert r4 == "europe-west4"


def test_is_open_maas_model_partner_vs_genai_models():
    # Partner OpenMaaS models -> True
    assert _is_open_maas_model("deepseek-ai/deepseek-v4.1-flash-1017-maas") is True
    assert _is_open_maas_model("deepseek-ai/deepseek-v4.1-flash-maas") is True
    assert _is_open_maas_model("qwen/qwen3-coder-480b-a35b-instruct-maas") is True
    assert _is_open_maas_model("mistralai/codestral-2-maas") is True

    # Gemini, Gemma MaaS, Meta Llama MaaS -> False (stay on google.genai)
    assert _is_open_maas_model("gemini-2.5-flash") is False
    assert _is_open_maas_model("gemini-3.1-pro-preview") is False
    assert _is_open_maas_model("gemma-4-26b-a4b-it-maas") is False
    assert _is_open_maas_model("google/gemma-4-26b-a4b-it-maas") is False
    assert _is_open_maas_model("meta/llama-4-maverick-17b-128e-instruct-maas") is False
    assert _is_open_maas_model("meta/llama-3.3-70b-instruct-maas") is False


@pytest.mark.parametrize(
    "genai_model,expected_resolved_model,expected_location",
    [
        ("gemini-2.5-flash", "gemini-2.5-flash", "us-central1"),
        ("gemma-4-26b-a4b-it-maas", "gemma-4-26b-a4b-it-maas", "global"),
        (
            "llama-4-maverick-17b-128e-instruct-maas",
            "meta/llama-4-maverick-17b-128e-instruct-maas",
            "us-east5",
        ),
        (
            "meta/llama-3.3-70b-instruct-maas",
            "meta/llama-3.3-70b-instruct-maas",
            "us-central1",
        ),
    ],
)
def test_non_regression_google_genai_routing(
    genai_model: str, expected_resolved_model: str, expected_location: str
):
    """Gemini, gemma-4-*-maas, and meta/llama-*-maas must continue using google.genai."""
    agent = GemmaAgent(
        project_id="test-proj", region="us-central1", managed_model=genai_model
    )
    mock_client = MagicMock()
    mock_chat = MagicMock()
    mock_res = MagicMock()
    mock_res.text = "genai ok"
    mock_res.candidates = []
    mock_res.usage_metadata = MagicMock(
        prompt_token_count=11, candidates_token_count=4, total_token_count=15
    )
    mock_chat.send_message.return_value = mock_res
    mock_client.chats.create.return_value = mock_chat

    with patch("google.genai.Client", return_value=mock_client) as client_cls, patch(
        "urllib.request.urlopen",
        side_effect=AssertionError("urlopen must not be called for google.genai models"),
    ):
        out = agent.query("ping")

    assert out["response"] == "genai ok"
    assert out["model"] == expected_resolved_model
    assert out["region"] == expected_location
    client_cls.assert_called_once()
    assert client_cls.call_args.kwargs["location"] == expected_location
    mock_client.chats.create.assert_called_once()
    assert mock_client.chats.create.call_args.kwargs["model"] == expected_resolved_model


# ---------------------------------------------------------------------------
# 2. OpenMaaS Auth Refresh, Retries, Fast-Fail, Multimodal, and Usage Tests
# ---------------------------------------------------------------------------


def test_open_maas_bearer_refresh_multimodal_payload_and_actual_usage():
    agent = GemmaAgent(
        project_id="secops-test-proj",
        region="us-central1",
        managed_model="deepseek-v4.1-flash-1017-maas",
        system_instruction="SOC System Persona",
    )

    mock_creds = MagicMock()
    mock_creds.valid = False
    mock_creds.token = None

    def _refresh(req):
        mock_creds.valid = True
        mock_creds.token = "refreshed-adc-token-xyz"

    mock_creds.refresh.side_effect = _refresh

    captured_requests: List[urllib.request.Request] = []

    def _fake_urlopen(req, timeout=300):
        captured_requests.append(req)
        return _mock_http_response(
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Screenshot shows phishing login portal.",
                            "reasoning_content": "Inspecting DOM and logo.",
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": 312,
                    "completion_tokens": 48,
                    "total_tokens": 360,
                    "completion_tokens_details": {"reasoning_tokens": 19},
                },
            }
        )

    tools_schema = [
        {
            "type": "function",
            "function": {
                "name": "get_domain_report",
                "parameters": {"type": "object", "properties": {"domain": {"type": "string"}}},
            },
        }
    ]
    img_url = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

    with patch("google.auth.default", return_value=(mock_creds, "secops-test-proj")), patch(
        "google.auth.transport.requests.Request", return_value=MagicMock()
    ), patch("urllib.request.urlopen", side_effect=_fake_urlopen):
        res = agent.query(
            prompt="Analyze login screenshot",
            max_tokens=None,
            temperature=0.2,
            image_urls=[img_url],
            tools_schema=tools_schema,
        )

    mock_creds.refresh.assert_called_once()
    assert len(captured_requests) == 1
    req = captured_requests[0]
    assert req.full_url == (
        "https://aiplatform.googleapis.com/v1/projects/secops-test-proj"
        "/locations/global/endpoints/openapi/chat/completions"
    )
    auth_header = req.headers.get("Authorization") or req.headers.get("authorization")
    assert auth_header == "Bearer refreshed-adc-token-xyz"

    sent_body = json.loads(req.data.decode("utf-8"))
    assert sent_body["model"] == "deepseek-ai/deepseek-v4.1-flash-1017-maas"
    # max_tokens=None must omit "max_tokens" so reasoning models are not truncated
    assert "max_tokens" not in sent_body
    assert sent_body["tools"] == tools_schema
    assert sent_body["messages"][0] == {"role": "system", "content": "SOC System Persona"}
    assert sent_body["messages"][1] == {
        "role": "user",
        "content": [
            {"type": "text", "text": "Analyze login screenshot"},
            {"type": "image_url", "image_url": {"url": img_url}},
        ],
    }

    assert res["response"] == "Screenshot shows phishing login portal."
    assert res["reasoning_content"] == "Inspecting DOM and logo."
    assert res["region"] == "global"
    assert res["model"] == "deepseek-ai/deepseek-v4.1-flash-1017-maas"
    assert res["token_count_source"] == "actual"
    assert res["usage"] == {
        "prompt_tokens": 312,
        "completion_tokens": 48,
        "total_tokens": 360,
        "reasoning_tokens": 19,
        "token_count_source": "actual",
    }


def test_open_maas_regional_endpoint_and_explicit_max_tokens():
    agent = GemmaAgent(
        project_id="secops-test-proj",
        region="europe-west4",
        managed_model="mistralai/codestral-2-maas",
    )
    mock_creds = MagicMock(valid=True, token="tok-regional")
    captured: List[urllib.request.Request] = []

    def _fake_urlopen(req, timeout=300):
        captured.append(req)
        return _mock_http_response(
            {
                "choices": [{"message": {"content": "Regional response"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            }
        )

    with patch("google.auth.default", return_value=(mock_creds, "secops-test-proj")), patch(
        "urllib.request.urlopen", side_effect=_fake_urlopen
    ):
        res = agent.query("Check regional", max_tokens=1024, temperature=0.1)

    assert captured[0].full_url == (
        "https://europe-west4-aiplatform.googleapis.com/v1/projects/secops-test-proj"
        "/locations/europe-west4/endpoints/openapi/chat/completions"
    )
    body = json.loads(captured[0].data.decode("utf-8"))
    assert body["max_tokens"] == 1024
    assert body["messages"][1]["content"] == "Check regional"
    assert res["response"] == "Regional response"
    assert res["region"] == "europe-west4"


def test_open_maas_retries_429_and_503_with_exponential_backoff():
    agent = GemmaAgent(
        project_id="secops-test-proj",
        managed_model="deepseek-ai/deepseek-v4.1-flash-1017-maas",
    )
    url = _build_open_maas_url("secops-test-proj", "global")
    mock_creds = MagicMock(valid=True, token="tok")
    sleeps: List[float] = []

    side_effects = [
        _http_error(url, 429, {"error": {"message": "Rate limit exceeded"}}),
        _http_error(url, 503, {"error": {"message": "Backend overloaded"}}),
        _mock_http_response(
            {
                "choices": [{"message": {"content": "Recovered after backoff"}}],
                "usage": {"prompt_tokens": 20, "completion_tokens": 6, "total_tokens": 26},
            }
        ),
    ]

    with patch("google.auth.default", return_value=(mock_creds, "secops-test-proj")), patch(
        "urllib.request.urlopen", side_effect=side_effects
    ) as mock_open, patch("agent.gemma_agent.time.sleep", side_effect=sleeps.append):
        res = agent.query("Retry test")

    assert mock_open.call_count == 3
    assert len(sleeps) == 2
    assert sleeps[1] > sleeps[0] > 0
    assert res["response"] == "Recovered after backoff"


@pytest.mark.parametrize("status_code", [401, 403, 404])
def test_open_maas_fast_fails_without_retries_on_401_403_404(status_code: int):
    agent = GemmaAgent(
        project_id="secops-test-proj",
        managed_model="deepseek-v4.1-flash-1017-maas",
    )
    url = _build_open_maas_url("secops-test-proj", "global")
    mock_creds = MagicMock(valid=True, token="tok")

    err = _http_error(
        url,
        status_code,
        {"error": {"code": status_code, "message": "Model access not enabled for project"}},
    )

    with patch("google.auth.default", return_value=(mock_creds, "secops-test-proj")), patch(
        "urllib.request.urlopen", side_effect=err
    ) as mock_open, patch(
        "agent.gemma_agent.time.sleep",
        side_effect=AssertionError("Must not sleep/retry on 401/403/404"),
    ):
        res = agent.query("Access check")

    assert mock_open.call_count == 1
    assert res["status_code"] == status_code
    assert str(status_code) in res["error"]
    assert "Model access not enabled for project" in res["error"]
    if status_code in (403, 404):
        assert "MAAS_ACCESS_GATED" in res["error"]


# ---------------------------------------------------------------------------
# 3. deepseek_v41 Reasoning & Tool-Call Bridging Tests
# ---------------------------------------------------------------------------


def test_extract_openai_chat_message_serializes_tool_calls_before_reasoning_content():
    msg = {
        "role": "assistant",
        "content": None,
        "reasoning_content": "Wait, should I call isolate_host? No, check IP reputation first!",
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "get_ip_address_report",
                    "arguments": '{"ip": "198.51.100.25"}',
                },
            }
        ],
    }
    text, reasoning = _extract_openai_chat_message(msg)
    assert text == 'Action: {"name": "get_ip_address_report", "arguments": {"ip": "198.51.100.25"}}'
    assert "isolate_host" not in text
    assert reasoning == "Wait, should I call isolate_host? No, check IP reputation first!"


def test_extract_openai_chat_message_strips_think_tags_and_prevents_must_not_contain_pollution():
    msg = {
        "role": "assistant",
        "content": (
            "<think>\n"
            "The user might suspect FORBIDDEN_RED_HERRING_TOKEN or isolate_host, "
            "but telemetry proves RFC-5737 benign test traffic.\n"
            "</think>\n\n"
            "Final Answer:\n"
            "[Context & Enrichment]\n"
            "- IP 192.0.2.100 is RFC-5737 documentation space.\n\n"
            "[Analysis & Verdict]\n"
            "- Verdict: BENIGN"
        ),
    }
    text, reasoning = _extract_openai_chat_message(msg)
    assert "FORBIDDEN_RED_HERRING_TOKEN" not in text
    assert "<think>" not in text
    assert "</think>" not in text
    assert text.startswith("Final Answer:")
    assert reasoning is not None
    assert "FORBIDDEN_RED_HERRING_TOKEN" in reasoning


def test_extract_openai_chat_message_handles_closing_think_without_opening_tag():
    msg = {
        "role": "assistant",
        "content": "Internal deliberation about SECRET_COT_MARKER</think>\nClean final report.",
    }
    text, reasoning = _extract_openai_chat_message(msg)
    assert text == "Clean final report."
    assert "SECRET_COT_MARKER" not in text
    assert reasoning == "Internal deliberation about SECRET_COT_MARKER"


def test_extract_openai_chat_message_combines_clean_content_and_multiple_tool_calls():
    msg = {
        "role": "assistant",
        "content": "<think>Hidden thought</think>Thought: Enriching indicator.",
        "reasoning_content": "Explicit reasoning field",
        "tool_calls": [
            {
                "type": "function",
                "function": {"name": "lookup_entity", "arguments": {"entity": "host-01"}},
            }
        ],
    }
    text, reasoning = _extract_openai_chat_message(msg)
    assert text == (
        "Thought: Enriching indicator.\n"
        'Action: {"name": "lookup_entity", "arguments": {"entity": "host-01"}}'
    )
    assert "Hidden thought" not in text
    assert "Explicit reasoning field" not in text
    assert reasoning == "Explicit reasoning field"


def test_extract_openai_chat_message_falls_back_to_reasoning_only_when_both_empty():
    msg = {"role": "assistant", "content": "", "reasoning_content": "Last resort output"}
    text, reasoning = _extract_openai_chat_message(msg)
    assert text == "Last resort output"
    assert reasoning == "Last resort output"


# ---------------------------------------------------------------------------
# 4. DSML Native Markup Fallback Parser & SocTier1Agent Integration Tests
# ---------------------------------------------------------------------------


def test_parse_dsml_fullwidth_and_ascii_pipes_and_containers():
    fw = "\uff5c"
    dsml_fullwidth_fn = (
        f"<{fw}DSML{fw}function_calls>\n"
        f'<{fw}DSML{fw}invoke name="get_ip_address_report">\n'
        f'<{fw}DSML{fw}parameter name="ip" string="true">198.51.100.25</{fw}DSML{fw}parameter>\n'
        f"</{fw}DSML{fw}invoke>\n"
        f"</{fw}DSML{fw}function_calls>"
    )
    assert parse_dsml_tool_call(dsml_fullwidth_fn) == (
        "get_ip_address_report",
        {"ip": "198.51.100.25"},
    )

    dsml_ascii_tool = (
        "<|DSML|tool_calls>"
        '<|DSML|invoke name="get_domain_report">'
        '<|DSML|parameter name="domain" string="true">  evil-login.example  </|DSML|parameter>'
        "</|DSML|invoke>"
        "</|DSML|tool_calls>"
    )
    assert parse_dsml_tool_call(dsml_ascii_tool) == (
        "get_domain_report",
        {"domain": "evil-login.example"},
    )


def test_parse_dsml_type_coercion_multi_parameter():
    fw = "\uff5c"
    dsml_multi = (
        f"<{fw}DSML{fw}tool_calls>\n"
        f'  <{fw}DSML{fw}invoke name="search_security_events">\n'
        f'    <{fw}DSML{fw}parameter name="query" string="true">target.ip = "10.0.0.5"</{fw}DSML{fw}parameter>\n'
        f'    <{fw}DSML{fw}parameter name="hours_back" string="false">168</{fw}DSML{fw}parameter>\n'
        f'    <{fw}DSML{fw}parameter name="include_raw" string="false">true</{fw}DSML{fw}parameter>\n'
        f'    <{fw}DSML{fw}parameter name="exclude_benign">false</{fw}DSML{fw}parameter>\n'
        f'    <{fw}DSML{fw}parameter name="threshold">0.85</{fw}DSML{fw}parameter>\n'
        f'    <{fw}DSML{fw}parameter name="case_code">001</{fw}DSML{fw}parameter>\n'
        f'    <{fw}DSML{fw}parameter name="zero_val">0</{fw}DSML{fw}parameter>\n'
        f'    <{fw}DSML{fw}parameter name="numeric_as_str" string="true">42</{fw}DSML{fw}parameter>\n'
        f'    <{fw}DSML{fw}parameter name="filters">{{"severity": ["HIGH", "CRITICAL"]}}</{fw}DSML{fw}parameter>\n'
        f'    <{fw}DSML{fw}parameter name="tags">["c2", "edr"]</{fw}DSML{fw}parameter>\n'
        f"  </{fw}DSML{fw}invoke>\n"
        f"</{fw}DSML{fw}tool_calls>"
    )
    parsed = parse_dsml_tool_call(dsml_multi)
    assert parsed is not None
    tool_name, args = parsed
    assert tool_name == "search_security_events"
    assert args == {
        "query": 'target.ip = "10.0.0.5"',
        "hours_back": 168,
        "include_raw": True,
        "exclude_benign": False,
        "threshold": 0.85,
        "case_code": "001",
        "zero_val": 0,
        "numeric_as_str": "42",
        "filters": {"severity": ["HIGH", "CRITICAL"]},
        "tags": ["c2", "edr"],
    }


def test_soc_tier1_parse_action_ignores_decoy_action_inside_think_block():
    fw = "\uff5c"
    agent = SocTier1Agent()
    raw_turn = (
        "<think>\n"
        'Should I run Action: isolate_host(hostname="PROD-DB-01") right away? '
        "No! I must gather epistemic evidence first.\n"
        "</think>\n"
        f"<{fw}DSML{fw}function_calls>\n"
        f'<{fw}DSML{fw}invoke name="get_ip_address_report">\n'
        f'<{fw}DSML{fw}parameter name="ip" string="true">192.0.2.100</{fw}DSML{fw}parameter>\n'
        f"</{fw}DSML{fw}invoke>\n"
        f"</{fw}DSML{fw}function_calls>"
    )
    parsed = agent._parse_action(raw_turn)
    assert parsed == ("get_ip_address_report", {"ip": "192.0.2.100"})


def test_soc_tier1_agent_end_to_end_query_with_dsml_and_open_maas_transport():
    fw = "\uff5c"
    agent = SocTier1Agent(
        project_id="secops-test-proj",
        managed_model="deepseek-v4.1-flash-1017-maas",
    )

    turn1_payload = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "reasoning_content": "Do not call isolate_host yet; check 192.0.2.100.",
                    "content": (
                        "Thought: Checking IP intelligence via DSML.\n"
                        f"<{fw}DSML{fw}function_calls>\n"
                        f'<{fw}DSML{fw}invoke name="get_ip_address_report">\n'
                        f'<{fw}DSML{fw}parameter name="ip" string="true">192.0.2.100</{fw}DSML{fw}parameter>\n'
                        f"</{fw}DSML{fw}invoke>\n"
                        f"</{fw}DSML{fw}function_calls>"
                    ),
                }
            }
        ],
        "usage": {"prompt_tokens": 200, "completion_tokens": 45, "total_tokens": 245},
    }
    turn2_payload = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": (
                        "<think>Confirmed RFC-5737 TEST-NET-1 benign IP; avoid FORBIDDEN_WORD.</think>\n"
                        "Final Answer:\n"
                        "[Context & Enrichment]\n"
                        "- IP 192.0.2.100 belongs to RFC-5737 documentation range.\n\n"
                        "[Analysis & Verdict]\n"
                        "- Verdict: BENIGN\n\n"
                        "[Action & Escalation]\n"
                        "- Close case as benign test artifact.\n\n"
                        "[SOAR Documentation]\n"
                        "Verified RFC-5737 IP; closing alert.\n\n"
                        "```soc_decision\n"
                        "{\n"
                        '  "verdict": "BENIGN",\n'
                        '  "recommended_actions": ["close_case"],\n'
                        '  "target_entity": "192.0.2.100",\n'
                        '  "rationale": "RFC-5737 documentation range."\n'
                        "}\n"
                        "```"
                    ),
                }
            }
        ],
        "usage": {"prompt_tokens": 310, "completion_tokens": 90, "total_tokens": 400},
    }

    mock_creds = MagicMock(valid=True, token="maas-tok")
    responses = [_mock_http_response(turn1_payload), _mock_http_response(turn2_payload)]

    with patch("google.auth.default", return_value=(mock_creds, "secops-test-proj")), patch(
        "urllib.request.urlopen", side_effect=responses
    ):
        result = agent.query("Triage alert for IP 192.0.2.100")

    assert len(result["trajectory"]) == 1
    assert result["trajectory"][0]["tool"] == "get_ip_address_report"
    assert result["trajectory"][0]["args"] == {"ip": "192.0.2.100"}
    assert "RFC-5737" in result["trajectory"][0]["observation"]
    assert "FORBIDDEN_WORD" not in result["response"]
    assert result["usage"]["total_tokens"] == 645
    decision = extract_soc_decision(result["response"])
    assert decision is not None
    assert decision.verdict == "BENIGN"
    assert decision.recommended_actions == ["close_case"]


# ---------------------------------------------------------------------------
# 5. BenchmarkRunner OpenMaaS Single/Concurrent TPS, SSE TTFT/ITL, and Vision
# ---------------------------------------------------------------------------


def test_resolve_open_maas_target_from_flag_and_catalog_flavor():
    cat = {
        "deepseek-v4.1-flash-1017-maas": {
            "type": "maas",
            "maasModelId": "deepseek-ai/deepseek-v4.1-flash-1017-maas",
            "region": "global",
        }
    }
    m1, r1 = resolve_open_maas_target(
        maas_model="deepseek-ai/deepseek-v4.1-flash-1017-maas", region="us-central1", catalog=cat
    )
    assert (m1, r1) == ("deepseek-ai/deepseek-v4.1-flash-1017-maas", "global")

    m2, r2 = resolve_open_maas_target(
        flavor="deepseek-v4.1-flash-1017-maas", region="us-central1", catalog=cat
    )
    assert (m2, r2) == ("deepseek-ai/deepseek-v4.1-flash-1017-maas", "global")


def test_benchmark_open_maas_single_and_4stream_concurrent_tps():
    class ImmediateExecutor:
        def __init__(self, max_workers):
            self.max_workers = max_workers

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def submit(self, fn, *args, **kwargs):
            fut = Future()
            fut.set_result(fn(*args, **kwargs))
            return fut

    captured_urls: List[str] = []

    def _fake_urlopen(req, timeout=300):
        captured_urls.append(req.full_url)
        return _mock_http_response(
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "SOC analysis summary.",
                            "reasoning_content": "Brief reasoning.",
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": 64,
                    "completion_tokens": 120,
                    "total_tokens": 184,
                    "completion_tokens_details": {"reasoning_tokens": 40},
                },
            }
        )

    mock_creds = MagicMock(valid=True, token="bench-token")
    runner = BenchmarkRunner(
        project_id="bench-proj",
        maas_model="deepseek-ai/deepseek-v4.1-flash-1017-maas",
        runs=2,
        concurrency=1,
        stream=False,
    )

    with patch("google.auth.default", return_value=(mock_creds, "bench-proj")), patch(
        "scripts.benchmark.urllib.request.urlopen", side_effect=_fake_urlopen
    ):
        single_summary = runner.run(concurrency=1, runs=2, stream=False)

    assert single_summary is not None
    assert single_summary["token_count_source"] == "actual"
    assert single_summary["successful_requests"] == 2
    assert single_summary["avg_tokens"] == 120.0
    assert single_summary["tps"] > 0
    assert all(
        u
        == "https://aiplatform.googleapis.com/v1/projects/bench-proj/locations/global/endpoints/openapi/chat/completions"
        for u in captured_urls
    )

    # 4-stream concurrent TPS
    with patch("google.auth.default", return_value=(mock_creds, "bench-proj")), patch(
        "scripts.benchmark.ThreadPoolExecutor", ImmediateExecutor
    ), patch("scripts.benchmark.urllib.request.urlopen", side_effect=_fake_urlopen):
        conc_summary = runner.run(concurrency=4, runs=1, stream=False)

    assert conc_summary is not None
    assert conc_summary["concurrency"] == 4
    assert conc_summary["successful_requests"] == 4
    assert conc_summary["token_count_source"] == "actual"
    assert conc_summary["aggregate_tps"] is not None
    assert conc_summary["aggregate_tps"] > 0


def test_benchmark_open_maas_streaming_sse_ttft_itl_and_actual_usage():
    clock = [0.0]
    sse_events = [
        (0.08, b'data: {"choices":[{"delta":{"role":"assistant","content":""}}]}\n\n'),
        (0.12, b'data: {"choices":[{"delta":{"reasoning_content":"Think1"}}]}\n\n'),
        (0.15, b'data: {"choices":[{"delta":{"reasoning_content":" Think2"}}]}\n\n'),
        (0.20, b'data: {"choices":[{"delta":{"content":"Answer1"}}]}\n\n'),
        (0.26, b'data: {"choices":[{"delta":{"content":" Answer2"}}]}\n\n'),
        (
            0.30,
            b'data: {"choices":[],"usage":{"prompt_tokens":45,"completion_tokens":32,"total_tokens":77,"completion_tokens_details":{"reasoning_tokens":18}}}\n\n',
        ),
        (0.30, b"data: [DONE]\n\n"),
    ]

    def _make_chunked_response() -> HTTPResponse:
        arrivals = [(0.0, b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n")]
        for at, ev in sse_events:
            arrivals.append((at, f"{len(ev):x}\r\n".encode("ascii") + ev + b"\r\n"))
        arrivals.append((0.30, b"0\r\n\r\n"))

        class Transport(RawIOBase):
            def readable(self):
                return True

            def readinto(self, buffer):
                if not arrivals:
                    return 0
                at, chunk = arrivals.pop(0)
                clock[0] = at
                n = min(len(buffer), len(chunk))
                buffer[:n] = chunk[:n]
                if n < len(chunk):
                    arrivals.insert(0, (at, chunk[n:]))
                return n

        class Sock:
            def makefile(self, *args):
                return BufferedReader(Transport())

        resp = HTTPResponse(Sock())
        resp.begin()
        return resp

    captured_payloads: List[Dict[str, Any]] = []

    def _fake_urlopen(req, timeout=300):
        captured_payloads.append(json.loads(req.data.decode("utf-8")))
        return _make_chunked_response()

    mock_creds = MagicMock(valid=True, token="stream-tok")
    runner = BenchmarkRunner(
        project_id="bench-proj",
        maas_model="deepseek-ai/deepseek-v4.1-flash-1017-maas",
        runs=1,
        concurrency=1,
        stream=True,
    )

    with patch("google.auth.default", return_value=(mock_creds, "bench-proj")), patch(
        "scripts.benchmark.urllib.request.urlopen", side_effect=_fake_urlopen
    ), patch("scripts.benchmark.time.perf_counter", side_effect=lambda: clock[0]):
        summary = runner.run(concurrency=1, runs=1, stream=True)

    assert captured_payloads[0]["stream"] is True
    assert captured_payloads[0]["stream_options"] == {"include_usage": True}
    assert summary is not None
    assert summary["token_count_source"] == "actual"
    assert summary["avg_tokens"] == 32.0
    # First non-empty delta is reasoning_content at t=0.12s (not empty role delta at 0.08s)
    assert summary["ttft_ms"] == pytest.approx(120.0, abs=1.0)
    # Inter-chunk intervals: (0.15-0.12)=30ms, (0.20-0.15)=50ms, (0.26-0.20)=60ms
    assert summary["itl_mean_ms"] == pytest.approx((30.0 + 50.0 + 60.0) / 3.0, abs=1.0)
    assert summary["itl_p50_ms"] == pytest.approx(50.0, abs=1.0)
    assert summary["itl_p95_ms"] > 50.0


def test_benchmark_open_maas_vision_check_and_json_report(tmp_path: Path):
    captured_bodies: List[Dict[str, Any]] = []

    def _fake_urlopen(req, timeout=300):
        body = json.loads(req.data.decode("utf-8"))
        captured_bodies.append(body)
        return _mock_http_response(
            {
                "choices": [
                    {"message": {"role": "assistant", "content": "Valid compact PNG inspected."}}
                ],
                "usage": {"prompt_tokens": 210, "completion_tokens": 14, "total_tokens": 224},
            },
            status=200,
        )

    out_json = tmp_path / "maas_bench.json"
    mock_creds = MagicMock(valid=True, token="vis-tok")

    with patch("google.auth.default", return_value=(mock_creds, "bench-proj")), patch(
        "scripts.benchmark.urllib.request.urlopen", side_effect=_fake_urlopen
    ), patch(
        "sys.argv",
        [
            "benchmark.py",
            "--project",
            "bench-proj",
            "--maas-model",
            "deepseek-ai/deepseek-v4.1-flash-1017-maas",
            "--runs",
            "1",
            "--vision-check",
            "--output-json",
            str(out_json),
        ],
    ):
        benchmark_main()

    assert out_json.exists()
    report = json.loads(out_json.read_text(encoding="utf-8"))
    assert report["token_count_source"] == "actual"
    assert "vision_check" in report
    vc = report["vision_check"]
    assert vc["status"] == "OK"
    assert vc["status_code"] == 200
    assert vc["latency_ms"] >= 0.0
    assert vc["token_count_source"] == "actual"
    assert vc["usage"]["total_tokens"] == 224
    assert "Valid compact PNG inspected" in vc["response_snippet"]

    # Verify the vision request payload sent a genuine valid PNG data URL
    vision_req = captured_bodies[-1]
    content_parts = vision_req["messages"][0]["content"]
    img_part = next(p for p in content_parts if p["type"] == "image_url")
    data_url = img_part["image_url"]["url"]
    assert data_url.startswith("data:image/png;base64,")
    png_bytes = base64.b64decode(data_url.split(",", 1)[1])
    assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.parametrize("status_code", [403, 404])
def test_benchmark_open_maas_fast_fails_closed_on_403_404(status_code: int):
    url = _build_open_maas_url("bench-proj", "global")
    err = _http_error(url, status_code, {"error": {"message": "Publisher model not enabled"}})
    mock_creds = MagicMock(valid=True, token="tok")

    runner = BenchmarkRunner(
        project_id="bench-proj",
        maas_model="deepseek-ai/deepseek-v4.1-flash-1017-maas",
        runs=3,
        concurrency=1,
    )
    with patch("google.auth.default", return_value=(mock_creds, "bench-proj")), patch(
        "scripts.benchmark.urllib.request.urlopen", side_effect=err
    ) as mock_open, patch(
        "scripts.benchmark.time.sleep",
        side_effect=AssertionError("Benchmark must not retry on 403/404"),
    ):
        summary = runner.run(concurrency=1, runs=3, stream=False)

    # Must stop immediately on Run 1 without executing Runs 2 & 3
    assert mock_open.call_count == 1
    assert summary is not None
    assert summary["status"] == "MAAS_ACCESS_GATED"
    assert summary["status_code"] == status_code
    assert "Publisher model not enabled" in summary["error"]


# ---------------------------------------------------------------------------
# 6. Hygiene Invariant Self-Check Across All 4 Owned Wave-1 Bridge Files
# ---------------------------------------------------------------------------


def test_wave1_bridge_owned_files_hygiene_invariants():
    root = Path(__file__).resolve().parent.parent
    owned = [
        root / "agent" / "gemma_agent.py",
        root / "agent" / "soc_tier1_agent.py",
        root / "scripts" / "benchmark.py",
        root / "tests" / "test_deepseek_v41_maas_and_dsml.py",
    ]
    emoji_re = re.compile(
        "[\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001F900-\U0001F9FF"
        "\U0001FA00-\U0001FA6F"
        "\U0001FA70-\U0001FAFF]+",
        flags=re.UNICODE,
    )
    forbidden_parts = [
        r"\bb/\d{5,}",
        r"\bcl/\d{5,}",
        "corp." + "google.com",
        "google" + "plex.com",
        "/usr/local/" + "google/home",
    ]
    forbidden_internal_re = re.compile("|".join(forbidden_parts), flags=re.IGNORECASE)
    for fpath in owned:
        text = fpath.read_text(encoding="utf-8")
        assert "\u2014" not in text, f"Em-dash found in {fpath}"
        assert not emoji_re.findall(text), f"Emoji found in {fpath}"
        assert not forbidden_internal_re.findall(text), f"Internal token found in {fpath}"
