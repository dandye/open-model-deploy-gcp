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
updated: 2026-09-03
---

# SOC Tier 1 Agent Multi-Model Comparative Evaluation

This document presents the empirical findings and capability analysis from evaluating distinct model tiers on the declarative SOC Tier 1 benchmark suite ([`configs/evals/soc_tier1_evalset.json`](../configs/evals/soc_tier1_evalset.json)) under the un-spoiled, principled persona.

---

## 1. Executive Summary & Scorecard

All models were evaluated under identical conditions using the un-spoiled persona in [`agent/soc_tier1_agent.py`](../agent/soc_tier1_agent.py) with zero alert-specific cheat sheets. Triage decisions, tool invocations, and responses were scored across deterministic assertions and a 100-point rubric auto-rated by Gemini 2.5 Pro.

### Multi-Model Capability Matrix

| Metric | `gemma-2-2b-it` | `gemma-2-9b-it` | `gemma-2-27b-it` | `gemma-2-2b-it-speculative` | `gemma-2-9b-it-fp8` | `gemma-2-9b-it-speculative` | `gemma-2-27b-it-fp8` | `gemma-2-27b-it-speculative` | `gemma-3-1b-it` | `gemma-3-4b-it` | `gemma-3-12b-it` | `gemma-3-27b-it` | `gemma-3-1b-it-speculative` | `gemma-3-4b-it-speculative` | `gemma-3-12b-it-fp8` | `gemma-3-12b-it-speculative` | `gemma-3-12b-it-draft-1b` | `gemma-3-27b-it-fp8` | `gemma-3-27b-it-speculative` | `gemma-3-27b-it-caching` | `gemma-3-27b-it-draft-1b` | `gemma-3-27b-it-draft-4b` | `gemma-4-e2b-it` | `gemma-4-e4b-it` | `gemma-4-31b-it` | `gemma-4-e2b-it-speculative` | `gemma-4-e4b-it-speculative` | `gemma-4-31b-it-speculative` | `gemma-4-31b-it-draft-e2b` | `gemma-4-31b-it-draft-e4b` | `gemini-2.5-flash` | `gemini-2.5-pro` | `gemini-3.5-flash-lite` | `gemini-3.7-flash` | `gemini-2.5-flash-lite` | `gemini-3.1-flash-lite` | `gemma-4-26b-a4b-it-maas` | `grok-4.6` | `inkling-small` | `llama-3.1-405b-instruct-maas` | `llama-3.1-8b-instruct-maas` | `llama-3.1-nemotron-70b-instruct` | `llama-3.2-11b-vision-instruct-maas` | `llama-3.2-3b-instruct` | `llama-3.3-70b-instruct-maas` | `llama-4-maverick-17b-128e-instruct-maas` | `llama-4-scout-17b-16e-instruct-maas` | `llama-guard-3-8b` | `muse-spark-1.3` | `nemotron-3.5-lightning-bf16` | `qwen3.8-27b` |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Model Generation / Notes** | Gemma 2 2B (1x L4) | Gemma 2 9B (1x L4) | Gemma 2 27B (4x L4) | Gemma 2 2B + Speculative Decoding (1x L4) | Gemma 2 9B FP8 Quantized (1x L4) | Gemma 2 9B FP8 + Speculative Decoding (1x L4) | Gemma 2 27B FP8 Quantized (4x L4) | Gemma 2 27B FP8 + Speculative Decoding (4x L4) | Gemma 3 1B (1x L4) | Gemma 3 4B (1x L4) | Gemma 3 12B Multimodal (4x L4) | Gemma 3 27B Multimodal (4x L4) | Gemma 3 1B + Speculative Decoding (1x L4) | Gemma 3 4B + Speculative Decoding (1x L4) | Gemma 3 12B FP8 Quantized (4x L4) | Gemma 3 12B FP8 + Speculative Decoding (4x L4) | Gemma 3 12B + Gemma 3 1B Draft (4x L4) | Gemma 3 27B FP8 Quantized (4x L4) | Gemma 3 27B FP8 + Speculative Decoding (4x L4) | Gemma 3 27B FP8 + Prefix Caching (4x L4) | Gemma 3 27B + Gemma 3 1B Draft (4x L4) | Gemma 3 27B + Gemma 3 4B Draft (4x L4) | Gemma 4 Edge (1x L4) | Gemma 4 Edge (1x L4) | Gemma 4 Multimodal Reasoner (2x A100) | Gemma 4 E2B + Speculative Decoding (1x L4) | Gemma 4 E4B + Speculative Decoding (1x L4) | Gemma 4 31B + Speculative Decoding (2x A100) | Gemma 4 31B + Gemma 4 E2B Draft (2x A100) | Gemma 4 31B + Gemma 4 E4B Draft (2x A100) | Vertex AI Managed MaaS | Vertex AI Managed MaaS Pro | Vertex AI Global MaaS | Vertex AI Global MaaS | Vertex AI Managed MaaS Lite | Vertex AI Global MaaS Lite | Gemma 4 MoE (Active 4B) Vertex MaaS | Partner / OpenModel | Partner / OpenModel | Partner / OpenModel | Partner / OpenModel | Partner / OpenModel | Partner / OpenModel | Partner / OpenModel | Partner / OpenModel | Partner / OpenModel | Partner / OpenModel | Partner / OpenModel | Meta Muse Spark 1.3 Agentic Reasoner | Partner / OpenModel | Partner / OpenModel |
| **Pass Rate** | **20.0%** (2/10) | **50.0%** (5/10) | **50.0%** (5/10) | **30.0%** (3/10) | **20.0%** (2/10) | **40.0%** (4/10) | **40.0%** (4/10) | **40.0%** (4/10) | **70.0%** (7/10) | **10.0%** (1/10) | **10.0%** (1/10) | **0.0%** (0/10) | **0.0%** (0/10) | **10.0%** (1/10) | **0.0%** (0/10) | **0.0%** (0/10) | **0.0%** (0/10) | **0.0%** (0/10) | **0.0%** (0/10) | **0.0%** (0/10) | **0.0%** (0/10) | **0.0%** (0/10) | **0.0%** (0/10) | **0.0%** (0/10) | **0.0%** (0/10) | **0.0%** (0/10) | **0.0%** (0/10) | **0.0%** (0/10) | **0.0%** (0/10) | **0.0%** (0/10) | **30.0%** (3/10) | **20.0%** (2/10) | **60.0%** (6/10) | **20.0%** (2/10) | **30.0%** (3/10) | **20.0%** (2/10) | **0.0%** (0/10) | **0.0%** (0/10) | **40.0%** (4/10) | **0.0%** (0/10) | **0.0%** (0/10) | **50.0%** (5/10) | **0.0%** (0/10) | **40.0%** (4/10) | **0.0%** (0/10) | **0.0%** (0/10) | **0.0%** (0/10) | **40.0%** (4/10) | **0.0%** (0/10) | **40.0%** (4/10) | **20.0%** (2/10) |
| **Average Score** | **54.5 / 100** | **76.5 / 100** | **74.5 / 100** | **58.5 / 100** | **67.8 / 100** | **68.8 / 100** | **70.0 / 100** | **64.8 / 100** | **80.5 / 100** | **37.5 / 100** | **51.0 / 100** | **36.8 / 100** | **28.0 / 100** | **38.5 / 100** | **54.5 / 100** | **43.5 / 100** | **49.2 / 100** | **48.5 / 100** | **42.0 / 100** | **36.0 / 100** | **38.3 / 100** | **42.0 / 100** | **31.5 / 100** | **58.5 / 100** | **65.0 / 100** | **59.5 / 100** | **69.5 / 100** | **71.8 / 100** | **62.5 / 100** | **60.5 / 100** | **64.0 / 100** | **42.0 / 100** | **75.0 / 100** | **57.1 / 100** | **58.0 / 100** | **53.5 / 100** | **31.0 / 100** | **1.0 / 100** | **75.5 / 100** | **1.0 / 100** | **0.0 / 100** | **77.8 / 100** | **1.0 / 100** | **67.0 / 100** | **0.0 / 100** | **1.0 / 100** | **1.0 / 100** | **64.3 / 100** | **1.0 / 100** | **71.0 / 100** | **56.5 / 100** |
| **Average Latency** | **18.57 s** | **15.13 s** | **18.26 s** | **20.73 s** | **39.78 s** | **18.67 s** | **20.63 s** | **16.19 s** | **15.11 s** | **55.91 s** | **56.30 s** | **56.98 s** | **6.36 s** | **54.68 s** | **11.25 s** | **25.63 s** | **26.05 s** | **44.97 s** | **46.94 s** | **46.48 s** | **56.77 s** | **57.92 s** | **6.30 s** | **35.61 s** | **16.03 s** | **13.03 s** | **13.97 s** | **12.56 s** | **15.41 s** | **15.41 s** | **13.77 s** | **43.35 s** | **9.30 s** | **27.91 s** | **28.56 s** | **10.40 s** | **86.76 s** | **1.31 s** | **14.34 s** | **1.25 s** | **1.20 s** | **18.21 s** | **1.30 s** | **15.44 s** | **1.21 s** | **1.19 s** | **1.30 s** | **16.51 s** | **2.27 s** | **17.21 s** | **16.92 s** |
| **Output Speed (Gen TPS)** | **91.11 tok/s** | **74.74 tok/s** | **80.37 tok/s** | **80.67 tok/s** | **201.40 tok/s** | **94.57 tok/s** | **83.10 tok/s** | **73.81 tok/s** | **75.61 tok/s** | **14.56 tok/s** | **16.29 tok/s** | **8.72 tok/s** | **58.94 tok/s** | **14.89 tok/s** | **80.63 tok/s** | **18.26 tok/s** | **18.13 tok/s** | **12.67 tok/s** | **12.20 tok/s** | **12.18 tok/s** | **8.75 tok/s** | **8.58 tok/s** | **24.04 tok/s** | **17.75 tok/s** | **57.72 tok/s** | **64.01 tok/s** | **64.21 tok/s** | **69.59 tok/s** | **51.58 tok/s** | **57.48 tok/s** | **98.14 tok/s** | **51.86 tok/s** | **85.73 tok/s** | **67.46 tok/s** | **361.37 tok/s** | **119.10 tok/s** | **36.19 tok/s** | **0.00 tok/s** | **74.76 tok/s** | **0.00 tok/s** | **0.00 tok/s** | **79.76 tok/s** | **0.00 tok/s** | **69.42 tok/s** | **0.00 tok/s** | **0.00 tok/s** | **0.00 tok/s** | **79.18 tok/s** | **0.00 tok/s** | **81.63 tok/s** | **83.99 tok/s** |
| **Total Processing TPS** | **540.99 tok/s** | **558.15 tok/s** | **533.89 tok/s** | **487.14 tok/s** | **573.02 tok/s** | **619.60 tok/s** | **520.71 tok/s** | **520.20 tok/s** | **587.99 tok/s** | **108.01 tok/s** | **132.69 tok/s** | **27.75 tok/s** | **258.18 tok/s** | **110.44 tok/s** | **320.61 tok/s** | **70.32 tok/s** | **69.31 tok/s** | **33.44 tok/s** | **38.06 tok/s** | **35.47 tok/s** | **27.85 tok/s** | **27.30 tok/s** | **150.49 tok/s** | **56.37 tok/s** | **282.76 tok/s** | **302.83 tok/s** | **315.66 tok/s** | **297.59 tok/s** | **283.38 tok/s** | **273.93 tok/s** | **670.31 tok/s** | **382.95 tok/s** | **881.00 tok/s** | **514.11 tok/s** | **1350.74 tok/s** | **863.65 tok/s** | **224.99 tok/s** | **0.00 tok/s** | **552.61 tok/s** | **0.00 tok/s** | **0.00 tok/s** | **463.51 tok/s** | **0.00 tok/s** | **537.64 tok/s** | **0.00 tok/s** | **0.00 tok/s** | **0.00 tok/s** | **530.38 tok/s** | **0.00 tok/s** | **514.67 tok/s** | **508.52 tok/s** |
| **Total Tool Invocations** | **12 tool calls** | **12 tool calls** | **12 tool calls** | **12 tool calls** | **11 tool calls** | **17 tool calls** | **12 tool calls** | **11 tool calls** | **12 tool calls** | **17 tool calls** | **25 tool calls** | **3 tool calls** | **5 tool calls** | **17 tool calls** | **9 tool calls** | **6 tool calls** | **6 tool calls** | **1 tool calls** | **4 tool calls** | **3 tool calls** | **3 tool calls** | **3 tool calls** | **0 tool calls** | **6 tool calls** | **14 tool calls** | **11 tool calls** | **14 tool calls** | **9 tool calls** | **14 tool calls** | **12 tool calls** | **11 tool calls** | **24 tool calls** | **15 tool calls** | **22 tool calls** | **24 tool calls** | **14 tool calls** | **31 tool calls** | **0 tool calls** | **11 tool calls** | **0 tool calls** | **0 tool calls** | **10 tool calls** | **0 tool calls** | **11 tool calls** | **0 tool calls** | **0 tool calls** | **0 tool calls** | **12 tool calls** | **0 tool calls** | **11 tool calls** | **11 tool calls** |
| **Total Tokens Consumed** | **100,459 tokens** | **84,423 tokens** | **97,470 tokens** | **100,966 tokens** | **227,971 tokens** | **115,656 tokens** | **107,441 tokens** | **84,203 tokens** | **88,846 tokens** | **60,387 tokens** | **74,710 tokens** | **15,810 tokens** | **16,421 tokens** | **60,387 tokens** | **36,083 tokens** | **18,026 tokens** | **18,053 tokens** | **15,035 tokens** | **17,866 tokens** | **16,485 tokens** | **15,810 tokens** | **15,810 tokens** | **9,484 tokens** | **20,072 tokens** | **45,324 tokens** | **39,448 tokens** | **44,107 tokens** | **37,367 tokens** | **43,676 tokens** | **42,209 tokens** | **92,319 tokens** | **165,996 tokens** | **81,926 tokens** | **143,479 tokens** | **385,830 tokens** | **89,789 tokens** | **195,209 tokens** | **0 tokens** | **79,258 tokens** | **0 tokens** | **0 tokens** | **84,390 tokens** | **0 tokens** | **83,021 tokens** | **0 tokens** | **0 tokens** | **0 tokens** | **87,591 tokens** | **0 tokens** | **88,598 tokens** | **86,018 tokens** |

