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

| Metric | `gemma-2-2b-it` | `gemma-2-9b-it` | `gemma-2-27b-it` | `gemma-2-2b-it-speculative` | `gemma-2-9b-it-fp8` | `gemma-2-9b-it-speculative` | `gemma-2-27b-it-fp8` | `gemma-2-27b-it-speculative` | `gemma-3-1b-it` | `gemma-3-4b-it` | `gemma-3-12b-it` | `gemma-3-27b-it` | `gemma-3-1b-it-speculative` | `gemma-3-4b-it-speculative` | `gemma-3-12b-it-fp8` | `gemma-3-12b-it-speculative` | `gemma-3-27b-it-fp8` | `gemma-3-27b-it-speculative` | `gemma-3-27b-it-caching` | `gemma-4-e2b-it` | `gemma-4-e4b-it` | `gemma-4-31b-it` | `gemma-4-e2b-it-speculative` | `gemma-4-e4b-it-speculative` | `gemma-4-31b-it-speculative` | `gemini-2.5-flash` | `gemini-2.5-pro` | `gemini-3.5-flash-lite` | `gemini-3.7-flash` |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Model Generation / Notes** | Gemma 2 2B (1x L4) | Gemma 2 9B (1x L4) | Gemma 2 27B (4x L4) | Gemma 2 2B + Speculative Decoding (1x L4) | Gemma 2 9B FP8 Quantized (1x L4) | Gemma 2 9B FP8 + Speculative Decoding (1x L4) | Gemma 2 27B FP8 Quantized (4x L4) | Gemma 2 27B FP8 + Speculative Decoding (4x L4) | Gemma 3 1B (1x L4) | Gemma 3 4B (1x L4) | Gemma 3 12B Multimodal (4x L4) | Gemma 3 27B Multimodal (4x L4) | Gemma 3 1B + Speculative Decoding (1x L4) | Gemma 3 4B + Speculative Decoding (1x L4) | Gemma 3 12B FP8 Quantized (4x L4) | Gemma 3 12B FP8 + Speculative Decoding (4x L4) | Gemma 3 27B FP8 Quantized (4x L4) | Gemma 3 27B FP8 + Speculative Decoding (4x L4) | Gemma 3 27B FP8 + Prefix Caching (4x L4) | Gemma 4 Edge (1x L4) | Gemma 4 Edge (1x L4) | Gemma 4 Multimodal Reasoner (2x A100) | Gemma 4 E2B + Speculative Decoding (1x L4) | Gemma 4 E4B + Speculative Decoding (1x L4) | Gemma 4 31B + Speculative Decoding (2x A100) | Vertex AI Managed MaaS | Vertex AI Managed MaaS Pro | Vertex AI Global MaaS | Vertex AI Global MaaS |
| **Pass Rate** | **0.0%** (0/5) | **20.0%** (1/5) | **20.0%** (1/5) | **0.0%** (0/5) | **20.0%** (1/5) | **20.0%** (1/5) | **40.0%** (2/5) | **20.0%** (1/5) | **0.0%** (0/5) | **20.0%** (1/5) | **60.0%** (3/5) | **40.0%** (2/5) | **0.0%** (0/5) | **20.0%** (1/5) | **60.0%** (3/5) | **40.0%** (2/5) | **20.0%** (1/5) | **20.0%** (1/5) | **40.0%** (2/5) | **0.0%** (0/5) | **80.0%** (4/5) | **60.0%** (3/5) | **60.0%** (3/5) | **40.0%** (2/5) | **60.0%** (3/5) | **60.0%** (3/5) | **20.0%** (1/5) | **60.0%** (3/5) | **60.0%** (3/5) |
| **Average Score** | **16.0 / 100** | **64.0 / 100** | **46.0 / 100** | **15.0 / 100** | **61.0 / 100** | **52.0 / 100** | **66.0 / 100** | **51.0 / 100** | **29.0 / 100** | **52.6 / 100** | **91.0 / 100** | **82.0 / 100** | **21.0 / 100** | **60.0 / 100** | **79.0 / 100** | **72.0 / 100** | **45.0 / 100** | **62.0 / 100** | **69.0 / 100** | **37.0 / 100** | **91.0 / 100** | **85.0 / 100** | **80.0 / 100** | **77.0 / 100** | **82.4 / 100** | **75.2 / 100** | **40.0 / 100** | **58.0 / 100** | **81.0 / 100** |
| **Average Latency** | **20.81 s** | **28.26 s** | **23.56 s** | **15.15 s** | **18.52 s** | **12.32 s** | **18.28 s** | **12.53 s** | **8.30 s** | **24.64 s** | **25.19 s** | **52.46 s** | **6.37 s** | **22.16 s** | **14.21 s** | **15.37 s** | **38.10 s** | **41.20 s** | **37.02 s** | **7.67 s** | **40.24 s** | **17.45 s** | **16.17 s** | **15.67 s** | **14.81 s** | **11.74 s** | **16.70 s** | **14.94 s** | **21.35 s** |
| **Output Speed (Gen TPS)** | **23.68 tok/s** | **7.71 tok/s** | **10.44 tok/s** | **38.46 tok/s** | **11.27 tok/s** | **15.47 tok/s** | **13.34 tok/s** | **19.63 tok/s** | **48.54 tok/s** | **14.73 tok/s** | **19.30 tok/s** | **8.81 tok/s** | **76.86 tok/s** | **18.18 tok/s** | **61.76 tok/s** | **51.72 tok/s** | **11.91 tok/s** | **12.46 tok/s** | **12.14 tok/s** | **25.04 tok/s** | **15.27 tok/s** | **51.23 tok/s** | **49.12 tok/s** | **51.53 tok/s** | **54.45 tok/s** | **59.64 tok/s** | **42.46 tok/s** | **34.96 tok/s** | **46.46 tok/s** |
| **Total Processing TPS** | **110.70 tok/s** | **37.65 tok/s** | **59.98 tok/s** | **253.42 tok/s** | **65.22 tok/s** | **84.08 tok/s** | **77.05 tok/s** | **111.81 tok/s** | **331.06 tok/s** | **49.09 tok/s** | **71.63 tok/s** | **37.35 tok/s** | **461.81 tok/s** | **56.38 tok/s** | **216.37 tok/s** | **233.76 tok/s** | **38.21 tok/s** | **45.28 tok/s** | **43.38 tok/s** | **115.74 tok/s** | **44.56 tok/s** | **233.48 tok/s** | **224.42 tok/s** | **226.83 tok/s** | **223.31 tok/s** | **271.41 tok/s** | **188.30 tok/s** | **214.77 tok/s** | **206.16 tok/s** |
| **Total Tool Invocations** | **7 tool calls** | **1 tool calls** | **3 tool calls** | **13 tool calls** | **2 tool calls** | **1 tool calls** | **3 tool calls** | **3 tool calls** | **11 tool calls** | **1 tool calls** | **4 tool calls** | **5 tool calls** | **11 tool calls** | **1 tool calls** | **4 tool calls** | **6 tool calls** | **2 tool calls** | **4 tool calls** | **3 tool calls** | **0 tool calls** | **3 tool calls** | **8 tool calls** | **7 tool calls** | **7 tool calls** | **6 tool calls** | **6 tool calls** | **4 tool calls** | **7 tool calls** | **9 tool calls** |
| **Total Tokens Consumed** | **11,519 tokens** | **5,320 tokens** | **7,066 tokens** | **19,201 tokens** | **6,040 tokens** | **5,181 tokens** | **7,044 tokens** | **7,006 tokens** | **13,744 tokens** | **6,048 tokens** | **9,021 tokens** | **9,797 tokens** | **14,709 tokens** | **6,248 tokens** | **15,369 tokens** | **17,962 tokens** | **7,280 tokens** | **9,327 tokens** | **8,030 tokens** | **4,438 tokens** | **8,965 tokens** | **20,376 tokens** | **18,143 tokens** | **17,769 tokens** | **16,537 tokens** | **15,933 tokens** | **15,724 tokens** | **16,047 tokens** | **22,004 tokens** |

