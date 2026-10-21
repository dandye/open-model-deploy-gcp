# Harness^2 Recursive Runbook Evolution Campaign Report

- **Branch**: `harness2__recursive-runbook-evolution`
- **Paper Reference**: *Harness^2: Recursive Agent Harnessing for an Open World* (`arXiv:2610.14224`, `https://github.com/google-research/harness2`)
- **Evaluation Harness Lock**: Verified across all 33 protected files (`composite_sha256=038639ae9c6839146f0ecad07b0ecfc6c48ea47b8a49d507c7dab237619218df`, zero locked-file modifications, `final_test.json` sealed)
- **Cumulative Campaign Spend**: `\$2.28` across all live evolution, probing, and cross-model transfer benchmarks (hard budget ceiling: `\$15.00`)

---

## 1. Executive Summary & Root-Cause Resolution

Prior to this campaign, `run_id=20261019T004640Z-68a18137` (commit `a5a0c4e`) demonstrated that component-scoped inner probing (`Harness2ProposeProbeComposeProposer._select_probe_batch(comp_name)`) enabled `Harness2ProposeProbeComposeProposer` to propose winning `malware_triage.md` revisions on its 8 matched training cases, yet outer GEPA evolution still terminated with `seed_retained_all_candidates_reverted` (`0.9462` baseline retained). Trajectory forensics and code inspection uncovered three structural bottlenecks:

1. **Uniform Outer GEPA Minibatch Sampling Starvation (`agent/gepa_runbook_optimizer.py`)**:
   - GEPA's default `EpochShuffledBatchSampler` drew `minibatch_size=3` uniformly across all 40 Gen 5 `trainset` cases (`basic_ioc_enrichment.md`: `22/40`, `malware_triage.md`: `8/40`, `suspicious_login_triage.md`: `6/40`, `lateral_movement_hunt_psexec_wmi.md`: `4/40`).
   - A uniform 3-case draw had a $(32/40)^3 = 51.2\%$ probability of containing zero `malware_triage.md` cases and a $(36/40)^3 = 72.9\%$ probability of containing zero `lateral_movement_hunt_psexec_wmi.md` cases, causing outer minibatch score ties (`2.8996 vs 2.8996` in Iteration 3 of `run_id=20261019T004640Z-68a18137`) even when the inner probe won outright.
   - **Resolution**: Implemented `ComponentStratifiedBatchSampler` (`minibatch_size=4`) and `NonFrozenRoundRobinSelector`, guaranteeing that when component $c$ is scheduled for mutation, the outer GEPA minibatch contains 3 family-interleaved cases where `resolve_implicated_runbook(case) == c` plus 1 cross-runbook benign/duplicate guard case.

2. **Un-Gated Inner Probe Scoring (`Harness2ProposeProbeComposeProposer._probe_score`)**:
   - In `run_id=20261016T175833Z-9f54c812`, Iteration 5 cleared the outer GEPA subsample (`2.9557 -> 2.9574`) and lifted the Pareto front (`0.9572 -> 0.9582`), but was reverted at post-loop validation by `REVERTED_CATEGORICAL_TAXONOMY` because `_probe_score()` evaluated only mean scalar reward without running `evaluate_candidate_acceptance()` categorical checks during inner `INV`/`DOM`/`COMPOSED` probing.
   - **Resolution**: Hardened `_probe_score()` (`agent/gepa_runbook_optimizer.py:1695-1731`) to capture full trajectory telemetry (`capture_traces=True`) and run `evaluate_candidate_acceptance()` against the base candidate on the probe batch (including a benign/duplicate guard case), penalizing any candidate that triggers `REVERTED_CATEGORICAL_ZERO_TOOLS`, `REVERTED_CATEGORICAL_INERT`, `REVERTED_CATEGORICAL_SAFETY`, `REVERTED_CATEGORICAL_TAXONOMY`, or `REVERTED_REGRESSION` with `-1.0`.

