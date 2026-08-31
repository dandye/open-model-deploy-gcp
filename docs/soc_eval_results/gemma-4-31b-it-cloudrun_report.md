# SOC Evaluation Report: gemma-4-31b-it (Cloud Run Serverless GPU)

**Date:** 2026-08-29 15:41:50 UTC
**Deployment Platform:** Cloud Run (Serverless GPU, Scale-to-Zero)
**Region:** europe-west4
**Hardware:** 1x nvidia-rtx-pro-6000
**Cold Start Latency (0 -> 1 instance):** 8.50 s
**Notes:** Gemma 4 31B Multimodal Reasoner (1x RTX PRO 6000 96GB)

## 1. Executive Summary
- **Pass Rate:** 80.0% (4/5)
- **Average Rubric Score:** 88.0 / 100
- **Average Latency:** 10.5 s
- **Output Throughput (Generation TPS):** 55.0 tok/s
- **Total Processing Throughput:** 180.0 tok/s
- **Total Token Usage:** 12000 tokens (Avg: 2400.0 tok/case)
- **Total Tool Invocations:** 6

## 2. Evaluation Scorecard Matrix

| Case ID | Case Name | Rubric Score | Grounding | Status | Latency | Gen TPS | Total Tokens | Tool Calls |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |