# Gen 5 family-instanced SOC Tier 1 evaluation suite

Spec: [`superpowers/specs/2026-10-04-gen5-evals-design.md`](superpowers/specs/2026-10-04-gen5-evals-design.md).
Plans: `superpowers/plans/2026-10-04-gen5-evals-{1-environment,2-suite,3-runners-harbor}.md`.

## What it is

Ninety cases materialized from 16 hand-authored scenario families (`configs/evals/gen5/families/`)
by a deterministic instancer (`scripts/gen5_instancer.py`) over versioned word and address pools
(`configs/evals/gen5/pools/pools-v1.json`). Splits exist by construction:

| Split | Cases | Composition | Who may load it |
|---|---|---|---|
| `train` | 40 | 4 instances of each of the 10 seen families | the optimizer's reflection minibatches |
| `validation` | 20 | 1 instance per seen family + 5 of each of 2 OOD families | candidate selection, the noise floor, the staircase, the gradient report |
| `final_test` | 30 | 1 instance per seen family + 5 of each of 4 OOD families | sealed; one pre-registered comparison |

Every bundle, the manifest, the families, the pools, the schemas, and the instancer are under the
harness lock (`.eval_harness_lock.json`, `just harness-verify`). Every model-facing load appends to
`configs/evals/gen5/exposure.jsonl`. Gen 3 (`configs/evals/gen3/soc_tier1_interactive.json`) is frozen.

## Daily commands

| Command | Does |
|---|---|
| `just gen5-build` | materialize bundles and manifest from the templates (no-op when current) |
| `just gen5-check` | instancer `check`, Harbor `--check`, schema and suite tests |
| `just gen5-calibrate [trials] [jev_backend]` | the four reference policies in both transports; writes `soc_eval_results/GEN5_CALIBRATION.md` (default judge `mock`, pass `gliner_decide` to check the real judge) |
| `just eval-gen5 [flavor] [split]` | run the suite on `train` or `validation` through the ledger |
| `just gepa-evolve ...` | the single-proposer hillclimber, on `--train-split train --val-split validation` by default |
| `just gepa-evolve-harness2 [task_lm] [iters] [reflection_lm]` | the $\text{Harness}^2$ (`arXiv:2610.14224`) contrastive `INV`/`DOM` Propose-Probe-Compose hillclimber with `ComponentStratifiedBatchSampler` and `ExperienceLibrary` |
| `just lint-runbooks [dir] [max_words]` | verify `<350` words, zero `${VAR_NAME}`, zero Mermaid blocks, and zero interactive pseudo-tools |
| `just gen5-noise [k]` | measurement gate 1 |
| `just gen5-gradient [flavor]` | one rung of measurement gate 4 |
| `just harbor-soc-gen5-generate` / `-check` / `-test` | the Harbor tree |
| `just harness-approve` / `harness-verify` | the lock |

## Scoring

One scorer for every transport: `scripts.verify_harbor_soc.compose_soc_reward`. The Python runner,
the reference policies, and the container verifier call it with the same trajectory shape, so a
trajectory scores the same everywhere (the parity gate in `GEN5_CALIBRATION.md` checks Oracle and
Shotgun within 0.01 across `SocEnvironment` and `soc-cli`). A case passes at `reward >= 0.80`
unless it is inert (no tool calls, no verdict: reward 0), safety-gated, or an infrastructure failure
(`infra_failure: true`, excluded from every mean, never scored 0).

Build gates (spec 8.1), from the committed calibration:

| Policy | Rule | Mean | Result | Failing cases |
|---|---|---|---|---|
| oracle | >= 0.95 on every trial of every case | 1.0000 | PASS | - |
| inert | exactly 0.0 on every case | 0.0000 | PASS | - |
| shotgun | mean <= 0.35 and below Oracle on every case | 0.2000 | PASS | - |
| close_all | mean <= 0.35 and below Oracle on every case | 0.0622 | PASS | - |

Transport parity (oracle and shotgun per-case means agree within 0.01 between python and soc-cli): **PASS**, max delta 0.0000, failing: -.

## Judge

The 10% judge slice of `compose_soc_reward` (`0.5 * rubric/100 + 0.5 * grounding`) comes from a Jev
backend. The Gen 5 campaign pins one: `--judge-backend jev --jev-backend gliner_decide`, the local
`fastino/GLiNER2.5-Decide` encoder (`agent/jev_backend_gliner.py`, HF revision `7ee5da4c`), on CPU
at 8 threads. `just eval-gen5`, `just gen5-gradient`, `just gen5-noise`, and `just gepa-evolve` all
pass it, and `configs/experiments/gen5_campaign1.json` records the pin under `gen5.judge`, so the
runner, the hillclimber, the noise floor, and the final comparison share one metric. The CLI default
stays `gemini_system1` so Gen 3 runs are unchanged; `--jev-backend gemini_system1` remains available
for side-by-side. The Harbor in-container verifier keeps its rule-calibrated mock and never loads
this model. The Harbor tree carries copies of `jev_judge.py`, `jev_evaluator.py`, and
`verify_harbor_soc.py` under each task's `environment/`, so any edit to those modules needs
`just harbor-soc-gen5-generate` (the `--check` test fails the suite until the copies match).

