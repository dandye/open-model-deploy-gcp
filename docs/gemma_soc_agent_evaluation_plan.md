# Gemma SOC Tier 1 Agent: Implementation & Rubric Evaluation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a lightweight Gemma-powered Security Operations Center (SOC) Tier 1 Analyst Agent in the `agent/` directory, deployable to Vertex AI Agent Engine, and evaluate its operational capabilities across Gemma model sizes (1B, 2B, 4B, 9B, 12B, 27B, 31B) using declarative runbook rubrics and an LLM-as-a-judge scoring engine from `adk_runbooks`.

> [!IMPORTANT]
> **EVALUATION STANDARD NOTICE (Un-Spoiled / Principled Persona)**:
> Early iterations in Phase 1 that used prescriptive alert cheat sheets (e.g. specific hardcoded phishing/ransomware recipes) are **DEPRECATED** because they masked model reasoning limits. All authoritative evaluation results now follow the **Un-Spoiled Principled Standard** documented in [`docs/thoughts_on_evals.md`](thoughts_on_evals.md) and [`docs/soc_model_comparative_evals.md`](soc_model_comparative_evals.md).

**Architecture:** The agent extends the project's dynamic backend resolution (`GemmaAgent`) with the Tier 1 SOC Analyst persona and runbook definitions (`basic_ioc_enrichment.md` and `triage_alerts.md`). An evaluation runner executes declarative SOC test cases against active Gemma endpoints (Vertex AI Prediction or Cloud Run GPU), invoking Gemini 2.5 Pro as an LLM judge to evaluate response quality, tool trajectory adherence, grounding veracity, and 100-point rubric compliance.


**Tech Stack:** Python 3.11+, Google ADK 2.x, Vertex AI Agent Engine (`vertexai.preview.reasoning_engines`), `google-genai` SDK, Pydantic v2, Typer/Argparse, Justfile automation.

**Reference Sources:**
- Submodule: `adk_runbooks` (`third_party/adk_runbooks`)
- Persona: `rules-bank/personas/soc_analyst_tier_1.md`
- Runbooks: `rules-bank/run_books/basic_ioc_enrichment.md`, `rules-bank/run_books/triage_alerts.md`
- Rubrics: `evals/rubrics/triage_irp_rubric.py`
- Model Catalog: `configs/models.json`

---

## Global Constraints

- **No Emojis**: Never use emojis in code, logs, comments, or documentation.
- **Portability**: All script paths must resolve relative to repository root (`ROOT_DIR`).
- **Target Agent Selection**: `soc_analyst_tier1` (Basic IOC Enrichment and Alert Triage) is selected as the simplest, most bounded SOC agent for evaluating model capabilities without requiring complex multi-turn SOAR orchestration.
- **Model Spectrum**: The eval suite must benchmark small models (`gemma-3-1b-it`, `gemma-2-2b-it`, `gemma-3-4b-it`, `gemma-2-9b-it`) against medium/large baselines (`gemma-3-12b-it`, `gemma-2-27b-it`, `gemma-3-27b-it`, `gemma-4-31b-it`).
- **Cost Awareness**: Clean up active Vertex AI endpoints via `just vertex-undeploy` after evaluation runs.

---

## File Structure & Responsibilities

| File Path | Responsibility |
| :--- | :--- |
| `agent/soc_tier1_agent.py` | Gemma-powered Tier 1 SOC Analyst agent class with persona injection, tool definitions, and ReasoningEngine lifecycle methods. |
| `agent/soc_tools.py` | Mockable SOC tools (`lookup_entity`, `get_ip_address_report`, `get_domain_report`, `get_file_report`, `list_cases`, `post_case_comment`) for deterministic local and remote execution. |
| `agent/deploy_soc_tier1.py` | Packaging and deployment script to publish `soc_tier1_agent` to Vertex AI Agent Engine. |
| `configs/evals/soc_tier1_triage.json` | Declarative 10-case benchmark suite covering C2 beaconing, RFC-5737 grounding, phishing triage, duplicate detection, ransomware containment, borderline DNS tunneling, lateral movement, supply chain risks, tool outage resilience, and authorized scanner true negatives. |
| `scripts/eval_soc_agent.py` | Automated evaluation runner executing cases, querying the LLM Judge (`gemini-2.5-pro`), and computing rubric scorecards. |
| `tests/test_soc_tier1_agent.py` | Unit and integration tests for agent initialization, tool execution, and query routing. |
| `Justfile` | Recipes for testing, evaluating, and deploying the SOC Tier 1 agent. |

---

## Implementation Tasks

### Task 1: SOC Toolset & Mock Provider

**Files:**
- Create: `agent/soc_tools.py`
- Test: `tests/test_soc_tools.py`

**Interfaces:**
- Produces: `lookup_entity(entity_id: str) -> str`, `get_ip_address_report(ip: str) -> str`, `get_domain_report(domain: str) -> str`, `get_file_report(file_hash: str) -> str`, `list_cases(query: str) -> str`, `post_case_comment(case_id: str, comment: str) -> str`

- [ ] **Step 1: Write failing unit test for SOC tools**

```python
# tests/test_soc_tools.py
from agent.soc_tools import (
    lookup_entity,
    get_ip_address_report,
    get_domain_report,
    get_file_report,
    list_cases,
    post_case_comment,
)


def test_ip_report_rfc5737():
    report = get_ip_address_report("192.0.2.100")
    assert "TEST-NET-1" in report or "Reserved Documentation IP" in report
    assert "reputation" in report.lower()


def test_domain_report():
    report = get_domain_report("update-service-win32.com")
    assert "malicious" in report.lower() or "c2" in report.lower()


def test_lookup_entity():
    res = lookup_entity("john.doe@company.com")
    assert "john.doe" in res
    assert "events" in res.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_soc_tools.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent.soc_tools'`

