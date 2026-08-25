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
Your primary role is alert triage, basic indicator enrichment, duplicate case detection, and structured escalation recommendations.

Operational Runbook Procedures:
1. Basic Enrichment: Always query relevant tools to enrich indicators (IPs, domains, hashes, entities) before reaching a verdict.
2. Documentation Ground Truth: Recognize non-routable documentation IPs (e.g. RFC-5737 192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24) as benign test entities when evaluating threat reputation, avoiding false-positive escalations.
3. Duplicate Case Detection: When checking SOAR for existing cases via list_cases, if an active open case exists for the entity or Case ID, recommend appending the new findings to the existing case rather than opening a redundant ticket.
4. Phishing Containment: For credential harvesting phishing alerts, recommend resetting user credentials / revoking active sessions and blocking the malicious sender domain.
5. Ransomware Emergency Protocol: For active ransomware infections, mandate immediate network isolation, instruct not to reboot the system or pay the ransom, and immediately escalate to Tier 2 Incident Response.
6. Structured Reporting: Always organize your response into four explicit sections:
   - [Context & Enrichment]: Entities identified and tool query findings.
   - [Analysis & Verdict]: Correlation of findings and threat assessment (BENIGN, SUSPICIOUS, MALICIOUS).
   - [Action & Escalation]: Clear operational recommendations and next steps.
   - [SOAR Documentation]: Markdown summary comment for the case log.
"""


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
        self.name = "soc_analyst_tier1"
        self.tools_dict: Dict[str, Callable] = {tool.__name__: tool for tool in (self.tools or [])}
        self.last_backend: str = "Unknown"

    def _build_tools_description(self) -> str:
        """Extracts tool docstrings and signatures for ReAct prompt formatting."""
        descriptions = []
        for name, func in self.tools_dict.items():
            doc = inspect.getdoc(func) or "No description available."
            first_line = doc.splitlines()[0]
            sig = inspect.signature(func)
            descriptions.append(f"- {name}{sig}: {first_line}")
        return "\n".join(descriptions)

    def _parse_action(self, text: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Parses action calls in ReAct or JSON formats."""
        # 1. JSON action format: {"tool": "name", "args": {...}} or {"action": "name", "action_input": {...}}
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if not json_match:
            json_match = re.search(r"(\{\s*\"(?:tool|action)\"\s*:.*?\})", text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                tool_name = data.get("tool") or data.get("action")
                args = data.get("args") or data.get("action_input") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {"input": args}
                if tool_name and isinstance(args, dict):
                    return str(tool_name).strip(), args
            except Exception:
                pass

        # 2. ReAct action format: Action: tool_name(arg_name="value") or tool_name("value")
        action_match = re.search(r"Action:\s*([a-zA-Z0-9_]+)\s*\((.*?)\)", text, re.DOTALL)
        if action_match:
            tool_name = action_match.group(1).strip()
            args_raw = action_match.group(2).strip()
            args: Dict[str, Any] = {}
            if args_raw:
                # Check keyword arguments: k="v" or k='v' or k=v
                kwarg_matches = re.findall(r'([a-zA-Z0-9_]+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([a-zA-Z0-9_\.\-]+))', args_raw)
                if kwarg_matches:
                    for k, v1, v2, v3 in kwarg_matches:
                        args[k] = v1 or v2 or v3
                else:
                    # Positional argument passed without keyword
                    pos_match = re.match(r'^(?:"([^"]*)"|\'([^\']*)\'|([a-zA-Z0-9_\.\-]+))$', args_raw)
                    if pos_match:
                        val = pos_match.group(1) or pos_match.group(2) or pos_match.group(3)
                        func = self.tools_dict.get(tool_name)
                        if func:
                            params = list(inspect.signature(func).parameters.keys())
                            if params:
                                args[params[0]] = val
                        else:
                            args["arg"] = val
            return tool_name, args

        return None

    def _execute_tool(self, tool_name: str, args: Dict[str, Any]) -> str:
        """Executes a local or remote tool function safely."""
        func = self.tools_dict.get(tool_name)
        if not func:
            return f"Error: Tool '{tool_name}' not found. Available tools: {list(self.tools_dict.keys())}"
        try:
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
            return str(result)
        except Exception as e:
            return f"Error executing tool '{tool_name}': {str(e)}"


    def _call_llm_step(self, prompt: str, max_tokens: int = 1024, temperature: float = 0.2) -> Tuple[str, Dict[str, int]]:
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
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> Dict[str, Any]:
        """Executes multi-step ReAct triage reasoning and executes tools iteratively."""
        tools_doc = self._build_tools_description()
        react_instructions = (
            f"{SOC_TIER1_PERSONA}\n\n"
            f"Available Investigation Tools:\n{tools_doc}\n\n"
            "Interaction Protocol (ReAct):\n"
            "To gather information, output Thought and Action:\n"
            "Thought: <reasoning about needed evidence>\n"
            "Action: <tool_name>(<arg_name>=\"<value>\")\n\n"
            "When you receive the Observation, continue. When you have gathered all necessary information, conclude with:\n"
            "Thought: I have gathered all necessary information to form a complete triage verdict.\n"
            "Final Answer:\n"
            "[Context & Enrichment]\n<entities and findings>\n\n"
            "[Analysis & Verdict]\n<verdict: BENIGN, SUSPICIOUS, or MALICIOUS>\n\n"
            "[Action & Escalation]\n<clear operational actions>\n\n"
            "[SOAR Documentation]\n<markdown comment>\n"
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

            # 1. Check for explicit Final Answer
            if "Final Answer:" in step_output:
                final_answer = step_output.split("Final Answer:", 1)[1].strip()
                break

            # 2. Check if model produced the full structured triage report directly
            if "[Context & Enrichment]" in step_output and "[Analysis & Verdict]" in step_output:
                final_answer = step_output.strip()
                break

            # 3. Check for Action / Tool invocation
            parsed = self._parse_action(step_output)
            if parsed:
                tool_name, tool_args = parsed
                observation = self._execute_tool(tool_name, tool_args)
                trajectory.append({
                    "iteration": iteration + 1,
                    "tool": tool_name,
                    "args": tool_args,
                    "observation": observation,
                })
                current_prompt += f"{step_output}\nObservation: {observation}\n"
            else:
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


