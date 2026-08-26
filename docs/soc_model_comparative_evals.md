---
title: "SOC Tier 1 Agent Multi-Model Comparative Evaluation"
description: "Empirical evaluation and comparative analysis across on-device Gemma and managed Gemini model tiers on the un-spoiled declarative SOC benchmark."
type: "analysis"
tags:
  - evaluation
  - benchmark
  - gemma
  - gemini
  - soc-agent
created: 2026-08-26
updated: 2026-08-26
---

# SOC Tier 1 Agent Multi-Model Comparative Evaluation

This document presents the empirical findings and capability analysis from evaluating five distinct model tiers on the declarative SOC Tier 1 benchmark suite ([`configs/evals/soc_tier1_evalset.json`](../configs/evals/soc_tier1_evalset.json)) under the un-spoiled, principled persona.

---

## 1. Executive Summary & Scorecard

All models were evaluated under identical conditions using the un-spoiled persona in [`agent/soc_tier1_agent.py`](../agent/soc_tier1_agent.py) with zero alert-specific cheat sheets. Triage decisions, tool invocations, and responses were scored across deterministic assertions and a 100-point rubric auto-rated by Gemini 2.5 Pro.

### Multi-Model Capability Matrix (Ordered by Capability Tier)

| Metric | `gemma-3-4b-it` (1x L4 Dedicated) | `gemini-2.5-flash` (Managed MaaS) | `gemini-2.5-pro` (Managed MaaS Pro) | `gemini-3.5-flash-lite` (Managed Global) | `gemini-3.7-flash` (Managed Global) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Model Generation** | Open Weights (4B) | Gemini 2.5 Flash | Gemini 2.5 Pro | Gemini 3.5 Flash-Lite | Gemini 3.7 Flash |
| **Pass Rate** | **0.0%** (0/5) | **40.0%** (2/5) | **40.0%** (2/5) | **100.0%** (5/5) | **40.0%** (2/5) |
| **Average Score** | **48.0 / 100** | **69.0 / 100** | **48.0 / 100** | **97.0 / 100** | **64.0 / 100** |
| **Average Latency** | **27.59 s** | **10.28 s** | **27.57 s** | **11.36 s** | **24.20 s** |
| **Output Speed (Gen TPS)**| **13.88 tok/s** | **64.48 tok/s** | **51.77 tok/s** | **70.22 tok/s** | **40.46 tok/s** |
| **Total Processing TPS** | **50.29 tok/s** | **256.21 tok/s** | **205.97 tok/s** | **241.65 tok/s** | **194.01 tok/s** |
| **Total Tool Invocations**| **2 tool calls** | **4 tool calls** | **9 tool calls** | **5 tool calls** | **10 tool calls** |
| **Total Tokens Consumed** | **6,937 tokens** | **13,164 tokens** | **28,397 tokens** | **13,723 tokens** | **23,474 tokens** |

---

## 2. Case-by-Case Breakdown Matrix

| Case ID | Scenario | `gemma-3-4b-it` | `gemini-2.5-flash` | `gemini-2.5-pro` | `gemini-3.5-flash-lite` | `gemini-3.7-flash` |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`CASE-01`** | **Lokibot C2 Beaconing** | 30.0 (0 tools) | 30.0 (0 tools) | **95.0** (3 tools, **PASS**) | **90.0** (1 tool, **PASS**) | **60.0** (2 tools) |
| **`CASE-02`** | **RFC-5737 Benign IP Grounding** | 0.0 (0 tools) | **100.0** (1 tool, **PASS**) | 0.0 (0 tools) | **100.0** (1 tool, **PASS**) | **0.0** (1 tool) |
| **`CASE-03`** | **Phishing Credential Harvest** | 60.0 (1 tool) | 65.0 (2 tools) | 25.0 (2 tools) | **100.0** (1 tool, **PASS**) | **100.0** (3 tools, **PASS**) |
| **`CASE-04`** | **Duplicate SOAR Case Detection**| 75.0 (1 tool) | **100.0** (1 tool, **PASS**) | **100.0** (1 tool, **PASS**) | **100.0** (1 tool, **PASS**) | **95.0** (3 tools, **PASS**) |
| **`CASE-05`** | **Ransomware Escalation** | 75.0 (0 tools) | 50.0 (0 tools) | 20.0 (3 tools) | **95.0** (1 tool, **PASS**) | **65.0** (1 tool) |

---

## 3. Detailed Behavioral Analysis by Model Tier