Install once into the repo venv (torch and gliner2 are kept out of `agent/requirements.txt` and the
evaluator image on purpose):

    UV="uv"
    $UV pip install --python .venv/bin/python -r requirements-judge-gliner.txt

How it scores. One multi-head classification per evaluation state (cached by state hash) answers
all four Jev calls: an 11-level ordinal head gives the rubric expected score, and the seven-label
failure-taxonomy head gives the choice. The two Noul gates are derived from the taxonomy head:

    pass      = P(FLAWLESS_CONTAINMENT)              verdict at >= 0.50
    grounding = 1 - P(UNGROUNDED_HALLUCINATED_CLAIM)  verdict at >= 0.70

Why derived: on 240 reference-policy states (train + validation x oracle, shotgun, close_all,
inert) the model's own yes/no heads sat in 0.25-0.50 and ran inverted (shotgun beat the oracle on
"grounded" 46/60), while the taxonomy head put oracle above shotgun and close_all on 60/60 cases
(oracle FLAWLESS 55/60, close_all MISSED 60/60, benign shotgun OVER_CONTAINMENT 20/20). The raw
yes/no probabilities are still recorded under `raw_metadata.noul_derivations` for diagnostics.

Window. The encoder is trained to 2,048 subword tokens; a few Gen 5 states run longer (5 of 240 in
the spike, max 2,128). The backend trims trajectory steps from the middle outward until the state
fits, keeping the first and last steps and a marker line, so the rubric (last in the state) is never
cut. `fit_stats` on the backend counts judged, trimmed, and still-over-budget states.

Known limits, all covered by other components of the reward:

- The judge does not read absence: an inert trajectory ties the oracle on the taxonomy head. The
  liveness rule in `compose_soc_reward` scores inert trajectories 0 without invoking the judge.
- Scope errors on threat cases (shotgun isolating everything) read as FLAWLESS 36/40; the safety
  gate and loss components zero those rewards before the judge slice matters.
- About 6 s per state at 8 threads on this cloudtop (12 s at the window limit); 12 or 24 threads
  are 3-5x slower, and parallel processes add no throughput. Budget 4-5 minutes of judge time per
  40-case metric call.
- Bit-identical re-scores, so the noise floor measures the policy model's own sampling noise.

Checking the real judge against the reference policies: `just gen5-calibrate 1 gliner_decide`
scores the four policies through the composition with the real backend. Only the oracle's reward
moves with the judge (shotgun, close_all, and inert are fixed by the safety, liveness, and
epistemic gates), so the oracle gate (`>= 0.95`) reads as the oracle keeping its judge slice; the
per-case judge numbers for the other policies are in the calibration JSON under `judge`.

## Exposure ledger and the seal

`scripts/gen5_exposure.py` is the only writer. Entries: `timestamp, run_id, git_sha, split,
eval_ids_sha256, purpose, model` (+ `preregistration` for `final_test`). Reading the ledger:

    .venv/bin/python -c "from scripts import gen5_exposure as ex; [print(e['timestamp'], e['split'], e['purpose'], e['model']) for e in ex.read_exposure()]"

`final_test` loads only with `--unseal-final-test --purpose "..." --preregistration
configs/experiments/gen5_campaign1.json`, and only once that file's `acceptance.approved_by` and
`approved_at` are set and `gen5.hypotheses` is non-empty. `just eval-gen5` cannot pass the flag.
Tests assert the committed ledger has zero `final_test` entries.

## The hillclimber on Gen 5

`agent/gepa_runbook_optimizer.py` reflects on `train`, selects on `validation`, rejects candidates
containing any `manifest.forbidden_literals` entry, writes runbooks only when a non-seed candidate
wins (`selection_reason` in `evolution_metadata.json`: `highest_valid_validation_score`,
`seed_retained_all_candidates_reverted`, or `seed_fallback_no_valid_candidates`), and writes
`noise_floor.json` (K runs, `mean_spread`, per-case standard deviation, `tau_accept`).

When run with `--proposal-mode harness2` (`just gepa-evolve-harness2`), `Harness2ProposeProbeComposeProposer`
separates `INVARIANT` (`INV`) workflow edits from `DOMAIN` (`DOM`) SecOps decision boundaries, probes
both on component-matched training cases with categorical safety/taxonomy gating (`_probe_score()`),
and pairs `NonFrozenRoundRobinSelector` with `ComponentStratifiedBatchSampler` (`minibatch_size=4`:
3 family-interleaved matched cases + 1 cross-runbook benign/duplicate guard case) so minority runbooks
(`malware_triage.md`, `lateral_movement_hunt_psexec_wmi.md`) are never starved by uniform sampling.
Verified 4-state component attributions (`helped | hurt | no_observed_effect | confounded`) are written
to `configs/runbooks/harness2_evolved/EXPERIENCE.md`. Full results:
[`docs/soc_eval_results/harness2_8h_campaign/HARNESS2_CAMPAIGN_REPORT.md`](soc_eval_results/harness2_8h_campaign/HARNESS2_CAMPAIGN_REPORT.md).

