from dataclasses import asdict, dataclass, field
import inspect
import json
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

try:

    from agent.gemma_agent import GemmaAgent
    from agent.soc_tools import (
        get_domain_report,
        get_file_report,
        get_ip_address_report,
        list_cases,
        lookup_entity,
        post_case_comment,
    )
    from agent.mcp_provider import McpToolProvider
    from agent.secops_mcp_tools import (
        SECOPS_MCP_TOOLS,
        create_case_comment as secops_create_case_comment,
        fetch_alert_data as secops_fetch_alert_data,
        get_case as secops_get_case,
        list_cases as secops_list_cases,
        summarize_entity as secops_summarize_entity,
        udm_search as secops_udm_search,
    )
except ModuleNotFoundError:
    from gemma_agent import GemmaAgent
    from mcp_provider import McpToolProvider
    from soc_tools import (
        get_domain_report,
        get_file_report,
        get_ip_address_report,
        list_cases,
        lookup_entity,
        post_case_comment,
    )
    from secops_mcp_tools import (
        SECOPS_MCP_TOOLS,
        create_case_comment as secops_create_case_comment,
        fetch_alert_data as secops_fetch_alert_data,
        get_case as secops_get_case,
        list_cases as secops_list_cases,
        summarize_entity as secops_summarize_entity,
        udm_search as secops_udm_search,
    )


SOC_TIER1_PERSONA = """You are a Tier 1 Security Operations Center (SOC) Analyst.
Your primary role is alert triage, indicator enrichment, threat assessment, containment recommendations, and structured SOAR case logging.

Core Operating Principles:
1. Evidence-Based Investigation: Gather observations across all relevant indicators (IPs, domains, hosts, hashes) using available tools before reaching a conclusion. You must invoke at least one investigation tool to gather verified telemetry before issuing a final verdict. Do not fabricate threat intelligence.
2. Grounded Threat Attribution: Correlate tool observations and technical indicators to identify threat severity (BENIGN, SUSPICIOUS, MALICIOUS) and specific threat families when supported by evidence.
3. Decisive Action & Containment: Recommend clear, proportionate containment actions for active threats and appropriate escalation paths for high-severity incidents.
4. Case & Lifecycle Management: Check for existing related cases to maintain investigation continuity and avoid redundant workflows.
5. Structured Reporting: Always organize your response into four explicit sections, concluding with a structured decision block:
   - [Context & Enrichment]: Entities identified and tool query findings.
   - [Analysis & Verdict]: Correlation of findings and threat assessment (BENIGN, SUSPICIOUS, MALICIOUS).
   - [Action & Escalation]: Clear operational recommendations and next steps.
   - [SOAR Documentation]: Markdown summary comment for the case log.
   - Conclude your final response with a ```soc_decision JSON block specifying verdict, recommended_actions (e.g. isolate_host, block_indicator, update_case_comment, close_case), target_entity, and rationale:
```soc_decision
{
  "verdict": "BENIGN",
  "recommended_actions": ["close_case"],
  "target_entity": "<entity>",
  "rationale": "<summary explanation>"
}
```

6. Investigation Cycle Exemplar:
Thought: The alert references external IP 198.51.100.25. I must enrich this indicator to determine reputation and adversary infrastructure association.
Action: get_ip_address_report(ip="198.51.100.25")
Observation: {"ip": "198.51.100.25", "reputation": "MALICIOUS", "threat_category": "C2_SERVER", "asn": "AS64496"}
Thought: The IP is confirmed active command-and-control infrastructure. I have sufficient evidence to form a complete triage verdict and containment strategy.
Final Answer:
[Context & Enrichment]
- External IP: 198.51.100.25
- Threat Intelligence: Confirmed C2 server under AS64496 with malicious reputation.

[Analysis & Verdict]
- Threat Assessment: MALICIOUS
- Correlation: Outbound traffic to confirmed adversary command-and-control infrastructure.

[Action & Escalation]
- Containment: Block indicator 198.51.100.25 on perimeter firewalls.
- Host Isolation: Isolate host DESKTOP-FIN-08 pending forensic review.
- Escalation: Escalate to Tier 2 Incident Response.

[SOAR Documentation]
Enriched IP 198.51.100.25 confirmed C2 node. Perimeter block requested and endpoint isolated.

```soc_decision
{
  "verdict": "MALICIOUS",
  "recommended_actions": ["block_indicator", "isolate_host", "update_case_comment"],
  "target_entity": "198.51.100.25",
  "rationale": "Confirmed communication with active adversary C2 server."
}
```
"""

SOC_ANALYST_PERSONA = SOC_TIER1_PERSONA