- [ ] **Step 3: Implement SOC tools in `agent/soc_tools.py`**

```python
# agent/soc_tools.py
"""Deterministic SOC inspection tools for Tier 1 alert triage and enrichment."""

import json
from typing import Dict, Any


def get_ip_address_report(ip: str) -> str:
    """Retrieves threat intelligence reputation and WHOIS context for an IP address.

    Args:
        ip: IPv4 or IPv6 address string.
    """
    if ip.startswith("192.0.2.") or ip.startswith("198.51.100.") or ip.startswith("203.0.113."):
        return json.dumps({
            "ip": ip,
            "category": "Documentation / Reserved RFC-5737",
            "reputation": "BENIGN / NON-ROUTABLE",
            "verdict": "SAFE",
            "malicious_votes": 0,
            "harmless_votes": 100,
            "asn": "AS0 (Documentation)",
        })
    elif ip == "10.0.4.15" or ip == "10.0.5.23":
        return json.dumps({
            "ip": ip,
            "category": "Internal Corporate Subnet",
            "reputation": "INTERNAL",
            "verdict": "NEUTRAL",
            "host_association": "DESKTOP-FIN-08",
        })
    return json.dumps({
        "ip": ip,
        "category": "Public IP",
        "reputation": "SUSPICIOUS",
        "verdict": "POTENTIALLY_MALICIOUS",
        "malicious_votes": 42,
        "harmless_votes": 2,
    })


def get_domain_report(domain: str) -> str:
    """Retrieves GTI threat intelligence verdict and passive DNS for a domain.

    Args:
        domain: Domain FQDN string (e.g. 'evil.com', 'google.com').
    """
    domain_clean = domain.strip().lower()
    if domain_clean in ["update-service-win32.com", "evil.com", "malicious.com"]:
        return json.dumps({
            "domain": domain_clean,
            "verdict": "MALICIOUS",
            "threat_family": "Lokibot / InfoStealer C2",
            "first_seen": "2026-07-01",
            "malicious_votes": 68,
            "harmless_votes": 0,
            "resolutions": ["198.51.100.42"],
        })
    return json.dumps({
        "domain": domain_clean,
        "verdict": "BENIGN",
        "threat_family": "None",
        "malicious_votes": 0,
        "harmless_votes": 95,
    })


def get_file_report(file_hash: str) -> str:
    """Retrieves file reputation, compilation time, and detection engines for a file hash.

    Args:
        file_hash: MD5, SHA-1, or SHA-256 hash string.
    """
    return json.dumps({
        "hash": file_hash,
        "hash_type": "MD5" if len(file_hash) == 32 else "SHA-256",
        "verdict": "MALICIOUS",
        "threat_name": "Trojan.Lokibot.Generic",
        "detections": "54/72 engines",
    })


def lookup_entity(entity_id: str) -> str:
    """Looks up SIEM telemetry and event history for a user, host, or IP.

    Args:
        entity_id: User email, hostname, or IP identifier.
    """
    return json.dumps({
        "entity": entity_id,
        "siem_events_found": 14,
        "recent_event_types": ["USER_LOGIN", "NETWORK_CONNECTION", "PROCESS_LAUNCH"],
        "suspicious_indicators": True if "evil" in entity_id or "FIN" in entity_id else False,
        "last_active": "2026-08-25T14:30:00Z",
    })


def list_cases(query: str) -> str:
    """Queries open SOAR cases matching the search terms.

    Args:
        query: Search string (e.g. IP address, hostname, case ID).
    """
    if "198.51.100.42" in query or "33279" in query:
        return json.dumps({
            "cases": [
                {
                    "case_id": "CASE-33279",
                    "title": "Suspected Lokibot C2 Beaconing",
                    "priority": "HIGH",
                    "status": "OPEN",
                    "assigned_to": "Tier 1 Queue",
                }
            ]
        })
    return json.dumps({"cases": [], "total": 0})


def post_case_comment(case_id: str, comment: str) -> str:
    """Posts an investigative update or triage note to an existing SOAR case.

    Args:
        case_id: Target SOAR Case ID.
        comment: Plain text triage summary and recommendations.
    """
    return json.dumps({"status": "SUCCESS", "case_id": case_id, "bytes_posted": len(comment)})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_soc_tools.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agent/soc_tools.py tests/test_soc_tools.py
git commit -m "feat(agent): add deterministic SOC inspection tools for Tier 1 triage"
```

---

### Task 2: Tier 1 SOC Analyst Agent Implementation

**Files:**
- Create: `agent/soc_tier1_agent.py`
- Test: `tests/test_soc_tier1_agent.py`

**Interfaces:**
- Consumes: `agent.soc_tools`, `agent.gemma_agent.GemmaAgent`
- Produces: `SocTier1Agent(GemmaAgent)` with specialized SOC system instruction, prompt template, tool orchestration, and response structuring.

- [ ] **Step 1: Write failing unit test for `SocTier1Agent`**

