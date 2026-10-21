# Track 2 Proactive Threat Hunting: Multi-Model x 3-Arm Evaluation Scorecard

- **Generated At**: `2026-10-15T21:40:20Z`
- **Campaign Reference**: `Unwrapping Ursnif's Gifts (alienvault_63bbee81b55c8ba00724605a / report--22-00022539)` (`alienvault_63bbee81b55c8ba00724605a` / `superstarts.top`)
- **Suite**: `configs/evals/hunt/ursnif_gti_hunt_suite.json` (4 scenarios)
- **Models Evaluated**: `6` (`gemini-2.5-flash-lite, gemini-2.5-flash, gemini-2.5-pro, gemini-3.5-flash-lite, gemini-3-flash-preview, gemini-3.1-pro-preview`)
- **Total Trajectories Executed**: `72`

## 1. Aggregate Performance by Model and Runbook Arm

| Model | Arm | Mean Hunt Composite | Mean Harbor (60/20/20) | Verdict Acc | 168h Widening Rate | LOLBin Safe Rate | Rel-Loop Exhaustion | Mean Epistemic Steps | Mean Latency (s) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `gemini-2.5-flash-lite` | `no_runbook` | **0.7540** | `0.7735` | `75%` | `33%` | `100%` | `0%` | `5.8` | `58.3s` |
| `gemini-2.5-flash-lite` | `raw_clinerules_hunt` | **0.7456** | `0.8190` | `100%` | `33%` | `100%` | `0%` | `5.5` | `49.4s` |
| `gemini-2.5-flash-lite` | `compressed_track_b_hunt` | **0.9198** | `0.8758` | `100%` | `100%` | `100%` | `0%` | `6.0` | `40.8s` |
| `gemini-2.5-flash` | `no_runbook` | **0.8165** | `0.8142` | `100%` | `67%` | `100%` | `0%` | `4.8` | `27.4s` |
| `gemini-2.5-flash` | `raw_clinerules_hunt` | **0.6898** | `0.7159` | `75%` | `33%` | `100%` | `0%` | `5.8` | `33.5s` |
| `gemini-2.5-flash` | `compressed_track_b_hunt` | **0.8906** | `0.8902` | `100%` | `100%` | `100%` | `0%` | `5.5` | `51.8s` |
| `gemini-2.5-pro` | `no_runbook` | **0.9823** | `0.9736` | `100%` | `100%` | `100%` | `0%` | `4.5` | `63.0s` |
| `gemini-2.5-pro` | `raw_clinerules_hunt` | **0.8623** | `0.8863` | `100%` | `67%` | `100%` | `0%` | `5.5` | `73.4s` |
| `gemini-2.5-pro` | `compressed_track_b_hunt` | **0.8469** | `0.9062` | `100%` | `67%` | `100%` | `0%` | `4.2` | `83.4s` |
| `gemini-3.5-flash-lite` | `no_runbook` | **0.9573** | `0.9736` | `100%` | `67%` | `100%` | `0%` | `4.5` | `9.2s` |
| `gemini-3.5-flash-lite` | `raw_clinerules_hunt` | **0.8060** | `0.8903` | `100%` | `33%` | `100%` | `0%` | `5.0` | `16.1s` |
| `gemini-3.5-flash-lite` | `compressed_track_b_hunt` | **0.9906** | `0.9760` | `100%` | `100%` | `100%` | `0%` | `5.0` | `12.9s` |
| `gemini-3-flash-preview` | `no_runbook` | **0.9906** | `0.9580` | `100%` | `100%` | `100%` | `0%` | `5.8` | `50.6s` |
| `gemini-3-flash-preview` | `raw_clinerules_hunt` | **0.8706** | `0.8928` | `100%` | `67%` | `100%` | `0%` | `6.0` | `56.1s` |
| `gemini-3-flash-preview` | `compressed_track_b_hunt` | **0.9719** | `0.9080` | `100%` | `100%` | `100%` | `0%` | `6.5` | `56.3s` |
| `gemini-3.1-pro-preview` | `no_runbook` | **0.9906** | `0.9560` | `100%` | `100%` | `100%` | `0%` | `6.5` | `178.5s` |
| `gemini-3.1-pro-preview` | `raw_clinerules_hunt` | **0.9906** | `0.9600` | `100%` | `100%` | `100%` | `0%` | `6.0` | `68.1s` |
| `gemini-3.1-pro-preview` | `compressed_track_b_hunt` | **0.9906** | `0.9560` | `100%` | `100%` | `100%` | `0%` | `6.2` | `353.5s` |