3. **Noisy System-One `jev_choice` Overriding Passing Trajectories (`agent/aqua_diagnostics.py:501`) & Parenthetical Host Target Resolution (`agent/hierarchical_soc_agent.py:1353`)**:
   - In `run_id=20261019T004640Z-68a18137`, `gliner_decide` emitted noisy `jev_choice` labels on cases that passed deterministically (`score >= 0.95`, `loss_penalty >= 1.0`, `assert_passed=True`), causing `extract_trace_diagnosis()` to misclassify passing traces and preventing AQuA from freezing `basic_ioc_enrichment.md`. Simultaneously, on `CASE-GEN5-RANSOMWARE-CRITICAL-05` (`0.7577`) and `CASE-GEN5-LATERAL-PSEXEC-05` (`0.7501`), the supervisor recommended `isolate_host` with `target_entity="SRV-FILE-CORE-01 (10.50.4.20)"`, which `_resolve_target_host()` rejected as two distinct host targets (`SRV-FILE-CORE-01` and `10.50.4.20`).
   - **Resolution**: Gated `extract_trace_diagnosis()` so passing trajectories (`score >= 0.95`, `loss_penalty >= 1.0`, `assert_passed=True`, no safety/inert/zero-tool violations) are canonically classified as `FLAWLESS_CONTAINMENT`, and updated `_resolve_target_host()` to strip parenthetical annotations (`"HOST (IP)"`) when resolving `decision.target_entity` against environment inventory.

---

## 2. Phase 2: Multi-Round ($k=2$) Gen 5 Tier 1 Recursive Evolution Results

- **Run ID**: `20261020T055127Z-64c54d88`
- **Artifacts Directory**: `docs/soc_eval_results/harness2_8h_campaign/gen5_flash_lite/`
- **Configuration**: `--task-lm gemini-2.5-flash-lite --reflection-lm gemini-2.5-pro --proposal-mode harness2 --rounds 2 --freeze-passing-runbooks --forbid-template-vars --forbid-mermaid --forbid-pseudotools --max-words 350 --budget-limit-usd 6.00`
- **Noise Floor Gate (`noise_floor.json`)**:
  - `run1_mean = 0.92599`, `run2_mean = 0.92520`, `mean_spread = 0.00079 <= 0.0200` (**PASS**)
  - `mean_case_std = 0.00467`, `tau_accept = 0.0150`
  - Frozen 100%-passing runbooks locked by AQuA: `basic_ioc_enrichment.md`, `suspicious_login_triage.md`
  - Unfrozen weak runbooks targeted by `NonFrozenRoundRobinSelector`: `malware_triage.md` (baseline `0.9293` across 7 val cases; `CASE-GEN5-RANSOMWARE-CRITICAL-05` at `0.7577`), `lateral_movement_hunt_psexec_wmi.md` (baseline `0.7501` on `CASE-GEN5-LATERAL-PSEXEC-05`).

### 2.1 Hillclimb Ledger & $k=1 \to k=2$ Progression (`hillclimb_ledger.jsonl`)

