# Disciplined Hillclimber run analysis: the 2026-10-02 GEPA runbook evolution

Author: Dan Dye
Written: 2026-10-04
Branch: `disciplined_hillclimber_v0001` (harness code at `b4fd8d2`, run artifacts committed at `26c4a8e`)
Status: evidence review of committed artifacts. No new rollouts were executed for this document.

This document reads the artifacts that the first full Disciplined Hillclimber run wrote to `configs/runbooks/gepa_evolved/` and states what they do and do not support. It follows the same rule as [GEPA_EVIDENCE_RECONCILIATION.md](GEPA_EVIDENCE_RECONCILIATION.md): every number below is copied from a committed file whose SHA-256 is listed, and every dollar figure is an output of the simulated loss model, not a realized saving.

The short version. The five guards did their job and accepted nothing. GEPA proposed two candidates, both landed inside the seed runbooks' own run-to-run variance, both were reverted, and the optimizer then wrote the unmodified seed runbooks back to the output directory. That last step overwrote the four-stage evolved `basic_ioc_enrichment.md` from 2026-09-04 that the blog post quotes. The evolved text still exists at commit `b4fd8d2`.

## Artifacts

| Role | Path | SHA-256 | Notes |
| --- | --- | --- | --- |
| Run metadata | `configs/runbooks/gepa_evolved/evolution_metadata.json` | `f83d278aa76f94735b58e852cc4fc6c5ad4cda6ea3a96f80cb7db3c2b698d948` | Written by `save_runbooks()` |
| Acceptance ledger | `configs/runbooks/gepa_evolved/hillclimb_ledger.jsonl` | `34ec16d40b35063cbb1d02aa14f1bc014cfbd7ad939b528086e91c47b45b476f` | 3 entries |
| Cost staircase | `configs/runbooks/gepa_evolved/cost_staircase_report.json` | `25455e5b72b76f436f3ee87afaf36c46b5ab026984a32a24deb6023651c840e8` | 5 rungs |
| Harness lock | `.eval_harness_lock.json` | `14af323c82b5fe890ad51e6e0ff850db4e28071f5449c5868dc6ebe916cd8c64` | Composite `af9f67a5...01e5` |
| Output runbook | `configs/runbooks/gepa_evolved/basic_ioc_enrichment.md` | `a8d1b0b100227a44557d1c01d45be93086b76a96284e083a13e0d4add6f285ac` | Byte-identical to seed |
| Output runbook | `configs/runbooks/gepa_evolved/suspicious_login_triage.md` | `10d64b2edff4cd9f27cc105a318adab617adc87f8e4f4daa1f82a5c2c75e8d7d` | Byte-identical to seed |
| Output runbook | `configs/runbooks/gepa_evolved/malware_triage.md` | `e927294eaefff2ebbdfd22bbb0e1c441ba2c1476e384d15fdc720d70d1b4881d` | Byte-identical to seed |
| Output runbook | `configs/runbooks/gepa_evolved/lateral_movement_hunt_psexec_wmi.md` | `64a4390d0dad2547237739e19c582fb9b33fc9ee3c796ca3e024db4d1a0770ec` | Byte-identical to seed |
| Prior evolved runbook | `git show b4fd8d2:configs/runbooks/gepa_evolved/basic_ioc_enrichment.md` | `3d86b8e3a0801d2f7ec1409bdaca2269c455c1c5739db74994245347d746d0fc` | 9,386 bytes, the four-stage version |

The seed runbooks are the four `CORE_RUNBOOKS` loaded by `load_seed_runbooks()` from `third_party/ai-runbooks/.clinerules/run_books/` (submodule at `f7a049ed`).

The harness lock pins the five protected files at the SHA-256 values below. Every ledger entry stamps the composite hash, so any score in this document is tied to exactly this dataset, sandbox, verifier, and cost engine.

| Protected file | SHA-256 |
| --- | --- |
| `configs/evals/gen3/soc_tier1_interactive.json` | `ee815b6f3952e64e7f462360c23c8b37184a5f2af11991b2f40e621279b7836c` |
| `agent/soc_environment.py` | `ccdce9786681ca323220b0d8b82c73a2b32ddbf12edda70b12ab4d344c9550fa` |
| `scripts/eval_trajectory_verifier.py` | `da96537710f98ccfed439a107f04e6cba35f0cfb1993906e15b9e428fc8353a2` |
| `scripts/eval_cost_engine.py` | `226218bdc3ed2f563aa0064ee09152730c43d048521a1a59add87de9703fd281` |
| `scripts/eval_soc_agent.py` | `43acf4ae81f7e2ff2cb5468b4f36ea76e3c7b050032fede37ac551b9a30d7a3e` |

