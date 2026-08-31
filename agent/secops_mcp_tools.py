"""Live Google SecOps Remote MCP Tool Client.

Connects to the official Google Security Operations Remote MCP Server
(https://us-chronicle.googleapis.com/mcp) using Application Default Credentials (ADC)
and tenant context.
"""

import datetime
import json
import os
import subprocess
import urllib.request
from typing import Any, Dict, Optional

DEFAULT_PROJECT_ID = os.environ.get("CHRONICLE_PROJECT_ID", "secops-demo-env")
DEFAULT_CUSTOMER_ID = os.environ.get("CHRONICLE_CUSTOMER_ID", "a13f6726-efed-452e-9008-8fe0d3cb0f75")
DEFAULT_REGION = os.environ.get("CHRONICLE_REGION", "us")
SECOPS_MCP_ENDPOINT = os.environ.get("SECOPS_MCP_ENDPOINT", f"https://{DEFAULT_REGION}-chronicle.googleapis.com/mcp")


def _get_access_token() -> str:
    """Retrieves OAuth2 access token via Google Cloud ADC or metadata."""
    try:
        import google.auth
        import google.auth.transport.requests
        credentials, _ = google.auth.default()
        if not credentials.valid:
            auth_req = google.auth.transport.requests.Request()
            credentials.refresh(auth_req)
        return credentials.token or ""
    except Exception:
        try:
            token_res = subprocess.run(
                ["gcloud", "auth", "print-access-token"],
                capture_output=True,
                text=True,
            )
            return token_res.stdout.strip()
        except Exception:
            return ""


def call_secops_mcp(
    tool_name: str,
    arguments: Optional[Dict[str, Any]] = None,
    project_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    region: Optional[str] = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    """Invokes a tool on the remote Google SecOps MCP server.

    Args:
        tool_name: Name of the SecOps MCP tool (e.g. 'list_cases', 'summarize_entity').
        arguments: Key-value dictionary of arguments for the tool.
        project_id: GCP project ID.
        customer_id: Chronicle customer ID.
        region: Chronicle region ('us', 'europe', etc.).
        timeout: HTTP request timeout in seconds.
    """
    args = dict(arguments or {})
    args.setdefault("projectId", project_id or DEFAULT_PROJECT_ID)
    args.setdefault("customerId", customer_id or DEFAULT_CUSTOMER_ID)
    args.setdefault("region", region or DEFAULT_REGION)

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": args,
        },
    }

    token = _get_access_token()
    endpoint = f"https://{args['region']}-chronicle.googleapis.com/mcp" if args.get("region") else SECOPS_MCP_ENDPOINT

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    if "error" in data:
        return {"error": data["error"]}
    return data.get("result", {})


def list_cases(
    filter_expr: Optional[str] = None,
    page_size: int = 10,
    page_token: Optional[str] = None,
) -> str:
    """Lists recent SOAR cases from the live Google SecOps instance.

    Args:
        filter_expr: Optional filter expression (e.g. \"Priority='PRIORITY_HIGH'\").
        page_size: Maximum number of cases to return (default 10).
        page_token: Optional pagination token.
    """
    args: Dict[str, Any] = {"pageSize": page_size}
    if filter_expr:
        args["filter"] = filter_expr
    if page_token:
        args["pageToken"] = page_token
    res = call_secops_mcp("list_cases", args)
    if "content" in res and res["content"]:
        return res["content"][0].get("text", json.dumps(res))
    return json.dumps(res)


def get_case(case_id: str) -> str:
    """Retrieves a single SOAR case by its numeric ID or full resource name.

    Args:
        case_id: Numeric Case ID (e.g. '17305') or full resource name.
    """
    clean_id = str(case_id).strip().split("/")[-1]
    res = call_secops_mcp("get_case", {"caseId": clean_id})
    if "content" in res and res["content"]:
        return res["content"][0].get("text", json.dumps(res))
    return json.dumps(res)


def create_case_comment(case_id: str, comment: str) -> str:
    """Creates a new comment/investigative note on a SOAR case in Google SecOps.

    Args:
        case_id: Numeric Case ID (e.g. '17305') or full resource name.
        comment: Plain text or markdown comment content.
    """
    clean_id = str(case_id).strip().split("/")[-1]
    res = call_secops_mcp("create_case_comment", {
        "caseId": clean_id,
        "comment": comment,
    })
    if "content" in res and res["content"]:
        return res["content"][0].get("text", json.dumps(res))
    return json.dumps(res)


def summarize_entity(
    query: str,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
) -> str:
    """Enriches and summarizes an entity query in Chronicle SIEM.

    Args:
        query: UDM query expression (e.g. 'principal.hostname = \"DESKTOP-01\"' or 'principal.ip = \"1.2.3.4\"').
        start_time: Optional ISO-8601 start timestamp.
        end_time: Optional ISO-8601 end timestamp.
    """
    args: Dict[str, Any] = {"query": query}
    now = datetime.datetime.now(datetime.timezone.utc)
    if not start_time:
        start_time = (now - datetime.timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    if not end_time:
        end_time = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    args["startTime"] = start_time
    args["endTime"] = end_time

    res = call_secops_mcp("summarize_entity", args)
    if "content" in res and res["content"]:
        return res["content"][0].get("text", json.dumps(res))
    return json.dumps(res)


def udm_search(
    query: str,
    max_events: int = 10,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
) -> str:
    """Executes a UDM search query across Chronicle SIEM telemetry events.

    Args:
        query: Unified Data Model (UDM) search query expression (e.g. 'metadata.event_type = \"NETWORK_CONNECTION\"').
        max_events: Maximum number of events to return (default 10).
        start_time: Optional ISO-8601 start timestamp.
        end_time: Optional ISO-8601 end timestamp.
    """
    args: Dict[str, Any] = {
        "query": query,
        "maxEvents": max_events,
    }
    now = datetime.datetime.now(datetime.timezone.utc)
    if not start_time:
        start_time = (now - datetime.timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    if not end_time:
        end_time = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    args["startTime"] = start_time
    args["endTime"] = end_time

    res = call_secops_mcp("udm_search", args)
    if "content" in res and res["content"]:
        return res["content"][0].get("text", json.dumps(res))
    return json.dumps(res)


def fetch_alert_data(siem_alert_id: str) -> str:
    """Retrieves comprehensive profile and telemetry for a specific SIEM alert.

    Args:
        siem_alert_id: Unique alert ID from Chronicle SIEM.
    """
    res = call_secops_mcp("fetch_alert_data", {"siemAlertId": str(siem_alert_id)})
    if "content" in res and res["content"]:
        return res["content"][0].get("text", json.dumps(res))
    return json.dumps(res)


SECOPS_MCP_TOOLS = [
    list_cases,
    get_case,
    create_case_comment,
    summarize_entity,
    udm_search,
    fetch_alert_data,
]