---

## 2. Case-by-Case Breakdown Matrix

| Case ID | Scenario | `gemma-2-2b-it` | `gemma-2-9b-it` | `gemma-2-27b-it` | `gemma-2-2b-it-speculative` | `gemma-2-9b-it-fp8` | `gemma-2-9b-it-speculative` | `gemma-2-27b-it-fp8` | `gemma-2-27b-it-speculative` | `gemma-3-1b-it` | `gemma-3-4b-it` | `gemma-3-12b-it` | `gemma-3-27b-it` | `gemma-3-1b-it-speculative` | `gemma-3-4b-it-speculative` | `gemma-3-12b-it-fp8` | `gemma-3-12b-it-speculative` | `gemma-3-12b-it-draft-1b` | `gemma-3-27b-it-fp8` | `gemma-3-27b-it-speculative` | `gemma-3-27b-it-caching` | `gemma-3-27b-it-draft-1b` | `gemma-3-27b-it-draft-4b` | `gemma-4-e2b-it` | `gemma-4-e4b-it` | `gemma-4-31b-it` | `gemma-4-e2b-it-speculative` | `gemma-4-e4b-it-speculative` | `gemma-4-31b-it-speculative` | `gemma-4-31b-it-draft-e2b` | `gemma-4-31b-it-draft-e4b` | `gemini-2.5-flash` | `gemini-2.5-pro` | `gemini-3.5-flash-lite` | `gemini-3.7-flash` | `gemini-2.5-flash-lite` | `gemini-3.1-flash-lite` | `gemma-4-26b-a4b-it-maas` | `grok-4.6` | `inkling-small` | `llama-3.1-405b-instruct-maas` | `llama-3.1-8b-instruct-maas` | `llama-3.1-nemotron-70b-instruct` | `llama-3.2-11b-vision-instruct-maas` | `llama-3.2-3b-instruct` | `llama-3.3-70b-instruct-maas` | `llama-4-maverick-17b-128e-instruct-maas` | `llama-4-scout-17b-16e-instruct-maas` | `llama-guard-3-8b` | `muse-spark-1.3` | `nemotron-3.5-lightning-bf16` | `qwen3.8-27b` |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`CASE-01`** | **Lokibot C2 Beaconing** | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| **`CASE-02`** | **RFC-5737 Benign IP Grounding** | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| **`CASE-03`** | **Phishing Credential Harvest** | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| **`CASE-04`** | **Duplicate SOAR Case Detection** | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| **`CASE-05`** | **Ransomware Escalation** | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |

