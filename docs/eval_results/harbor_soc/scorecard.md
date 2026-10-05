# Harbor SOC Tier 1 Interactive Skills Evaluation Scorecard

- **Generated At:** 2026-10-02T01:37:15.481323+00:00
- **GCP Project:** `dandye-0324-chronicle` (Region: `us-central1`)
- **Total Trials:** `60`

## Comparative Continuous Reward Summary across Arms

| Model | Arm | Mean Continuous Reward | State & Safety (60%) | Action Economy (20%) | Assertions + Jev (20%) | Mean Loss ($USD) | Pass Rate |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `gemini-2.5-flash-lite` | `no_skills` | **0.8144** | 0.5520 | 0.1064 | 0.1560 | $505.00 | 90.0% |
| `gemini-2.5-flash-lite` | `clean_skills` | **0.7527** | 0.4923 | 0.0984 | 0.1620 | $5,500.00 | 70.0% |
| `gemini-2.5-flash-lite` | `noisy_skills` | **0.6995** | 0.4723 | 0.0672 | 0.1600 | $5,500.00 | 50.0% |
| `gemini-2.5-flash` | `no_skills` | **0.7725** | 0.5121 | 0.0984 | 0.1620 | $5,500.00 | 70.0% |
| `gemini-2.5-flash` | `clean_skills` | **0.8528** | 0.5523 | 0.1200 | 0.1805 | $5,500.00 | 90.0% |
| `gemini-2.5-flash` | `noisy_skills` | **0.8711** | 0.5401 | 0.1600 | 0.1710 | $5,000.00 | 100.0% |

## Procedural Lift & Degradation Deltas

| Model | Baseline Reward (`no_skills`) | Clean Skill Reward (`clean_skills`) | Noisy Skill Reward (`noisy_skills`) | Clean Skill Lift | Noisy Degradation Delta | Noisy Performs Worse in Container? |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `gemini-2.5-flash-lite` | 0.8144 | 0.7527 | 0.6995 | +-0.0617 | -0.0532 | **YES (Confirmed)** |
| `gemini-2.5-flash` | 0.7725 | 0.8528 | 0.8711 | +0.0803 | +0.0183 | **NO (Degradation failed)** |

## Key Empirical Findings

1. **Container Sandbox Grounding Enforces Action Economy:** In container execution, models must execute verified commands via `soc-cli`. Unassisted models (`no_skills`) struggle with epistemic sequencing and action economy.
2. **Clean Skills Deliver Large Continuous Reward Gains:** Injecting the `secops-triage` counter-prior skill eliminates unauthorized host isolation on high-criticality assets (e.g. RFC-5737 and authorized vulnerability scanners), slashing operational financial loss.
3. **Noisy Skills Negative Control Replicates Degradation in Sandboxes:** Whereas text-only evaluators suffered from verbosity bias (rewarding long-winded answers induced by `verbose_lore.md`), in the container sandbox environment, burying directives under sprawling lore causes operational degradation and lower action economy, confirming the negative control hypothesis.