LOCAL_CANONICAL_MAP: Dict[str, str] = {
    "isolate": "isolate_host",
    "isolate_host": "isolate_host",
    "unblock_host": "unblock_host",
    "unisolate": "unblock_host",
    "unisolate_host": "unblock_host",
    "block_indicator": "block_indicator",
    "block_domain": "block_indicator",
    "block_ip": "block_indicator",
    "block_hash": "block_indicator",
    "update_case_comment": "update_case_comment",
    "post_case_comment": "update_case_comment",
    "create_case_comment": "update_case_comment",
    "add_case_comment": "update_case_comment",
    "close_case": "close_case",
    "resolve_case": "close_case",
    "close_alert": "close_case",
    "resolve_alert": "close_case",
    "close": "close_case",
    "resolve": "close_case",
    "quarantine": "isolate_host",
    "quarantine_host": "isolate_host",
}


@dataclass
class SocDecision:
    """Structured decision output from Tier 1 SOC investigation."""

    verdict: str  # BENIGN, MALICIOUS, SUSPICIOUS, INCONCLUSIVE
    recommended_actions: List[str] = field(default_factory=list)
    target_entity: Optional[str] = None
    rationale: Optional[str] = None
    prohibited_actions_avoided: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes decision to dictionary."""
        return asdict(self)

    def __getitem__(self, key: str) -> Any:
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key)


def _normalize_verdict(raw: str) -> str:
    """Normalizes verdict string to canonical category."""
    u = str(raw or "").strip().upper()
    if re.search(r"\b(?:NOT|NON|NO)\s+(?:MALICIOUS|THREAT|SUSPICIOUS)\b", u) or any(b in u for b in ("BENIGN", "FALSE_POSITIVE", "SAFE")):
        return "BENIGN"
    if "MALICIOUS" in u:
        return "MALICIOUS"
    if "SUSPICIOUS" in u:
        return "SUSPICIOUS"
    if "INCONCLUSIVE" in u:
        return "INCONCLUSIVE"
    return "INCONCLUSIVE"


def extract_soc_decision(response_text: str) -> Optional[SocDecision]:
    """Extracts structured SOC decision from model response text.

    Supports fenced ```soc_decision or ```json blocks, as well as fallback parsing
    of [Analysis & Verdict] and [Action & Escalation] sections.

    Args:
        response_text: Raw LLM response string.

    Returns:
        SocDecision dataclass instance, or None if no structured or fallback decision found.
    """
    if not response_text or not isinstance(response_text, str):
        return None

    def _canonicalize(act_name: str) -> str:
        clean = str(act_name or "").strip().lower()
        try:
            return canonicalize_pragmatic_action(clean)
        except Exception:
            return LOCAL_CANONICAL_MAP.get(clean, clean)

    # 1. Parse fenced code blocks: ```soc_decision ... ``` or ```json ... ```
    fenced_patterns = [
        r"```soc_decision\s*(\{.*?\})\s*```",
        r"```(?:json)?\s*(\{.*?\})\s*```",
    ]
    for pattern in fenced_patterns:
        matches = re.findall(pattern, response_text, re.DOTALL | re.IGNORECASE)
        for raw_json in matches:
            try:
                data = json.loads(raw_json)
                if isinstance(data, dict) and any(k in data for k in ("verdict", "recommended_actions", "decision")):
                    raw_verdict = str(data.get("verdict") or data.get("decision") or "").strip()
                    verdict = _normalize_verdict(raw_verdict) if raw_verdict else "INCONCLUSIVE"

                    raw_actions = data.get("recommended_actions") or []
                    if isinstance(raw_actions, str):
                        raw_actions = [raw_actions]
                    elif not isinstance(raw_actions, list):
                        raw_actions = []

                    recommended_actions: List[str] = []
                    for act in raw_actions:
                        if act and isinstance(act, str):
                            can_act = _canonicalize(act)
                            if can_act not in recommended_actions:
                                recommended_actions.append(can_act)

                    raw_avoided = data.get("prohibited_actions_avoided") or []
                    if isinstance(raw_avoided, str):
                        raw_avoided = [raw_avoided]
                    elif not isinstance(raw_avoided, list):
                        raw_avoided = []

                    prohibited_avoided: List[str] = []
                    for act in raw_avoided:
                        if act and isinstance(act, str):
                            can_act = _canonicalize(act)
                            if can_act not in prohibited_avoided:
                                prohibited_avoided.append(can_act)

                    target_entity = data.get("target_entity") or data.get("entity")
                    if target_entity is not None:
                        target_entity = str(target_entity).strip()

                    rationale = data.get("rationale") or data.get("reasoning") or data.get("reason")
                    if rationale is not None:
                        rationale = str(rationale).strip()

                    return SocDecision(
                        verdict=verdict,
                        recommended_actions=recommended_actions,
                        target_entity=target_entity,
                        rationale=rationale,
                        prohibited_actions_avoided=prohibited_avoided,
                    )
            except Exception:
                continue

    # 2. Check for raw unfenced JSON containing "verdict"
    raw_json_match = re.search(r"(\{\s*\"verdict\"\s*:.*?\})", response_text, re.DOTALL)
    if raw_json_match:
        try:
            data = json.loads(raw_json_match.group(1))
            if isinstance(data, dict) and "verdict" in data:
                raw_verdict = str(data.get("verdict") or "").strip()
                verdict = _normalize_verdict(raw_verdict)
                raw_actions = data.get("recommended_actions") or []
                if isinstance(raw_actions, str):
                    raw_actions = [raw_actions]
                elif not isinstance(raw_actions, list):
                    raw_actions = []
                recommended_actions = [_canonicalize(a) for a in raw_actions if isinstance(a, str)]
                target_entity = data.get("target_entity") or data.get("entity")
                rationale = data.get("rationale") or data.get("reasoning")
                raw_prohibited = data.get("prohibited_actions_avoided") or []
                if isinstance(raw_prohibited, str):
                    raw_prohibited = [raw_prohibited]
                elif not isinstance(raw_prohibited, list):
                    raw_prohibited = []
                prohibited_actions_avoided = [_canonicalize(a) for a in raw_prohibited if isinstance(a, str)]
                return SocDecision(
                    verdict=verdict,
                    recommended_actions=recommended_actions,
                    target_entity=str(target_entity).strip() if target_entity else None,
                    rationale=str(rationale).strip() if rationale else None,
                    prohibited_actions_avoided=prohibited_actions_avoided,
                )
        except Exception:
            pass

    # 3. Fallback: Parse [Analysis & Verdict] and [Action & Escalation]
    analysis_match = re.search(
        r"\[Analysis & Verdict\](.*?)(?=\[(?:Action & Escalation|SOAR Documentation|Structured Decision)\]|\Z)",
        response_text,
        re.DOTALL | re.IGNORECASE,
    )
    verdict_text = analysis_match.group(1).strip() if analysis_match else ""

    verdict = None
    if verdict_text:
        v_line_match = re.search(
            r"(?:Verdict|Threat Assessment|Threat Severity):\s*([^\n\r]+)",
            verdict_text,
            re.IGNORECASE,
        )
        if v_line_match:
            verdict = _normalize_verdict(v_line_match.group(1))
        else:
            verdict = _normalize_verdict(verdict_text)
    else:
        v_match = re.search(
            r"(?:Verdict|Threat Assessment|Threat Severity):\s*([^\n\r]+)",
            response_text,
            re.IGNORECASE,
        )
        if v_match:
            verdict = _normalize_verdict(v_match.group(1))

    action_match = re.search(
        r"\[Action & Escalation\](.*?)(?=\[(?:SOAR Documentation|Structured Decision)\]|\Z)",
        response_text,
        re.DOTALL | re.IGNORECASE,
    )
    action_text = action_match.group(1).strip() if action_match else ""

    if not analysis_match and not action_match and not verdict:
        return None

    search_text = action_text if action_text else response_text

    recommended_actions = []
    prohibited_avoided = []

    # Check isolate_host
    neg_isolate = bool(
        re.search(
            r"\b(?:no|not|never|without|neither|nor|avoid|do not)\b(?:\s+\w+){0,6}\s+(?:isolate|isolating|isolation|containment)\b",
            search_text,
            re.IGNORECASE,
        )
        or re.search(
            r"\b(?:isolate|isolating|isolation|containment)\b[\w\s:\-]{0,25}\b(?:not|unnecessary|not recommended|not required)\b",
            search_text,
            re.IGNORECASE,
        )
    )
    if neg_isolate:
        prohibited_avoided.append("isolate_host")
    else:
        pos_isolate = bool(
            re.search(
                r"\b(?:isolate_host|isolate\s+(?:the\s+)?(?:host|endpoint|workstation|machine|system)|network\s+isolation)\b",
                search_text,
                re.IGNORECASE,
            )
        )
        if pos_isolate:
            recommended_actions.append("isolate_host")

    # Check block_indicator
    neg_block = bool(
        re.search(
            r"\b(?:no|not|never|without|neither|nor|avoid|do not)\b(?:\s+\w+){0,6}\s+(?:block|blocking)\b",
            search_text,
            re.IGNORECASE,
        )
        or re.search(
            r"\b(?:block|blocking)\b[\w\s:\-]{0,25}\b(?:not|unnecessary|not recommended|not required)\b",
            search_text,
            re.IGNORECASE,
        )
    )
    if neg_block:
        prohibited_avoided.append("block_indicator")
    else:
        pos_block = bool(
            re.search(
                r"\b(?:block_indicator|block_domain|block_ip|block_hash|block\s+(?:the\s+)?(?:indicator|domain|ip|hash|url|address)|firewall\s+block|perimeter\s+block)\b",
                search_text,
                re.IGNORECASE,
            )
        )
        if pos_block:
            recommended_actions.append("block_indicator")

    # Check close_case
    neg_close = bool(
        re.search(
            r"\b(?:no|not|never|without|avoid|do not)\b(?:\s+\w+){0,6}\s+(?:close|closing|resolve|resolving)\b",
            search_text,
            re.IGNORECASE,
        )
        or re.search(
            r"\b(?:close|closing|resolve|resolving)\b[\w\s:\-]{0,25}\b(?:not|unnecessary|not recommended|not required)\b",
            search_text,
            re.IGNORECASE,
        )
    )
    pos_close = bool(
        re.search(
            r"\b(?:close_case|resolve_case|close\s+(?:the\s+)?(?:case|alert)|resolve\s+(?:the\s+)?(?:case|alert)|close\s+alert)\b",
            search_text,
            re.IGNORECASE,
        )
    )
    if neg_close:
        prohibited_avoided.append("close_case")
    elif pos_close:
        recommended_actions.append("close_case")

    # Check update_case_comment
    neg_comment = bool(
        re.search(
            r"\b(?:no|not|never|without|avoid|do not)\b(?:\s+\w+){0,6}\s+(?:comment|update_case|post_case)\b",
            search_text,
            re.IGNORECASE,
        )
    )
    pos_comment = bool(
        re.search(
            r"\b(?:update_case_comment|post_case_comment|create_case_comment|update\s+(?:the\s+)?case\s+comment|post\s+(?:a\s+)?comment|add\s+(?:a\s+)?comment|log\s+(?:findings|to\s+case)|document\s+(?:findings|in\s+case)|case\s+comment)\b",
            search_text,
            re.IGNORECASE,
        )
    )
    if neg_comment:
        prohibited_avoided.append("update_case_comment")
    elif pos_comment:
        recommended_actions.append("update_case_comment")

    # Check unblock_host
    pos_unblock = bool(
        re.search(
            r"\b(?:unblock_host|unisolate_host|unblock\s+host|unisolate\s+host|remove\s+isolation)\b",
            search_text,
            re.IGNORECASE,
        )
    )
    if pos_unblock:
        recommended_actions.append("unblock_host")

    target_entity = None
    ent_match = re.search(
        r"(?:target entity|entity|host|ip|domain):\s*([a-zA-Z0-9_\.\-]+)",
        response_text,
        re.IGNORECASE,
    )
    if ent_match:
        target_entity = ent_match.group(1).strip()

    rationale = verdict_text if verdict_text else None

    if verdict is None and not recommended_actions and not prohibited_avoided:
        return None

    return SocDecision(
        verdict=verdict or "INCONCLUSIVE",
        recommended_actions=recommended_actions,
        target_entity=target_entity,
        rationale=rationale,
        prohibited_actions_avoided=prohibited_avoided,
    )


try:
    from scripts.eval_trajectory_verifier import (
        canonicalize_pragmatic_action,
        is_epistemic_tool,
        is_pragmatic_action,
    )
except Exception:
    def is_epistemic_tool(name: str) -> bool:
        n = str(name).lower()
        return any(n.startswith(p) for p in ("get_", "lookup_", "search_", "fetch_", "list_", "query_", "summarize_")) or n in ("udm_search",)

    def is_pragmatic_action(name: str) -> bool:
        n = str(name).lower()
        return any(n.startswith(p) for p in ("isolate", "block_", "unblock_", "unisolate", "close_", "resolve_", "update_case", "post_case", "create_case", "add_case"))

    def canonicalize_pragmatic_action(action_name: str) -> str:
        clean = str(action_name or "").strip().lower()
        return LOCAL_CANONICAL_MAP.get(clean, clean)


def _extract_json_dicts(text: str) -> List[Dict[str, Any]]:
    """Extracts all valid top-level JSON dictionaries from text."""
    results: List[Dict[str, Any]] = []
    n = len(text)
    i = 0
    while i < n:
        if text[i] == "{":
            start = i
            depth = 0
            in_string = False
            escape = False
            matched = False
            for j in range(start, n):
                c = text[j]
                if escape:
                    escape = False
                    continue
                if c == "\\":
                    escape = True
                    continue
                if c == '"':
                    in_string = not in_string
                    continue
                if not in_string:
                    if c == "{":
                        depth += 1
                    elif c == "}":
                        depth -= 1
                        if depth == 0:
                            candidate = text[start : j + 1]
                            try:
                                data = json.loads(candidate)
                                if isinstance(data, dict):
                                    results.append(data)
                                    matched = True
                            except Exception:
                                pass
                            i = j + 1
                            break
            if not matched:
                i += 1
        else:
            i += 1
    return results


def _dict_to_action(data: Dict[str, Any]) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Converts a parsed dictionary into a (tool_name, args) tuple if it represents an action."""
    if not isinstance(data, dict):
        return None

    # Exclude soc_decision verdict blocks unless they explicitly specify a tool/action
    if "verdict" in data and not any(k in data for k in ("name", "tool", "action")):
        return None

    raw_tool_name = data.get("name") or data.get("tool") or data.get("action")
    if not raw_tool_name or not isinstance(raw_tool_name, str):
        return None

    tool_name = raw_tool_name.strip().strip('"\'')
    if not tool_name:
        return None

    raw_args = (
        data.get("arguments")
        if "arguments" in data
        else data.get("args")
        if "args" in data
        else data.get("parameters")
        if "parameters" in data
        else data.get("action_input")
    )

    if raw_args is None:
        raw_args = {k: v for k, v in data.items() if k not in ("name", "tool", "action")}

    if isinstance(raw_args, str):
        try:
            raw_args = json.loads(raw_args)
        except Exception:
            raw_args = {"input": raw_args}

    if not isinstance(raw_args, dict):
        raw_args = {"arg": raw_args}

    clean_args: Dict[str, Any] = {}
    for k, v in raw_args.items():
        clean_k = str(k).strip().strip('"\'')
        if isinstance(v, str):
            clean_args[clean_k] = v.strip()
        else:
            clean_args[clean_k] = v

    return tool_name, clean_args