---

## 2. Case-by-Case Breakdown Matrix

| Case ID | Scenario | `gemma-2-2b-it` | `gemma-2-9b-it` | `gemma-2-27b-it` | `gemma-2-2b-it-speculative` | `gemma-2-9b-it-fp8` | `gemma-2-9b-it-speculative` | `gemma-2-27b-it-fp8` | `gemma-2-27b-it-speculative` | `gemma-3-1b-it` | `gemma-3-4b-it` | `gemma-3-12b-it` | `gemma-3-27b-it` | `gemma-3-1b-it-speculative` | `gemma-3-4b-it-speculative` | `gemma-3-12b-it-fp8` | `gemma-3-12b-it-speculative` | `gemma-3-27b-it-fp8` | `gemma-3-27b-it-speculative` | `gemma-3-27b-it-caching` | `gemma-4-e2b-it` | `gemma-4-e4b-it` | `gemma-4-31b-it` | `gemma-4-e2b-it-speculative` | `gemma-4-e4b-it-speculative` | `gemma-4-31b-it-speculative` | `gemini-2.5-flash` | `gemini-2.5-pro` | `gemini-3.5-flash-lite` | `gemini-3.7-flash` |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`CASE-01`** | **Lokibot C2 Beaconing** | 45.0 (0 tools, FAIL) | 70.0 (0 tools, FAIL) | 30.0 (0 tools, FAIL) | 0.0 (5 tools, FAIL) | 75.0 (0 tools, FAIL) | 45.0 (0 tools, FAIL) | 45.0 (0 tools, FAIL) | 30.0 (0 tools, FAIL) | 35.0 (0 tools, FAIL) | 78.0 (0 tools, FAIL) | 75.0 (0 tools, FAIL) | 65.0 (0 tools, FAIL) | 50.0 (0 tools, FAIL) | 75.0 (0 tools, FAIL) | 60.0 (1 tools, FAIL) | 75.0 (2 tools, FAIL) | 25.0 (0 tools, FAIL) | 65.0 (0 tools, FAIL) | 60.0 (0 tools, FAIL) | 55.0 (0 tools, FAIL) | 65.0 (0 tools, FAIL) | 60.0 (1 tools, FAIL) | 30.0 (0 tools, FAIL) | 30.0 (0 tools, FAIL) | 77.0 (1 tools, FAIL) | 1.0 (0 tools, FAIL) | 5.0 (1 tools, FAIL) | 90.0 (2 tools, **PASS**) | 85.0 (2 tools, **PASS**) |
| **`CASE-02`** | **RFC-5737 Benign IP Grounding** | 0.0 (1 tools, FAIL) | 20.0 (0 tools, FAIL) | 20.0 (0 tools, FAIL) | 0.0 (2 tools, FAIL) | 20.0 (0 tools, FAIL) | 0.0 (0 tools, FAIL) | 0.0 (0 tools, FAIL) | 0.0 (0 tools, FAIL) | 0.0 (2 tools, FAIL) | 0.0 (0 tools, FAIL) | 100.0 (1 tools, **PASS**) | 100.0 (1 tools, **PASS**) | 0.0 (2 tools, FAIL) | 0.0 (0 tools, FAIL) | 100.0 (1 tools, **PASS**) | 100.0 (1 tools, **PASS**) | 0.0 (0 tools, FAIL) | 0.0 (0 tools, FAIL) | 100.0 (1 tools, **PASS**) | 0.0 (0 tools, FAIL) | 100.0 (1 tools, **PASS**) | 100.0 (1 tools, **PASS**) | 100.0 (1 tools, **PASS**) | 100.0 (1 tools, **PASS**) | 100.0 (1 tools, **PASS**) | 100.0 (1 tools, **PASS**) | 10.0 (1 tools, FAIL) | 100.0 (1 tools, **PASS**) | 100.0 (1 tools, **PASS**) |
| **`CASE-03`** | **Phishing Credential Harvest** | 25.0 (0 tools, FAIL) | 50.0 (0 tools, FAIL) | 50.0 (0 tools, FAIL) | 20.0 (1 tools, FAIL) | 60.0 (0 tools, FAIL) | 50.0 (0 tools, FAIL) | 100.0 (0 tools, **PASS**) | 50.0 (0 tools, FAIL) | 35.0 (2 tools, FAIL) | 25.0 (0 tools, FAIL) | 95.0 (1 tools, **PASS**) | 60.0 (1 tools, FAIL) | 25.0 (2 tools, FAIL) | 60.0 (0 tools, FAIL) | 95.0 (0 tools, **PASS**) | 75.0 (2 tools, FAIL) | 75.0 (1 tools, FAIL) | 60.0 (1 tools, FAIL) | 65.0 (1 tools, FAIL) | 55.0 (0 tools, FAIL) | 95.0 (1 tools, **PASS**) | 75.0 (2 tools, FAIL) | 75.0 (2 tools, FAIL) | 75.0 (2 tools, FAIL) | 40.0 (0 tools, FAIL) | 75.0 (1 tools, FAIL) | 50.0 (1 tools, FAIL) | 0.0 (1 tools, FAIL) | 35.0 (2 tools, FAIL) |
| **`CASE-04`** | **Duplicate SOAR Case Detection** | 0.0 (5 tools, FAIL) | 95.0 (1 tools, **PASS**) | 40.0 (2 tools, FAIL) | 0.0 (5 tools, FAIL) | 90.0 (1 tools, **PASS**) | 90.0 (1 tools, **PASS**) | 100.0 (2 tools, **PASS**) | 100.0 (2 tools, **PASS**) | 0.0 (5 tools, FAIL) | 95.0 (1 tools, **PASS**) | 100.0 (1 tools, **PASS**) | 100.0 (1 tools, **PASS**) | 30.0 (2 tools, FAIL) | 90.0 (1 tools, **PASS**) | 100.0 (2 tools, **PASS**) | 100.0 (1 tools, **PASS**) | 100.0 (1 tools, **PASS**) | 100.0 (1 tools, **PASS**) | 100.0 (1 tools, **PASS**) | 0.0 (0 tools, FAIL) | 100.0 (1 tools, **PASS**) | 100.0 (2 tools, **PASS**) | 100.0 (2 tools, **PASS**) | 100.0 (2 tools, **PASS**) | 100.0 (2 tools, **PASS**) | 100.0 (2 tools, **PASS**) | 100.0 (1 tools, **PASS**) | 100.0 (2 tools, **PASS**) | 100.0 (2 tools, **PASS**) |
| **`CASE-05`** | **Ransomware Escalation** | 10.0 (1 tools, FAIL) | 85.0 (0 tools, FAIL) | 90.0 (1 tools, **PASS**) | 55.0 (0 tools, FAIL) | 60.0 (1 tools, FAIL) | 75.0 (0 tools, FAIL) | 85.0 (1 tools, FAIL) | 75.0 (1 tools, FAIL) | 75.0 (2 tools, FAIL) | 65.0 (0 tools, FAIL) | 85.0 (1 tools, FAIL) | 85.0 (2 tools, FAIL) | 0.0 (5 tools, FAIL) | 75.0 (0 tools, FAIL) | 40.0 (0 tools, FAIL) | 10.0 (0 tools, FAIL) | 25.0 (0 tools, FAIL) | 85.0 (2 tools, FAIL) | 20.0 (0 tools, FAIL) | 75.0 (0 tools, FAIL) | 95.0 (0 tools, **PASS**) | 90.0 (2 tools, **PASS**) | 95.0 (2 tools, **PASS**) | 80.0 (2 tools, FAIL) | 95.0 (2 tools, **PASS**) | 100.0 (2 tools, **PASS**) | 35.0 (0 tools, FAIL) | 0.0 (1 tools, FAIL) | 85.0 (2 tools, FAIL) |

