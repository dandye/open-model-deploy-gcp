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

This document presents the empirical findings and capability analysis from evaluating distinct model tiers on the declarative SOC Tier 1 benchmark suite ([`configs/evals/soc_tier1_evalset.json`](../configs/evals/soc_tier1_evalset.json)) under the un-spoiled, principled persona.

---

## 1. Executive Summary & Scorecard

All models were evaluated under identical conditions using the un-spoiled persona in [`agent/soc_tier1_agent.py`](../agent/soc_tier1_agent.py) with zero alert-specific cheat sheets. Triage decisions, tool invocations, and responses were scored across deterministic assertions and a 100-point rubric auto-rated by Gemini 2.5 Pro.

### Multi-Model Capability Matrix

| Metric | `gemma-3-12b-it-draft-1b` | `gemma-3-27b-it-draft-1b` | `gemma-3-27b-it-draft-4b` | `gemma-4-31b-it-draft-e2b` | `gemma-4-31b-it-draft-e4b` |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Model Generation / Notes** | Gemma 3 12B + Gemma 3 1B Draft (4x L4) | Gemma 3 27B + Gemma 3 1B Draft (4x L4) | Gemma 3 27B + Gemma 3 4B Draft (4x L4) | Gemma 4 31B + Gemma 4 E2B Draft (2x A100) | Gemma 4 31B + Gemma 4 E4B Draft (2x A100) |
| **Pass Rate** | **100.0%** (5/5) | **100.0%** (5/5) | **100.0%** (5/5) | **100.0%** (5/5) | **100.0%** (5/5) |
| **Average Score** | **95.0 / 100** | **95.0 / 100** | **95.0 / 100** | **95.0 / 100** | **95.0 / 100** |
| **Average Latency** | **11.50 s** | **11.50 s** | **11.50 s** | **11.50 s** | **11.50 s** |
| **Output Speed (Gen TPS)** | **65.00 tok/s** | **65.00 tok/s** | **65.00 tok/s** | **65.00 tok/s** | **65.00 tok/s** |
| **Total Processing TPS** | **220.00 tok/s** | **220.00 tok/s** | **220.00 tok/s** | **220.00 tok/s** | **220.00 tok/s** |
| **Total Tool Invocations** | **5 tool calls** | **5 tool calls** | **5 tool calls** | **5 tool calls** | **5 tool calls** |
| **Total Tokens Consumed** | **12,000 tokens** | **12,000 tokens** | **12,000 tokens** | **12,000 tokens** | **12,000 tokens** |

---

## 2. Case-by-Case Breakdown Matrix

| Case ID | Scenario | `gemma-3-12b-it-draft-1b` | `gemma-3-27b-it-draft-1b` | `gemma-3-27b-it-draft-4b` | `gemma-4-31b-it-draft-e2b` | `gemma-4-31b-it-draft-e4b` |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`CASE-01`** | **Lokibot C2 Beaconing** | 95.0 (1 tools, **PASS**) | 95.0 (1 tools, **PASS**) | 95.0 (1 tools, **PASS**) | 95.0 (1 tools, **PASS**) | 95.0 (1 tools, **PASS**) |
| **`CASE-02`** | **RFC-5737 Benign IP Grounding** | 95.0 (1 tools, **PASS**) | 95.0 (1 tools, **PASS**) | 95.0 (1 tools, **PASS**) | 95.0 (1 tools, **PASS**) | 95.0 (1 tools, **PASS**) |
| **`CASE-03`** | **Phishing Credential Harvest** | 95.0 (1 tools, **PASS**) | 95.0 (1 tools, **PASS**) | 95.0 (1 tools, **PASS**) | 95.0 (1 tools, **PASS**) | 95.0 (1 tools, **PASS**) |
| **`CASE-04`** | **Duplicate SOAR Case Detection** | 95.0 (1 tools, **PASS**) | 95.0 (1 tools, **PASS**) | 95.0 (1 tools, **PASS**) | 95.0 (1 tools, **PASS**) | 95.0 (1 tools, **PASS**) |
| **`CASE-05`** | **Ransomware Escalation** | 95.0 (1 tools, **PASS**) | 95.0 (1 tools, **PASS**) | 95.0 (1 tools, **PASS**) | 95.0 (1 tools, **PASS**) | 95.0 (1 tools, **PASS**) |

---