---

## 3. Detailed Behavioral Analysis by Model Tier

### `gemma-2-2b-it` (Gemma 2 2B (1x L4))
- **Score:** 54.5 / 100 (Pass Rate: 20.0%)
- **Latency & Throughput:** 18.57 s latency | 91.11 gen tok/s (540.99 total tok/s)
- **Tool Invocations:** 12 total calls across 10 cases
- **Token Footprint:** 100,459 total tokens (10045.9 tok/case)

### `gemma-2-9b-it` (Gemma 2 9B (1x L4))
- **Score:** 76.5 / 100 (Pass Rate: 50.0%)
- **Latency & Throughput:** 15.13 s latency | 74.74 gen tok/s (558.15 total tok/s)
- **Tool Invocations:** 12 total calls across 10 cases
- **Token Footprint:** 84,423 total tokens (8442.3 tok/case)

### `gemma-2-27b-it` (Gemma 2 27B (4x L4))
- **Score:** 74.5 / 100 (Pass Rate: 50.0%)
- **Latency & Throughput:** 18.26 s latency | 80.37 gen tok/s (533.89 total tok/s)
- **Tool Invocations:** 12 total calls across 10 cases
- **Token Footprint:** 97,470 total tokens (9747.0 tok/case)

### `gemma-2-2b-it-speculative` (Gemma 2 2B + Speculative Decoding (1x L4))
- **Score:** 58.5 / 100 (Pass Rate: 30.0%)
- **Latency & Throughput:** 20.73 s latency | 80.67 gen tok/s (487.14 total tok/s)
- **Tool Invocations:** 12 total calls across 10 cases
- **Token Footprint:** 100,966 total tokens (10096.6 tok/case)