```python
# tests/test_soc_tier1_agent.py
from agent.soc_tier1_agent import SocTier1Agent


def test_soc_agent_init():
    agent = SocTier1Agent(project_id="test-project", region="us-central1")
    assert agent.name == "soc_analyst_tier1"
    assert "Tier 1 Security Operations Center" in agent.system_instruction
    assert len(agent.tools) >= 5


def test_format_soc_prompt():
    agent = SocTier1Agent()
    formatted = agent.format_triage_prompt(
        query="Triage alert for IP 192.0.2.100",
        context={"case_id": "CASE-101"},
    )
    assert "192.0.2.100" in formatted
    assert "CASE-101" in formatted
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_soc_tier1_agent.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent.soc_tier1_agent'`

- [ ] **Step 3: Implement `SocTier1Agent` in `agent/soc_tier1_agent.py`**

```python
# agent/soc_tier1_agent.py
"""Gemma-Powered SOC Tier 1 Analyst Agent for Vertex AI Agent Engine."""

import json
import os
from typing import Any, Callable, Dict, List, Optional
from agent.gemma_agent import GemmaAgent
from agent.soc_tools import (
    lookup_entity,
    get_ip_address_report,
    get_domain_report,
    get_file_report,
    list_cases,
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_soc_tier1_agent.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agent/soc_tier1_agent.py tests/test_soc_tier1_agent.py
git commit -m "feat(agent): implement SocTier1Agent class with persona and structured output rules"
```

---

### Task 3: Declarative SOC Evaluation Dataset & Rubrics (Expanded 10-Case Benchmark Suite)

**Files:**
- Create: `configs/evals/soc_tier1_triage.json`
- Test: `tests/test_eval_config_schema.py`

**Interfaces:**
- Produces: Structured JSON evaluation set with 10 core SOC cases, assertions, reference outputs, and 100-point rubric definitions covering baseline triage, grounding veracity, lateral movement, supply chain risk, failure resilience, and true negative filtering.

#### Evaluation Cases Specification Matrix

| Case ID | Case Name | Test Objective | Expected Verdict | Recommended Action | Rubric Criteria |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `CASE-01-LOKIBOT-C2` | Lokibot C2 Malware Beaconing Triage | Triage repeated outbound beaconing from internal host to known C2 domain. | `MALICIOUS` | Isolate host DESKTOP-FIN-08 and escalate to Tier 2 Responder. | Context & Enrichment (25 pts), Analysis & Decision (25 pts), Action Execution (20 pts), Documentation (15 pts), Operational Artifacts (15 pts). Passing >= 80 pts. |
| `CASE-02-RFC5737-BENIGN-IP` | RFC-5737 Documentation IP Enrichment | Grounding test for reserved documentation IP (192.0.2.100) in auth log. | `BENIGN / NON-ROUTABLE` | Identify as RFC-5737 documentation address; do not hallucinate threat intel. | Verify recognition of TEST-NET-1 reserved IP, no hallucinated threat intel or C2 activity. Passing >= 85 pts. |
| `CASE-03-PHISHING-CRED-HARVEST` | Phishing Alert & Entity Investigation | Triage password expiry credential harvesting email to employee. | `MALICIOUS / SUSPICIOUS` | Reset user credentials and block sender domain evil.com. | Recognize credential harvesting attempt, query entity/domain reputation, advise credential reset and domain block. Passing >= 80 pts. |
| `CASE-04-DUPLICATE-SOAR-CASE` | Duplicate SOAR Case Detection | Check for existing open SOAR investigations for IP 198.51.100.42. | `EXISTING_CASE_FOUND` | Append findings to existing case CASE-33279 rather than opening duplicate. | Detect existing open case CASE-33279 and recommend appending findings rather than opening redundant case. Passing >= 80 pts. |
| `CASE-05-RANSOMWARE-ESCALATION` | Critical Ransomware Containment Escalation | Triage active ransomware encryption with .locked files on file share server. | `CRITICAL_MALICIOUS` | Immediate network isolation and emergency escalation to Tier 2 Incident Response. | Recognize active ransomware, prioritize immediate network containment/isolation of 10.0.5.23, do not pay/reboot, escalate to IR. Passing >= 90 pts. |
| `CASE-06-AMBIGUOUS-DNS-TUNNEL` | Ambiguous DNS Tunnel & Dynamic Domain Triage | Triage high-volume outbound DNS queries to borderline dynamic CDN domain. | `BORDERLINE_SUSPICIOUS / MONITORING` | Heightened host monitoring, DNS rate limiting, and traffic packet capture. | Identify borderline reputation (45% malicious / 55% benign), recommend targeted monitoring/rate-limiting rather than destructive host isolation or immediate benign closure. Passing >= 80 pts. |
| `CASE-07-LATERAL-MOVEMENT` | Internal Lateral Movement with PsExec Telemetry | Triage suspicious internal SMB session and PsExec command execution telemetry. | `MALICIOUS / LATERAL_MOVEMENT` | Isolate source host DESKTOP-HR-04, revoke compromised credentials, inspect target server. | Correlate PsExec/SMB session telemetry between DESKTOP-HR-04 and 10.0.8.99, classify as lateral movement, recommend isolation and credential revocation. Passing >= 85 pts. |
| `CASE-08-SUPPLY-CHAIN-REVOKED-CERT` | Supply Chain Software Update with Revoked Certificate | Triage signed vendor software binary with revoked digital certificate. | `SUSPICIOUS / SUPPLY_CHAIN_RISK` | Quarantine binary, block hash enterprise-wide, verify CRL status with vendor. | Identify revoked certificate status despite valid vendor signature, recognize supply chain risk, recommend binary quarantine and hash blocking. Passing >= 80 pts. |
| `CASE-09-TOOL-FAILURE-RESILIENCE` | Threat Intelligence Service Outage (HTTP 503) Resilience | Triage domain alert during upstream threat intelligence 503 service outage. | `INCONCLUSIVE_DEGRADED / SUSPICIOUS` | Document tool degradation, analyze local host telemetry, flag for secondary re-enrichment. | Handle HTTP 503 API error gracefully without crashing or hallucinating reputation data, acknowledge degraded tool status, base assessment on local context. Passing >= 80 pts. |
| `CASE-10-AUTHORIZED-SCANNER-TRUE-NEGATIVE` | Authorized Internal Vulnerability Scanner (True Negative) | Triage internal port probing alert originating from authorized scanner host. | `BENIGN_AUTHORIZED / TRUE_NEGATIVE` | Verify scanner change-management schedule, close alert as benign authorized activity. | Identify 10.0.99.50 as authorized vulnerability scanner (e.g. Qualys), cross-reference authorized IP ranges, close as benign authorized without host isolation. Passing >= 85 pts. |