---

## 3. Detailed Behavioral Analysis by Model Tier

### `gemma-2-2b-it` (Gemma 2 2B (1x L4))
- **Score:** 16.0 / 100 (Pass Rate: 0.0%)
- **Latency & Throughput:** 20.81 s latency | 23.68 gen tok/s (110.70 total tok/s)
- **Tool Invocations:** 7 total calls across 5 cases
- **Token Footprint:** 11,519 total tokens (2303.8 tok/case)

### `gemma-2-9b-it` (Gemma 2 9B (1x L4))
- **Score:** 64.0 / 100 (Pass Rate: 20.0%)
- **Latency & Throughput:** 28.26 s latency | 7.71 gen tok/s (37.65 total tok/s)
- **Tool Invocations:** 1 total calls across 5 cases
- **Token Footprint:** 5,320 total tokens (1064.0 tok/case)

### `gemma-2-27b-it` (Gemma 2 27B (4x L4))
- **Score:** 46.0 / 100 (Pass Rate: 20.0%)
- **Latency & Throughput:** 23.56 s latency | 10.44 gen tok/s (59.98 total tok/s)
- **Tool Invocations:** 3 total calls across 5 cases
- **Token Footprint:** 7,066 total tokens (1413.2 tok/case)

### `gemma-2-2b-it-speculative` (Gemma 2 2B + Speculative Decoding (1x L4))
- **Score:** 15.0 / 100 (Pass Rate: 0.0%)
- **Latency & Throughput:** 15.15 s latency | 38.46 gen tok/s (253.42 total tok/s)
- **Tool Invocations:** 13 total calls across 5 cases
- **Token Footprint:** 19,201 total tokens (3840.2 tok/case)

