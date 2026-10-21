# Track 2 Proactive Threat Hunting: Multi-Model x 3-Arm Evaluation Scorecard

- **Generated At**: `2026-10-20T06:49:44Z`
- **Campaign Reference**: `Unwrapping Ursnif's Gifts (alienvault_63bbee81b55c8ba00724605a / report--22-00022539)` (`alienvault_63bbee81b55c8ba00724605a` / `superstarts.top`)
- **Suite**: `configs/evals/hunt/ursnif_gti_hunt_suite.json` (4 scenarios)
- **Models Evaluated**: `3` (`gemini-2.5-flash-lite, gemini-2.5-flash, gemini-3.5-flash-lite`)
- **Total Trajectories Executed**: `48`

## 1. Aggregate Performance by Model and Runbook Arm

| Model | Arm | Mean Hunt Composite | Mean Harbor (60/20/20) | Verdict Acc | 168h Widening Rate | LOLBin Safe Rate | Rel-Loop Exhaustion | Mean Epistemic Steps | Mean Latency (s) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `gemini-2.5-flash-lite` | `no_runbook` | **0.7696** | `0.8272` | `100%` | `0%` | `100%` | `0%` | `5.2` | `55.9s` |
| `gemini-2.5-flash-lite` | `raw_clinerules_hunt` | **0.7456** | `0.8190` | `100%` | `33%` | `100%` | `0%` | `5.5` | `70.2s` |
| `gemini-2.5-flash-lite` | `compressed_track_b_hunt` | **0.9094** | `0.8902` | `100%` | `100%` | `100%` | `0%` | `5.5` | `41.2s` |
| `gemini-2.5-flash-lite` | `harness2_evolved_hunt` | **1.0000** | `0.9560` | `100%` | `100%` | `100%` | `0%` | `6.5` | `43.2s` |
| `gemini-2.5-flash` | `no_runbook` | **0.8248** | `0.8196` | `75%` | `67%` | `100%` | `0%` | `5.0` | `38.8s` |
| `gemini-2.5-flash` | `raw_clinerules_hunt` | **0.7523** | `0.7896` | `75%` | `33%` | `100%` | `0%` | `6.2` | `33.1s` |
| `gemini-2.5-flash` | `compressed_track_b_hunt` | **0.9719** | `0.9640` | `100%` | `100%` | `100%` | `0%` | `6.0` | `39.2s` |
| `gemini-2.5-flash` | `harness2_evolved_hunt` | **0.9719** | `0.9560` | `100%` | `100%` | `100%` | `0%` | `6.2` | `43.5s` |
| `gemini-3.5-flash-lite` | `no_runbook` | **0.9719** | `0.9550` | `100%` | `100%` | `100%` | `0%` | `5.0` | `15.7s` |
| `gemini-3.5-flash-lite` | `raw_clinerules_hunt` | **0.9906** | `0.9640` | `100%` | `100%` | `100%` | `0%` | `6.0` | `23.3s` |
| `gemini-3.5-flash-lite` | `compressed_track_b_hunt` | **0.9719** | `0.9470` | `100%` | `100%` | `100%` | `0%` | `5.5` | `20.8s` |
| `gemini-3.5-flash-lite` | `harness2_evolved_hunt` | **0.9719** | `0.9640` | `100%` | `100%` | `100%` | `0%` | `6.0` | `20.2s` |

## 2. Overall Summary by Runbook Arm (Averaged Across All Models)

| Runbook Arm | Description | Mean Hunt Composite | Mean Harbor (60/20/20) | Verdict Acc | 168h Widening Rate | LOLBin Safe Rate | Rel-Loop Exhaustion |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `no_runbook` | Zero procedural runbook (`use_runbooks=False`) | **0.8554** | `0.8673` | `92%` | `56%` | `100%` | `0%` |
| `raw_clinerules_hunt` | Raw upstream `.clinerules/run_books/investigate_a_gti_collection_id.md` (`1,100+` words, Mermaid, `${COLLECTION_ID}`, 13-rel loop) | **0.8295** | `0.8575` | `92%` | `56%` | `100%` | `0%` |
| `compressed_track_b_hunt` | Compressed Track 2 `configs/runbooks/gti_collection_threat_hunt.md` (`350` words, 72h->168h widening, second-hop pivot, LOLBin guard) | **0.9510** | `0.9337` | `100%` | `100%` | `100%` | `0%` |
| `harness2_evolved_hunt` | Harness^2 Evolved Track 2 `gti_collection_threat_hunt.md` (`INV`/`DOM`/`COMPOSED`, dual-hash `get_file_report` verification, 503 SOAR `list_cases` pivot) | **0.9813** | `0.9587` | `100%` | `100%` | `100%` | `0%` |