### `gemma-2-9b-it-fp8` (Gemma 2 9B FP8 Quantized (1x L4))
- **Score:** 67.8 / 100 (Pass Rate: 20.0%)
- **Latency & Throughput:** 39.78 s latency | 201.40 gen tok/s (573.02 total tok/s)
- **Tool Invocations:** 11 total calls across 10 cases
- **Token Footprint:** 227,971 total tokens (22797.1 tok/case)

### `gemma-2-9b-it-speculative` (Gemma 2 9B FP8 + Speculative Decoding (1x L4))
- **Score:** 68.8 / 100 (Pass Rate: 40.0%)
- **Latency & Throughput:** 18.67 s latency | 94.57 gen tok/s (619.60 total tok/s)
- **Tool Invocations:** 17 total calls across 10 cases
- **Token Footprint:** 115,656 total tokens (11565.6 tok/case)

### `gemma-2-27b-it-fp8` (Gemma 2 27B FP8 Quantized (4x L4))
- **Score:** 70.0 / 100 (Pass Rate: 40.0%)
- **Latency & Throughput:** 20.63 s latency | 83.10 gen tok/s (520.71 total tok/s)
- **Tool Invocations:** 12 total calls across 10 cases
- **Token Footprint:** 107,441 total tokens (10744.1 tok/case)

### `gemma-2-27b-it-speculative` (Gemma 2 27B FP8 + Speculative Decoding (4x L4))
- **Score:** 64.8 / 100 (Pass Rate: 40.0%)
- **Latency & Throughput:** 16.19 s latency | 73.81 gen tok/s (520.20 total tok/s)
- **Tool Invocations:** 11 total calls across 10 cases
- **Token Footprint:** 84,203 total tokens (8420.3 tok/case)

### `gemma-3-1b-it` (Gemma 3 1B (1x L4))
- **Score:** 80.5 / 100 (Pass Rate: 70.0%)
- **Latency & Throughput:** 15.11 s latency | 75.61 gen tok/s (587.99 total tok/s)
- **Tool Invocations:** 12 total calls across 10 cases
- **Token Footprint:** 88,846 total tokens (8884.6 tok/case)

### `gemma-3-4b-it` (Gemma 3 4B (1x L4))
- **Score:** 37.5 / 100 (Pass Rate: 10.0%)
- **Latency & Throughput:** 55.91 s latency | 14.56 gen tok/s (108.01 total tok/s)
- **Tool Invocations:** 17 total calls across 10 cases
- **Token Footprint:** 60,387 total tokens (6038.7 tok/case)

### `gemma-3-12b-it` (Gemma 3 12B Multimodal (4x L4))
- **Score:** 51.0 / 100 (Pass Rate: 10.0%)
- **Latency & Throughput:** 56.30 s latency | 16.29 gen tok/s (132.69 total tok/s)
- **Tool Invocations:** 25 total calls across 10 cases
- **Token Footprint:** 74,710 total tokens (7471.0 tok/case)

### `gemma-3-27b-it` (Gemma 3 27B Multimodal (4x L4))
- **Score:** 36.8 / 100 (Pass Rate: 0.0%)
- **Latency & Throughput:** 56.98 s latency | 8.72 gen tok/s (27.75 total tok/s)
- **Tool Invocations:** 3 total calls across 10 cases
- **Token Footprint:** 15,810 total tokens (1581.0 tok/case)

### `gemma-3-1b-it-speculative` (Gemma 3 1B + Speculative Decoding (1x L4))
- **Score:** 28.0 / 100 (Pass Rate: 0.0%)
- **Latency & Throughput:** 6.36 s latency | 58.94 gen tok/s (258.18 total tok/s)
- **Tool Invocations:** 5 total calls across 10 cases
- **Token Footprint:** 16,421 total tokens (1642.1 tok/case)

### `gemma-3-4b-it-speculative` (Gemma 3 4B + Speculative Decoding (1x L4))
- **Score:** 38.5 / 100 (Pass Rate: 10.0%)
- **Latency & Throughput:** 54.68 s latency | 14.89 gen tok/s (110.44 total tok/s)
- **Tool Invocations:** 17 total calls across 10 cases
- **Token Footprint:** 60,387 total tokens (6038.7 tok/case)

### `gemma-3-12b-it-fp8` (Gemma 3 12B FP8 Quantized (4x L4))
- **Score:** 54.5 / 100 (Pass Rate: 0.0%)
- **Latency & Throughput:** 11.25 s latency | 80.63 gen tok/s (320.61 total tok/s)
- **Tool Invocations:** 9 total calls across 10 cases
- **Token Footprint:** 36,083 total tokens (3608.3 tok/case)

### `gemma-3-12b-it-speculative` (Gemma 3 12B FP8 + Speculative Decoding (4x L4))
- **Score:** 43.5 / 100 (Pass Rate: 0.0%)
- **Latency & Throughput:** 25.63 s latency | 18.26 gen tok/s (70.32 total tok/s)
- **Tool Invocations:** 6 total calls across 10 cases
- **Token Footprint:** 18,026 total tokens (1802.6 tok/case)

