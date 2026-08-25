"""Unit tests for live Google SecOps Remote MCP tools module."""

import json
from unittest.mock import MagicMock, patch
from agent.secops_mcp_tools import (
    call_secops_mcp,
    create_case_comment,
    fetch_alert_data,
    get_case,
    list_cases,
    summarize_entity,
    udm_search,
)


@patch("urllib.request.urlopen")
@patch("agent.secops_mcp_tools._get_access_token")
def test_call_secops_mcp_success(mock_token, mock_urlopen):
    mock_token.return_value = "fake-token"
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({
        "result": {
            "content": [{"type": "text", "text": "{\"status\": \"OK\"}"}],
        }
    }).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_urlopen.return_value = mock_resp

    res = call_secops_mcp("list_cases", {"pageSize": 5})
    assert "content" in res
    assert res["content"][0]["text"] == '{"status": "OK"}'


@patch("agent.secops_mcp_tools.call_secops_mcp")
def test_list_cases_wrapper(mock_call):
    mock_call.return_value = {
        "content": [{"text": json.dumps({"cases": [{"name": "case-123"}]})}]
    }
    output = list_cases(page_size=5)
    data = json.loads(output)
    assert len(data["cases"]) == 1
    assert data["cases"][0]["name"] == "case-123"


@patch("agent.secops_mcp_tools.call_secops_mcp")
def test_get_case_wrapper(mock_call):
    mock_call.return_value = {
        "content": [{"text": json.dumps({"name": "case-456", "priority": "HIGH"})}]
    }
    output = get_case("case-456")
    data = json.loads(output)
    assert data["name"] == "case-456"
    assert data["priority"] == "HIGH"


@patch("agent.secops_mcp_tools.call_secops_mcp")
def test_create_case_comment_wrapper(mock_call):
    mock_call.return_value = {
        "content": [{"text": json.dumps({"status": "SUCCESS"})}]
    }
    output = create_case_comment("case-456", "Triage note")
    data = json.loads(output)
    assert data["status"] == "SUCCESS"


@patch("agent.secops_mcp_tools.call_secops_mcp")
def test_summarize_entity_wrapper(mock_call):
    mock_call.return_value = {
        "content": [{"text": json.dumps({"entity": "1.1.1.1", "verdict": "BENIGN"})}]
    }
    output = summarize_entity("1.1.1.1")
    data = json.loads(output)
    assert data["verdict"] == "BENIGN"


@patch("agent.secops_mcp_tools.call_secops_mcp")
def test_udm_search_wrapper(mock_call):
    mock_call.return_value = {
        "content": [{"text": json.dumps({"events_count": 42})}]
    }
    output = udm_search("metadata.event_type = 'USER_LOGIN'")
    data = json.loads(output)
    assert data["events_count"] == 42


@patch("agent.secops_mcp_tools.call_secops_mcp")
def test_fetch_alert_data_wrapper(mock_call):
    mock_call.return_value = {
        "content": [{"text": json.dumps({"alert_id": "ALERT-1", "severity": "HIGH"})}]
    }
    output = fetch_alert_data("ALERT-1")
    data = json.loads(output)
    assert data["severity"] == "HIGH"


def test_no_emojis_in_secops_mcp_tools_file():
    with open("agent/secops_mcp_tools.py", "r", encoding="utf-8") as f:
        content = f.read()
    for char in content:
        assert ord(char) < 128 or ord(char) in [8212, 8216, 8217, 8220, 8221], f"Non-ASCII/Emoji char: {char}"