## 3. Scenario-Level Breakdown Across Models and Arms

| Scenario ID | Model | Arm | Expected | Actual | Hunt Composite | Harbor Reward | 168h Widened | LOLBin Verified | Patient Zero Found | Executed Actions |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `HUNT-URSNIF-COLLECTION-01` | `gemini-2.5-flash-lite` | `no_runbook` | `MALICIOUS` | `MALICIOUS` | **0.5200** | `0.6510` | `False` | `False` | `False` | `block_indicator, update_case_comment` |
| `HUNT-URSNIF-DOMAIN-PIVOT-02` | `gemini-2.5-flash-lite` | `no_runbook` | `MALICIOUS` | `MALICIOUS` | **0.6583** | `0.7217` | `False` | `False` | `False` | `block_indicator, update_case_comment` |
| `HUNT-CLEAN-COUNTERFACTUAL-03` | `gemini-2.5-flash-lite` | `no_runbook` | `BENIGN` | `BENIGN` | **0.9000** | `0.9360` | `False` | `True` | `False` | `close_case, update_case_comment` |
| `HUNT-DEGRADED-503-04` | `gemini-2.5-flash-lite` | `no_runbook` | `INCONCLUSIVE` | `INCONCLUSIVE` | **1.0000** | `1.0000` | `False` | `False` | `False` | `update_case_comment` |
| `HUNT-URSNIF-COLLECTION-01` | `gemini-2.5-flash-lite` | `raw_clinerules_hunt` | `MALICIOUS` | `MALICIOUS` | **0.5200** | `0.6510` | `False` | `False` | `False` | `block_indicator, update_case_comment` |
| `HUNT-URSNIF-DOMAIN-PIVOT-02` | `gemini-2.5-flash-lite` | `raw_clinerules_hunt` | `MALICIOUS` | `MALICIOUS` | **0.9625** | `0.9680` | `True` | `False` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-CLEAN-COUNTERFACTUAL-03` | `gemini-2.5-flash-lite` | `raw_clinerules_hunt` | `BENIGN` | `BENIGN` | **0.7500** | `0.9520` | `False` | `False` | `False` | `close_case, update_case_comment` |
| `HUNT-DEGRADED-503-04` | `gemini-2.5-flash-lite` | `raw_clinerules_hunt` | `INCONCLUSIVE` | `INCONCLUSIVE` | **0.7500** | `0.7050` | `False` | `False` | `False` | `none` |
| `HUNT-URSNIF-COLLECTION-01` | `gemini-2.5-flash-lite` | `compressed_track_b_hunt` | `MALICIOUS` | `MALICIOUS` | **1.0000** | `0.9360` | `True` | `True` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-URSNIF-DOMAIN-PIVOT-02` | `gemini-2.5-flash-lite` | `compressed_track_b_hunt` | `MALICIOUS` | `MALICIOUS` | **0.9625** | `0.9520` | `True` | `False` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-CLEAN-COUNTERFACTUAL-03` | `gemini-2.5-flash-lite` | `compressed_track_b_hunt` | `BENIGN` | `BENIGN` | **0.9250** | `0.9680` | `True` | `False` | `False` | `close_case, update_case_comment` |
| `HUNT-DEGRADED-503-04` | `gemini-2.5-flash-lite` | `compressed_track_b_hunt` | `INCONCLUSIVE` | `INCONCLUSIVE` | **0.7500** | `0.7050` | `False` | `False` | `False` | `none` |
| `HUNT-URSNIF-COLLECTION-01` | `gemini-2.5-flash-lite` | `harness2_evolved_hunt` | `MALICIOUS` | `MALICIOUS` | **1.0000** | `0.9360` | `True` | `True` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-URSNIF-DOMAIN-PIVOT-02` | `gemini-2.5-flash-lite` | `harness2_evolved_hunt` | `MALICIOUS` | `MALICIOUS` | **1.0000** | `0.9360` | `True` | `True` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-CLEAN-COUNTERFACTUAL-03` | `gemini-2.5-flash-lite` | `harness2_evolved_hunt` | `BENIGN` | `BENIGN` | **1.0000** | `0.9520` | `True` | `True` | `False` | `update_case_comment, close_case` |
| `HUNT-DEGRADED-503-04` | `gemini-2.5-flash-lite` | `harness2_evolved_hunt` | `INCONCLUSIVE` | `INCONCLUSIVE` | **1.0000** | `1.0000` | `False` | `False` | `False` | `update_case_comment` |
| `HUNT-URSNIF-COLLECTION-01` | `gemini-2.5-flash` | `no_runbook` | `MALICIOUS` | `INCONCLUSIVE` | **0.3700** | `0.4003` | `False` | `False` | `False` | `update_case_comment` |
| `HUNT-URSNIF-DOMAIN-PIVOT-02` | `gemini-2.5-flash` | `no_runbook` | `MALICIOUS` | `MALICIOUS` | **0.9292** | `0.9263` | `True` | `False` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-CLEAN-COUNTERFACTUAL-03` | `gemini-2.5-flash` | `no_runbook` | `BENIGN` | `BENIGN` | **1.0000** | `0.9520` | `True` | `True` | `False` | `update_case_comment, close_case` |
| `HUNT-DEGRADED-503-04` | `gemini-2.5-flash` | `no_runbook` | `INCONCLUSIVE` | `INCONCLUSIVE` | **1.0000** | `1.0000` | `False` | `False` | `False` | `update_case_comment` |
| `HUNT-URSNIF-COLLECTION-01` | `gemini-2.5-flash` | `raw_clinerules_hunt` | `MALICIOUS` | `INCONCLUSIVE` | **0.3300** | `0.2963` | `False` | `False` | `False` | `none` |
| `HUNT-URSNIF-DOMAIN-PIVOT-02` | `gemini-2.5-flash` | `raw_clinerules_hunt` | `MALICIOUS` | `MALICIOUS` | **0.9292** | `0.9263` | `True` | `False` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-CLEAN-COUNTERFACTUAL-03` | `gemini-2.5-flash` | `raw_clinerules_hunt` | `BENIGN` | `BENIGN` | **0.7500** | `0.9360` | `False` | `False` | `False` | `close_case, update_case_comment` |
| `HUNT-DEGRADED-503-04` | `gemini-2.5-flash` | `raw_clinerules_hunt` | `INCONCLUSIVE` | `INCONCLUSIVE` | **1.0000** | `1.0000` | `False` | `False` | `False` | `update_case_comment` |
| `HUNT-URSNIF-COLLECTION-01` | `gemini-2.5-flash` | `compressed_track_b_hunt` | `MALICIOUS` | `MALICIOUS` | **1.0000** | `0.9360` | `True` | `True` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-URSNIF-DOMAIN-PIVOT-02` | `gemini-2.5-flash` | `compressed_track_b_hunt` | `MALICIOUS` | `MALICIOUS` | **0.9625** | `0.9680` | `True` | `False` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-CLEAN-COUNTERFACTUAL-03` | `gemini-2.5-flash` | `compressed_track_b_hunt` | `BENIGN` | `BENIGN` | **0.9250** | `0.9520` | `True` | `True` | `False` | `close_case, update_case_comment` |
| `HUNT-DEGRADED-503-04` | `gemini-2.5-flash` | `compressed_track_b_hunt` | `INCONCLUSIVE` | `INCONCLUSIVE` | **1.0000** | `1.0000` | `False` | `False` | `False` | `update_case_comment` |
| `HUNT-URSNIF-COLLECTION-01` | `gemini-2.5-flash` | `harness2_evolved_hunt` | `MALICIOUS` | `MALICIOUS` | **1.0000** | `0.9360` | `True` | `True` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-URSNIF-DOMAIN-PIVOT-02` | `gemini-2.5-flash` | `harness2_evolved_hunt` | `MALICIOUS` | `MALICIOUS` | **0.9625** | `0.9520` | `True` | `False` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-CLEAN-COUNTERFACTUAL-03` | `gemini-2.5-flash` | `harness2_evolved_hunt` | `BENIGN` | `BENIGN` | **0.9250** | `0.9360` | `True` | `True` | `False` | `close_case, update_case_comment` |
| `HUNT-DEGRADED-503-04` | `gemini-2.5-flash` | `harness2_evolved_hunt` | `INCONCLUSIVE` | `INCONCLUSIVE` | **1.0000** | `1.0000` | `False` | `False` | `False` | `update_case_comment` |
| `HUNT-URSNIF-COLLECTION-01` | `gemini-3.5-flash-lite` | `no_runbook` | `MALICIOUS` | `MALICIOUS` | **0.9250** | `0.9840` | `True` | `False` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-URSNIF-DOMAIN-PIVOT-02` | `gemini-3.5-flash-lite` | `no_runbook` | `MALICIOUS` | `MALICIOUS` | **0.9625** | `0.9680` | `True` | `False` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-CLEAN-COUNTERFACTUAL-03` | `gemini-3.5-flash-lite` | `no_runbook` | `BENIGN` | `BENIGN` | **1.0000** | `0.9680` | `True` | `True` | `False` | `close_case, update_case_comment` |
| `HUNT-DEGRADED-503-04` | `gemini-3.5-flash-lite` | `no_runbook` | `INCONCLUSIVE` | `INCONCLUSIVE` | **1.0000** | `0.9000` | `False` | `False` | `False` | `update_case_comment` |
| `HUNT-URSNIF-COLLECTION-01` | `gemini-3.5-flash-lite` | `raw_clinerules_hunt` | `MALICIOUS` | `MALICIOUS` | **1.0000** | `0.9360` | `True` | `True` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-URSNIF-DOMAIN-PIVOT-02` | `gemini-3.5-flash-lite` | `raw_clinerules_hunt` | `MALICIOUS` | `MALICIOUS` | **0.9625** | `0.9680` | `True` | `False` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-CLEAN-COUNTERFACTUAL-03` | `gemini-3.5-flash-lite` | `raw_clinerules_hunt` | `BENIGN` | `BENIGN` | **1.0000** | `0.9520` | `True` | `True` | `False` | `close_case, update_case_comment` |
| `HUNT-DEGRADED-503-04` | `gemini-3.5-flash-lite` | `raw_clinerules_hunt` | `INCONCLUSIVE` | `INCONCLUSIVE` | **1.0000** | `1.0000` | `False` | `False` | `False` | `update_case_comment` |
| `HUNT-URSNIF-COLLECTION-01` | `gemini-3.5-flash-lite` | `compressed_track_b_hunt` | `MALICIOUS` | `MALICIOUS` | **0.9250** | `0.9680` | `True` | `False` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-URSNIF-DOMAIN-PIVOT-02` | `gemini-3.5-flash-lite` | `compressed_track_b_hunt` | `MALICIOUS` | `MALICIOUS` | **0.9625** | `0.9680` | `True` | `False` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-CLEAN-COUNTERFACTUAL-03` | `gemini-3.5-flash-lite` | `compressed_track_b_hunt` | `BENIGN` | `BENIGN` | **1.0000** | `0.9520` | `True` | `True` | `False` | `close_case, update_case_comment` |
| `HUNT-DEGRADED-503-04` | `gemini-3.5-flash-lite` | `compressed_track_b_hunt` | `INCONCLUSIVE` | `INCONCLUSIVE` | **1.0000** | `0.9000` | `False` | `False` | `False` | `update_case_comment` |
| `HUNT-URSNIF-COLLECTION-01` | `gemini-3.5-flash-lite` | `harness2_evolved_hunt` | `MALICIOUS` | `MALICIOUS` | **0.9250** | `0.9520` | `True` | `False` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-URSNIF-DOMAIN-PIVOT-02` | `gemini-3.5-flash-lite` | `harness2_evolved_hunt` | `MALICIOUS` | `MALICIOUS` | **0.9625** | `0.9520` | `True` | `False` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-CLEAN-COUNTERFACTUAL-03` | `gemini-3.5-flash-lite` | `harness2_evolved_hunt` | `BENIGN` | `BENIGN` | **1.0000** | `0.9520` | `True` | `True` | `False` | `close_case, update_case_comment` |
| `HUNT-DEGRADED-503-04` | `gemini-3.5-flash-lite` | `harness2_evolved_hunt` | `INCONCLUSIVE` | `INCONCLUSIVE` | **1.0000** | `1.0000` | `False` | `False` | `False` | `update_case_comment` |