## Run configuration

From `evolution_metadata.json` and the commit message of `26c4a8e`:

| Setting | Value | Source |
| --- | --- | --- |
| Task model (policy) | `gemini-2.5-flash-lite` | metadata |
| Reflection model (proposer) | `gemini-2.5-pro` | metadata |
| `max_metric_calls` | 20 | metadata |
| `seed` | 42 | metadata |
| Candidate selection | `pareto` | code, `gepa.optimize(...)` |
| Train / validation split | `--split-train-val` (cases 1 to 6 train, cases 7 to 10 validation) | commit message, code |
| Inner-loop judge | `--judge-backend jev` | commit message |
| Noise runs | 2 | metadata (`noise_floor` block present) |
| `min_delta` | 0.015 | metadata |
| `max_growth_ratio` | 1.35 | code default |
| Cost staircase tolerance | 0.05 | metadata |

Two provenance gaps. The metadata file does not record the split, the judge backend, the growth ratio, or the full command line, so three of the rows above come from the commit message and code defaults rather than the artifact. And the commit title says "20 generations" when the run had 20 metric calls. With a four-case validation set, 20 metric calls paid for the seed's validation pass and two proposals that reached full validation. There were two mutations, not twenty.

## Timeline

| UTC | Event | Source |
| --- | --- | --- |
| 02:43:51 | Harness lock approved (`--approve-harness`) | `.eval_harness_lock.json` `approved_at_utc` |
| 03:11:31 | Three ledger entries written within 15 ms of each other | `hillclimb_ledger.jsonl` |
| 03:16:04 | Commit `26c4a8e` | `git log` |

Two things follow from the timestamps. First, the ledger is written after `gepa.optimize()` returns, in a loop over `result.candidates` (see `agent/gepa_runbook_optimizer.py` around lines 993 to 1067). It is append-only on disk, but it is a reconstruction, not a stream. The `iteration` field is the candidate index in GEPA's result, `train_score` is always `null`, and nothing GEPA did on the train minibatches is recorded. Second, the cost staircase runs after the ledger is written, so all 20 staircase rollouts (five rungs times four validation cases) finished between 03:11:31 and 03:16:04. I come back to that under the staircase section.

## Step 0 noise floor

`estimate_noise_floor()` evaluated the seed runbooks on the four validation cases twice before GEPA started:

| Quantity | Value |
| --- | ---: |
| Run 1 mean | 0.65025 |
| Run 2 mean | 0.65050 |
| Aggregate noise, `abs(run1 - run2)` | 0.00025 |
| Mean per-case noise, `mean(abs(case_a - case_b))` | 0.14225 |
| `tau_accept = max(0.015, 1.5 * 0.00025)` | 0.015 |

Then GEPA evaluated the same seed on the same four cases a third time as candidate 0 and scored it 0.6194.

So three evaluations of identical runbooks on identical cases produced 0.650, 0.651, and 0.619. The spread is 0.031, about twice the acceptance threshold. The two noise runs happened to agree to four decimal places while the per-case scores moved by 0.142 on average, which means the agreement was cases cancelling each other out, not a quiet system. `tau_accept` ended up carried entirely by the `min_delta` floor. The 0.015 default happened to be the right order of magnitude, but the estimator did not earn it.

Two evaluations are not enough to estimate a noise band for a four-case agentic benchmark. RRSI's version of this mechanism repeatedly evaluates the unchanged base harness and uses the resulting band both for acceptance and for stall detection. The cheapest fix here is to count GEPA's own baseline pass as a third sample and to set the threshold from the per-case band rather than the aggregate.

## Acceptance ledger

| Candidate | Validation score | Delta vs seed | Regressed cases | Decision |
| ---: | ---: | ---: | --- | --- |
| 0 (seed) | 0.6194 | | | `KEPT` (baseline) |
| 1 | 0.6322 | +0.0128 | none | `REVERTED_NOISE` |
| 2 | 0.6230 | +0.0036 | none | `REVERTED_NOISE` |

Both proposals cleared the anti-memorization validator (no `REJECTED_INVALID` entries) and neither regressed a passing case. Both deltas sit inside the 0.031 band the seed produced on its own. Rejecting them was correct, and would still have been correct under a properly estimated threshold.