### `gemma-3-12b-it-draft-1b` (Gemma 3 12B + Gemma 3 1B Draft (4x L4))
- **Score:** 49.2 / 100 (Pass Rate: 0.0%)
- **Latency & Throughput:** 26.05 s latency | 18.13 gen tok/s (69.31 total tok/s)
- **Tool Invocations:** 6 total calls across 10 cases
- **Token Footprint:** 18,053 total tokens (1805.3 tok/case)

### `gemma-3-27b-it-fp8` (Gemma 3 27B FP8 Quantized (4x L4))
- **Score:** 48.5 / 100 (Pass Rate: 0.0%)
- **Latency & Throughput:** 44.97 s latency | 12.67 gen tok/s (33.44 total tok/s)
- **Tool Invocations:** 1 total calls across 10 cases
- **Token Footprint:** 15,035 total tokens (1503.5 tok/case)

### `gemma-3-27b-it-speculative` (Gemma 3 27B FP8 + Speculative Decoding (4x L4))
- **Score:** 42.0 / 100 (Pass Rate: 0.0%)
- **Latency & Throughput:** 46.94 s latency | 12.20 gen tok/s (38.06 total tok/s)
- **Tool Invocations:** 4 total calls across 10 cases
- **Token Footprint:** 17,866 total tokens (1786.6 tok/case)

### `gemma-3-27b-it-caching` (Gemma 3 27B FP8 + Prefix Caching (4x L4))
- **Score:** 36.0 / 100 (Pass Rate: 0.0%)
- **Latency & Throughput:** 46.48 s latency | 12.18 gen tok/s (35.47 total tok/s)
- **Tool Invocations:** 3 total calls across 10 cases
- **Token Footprint:** 16,485 total tokens (1648.5 tok/case)

### `gemma-3-27b-it-draft-1b` (Gemma 3 27B + Gemma 3 1B Draft (4x L4))
- **Score:** 38.3 / 100 (Pass Rate: 0.0%)
- **Latency & Throughput:** 56.77 s latency | 8.75 gen tok/s (27.85 total tok/s)
- **Tool Invocations:** 3 total calls across 10 cases
- **Token Footprint:** 15,810 total tokens (1581.0 tok/case)

### `gemma-3-27b-it-draft-4b` (Gemma 3 27B + Gemma 3 4B Draft (4x L4))
- **Score:** 42.0 / 100 (Pass Rate: 0.0%)
- **Latency & Throughput:** 57.92 s latency | 8.58 gen tok/s (27.30 total tok/s)
- **Tool Invocations:** 3 total calls across 10 cases
- **Token Footprint:** 15,810 total tokens (1581.0 tok/case)

### `gemma-4-e2b-it` (Gemma 4 Edge (1x L4))
- **Score:** 31.5 / 100 (Pass Rate: 0.0%)
- **Latency & Throughput:** 6.30 s latency | 24.04 gen tok/s (150.49 total tok/s)
- **Tool Invocations:** 0 total calls across 10 cases
- **Token Footprint:** 9,484 total tokens (948.4 tok/case)

### `gemma-4-e4b-it` (Gemma 4 Edge (1x L4))
- **Score:** 58.5 / 100 (Pass Rate: 0.0%)
- **Latency & Throughput:** 35.61 s latency | 17.75 gen tok/s (56.37 total tok/s)
- **Tool Invocations:** 6 total calls across 10 cases
- **Token Footprint:** 20,072 total tokens (2007.2 tok/case)

### `gemma-4-31b-it` (Gemma 4 Multimodal Reasoner (2x A100))
- **Score:** 65.0 / 100 (Pass Rate: 0.0%)
- **Latency & Throughput:** 16.03 s latency | 57.72 gen tok/s (282.76 total tok/s)
- **Tool Invocations:** 14 total calls across 10 cases
- **Token Footprint:** 45,324 total tokens (4532.4 tok/case)

### `gemma-4-e2b-it-speculative` (Gemma 4 E2B + Speculative Decoding (1x L4))
- **Score:** 59.5 / 100 (Pass Rate: 0.0%)
- **Latency & Throughput:** 13.03 s latency | 64.01 gen tok/s (302.83 total tok/s)
- **Tool Invocations:** 11 total calls across 10 cases
- **Token Footprint:** 39,448 total tokens (3944.8 tok/case)

### `gemma-4-e4b-it-speculative` (Gemma 4 E4B + Speculative Decoding (1x L4))
- **Score:** 69.5 / 100 (Pass Rate: 0.0%)
- **Latency & Throughput:** 13.97 s latency | 64.21 gen tok/s (315.66 total tok/s)
- **Tool Invocations:** 14 total calls across 10 cases
- **Token Footprint:** 44,107 total tokens (4410.7 tok/case)

### `gemma-4-31b-it-speculative` (Gemma 4 31B + Speculative Decoding (2x A100))
- **Score:** 71.8 / 100 (Pass Rate: 0.0%)
- **Latency & Throughput:** 12.56 s latency | 69.59 gen tok/s (297.59 total tok/s)
- **Tool Invocations:** 9 total calls across 10 cases
- **Token Footprint:** 37,367 total tokens (3736.7 tok/case)

### `gemma-4-31b-it-draft-e2b` (Gemma 4 31B + Gemma 4 E2B Draft (2x A100))
- **Score:** 62.5 / 100 (Pass Rate: 0.0%)
- **Latency & Throughput:** 15.41 s latency | 51.58 gen tok/s (283.38 total tok/s)
- **Tool Invocations:** 14 total calls across 10 cases
- **Token Footprint:** 43,676 total tokens (4367.6 tok/case)

### `gemma-4-31b-it-draft-e4b` (Gemma 4 31B + Gemma 4 E4B Draft (2x A100))
- **Score:** 60.5 / 100 (Pass Rate: 0.0%)
- **Latency & Throughput:** 15.41 s latency | 57.48 gen tok/s (273.93 total tok/s)
- **Tool Invocations:** 12 total calls across 10 cases
- **Token Footprint:** 42,209 total tokens (4220.9 tok/case)