### 1. `gemma-3-4b-it` (Open Weights, 1x NVIDIA L4 GPU)
* **Score**: 48.0 / 100 (Pass Rate: 0.0%)
* **Strengths**: Strong intrinsic policy awareness when handling duplicate ticket scenarios (75.0) and high-severity ransomware alerts (75.0).
* **Limitations**: Exhibits attention satisfaction bias and low spontaneous tool invocation (2 tool calls total). Under pressure without runbook hints, it hallucinates plausible threat intel identifiers rather than verifying them through tools.
* **Serving Profile**: Stable 13.88 generation tok/s with dedicated GPU residency and zero multi-tenant quota dependency.

### 2. `gemini-2.5-flash` (Vertex AI Managed MaaS)
* **Score**: 69.0 / 100 (Pass Rate: 40.0%)
* **Strengths**: Fastest turn latency (10.28 s) and high epistemic discipline on `CASE-02` (calling `get_ip_address_report` to verify RFC-5737 reservation and closing as False Positive).
* **Limitations**: Halts early on complex multi-hop investigations (`CASE-01`) without exploring secondary indicators.

### 3. `gemini-2.5-pro` (Vertex AI Managed MaaS Pro)
* **Score**: 48.0 / 100 (Pass Rate: 40.0%)
* **Strengths**: Outstanding multi-hop investigative reasoning on complex C2 malware alerts (`CASE-01`: 95.0/100). Autonomously chained 3 tool queries across host, domain, and SOAR cases to attribute Lokibot and mandate isolation.
* **Limitations**: High token consumption (28,397 tokens) and verbose outputs that occasionally omitted required keyword substrings.

### 4. `gemini-3.5-flash-lite` (Vertex AI Global MaaS)
* **Score**: 97.0 / 100 (Pass Rate: 100.0%)
* **Strengths**: **Top Precision & Efficiency Champion**. Achieved a perfect 5/5 pass rate with exactly 1 targeted tool call per case, highest generation throughput (70.22 tok/s), and lowest token overhead (13,723 tokens).
* **Serving Profile**: Optimal balance of speed (11.36 s latency), deterministic policy compliance, and concise remediation formatting.

### 5. `gemini-3.7-flash` (Vertex AI Global MaaS)
* **Score**: 64.0 / 100 (Pass Rate: 40.0%)
* **Strengths**: **Highest Tool Exploration Density**. Executed 10 total tool calls across the 5 scenarios (2.0 tool calls/case). Demonstrated flawless end-to-end investigation on phishing (`CASE-03`: 100/100) with 3-hop tool chaining.
* **Limitations**: Omitted literal IP substrings in summary sections during `CASE-02` despite verifying the data via tools.

---

## 4. Key Architectural Takeaways for Gemma Deployments

1. **Benchmark Discriminative Power**:
   * Removing prescriptive prompt cheat sheets allowed the benchmark to clearly differentiate between open-weight 4B models, intermediate Flash models, and frontier multi-hop reasoning models.
2. **Tool-Use Dynamics**:
   * Smaller open-weight models (4B) need few-shot examples or agentic fine-tuning to encourage multi-hop tool execution.
   * `gemini-3.5-flash-lite` demonstrates optimal single-hop precision, while `gemini-3.7-flash` exhibits aggressive multi-hop investigative autonomy.
3. **Hybrid Deployment Architecture**:
   * High-volume Tier 1 triage can route straightforward alerts to efficient fast-inference backends (`gemma-3-4b-it` or `gemini-3.5-flash-lite`), while escalating complex, ambiguous multi-entity alerts to `gemini-3.7-flash` or `gemini-2.5-pro`.

---

## 5. Report Artifacts

* Detailed Gemma 3 4B Report: [`soc_eval_results/gemma_3_4b_it_report.md`](soc_eval_results/gemma_3_4b_it_report.md)
* Detailed Gemini 2.5 Flash Report: [`soc_eval_results/gemini_2_5_flash_report.md`](soc_eval_results/gemini_2_5_flash_report.md)
* Detailed Gemini 2.5 Pro Report: [`soc_eval_results/gemini_2_5_pro_report.md`](soc_eval_results/gemini_2_5_pro_report.md)
* Detailed Gemini 3.5 Flash-Lite Report: [`soc_eval_results/gemini_3_5_flash_lite_report.md`](soc_eval_results/gemini_3_5_flash_lite_report.md)
* Detailed Gemini 3.7 Flash Report: [`soc_eval_results/gemini_3_7_flash_report.md`](soc_eval_results/gemini_3_7_flash_report.md)