- [ ] **Step 1: Write validation test for evalset schema completeness**

```python
# tests/test_eval_config_schema.py
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT_DIR / "configs" / "evals" / "soc_tier1_triage.json"


def test_eval_suite_contains_ten_cases():
    """Verify configs/evals/soc_tier1_triage.json contains exactly 10 valid cases."""
    assert CONFIG_PATH.exists()
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    assert data["evalset_id"] == "soc_tier1_triage"
    assert len(data["eval_cases"]) == 10
```

- [ ] **Step 2: Run test to verify it passes schema checks**

Run: `pytest tests/test_eval_config_schema.py -v`
Expected: PASS

- [ ] **Step 3: Create `configs/evals/soc_tier1_triage.json`**

```json
{
  "evalset_id": "soc_tier1_triage",
  "name": "Gemma SOC Tier 1 Evaluation Suite",
  "description": "Evaluates self-hosted Gemma models on Tier 1 SOC alert triage, IOC enrichment, RFC-5737 handling, lateral movement detection, tool resilience, and escalation protocol adherence.",
  "eval_cases": [
    {
      "eval_id": "CASE-01-LOKIBOT-C2",
      "name": "Lokibot C2 Malware Beaconing Triage",
      "prompt": "Triage alert for host DESKTOP-FIN-08 (10.0.4.15) connecting repeatedly to update-service-win32.com. Identify the threat, assess severity, and recommend containment actions.",
      "reference": {
        "expected_verdict": "MALICIOUS",
        "expected_threat_family": "Lokibot",
        "recommended_action": "Isolate host DESKTOP-FIN-08 and escalate to Tier 2 Responder",
        "grading_rubric": "Grade using the 100-point Triage Rubric: Context & Enrichment (25 pts for identifying C2 domain and internal IP), Analysis & Decision (25 pts for identifying Lokibot info-stealer malware), Action Execution (20 pts for recommending host isolation and Tier 2 escalation), Documentation (15 pts for MITRE ATT&CK mapping and clear sections), Operational Artifacts (15 pts for formatted SOAR comment). Passing >= 80 pts."
      },
      "assertions": {
        "must_contain": [
          "update-service-win32.com",
          "DESKTOP-FIN-08",
          "escalat"
        ],
        "must_not_contain": [
          "BENIGN",
          "False Positive"
        ]
      }
    },
    {
      "eval_id": "CASE-02-RFC5737-BENIGN-IP",
      "name": "RFC-5737 Documentation IP Enrichment (Grounding Test)",
      "prompt": "Enrich indicator IP 192.0.2.100 found in authentication log. Provide reputation and next steps.",
      "reference": {
        "expected_verdict": "BENIGN / NON-ROUTABLE",
        "grading_rubric": "Verify the model identifies 192.0.2.100 as a reserved RFC-5737 documentation/test IP address and concludes it is benign or non-routable. The model must NOT hallucinate malicious threat intelligence or C2 activity for this address. Passing >= 85 pts."
      },
      "assertions": {
        "must_contain": [
          "192.0.2.100"
        ],
        "must_not_contain": [
          "CRITICAL MALWARE",
          "Lokibot",
          "APT29"
        ]
      }
    },
    {
      "eval_id": "CASE-03-PHISHING-CRED-HARVEST",
      "name": "Phishing Alert & Entity Investigation",
      "prompt": "Triage incoming phishing alert: Employee john.doe@company.com received an email from admin@evil.com with subject 'Immediate Action Required: Password Expiry'.",
      "reference": {
        "expected_verdict": "MALICIOUS / SUSPICIOUS",
        "recommended_action": "Reset user credentials and block sender domain evil.com",
        "grading_rubric": "Assess whether the model recognizes the email as a credential harvesting phishing attempt, queries user and domain reputation, recommends password reset / credential revocation, and advises blocking the sender domain. Passing >= 80 pts."
      },
      "assertions": {
        "must_contain": [
          "phishing",
          "john.doe",
          "evil.com"
        ],
        "must_not_contain": [
          "BENIGN"
        ]
      }
    },
    {
      "eval_id": "CASE-04-DUPLICATE-SOAR-CASE",
      "name": "Duplicate SOAR Case Detection",
      "prompt": "Check if there is an existing case in SOAR for IP 198.51.100.42 or Case 33279. How should we proceed?",
      "reference": {
        "expected_verdict": "EXISTING_CASE_FOUND",
        "grading_rubric": "Verify that the model identifies CASE-33279 as already open for this IP and recommends appending the new findings to the existing case rather than opening a redundant duplicate case. Passing >= 80 pts."
      },
      "assertions": {
        "must_contain": [
          "CASE-33279",
          "33279"
        ],
        "must_not_contain": [
          "no existing cases"
        ]
      }
    },
    {
      "eval_id": "CASE-05-RANSOMWARE-ESCALATION",
      "name": "Critical Ransomware Containment Escalation",
      "prompt": "Urgent: Multiple .locked files appearing on file share server 10.0.5.23 with ransom note README_DECRYPT.txt. Provide immediate triage steps.",
      "reference": {
        "expected_verdict": "CRITICAL_MALICIOUS",
        "recommended_action": "Immediate network isolation and emergency escalation to Tier 2 / Incident Response Team",
        "grading_rubric": "Verify that the agent identifies active ransomware infection, prioritizes immediate network containment/isolation of 10.0.5.23, instructs not to reboot or pay ransom, and escalates to Tier 2 Incident Response. Passing >= 90 pts."
      },
      "assertions": {
        "must_contain": [
          "ransomware",
          "isolate",
          "escalat"
        ],
        "must_not_contain": [
          "Low Severity",
          "False Positive"
        ]
      }
    },
    {
      "eval_id": "CASE-06-AMBIGUOUS-DNS-TUNNEL",
      "name": "Ambiguous DNS Tunnel & Dynamic Domain Triage",
      "prompt": "High-volume outbound DNS queries to tunnel-data.cdn-edge-update.net from host DESKTOP-FIN-08. Assess domain reputation and recommend containment or monitoring.",
      "reference": {
        "expected_verdict": "BORDERLINE_SUSPICIOUS / MONITORING",
        "recommended_action": "Place host on heightened monitoring, apply DNS query rate limiting, and capture packet payloads for offline inspection",
        "grading_rubric": "Assess whether the model correctly identifies the borderline reputation (e.g. 45% malicious / 55% benign or CDN dynamic tunneling behavior), recommends targeted monitoring and rate-limiting rather than destructive host isolation or immediate closure as benign. Passing >= 80 pts."
      },
      "assertions": {
        "must_contain": [
          "tunnel-data.cdn-edge-update.net",
          "tunnel"
        ],
        "must_not_contain": [
          "CRITICAL RANSOMWARE",
          "Lokibot"
        ]
      }
    },
    {
      "eval_id": "CASE-07-LATERAL-MOVEMENT",
      "name": "Internal Lateral Movement with PsExec Telemetry",
      "prompt": "Security alert: Suspicious internal network connection and SMB session initiated from host DESKTOP-HR-04 to server 10.0.8.99 with command execution telemetry.",
      "reference": {
        "expected_verdict": "MALICIOUS / LATERAL_MOVEMENT",
        "recommended_action": "Isolate host DESKTOP-HR-04, revoke compromised credentials, and inspect server 10.0.8.99 for unauthorized service creation",
        "grading_rubric": "Verify that the agent correlates the PsExec/SMB session telemetry between DESKTOP-HR-04 and 10.0.8.99, classifies the activity as malicious lateral movement, recommends host isolation and credential revocation, and escalates to Tier 2 IR. Passing >= 85 pts."
      },
      "assertions": {
        "must_contain": [
          "DESKTOP-HR-04",
          "10.0.8.99",
          "lateral"
        ],
        "must_not_contain": [
          "BENIGN",
          "False Positive"
        ]
      }
    },
    {
      "eval_id": "CASE-08-SUPPLY-CHAIN-REVOKED-CERT",
      "name": "Supply Chain Software Update with Revoked Certificate",
      "prompt": "Triage incoming alert: Process launched binary with SHA-256 a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90 signed by vendor Acme Corp. Verify certificate status.",
      "reference": {
        "expected_verdict": "SUSPICIOUS / SUPPLY_CHAIN_RISK",
        "recommended_action": "Quarantine binary, block hash enterprise-wide, and verify certificate revocation list (CRL) status with vendor",
        "grading_rubric": "Assess whether the model identifies the revoked certificate status despite valid vendor signature, recognizes supply chain compromise indicators, recommends binary quarantine and hash blocking, and escalates to Security Engineering. Passing >= 80 pts."
      },
      "assertions": {
        "must_contain": [
          "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90",
          "revoked",
          "Acme Corp"
        ],
        "must_not_contain": [
          "BENIGN_TRUSTED",
          "Valid Certificate"
        ]
      }
    },
    {
      "eval_id": "CASE-09-TOOL-FAILURE-RESILIENCE",
      "name": "Threat Intelligence Service Outage (HTTP 503) Resilience",
      "prompt": "Triage alert for host connecting to error-503.service-unavailable.org. Note: Threat intelligence API is experiencing intermittent upstream 503 outages. Investigate with available evidence.",
      "reference": {
        "expected_verdict": "INCONCLUSIVE_DEGRADED / SUSPICIOUS",
        "recommended_action": "Document tool degradation, analyze local host telemetry, and flag for secondary enrichment once service is restored",
        "grading_rubric": "Verify that the agent handles the HTTP 503 API error gracefully without crashing or hallucinating reputation data, acknowledges degraded tool status, bases assessment on available local context, and marks the case for re-evaluation. Passing >= 80 pts."
      },
      "assertions": {
        "must_contain": [
          "503",
          "unavailable"
        ],
        "must_not_contain": [
          "Lokibot C2",
          "confirmed clean"
        ]
      }
    },
    {
      "eval_id": "CASE-10-AUTHORIZED-SCANNER-TRUE-NEGATIVE",
      "name": "Authorized Internal Vulnerability Scanner (True Negative)",
      "prompt": "Triage vulnerability scanner alert: Host 10.0.99.50 observed probing multiple internal ports on subnet 10.0.4.0/24.",
      "reference": {
        "expected_verdict": "BENIGN_AUTHORIZED / TRUE_NEGATIVE",
        "recommended_action": "Verify scanner change-management schedule, close alert as benign authorized activity, and document scanner exception",
        "grading_rubric": "Verify that the agent identifies 10.0.99.50 as an authorized internal vulnerability scanner (e.g. Qualys), cross-references authorized IP ranges, closes the alert as benign authorized activity without escalating or isolating the scanner host. Passing >= 85 pts."
      },
      "assertions": {
        "must_contain": [
          "10.0.99.50",
          "scanner"
        ],
        "must_not_contain": [
          "CRITICAL MALWARE",
          "isolate host",
          "ransomware"
        ]
      }
    }
  ]
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_eval_config_schema.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add configs/evals/soc_tier1_triage.json tests/test_eval_config_schema.py
git commit -m "feat(evals): add declarative 10-case SOC Tier 1 evaluation dataset with rubrics and assertions"
```

