# SOC Evaluation Report: gemma-3-1b-it [DEPRECATED]

> [!WARNING]
> **DEPRECATED / SUPERSEDED**:
> This report reflects initial Phase 1 testing using a prescriptive ("spoiled") system prompt. It is superseded by the un-spoiled evaluation standard documented in [`../soc_model_comparative_evals.md`](../soc_model_comparative_evals.md).

**Date:** 2026-08-25 19:11:59 UTC


## Summary
- **Pass Rate:** 20.0%
- **Average Rubric Score:** 64.0/100
- **Average Latency:** 12.76 s

## Detailed Case Breakdown

| Case ID | Case Name | Rubric Score | Grounding | Status | Latency |
| :--- | :--- | :--- | :--- | :--- | :--- |
| CASE-01-LOKIBOT-C2 | Lokibot C2 Malware Beaconing Triage | 55.0/100 | 0.20 | FAIL | 14.32s |
| CASE-02-RFC5737-BENIGN-IP | RFC-5737 Documentation IP Enrichment (Grounding Test) | 100.0/100 | 1.00 | PASS | 9.46s |
| CASE-03-PHISHING-CRED-HARVEST | Phishing Alert & Entity Investigation | 70.0/100 | 0.50 | FAIL | 13.19s |
| CASE-04-DUPLICATE-SOAR-CASE | Duplicate SOAR Case Detection | 20.0/100 | 0.20 | FAIL | 13.27s |
| CASE-05-RANSOMWARE-ESCALATION | Critical Ransomware Containment Escalation | 75.0/100 | 0.20 | FAIL | 13.56s |