| Global Iteration | Round | Target Component(s) | Validation Score | Delta vs Baseline (`0.9252`) | Gate Decision | Attribution Breakdown | Key Case Movements |
| :---: | :---: | :--- | :---: | :---: | :---: | :--- | :--- |
| `0` | `1` | Seed Baseline ($H_0$) | `0.9252` | `+0.0000` | `KEPT` | Baseline | `RANSOMWARE-CRITICAL-05`: `0.7577`, `LATERAL-PSEXEC-05`: `0.7501` |
| `1` | `1` | `malware_triage.md` (`DOM`) | `0.9314` | `+0.0062` | `REVERTED_CATEGORICAL_TAXONOMY` | `malware_triage.md`: `hurt` | Lifted `RANSOMWARE-CRITICAL-05` `0.7577 -> 0.9668` (`+0.2091`), dipped `CRYPTOMINER-DEV-01` `0.9368 -> 0.7063` |
| **`2`** | **`1`** | **`malware_triage.md` + `lateral_movement_hunt_psexec_wmi.md` (`COMPOSED`)** | **`0.9642`** | **`+0.0390`** (`2.6x` $\tau_{\text{accept}}$) | **`KEPT` (PROMOTED)** | `lateral_movement_hunt_psexec_wmi.md`: `helped` (`+0.2187`), `malware_triage.md`: `helped` (`+0.0528`) | `LATERAL-PSEXEC-05`: `0.7501 -> 0.9688` (`+0.2187`), `RANSOMWARE-CRITICAL-05`: `0.7577 -> 0.9748` (`+0.2171`), `CRYPTOMINER-DEV-01`: `0.9368 -> 0.9707`, **20/20 cases passed (`0` regressions)** |
| `3` | `2` (Warm-Start from Cand `2`) | `malware_triage.md` (`COMPOSED`) | `0.9495` | `+0.0243` | `REVERTED_CATEGORICAL_TAXONOMY` | `lateral_movement_hunt_psexec_wmi.md`: `helped`, `malware_triage.md`: `hurt` | Retained `LATERAL-PSEXEC-05` (`0.9688`), rejected by categorical gate on `CRYPTOMINER-DEV-01` |
| `4` | `2` | `lateral_movement_hunt_psexec_wmi.md` (`INV`) | `0.9495` | `+0.0243` | `REVERTED_CATEGORICAL_TAXONOMY` | `lateral_movement_hunt_psexec_wmi.md`: `helped`, `malware_triage.md`: `hurt` | Retained `LATERAL-PSEXEC-05` (`0.9668`) |
| `5` | `2` | `malware_triage.md` (`DOM`) | `0.9494` | `+0.0242` | `REVERTED_CATEGORICAL_TAXONOMY` | `lateral_movement_hunt_psexec_wmi.md`: `helped`, `malware_triage.md`: `hurt` | Candidate `2` (`0.96423`) retained as overall champion |

### 2.2 Component-Level Progression Across the 4 Core Runbooks

| Runbook Component | Raw `.clinerules` Words | Evolved Words | Word Delta | Baseline Val Score (`run_id=64c54d88`) | Evolved Val Score (Cand `2`) | Post-Refinement Transfer Score (`gemini-2.5-flash-lite`) | Attribution Label |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :---: |
| `basic_ioc_enrichment.md` | `860` | `570` | `-33.7%` | `0.9585` | `0.9602` | `0.9833` | `no_observed_effect` (frozen) |
| `suspicious_login_triage.md` | `871` | `556` | `-36.2%` | `1.0000` (train) | `1.0000` (train) | `1.0000` (train) | `no_observed_effect` (frozen) |
| `malware_triage.md` | `843` | `336` | `-60.1%` | `0.9293` | `0.9690` (`+0.0397`) | **`0.9850`** (`+0.0557`) | **`helped`** |
| `lateral_movement_hunt_psexec_wmi.md` | `1,074` | `281` | `-73.8%` | `0.7501` | `0.9688` (`+0.2187`) | **`0.9850`** (`+0.2349`) | **`helped`** |
| **Total / Aggregate** | **`3,648`** | **`1,743`** | **`-52.2%`** | **`0.9252`** | **`0.9642`** (`+0.0390`) | **`0.9840`** (`+0.0588`) | **2 `helped`, 2 `frozen`** |

---

## 3. Phase 3A: Track 2 Proactive Threat Hunting (`ThreatHuntEnvironment`) Evolution & Transfer

- **Evolution Script**: `scripts/evolve_threat_hunt_harness2.py`
- **Artifacts Directory**: `docs/soc_eval_results/harness2_8h_campaign/threat_hunt/` and `docs/soc_eval_results/harness2_8h_campaign/threat_hunt_multi_model/`
- **Seed Baseline Runbook**: `configs/runbooks/gti_collection_threat_hunt.md` (`350` words)
- **Evolved Target Runbook**: `configs/runbooks/harness2_evolved/gti_collection_threat_hunt.md` (`347` words raw / `266` words stripped, zero Mermaid, zero `${VAR_NAME}`, zero interactive pseudo-tools)
- **Evaluation Scope**: In-distribution 4-scenario diagnostic CTI threat-hunt benchmark (`configs/evals/hunt/ursnif_gti_hunt_suite.json`, `N=4` scenarios evaluated across 3 models $\times$ 4 arms = `48` trajectories)
- **Evolution Summary (`evolution_metadata.json`)**:
  - Baseline score (`compressed_track_b_hunt` on `gemini-2.5-flash-lite`): `0.8998` (`HUNT-DEGRADED-503-04`: `0.7275`, `HUNT-URSNIF-DOMAIN-PIVOT-02`: `0.9573`).
  - Round 1 `Harness^2` Propose-Probe-Compose: `INV` scored `-1.0` (rejected by inner categorical gate), `DOM` scored **`0.9780`** (`+0.0782`), `COMPOSED` was skipped (`composed_score: null`). The proposer selected `DOM` (`decision=KEPT`, `+0.0782 >= tau_accept 0.0100`, `attribution=helped`, zero regressions). Round 2 selected `KEEP_BASE` (`0.9780` retained).

