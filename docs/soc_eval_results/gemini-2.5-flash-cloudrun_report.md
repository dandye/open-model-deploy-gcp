# SOC Evaluation Report: gemini-2.5-flash (Vertex AI Model-as-a-Service)

**Date:** 2026-08-29 23:01:16 UTC
**Deployment Platform:** Vertex AI MaaS
**Region:** us-central1
**Hardware:** Hosted Managed Model
**Cold Start:** 0.00 s (Managed)
**Notes:** High-Speed Production Baseline

## 1. Executive Summary
- **Pass Rate:** 40.0% (2/5)
- **Average Rubric Score:** 66.0 / 100
- **Average Latency:** 10.84 s
- **Output Throughput (Generation TPS):** 57.48 tok/s
- **Total Processing Throughput:** 273.55 tok/s
- **Total Token Usage:** 14828 tokens (Avg: 2965.6 tok/case)
- **Total Tool Invocations:** 5

## 2. Evaluation Scorecard Matrix

| Case ID | Case Name | Rubric Score | Grounding | Status | Latency | Gen TPS | Total Tokens | Tool Calls |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| CASE-01-LOKIBOT-C2 | Lokibot C2 Malware Beaconing Triage | 55.0/100 | 0.25 | FAIL | 13.04s | 71.22 tok/s | 3285 | 1 |
| CASE-02-RFC5737-BENIGN-IP | RFC-5737 Documentation IP Enrichment (Grounding Test) | 100.0/100 | 1.00 | PASS | 8.15s | 55.07 tok/s | 2575 | 1 |
| CASE-03-PHISHING-CRED-HARVEST | Phishing Alert & Entity Investigation | 75.0/100 | 1.00 | FAIL | 8.67s | 65.54 tok/s | 2604 | 1 |
| CASE-04-DUPLICATE-SOAR-CASE | Duplicate SOAR Case Detection | 100.0/100 | 1.00 | PASS | 16.08s | 53.05 tok/s | 4462 | 2 |
| CASE-05-RANSOMWARE-ESCALATION | Critical Ransomware Containment Escalation | 0.0/100 | 0.00 | FAIL | 8.26s | 38.38 tok/s | 1902 | 0 |