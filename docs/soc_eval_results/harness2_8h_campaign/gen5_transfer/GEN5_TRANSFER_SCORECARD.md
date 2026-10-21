# Gen 5 Tier 1 Cross-Model Transfer & Cost Staircase Scorecard

- **Run ID**: `20261020T092042Z-88248e1f`
- **Split**: Gen 5 `validation` (`20` cases)
- **Harness Composite SHA-256**: `038639ae9c6839146f0ecad07b0ecfc6c48ea47b8a49d507c7dab237619218df`

## 1. Cross-Model Transfer Matrix (3 Models x 3 Runbook Arms)

| Model | Runbook Arm | Words | Harbor 60/20/20 | GEPA Fitness | MALICIOUS | BENIGN | SUSPICIOUS | INCONCLUSIVE | $d'$ | $c$ | Total Loss (USD) | Mean Tools | Token Cost (USD) |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `gemini-2.5-flash-lite` | `seed_runbooks` | 3648 | **0.9684** | 0.9524 | 0.9503 | 0.9827 | 0.9834 | 0.9850 | 2.56 | -0.06 | \$50,251.32 | 6.35 | \$0.0990 |
| `gemini-2.5-flash-lite` | `gepa_single_proposer` | 1988 | **0.9784** | 0.9624 | 0.9726 | 0.9827 | 0.9834 | 0.9850 | 2.56 | -0.06 | \$50,251.37 | 6.50 | \$0.1027 |
| `gemini-2.5-flash-lite` | `harness2_k2_evolved` | 1743 | **0.9840** | 0.9840 | 0.9850 | 0.9827 | 0.9834 | 0.9850 | 2.91 | -0.23 | \$251.02 | 5.60 | \$0.0716 |
| `gemini-2.5-flash` | `seed_runbooks` | 3648 | **0.9723** | 0.9563 | 0.9850 | 0.9850 | 0.9005 | 0.9850 | 2.91 | -0.23 | \$250.94 | 5.00 | \$0.2017 |
| `gemini-2.5-flash` | `gepa_single_proposer` | 1988 | **0.9751** | 0.9591 | 0.9850 | 0.9850 | 0.9188 | 0.9850 | 2.91 | -0.23 | \$50,000.91 | 4.95 | \$0.1943 |
| `gemini-2.5-flash` | `harness2_k2_evolved` | 1743 | **0.9723** | 0.9723 | 0.9850 | 0.9850 | 0.9005 | 0.9850 | 2.49 | -0.40 | \$5,250.87 | 5.10 | \$0.1809 |
| `gemini-3.5-flash-lite` | `seed_runbooks` | 3648 | **0.9825** | 0.9665 | 0.9850 | 0.9850 | 0.9683 | 0.9850 | 3.27 | -0.10 | \$0.93 | 5.25 | \$0.0568 |
| `gemini-3.5-flash-lite` | `gepa_single_proposer` | 1988 | **0.9825** | 0.9665 | 0.9850 | 0.9850 | 0.9683 | 0.9850 | 3.27 | -0.10 | \$0.93 | 5.25 | \$0.0587 |
| `gemini-3.5-flash-lite` | `harness2_k2_evolved` | 1743 | **0.9848** | 0.9848 | 0.9850 | 0.9850 | 0.9834 | 0.9850 | 3.27 | -0.10 | \$0.84 | 5.20 | \$0.0502 |

## 2. 3-Model Aggregate Summary by Runbook Arm

| Runbook Arm | Total Words | Mean Harbor 60/20/20 | Mean GEPA Fitness | Mean $d'$ | Mean Total Loss (USD) | Mean Tools | Total Safety Violations |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `seed_runbooks` | 3648 | **0.9744** | 0.9584 | 2.91 | \$16,834.40 | 5.53 | 0 |
| `gepa_single_proposer` | 1988 | **0.9787** | 0.9627 | 2.91 | \$33,417.74 | 5.57 | 0 |
| `harness2_k2_evolved` | 1743 | **0.9804** | 0.9804 | 2.89 | \$1,834.24 | 5.30 | 0 |

## 3. Per-Runbook Component Breakdown (`harness2_k2_evolved` vs `seed_runbooks`)

| Model | Arm | `basic_ioc_enrichment.md` | `malware_triage.md` | `suspicious_login_triage.md` | `lateral_movement_hunt_psexec_wmi.md` |
| :--- | :--- | ---: | ---: | ---: | ---: |
| `gemini-2.5-flash-lite` | `seed_runbooks` | 0.9833 | 0.9690 | frozen (train-only) | 0.7850 |
| `gemini-2.5-flash-lite` | `gepa_single_proposer` | 0.9833 | 0.9690 | frozen (train-only) | 0.9850 |
| `gemini-2.5-flash-lite` | `harness2_k2_evolved` | 0.9833 | 0.9850 | frozen (train-only) | 0.9850 |
| `gemini-2.5-flash` | `seed_runbooks` | 0.9639 | 0.9850 | frozen (train-only) | 0.9850 |
| `gemini-2.5-flash` | `gepa_single_proposer` | 0.9684 | 0.9850 | frozen (train-only) | 0.9850 |
| `gemini-2.5-flash` | `harness2_k2_evolved` | 0.9639 | 0.9850 | frozen (train-only) | 0.9850 |
| `gemini-3.5-flash-lite` | `seed_runbooks` | 0.9808 | 0.9850 | frozen (train-only) | 0.9850 |
| `gemini-3.5-flash-lite` | `gepa_single_proposer` | 0.9808 | 0.9850 | frozen (train-only) | 0.9850 |
| `gemini-3.5-flash-lite` | `harness2_k2_evolved` | 0.9846 | 0.9850 | frozen (train-only) | 0.9850 |

## 4. Cost Staircase Walk (`harness2_k2_evolved` on Gen 5 `validation`)

- **Ceiling Model**: `gemini-2.5-flash` (`0.9723`)
- **Selected Most Cost-Effective Model**: `gemini-2.5-flash-lite` (`0.9840`, tolerance `0.05`)

| Rung Model Tier | Mean Score | Min Loss Penalty | Passed Safety | Within Tolerance | Tokens In | Tokens Out | Mean Latency (ms) |
| :--- | ---: | ---: | :---: | :---: | ---: | ---: | ---: |
| `gemini-2.5-flash` | **0.9723** | 1.00 | True | True | 305348 | 35720 | 22011.0 |
| `gemini-3.5-flash-lite` | **0.9848** | 1.00 | True | True | 326151 | 43928 | 9132.0 |
| `gemini-2.5-flash-lite` | **0.9840** | 1.00 | True | True | 369227 | 86655 | 19500.0 |