### 3.1 Track 2 Multi-Model x 4-Arm Transfer Scorecard (`48` Trajectories)

| Model | Runbook Arm | Mean Hunt Composite | Mean Harbor (60/20/20) | Verdict Acc | `168h` Widening Rate | LOLBin Safe Rate | Rel-Loop Exhaustion | Mean Epistemic Steps |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `gemini-2.5-flash-lite` | `no_runbook` | `0.7696` | `0.8272` | `100%` | `0%` | `100%` | `0%` | `5.2` |
| `gemini-2.5-flash-lite` | `raw_clinerules_hunt` | `0.7456` | `0.8190` | `100%` | `33%` | `100%` | `0%` | `5.5` |
| `gemini-2.5-flash-lite` | `compressed_track_b_hunt` | `0.9094` | `0.8902` | `100%` | `100%` | `100%` | `0%` | `5.5` |
| `gemini-2.5-flash-lite` | **`harness2_evolved_hunt`** | **`1.0000`** | **`0.9560`** | **`100%`** | **`100%`** | **`100%`** | **`0%`** | `6.5` |
| `gemini-2.5-flash` | `no_runbook` | `0.8248` | `0.8196` | `75%` | `67%` | `100%` | `0%` | `5.0` |
| `gemini-2.5-flash` | `raw_clinerules_hunt` | `0.7523` | `0.7896` | `75%` | `33%` | `100%` | `0%` | `6.2` |
| `gemini-2.5-flash` | `compressed_track_b_hunt` | `0.9719` | `0.9640` | `100%` | `100%` | `100%` | `0%` | `6.0` |
| `gemini-2.5-flash` | **`harness2_evolved_hunt`** | **`0.9719`** | **`0.9560`** | **`100%`** | **`100%`** | **`100%`** | **`0%`** | `6.2` |
| `gemini-3.5-flash-lite` | `no_runbook` | `0.9719` | `0.9550` | `100%` | `100%` | `100%` | `0%` | `5.0` |
| `gemini-3.5-flash-lite` | `raw_clinerules_hunt` | `0.9906` | `0.9640` | `100%` | `100%` | `100%` | `0%` | `6.0` |
| `gemini-3.5-flash-lite` | `compressed_track_b_hunt` | `0.9719` | `0.9470` | `100%` | `100%` | `100%` | `0%` | `5.5` |
| `gemini-3.5-flash-lite` | **`harness2_evolved_hunt`** | **`0.9719`** | **`0.9640`** | **`100%`** | **`100%`** | **`100%`** | **`0%`** | `6.0` |

### 3.2 Track 2 3-Model Aggregate Summary

| Runbook Arm | Mean Hunt Composite | Mean Harbor (60/20/20) | Verdict Acc | `168h` Widening Rate | LOLBin Safe Rate |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `no_runbook` | `0.8554` | `0.8673` | `92%` | `56%` | `100%` |
| `raw_clinerules_hunt` | `0.8295` | `0.8575` | `92%` | `56%` | `100%` |
| `compressed_track_b_hunt` | `0.9510` | `0.9337` | `100%` | `100%` | `100%` |
| **`harness2_evolved_hunt`** | **`0.9813`** | **`0.9587`** | **`100%`** | **`100%`** | **`100%`** |

---

## 4. Phase 3B: Gen 5 Cross-Model Transfer & Cost Staircase Benchmark

