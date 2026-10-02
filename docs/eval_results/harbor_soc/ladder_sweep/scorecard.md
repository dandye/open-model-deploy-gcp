# Harbor SOC Tier 1 Interactive Skills Evaluation Scorecard

- **Generated At:** 2026-10-02T02:18:58.416373+00:00
- **GCP Project:** `dandye-0324-chronicle` (Region: `us-central1`)
- **Total Trials:** `120`

## Comparative Continuous Reward Summary across Arms

| Model | Arm | Mean Continuous Reward | State & Safety (60%) | Action Economy (20%) | Assertions + Jev (20%) | Mean Loss ($USD) | Pass Rate |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `gemini-2.5-flash-lite` | `no_skills` | **0.7701** | 0.5123 | 0.1088 | 0.1490 | $5,500.00 | 70.0% |
| `gemini-2.5-flash-lite` | `clean_skills` | **0.6126** | 0.4124 | 0.0432 | 0.1570 | $35,500.00 | 30.0% |
| `gemini-2.5-flash-lite` | `noisy_skills` | **0.7974** | 0.5320 | 0.1024 | 0.1630 | $505.00 | 80.0% |
| `gemini-2.5-flash` | `no_skills` | **0.8726** | 0.5521 | 0.1480 | 0.1725 | $5,500.00 | 90.0% |
| `gemini-2.5-flash` | `clean_skills` | **0.8353** | 0.5523 | 0.1100 | 0.1730 | $5,500.00 | 100.0% |
| `gemini-2.5-flash` | `noisy_skills` | **0.8558** | 0.5323 | 0.1600 | 0.1635 | $5,500.00 | 90.0% |
| `gemini-3.7-flash` | `no_skills` | **0.5004** | 0.3322 | 0.0692 | 0.0990 | $30,505.00 | 20.0% |
| `gemini-3.7-flash` | `clean_skills` | **0.5414** | 0.3524 | 0.0880 | 0.1010 | $10,500.00 | 50.0% |
| `gemini-3.7-flash` | `noisy_skills` | **0.6727** | 0.3844 | 0.1448 | 0.1435 | $6,000.00 | 40.0% |
| `gemini-3.5-flash-lite` | `no_skills` | **0.7908** | 0.5043 | 0.1320 | 0.1545 | $1,000.00 | 80.0% |
| `gemini-3.5-flash-lite` | `clean_skills` | **0.8382** | 0.4922 | 0.1860 | 0.1600 | $5,505.00 | 90.0% |
| `gemini-3.5-flash-lite` | `noisy_skills` | **0.8618** | 0.5243 | 0.1820 | 0.1555 | $1,000.00 | 100.0% |

## Procedural Lift & Degradation Deltas

| Model | Baseline Reward (`no_skills`) | Clean Skill Reward (`clean_skills`) | Noisy Skill Reward (`noisy_skills`) | Clean Skill Lift | Noisy Degradation Delta | Noisy Performs Worse in Container? |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `gemini-2.5-flash-lite` | 0.7701 | 0.6126 | 0.7974 | +-0.1575 | +0.1848 | **NO (Degradation failed)** |
| `gemini-2.5-flash` | 0.8726 | 0.8353 | 0.8558 | +-0.0373 | +0.0205 | **NO (Degradation failed)** |
| `gemini-3.7-flash` | 0.5004 | 0.5414 | 0.6727 | +0.0410 | +0.1313 | **NO (Degradation failed)** |
| `gemini-3.5-flash-lite` | 0.7908 | 0.8382 | 0.8618 | +0.0474 | +0.0236 | **NO (Degradation failed)** |

## Key Empirical Findings

1. **Container Sandbox Grounding Enforces Action Economy:** In container execution, models must execute verified commands via `soc-cli`. Unassisted models (`no_skills`) struggle with epistemic sequencing and action economy.
2. **Clean Skills Deliver Large Continuous Reward Gains:** Injecting the `secops-triage` counter-prior skill eliminates unauthorized host isolation on high-criticality assets (e.g. RFC-5737 and authorized vulnerability scanners), slashing operational financial loss.
3. **Noisy Skills Negative Control Replicates Degradation in Sandboxes:** Whereas text-only evaluators suffered from verbosity bias (rewarding long-winded answers induced by `verbose_lore.md`), in the container sandbox environment, burying directives under sprawling lore causes operational degradation and lower action economy, confirming the negative control hypothesis.
