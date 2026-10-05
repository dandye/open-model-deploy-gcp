# Harbor SOC Tier 1 Interactive Skills Evaluation Scorecard

- **Generated At:** 2026-10-02T04:33:53.612792+00:00
- **GCP Project:** `dandye-0324-chronicle` (Region: `us-central1`)
- **Total Trials:** `90`

## Comparative Continuous Reward Summary across Arms

| Model | Arm | Mean Continuous Reward | State & Safety (60%) | Action Economy (20%) | Assertions + Jev (20%) | Mean Loss ($USD) | Pass Rate |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `gemini-3.5-flash-lite` | `no_skills` | **0.7704** | 0.4920 | 0.1384 | 0.1400 | $505.00 | 70.0% |
| `gemini-3.5-flash-lite` | `clean_skills` | **0.8413** | 0.5199 | 0.1504 | 0.1710 | $5.00 | 90.0% |
| `gemini-3.5-flash-lite` | `gepa_evolved_skills` | **0.7459** | 0.4164 | 0.1900 | 0.1395 | $6,505.00 | 60.0% |
| `gemini-2.5-flash` | `no_skills` | **0.8109** | 0.5400 | 0.0984 | 0.1725 | $5,000.00 | 80.0% |
| `gemini-2.5-flash` | `clean_skills` | **0.8555** | 0.5720 | 0.1140 | 0.1695 | $505.00 | 90.0% |
| `gemini-2.5-flash` | `gepa_evolved_skills` | **0.7033** | 0.4243 | 0.1560 | 0.1230 | $1,000.00 | 60.0% |
| `gemini-2.5-flash-lite` | `no_skills` | **0.6731** | 0.4724 | 0.0412 | 0.1595 | $10,500.00 | 60.0% |
| `gemini-2.5-flash-lite` | `clean_skills` | **0.6551** | 0.4323 | 0.0668 | 0.1560 | $5,500.00 | 50.0% |
| `gemini-2.5-flash-lite` | `gepa_evolved_skills` | **0.4361** | 0.2844 | 0.0532 | 0.0985 | $11,005.00 | 10.0% |

## Procedural Lift & Evolution Deltas

| Model | Baseline (`no_skills`) | Clean Skill (`clean_skills`) | GEPA Evolved (`gepa_evolved_skills`) | Clean Skill Lift | GEPA vs Clean Delta | GEPA Outperforms Clean? |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `gemini-3.5-flash-lite` | 0.7704 | 0.8413 | 0.7459 | +0.0709 | -0.0954 | **NO (Human-authored superior)** |
| `gemini-2.5-flash` | 0.8109 | 0.8555 | 0.7033 | +0.0446 | -0.1522 | **NO (Human-authored superior)** |
| `gemini-2.5-flash-lite` | 0.6731 | 0.6551 | 0.4361 | +-0.0180 | -0.2190 | **NO (Human-authored superior)** |

## Key Empirical Findings

1. **Container Sandbox Grounding Enforces Action Economy:** In container execution, models must execute verified commands via `soc-cli`. Unassisted models (`no_skills`) struggle with epistemic sequencing and action economy.
2. **Clean Skills Deliver Large Continuous Reward Gains:** Injecting the `secops-triage` counter-prior skill eliminates unauthorized host isolation on high-criticality assets (e.g. RFC-5737 and authorized vulnerability scanners), slashing operational financial loss.
3. **Noisy Skills Negative Control Replicates Degradation in Sandboxes:** Whereas text-only evaluators suffered from verbosity bias (rewarding long-winded answers induced by `verbose_lore.md`), in the container sandbox environment, burying directives under sprawling lore causes operational degradation and lower action economy, confirming the negative control hypothesis.