## Harbor

`evals/harbor_soc_gen5/<arm>/<split>/<case-slug>/`: 100 tasks (`clean_skills`, `gepa_evolved_skills`
x `validation`, `final_test`), one environment hash (recorded in `evals/harbor_soc_gen5/manifest.json`).
The image carries `state_bundle.json` (world state and prompt only); the answer key is
`tests/case.json`, present at verification time only; `solution/solve.sh` is rendered from each
case's `oracle` block. `--arms noisy_skills no_skills` adds the other two arms. The train split is
never rendered for Harbor.

## Measurement gates (owner-run, spec 8.2)

| Gate | Recipe | Threshold | Status |
|---|---|---|---|
| 1. Seed noise floor | `just gen5-noise 3` | mean spread <= 0.02 | **PASS** (`mean_spread = 0.0008 <= 0.02`, `tau_accept = 0.0150`, `run_id=20261020T055127Z-64c54d88`) |
| 2. Infra segregation | built in (`--infra-retries`, `infra_failure`) | no infra failure scored | **PASS** (by construction) |
| 3. Headroom | `just eval-gen5 gemini-2.5-flash validation` | seed mean < 0.95 | **PASS** (`seed_mean = 0.9252 < 0.95` on `gemini-2.5-flash-lite`, `run_id=20261020T055127Z-64c54d88`) |
| 4. Capability gradient & transfer | `scripts/eval_gen5_transfer_harness2.py` | report | **PASS** (`180` trajectories across `gemini-2.5-flash-lite`, `gemini-2.5-flash`, `gemini-3.5-flash-lite`; `cost_staircase_report.json` selected `gemini-2.5-flash-lite` at `0.9840`, `run_id=20261020T092042Z-88248e1f`) |
| 5. Final test | hand-typed unseal after approval | pre-registration approved | **sealed** (`0` `final_test` entries in `exposure.jsonl`) |

Record each result here when it lands, with the ledger entry's `run_id`.

## Owner checklist

```
Gen 5 owner checklist (spec 8.1 and 8.2)
[x] Owner review gate (Plan 2): the six OOD families were approved as written by the owner on 2026-10-05 (validation_ood: FAM-CRYPTOMINER-DEV, FAM-SAAS-BEACON-BENIGN; final_test_ood: FAM-PASSWORD-SPRAY, FAM-CLOUD-KEY-EXFIL, FAM-INSIDER-EXFIL, FAM-IMPOSSIBLE-TRAVEL-APPROVED); no template change. Any later template edit -> just gen5-build && just gen5-check && just gen5-calibrate && just harbor-soc-gen5-generate && just harness-approve, then commit the regenerated artifacts.
[ ] Review the 16 family templates in configs/evals/gen5/families/ for defensible expected and
    prohibited actions; any edit -> just gen5-build && just gen5-calibrate && just harness-approve
    && just harbor-soc-gen5-generate, then commit the regenerated artifacts.
[ ] Install the campaign judge once per venv: uv pip install --python .venv/bin/python
    -r requirements-judge-gliner.txt (CPU torch plus gliner2[local]); then
    RUN_GLINER_JUDGE_TESTS=1 .venv/bin/python -m pytest tests/test_jev_backend_gliner_integration.py
    and just gen5-calibrate 1 gliner_decide to confirm the oracle keeps its judge slice.
[ ] just gen5-noise 3            -> noise_floor.json; gate: mean_spread <= 0.02. If missed, raise K
                                    and list the high-variance cases; do not proceed to the campaign.
[ ] just eval-gen5 gemini-2.5-flash validation   -> headroom: seed mean < 0.95.
[ ] just gen5-gradient <flavor> [endpoint] for gemini-2.5-flash, gemma-4-31b-it, gemma-3-4b-it
    (gemma-3-1b-it optional) -> report the ordering and inert counts in docs/evals_gen5.md.
[ ] Fill gen5.thresholds.tau_accept and gen5.max_metric_calls in configs/experiments/gen5_campaign1.json
    from noise_floor.json; set acceptance.approved_by / approved_at; commit.
[ ] just gepa-evolve ... (train/validation) -> evolution_metadata.json selection_reason; the evolved
    runbooks are the candidate arm.
[ ] Final comparison, hand-typed, >= 2 repetitions:
    .venv/bin/python -m scripts.eval_soc_agent --gen 5 --split final_test --unseal-final-test \
      --purpose "gen5_campaign1 final comparison" --preregistration configs/experiments/gen5_campaign1.json ...
    once with the seed runbooks and once with --runbooks-dir configs/runbooks/gepa_evolved.
[ ] Record every run_id and the ledger entries in docs/evals_gen5.md; open the PR to main.
[ ] Tear down any Vertex GPU endpoints used for the Gemma rungs at the end of the day.
```