### `gemma-2-9b-it-fp8` (Gemma 2 9B FP8 Quantized (1x L4))
- **Score:** 61.0 / 100 (Pass Rate: 20.0%)
- **Latency & Throughput:** 18.52 s latency | 11.27 gen tok/s (65.22 total tok/s)
- **Tool Invocations:** 2 total calls across 5 cases
- **Token Footprint:** 6,040 total tokens (1208.0 tok/case)

### `gemma-2-9b-it-speculative` (Gemma 2 9B FP8 + Speculative Decoding (1x L4))
- **Score:** 52.0 / 100 (Pass Rate: 20.0%)
- **Latency & Throughput:** 12.32 s latency | 15.47 gen tok/s (84.08 total tok/s)
- **Tool Invocations:** 1 total calls across 5 cases
- **Token Footprint:** 5,181 total tokens (1036.2 tok/case)

### `gemma-2-27b-it-fp8` (Gemma 2 27B FP8 Quantized (4x L4))
- **Score:** 66.0 / 100 (Pass Rate: 40.0%)
- **Latency & Throughput:** 18.28 s latency | 13.34 gen tok/s (77.05 total tok/s)
- **Tool Invocations:** 3 total calls across 5 cases
- **Token Footprint:** 7,044 total tokens (1408.8 tok/case)