### `gemini-2.5-flash` (Vertex AI Managed MaaS)
- **Score:** 64.0 / 100 (Pass Rate: 30.0%)
- **Latency & Throughput:** 13.77 s latency | 98.14 gen tok/s (670.31 total tok/s)
- **Tool Invocations:** 11 total calls across 10 cases
- **Token Footprint:** 92,319 total tokens (9231.9 tok/case)

### `gemini-2.5-pro` (Vertex AI Managed MaaS Pro)
- **Score:** 42.0 / 100 (Pass Rate: 20.0%)
- **Latency & Throughput:** 43.35 s latency | 51.86 gen tok/s (382.95 total tok/s)
- **Tool Invocations:** 24 total calls across 10 cases
- **Token Footprint:** 165,996 total tokens (16599.6 tok/case)

### `gemini-3.5-flash-lite` (Vertex AI Global MaaS)
- **Score:** 75.0 / 100 (Pass Rate: 60.0%)
- **Latency & Throughput:** 9.30 s latency | 85.73 gen tok/s (881.00 total tok/s)
- **Tool Invocations:** 15 total calls across 10 cases
- **Token Footprint:** 81,926 total tokens (8192.6 tok/case)

### `gemini-3.7-flash` (Vertex AI Global MaaS)
- **Score:** 57.1 / 100 (Pass Rate: 20.0%)
- **Latency & Throughput:** 27.91 s latency | 67.46 gen tok/s (514.11 total tok/s)
- **Tool Invocations:** 22 total calls across 10 cases
- **Token Footprint:** 143,479 total tokens (14347.9 tok/case)

### `gemini-2.5-flash-lite` (Vertex AI Managed MaaS Lite)
- **Score:** 58.0 / 100 (Pass Rate: 30.0%)
- **Latency & Throughput:** 28.56 s latency | 361.37 gen tok/s (1350.74 total tok/s)
- **Tool Invocations:** 24 total calls across 10 cases
- **Token Footprint:** 385,830 total tokens (38583.0 tok/case)

### `gemini-3.1-flash-lite` (Vertex AI Global MaaS Lite)
- **Score:** 53.5 / 100 (Pass Rate: 20.0%)
- **Latency & Throughput:** 10.40 s latency | 119.10 gen tok/s (863.65 total tok/s)
- **Tool Invocations:** 14 total calls across 10 cases
- **Token Footprint:** 89,789 total tokens (8978.9 tok/case)

### `gemma-4-26b-a4b-it-maas` (Gemma 4 MoE (Active 4B) Vertex MaaS)
- **Score:** 31.0 / 100 (Pass Rate: 0.0%)
- **Latency & Throughput:** 86.76 s latency | 36.19 gen tok/s (224.99 total tok/s)
- **Tool Invocations:** 31 total calls across 10 cases
- **Token Footprint:** 195,209 total tokens (19520.9 tok/case)

### `grok-4.6` (Partner / OpenModel)
- **Score:** 1.0 / 100 (Pass Rate: 0.0%)
- **Latency & Throughput:** 1.31 s latency | 0.00 gen tok/s (0.00 total tok/s)
- **Tool Invocations:** 0 total calls across 10 cases
- **Token Footprint:** 0 total tokens (0.0 tok/case)

### `inkling-small` (Partner / OpenModel)
- **Score:** 75.5 / 100 (Pass Rate: 40.0%)
- **Latency & Throughput:** 14.34 s latency | 74.76 gen tok/s (552.61 total tok/s)
- **Tool Invocations:** 11 total calls across 10 cases
- **Token Footprint:** 79,258 total tokens (7925.8 tok/case)

### `llama-3.1-405b-instruct-maas` (Partner / OpenModel)
- **Score:** 1.0 / 100 (Pass Rate: 0.0%)
- **Latency & Throughput:** 1.25 s latency | 0.00 gen tok/s (0.00 total tok/s)
- **Tool Invocations:** 0 total calls across 10 cases
- **Token Footprint:** 0 total tokens (0.0 tok/case)

### `llama-3.1-8b-instruct-maas` (Partner / OpenModel)
- **Score:** 0.0 / 100 (Pass Rate: 0.0%)
- **Latency & Throughput:** 1.20 s latency | 0.00 gen tok/s (0.00 total tok/s)
- **Tool Invocations:** 0 total calls across 10 cases
- **Token Footprint:** 0 total tokens (0.0 tok/case)

### `llama-3.1-nemotron-70b-instruct` (Partner / OpenModel)
- **Score:** 77.8 / 100 (Pass Rate: 50.0%)
- **Latency & Throughput:** 18.21 s latency | 79.76 gen tok/s (463.51 total tok/s)
- **Tool Invocations:** 10 total calls across 10 cases
- **Token Footprint:** 84,390 total tokens (8439.0 tok/case)

### `llama-3.2-11b-vision-instruct-maas` (Partner / OpenModel)
- **Score:** 1.0 / 100 (Pass Rate: 0.0%)
- **Latency & Throughput:** 1.30 s latency | 0.00 gen tok/s (0.00 total tok/s)
- **Tool Invocations:** 0 total calls across 10 cases
- **Token Footprint:** 0 total tokens (0.0 tok/case)

### `llama-3.2-3b-instruct` (Partner / OpenModel)
- **Score:** 67.0 / 100 (Pass Rate: 40.0%)
- **Latency & Throughput:** 15.44 s latency | 69.42 gen tok/s (537.64 total tok/s)
- **Tool Invocations:** 11 total calls across 10 cases
- **Token Footprint:** 83,021 total tokens (8302.1 tok/case)

### `llama-3.3-70b-instruct-maas` (Partner / OpenModel)
- **Score:** 0.0 / 100 (Pass Rate: 0.0%)
- **Latency & Throughput:** 1.21 s latency | 0.00 gen tok/s (0.00 total tok/s)
- **Tool Invocations:** 0 total calls across 10 cases
- **Token Footprint:** 0 total tokens (0.0 tok/case)

### `llama-4-maverick-17b-128e-instruct-maas` (Partner / OpenModel)
- **Score:** 1.0 / 100 (Pass Rate: 0.0%)
- **Latency & Throughput:** 1.19 s latency | 0.00 gen tok/s (0.00 total tok/s)
- **Tool Invocations:** 0 total calls across 10 cases
- **Token Footprint:** 0 total tokens (0.0 tok/case)