One wording problem. The seed is candidate 0, and the selection loop logs index 0 through the `else` branch as `KEPT` before any gating applies. Because `selected_index` is therefore `0` rather than `None`, `selection_reason` in the metadata reads `highest_valid_validation_score`. The code's `seed_fallback_no_valid_candidates` label only fires when no candidate at all, including the seed, survives. A reader of the metadata alone would conclude a candidate won. None did.

## Cost staircase

`run_cost_staircase_walk()` then evaluated the selected candidate, which was the seed, on the four validation cases at each rung:

| Rung | Mean score | `min_loss_penalty` | `passed_safety` | `within_tolerance` |
| --- | ---: | ---: | --- | --- |
| `gemini-2.5-flash` (ceiling) | 0.73025 | 1.0 | true | true |
| `gemma-4-31b-it` | 0.325 | 1.0 | true | false |
| `gemma-4-e4b-it` | 0.336 | 1.0 | true | false |
| `gemma-3-4b-it` | 0.336 | 1.0 | true | false |
| `gemma-3-1b-it` | 0.311 | 1.0 | true | false |

Selected model: `gemini-2.5-flash` at 0.73025. No Gemma rung came within the 0.05 tolerance.

Three caveats, in decreasing order of confidence.

The staircase walked the seed. Nothing in this table says anything about evolved runbooks, because none were accepted. The ceiling score of 0.730 is "human-written community runbooks on `gemini-2.5-flash`, four validation cases, one pass".

`passed_safety` is vacuous for an inert agent. `calculate_loss_penalty()` returns `exp(0) = 1.0` when there are no prohibited actions and no verdict that mismatches the label. An agent that calls no tools and emits no verdict gets a perfect loss penalty. The safety gate as written cannot distinguish "contained the right hosts and left the right hosts alone" from "did nothing". The gate needs a liveness requirement, such as `epistemic_step_count >= 1` on every case, which `scripts/eval_trajectory_verifier.py` already computes.

The Gemma rung scores should not be cited until someone has read the trajectories. Four models spanning 1B to 31B parameters scored 0.311 to 0.336, within 0.025 of each other, all with a perfect loss penalty. All 16 Gemma rollouts, plus the four Gemini ones, finished in under four and a half minutes. The adapter constructs `HierarchicalSOCTier1Agent(managed_model=tier, ...)` with no `endpoint_id`, and the report records neither the resolved endpoint nor the trajectories. The pattern is consistent with rollouts that failed fast and were scored as empty episodes. I cannot confirm that from the artifacts, which is the point: the staircase report needs to carry per-rung trajectory summaries and the resolved model endpoint before its numbers mean anything.

## Artifact integrity: the seed overwrote the evolved runbooks

`save_runbooks(candidate=best_candidate, output_dir=output_dir, ...)` at the end of `main()` writes whichever candidate was selected into `configs/runbooks/gepa_evolved/`. In this run the selected candidate was the seed. The four files in that directory are now byte-identical to the four seed files under `third_party/ai-runbooks/.clinerules/run_books/` (hashes in the artifacts table above).

Before this run, `configs/runbooks/gepa_evolved/basic_ioc_enrichment.md` held the four-stage "Structured IOC Triage and Response Runbook" produced on 2026-09-04 (Stage A through D, `${IOC_ROUTING_TYPE}`, Rules 1 to 3). That is the text quoted in the blog post and the text evaluated in `GEPA_RUNBOOK_EVALUATION_ANALYSIS.md` and `GEPA_EVIDENCE_RECONCILIATION.md`. It survives only in git history:

```bash
COMMIT="b4fd8d2"
RUNBOOK="configs/runbooks/gepa_evolved/basic_ioc_enrichment.md"

git show "$COMMIT:$RUNBOOK" > /tmp/basic_ioc_enrichment_evolved_2026-09-04.md
sha256sum /tmp/basic_ioc_enrichment_evolved_2026-09-04.md
# expected: 3d86b8e3a0801d2f7ec1409bdaca2269c455c1c5739db74994245347d746d0fc
```

A run whose honest outcome is "no change" should not be able to destroy the previous run's output. Two fixes, both small. Write each run into a timestamped directory (`configs/runbooks/gepa_evolved/runs/<utc>/`) and only update a `latest` pointer when a non-seed candidate is accepted. And when the seed is selected, write the metadata and ledger but refuse to write runbooks at all.

## What this run supports and what it does not

