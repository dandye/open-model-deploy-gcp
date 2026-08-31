# SOC Evaluation Report: gemma-3-1b-it (Cloud Run Serverless GPU)

**Date:** 2026-08-29 23:08:44 UTC
**Deployment Platform:** Cloud Run (Serverless GPU, Scale-to-Zero)
**Region:** europe-west4
**Hardware:** 1x nvidia-l4
**Cold Start Latency (0 -> 1 instance):** 0.87 s
**Notes:** Gemma 3 1B Dense (1x L4, Scale-to-Zero)

## 1. Executive Summary
- **Pass Rate:** 0.0% (0/5)
- **Average Rubric Score:** 28.0 / 100
- **Average Latency:** 25.71 s
- **Output Throughput (Generation TPS):** 17.35 tok/s
- **Total Processing Throughput:** 103.08 tok/s
- **Total Token Usage:** 13249 tokens (Avg: 2649.8 tok/case)
- **Total Tool Invocations:** 5

## 2. Evaluation Scorecard Matrix

| Case ID | Case Name | Rubric Score | Grounding | Status | Latency | Gen TPS | Total Tokens | Tool Calls |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| CASE-01-LOKIBOT-C2 | Lokibot C2 Malware Beaconing Triage | 25.0/100 | 0.20 | FAIL | 17.93s | 18.24 tok/s | 1238 | 0 |
| CASE-02-RFC5737-BENIGN-IP | RFC-5737 Documentation IP Enrichment (Grounding Test) | 0.0/100 | 0.00 | FAIL | 69.94s | 17.67 tok/s | 6303 | 3 |
| CASE-03-PHISHING-CRED-HARVEST | Phishing Alert & Entity Investigation | 20.0/100 | 0.25 | FAIL | 5.62s | 16.73 tok/s | 990 | 0 |
| CASE-04-DUPLICATE-SOAR-CASE | Duplicate SOAR Case Detection | 85.0/100 | 1.00 | FAIL | 28.55s | 16.57 tok/s | 3720 | 2 |
| CASE-05-RANSOMWARE-ESCALATION | Critical Ransomware Containment Escalation | 10.0/100 | 0.50 | FAIL | 6.48s | 15.42 tok/s | 998 | 0 |