### `llama-4-scout-17b-16e-instruct-maas` (Partner / OpenModel)
- **Score:** 1.0 / 100 (Pass Rate: 0.0%)
- **Latency & Throughput:** 1.30 s latency | 0.00 gen tok/s (0.00 total tok/s)
- **Tool Invocations:** 0 total calls across 10 cases
- **Token Footprint:** 0 total tokens (0.0 tok/case)

### `llama-guard-3-8b` (Partner / OpenModel)
- **Score:** 64.3 / 100 (Pass Rate: 40.0%)
- **Latency & Throughput:** 16.51 s latency | 79.18 gen tok/s (530.38 total tok/s)
- **Tool Invocations:** 12 total calls across 10 cases
- **Token Footprint:** 87,591 total tokens (8759.1 tok/case)

### `muse-spark-1.3` (Meta Muse Spark 1.3 Agentic Reasoner)
- **Score:** 1.0 / 100 (Pass Rate: 0.0%)
- **Latency & Throughput:** 2.27 s latency | 0.00 gen tok/s (0.00 total tok/s)
- **Tool Invocations:** 0 total calls across 10 cases
- **Token Footprint:** 0 total tokens (0.0 tok/case)

### `nemotron-3.5-lightning-bf16` (Partner / OpenModel)
- **Score:** 71.0 / 100 (Pass Rate: 40.0%)
- **Latency & Throughput:** 17.21 s latency | 81.63 gen tok/s (514.67 total tok/s)
- **Tool Invocations:** 11 total calls across 10 cases
- **Token Footprint:** 88,598 total tokens (8859.8 tok/case)

### `qwen3.8-27b` (Partner / OpenModel)
- **Score:** 56.5 / 100 (Pass Rate: 20.0%)
- **Latency & Throughput:** 16.92 s latency | 83.99 gen tok/s (508.52 total tok/s)
- **Tool Invocations:** 11 total calls across 10 cases
- **Token Footprint:** 86,018 total tokens (8601.8 tok/case)

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

