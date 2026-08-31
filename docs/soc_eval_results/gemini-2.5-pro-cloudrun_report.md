# SOC Evaluation Report: gemini-2.5-pro (Vertex AI Model-as-a-Service)

**Date:** 2026-08-29 22:59:15 UTC
**Deployment Platform:** Vertex AI MaaS
**Region:** us-central1
**Hardware:** Hosted Managed Model
**Cold Start:** 0.00 s (Managed)
**Notes:** Frontier Reasoning & Agentic Baseline

## 1. Executive Summary
- **Pass Rate:** 0.0% (0/5)
- **Average Rubric Score:** 29.0 / 100
- **Average Latency:** 22.89 s
- **Output Throughput (Generation TPS):** 44.25 tok/s
- **Total Processing Throughput:** 197.51 tok/s
- **Total Token Usage:** 22606 tokens (Avg: 4521.2 tok/case)
- **Total Tool Invocations:** 7

## 2. Evaluation Scorecard Matrix

| Case ID | Case Name | Rubric Score | Grounding | Status | Latency | Gen TPS | Total Tokens | Tool Calls |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| CASE-01-LOKIBOT-C2 | Lokibot C2 Malware Beaconing Triage | 65.0/100 | 1.00 | FAIL | 28.45s | 50.01 tok/s | 6056 | 2 |
| CASE-02-RFC5737-BENIGN-IP | RFC-5737 Documentation IP Enrichment (Grounding Test) | 0.0/100 | 0.00 | FAIL | 10.98s | 82.64 tok/s | 1900 | 0 |
| CASE-03-PHISHING-CRED-HARVEST | Phishing Alert & Entity Investigation | 10.0/100 | 1.00 | FAIL | 18.27s | 57.43 tok/s | 3316 | 1 |
| CASE-04-DUPLICATE-SOAR-CASE | Duplicate SOAR Case Detection | 20.0/100 | 0.50 | FAIL | 30.50s | 29.28 tok/s | 6089 | 2 |
| CASE-05-RANSOMWARE-ESCALATION | Critical Ransomware Containment Escalation | 50.0/100 | 1.00 | FAIL | 26.26s | 30.16 tok/s | 5245 | 2 |