| Claim | Supported? | Why |
| --- | --- | --- |
| The harness lock was verified and stamped on every ledger entry | Yes | Composite hash matches in lock, ledger, and metadata |
| The noise gate rejected two sub-noise candidates | Yes | Ledger entries 1 and 2 |
| The noise gate's threshold was well estimated | No | K=2 aggregate agreement of 0.00025 against a per-case band of 0.142 and a third seed sample 0.031 away |
| GEPA found an improved runbook at this budget | No | Nothing accepted; the seed was written back |
| The evolved runbooks run on `gemini-2.5-flash` at 0.730 | No | The staircase walked the seed, not an evolved candidate |
| Gemma 4 31B scored 0.325 on the validation set | Not yet | Trajectories and endpoint resolution are not in the artifacts; pattern consistent with inert rollouts |
| `passed_safety: true` means the Gemma rungs made safe decisions | No | Loss penalty is 1.0 for an agent that does nothing |
| Twenty generations were run | No | Twenty metric calls, two mutations |
| `selection_reason: highest_valid_validation_score` means a candidate won | No | Index 0 is the seed and is logged `KEPT` unconditionally |

## Recommended fixes

In priority order, with the code they touch.

1. Stop overwriting on seed selection. In `agent/gepa_runbook_optimizer.py` `main()`, write runbooks only when `selected_index` is not `None` and not `0`; write metadata and ledger regardless; use per-run output directories.
2. Report seed selection honestly. Set `selection_reason` to `seed_selected_no_candidate_cleared_gate` when `selected_index == 0`, and surface it in the ledger rationale.
3. Estimate noise from at least three samples and from the per-case band. In `agent/hillclimb_harness.py` `estimate_noise_floor()`, accept a list of runs, include GEPA's candidate-0 scores as a sample, and set `tau_accept` from `mean_case_noise` scaled by `1/sqrt(n_cases)` rather than from the aggregate difference alone.
4. Add a liveness requirement to the staircase safety gate. In `run_cost_staircase_walk()`, require `epistemic_step_count >= 1` and a non-empty verdict on every case before `passed_safety` can be true.
5. Record what the staircase actually called. Per rung, persist the resolved model or endpoint, per-case tool counts, verdicts, and the episode-level `SOC_FAILURE_TAXONOMY` choice from Jev.
6. Record the full command line in `evolution_metadata.json`, including split, judge backend, growth ratio, and noise runs.
7. Write the ledger during the run, not after. Wrap `adapter.evaluate()` so each full-validation evaluation appends an entry with a real timestamp, and keep the post-hoc reconstruction only as a cross-check.
8. Rename the budget in commit messages and logs. `max_metric_calls` is a count of evaluations, not generations.

## Relationship to RRSI

Xia et al. (2026) describe harness evolution as an estimation problem that overfits unless both the proposer and the selector are regularized. Their selection-side mechanisms, stability-aware acceptance against a measured noise band and complexity-aware acceptance against a cost budget, are what guards 2 and 5 in this repo approximate. Their ablation is the relevant warning: removing acceptance constraints raised their evolve-set score from 90.5 to 91.5 while dropping the out-of-distribution average from 43.6 to 41.0 and spending about 50% more tokens. The 2026-10-02 run is the constrained loop behaving as designed, which at this budget means declining to accept anything.

The mechanism-by-mechanism comparison, including what this harness still lacks (structural pruning, an edit budget, a proposer that reads the ledger), is in [hillclimber_rrsi_crosswalk.md](../hillclimber_rrsi_crosswalk.md). The out-of-distribution evidence that the earlier evolved runbooks did not transfer to a container sandbox (Campaign 5 on branch `harbor_soc_evals_v0001`) is summarized there and in the blog post.

## References

Full annotated entries are in [references_agent_harness_literature.md](../references_agent_harness_literature.md).

- Xia, P., Han, R., Wang, Z., et al. (2026). RRSI: Regularized Recursive Self-Improvement of Agent Harnesses. arXiv:2609.24972.
- Ding, W., Lu, Q., Yu, C., et al. (2026). Harness-Delta Attribution: What Evolves When We Talk About Harness Evolution? UT Austin blog.
- Agrawal, L. A., et al. (2025). GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning. arXiv:2507.19457.
- Anthropic (2026). Hill-Climbing on an Eval: Iteratively Improving Claude Applications. `anthropics/skills`, `claude-api/shared/evals/eval-hillclimb.md`.
- Dwork, C., Feldman, V., Hardt, M., Pitassi, T., Reingold, O., Roth, A. (2015). Generalization in Adaptive Data Analysis and Holdout Reuse. NeurIPS 28.
