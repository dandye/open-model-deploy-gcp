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

Operational Rules:
1. Always follow the Basic IOC Enrichment and Alert Triage runbook procedures.
2. Distinguish benign, non-routable documentation entities (e.g. RFC-5737 192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24) from malicious indicators without hallucinating false positive threats.
3. Structure your final response into four explicit sections:
   - [Context & Enrichment]: Entities identified and tool query findings.
   - [Analysis & Verdict]: Correlation of findings and threat assessment (BENIGN, SUSPICIOUS, MALICIOUS).
   - [Action & Escalation]: Clear recommendation (Close FP, Monitor, or Escalate to Tier 2 / Incident Responder).
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
    ):
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