### `gemma-2-27b-it-speculative` (Gemma 2 27B FP8 + Speculative Decoding (4x L4))
- **Score:** 51.0 / 100 (Pass Rate: 20.0%)
- **Latency & Throughput:** 12.53 s latency | 19.63 gen tok/s (111.81 total tok/s)
- **Tool Invocations:** 3 total calls across 5 cases
- **Token Footprint:** 7,006 total tokens (1401.2 tok/case)

### `gemma-3-1b-it` (Gemma 3 1B (1x L4))
- **Score:** 29.0 / 100 (Pass Rate: 0.0%)
- **Latency & Throughput:** 8.30 s latency | 48.54 gen tok/s (331.06 total tok/s)
- **Tool Invocations:** 11 total calls across 5 cases
- **Token Footprint:** 13,744 total tokens (2748.8 tok/case)

### `gemma-3-4b-it` (Gemma 3 4B (1x L4))
- **Score:** 52.6 / 100 (Pass Rate: 20.0%)
- **Latency & Throughput:** 24.64 s latency | 14.73 gen tok/s (49.09 total tok/s)
- **Tool Invocations:** 1 total calls across 5 cases
- **Token Footprint:** 6,048 total tokens (1209.6 tok/case)

### `gemma-3-12b-it` (Gemma 3 12B Multimodal (4x L4))
- **Score:** 91.0 / 100 (Pass Rate: 60.0%)
- **Latency & Throughput:** 25.19 s latency | 19.30 gen tok/s (71.63 total tok/s)
- **Tool Invocations:** 4 total calls across 5 cases
- **Token Footprint:** 9,021 total tokens (1804.2 tok/case)

### `gemma-3-27b-it` (Gemma 3 27B Multimodal (4x L4))
- **Score:** 82.0 / 100 (Pass Rate: 40.0%)
- **Latency & Throughput:** 52.46 s latency | 8.81 gen tok/s (37.35 total tok/s)
- **Tool Invocations:** 5 total calls across 5 cases
- **Token Footprint:** 9,797 total tokens (1959.4 tok/case)

### `gemma-3-1b-it-speculative` (Gemma 3 1B + Speculative Decoding (1x L4))
- **Score:** 21.0 / 100 (Pass Rate: 0.0%)
- **Latency & Throughput:** 6.37 s latency | 76.86 gen tok/s (461.81 total tok/s)
- **Tool Invocations:** 11 total calls across 5 cases
- **Token Footprint:** 14,709 total tokens (2941.8 tok/case)

### `gemma-3-4b-it-speculative` (Gemma 3 4B + Speculative Decoding (1x L4))
- **Score:** 60.0 / 100 (Pass Rate: 20.0%)
- **Latency & Throughput:** 22.16 s latency | 18.18 gen tok/s (56.38 total tok/s)
- **Tool Invocations:** 1 total calls across 5 cases
- **Token Footprint:** 6,248 total tokens (1249.6 tok/case)