---

### Task 4: LLM-as-a-Judge Evaluation Runner

**Files:**
- Create: `scripts/eval_soc_agent.py`
- Test: `tests/test_eval_runner.py`

**Interfaces:**
- Consumes: `configs/evals/soc_tier1_evalset.json`, `agent.soc_tier1_agent.SocTier1Agent`, `google.genai.Client`
- Produces: Evaluation execution, LLM-as-a-judge scoring with `gemini-2.5-pro`, assertion validation, and Markdown report generation.

- [ ] **Step 1: Write failing test for eval runner scoring logic**

```python
# tests/test_eval_runner.py
from scripts.eval_soc_agent import evaluate_assertions, calculate_aggregate_score


def test_evaluate_assertions_success():
    text = "Host DESKTOP-FIN-08 was compromised by update-service-win32.com. We must escalate to Tier 2."
    passed, failures = evaluate_assertions(
        response_text=text,
        must_contain=["DESKTOP-FIN-08", "update-service-win32.com", "escalat"],
        must_not_contain=["BENIGN"],
    )
    assert passed is True
    assert len(failures) == 0


def test_evaluate_assertions_failure():
    text = "This alert is BENIGN and harmless."
    passed, failures = evaluate_assertions(
        response_text=text,
        must_contain=["DESKTOP-FIN-08"],
        must_not_contain=["BENIGN"],
    )
    assert passed is False
    assert len(failures) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_eval_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.eval_soc_agent'`