- **Run ID**: `20261020T092042Z-88248e1f`
- **Artifacts Directory**: `docs/soc_eval_results/harness2_8h_campaign/gen5_transfer/`
- **Dataset**: Gen 5 `validation` split (`20` cases across 10 scenario families, loaded via `scripts/gen5_exposure.py`)
- **Total Trajectories Executed**: `180` (`3` models $\times$ `3` arms $\times$ `20` validation cases, all evaluated on the identical runtime agent harness to isolate runbook effect from runtime agent guardrails)

### 4.1 Cross-Model Transfer Matrix (3 Models $\times$ 3 Arms)

| Model | Runbook Arm | Words | Harbor 60/20/20 | GEPA Fitness | `MALICIOUS` | `BENIGN` | `SUSPICIOUS` | `INCONCLUSIVE` | $d'$ | $c$ | Total Loss ($L$, USD) | Mean Tools | Token Cost (USD) |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `gemini-2.5-flash-lite` | `seed_runbooks` | `3,648` | `0.9684` | `0.9524` | `0.9503` | `0.9827` | `0.9834` | `0.9850` | `2.56` | `-0.06` | `\$50,251.32` | `6.35` | `\$0.0990` |
| `gemini-2.5-flash-lite` | `gepa_single_proposer` | `1,988` | `0.9784` | `0.9624` | `0.9726` | `0.9827` | `0.9834` | `0.9850` | `2.56` | `-0.06` | `\$50,251.37` | `6.50` | `\$0.1027` |
| `gemini-2.5-flash-lite` | **`harness2_k2_evolved`** | **`1,743`** | **`0.9840`** | **`0.9840`** | **`0.9850`** | **`0.9827`** | **`0.9834`** | **`0.9850`** | **`2.91`** | **`-0.23`** | **`\$251.02`** | **`5.60`** | **`\$0.0716`** |
| `gemini-2.5-flash` | `seed_runbooks` | `3,648` | `0.9723` | `0.9563` | `0.9850` | `0.9850` | `0.9005` | `0.9850` | `2.91` | `-0.23` | `\$250.94` | `5.00` | `\$0.2017` |
| `gemini-2.5-flash` | `gepa_single_proposer` | `1,988` | `0.9751` | `0.9591` | `0.9850` | `0.9850` | `0.9188` | `0.9850` | `2.91` | `-0.23` | `\$50,000.91` | `4.95` | `\$0.1943` |
| `gemini-2.5-flash` | **`harness2_k2_evolved`** | **`1,743`** | **`0.9723`** | **`0.9723`** | **`0.9850`** | **`0.9850`** | `0.9005` | **`0.9850`** | `2.49` | `-0.40` | **`\$5,250.87`** | `5.10` | **`\$0.1809`** |
| `gemini-3.5-flash-lite` | `seed_runbooks` | `3,648` | `0.9825` | `0.9665` | `0.9850` | `0.9850` | `0.9683` | `0.9850` | `3.27` | `-0.10` | `\$0.93` | `5.25` | `\$0.0568` |
| `gemini-3.5-flash-lite` | `gepa_single_proposer` | `1,988` | `0.9825` | `0.9665` | `0.9850` | `0.9850` | `0.9683` | `0.9850` | `3.27` | `-0.10` | `\$0.93` | `5.25` | `\$0.0587` |
| `gemini-3.5-flash-lite` | **`harness2_k2_evolved`** | **`1,743`** | **`0.9848`** | **`0.9848`** | **`0.9850`** | **`0.9850`** | **`0.9834`** | **`0.9850`** | **`3.27`** | **`-0.10`** | **`\$0.84`** | **`5.20`** | **`\$0.0502`** |

### 4.2 3-Model Aggregate Comparison Across Gen 5 Arms

| Runbook Arm | Total Words | Word Reduction vs Seed | Mean Harbor 60/20/20 | Mean GEPA Fitness | Mean $d'$ | Mean Operational Loss ($L$, USD) | Mean Tool Calls | Total Safety Violations |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `seed_runbooks` | `3,648` | `0.0%` | `0.9744` | `0.9584` | `2.91` | `\$16,834.40` | `5.53` | `0` |
| `gepa_single_proposer` | `1,988` | `-45.5%` | `0.9787` | `0.9627` | `2.91` | `\$33,417.74` | `5.57` | `0` |
| **`harness2_k2_evolved`** | **`1,743`** | **`-52.2%`** | **`0.9804`** | **`0.9804`** | `2.89` | **`\$1,834.24`** (**`-89.1%`** vs seed, **`-94.5%`** vs single-proposer) | **`5.30`** | **`0`** |