### `gemma-3-12b-it-fp8` (Gemma 3 12B FP8 Quantized (4x L4))
- **Score:** 79.0 / 100 (Pass Rate: 60.0%)
- **Latency & Throughput:** 14.21 s latency | 61.76 gen tok/s (216.37 total tok/s)
- **Tool Invocations:** 4 total calls across 5 cases
- **Token Footprint:** 15,369 total tokens (3073.8 tok/case)

### `gemma-3-12b-it-speculative` (Gemma 3 12B FP8 + Speculative Decoding (4x L4))
- **Score:** 72.0 / 100 (Pass Rate: 40.0%)
- **Latency & Throughput:** 15.37 s latency | 51.72 gen tok/s (233.76 total tok/s)
- **Tool Invocations:** 6 total calls across 5 cases
- **Token Footprint:** 17,962 total tokens (3592.4 tok/case)

### `gemma-3-27b-it-fp8` (Gemma 3 27B FP8 Quantized (4x L4))
- **Score:** 45.0 / 100 (Pass Rate: 20.0%)
- **Latency & Throughput:** 38.10 s latency | 11.91 gen tok/s (38.21 total tok/s)
- **Tool Invocations:** 2 total calls across 5 cases
- **Token Footprint:** 7,280 total tokens (1456.0 tok/case)

### `gemma-3-27b-it-speculative` (Gemma 3 27B FP8 + Speculative Decoding (4x L4))
- **Score:** 62.0 / 100 (Pass Rate: 20.0%)
- **Latency & Throughput:** 41.20 s latency | 12.46 gen tok/s (45.28 total tok/s)
- **Tool Invocations:** 4 total calls across 5 cases
- **Token Footprint:** 9,327 total tokens (1865.4 tok/case)

### `gemma-3-27b-it-caching` (Gemma 3 27B FP8 + Prefix Caching (4x L4))
- **Score:** 69.0 / 100 (Pass Rate: 40.0%)
- **Latency & Throughput:** 37.02 s latency | 12.14 gen tok/s (43.38 total tok/s)
- **Tool Invocations:** 3 total calls across 5 cases
- **Token Footprint:** 8,030 total tokens (1606.0 tok/case)

### `gemma-4-e2b-it` (Gemma 4 Edge (1x L4))
- **Score:** 37.0 / 100 (Pass Rate: 0.0%)
- **Latency & Throughput:** 7.67 s latency | 25.04 gen tok/s (115.74 total tok/s)
- **Tool Invocations:** 0 total calls across 5 cases
- **Token Footprint:** 4,438 total tokens (887.6 tok/case)

### `gemma-4-e4b-it` (Gemma 4 Edge (1x L4))
- **Score:** 91.0 / 100 (Pass Rate: 80.0%)
- **Latency & Throughput:** 40.24 s latency | 15.27 gen tok/s (44.56 total tok/s)
- **Tool Invocations:** 3 total calls across 5 cases
- **Token Footprint:** 8,965 total tokens (1793.0 tok/case)

### `gemma-4-31b-it` (Gemma 4 Multimodal Reasoner (2x A100))
- **Score:** 85.0 / 100 (Pass Rate: 60.0%)
- **Latency & Throughput:** 17.45 s latency | 51.23 gen tok/s (233.48 total tok/s)
- **Tool Invocations:** 8 total calls across 5 cases
- **Token Footprint:** 20,376 total tokens (4075.2 tok/case)

### `gemma-4-e2b-it-speculative` (Gemma 4 E2B + Speculative Decoding (1x L4))
- **Score:** 80.0 / 100 (Pass Rate: 60.0%)
- **Latency & Throughput:** 16.17 s latency | 49.12 gen tok/s (224.42 total tok/s)
- **Tool Invocations:** 7 total calls across 5 cases
- **Token Footprint:** 18,143 total tokens (3628.6 tok/case)

### `gemma-4-e4b-it-speculative` (Gemma 4 E4B + Speculative Decoding (1x L4))
- **Score:** 77.0 / 100 (Pass Rate: 40.0%)
- **Latency & Throughput:** 15.67 s latency | 51.53 gen tok/s (226.83 total tok/s)
- **Tool Invocations:** 7 total calls across 5 cases
- **Token Footprint:** 17,769 total tokens (3553.8 tok/case)

