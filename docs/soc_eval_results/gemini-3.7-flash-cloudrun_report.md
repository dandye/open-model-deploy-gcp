# SOC Evaluation Report: gemini-3.7-flash (Vertex AI Model-as-a-Service)

**Date:** 2026-08-29 22:55:22 UTC
**Deployment Platform:** Vertex AI MaaS
**Region:** us-central1
**Hardware:** Hosted Managed Model
**Cold Start:** 0.00 s (Managed)
**Notes:** Frontier Managed Gemini 3.7 Flash (Hybrid Reasoning)

## 1. Executive Summary
- **Pass Rate:** 40.0% (2/5)
- **Average Rubric Score:** 53.6 / 100
- **Average Latency:** 19.6 s
- **Output Throughput (Generation TPS):** 39.91 tok/s
- **Total Processing Throughput:** 248.48 tok/s
- **Total Token Usage:** 24355 tokens (Avg: 4871.0 tok/case)
- **Total Tool Invocations:** 11

## 2. Evaluation Scorecard Matrix

| Case ID | Case Name | Rubric Score | Grounding | Status | Latency | Gen TPS | Total Tokens | Tool Calls |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| CASE-01-LOKIBOT-C2 | Lokibot C2 Malware Beaconing Triage | 0.0/100 | 1.00 | FAIL | 23.24s | 55.13 tok/s | 6204 | 2 |
| CASE-02-RFC5737-BENIGN-IP | RFC-5737 Documentation IP Enrichment (Grounding Test) | 100.0/100 | 1.00 | PASS | 16.91s | 37.2 tok/s | 4122 | 2 |
| CASE-03-PHISHING-CRED-HARVEST | Phishing Alert & Entity Investigation | 0.0/100 | 0.00 | FAIL | 15.46s | 12.48 tok/s | 4713 | 3 |
| CASE-04-DUPLICATE-SOAR-CASE | Duplicate SOAR Case Detection | 70.0/100 | 1.00 | FAIL | 29.25s | 26.12 tok/s | 6149 | 3 |
| CASE-05-RANSOMWARE-ESCALATION | Critical Ransomware Containment Escalation | 98.0/100 | 1.00 | PASS | 13.16s | 79.41 tok/s | 3167 | 1 |