# SOC Evaluation Report: gemma-4-e2b-it (Cloud Run Serverless GPU)

**Date:** 2026-08-30 18:16:45 UTC
**Deployment Platform:** Cloud Run (Serverless GPU, Scale-to-Zero)
**Region:** europe-west4
**Hardware:** 1x nvidia-l4
**Cold Start Latency (0 -> 1 instance):** 2.94 s
**Notes:** Gemma 4 Edge 2.3B Serverless (1x L4)

## 1. Executive Summary
- **Pass Rate:** 60.0% (3/5)
- **Average Rubric Score:** 89.0 / 100
- **Average Latency:** 45.69 s
- **Output Throughput (Generation TPS):** 18.63 tok/s
- **Total Processing Throughput:** 62.27 tok/s
- **Total Token Usage:** 14225 tokens (Avg: 2845.0 tok/case)
- **Total Tool Invocations:** 5

## 2. Evaluation Scorecard Matrix

| Case ID | Case Name | Rubric Score | Grounding | Status | Latency | Gen TPS | Total Tokens | Tool Calls |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| CASE-01-LOKIBOT-C2 | Lokibot C2 Malware Beaconing Triage | 75.0/100 | 1.00 | FAIL | 42.97s | 18.17 tok/s | 2807 | 1 |
| CASE-02-RFC5737-BENIGN-IP | RFC-5737 Documentation IP Enrichment (Grounding Test) | 100.0/100 | 1.00 | PASS | 28.75s | 17.81 tok/s | 2475 | 1 |
| CASE-03-PHISHING-CRED-HARVEST | Phishing Alert & Entity Investigation | 95.0/100 | 1.00 | PASS | 51.80s | 18.63 tok/s | 2964 | 1 |
| CASE-04-DUPLICATE-SOAR-CASE | Duplicate SOAR Case Detection | 100.0/100 | 0.00 | PASS | 53.11s | 18.96 tok/s | 2976 | 1 |
| CASE-05-RANSOMWARE-ESCALATION | Critical Ransomware Containment Escalation | 75.0/100 | 0.90 | FAIL | 51.81s | 19.15 tok/s | 3003 | 1 |