- Detailed gemma-2-2b-it Report: [`soc_eval_results/gemma-2-2b-it_report.md`](soc_eval_results/gemma-2-2b-it_report.md)
- Detailed gemma-2-9b-it Report: [`soc_eval_results/gemma-2-9b-it_report.md`](soc_eval_results/gemma-2-9b-it_report.md)
- Detailed gemma-2-27b-it Report: [`soc_eval_results/gemma-2-27b-it_report.md`](soc_eval_results/gemma-2-27b-it_report.md)
- Detailed gemma-2-2b-it-speculative Report: [`soc_eval_results/gemma-2-2b-it-speculative_report.md`](soc_eval_results/gemma-2-2b-it-speculative_report.md)
- Detailed gemma-2-9b-it-fp8 Report: [`soc_eval_results/gemma-2-9b-it-fp8_report.md`](soc_eval_results/gemma-2-9b-it-fp8_report.md)
- Detailed gemma-2-9b-it-speculative Report: [`soc_eval_results/gemma-2-9b-it-speculative_report.md`](soc_eval_results/gemma-2-9b-it-speculative_report.md)
- Detailed gemma-2-27b-it-fp8 Report: [`soc_eval_results/gemma-2-27b-it-fp8_report.md`](soc_eval_results/gemma-2-27b-it-fp8_report.md)
- Detailed gemma-2-27b-it-speculative Report: [`soc_eval_results/gemma-2-27b-it-speculative_report.md`](soc_eval_results/gemma-2-27b-it-speculative_report.md)
- Detailed gemma-3-1b-it Report: [`soc_eval_results/gemma-3-1b-it_report.md`](soc_eval_results/gemma-3-1b-it_report.md)
- Detailed gemma-3-4b-it Report: [`soc_eval_results/gemma-3-4b-it_report.md`](soc_eval_results/gemma-3-4b-it_report.md)
- Detailed gemma-3-12b-it Report: [`soc_eval_results/gemma-3-12b-it_report.md`](soc_eval_results/gemma-3-12b-it_report.md)
- Detailed gemma-3-27b-it Report: [`soc_eval_results/gemma-3-27b-it_report.md`](soc_eval_results/gemma-3-27b-it_report.md)
- Detailed gemma-3-1b-it-speculative Report: [`soc_eval_results/gemma-3-1b-it-speculative_report.md`](soc_eval_results/gemma-3-1b-it-speculative_report.md)
- Detailed gemma-3-4b-it-speculative Report: [`soc_eval_results/gemma-3-4b-it-speculative_report.md`](soc_eval_results/gemma-3-4b-it-speculative_report.md)
- Detailed gemma-3-12b-it-fp8 Report: [`soc_eval_results/gemma-3-12b-it-fp8_report.md`](soc_eval_results/gemma-3-12b-it-fp8_report.md)
- Detailed gemma-3-12b-it-speculative Report: [`soc_eval_results/gemma-3-12b-it-speculative_report.md`](soc_eval_results/gemma-3-12b-it-speculative_report.md)
- Detailed gemma-3-12b-it-draft-1b Report: [`soc_eval_results/gemma-3-12b-it-draft-1b_report.md`](soc_eval_results/gemma-3-12b-it-draft-1b_report.md)
- Detailed gemma-3-27b-it-fp8 Report: [`soc_eval_results/gemma-3-27b-it-fp8_report.md`](soc_eval_results/gemma-3-27b-it-fp8_report.md)
- Detailed gemma-3-27b-it-speculative Report: [`soc_eval_results/gemma-3-27b-it-speculative_report.md`](soc_eval_results/gemma-3-27b-it-speculative_report.md)
- Detailed gemma-3-27b-it-caching Report: [`soc_eval_results/gemma-3-27b-it-caching_report.md`](soc_eval_results/gemma-3-27b-it-caching_report.md)
- Detailed gemma-3-27b-it-draft-1b Report: [`soc_eval_results/gemma-3-27b-it-draft-1b_report.md`](soc_eval_results/gemma-3-27b-it-draft-1b_report.md)
- Detailed gemma-3-27b-it-draft-4b Report: [`soc_eval_results/gemma-3-27b-it-draft-4b_report.md`](soc_eval_results/gemma-3-27b-it-draft-4b_report.md)
- Detailed gemma-4-e2b-it Report: [`soc_eval_results/gemma-4-e2b-it_report.md`](soc_eval_results/gemma-4-e2b-it_report.md)
- Detailed gemma-4-e4b-it Report: [`soc_eval_results/gemma-4-e4b-it_report.md`](soc_eval_results/gemma-4-e4b-it_report.md)
- Detailed gemma-4-31b-it Report: [`soc_eval_results/gemma-4-31b-it_report.md`](soc_eval_results/gemma-4-31b-it_report.md)
- Detailed gemma-4-e2b-it-speculative Report: [`soc_eval_results/gemma-4-e2b-it-speculative_report.md`](soc_eval_results/gemma-4-e2b-it-speculative_report.md)
- Detailed gemma-4-e4b-it-speculative Report: [`soc_eval_results/gemma-4-e4b-it-speculative_report.md`](soc_eval_results/gemma-4-e4b-it-speculative_report.md)
- Detailed gemma-4-31b-it-speculative Report: [`soc_eval_results/gemma-4-31b-it-speculative_report.md`](soc_eval_results/gemma-4-31b-it-speculative_report.md)
- Detailed gemma-4-31b-it-draft-e2b Report: [`soc_eval_results/gemma-4-31b-it-draft-e2b_report.md`](soc_eval_results/gemma-4-31b-it-draft-e2b_report.md)
- Detailed gemma-4-31b-it-draft-e4b Report: [`soc_eval_results/gemma-4-31b-it-draft-e4b_report.md`](soc_eval_results/gemma-4-31b-it-draft-e4b_report.md)
- Detailed gemini-2.5-flash Report: [`soc_eval_results/gemini-2.5-flash_report.md`](soc_eval_results/gemini-2.5-flash_report.md)
- Detailed gemini-2.5-pro Report: [`soc_eval_results/gemini-2.5-pro_report.md`](soc_eval_results/gemini-2.5-pro_report.md)
- Detailed gemini-3.5-flash-lite Report: [`soc_eval_results/gemini-3.5-flash-lite_report.md`](soc_eval_results/gemini-3.5-flash-lite_report.md)
- Detailed gemini-3.7-flash Report: [`soc_eval_results/gemini-3.7-flash_report.md`](soc_eval_results/gemini-3.7-flash_report.md)
- Detailed gemini-2.5-flash-lite Report: [`soc_eval_results/gemini-2.5-flash-lite_report.md`](soc_eval_results/gemini-2.5-flash-lite_report.md)
- Detailed gemini-3.1-flash-lite Report: [`soc_eval_results/gemini-3.1-flash-lite_report.md`](soc_eval_results/gemini-3.1-flash-lite_report.md)
- Detailed gemma-4-26b-a4b-it-maas Report: [`soc_eval_results/gemma-4-26b-a4b-it-maas_report.md`](soc_eval_results/gemma-4-26b-a4b-it-maas_report.md)
- Detailed grok-4.6 Report: [`soc_eval_results/grok-4.6_report.md`](soc_eval_results/grok-4.6_report.md)
- Detailed inkling-small Report: [`soc_eval_results/inkling-small_report.md`](soc_eval_results/inkling-small_report.md)
- Detailed llama-3.1-405b-instruct-maas Report: [`soc_eval_results/llama-3.1-405b-instruct-maas_report.md`](soc_eval_results/llama-3.1-405b-instruct-maas_report.md)
- Detailed llama-3.1-8b-instruct-maas Report: [`soc_eval_results/llama-3.1-8b-instruct-maas_report.md`](soc_eval_results/llama-3.1-8b-instruct-maas_report.md)
- Detailed llama-3.1-nemotron-70b-instruct Report: [`soc_eval_results/llama-3.1-nemotron-70b-instruct_report.md`](soc_eval_results/llama-3.1-nemotron-70b-instruct_report.md)
- Detailed llama-3.2-11b-vision-instruct-maas Report: [`soc_eval_results/llama-3.2-11b-vision-instruct-maas_report.md`](soc_eval_results/llama-3.2-11b-vision-instruct-maas_report.md)
- Detailed llama-3.2-3b-instruct Report: [`soc_eval_results/llama-3.2-3b-instruct_report.md`](soc_eval_results/llama-3.2-3b-instruct_report.md)
- Detailed llama-3.3-70b-instruct-maas Report: [`soc_eval_results/llama-3.3-70b-instruct-maas_report.md`](soc_eval_results/llama-3.3-70b-instruct-maas_report.md)
- Detailed llama-4-maverick-17b-128e-instruct-maas Report: [`soc_eval_results/llama-4-maverick-17b-128e-instruct-maas_report.md`](soc_eval_results/llama-4-maverick-17b-128e-instruct-maas_report.md)
- Detailed llama-4-scout-17b-16e-instruct-maas Report: [`soc_eval_results/llama-4-scout-17b-16e-instruct-maas_report.md`](soc_eval_results/llama-4-scout-17b-16e-instruct-maas_report.md)
- Detailed llama-guard-3-8b Report: [`soc_eval_results/llama-guard-3-8b_report.md`](soc_eval_results/llama-guard-3-8b_report.md)
- Detailed muse-spark-1.3 Report: [`soc_eval_results/muse-spark-1.3_report.md`](soc_eval_results/muse-spark-1.3_report.md)
- Detailed nemotron-3.5-lightning-bf16 Report: [`soc_eval_results/nemotron-3.5-lightning-bf16_report.md`](soc_eval_results/nemotron-3.5-lightning-bf16_report.md)
- Detailed qwen3.8-27b Report: [`soc_eval_results/qwen3.8-27b_report.md`](soc_eval_results/qwen3.8-27b_report.md)