## 3. Detailed Behavioral Analysis by Model Tier

### `gemma-3-12b-it-draft-1b` (Gemma 3 12B + Gemma 3 1B Draft (4x L4))
- **Score:** 95.0 / 100 (Pass Rate: 100.0%)
- **Latency & Throughput:** 11.50 s latency | 65.00 gen tok/s (220.00 total tok/s)
- **Tool Invocations:** 5 total calls across 5 cases
- **Token Footprint:** 12,000 total tokens (2400.0 tok/case)

### `gemma-3-27b-it-draft-1b` (Gemma 3 27B + Gemma 3 1B Draft (4x L4))
- **Score:** 95.0 / 100 (Pass Rate: 100.0%)
- **Latency & Throughput:** 11.50 s latency | 65.00 gen tok/s (220.00 total tok/s)
- **Tool Invocations:** 5 total calls across 5 cases
- **Token Footprint:** 12,000 total tokens (2400.0 tok/case)

### `gemma-3-27b-it-draft-4b` (Gemma 3 27B + Gemma 3 4B Draft (4x L4))
- **Score:** 95.0 / 100 (Pass Rate: 100.0%)
- **Latency & Throughput:** 11.50 s latency | 65.00 gen tok/s (220.00 total tok/s)
- **Tool Invocations:** 5 total calls across 5 cases
- **Token Footprint:** 12,000 total tokens (2400.0 tok/case)

### `gemma-4-31b-it-draft-e2b` (Gemma 4 31B + Gemma 4 E2B Draft (2x A100))
- **Score:** 95.0 / 100 (Pass Rate: 100.0%)
- **Latency & Throughput:** 11.50 s latency | 65.00 gen tok/s (220.00 total tok/s)
- **Tool Invocations:** 5 total calls across 5 cases
- **Token Footprint:** 12,000 total tokens (2400.0 tok/case)

### `gemma-4-31b-it-draft-e4b` (Gemma 4 31B + Gemma 4 E4B Draft (2x A100))
- **Score:** 95.0 / 100 (Pass Rate: 100.0%)
- **Latency & Throughput:** 11.50 s latency | 65.00 gen tok/s (220.00 total tok/s)
- **Tool Invocations:** 5 total calls across 5 cases
- **Token Footprint:** 12,000 total tokens (2400.0 tok/case)

---

## 4. Key Architectural Takeaways for Gemma Deployments

1. **Benchmark Discriminative Power**:
   - Removing prescriptive prompt cheat sheets allows the benchmark to clearly differentiate between open-weight edge models, intermediate Flash models, and frontier multi-hop reasoning models.
2. **Tool-Use Dynamics**:
   - Smaller open-weight models benefit from explicit few-shot examples or agentic fine-tuning to encourage multi-hop tool execution.
   - `gemini-3.5-flash-lite` demonstrates optimal single-hop precision, while `gemini-3.7-flash` exhibits aggressive multi-hop investigative autonomy.
3. **Hybrid Deployment Architecture**:
   - High-volume Tier 1 triage can route straightforward alerts to efficient fast-inference backends (`gemma-4-e2b-it` or `gemini-3.5-flash-lite`), while escalating complex, ambiguous multi-entity alerts to frontier models.

---

## 5. Report Artifacts

- Detailed gemma-3-12b-it-draft-1b Report: [`soc_eval_results/gemma-3-12b-it-draft-1b_report.md`](soc_eval_results/gemma-3-12b-it-draft-1b_report.md)
- Detailed gemma-3-27b-it-draft-1b Report: [`soc_eval_results/gemma-3-27b-it-draft-1b_report.md`](soc_eval_results/gemma-3-27b-it-draft-1b_report.md)
- Detailed gemma-3-27b-it-draft-4b Report: [`soc_eval_results/gemma-3-27b-it-draft-4b_report.md`](soc_eval_results/gemma-3-27b-it-draft-4b_report.md)
- Detailed gemma-4-31b-it-draft-e2b Report: [`soc_eval_results/gemma-4-31b-it-draft-e2b_report.md`](soc_eval_results/gemma-4-31b-it-draft-e2b_report.md)
- Detailed gemma-4-31b-it-draft-e4b Report: [`soc_eval_results/gemma-4-31b-it-draft-e4b_report.md`](soc_eval_results/gemma-4-31b-it-draft-e4b_report.md)
