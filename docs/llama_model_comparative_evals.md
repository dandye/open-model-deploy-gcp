# Llama & Partner Models SOC Comparative Evaluations

## 1. Executive Summary & Benchmark Scorecard

This document tracks the comparative performance of Meta Llama and partner Model Garden models evaluated on the un-spoiled SOC Tier 1 declarative evaluation benchmark ([`configs/evals/soc_tier1_evalset.json`](../configs/evals/soc_tier1_evalset.json)).

### Comparative Matrix

| Model Architecture | Provider / Serving | Pass Rate | Avg Rubric | Latency | Gen TPS | Total TPS | Tool Calls |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Llama 4 Scout 17B-16E** | Meta / Vertex MaaS (`us-east5`) | **40.0% (2/5)** | **77.0 / 100** | **8.93 s** | **82.73 tok/s** | **269.56 tok/s** | **4** |
| **Nemotron 3.5 Super VL 120B-A12B NVFP4** | NVIDIA / Dedicated 1x RTX PRO 6000 (`g4-48`) | **50.0% (5/10)** | **83.0 / 100** | **45.84 s** | **186.87 tok/s** | **439.65 tok/s** | **20** |
| **Llama 4 Maverick 17B-128E** | Meta / Vertex MaaS (`us-east5`) | 0.0% (0/5) | 62.0 / 100 | 12.08 s | 61.36 tok/s | 131.51 tok/s | 0 |
| **Gemma 4 31B Instruct** | Google / Dedicated 4x L4 (`g2-48`) | 80.0% (4/5) | 88.0 / 100 | 6.84 s | 35.84 tok/s | 35.84 tok/s | 4 |
| **Gemma 4 E4B Instruct** | Google / Dedicated 1x L4 (`g2-8`) | 60.0% (3/5) | 82.0 / 100 | 5.21 s | 46.12 tok/s | 46.12 tok/s | 3 |
| **Gemma 3 27B Instruct** | Google / Dedicated 4x L4 (`g2-48`) | 80.0% (4/5) | 87.0 / 100 | 7.12 s | 32.40 tok/s | 32.40 tok/s | 4 |
| **Gemma 3 12B Instruct** | Google / Dedicated 1x L4 (`g2-12`) | 60.0% (3/5) | 79.0 / 100 | 6.45 s | 38.20 tok/s | 38.20 tok/s | 3 |
| **Gemini 2.5 Flash** | Google / Vertex AI Managed | 100.0% (5/5) | 96.0 / 100 | 3.14 s | 124.50 tok/s | 340.20 tok/s | 5 |

---

## 2. Case-by-Case Breakdown

### 2.1 Llama 4 Scout 17B-16E (`llama-4-scout-17b-16e-instruct-maas`)
* **Pass Rate:** 40.0% (2/5)
* **Average Rubric:** 77.0 / 100
* **Average Output Speed:** 82.73 tok/s
* **Total Tokens Consumed:** 12,033 tokens
* **Total Autonomous Tool Calls:** 4

| Case ID | Scenario Name | Status | Rubric | Latency | Gen TPS | Tool Calls | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `CASE-01` | Lokibot C2 Malware Triage | FAIL | 75 / 100 | 13.18 s | 73.19 tok/s | 1 | Correctly queried `search_threat_intel`; partial containment formatting. |
| `CASE-02` | RFC-5737 Benign IP Grounding | **PASS** | **100 / 100** | **7.06 s** | **66.03 tok/s** | **1** | Perfect epistemic grounding; resolved RFC-5737 as benign. |
| `CASE-03` | Phishing Credential Harvest | FAIL | 50 / 100 | 7.34 s | 111.95 tok/s | 0 | Jumped directly to final answer without querying entity lookups. |
| `CASE-04` | Duplicate SOAR Case Detection | **PASS** | **85 / 100** | **11.23 s** | **74.16 tok/s** | **2** | Executed 2-hop SOAR search and merged duplicate case correctly. |
| `CASE-05` | Ransomware Escalation | FAIL | 75 / 100 | 5.82 s | 104.22 tok/s | 0 | Correct high-severity escalation, but missed host isolation tool call. |

---

### 2.2 Llama 4 Maverick 17B-128E (`llama-4-maverick-17b-128e-instruct-maas`)
* **Pass Rate:** 0.0% (0/5)
* **Average Rubric:** 62.0 / 100
* **Average Output Speed:** 61.36 tok/s
* **Total Tokens Consumed:** 7,945 tokens
* **Total Autonomous Tool Calls:** 0

| Case ID | Scenario Name | Status | Rubric | Latency | Gen TPS | Tool Calls | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `CASE-01` | Lokibot C2 Malware Triage | FAIL | 75 / 100 | 24.00 s | 35.16 tok/s | 0 | Outputted correct structured triage directly without calling tools. |
| `CASE-02` | RFC-5737 Benign IP Grounding | FAIL | 0 / 100 | 6.26 s | 74.61 tok/s | 0 | Hallucinated malicious verdict on test documentation IP without calling IP report tool. |
| `CASE-03` | Phishing Credential Harvest | FAIL | 75 / 100 | 7.80 s | 89.24 tok/s | 0 | Good structured analysis, but omitted user investigation tool call. |
| `CASE-04` | Duplicate SOAR Case Detection | FAIL | 100 / 100 (Judge) | 11.60 s | 70.09 tok/s | 0 | Scored 100 on rubric, but failed deterministic assertion on case ID check. |
| `CASE-05` | Ransomware Escalation | FAIL | 60 / 100 | 10.75 s | 82.48 tok/s | 0 | Missed host containment assertion check. |