class SocTier1Agent(GemmaAgent):
    """Reasoning Engine compatible Tier 1 SOC Analyst Agent powered by Gemma with ReAct tool execution."""

    def __init__(
        self,
        project_id: Optional[str] = None,
        region: str = "us-central1",
        endpoint_id: Optional[str] = None,
        cloudrun_url: Optional[str] = None,
        managed_model: Optional[str] = None,
        use_live_mcp: bool = False,
        environment: Optional[Any] = None,
        mcp_provider: str = "default",
    ):
        if use_live_mcp:
            from agent.secops_mcp_tools import (
                create_case_comment,
                fetch_alert_data,
                get_case,
                list_cases as mcp_list_cases,
                summarize_entity,
                udm_search,
            )
            soc_tools: List[Callable] = [
                mcp_list_cases,
                get_case,
                create_case_comment,
                summarize_entity,
                udm_search,
                fetch_alert_data,
            ]
        else:
            soc_tools: List[Callable] = [
                lookup_entity,
                get_ip_address_report,
                get_domain_report,
                get_file_report,
                list_cases,
                post_case_comment,
            ]
        super().__init__(
            project_id=project_id,
            region=region,
            endpoint_id=endpoint_id,
            cloudrun_url=cloudrun_url,
            managed_model=managed_model,
            system_instruction=SOC_TIER1_PERSONA,
            tools=soc_tools,
        )
        self.use_live_mcp = use_live_mcp
        self.environment = environment
        self.mcp_provider_name = mcp_provider
        self.mcp_provider = McpToolProvider(provider=mcp_provider)
        self.name = "soc_analyst_tier1"
        self.tools_dict: Dict[str, Callable] = {tool.__name__: tool for tool in (self.tools or [])}
        self.last_backend: str = "Unknown"

    def _build_tools_description(self) -> str:
        """Extracts tool docstrings and signatures for ReAct prompt formatting."""
        descriptions = []
        for name, func in self.tools_dict.items():
            doc = inspect.getdoc(func) or "No description available."
            desc = self.mcp_provider.get_description(name, default_doc=doc)
            sig = inspect.signature(func)
            descriptions.append(f"- {name}{sig}: {desc}")
        if self.environment is not None:
            env_actions = [
                "- isolate_host(hostname: str): Isolates host from enterprise network to contain active adversary threat.",
                "- unblock_host(hostname: str): Removes network isolation on benign or remediated host.",
                "- block_indicator(indicator: str): Adds domain, IP, or file hash to perimeter firewall and EDR blocklist.",
                "- update_case_comment(case_id: str, comment: str): Posts triage findings and IOC notes to SOAR incident case.",
                "- close_case(case_id: str, verdict: str): Resolves and closes SOAR case as benign false positive or contained incident.",
            ]
            for act_line in env_actions:
                act_name = act_line.split("(")[0].strip("- ")
                if act_name not in self.tools_dict:
                    descriptions.append(act_line)
        return "\n".join(descriptions)

    def _parse_action(self, step_output: str = "", text: Optional[str] = None) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Parses action calls in ReAct, JSON, and fenced block formats."""
        raw_text = text if text is not None else step_output
        if not raw_text or not isinstance(raw_text, str):
            return None

        # 1. Fenced call block format: ```call:<tool_name>\n{ ... }\n```
        fenced_call_match = re.search(r"```call:([a-zA-Z0-9_]+)\s*\n?(.*?)\s*```", raw_text, re.DOTALL)
        if fenced_call_match:
            tool_name = fenced_call_match.group(1).strip().strip('"\'')
            body = fenced_call_match.group(2).strip()
            args: Dict[str, Any] = {}
            if body:
                try:
                    parsed_body = json.loads(body)
                    if isinstance(parsed_body, dict):
                        args = parsed_body
                    else:
                        args = {"input": parsed_body}
                except Exception:
                    kwarg_pattern = re.compile(r'([a-zA-Z0-9_]+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s,\)]+))')
                    matches = list(kwarg_pattern.finditer(body))
                    if matches:
                        for m in matches:
                            k = m.group(1).strip().strip('"\'')
                            if m.group(2) is not None:
                                args[k] = m.group(2).strip()
                            elif m.group(3) is not None:
                                args[k] = m.group(3).strip()
                            elif m.group(4) is not None:
                                args[k] = m.group(4).strip()
                    else:
                        args = {"input": body}
            clean_args = {str(k).strip().strip('"\'') : (v.strip() if isinstance(v, str) else v) for k, v in args.items()}
            return tool_name, clean_args

        # 2. Fenced tool block format: ```tool_call\n{ ... }\n``` or ```tool\n{ ... }\n``` or ```action\n{ ... }\n```
        fenced_tool_match = re.search(r"```(?:tool_call|tool|action)\s*\n?(.*?)\s*```", raw_text, re.DOTALL | re.IGNORECASE)
        if fenced_tool_match:
            body = fenced_tool_match.group(1).strip()
            try:
                data = json.loads(body)
                if isinstance(data, dict):
                    res = _dict_to_action(data)
                    if res:
                        return res
            except Exception:
                pass

        # 3. Standard ReAct function call: Action: <tool_name>(<arg_name>="<value>", ...)
        action_prefix = re.search(r"Action:\s*([a-zA-Z0-9_]+)\s*\(", raw_text)
        if action_prefix:
            tool_name = action_prefix.group(1).strip().strip('"\'')
            start_idx = action_prefix.end()
            in_quote = None
            escape = False
            paren_depth = 1
            end_idx = None
            for idx in range(start_idx, len(raw_text)):
                char = raw_text[idx]
                if escape:
                    escape = False
                    continue
                if char == "\\":
                    escape = True
                    continue
                if in_quote:
                    if char == in_quote:
                        in_quote = None
                else:
                    if char in ('"', "'"):
                        in_quote = char
                    elif char == "(":
                        paren_depth += 1
                    elif char == ")":
                        paren_depth -= 1
                        if paren_depth == 0:
                            end_idx = idx
                            break
            if end_idx is not None:
                args_raw = raw_text[start_idx:end_idx].strip()
                args: Dict[str, Any] = {}
                if args_raw:
                    kwarg_pattern = re.compile(r'([a-zA-Z0-9_]+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([a-zA-Z0-9_\.\-]+))')
                    kwarg_matches = list(kwarg_pattern.finditer(args_raw))
                    if kwarg_matches:
                        for m in kwarg_matches:
                            k = m.group(1).strip().strip('"\'')
                            if m.group(2) is not None:
                                args[k] = m.group(2).strip()
                            elif m.group(3) is not None:
                                args[k] = m.group(3).strip()
                            elif m.group(4) is not None:
                                raw_val = m.group(4).strip()
                                if raw_val.lower() == "true":
                                    args[k] = True
                                elif raw_val.lower() == "false":
                                    args[k] = False
                                elif raw_val.isdigit():
                                    args[k] = int(raw_val)
                                else:
                                    args[k] = raw_val
                    else:
                        pos_match = re.match(r'^(?:"([^"]*)"|\'([^\']*)\'|([a-zA-Z0-9_\.\-]+))$', args_raw)
                        if pos_match:
                            val = (
                                pos_match.group(1)
                                if pos_match.group(1) is not None
                                else (pos_match.group(2) if pos_match.group(2) is not None else pos_match.group(3))
                            )
                            if isinstance(val, str):
                                val = val.strip()
                            func = self.tools_dict.get(tool_name)
                            param_name = None
                            if func:
                                params = list(inspect.signature(func).parameters.keys())
                                if params:
                                    param_name = params[0]
                            if not param_name:
                                fallback_params = {
                                    "isolate_host": "hostname",
                                    "unblock_host": "hostname",
                                    "block_indicator": "indicator",
                                    "lookup_entity": "entity",
                                    "get_ip_address_report": "ip",
                                    "get_domain_report": "domain",
                                    "get_file_report": "file_hash",
                                    "list_cases": "entity",
                                    "close_case": "case_id",
                                    "update_case_comment": "case_id",
                                }
                                param_name = fallback_params.get(tool_name, "arg")
                            args[param_name] = val
                return tool_name, args

        # 4. JSON action format (Action: {...}, ```json {...} ```, or standalone JSON object)
        json_dicts = _extract_json_dicts(raw_text)
        for data in json_dicts:
            res = _dict_to_action(data)
            if res:
                return res

        # 5. Bare action format: Action: <tool_name> (no arguments)
        action_bare_match = re.search(r"Action:\s*([a-zA-Z0-9_]+)\s*$", raw_text, re.MULTILINE)
        if action_bare_match:
            tool_name = action_bare_match.group(1).strip().strip('"\'')
            if tool_name in self.tools_dict or is_epistemic_tool(tool_name) or is_pragmatic_action(tool_name):
                return tool_name, {}

        return None

    def _execute_tool_action(self, tool_name: str, args: Dict[str, Any]) -> str:
        """Executes a local or remote tool function safely and returns a JSON string."""
        if self.environment is not None:
            if is_epistemic_tool(tool_name):
                res = self.environment.query_tool(tool_name, args)
                if isinstance(res, (dict, list)):
                    return json.dumps(res)
                return str(res)
            elif is_pragmatic_action(tool_name):
                res = self.environment.execute_action(tool_name, args)
                if isinstance(res, (dict, list)):
                    return json.dumps(res)
                return str(res)

        func = self.tools_dict.get(tool_name)
        if not func:
            return json.dumps({
                "error": f"Tool '{tool_name}' not found. Available tools: {list(self.tools_dict.keys())}",
                "status": "ERROR",
            })
        try:
            if not isinstance(args, dict):
                args = {}
            sig = inspect.signature(func)
            valid_args = {}
            params = list(sig.parameters.keys())
            if len(params) == 1 and len(args) == 1:
                valid_args[params[0]] = list(args.values())[0]
            else:
                for param_name in params:
                    if param_name in args:
                        valid_args[param_name] = args[param_name]
                    elif len(args) == 1 and list(args.keys())[0] in ("input", "arg"):
                        valid_args[param_name] = list(args.values())[0]
            result = func(**valid_args)
            if isinstance(result, (dict, list)):
                return json.dumps(result)
            return str(result)
        except Exception as e:
            return json.dumps({
                "error": f"Tool execution failed: {str(e)}",
                "status": "ERROR",
            })

    def _execute_tool(self, tool_name: str, args: Dict[str, Any]) -> str:
        """Executes a tool action safely (alias for _execute_tool_action)."""
        return self._execute_tool_action(tool_name, args)


    def _call_llm_step(self, prompt: str, max_tokens: Optional[int] = None, temperature: float = 0.2) -> Tuple[str, Dict[str, int]]:
        """Invokes underlying Gemma LLM backend for a single reasoning step."""
        res = super().query(prompt=prompt, max_tokens=max_tokens, temperature=temperature)
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        if isinstance(res, dict):
            self.last_backend = res.get("backend", "Unknown")
            usage = res.get("usage", usage)
            return res.get("response", ""), usage
        return str(res), usage

    def format_triage_prompt(self, query: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Formats an operational triage request with optional case metadata."""
        if not context:
            return query
        ctx_str = "\n".join(f"- {k}: {v}" for k, v in context.items())
        return f"Operational Triage Request:\n{query}\n\nCase Context:\n{ctx_str}\n\nPerform initial investigation and provide the triage report."

    def query(
        self,
        prompt: str,
        max_iterations: int = 5,
        max_tokens: Optional[int] = None,
        temperature: float = 0.2,
    ) -> Dict[str, Any]:
        """Executes multi-step ReAct triage reasoning and executes tools iteratively."""
        tools_doc = self._build_tools_description()
        react_instructions = (
            f"{SOC_TIER1_PERSONA}\n\n"
            f"Available Investigation Tools:\n{tools_doc}\n\n"
            "Interaction Protocol (ReAct):\n"
            "To gather information, output Thought and Action using one of the following formats:\n"
            "Format 1 (Standard ReAct): Action: <tool_name>(<arg_name>=\"<value>\")\n"
            "Format 2 (JSON Action): Action: {\"name\": \"<tool_name>\", \"arguments\": {\"<arg_name>\": \"<value>\"}}\n"
            "Format 3 (Fenced Block): ```tool_call\n{\"name\": \"<tool_name>\", \"args\": {\"<arg_name>\": \"<value>\"}}\n```\n\n"
            "Example Interaction Cycle:\n"
            "Thought: I need to investigate the domain reputation.\n"
            "Action: get_domain_report(domain=\"evil.com\")\n"
            "Observation: {\"domain\": \"evil.com\", \"verdict\": \"MALICIOUS\", \"threat_category\": \"PHISHING\"}\n"
            "Thought: The domain is confirmed malicious phishing infrastructure. I have sufficient evidence to conclude.\n"
            "Final Answer:\n"
            "[Context & Enrichment]\n"
            "- Domain evil.com flagged as malicious phishing infrastructure.\n\n"
            "[Analysis & Verdict]\n"
            "- Verdict: MALICIOUS\n"
            "- Phishing domain targeting enterprise credentials.\n\n"
            "[Action & Escalation]\n"
            "- Block indicator evil.com on perimeter firewall and web proxy.\n"
            "- Update case with findings and escalate.\n\n"
            "[SOAR Documentation]\n"
            "Enriched domain evil.com: confirmed phishing threat. Blocked at boundary.\n\n"
            "```soc_decision\n"
            "{\n"
            '  "verdict": "MALICIOUS",\n'
            '  "recommended_actions": ["block_indicator", "update_case_comment"],\n'
            '  "target_entity": "evil.com",\n'
            '  "rationale": "Confirmed phishing domain targeting enterprise credentials."\n'
            "}\n"
            "```\n\n"
            "When you receive the Observation, continue. You must invoke at least one investigation tool before concluding with a final verdict. When you have gathered all necessary information, conclude with:\n"
            "Thought: I have gathered all necessary information to form a complete triage verdict.\n"
            "Final Answer:\n"
            "[Context & Enrichment]\n<entities and findings>\n\n"
            "[Analysis & Verdict]\n<verdict: BENIGN, SUSPICIOUS, or MALICIOUS>\n\n"
            "[Action & Escalation]\n<clear operational actions>\n\n"
            "[SOAR Documentation]\n<markdown comment>\n\n"
            "```soc_decision\n"
            "{\n"
            '  "verdict": "BENIGN",\n'
            '  "recommended_actions": ["close_case"],\n'
            '  "target_entity": "<entity>",\n'
            '  "rationale": "<summary explanation>"\n'
            "}\n"
            "```\n"
        )

        current_prompt = f"{react_instructions}\n\nQuestion: {prompt}\n"
        trajectory: List[Dict[str, Any]] = []
        final_answer = ""
        total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        for iteration in range(max_iterations):
            step_output, step_usage = self._call_llm_step(current_prompt, max_tokens=max_tokens, temperature=temperature)
            total_usage["prompt_tokens"] += step_usage.get("prompt_tokens", 0)
            total_usage["completion_tokens"] += step_usage.get("completion_tokens", 0)
            total_usage["total_tokens"] += step_usage.get("total_tokens", 0)

            if not step_output:
                break

            # 1. Check for Action / Tool invocation
            parsed = self._parse_action(step_output)
            if parsed:
                tool_name, tool_args = parsed
                observation = self._execute_tool_action(tool_name, tool_args)
                trajectory.append({
                    "iteration": iteration + 1,
                    "tool": tool_name,
                    "args": tool_args,
                    "observation": observation,
                })
                current_prompt += f"{step_output}\nObservation: {observation}\n"
                continue

            # 2. Check for premature zero-tool termination in step 0
            if iteration == 0 and iteration < max_iterations - 1:
                investigation_keywords = ("triage", "investigate", "query", "check", "enrich")
                requires_investigation = any(k in prompt.lower() for k in investigation_keywords)
                is_premature_conclusion = (
                    "Final Answer:" in step_output
                    or "[Analysis & Verdict]" in step_output
                    or "[Context & Enrichment]" in step_output
                    or "```soc_decision" in step_output
                )
                if requires_investigation and is_premature_conclusion:
                    reflection = (
                        "Observation: Investigation incomplete. You have not called any investigation tools "
                        "(e.g. get_ip_report, get_domain_report, get_file_report, lookup_entity, list_cases). "
                        "You must invoke an investigation tool to gather verified telemetry before issuing a final verdict."
                    )
                    current_prompt += f"{step_output}\n{reflection}\n"
                    continue

            # 3. Check for explicit Final Answer
            if "Final Answer:" in step_output:
                final_answer = step_output.split("Final Answer:", 1)[1].strip()
                break

            # 4. Check if model produced the full structured triage report directly
            if "[Context & Enrichment]" in step_output and "[Analysis & Verdict]" in step_output:
                final_answer = step_output.strip()
                break

            # No action and no final answer tag; treat output as final answer
            final_answer = step_output.strip()
            break

        if not final_answer:
            final_answer = "Reached maximum investigation iterations without final triage output."

        return {
            "response": final_answer,
            "trajectory": trajectory,
            "usage": total_usage,
            "backend": self.last_backend,
            "endpoint_id": self.endpoint_id,
        }


