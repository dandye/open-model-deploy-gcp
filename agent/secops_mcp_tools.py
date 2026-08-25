"""Live Google SecOps Remote MCP Tool Client.

Connects to the official Google Security Operations Remote MCP Server
(https://us-chronicle.googleapis.com/mcp) using Application Default Credentials (ADC)
and tenant context.
"""

import json
import os
import subprocess
import urllib.request
from typing import Any, Dict, Optional

DEFAULT_PROJECT_ID = os.environ.get("CHRONICLE_PROJECT_ID", "dandye-0324-chronicle")
DEFAULT_CUSTOMER_ID = os.environ.get("CHRONICLE_CUSTOMER_ID", "7e977ce4-f45d-43b2-aea0-52f8b66acd80")
DEFAULT_REGION = os.environ.get("CHRONICLE_REGION", "us")
SECOPS_MCP_ENDPOINT = os.environ.get("SECOPS_MCP_ENDPOINT", f"https://{DEFAULT_REGION}-chronicle.googleapis.com/mcp")


def _get_access_token() -> str:
    """Retrieves OAuth2 access token via Google Cloud ADC."""
    try:
        import google.auth
        import google.auth.transport.requests
        credentials, _ = google.auth.default(scopes=[
            "https://www.googleapis.com/auth/cloud-platform",
            "https://www.googleapis.com/auth/chronicle",
        ])
        auth_req = google.auth.transport.requests.Request()
        credentials.refresh(auth_req)
        return credentials.token
    except Exception:
        token_res = subprocess.run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True)
        return token_res.stdout.strip()


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
    page_size: int = 10,
    page_token: Optional[str] = None,
) -> str:
    """Lists recent SOAR cases from the live Google SecOps instance.

    Args:
        page_size: Maximum number of cases to return (default 10).
        page_token: Optional pagination token.
    """
    args: Dict[str, Any] = {"pageSize": page_size}
    if page_token:
        args["pageToken"] = page_token
    res = call_secops_mcp("list_cases", args)
    if "content" in res and res["content"]:
        return res["content"][0].get("text", json.dumps(res))
    return json.dumps(res)


def get_case(case_name: str) -> str:
    """Retrieves a single SOAR case by its resource name.

    Args:
        case_name: Full resource name of the case (e.g. 'projects/.../cases/12345').
    """
    res = call_secops_mcp("get_case", {"name": case_name})
    if "content" in res and res["content"]:
        return res["content"][0].get("text", json.dumps(res))
    return json.dumps(res)


def create_case_comment(case_name: str, comment: str) -> str:
    """Creates a new comment/investigative note on a SOAR case in Google SecOps.

    Args:
        case_name: Full resource name of the case.
        comment: Plain text or markdown comment content.
    """
    res = call_secops_mcp("create_case_comment", {
        "parent": case_name,
        "comment": {"content": comment},
    })
    if "content" in res and res["content"]:
        return res["content"][0].get("text", json.dumps(res))
    return json.dumps(res)


def summarize_entity(entity: str) -> str:
    """Enriches and summarizes an entity (IP, domain, hostname, hash, user) in Chronicle SIEM.

    Args:
        entity: Entity value to investigate (e.g. '198.51.100.42', 'evil.com', 'DESKTOP-01').
    """
    res = call_secops_mcp("summarize_entity", {"entity": entity})
    if "content" in res and res["content"]:
        return res["content"][0].get("text", json.dumps(res))
    return json.dumps(res)


def udm_search(query: str) -> str:
    """Executes a UDM search query across Chronicle SIEM telemetry events.

    Args:
        query: Unified Data Model (UDM) search query expression.
    """
    res = call_secops_mcp("udm_search", {"query": query})
    if "content" in res and res["content"]:
        return res["content"][0].get("text", json.dumps(res))
    return json.dumps(res)


def fetch_alert_data(siem_alert_id: str) -> str:
    """Retrieves comprehensive profile and telemetry for a specific SIEM alert.

    Args:
        siem_alert_id: Unique alert ID from Chronicle SIEM.
    """
    res = call_secops_mcp("fetch_alert_data", {"siemAlertId": siem_alert_id})
    if "content" in res and res["content"]:
        return res["content"][0].get("text", json.dumps(res))
    return json.dumps(res)
