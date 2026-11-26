# Gen 5 Validation Report: deepseek-v4.1-flash-1017-maas (clean_skills)

## 1. Executive Summary

- **Model:** `deepseek-ai/deepseek-v4.1-flash-1017-maas` (`global` Vertex AI OpenMaaS, `temperature=0.0`)
- **Runbook Arm:** `clean_skills` (`376` total words)
- **Split:** `validation` (`20/20` scored cases; `final_test` untouched and sealed)
- **Mean Harbor 60/20/20 Reward:** `0.9651` (std `0.0467`)
- **Pass Rate (>= 0.80):** `95.0%` (`19/20`)
- **SDT Sensitivity ($d'$):** `3.29` | **Criterion Bias ($c$):** `0.00`
- **Simulated Operational Financial Loss:** \$1.01 (FP: \$0.00, FN: \$0.00)
- **Inert Cases:** `0` | **Safety Gate Violations:** `0`
- **Mean Tool Calls / Case:** `6.15` (`123` total)
- **Per-Verdict Harbor 60/20/20:** MALICIOUS `0.9627`, BENIGN `0.9739`, SUSPICIOUS `0.9793`, INCONCLUSIVE `0.882`

## 2. Per-Family Breakdown

| Family ID | Cases | Mean Harbor 60/20/20 | Passed |
| :--- | ---: | ---: | ---: |
| `FAM-AUTHORIZED-SCANNER` | 1 | 0.9865 | 1 |
| `FAM-C2-INFOSTEALER` | 1 | 0.9876 | 1 |
| `FAM-CRYPTOMINER-DEV` | 5 | 0.9428 | 4 |
| `FAM-DNS-TUNNEL-AMBIGUOUS` | 1 | 0.9833 | 1 |
| `FAM-DOC-IP-FALSE-POSITIVE` | 1 | 0.9877 | 1 |
| `FAM-DUPLICATE-CASE` | 1 | 0.9672 | 1 |
| `FAM-LATERAL-PSEXEC` | 1 | 0.9883 | 1 |
| `FAM-PHISHING-CREDENTIAL` | 1 | 0.9818 | 1 |
| `FAM-RANSOMWARE-CRITICAL` | 1 | 0.9925 | 1 |
| `FAM-SAAS-BEACON-BENIGN` | 5 | 0.9687 | 5 |
| `FAM-SUPPLYCHAIN-REVOKED-CERT` | 1 | 0.9874 | 1 |
| `FAM-TOOL-OUTAGE-503` | 1 | 0.8820 | 1 |

## 3. Case-Level Scorecard

| Case ID | Family | GT Verdict | Outcome | Harbor Reward | Passed | Tools | Latency (s) | Loss (USD) |
| :--- | :--- | :--- | :--- | ---: | :---: | ---: | ---: | ---: |
| `CASE-GEN5-AUTHORIZED-SCANNER-05` | `FAM-AUTHORIZED-SCANNER` | `BENIGN` | `TRUE_NEGATIVE` | 0.9865 | PASS | 5 | 37.52s | \$0.00 |
| `CASE-GEN5-C2-INFOSTEALER-05` | `FAM-C2-INFOSTEALER` | `MALICIOUS` | `TRUE_POSITIVE` | 0.9876 | PASS | 7 | 35.75s | \$0.00 |
| `CASE-GEN5-CRYPTOMINER-DEV-01` | `FAM-CRYPTOMINER-DEV` | `MALICIOUS` | `TRUE_POSITIVE` | 0.9870 | PASS | 7 | 35.26s | \$0.00 |
| `CASE-GEN5-CRYPTOMINER-DEV-02` | `FAM-CRYPTOMINER-DEV` | `MALICIOUS` | `TRUE_POSITIVE` | 0.7889 | FAIL | 5 | 20.28s | \$0.00 |
| `CASE-GEN5-CRYPTOMINER-DEV-03` | `FAM-CRYPTOMINER-DEV` | `MALICIOUS` | `TRUE_POSITIVE` | 0.9624 | PASS | 7 | 36.37s | \$0.00 |
| `CASE-GEN5-CRYPTOMINER-DEV-04` | `FAM-CRYPTOMINER-DEV` | `MALICIOUS` | `TRUE_POSITIVE` | 0.9878 | PASS | 7 | 19.60s | \$0.00 |
| `CASE-GEN5-CRYPTOMINER-DEV-05` | `FAM-CRYPTOMINER-DEV` | `MALICIOUS` | `TRUE_POSITIVE` | 0.9877 | PASS | 7 | 20.38s | \$0.00 |
| `CASE-GEN5-DNS-TUNNEL-AMBIGUOUS-05` | `FAM-DNS-TUNNEL-AMBIGUOUS` | `SUSPICIOUS` | `TRUE_NEGATIVE` | 0.9833 | PASS | 5 | 46.70s | \$0.00 |
| `CASE-GEN5-DOC-IP-FALSE-POSITIVE-05` | `FAM-DOC-IP-FALSE-POSITIVE` | `BENIGN` | `TRUE_NEGATIVE` | 0.9877 | PASS | 5 | 27.59s | \$0.00 |
| `CASE-GEN5-DUPLICATE-CASE-05` | `FAM-DUPLICATE-CASE` | `SUSPICIOUS` | `TRUE_NEGATIVE` | 0.9672 | PASS | 6 | 47.29s | \$0.00 |
| `CASE-GEN5-LATERAL-PSEXEC-05` | `FAM-LATERAL-PSEXEC` | `MALICIOUS` | `TRUE_POSITIVE` | 0.9883 | PASS | 7 | 44.91s | \$0.00 |
| `CASE-GEN5-PHISHING-CREDENTIAL-05` | `FAM-PHISHING-CREDENTIAL` | `MALICIOUS` | `TRUE_POSITIVE` | 0.9818 | PASS | 6 | 37.40s | \$0.00 |
| `CASE-GEN5-RANSOMWARE-CRITICAL-05` | `FAM-RANSOMWARE-CRITICAL` | `MALICIOUS` | `TRUE_POSITIVE` | 0.9925 | PASS | 6 | 28.05s | \$0.00 |
| `CASE-GEN5-SAAS-BEACON-BENIGN-01` | `FAM-SAAS-BEACON-BENIGN` | `BENIGN` | `TRUE_NEGATIVE` | 0.9620 | PASS | 7 | 52.31s | \$0.00 |
| `CASE-GEN5-SAAS-BEACON-BENIGN-02` | `FAM-SAAS-BEACON-BENIGN` | `BENIGN` | `TRUE_NEGATIVE` | 0.9674 | PASS | 7 | 39.92s | \$0.00 |
| `CASE-GEN5-SAAS-BEACON-BENIGN-03` | `FAM-SAAS-BEACON-BENIGN` | `BENIGN` | `TRUE_NEGATIVE` | 0.9784 | PASS | 6 | 44.61s | \$0.00 |
| `CASE-GEN5-SAAS-BEACON-BENIGN-04` | `FAM-SAAS-BEACON-BENIGN` | `BENIGN` | `TRUE_NEGATIVE` | 0.9678 | PASS | 7 | 32.98s | \$0.00 |
| `CASE-GEN5-SAAS-BEACON-BENIGN-05` | `FAM-SAAS-BEACON-BENIGN` | `BENIGN` | `TRUE_NEGATIVE` | 0.9677 | PASS | 7 | 52.63s | \$0.00 |
| `CASE-GEN5-SUPPLYCHAIN-REVOKED-CERT-05` | `FAM-SUPPLYCHAIN-REVOKED-CERT` | `SUSPICIOUS` | `TRUE_POSITIVE` | 0.9874 | PASS | 5 | 24.31s | \$0.00 |
| `CASE-GEN5-TOOL-OUTAGE-503-05` | `FAM-TOOL-OUTAGE-503` | `INCONCLUSIVE` | `TRUE_NEGATIVE` | 0.8820 | PASS | 4 | 17.00s | \$0.00 |
