# SOC Evaluation Report: gemini-2.5-flash-baseline [DEPRECATED]

> [!WARNING]
> **DEPRECATED / SUPERSEDED**:
> This baseline report reflects early Phase 1 testing with a prescriptive ("spoiled") system prompt that hardcoded alert cheat sheets. It is superseded by the un-spoiled benchmark report in [`gemini_2_5_flash_report.md`](gemini_2_5_flash_report.md) and [`../soc_model_comparative_evals.md`](../soc_model_comparative_evals.md).

**Date:** 2026-08-25 18:50:30 UTC


## Summary
- **Pass Rate:** 100.0%
- **Average Rubric Score:** 97.0/100
- **Average Latency:** 19.21 s

## Detailed Case Breakdown

| Case ID | Case Name | Rubric Score | Grounding | Status | Latency |
| :--- | :--- | :--- | :--- | :--- | :--- |
| CASE-01-LOKIBOT-C2 | Lokibot C2 Malware Beaconing Triage | 90.0/100 | 1.00 | PASS | 17.97s |
| CASE-02-RFC5737-BENIGN-IP | RFC-5737 Documentation IP Enrichment (Grounding Test) | 100.0/100 | 1.00 | PASS | 22.96s |
| CASE-03-PHISHING-CRED-HARVEST | Phishing Alert & Entity Investigation | 95.0/100 | 0.80 | PASS | 19.66s |
| CASE-04-DUPLICATE-SOAR-CASE | Duplicate SOAR Case Detection | 100.0/100 | 1.00 | PASS | 14.84s |
| CASE-05-RANSOMWARE-ESCALATION | Critical Ransomware Containment Escalation | 100.0/100 | 1.00 | PASS | 20.60s |