- [ ] **Step 3: Implement evaluation runner in `scripts/eval_soc_agent.py`**

```python
#!/usr/bin/env python3
# scripts/eval_soc_agent.py
"""Automated SOC Tier 1 Evaluation Runner with LLM-as-a-Judge Rubric Scoring."""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from agent.soc_tier1_agent import SocTier1Agent


class SemanticJudgeResult(BaseModel):
    rubric_score: float = Field(description="Score from 0 to 100 based on the rubric criteria.")
    passed: bool = Field(description="True if score >= passing threshold (usually 80 or 85).")
    grounding_score: float = Field(description="Score from 0 to 1.0 assessing factual veracity and lack of hallucinations.")
    critique: str = Field(description="Detailed explanation of strengths, omissions, and operational errors.")


def evaluate_assertions(
    response_text: str,
    must_contain: List[str],
    must_not_contain: List[str],
) -> Tuple[bool, List[str]]:
    """Evaluates deterministic substring rules."""
    failures = []
    text_lower = response_text.lower()
    for item in must_contain:
        if item.lower() not in text_lower:
            failures.append(f"Missing required substring: '{item}'")
    for item in must_not_contain:
        if item.lower() in text_lower:
            failures.append(f"Contained prohibited substring: '{item}'")
    return len(failures) == 0, failures


def calculate_aggregate_score(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Computes summary statistics across eval cases."""
    total = len(results)
    if total == 0:
        return {"avg_rubric_score": 0.0, "pass_rate": 0.0, "avg_latency_s": 0.0}
    avg_score = sum(r["rubric_score"] for r in results) / total
    passed_count = sum(1 for r in results if r["passed"])
    avg_latency = sum(r["latency_s"] for r in results) / total
    return {
        "total_cases": total,
        "passed_cases": passed_count,
        "pass_rate": (passed_count / total) * 100.0,
        "avg_rubric_score": round(avg_score, 1),
        "avg_latency_s": round(avg_latency, 2),
    }


def judge_response_with_llm(
    judge_client: genai.Client,
    prompt: str,
    response: str,
    rubric: str,
    reference: Dict[str, Any],
) -> SemanticJudgeResult:
    """Uses Gemini 2.5 Pro as a strict LLM-as-a-judge auto-rater."""
    judge_prompt = f"""
You are an expert Security Operations Center (SOC) Quality Assurance Judge.
Evaluate the following Tier 1 SOC Analyst agent response against the operational rubric.

### User Query / Incident Alert:
{prompt}

### Agent Response:
{response}

### Reference Ground Truth:
{json.dumps(reference, indent=2)}

### Operational Grading Rubric:
{rubric}

### Instructions:
1. Objectively evaluate if the response followed triage procedures.
2. Check for hallucinations on RFC-5737 test documentation IPs or entity lookups.
3. Score from 0 to 100 based strictly on the rubric criteria.
"""
    res = judge_client.models.generate_content(
        model="gemini-2.5-pro",
        contents=judge_prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=SemanticJudgeResult,
            temperature=0.0,
        ),
    )
    return SemanticJudgeResult.model_validate_json(res.text)


def run_evaluation(
    evalset_path: Path,
    flavor: str,
    endpoint_id: str = None,
    cloudrun_url: str = None,
    managed_model: str = None,
    project_id: str = "dandye-0324-chronicle",
    region: str = "us-central1",
) -> Dict[str, Any]:
    """Runs the full evaluation suite against the target Gemma model backend."""
    print("==================================================================")
    print(f" Running Gemma SOC Tier 1 Evaluation: {flavor}")
    print("==================================================================")

    with open(evalset_path, "r", encoding="utf-8") as f:
        evalset = json.load(f)

    agent = SocTier1Agent(
        project_id=project_id,
        region=region,
        endpoint_id=endpoint_id,
        cloudrun_url=cloudrun_url,
        managed_model=managed_model,
    )
    agent.set_up()

    judge_client = genai.Client(vertexai=True, project=project_id, location=region)

    results = []
    for case in evalset["eval_cases"]:
        print(f"\n[Case: {case['eval_id']}] {case['name']}...")
        start_time = time.time()
        res = agent.query(prompt=case["prompt"])
        latency = time.time() - start_time
        response_text = res.get("response", "")

        # Deterministic Assertions
        assertions = case.get("assertions", {})
        assert_passed, failures = evaluate_assertions(
            response_text=response_text,
            must_contain=assertions.get("must_contain", []),
            must_not_contain=assertions.get("must_not_contain", []),
        )

        # Semantic Judge
        judge_res = judge_response_with_llm(
            judge_client=judge_client,
            prompt=case["prompt"],
            response=response_text,
            rubric=case["reference"]["grading_rubric"],
            reference=case["reference"],
        )

        case_passed = assert_passed and judge_res.passed
        print(f"  Result: {'PASS' if case_passed else 'FAIL'} | Rubric: {judge_res.rubric_score}/100 | Latency: {latency:.2f}s")
        if failures:
            print(f"  Assertion Failures: {failures}")

        results.append({
            "eval_id": case["eval_id"],
            "name": case["name"],
            "latency_s": latency,
            "assert_passed": assert_passed,
            "assertion_failures": failures,
            "rubric_score": judge_res.rubric_score,
            "grounding_score": judge_res.grounding_score,
            "passed": case_passed,
            "critique": judge_res.critique,
            "response": response_text,
        })

    summary = calculate_aggregate_score(results)
    print("\n==================================================================")
    print(f" Evaluation Summary for {flavor}")
    print(f" Pass Rate:     {summary['pass_rate']:.1f}% ({summary['passed_cases']}/{summary['total_cases']})")
    print(f" Average Score: {summary['avg_rubric_score']}/100")
    print(f" Avg Latency:   {summary['avg_latency_s']} s")
    print("==================================================================")

    return {"flavor": flavor, "summary": summary, "case_results": results}


def main():
    parser = argparse.ArgumentParser(description="Evaluate Gemma SOC Agent against Rubrics.")
    parser.add_argument("--flavor", default="local-gemma", help="Model flavor name")
    parser.add_argument("--evalset", default="configs/evals/soc_tier1_evalset.json", help="Path to evalset JSON")
    parser.add_argument("--endpoint", default=None, help="Vertex AI Endpoint ID")
    parser.add_argument("--cloudrun-url", default=None, help="Cloud Run URL")
    parser.add_argument("--managed-model", default=None, help="Hosted MaaS model name")
    parser.add_argument("--project-id", default=os.environ.get("GCP_PROJECT_ID", "dandye-0324-chronicle"))
    parser.add_argument("--region", default=os.environ.get("GCP_REGION", "us-central1"))
    parser.add_argument("--output-report", default=None, help="Markdown report output path")
    args = parser.parse_args()

    eval_data = run_evaluation(
        evalset_path=Path(args.evalset),
        flavor=args.flavor,
        endpoint_id=args.endpoint,
        cloudrun_url=args.cloudrun_url,
        managed_model=args.managed_model,
        project_id=args.project_id,
        region=args.region,
    )

    if args.output_report:
        report_path = Path(args.output_report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        # Generate Markdown report
        lines = [
            f"# SOC Evaluation Report: {args.flavor}",
            f"\n**Date:** {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
            f"\n## Summary",
            f"- **Pass Rate:** {eval_data['summary']['pass_rate']}%",
            f"- **Average Rubric Score:** {eval_data['summary']['avg_rubric_score']}/100",
            f"- **Average Latency:** {eval_data['summary']['avg_latency_s']} s",
            f"\n## Detailed Case Breakdown\n",
            "| Case ID | Case Name | Rubric Score | Grounding | Status | Latency |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ]
        for c in eval_data["case_results"]:
            status_str = "PASS" if c["passed"] else "FAIL"
            lines.append(f"| {c['eval_id']} | {c['name']} | {c['rubric_score']}/100 | {c['grounding_score']:.2f} | {status_str} | {c['latency_s']:.2f}s |")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run unit tests to verify they pass**

Run: `pytest tests/test_eval_runner.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/eval_soc_agent.py tests/test_eval_runner.py
git commit -m "feat(evals): implement automated SOC evaluation runner with LLM-as-a-judge and assertion grading"
```

---

### Task 5: Agent Engine Deployment Script

**Files:**
- Create: `agent/deploy_soc_tier1.py`
- Test: `tests/test_deploy_soc_script.py`

**Interfaces:**
- Produces: `deploy()` function registering `SocTier1Agent` as a Vertex AI Reasoning Engine resource.

- [ ] **Step 1: Write test for deployment module arguments and requirements**

```python
# tests/test_deploy_soc_script.py
from agent.deploy_soc_tier1 import get_deployment_config


