"""Gemma-Powered SOC Tier 1 Analyst Agent for Vertex AI Agent Engine."""

from typing import Any, Callable, Dict, List, Optional
from agent.gemma_agent import GemmaAgent
from agent.soc_tools import (
    get_domain_report,
    get_file_report,
    get_ip_address_report,
    list_cases,
    lookup_entity,
    post_case_comment,
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
    """Reasoning Engine compatible Tier 1 SOC Analyst Agent powered by Gemma."""

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

    def format_triage_prompt(self, query: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Formats an operational triage request with optional case metadata."""
        if not context:
            return query
        ctx_str = "\n".join(f"- {k}: {v}" for k, v in context.items())
        return f"Operational Triage Request:\n{query}\n\nCase Context:\n{ctx_str}\n\nPerform initial investigation and provide the triage report."

    def query(self, prompt: str, max_tokens: int = 1024, temperature: float = 0.2) -> Dict[str, Any]:
        """Executes triage reasoning with lower temperature for operational determinism."""
        return super().query(prompt=prompt, max_tokens=max_tokens, temperature=temperature)