---

### 2.3 NVIDIA Nemotron 3.5 Super VL 120B-A12B NVFP4 (`nemotron-3.5-super-vl-nvfp4`)
* **Hardware & Cost:** `g4-standard-48` (`1x NVIDIA_RTX_PRO_6000` 96 GB Blackwell, 192 GB RAM, `100 GB /dev/shm`, **$3.85/hr**, **$4.52 / 1M output tokens** at `236.5 tok/s` benchmark speed)
* **Pass Rate (Gen 3 10-Case Suite):** 50.0% (5/10)
* **Average Rubric:** 83.0 / 100 (90.0–100.0/100 on 8 of 10 cases)
* **Average Output Speed:** 186.87 tok/s (439.65 tok/s total TPS; 236.5 tok/s on `BenchmarkRunner` at `Concurrency=1`)
* **Total Tokens Consumed:** 201,519 tokens (Avg: 20,151.9 tok/case)
* **Total Autonomous Tool Calls:** 20 (Epistemic Efficiency: 0.85, Pragmatic Action Match: 90.0%, Counterfactual Consistency: 100.0%)

| Case ID | Scenario Name | Status | Rubric | Latency | Gen TPS | Tool Calls | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `CASE-GEN3-01` | Lokibot C2 Malware Triage | **PASS** | **100 / 100** | **29.53 s** | **166.22 tok/s** | **1** | Enriched `update-service-win32.com`, recommended `isolate_host` + `block_indicator` ($0 loss). |
| `CASE-GEN3-02` | RFC-5737 Benign IP Grounding | **PASS** | **100 / 100** | **25.90 s** | **193.54 tok/s** | **2** | Enriched `192.0.2.100` and `GW-CORE-VPN-01`, closed benign TEST-NET-1 alert ($0 loss). |
| `CASE-GEN3-03` | Phishing Credential Harvest | FAIL | 90 / 100 | 26.17 s | 191.42 tok/s | 1 | Matched `block_indicator` + `isolate_host` ($0 loss); failed single-call JEV grounding gate. |
| `CASE-GEN3-04` | Duplicate SOAR Case Detection | FAIL | 80 / 100 | 119.85 s | 186.62 tok/s | 5 | Located `CASE-33279`, enriched IP, and executed `update_case_comment` in-band before hitting 5-step cap. |
| `CASE-GEN3-05` | Ransomware Escalation | **PASS** | **90 / 100** | **25.71 s** | **181.53 tok/s** | **2** | Enriched `DESKTOP-FIN-08` and `198.51.100.42`, isolated host without reboot ($0 loss). |
| `CASE-GEN3-06` | Ambiguous DNS Tunneling | **PASS** | **90 / 100** | **69.52 s** | **203.15 tok/s** | **3** | Enriched case, domain, and CFO host; blocked domain while withholding disruptive `isolate_host` ($0 loss). |
| `CASE-GEN3-07` | PsExec Lateral Movement | FAIL | 90 / 100 | 40.69 s | 177.20 tok/s | 1 | Enriched `DESKTOP-HR-04`, matched `isolate_host` ($0 loss); failed single-call JEV grounding gate. |
| `CASE-GEN3-08` | Supply Chain Revoked Cert | FAIL | 0 / 100 | 43.55 s | 188.12 tok/s | 0 | Exhausted 8,192 completion token budget inside `<think>` reasoning at step 0. |
| `CASE-GEN3-09` | HTTP 503 Outage Resilience | FAIL | 90 / 100 | 29.87 s | 181.39 tok/s | 3 | Gracefully handled HTTP 503 without retry loops; held case as `SUSPICIOUS` ($250 escalation loss). |
| `CASE-GEN3-10` | Authorized Scanner Noise | **PASS** | **100 / 100** | **47.58 s** | **183.85 tok/s** | **2** | Verified Qualys Scanner on `SRV-PROD-PAYMENT-01`, avoided $50k downtime isolation ($0 loss). |

---

## 3. Key Observations & Comparison

1. **ReAct Tool-Calling Propensity**:
   - **Llama 4 Scout (16 experts)** demonstrated higher propensity to invoke external tools (4 tool calls across 5 scenarios), correctly executing multi-hop tool loops in `CASE-01`, `CASE-02`, and `CASE-04`.
   - **Llama 4 Maverick (128 experts)** tended to synthesize answers in a single turn without triggering ReAct `Action:` loops, leading to severe hallucination in `CASE-02` (RFC-5737).
2. **Generation Throughput**:
   - Llama 4 MaaS endpoints demonstrated strong throughput on Vertex AI, averaging **82.73 tok/s** for Scout and **61.36 tok/s** for Maverick.
3. **Structured SOAR Formatting**:
   - Both models followed the four-part structured report format (`[Context & Enrichment]`, `[Analysis & Verdict]`, `[Action & Escalation]`, `[SOAR Documentation]`) consistently.