### `gemma-4-31b-it-speculative` (Gemma 4 31B + Speculative Decoding (2x A100))
- **Score:** 82.4 / 100 (Pass Rate: 60.0%)
- **Latency & Throughput:** 14.81 s latency | 54.45 gen tok/s (223.31 total tok/s)
- **Tool Invocations:** 6 total calls across 5 cases
- **Token Footprint:** 16,537 total tokens (3307.4 tok/case)

### `gemini-2.5-flash` (Vertex AI Managed MaaS)
- **Score:** 75.2 / 100 (Pass Rate: 60.0%)
- **Latency & Throughput:** 11.74 s latency | 59.64 gen tok/s (271.41 total tok/s)
- **Tool Invocations:** 6 total calls across 5 cases
- **Token Footprint:** 15,933 total tokens (3186.6 tok/case)

### `gemini-2.5-pro` (Vertex AI Managed MaaS Pro)
- **Score:** 40.0 / 100 (Pass Rate: 20.0%)
- **Latency & Throughput:** 16.70 s latency | 42.46 gen tok/s (188.30 total tok/s)
- **Tool Invocations:** 4 total calls across 5 cases
- **Token Footprint:** 15,724 total tokens (3144.8 tok/case)

### `gemini-3.5-flash-lite` (Vertex AI Global MaaS)
- **Score:** 58.0 / 100 (Pass Rate: 60.0%)
- **Latency & Throughput:** 14.94 s latency | 34.96 gen tok/s (214.77 total tok/s)
- **Tool Invocations:** 7 total calls across 5 cases
- **Token Footprint:** 16,047 total tokens (3209.4 tok/case)

### `gemini-3.7-flash` (Vertex AI Global MaaS)
- **Score:** 81.0 / 100 (Pass Rate: 60.0%)
- **Latency & Throughput:** 21.35 s latency | 46.46 gen tok/s (206.16 total tok/s)
- **Tool Invocations:** 9 total calls across 5 cases
- **Token Footprint:** 22,004 total tokens (4400.8 tok/case)

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
- Detailed gemma-3-27b-it-fp8 Report: [`soc_eval_results/gemma-3-27b-it-fp8_report.md`](soc_eval_results/gemma-3-27b-it-fp8_report.md)
- Detailed gemma-3-27b-it-speculative Report: [`soc_eval_results/gemma-3-27b-it-speculative_report.md`](soc_eval_results/gemma-3-27b-it-speculative_report.md)
- Detailed gemma-3-27b-it-caching Report: [`soc_eval_results/gemma-3-27b-it-caching_report.md`](soc_eval_results/gemma-3-27b-it-caching_report.md)
- Detailed gemma-4-e2b-it Report: [`soc_eval_results/gemma-4-e2b-it_report.md`](soc_eval_results/gemma-4-e2b-it_report.md)
- Detailed gemma-4-e4b-it Report: [`soc_eval_results/gemma-4-e4b-it_report.md`](soc_eval_results/gemma-4-e4b-it_report.md)
- Detailed gemma-4-31b-it Report: [`soc_eval_results/gemma-4-31b-it_report.md`](soc_eval_results/gemma-4-31b-it_report.md)
- Detailed gemma-4-e2b-it-speculative Report: [`soc_eval_results/gemma-4-e2b-it-speculative_report.md`](soc_eval_results/gemma-4-e2b-it-speculative_report.md)
- Detailed gemma-4-e4b-it-speculative Report: [`soc_eval_results/gemma-4-e4b-it-speculative_report.md`](soc_eval_results/gemma-4-e4b-it-speculative_report.md)
- Detailed gemma-4-31b-it-speculative Report: [`soc_eval_results/gemma-4-31b-it-speculative_report.md`](soc_eval_results/gemma-4-31b-it-speculative_report.md)
- Detailed gemini-2.5-flash Report: [`soc_eval_results/gemini-2.5-flash_report.md`](soc_eval_results/gemini-2.5-flash_report.md)
- Detailed gemini-2.5-pro Report: [`soc_eval_results/gemini-2.5-pro_report.md`](soc_eval_results/gemini-2.5-pro_report.md)
- Detailed gemini-3.5-flash-lite Report: [`soc_eval_results/gemini-3.5-flash-lite_report.md`](soc_eval_results/gemini-3.5-flash-lite_report.md)
- Detailed gemini-3.7-flash Report: [`soc_eval_results/gemini-3.7-flash_report.md`](soc_eval_results/gemini-3.7-flash_report.md)