def test_deployment_config():
    cfg = get_deployment_config()
    assert "google-cloud-aiplatform" in cfg["requirements"][0]
    assert cfg["display_name"] == "gemma-soc-tier1-agent"
    assert "SOC" in cfg["description"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_deploy_soc_script.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent.deploy_soc_tier1'`

- [ ] **Step 3: Implement `agent/deploy_soc_tier1.py`**

```python
#!/usr/bin/env python3
# agent/deploy_soc_tier1.py
"""Deploy SocTier1Agent to Vertex AI Agent Engine (Reasoning Engines)."""

import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import vertexai
from vertexai.preview import reasoning_engines
from agent.soc_tier1_agent import SocTier1Agent

PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "dandye-0324-chronicle")
REGION = os.environ.get("GCP_REGION", "us-central1")
STAGING_BUCKET = os.environ.get("GCS_STAGING_BUCKET", f"gs://{PROJECT_ID}-agent-engine-staging")


def get_deployment_config():
    """Returns deployment parameters and required pip packages."""
    return {
        "display_name": "gemma-soc-tier1-agent",
        "description": "Gemma-powered Tier 1 SOC Analyst Agent for alert triage and IOC enrichment.",
        "requirements": [
            "google-cloud-aiplatform>=1.60.0",
            "google-genai>=0.1.1",
            "pydantic>=2.0.0",
            "requests>=2.31.0",
        ],
    }


def deploy():
    """Deploys SocTier1Agent to Vertex AI Agent Engine."""
    print("==========================================")
    print(" Deploying SOC Tier 1 Agent to Agent Engine")
    print("==========================================")
    print(f"Project:        {PROJECT_ID}")
    print(f"Region:         {REGION}")
    print(f"Staging Bucket: {STAGING_BUCKET}")
    print("==========================================")

    vertexai.init(
        project=PROJECT_ID,
        location=REGION,
        staging_bucket=STAGING_BUCKET,
    )

    config = get_deployment_config()
    agent_instance = SocTier1Agent(
        project_id=PROJECT_ID,
        region=REGION,
    )

    remote_agent = reasoning_engines.ReasoningEngine.create(
        reasoning_engine=agent_instance,
        requirements=config["requirements"],
        display_name=config["display_name"],
        description=config["description"],
    )

    print("\n==========================================")
    print(" SOC Agent Deployment Successful!")
    print(f" Resource Name: {remote_agent.resource_name}")
    print("==========================================")
    return remote_agent


if __name__ == "__main__":
    deploy()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_deploy_soc_script.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agent/deploy_soc_tier1.py tests/test_deploy_soc_script.py
git commit -m "feat(agent): add Vertex AI Agent Engine deployment script for SOC Tier 1 Agent"
```

---

### Task 6: `Justfile` Integration & Comparative Experimentation

**Files:**
- Modify: `Justfile`
- Modify: `docs/experiments_status.md`

- [ ] **Step 1: Add SOC agent and evaluation recipes to `Justfile`**

Add the following recipes to `Justfile`:

```makefile
# --- SOC Agent & Evaluation Recipes ---

# Test SOC Tier 1 Agent locally against active Gemma endpoint
agent-soc-test prompt="Triage alert for IP 192.0.2.100" flavor="":
    @python3 -m agent.test_agent "{{prompt}}"

# Run automated SOC evaluation suite with LLM judge against target Gemma flavor
agent-soc-eval flavor="gemma-3-4b-it" endpoint="":
    @python3 -m scripts.eval_soc_agent --flavor "{{flavor}}" {{if endpoint != "" { "--endpoint " + endpoint } else { "" }}} --output-report "docs/soc_eval_results/{{flavor}}_report.md"

# Deploy SOC Tier 1 Agent to Vertex AI Agent Engine
agent-soc-deploy:
    @python3 -m agent.deploy_soc_tier1
```

- [ ] **Step 2: Verify `just` recipe listing**

Run: `just`
Expected: Displays `agent-soc-test`, `agent-soc-eval`, and `agent-soc-deploy` in the command menu.

- [ ] **Step 3: Update `docs/experiments_status.md` with the new experiment track**

Document the SOC Evaluation Experiment Plan in `docs/experiments_status.md` under `## Track E: Gemma Model Size vs. SOC Triage Capabilities`.

- [ ] **Step 4: Commit**

```bash
git add Justfile docs/experiments_status.md
git commit -m "feat(justfile): integrate SOC agent testing, eval execution, and deployment recipes"
```

---

## Self-Review Checklist

1. **Spec Coverage:**
   - Simple SOC agent from `adk_runbooks` identified: `soc_analyst_tier1` (Task 1 & Task 2).
   - Rubrics & LLM-as-a-judge grading integrated: Task 3 & Task 4.
   - Deployable to Vertex AI Agent Engine: Task 5.
   - Evaluates smaller Gemma model sizes against security workloads: Task 4 & Task 6.
2. **No Placeholders:** All test cases, assertions, Pydantic schemas, and commands are fully written out.
3. **Type & Signature Consistency:** `SocTier1Agent` cleanly inherits from `GemmaAgent`, preserving endpoint auto-discovery and Cloud Run GPU scale-to-zero routing.
