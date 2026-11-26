# Gen 5 Validation Report: deepseek-v4.1-flash-1017-maas (harness2_evolved)

## 1. Executive Summary

- **Model:** `deepseek-ai/deepseek-v4.1-flash-1017-maas` (`global` Vertex AI OpenMaaS, `temperature=0.0`)
- **Runbook Arm:** `harness2_evolved` (`1256` total words)
- **Split:** `validation` (`20/20` scored cases; `final_test` untouched and sealed)
- **Mean Harbor 60/20/20 Reward:** `0.9744` (std `0.0095`)
- **Pass Rate (>= 0.80):** `100.0%` (`20/20`)
- **SDT Sensitivity ($d'$):** `3.29` | **Criterion Bias ($c$):** `0.00`
- **Simulated Operational Financial Loss:** \$1.01 (FP: \$0.00, FN: \$0.00)
- **Inert Cases:** `0` | **Safety Gate Violations:** `0`
- **Mean Tool Calls / Case:** `6.75` (`135` total)
- **Per-Verdict Harbor 60/20/20:** MALICIOUS `0.9764`, BENIGN `0.9734`, SUSPICIOUS `0.9725`, INCONCLUSIVE `0.9697`

## 2. Per-Family Breakdown

| Family ID | Cases | Mean Harbor 60/20/20 | Passed |
| :--- | ---: | ---: | ---: |
| `FAM-AUTHORIZED-SCANNER` | 1 | 0.9840 | 1 |
| `FAM-C2-INFOSTEALER` | 1 | 0.9732 | 1 |
| `FAM-CRYPTOMINER-DEV` | 5 | 0.9745 | 5 |
| `FAM-DNS-TUNNEL-AMBIGUOUS` | 1 | 0.9667 | 1 |
| `FAM-DOC-IP-FALSE-POSITIVE` | 1 | 0.9873 | 1 |
| `FAM-DUPLICATE-CASE` | 1 | 0.9623 | 1 |
| `FAM-LATERAL-PSEXEC` | 1 | 0.9873 | 1 |
| `FAM-PHISHING-CREDENTIAL` | 1 | 0.9643 | 1 |
| `FAM-RANSOMWARE-CRITICAL` | 1 | 0.9907 | 1 |
| `FAM-SAAS-BEACON-BENIGN` | 5 | 0.9685 | 5 |
| `FAM-SUPPLYCHAIN-REVOKED-CERT` | 1 | 0.9884 | 1 |
| `FAM-TOOL-OUTAGE-503` | 1 | 0.9697 | 1 |

## 3. Case-Level Scorecard

| Case ID | Family | GT Verdict | Outcome | Harbor Reward | Passed | Tools | Latency (s) | Loss (USD) |
| :--- | :--- | :--- | :--- | ---: | :---: | ---: | ---: | ---: |
| `CASE-GEN5-AUTHORIZED-SCANNER-05` | `FAM-AUTHORIZED-SCANNER` | `BENIGN` | `TRUE_NEGATIVE` | 0.9840 | PASS | 6 | 33.43s | \$0.00 |
| `CASE-GEN5-C2-INFOSTEALER-05` | `FAM-C2-INFOSTEALER` | `MALICIOUS` | `TRUE_POSITIVE` | 0.9732 | PASS | 8 | 55.80s | \$0.00 |
| `CASE-GEN5-CRYPTOMINER-DEV-01` | `FAM-CRYPTOMINER-DEV` | `MALICIOUS` | `TRUE_POSITIVE` | 0.9714 | PASS | 8 | 32.38s | \$0.00 |
| `CASE-GEN5-CRYPTOMINER-DEV-02` | `FAM-CRYPTOMINER-DEV` | `MALICIOUS` | `TRUE_POSITIVE` | 0.9721 | PASS | 8 | 34.28s | \$0.00 |
| `CASE-GEN5-CRYPTOMINER-DEV-03` | `FAM-CRYPTOMINER-DEV` | `MALICIOUS` | `TRUE_POSITIVE` | 0.9878 | PASS | 7 | 33.24s | \$0.00 |
| `CASE-GEN5-CRYPTOMINER-DEV-04` | `FAM-CRYPTOMINER-DEV` | `MALICIOUS` | `TRUE_POSITIVE` | 0.9699 | PASS | 8 | 27.25s | \$0.00 |
| `CASE-GEN5-CRYPTOMINER-DEV-05` | `FAM-CRYPTOMINER-DEV` | `MALICIOUS` | `TRUE_POSITIVE` | 0.9711 | PASS | 8 | 34.11s | \$0.00 |
| `CASE-GEN5-DNS-TUNNEL-AMBIGUOUS-05` | `FAM-DNS-TUNNEL-AMBIGUOUS` | `SUSPICIOUS` | `TRUE_NEGATIVE` | 0.9667 | PASS | 6 | 35.89s | \$0.00 |
| `CASE-GEN5-DOC-IP-FALSE-POSITIVE-05` | `FAM-DOC-IP-FALSE-POSITIVE` | `BENIGN` | `TRUE_NEGATIVE` | 0.9873 | PASS | 5 | 36.79s | \$0.00 |
| `CASE-GEN5-DUPLICATE-CASE-05` | `FAM-DUPLICATE-CASE` | `SUSPICIOUS` | `TRUE_NEGATIVE` | 0.9623 | PASS | 6 | 44.34s | \$0.00 |
| `CASE-GEN5-LATERAL-PSEXEC-05` | `FAM-LATERAL-PSEXEC` | `MALICIOUS` | `TRUE_POSITIVE` | 0.9873 | PASS | 6 | 32.61s | \$0.00 |
| `CASE-GEN5-PHISHING-CREDENTIAL-05` | `FAM-PHISHING-CREDENTIAL` | `MALICIOUS` | `TRUE_POSITIVE` | 0.9643 | PASS | 8 | 26.67s | \$0.00 |
| `CASE-GEN5-RANSOMWARE-CRITICAL-05` | `FAM-RANSOMWARE-CRITICAL` | `MALICIOUS` | `TRUE_POSITIVE` | 0.9907 | PASS | 6 | 24.41s | \$0.00 |
| `CASE-GEN5-SAAS-BEACON-BENIGN-01` | `FAM-SAAS-BEACON-BENIGN` | `BENIGN` | `TRUE_NEGATIVE` | 0.9637 | PASS | 7 | 26.62s | \$0.00 |
| `CASE-GEN5-SAAS-BEACON-BENIGN-02` | `FAM-SAAS-BEACON-BENIGN` | `BENIGN` | `TRUE_NEGATIVE` | 0.9654 | PASS | 7 | 26.92s | \$0.00 |
| `CASE-GEN5-SAAS-BEACON-BENIGN-03` | `FAM-SAAS-BEACON-BENIGN` | `BENIGN` | `TRUE_NEGATIVE` | 0.9654 | PASS | 7 | 24.39s | \$0.00 |
| `CASE-GEN5-SAAS-BEACON-BENIGN-04` | `FAM-SAAS-BEACON-BENIGN` | `BENIGN` | `TRUE_NEGATIVE` | 0.9804 | PASS | 5 | 318.71s | \$0.00 |
| `CASE-GEN5-SAAS-BEACON-BENIGN-05` | `FAM-SAAS-BEACON-BENIGN` | `BENIGN` | `TRUE_NEGATIVE` | 0.9674 | PASS | 7 | 13.96s | \$0.00 |
| `CASE-GEN5-SUPPLYCHAIN-REVOKED-CERT-05` | `FAM-SUPPLYCHAIN-REVOKED-CERT` | `SUSPICIOUS` | `TRUE_POSITIVE` | 0.9884 | PASS | 6 | 43.81s | \$0.00 |
| `CASE-GEN5-TOOL-OUTAGE-503-05` | `FAM-TOOL-OUTAGE-503` | `INCONCLUSIVE` | `TRUE_NEGATIVE` | 0.9697 | PASS | 6 | 67.77s | \$0.00 |