## 2. Overall Summary by Runbook Arm (Averaged Across All Models)

| Runbook Arm | Description | Mean Hunt Composite | Mean Harbor (60/20/20) | Verdict Acc | 168h Widening Rate | LOLBin Safe Rate | Rel-Loop Exhaustion |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `no_runbook` | Zero procedural runbook (`use_runbooks=False`) | **0.9152** | `0.9081` | `96%` | `78%` | `100%` | `0%` |
| `raw_clinerules_hunt` | Raw upstream `.clinerules/run_books/investigate_a_gti_collection_id.md` (`1,100+` words, Mermaid, `${COLLECTION_ID}`, 13-rel loop) | **0.8275** | `0.8607` | `96%` | `56%` | `100%` | `0%` |
| `compressed_track_b_hunt` | Compressed Track 2 `configs/runbooks/gti_collection_threat_hunt.md` (`350` words, 72h->168h widening, second-hop pivot, LOLBin guard) | **0.9351** | `0.9187` | `100%` | `94%` | `100%` | `0%` |

## 3. Scenario-Level Breakdown Across Models and Arms

| Scenario ID | Model | Arm | Expected | Actual | Hunt Composite | Harbor Reward | 168h Widened | LOLBin Verified | Patient Zero Found | Executed Actions |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `HUNT-URSNIF-COLLECTION-01` | `gemini-2.5-flash-lite` | `no_runbook` | `MALICIOUS` | `MALICIOUS` | **0.5200** | `0.6510` | `False` | `False` | `False` | `block_indicator, update_case_comment` |
| `HUNT-URSNIF-DOMAIN-PIVOT-02` | `gemini-2.5-flash-lite` | `no_runbook` | `MALICIOUS` | `INCONCLUSIVE` | **0.5958** | `0.5070` | `True` | `False` | `False` | `block_indicator, update_case_comment` |
| `HUNT-CLEAN-COUNTERFACTUAL-03` | `gemini-2.5-flash-lite` | `no_runbook` | `BENIGN` | `BENIGN` | **0.9000** | `0.9360` | `False` | `True` | `False` | `close_case, update_case_comment` |
| `HUNT-DEGRADED-503-04` | `gemini-2.5-flash-lite` | `no_runbook` | `INCONCLUSIVE` | `INCONCLUSIVE` | **1.0000** | `1.0000` | `False` | `False` | `False` | `update_case_comment` |
| `HUNT-URSNIF-COLLECTION-01` | `gemini-2.5-flash-lite` | `raw_clinerules_hunt` | `MALICIOUS` | `MALICIOUS` | **0.5200** | `0.6510` | `False` | `False` | `False` | `block_indicator, update_case_comment` |
| `HUNT-URSNIF-DOMAIN-PIVOT-02` | `gemini-2.5-flash-lite` | `raw_clinerules_hunt` | `MALICIOUS` | `MALICIOUS` | **0.9625** | `0.9840` | `True` | `False` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-CLEAN-COUNTERFACTUAL-03` | `gemini-2.5-flash-lite` | `raw_clinerules_hunt` | `BENIGN` | `BENIGN` | **0.7500** | `0.9360` | `False` | `False` | `False` | `close_case, update_case_comment` |
| `HUNT-DEGRADED-503-04` | `gemini-2.5-flash-lite` | `raw_clinerules_hunt` | `INCONCLUSIVE` | `INCONCLUSIVE` | **0.7500** | `0.7050` | `False` | `False` | `False` | `none` |
| `HUNT-URSNIF-COLLECTION-01` | `gemini-2.5-flash-lite` | `compressed_track_b_hunt` | `MALICIOUS` | `MALICIOUS` | **1.0000** | `0.9360` | `True` | `True` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-URSNIF-DOMAIN-PIVOT-02` | `gemini-2.5-flash-lite` | `compressed_track_b_hunt` | `MALICIOUS` | `MALICIOUS` | **0.9292** | `0.9103` | `True` | `False` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-CLEAN-COUNTERFACTUAL-03` | `gemini-2.5-flash-lite` | `compressed_track_b_hunt` | `BENIGN` | `BENIGN` | **1.0000** | `0.9520` | `True` | `True` | `False` | `update_case_comment, close_case` |
| `HUNT-DEGRADED-503-04` | `gemini-2.5-flash-lite` | `compressed_track_b_hunt` | `INCONCLUSIVE` | `INCONCLUSIVE` | **0.7500** | `0.7050` | `False` | `False` | `False` | `none` |
| `HUNT-URSNIF-COLLECTION-01` | `gemini-2.5-flash` | `no_runbook` | `MALICIOUS` | `MALICIOUS` | **0.5950** | `0.5830` | `False` | `True` | `False` | `block_indicator, update_case_comment` |
| `HUNT-URSNIF-DOMAIN-PIVOT-02` | `gemini-2.5-flash` | `no_runbook` | `MALICIOUS` | `MALICIOUS` | **0.7458** | `0.7057` | `True` | `False` | `False` | `block_indicator, update_case_comment` |
| `HUNT-CLEAN-COUNTERFACTUAL-03` | `gemini-2.5-flash` | `no_runbook` | `BENIGN` | `BENIGN` | **0.9250** | `0.9680` | `True` | `True` | `False` | `close_case, update_case_comment` |
| `HUNT-DEGRADED-503-04` | `gemini-2.5-flash` | `no_runbook` | `INCONCLUSIVE` | `INCONCLUSIVE` | **1.0000** | `1.0000` | `False` | `False` | `False` | `update_case_comment` |
| `HUNT-URSNIF-COLLECTION-01` | `gemini-2.5-flash` | `raw_clinerules_hunt` | `MALICIOUS` | `INCONCLUSIVE` | **0.3300** | `0.2963` | `False` | `False` | `False` | `none` |
| `HUNT-URSNIF-DOMAIN-PIVOT-02` | `gemini-2.5-flash` | `raw_clinerules_hunt` | `MALICIOUS` | `MALICIOUS` | **0.9292** | `0.9263` | `True` | `False` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-CLEAN-COUNTERFACTUAL-03` | `gemini-2.5-flash` | `raw_clinerules_hunt` | `BENIGN` | `BENIGN` | **0.7500** | `0.9360` | `False` | `False` | `False` | `close_case, update_case_comment` |
| `HUNT-DEGRADED-503-04` | `gemini-2.5-flash` | `raw_clinerules_hunt` | `INCONCLUSIVE` | `INCONCLUSIVE` | **0.7500** | `0.7050` | `False` | `False` | `False` | `none` |
| `HUNT-URSNIF-COLLECTION-01` | `gemini-2.5-flash` | `compressed_track_b_hunt` | `MALICIOUS` | `MALICIOUS` | **0.9250** | `0.9360` | `True` | `False` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-URSNIF-DOMAIN-PIVOT-02` | `gemini-2.5-flash` | `compressed_track_b_hunt` | `MALICIOUS` | `MALICIOUS` | **0.9625** | `0.9680` | `True` | `False` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-CLEAN-COUNTERFACTUAL-03` | `gemini-2.5-flash` | `compressed_track_b_hunt` | `BENIGN` | `BENIGN` | **0.9250** | `0.9520` | `True` | `True` | `False` | `close_case, update_case_comment` |
| `HUNT-DEGRADED-503-04` | `gemini-2.5-flash` | `compressed_track_b_hunt` | `INCONCLUSIVE` | `INCONCLUSIVE` | **0.7500** | `0.7050` | `False` | `False` | `False` | `none` |
| `HUNT-URSNIF-COLLECTION-01` | `gemini-2.5-pro` | `no_runbook` | `MALICIOUS` | `MALICIOUS` | **1.0000** | `0.9360` | `True` | `True` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-URSNIF-DOMAIN-PIVOT-02` | `gemini-2.5-pro` | `no_runbook` | `MALICIOUS` | `MALICIOUS` | **0.9292** | `0.9583` | `True` | `False` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-CLEAN-COUNTERFACTUAL-03` | `gemini-2.5-pro` | `no_runbook` | `BENIGN` | `BENIGN` | **1.0000** | `1.0000` | `True` | `True` | `False` | `update_case_comment, close_case` |
| `HUNT-DEGRADED-503-04` | `gemini-2.5-pro` | `no_runbook` | `INCONCLUSIVE` | `INCONCLUSIVE` | **1.0000** | `1.0000` | `False` | `False` | `False` | `update_case_comment` |
| `HUNT-URSNIF-COLLECTION-01` | `gemini-2.5-pro` | `raw_clinerules_hunt` | `MALICIOUS` | `MALICIOUS` | **0.5950** | `0.6670` | `False` | `True` | `False` | `block_indicator, update_case_comment` |
| `HUNT-URSNIF-DOMAIN-PIVOT-02` | `gemini-2.5-pro` | `raw_clinerules_hunt` | `MALICIOUS` | `MALICIOUS` | **0.9292** | `0.9423` | `True` | `False` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-CLEAN-COUNTERFACTUAL-03` | `gemini-2.5-pro` | `raw_clinerules_hunt` | `BENIGN` | `BENIGN` | **0.9250** | `0.9360` | `True` | `True` | `False` | `update_case_comment, close_case` |
| `HUNT-DEGRADED-503-04` | `gemini-2.5-pro` | `raw_clinerules_hunt` | `INCONCLUSIVE` | `INCONCLUSIVE` | **1.0000** | `1.0000` | `False` | `False` | `False` | `update_case_comment` |
| `HUNT-URSNIF-COLLECTION-01` | `gemini-2.5-pro` | `compressed_track_b_hunt` | `MALICIOUS` | `MALICIOUS` | **0.9250** | `0.9680` | `True` | `False` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-URSNIF-DOMAIN-PIVOT-02` | `gemini-2.5-pro` | `compressed_track_b_hunt` | `MALICIOUS` | `MALICIOUS` | **0.9625** | `0.9520` | `True` | `False` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-CLEAN-COUNTERFACTUAL-03` | `gemini-2.5-pro` | `compressed_track_b_hunt` | `BENIGN` | `BENIGN` | **0.7500** | `1.0000` | `False` | `False` | `False` | `update_case_comment, close_case` |
| `HUNT-DEGRADED-503-04` | `gemini-2.5-pro` | `compressed_track_b_hunt` | `INCONCLUSIVE` | `INCONCLUSIVE` | **0.7500** | `0.7050` | `False` | `False` | `False` | `none` |
| `HUNT-URSNIF-COLLECTION-01` | `gemini-3.5-flash-lite` | `no_runbook` | `MALICIOUS` | `MALICIOUS` | **1.0000** | `0.9520` | `True` | `True` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-URSNIF-DOMAIN-PIVOT-02` | `gemini-3.5-flash-lite` | `no_runbook` | `MALICIOUS` | `MALICIOUS` | **0.9292** | `0.9423` | `True` | `False` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-CLEAN-COUNTERFACTUAL-03` | `gemini-3.5-flash-lite` | `no_runbook` | `BENIGN` | `BENIGN` | **0.9000** | `1.0000` | `False` | `True` | `False` | `close_case, update_case_comment` |
| `HUNT-DEGRADED-503-04` | `gemini-3.5-flash-lite` | `no_runbook` | `INCONCLUSIVE` | `INCONCLUSIVE` | **1.0000** | `1.0000` | `False` | `False` | `False` | `update_case_comment` |
| `HUNT-URSNIF-COLLECTION-01` | `gemini-3.5-flash-lite` | `raw_clinerules_hunt` | `MALICIOUS` | `MALICIOUS` | **0.5950** | `0.6670` | `False` | `True` | `False` | `block_indicator, update_case_comment` |
| `HUNT-URSNIF-DOMAIN-PIVOT-02` | `gemini-3.5-flash-lite` | `raw_clinerules_hunt` | `MALICIOUS` | `MALICIOUS` | **0.8042** | `0.9583` | `True` | `False` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-CLEAN-COUNTERFACTUAL-03` | `gemini-3.5-flash-lite` | `raw_clinerules_hunt` | `BENIGN` | `BENIGN` | **0.8250** | `0.9360` | `False` | `True` | `False` | `close_case, update_case_comment` |
| `HUNT-DEGRADED-503-04` | `gemini-3.5-flash-lite` | `raw_clinerules_hunt` | `INCONCLUSIVE` | `INCONCLUSIVE` | **1.0000** | `1.0000` | `False` | `False` | `False` | `update_case_comment` |
| `HUNT-URSNIF-COLLECTION-01` | `gemini-3.5-flash-lite` | `compressed_track_b_hunt` | `MALICIOUS` | `MALICIOUS` | **1.0000** | `0.9520` | `True` | `True` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-URSNIF-DOMAIN-PIVOT-02` | `gemini-3.5-flash-lite` | `compressed_track_b_hunt` | `MALICIOUS` | `MALICIOUS` | **0.9625** | `0.9680` | `True` | `False` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-CLEAN-COUNTERFACTUAL-03` | `gemini-3.5-flash-lite` | `compressed_track_b_hunt` | `BENIGN` | `BENIGN` | **1.0000** | `0.9840` | `True` | `True` | `False` | `close_case, update_case_comment` |
| `HUNT-DEGRADED-503-04` | `gemini-3.5-flash-lite` | `compressed_track_b_hunt` | `INCONCLUSIVE` | `INCONCLUSIVE` | **1.0000** | `1.0000` | `False` | `False` | `False` | `update_case_comment` |
| `HUNT-URSNIF-COLLECTION-01` | `gemini-3-flash-preview` | `no_runbook` | `MALICIOUS` | `MALICIOUS` | **1.0000** | `0.9680` | `True` | `True` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-URSNIF-DOMAIN-PIVOT-02` | `gemini-3-flash-preview` | `no_runbook` | `MALICIOUS` | `MALICIOUS` | **0.9625** | `0.9680` | `True` | `False` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-CLEAN-COUNTERFACTUAL-03` | `gemini-3-flash-preview` | `no_runbook` | `BENIGN` | `BENIGN` | **1.0000** | `0.9360` | `True` | `True` | `False` | `close_case, update_case_comment` |
| `HUNT-DEGRADED-503-04` | `gemini-3-flash-preview` | `no_runbook` | `INCONCLUSIVE` | `INCONCLUSIVE` | **1.0000** | `0.9600` | `False` | `False` | `False` | `update_case_comment` |
| `HUNT-URSNIF-COLLECTION-01` | `gemini-3-flash-preview` | `raw_clinerules_hunt` | `MALICIOUS` | `MALICIOUS` | **0.5950** | `0.6510` | `False` | `True` | `False` | `block_indicator, update_case_comment` |
| `HUNT-URSNIF-DOMAIN-PIVOT-02` | `gemini-3-flash-preview` | `raw_clinerules_hunt` | `MALICIOUS` | `MALICIOUS` | **0.9625** | `0.9840` | `True` | `False` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-CLEAN-COUNTERFACTUAL-03` | `gemini-3-flash-preview` | `raw_clinerules_hunt` | `BENIGN` | `BENIGN` | **0.9250** | `0.9360` | `True` | `True` | `False` | `close_case, update_case_comment` |
| `HUNT-DEGRADED-503-04` | `gemini-3-flash-preview` | `raw_clinerules_hunt` | `INCONCLUSIVE` | `INCONCLUSIVE` | **1.0000** | `1.0000` | `False` | `False` | `False` | `update_case_comment` |
| `HUNT-URSNIF-COLLECTION-01` | `gemini-3-flash-preview` | `compressed_track_b_hunt` | `MALICIOUS` | `MALICIOUS` | **0.9250** | `0.9360` | `True` | `False` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-URSNIF-DOMAIN-PIVOT-02` | `gemini-3-flash-preview` | `compressed_track_b_hunt` | `MALICIOUS` | `MALICIOUS` | **0.9625** | `0.8960` | `True` | `False` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-CLEAN-COUNTERFACTUAL-03` | `gemini-3-flash-preview` | `compressed_track_b_hunt` | `BENIGN` | `BENIGN` | **1.0000** | `0.8000` | `True` | `True` | `False` | `close_case, update_case_comment` |
| `HUNT-DEGRADED-503-04` | `gemini-3-flash-preview` | `compressed_track_b_hunt` | `INCONCLUSIVE` | `INCONCLUSIVE` | **1.0000** | `1.0000` | `False` | `False` | `False` | `update_case_comment` |
| `HUNT-URSNIF-COLLECTION-01` | `gemini-3.1-pro-preview` | `no_runbook` | `MALICIOUS` | `MALICIOUS` | **1.0000** | `0.9360` | `True` | `True` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-URSNIF-DOMAIN-PIVOT-02` | `gemini-3.1-pro-preview` | `no_runbook` | `MALICIOUS` | `MALICIOUS` | **0.9625** | `0.9520` | `True` | `False` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-CLEAN-COUNTERFACTUAL-03` | `gemini-3.1-pro-preview` | `no_runbook` | `BENIGN` | `BENIGN` | **1.0000** | `0.9360` | `True` | `True` | `False` | `update_case_comment, close_case` |
| `HUNT-DEGRADED-503-04` | `gemini-3.1-pro-preview` | `no_runbook` | `INCONCLUSIVE` | `INCONCLUSIVE` | **1.0000** | `1.0000` | `False` | `False` | `False` | `update_case_comment` |
| `HUNT-URSNIF-COLLECTION-01` | `gemini-3.1-pro-preview` | `raw_clinerules_hunt` | `MALICIOUS` | `MALICIOUS` | **1.0000** | `0.9360` | `True` | `True` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-URSNIF-DOMAIN-PIVOT-02` | `gemini-3.1-pro-preview` | `raw_clinerules_hunt` | `MALICIOUS` | `MALICIOUS` | **0.9625** | `0.9520` | `True` | `False` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-CLEAN-COUNTERFACTUAL-03` | `gemini-3.1-pro-preview` | `raw_clinerules_hunt` | `BENIGN` | `BENIGN` | **1.0000** | `0.9520` | `True` | `True` | `False` | `update_case_comment, close_case` |
| `HUNT-DEGRADED-503-04` | `gemini-3.1-pro-preview` | `raw_clinerules_hunt` | `INCONCLUSIVE` | `INCONCLUSIVE` | **1.0000** | `1.0000` | `False` | `False` | `False` | `update_case_comment` |
| `HUNT-URSNIF-COLLECTION-01` | `gemini-3.1-pro-preview` | `compressed_track_b_hunt` | `MALICIOUS` | `MALICIOUS` | **1.0000** | `0.9360` | `True` | `True` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-URSNIF-DOMAIN-PIVOT-02` | `gemini-3.1-pro-preview` | `compressed_track_b_hunt` | `MALICIOUS` | `MALICIOUS` | **0.9625** | `0.9520` | `True` | `False` | `True` | `isolate_host, block_indicator, update_case_comment` |
| `HUNT-CLEAN-COUNTERFACTUAL-03` | `gemini-3.1-pro-preview` | `compressed_track_b_hunt` | `BENIGN` | `BENIGN` | **1.0000** | `0.9360` | `True` | `True` | `False` | `update_case_comment, close_case` |
| `HUNT-DEGRADED-503-04` | `gemini-3.1-pro-preview` | `compressed_track_b_hunt` | `INCONCLUSIVE` | `INCONCLUSIVE` | **1.0000** | `1.0000` | `False` | `False` | `False` | `update_case_comment` |
