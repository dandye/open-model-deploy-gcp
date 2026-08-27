# Llama & Partner Models SOC Agent Evaluation Plan

## 1. Overview & Objectives

This document defines the evaluation framework, methodology, and scoring criteria for evaluating Meta Llama models and Model Garden partner models (Thinking Machines, NVIDIA, xAI) within the SOC Tier 1 automated triage workflow.

To ensure consistency with prior Gemma benchmarks, all models are evaluated against the identical declarative benchmark suite ([`configs/evals/soc_tier1_evalset.json`](../configs/evals/soc_tier1_evalset.json)) using an un-spoiled, principled ReAct analyst persona without prompt overfitting.

---

## 2. Target Models & Serving Modes

| Model Key | Display Name | Provider | Serving Tier | Architecture / Parameters | Region |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `llama-4-maverick-17b-128e-instruct-maas` | Llama 4 Maverick 17B-128E | Meta | Vertex AI MaaS | 17B active MoE (128 experts) | `us-east5` |
| `llama-4-scout-17b-16e-instruct-maas` | Llama 4 Scout 17B-16E | Meta | Vertex AI MaaS | 17B active MoE (16 experts) | `us-east5` |
| `inkling-small` | Inkling Small | Thinking Machines | Model Garden | Multimodal Foundation Model | `us-central1` |
| `nemotron-3.5-lightning-bf16` | Nemotron 3.5 Lightning BF16 | NVIDIA | Model Garden | 30B MoE (3B active) | `us-central1` |
| `grok-4.6` | Grok 4.6 | xAI | Vertex AI MaaS | Frontier Reasoning Model | `global` |

---

## 3. Evaluation Framework & Un-Spoiled Persona

### 3.1 Principles
1. **Zero Prompt Overfitting**: The agent system prompt ([`agent/soc_tier1_agent.py`](../agent/soc_tier1_agent.py)) provides general investigative methodology and tool descriptions. No case-specific rules, indicators, or answer keys are embedded.
2. **Autonomous Tool Selection**: The model must determine when and how to call external tools (`get_entity_report`, `search_threat_intel`, `query_security_events`, `soar_get_case_details`, `soar_add_comment`, `soar_update_severity`).
3. **Structured SOAR Output**: All final answers must output four standardized sections:
   - `[Context & Enrichment]`
   - `[Analysis & Verdict]` (BENIGN, SUSPICIOUS, or MALICIOUS)
   - `[Action & Escalation]`
   - `[SOAR Documentation]`

---

## 4. Benchmark Evaluation Suite (5 Core Scenarios)

The evaluation suite exercises five distinct security engineering capabilities:

| Case ID | Scenario Name | Primary Capability Tested |
| :--- | :--- | :--- |
| `CASE-01-LOKIBOT-C2` | Lokibot C2 Malware Beaconing Triage | Multi-hop indicator correlation & malicious verdict synthesis |
| `CASE-02-RFC5737-BENIGN-IP` | RFC-5737 Documentation IP Enrichment | Epistemic grounding & false positive resolution (must not flag documentation IP as malicious) |
| `CASE-03-PHISHING-CRED-HARVEST` | Phishing Alert & Entity Investigation | Autonomous entity pivoting, credential compromise containment, and user notification |
| `CASE-04-DUPLICATE-SOAR-CASE` | Duplicate SOAR Case Detection | Historical SOAR case lookups, deduplication, and case continuity |
| `CASE-05-RANSOMWARE-ESCALATION` | Critical Ransomware Containment Escalation | High-urgency incident triage, host containment, and severity escalation |

---

## 5. Scoring & Grading Methodology

Each scenario is evaluated through two complementary layers:

### 5.1 Deterministic Assertions
- Exact string presence (`must_contain`) and absence (`must_not_contain`) verifying that key operational actions and correct verdicts are present without forbidden hallucinations.

### 5.2 LLM-as-a-Judge (Gemini 2.5 Pro)
- **100-point Rubric Score**: Evaluates technical accuracy, evidence-backed verdict, escalation justification, and SOAR documentation completeness.
- **Grounding Score (0.0–1.0)**: Measures adherence to tool observations vs ungrounded claims.
- **Structured Critique**: Diagnostic feedback on agent reasoning and trajectory.

---

## 6. Execution Commands

```bash
# Evaluate Llama 4 Maverick
just eval-llama llama-4-maverick-17b-128e-instruct-maas

# Evaluate Llama 4 Scout
just eval-llama llama-4-scout-17b-16e-instruct-maas

# Custom evaluation run
uv run python3 -m scripts.eval_soc_agent --flavor "llama-4-scout-17b-16e-instruct-maas" --output-report "docs/soc_eval_results/llama-4-scout-17b-16e-instruct-maas_report.md"
```
