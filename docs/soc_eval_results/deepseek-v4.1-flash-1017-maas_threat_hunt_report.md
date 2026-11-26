# Track 2 Proactive Threat Hunting: Multi-Model x 3-Arm Evaluation Scorecard

- **Generated At**: `2026-11-26T02:57:26Z`
- **Campaign Reference**: `Unwrapping Ursnif's Gifts (alienvault_63bbee81b55c8ba00724605a / report--22-00022539)` (`alienvault_63bbee81b55c8ba00724605a` / `superstarts.top`)
- **Suite**: `configs/evals/hunt/ursnif_gti_hunt_suite.json` (4 scenarios)
- **Models Evaluated**: `1` (`deepseek-ai/deepseek-v4.1-flash-1017-maas`)
- **Total Trajectories Executed**: `8`

## 1. Aggregate Performance by Model and Runbook Arm

| Model | Arm | Mean Hunt Composite | Mean Harbor (60/20/20) | Verdict Acc | 168h Widening Rate | LOLBin Safe Rate | Rel-Loop Exhaustion | Mean Epistemic Steps | Mean Latency (s) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `deepseek-ai/deepseek-v4.1-flash-1017-maas` | `compressed_track_b_hunt` | **0.9812** | `0.9400` | `100%` | `100%` | `100%` | `0%` | `7.8` | `86.3s` |
| `deepseek-ai/deepseek-v4.1-flash-1017-maas` | `harness2_evolved_hunt` | **1.0000** | `0.9440` | `100%` | `100%` | `100%` | `0%` | `7.5` | `85.3s` |

## 2. Overall Summary by Runbook Arm (Averaged Across All Models)

| Runbook Arm | Description | Mean Hunt Composite | Mean Harbor (60/20/20) | Verdict Acc | 168h Widening Rate | LOLBin Safe Rate | Rel-Loop Exhaustion |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `compressed_track_b_hunt` | Compressed Track 2 `configs/runbooks/gti_collection_threat_hunt.md` (`350` words, 72h->168h widening, second-hop pivot, LOLBin guard) | **0.9812** | `0.9400` | `100%` | `100%` | `100%` | `0%` |
| `harness2_evolved_hunt` | Harness^2 Evolved Track 2 `gti_collection_threat_hunt.md` (`INV`/`DOM`/`COMPOSED`, dual-hash `get_file_report` verification, 503 SOAR `list_cases` pivot) | **1.0000** | `0.9440` | `100%` | `100%` | `100%` | `0%` |

## 3. Scenario-Level Breakdown Across Models and Arms

| Scenario ID | Model | Arm | Expected | Actual | Hunt Composite | Harbor Reward | 168h Widened | LOLBin Verified | Patient Zero Found | Executed Actions |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `HUNT-URSNIF-COLLECTION-01` | `deepseek-ai/deepseek-v4.1-flash-1017-maas` | `compressed_track_b_hunt` | `MALICIOUS` | `MALICIOUS` | **1.0000** | `0.9360` | `True` | `True` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-URSNIF-DOMAIN-PIVOT-02` | `deepseek-ai/deepseek-v4.1-flash-1017-maas` | `compressed_track_b_hunt` | `MALICIOUS` | `MALICIOUS` | **1.0000** | `0.9360` | `True` | `True` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-CLEAN-COUNTERFACTUAL-03` | `deepseek-ai/deepseek-v4.1-flash-1017-maas` | `compressed_track_b_hunt` | `BENIGN` | `BENIGN` | **0.9250** | `0.9360` | `True` | `True` | `False` | `update_case_comment, close_case` |
| `HUNT-DEGRADED-503-04` | `deepseek-ai/deepseek-v4.1-flash-1017-maas` | `compressed_track_b_hunt` | `INCONCLUSIVE` | `INCONCLUSIVE` | **1.0000** | `0.9520` | `False` | `False` | `False` | `update_case_comment` |
| `HUNT-URSNIF-COLLECTION-01` | `deepseek-ai/deepseek-v4.1-flash-1017-maas` | `harness2_evolved_hunt` | `MALICIOUS` | `MALICIOUS` | **1.0000** | `0.9360` | `True` | `True` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-URSNIF-DOMAIN-PIVOT-02` | `deepseek-ai/deepseek-v4.1-flash-1017-maas` | `harness2_evolved_hunt` | `MALICIOUS` | `MALICIOUS` | **1.0000** | `0.9360` | `True` | `True` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-CLEAN-COUNTERFACTUAL-03` | `deepseek-ai/deepseek-v4.1-flash-1017-maas` | `harness2_evolved_hunt` | `BENIGN` | `BENIGN` | **1.0000** | `0.9360` | `True` | `True` | `False` | `update_case_comment, close_case` |
| `HUNT-DEGRADED-503-04` | `deepseek-ai/deepseek-v4.1-flash-1017-maas` | `harness2_evolved_hunt` | `INCONCLUSIVE` | `INCONCLUSIVE` | **1.0000** | `0.9680` | `False` | `False` | `False` | `update_case_comment` |
