# Gen 3 Comprehensive Enhancement Design Specification

## 1. Executive Summary

This specification addresses all structural, fidelity, and scoring limitations identified during the initial Gen 3 evaluation sweeps:
1. **Unbounded Generation Budget**: Eliminate artificial token truncation (`max_tokens=1024`) across the agent and evaluation layers so deliberative reasoning models (`gemini-2.5-pro`) complete their full multi-step analysis without mid-sentence cutoffs.
2. **Tiered Action Verification (Primary vs. Secondary)**: Decouple primary operational interventions (`isolate_host`, `block_indicator`, `close_case`) from secondary administrative documentation (`update_case_comment`), preventing models with 100/100 threat containment from failing on secondary comment fields.
3. **Multi-Syntax Tool Parsing & Few-Shot Exemplars**: Expand action parsing in `SocTier1Agent` to accept JSON function calls (`{"name": "...", "arguments": {...}}`), fenced tool syntax, and standard ReAct, supplemented with few-shot exemplars so compact models ($\le$4B) exercise autonomous tool invocation.
4. **High-Fidelity Telemetry Payloads**: Replace synthetic spoon-fed verdicts in `agent/soc_environment.py` and `agent/soc_tools.py` with realistic telemetry (VirusTotal detection ratios, WHOIS registrar details, RFC-5737 IP route classifications, and parent process trees).
5. **Explicit CMDB Asset & Financial Blast-Radius Context**: Provide real-world CMDB asset metadata and operational downtime risks directly in evaluation prompts so models can reason about business impact before containment.
6. **Counterfactual Consistency Evaluation**: Introduce paired-case counterfactual consistency scoring to measure whether models discriminate between real threats and ambiguous/benign twins.

---

## 2. Architectural Design

### 2.1 Unbounded Generation Budget (`agent/gemma_agent.py`, `agent/soc_tier1_agent.py`, `scripts/eval_soc_agent.py`)
- Change `max_tokens` default from `1024` to `None` across `SocTier1Agent.query()`, `_call_llm_step()`, and `GemmaAgent.query()`.
- When `max_tokens is None`:
  - Vertex AI MaaS (`google.genai`): Omit `max_output_tokens` in `GenerateContentConfig` to allow full model capacity (8,192+ tokens).
  - Vertex AI Endpoints / Cloud Run (vLLM): Use generous headroom `8192` instead of restrictive `512` or `1024`.

### 2.2 Tiered Action Matching (`scripts/eval_trajectory_verifier.py`)
- Split action taxonomy:
  - `PRIMARY_ACTIONS`: `isolate_host`, `unblock_host`, `block_indicator`, `close_case`.
  - `SECONDARY_ACTIONS`: `update_case_comment`, `create_case_comment`, `post_case_comment`.
- In `verify_agent_trajectory()`:
  - Separate `expected_actions` into `expected_primary` and `expected_secondary`.
  - Compute `primary_actions_matched = all(act in all_actions for act in expected_primary)`.
  - Compute `secondary_actions_matched = all(act in all_actions for act in expected_secondary)`.
  - Evaluate `actions_matched = primary_actions_matched` for pass-gate determination.
  - Record secondary action compliance in verification notes and diagnostic metadata.

### 2.3 Multi-Syntax Tool Parsing & Prompt Exemplars (`agent/soc_tier1_agent.py`)
- Support 3 distinct tool invocation grammars in `_parse_action()`:
  1. Standard ReAct: `Action: tool_name(arg="val", ...)`
  2. JSON Object: `Action: {"name": "tool_name", "arguments": {"arg": "val"}}` or `{"tool": "tool_name", "args": {...}}`
  3. Fenced Block: ````tool_call\n{"name": "...", "args": {...}}\n````
- Add two clear few-shot exemplars in `SOC_TIER1_PERSONA` demonstrating:
  - Step 1: Investigating an indicator with `get_ip_address_report(ip="192.0.2.100")`.
  - Step 2: Concluding with final report and structured ````soc_decision```` block.

### 2.4 Realistic Telemetry Payloads (`agent/soc_environment.py`, `agent/soc_tools.py`)
- Replace canned `{"verdict": "MALICIOUS"}` with rich, noisy telemetry:
  - `get_domain_report`: VirusTotal detections (`positives: 48, total: 72`), registrar (`NameCheap`), creation date (`2026-08-28`), DNS history (`198.51.100.42`), subdomains.
  - `get_ip_report`: Routing status (`"TEST-NET-1 (RFC-5737 Non-Routable)"` vs `"Routable Public IP"`), ASN (`"AS13335"`), reverse DNS, open ports.
  - `get_file_report`: Code signing info (`signer: "Acme Corp", certificate_status: "REVOKED_BY_CA", revocation_date: "2026-08-15"`), SHA-256, VT score (`56/70`).
  - `lookup_entity`: Process hierarchy (`ppid: 1044 (explorer.exe) -> pid: 4820 (PsExec.exe)`), user account, logon type (`Type 3 Network Logon`).

### 2.5 Explicit CMDB Asset Context (`configs/evals/gen3/soc_tier1_interactive.json`)
- Add CMDB metadata block to each case prompt:
  - Host identity, asset owner, operational role (e.g., `"CFO Workstation - Sarah Jenkins"` or `"Core Production Payment Gateway"`).
  - Explicit business blast-radius context (e.g., `"Containment blast radius: $50,000/hr downtime during active payroll"`).

### 2.6 Counterfactual Consistency Scoring (`scripts/eval_cost_engine.py`)
- Implement `calculate_counterfactual_consistency()`:
  - Evaluates paired test cases (`CASE-01` vs `CASE-06`, `CASE-05` vs `CASE-10`).
  - Measures whether the agent treats threats with containment and benign twins with non-disruptive closure.
  - Emits `counterfactual_consistency_score` ($0.0 - 1.0$) in summary metrics.

---

## 3. Backward Compatibility & Test Guardrails

- 100% backward compatibility for all existing test suites.
- Strict NO EMOJIS constraint across all code, datasets, comments, and documentation.
- All 230+ repository unit tests must pass.