### 4.3 Cost Staircase Walk (`cost_staircase_report.json`)

- **Ceiling Model**: `gemini-2.5-flash` (`0.9723`)
- **Selected Most Cost-Effective Model**: `gemini-2.5-flash-lite` (`0.9840`, within tolerance `0.05` and outscoring the ceiling model by `+0.0117` while cutting token cost by `-60.4%`, from `\$0.1809` to `\$0.0716`).

| Rung Model Tier | Mean Score | Min Loss Penalty | Passed Safety | Within Tolerance (`0.05`) | Tokens In | Tokens Out | Mean Latency (ms) | Token Cost (USD) |
| :--- | ---: | ---: | :---: | :---: | ---: | ---: | ---: | ---: |
| `gemini-2.5-flash` | `0.9723` | `1.00` | `True` | `True` | `305,348` | `35,720` | `22,011.0` | `\$0.1809` |
| `gemini-3.5-flash-lite` | **`0.9848`** | `1.00` | `True` | `True` | `326,151` | `43,928` | `9,132.0` | `\$0.0502` |
| `gemini-2.5-flash-lite` (Selected) | **`0.9840`** | `1.00` | `True` | `True` | `369,227` | `86,655` | `19,500.0` | `\$0.0716` |

---

## 5. Distilled Experience Library Rules (`EXPERIENCE.md` & `experience_library.jsonl`)

1. **Gen 5 Tier 1 (`docs/soc_eval_results/harness2_8h_campaign/gen5_flash_lite/EXPERIENCE.md` & `configs/runbooks/harness2_evolved/EXPERIENCE.md`)**:
   - **Entry 1 (`lateral_movement_hunt_psexec_wmi.md`)**:
     - **Scope**: `COMPOSED` | **Attribution**: `helped` | **Confidence**: `high` | **Mean Delta**: `+0.2187`
     - **Recorded Lesson**: `Updated lateral_movement_hunt_psexec_wmi.md (1074 -> 281 words) lifting validation fitness by +0.2187 with zero regressions: Use secops-mcp.get_threat_intel on T1021.002 (Remote Services: SMB/Windows Admin Shares) and T1047 (Windows Management Instrumentation) to inform query logic.; Formulate and execute UDM hunt queries using secops-mcp.search_security_events with hours_back=<time_frame_hours> and the optional <target_scope_query>.`
   - **Entry 2 (`malware_triage.md`)**:
     - **Scope**: `COMPOSED` | **Attribution**: `helped` | **Confidence**: `high` | **Mean Delta**: `+0.0528`
     - **Recorded Lesson**: `Updated malware_triage.md (843 -> 336 words) lifting validation fitness by +0.0528 with zero regressions: **Get File Reputation:** Call gti-mcp.get_file_report with hash=<file_hash> to get the file's threat intelligence report (<gti_report>).; **Check Host & Execution Context:** Call secops-mcp.lookup_entity on the alerted <hostname> (and secops-mcp.search_security_events if available) to verify active process execution or file creation on the host within <time_frame_hours>. Record the alerted <hostname> in AFFECTED_HOSTS.`

2. **Track 2 Proactive Threat Hunting (`docs/soc_eval_results/harness2_8h_campaign/threat_hunt/EXPERIENCE.md`)**:
   - **Cue**: `Track 2 Threat Hunt refinement (round 1)` (`gti_collection_threat_hunt.md`)
   - **Scope**: `DOM` | **Attribution**: `helped` | **Confidence**: `high` | **Mean Delta**: `+0.0782`
   - **Recorded Lesson**: `Updated gti_collection_threat_hunt.md (350 -> 347 words) lifting validation fitness by +0.0782 with zero regressions: Call get_collection_report and get_entities_related_to_a_collection (or get_domain_report and get_entities_related_to_a_domain) to extract indicators.; Call get_ioc_matches and search_security_events for extracted indicators, starting with hours_back=72.`
