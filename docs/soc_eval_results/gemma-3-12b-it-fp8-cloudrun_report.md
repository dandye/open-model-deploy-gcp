# SOC Evaluation Report: gemma-3-12b-it-fp8 (Cloud Run Serverless GPU)

**Date:** 2026-08-30 18:02:42 UTC
**Deployment Platform:** Cloud Run (Serverless GPU, Scale-to-Zero)
**Region:** europe-west4
**Hardware:** 1x nvidia-l4
**Cold Start Latency (0 -> 1 instance):** 2.76 s
**Notes:** Gemma 3 12B FP8 Quantized (1x L4)

## 1. Executive Summary
- **Pass Rate:** 40.0% (2/5)
- **Average Rubric Score:** 76.0 / 100
- **Average Latency:** 98.77 s
- **Output Throughput (Generation TPS):** 7.9 tok/s
- **Total Processing Throughput:** 25.56 tok/s
- **Total Token Usage:** 12625 tokens (Avg: 2525.0 tok/case)
- **Total Tool Invocations:** 4

## 2. Evaluation Scorecard Matrix

| Case ID | Case Name | Rubric Score | Grounding | Status | Latency | Gen TPS | Total Tokens | Tool Calls |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| CASE-01-LOKIBOT-C2 | Lokibot C2 Malware Beaconing Triage | 55.0/100 | 0.50 | FAIL | 128.46s | 7.97 tok/s | 1935 | 0 |
| CASE-02-RFC5737-BENIGN-IP | RFC-5737 Documentation IP Enrichment (Grounding Test) | 100.0/100 | 1.00 | PASS | 43.81s | 7.3 tok/s | 2258 | 1 |
| CASE-03-PHISHING-CRED-HARVEST | Phishing Alert & Entity Investigation | 60.0/100 | 0.10 | FAIL | 129.81s | 7.99 tok/s | 2994 | 1 |
| CASE-04-DUPLICATE-SOAR-CASE | Duplicate SOAR Case Detection | 90.0/100 | 0.10 | PASS | 54.04s | 7.49 tok/s | 2355 | 1 |
| CASE-05-RANSOMWARE-ESCALATION | Critical Ransomware Containment Escalation | 75.0/100 | 1.00 | FAIL | 137.72s | 8.1 tok/s | 3083 | 1 |