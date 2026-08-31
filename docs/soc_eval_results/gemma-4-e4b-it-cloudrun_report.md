# SOC Evaluation Report: gemma-4-e4b-it (Cloud Run Serverless GPU)

**Date:** 2026-08-30 18:34:12 UTC
**Deployment Platform:** Cloud Run (Serverless GPU, Scale-to-Zero)
**Region:** europe-west4
**Hardware:** 1x nvidia-l4
**Cold Start Latency (0 -> 1 instance):** 2.72 s
**Notes:** Gemma 4 Edge 4.5B Serverless (1x L4)

## 1. Executive Summary
- **Pass Rate:** 80.0% (4/5)
- **Average Rubric Score:** 93.6 / 100
- **Average Latency:** 54.55 s
- **Output Throughput (Generation TPS):** 15.81 tok/s
- **Total Processing Throughput:** 61.27 tok/s
- **Total Token Usage:** 16712 tokens (Avg: 3342.4 tok/case)
- **Total Tool Invocations:** 7

## 2. Evaluation Scorecard Matrix

| Case ID | Case Name | Rubric Score | Grounding | Status | Latency | Gen TPS | Total Tokens | Tool Calls |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| CASE-01-LOKIBOT-C2 | Lokibot C2 Malware Beaconing Triage | 95.0/100 | 1.00 | PASS | 67.25s | 16.06 tok/s | 3120 | 1 |
| CASE-02-RFC5737-BENIGN-IP | RFC-5737 Documentation IP Enrichment (Grounding Test) | 100.0/100 | 1.00 | PASS | 35.55s | 15.56 tok/s | 2523 | 1 |
| CASE-03-PHISHING-CRED-HARVEST | Phishing Alert & Entity Investigation | 75.0/100 | 0.50 | FAIL | 67.48s | 16.18 tok/s | 3053 | 1 |
| CASE-04-DUPLICATE-SOAR-CASE | Duplicate SOAR Case Detection | 100.0/100 | 1.00 | PASS | 49.40s | 15.41 tok/s | 4023 | 2 |
| CASE-05-RANSOMWARE-ESCALATION | Critical Ransomware Containment Escalation | 98.0/100 | 1.00 | PASS | 53.07s | 15.58 tok/s | 3993 | 2 |