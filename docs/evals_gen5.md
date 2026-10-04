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
| `just gen5-calibrate` | the four reference policies in both transports; writes `soc_eval_results/GEN5_CALIBRATION.md` |
| `just eval-gen5 [flavor] [split]` | run the suite on `train` or `validation` through the ledger |
| `just gepa-evolve ...` | the hillclimber, now on `--train-split train --val-split validation` by default |
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
| 1. Seed noise floor | `just gen5-noise 3` | mean spread <= 0.02 | pending |
| 2. Infra segregation | built in (`--infra-retries`, `infra_failure`) | no infra failure scored | by construction |
| 3. Headroom | `just eval-gen5 gemini-2.5-flash validation` | seed mean < 0.95 | pending |
| 4. Capability gradient | `just gen5-gradient <flavor> [endpoint]` per rung | report | pending |
| 5. Final test | hand-typed unseal after approval | pre-registration approved | sealed |

Record each result here when it lands, with the ledger entry's `run_id`.

## Owner checklist

```
Gen 5 owner checklist (spec 8.1 and 8.2)
[ ] Owner review gate (Plan 2, pending): approve the six OOD families as written (validation_ood: FAM-CRYPTOMINER-DEV, FAM-SAAS-BEACON-BENIGN; final_test_ood: FAM-PASSWORD-SPRAY, FAM-CLOUD-KEY-EXFIL, FAM-INSIDER-EXFIL, FAM-IMPOSSIBLE-TRAVEL-APPROVED), or name the family and the change. Any template edit -> just gen5-build && just gen5-check && just gen5-calibrate && just harbor-soc-gen5-generate && just harness-approve, then commit the regenerated artifacts.
[ ] Review the 16 family templates in configs/evals/gen5/families/ for defensible expected and
    prohibited actions; any edit -> just gen5-build && just gen5-calibrate && just harness-approve
    && just harbor-soc-gen5-generate, then commit the regenerated artifacts.
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
