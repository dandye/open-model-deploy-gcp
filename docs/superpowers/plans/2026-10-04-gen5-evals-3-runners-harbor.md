# Gen 5 Evals, Plan 3 of 3: Runners, Hillclimber, Harbor, Docs, and Harness Lock Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Gen 5 suite the default for every model-facing path: the eval runner loads splits through an append-only exposure ledger and scores with the shared Harbor composition; the GEPA optimizer trains on `train`, selects on `validation`, rejects candidates that contain manifest literals, and never overwrites the seed again; the hillclimb harness measures a K-run noise floor, locks the Gen 5 inputs, and reports inert staircase rungs honestly; `soc-cli` and the Harbor generator produce a checked-in `evals/harbor_soc_gen5/` tree whose oracle scores 1.0 inside the container; docs, recipes, the pre-registration file, and the harness lock close the loop.

**Architecture:** One new module, `scripts/gen5_exposure.py`, owns split loading and the ledger; every model-facing loader goes through it, nothing else writes the ledger. `scripts/eval_soc_agent.py` gains a Gen 5 branch that calls `compose_soc_reward` (Plan 2 Task 6) per case, so the Python runner, the reference policies, and the container produce the same scorecard for the same trajectory. `agent/gepa_runbook_optimizer.py` keeps its fitness formula and adds the three Gen 5 verifier kwargs, the manifest literal guard, split loading, and the two run-analysis fixes. `agent/hillclimb_harness.py` generalizes the noise floor to K runs and the protected paths to directories. `scripts/generate_harbor_soc_tasks.py` grows a Gen 5 mode that ships a stripped state bundle in the image and the answer key only under `tests/`, with `solution/solve.sh` rendered from the case's `oracle` block through `plan_oracle`, the same planner the calibration uses.

**Tech Stack:** Python 3.13 (`.venv/bin/python`), pytest 8, `tomllib`, `just`, bash for the Harbor scripts. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-04-gen5-evals-design.md`, sections 6.6, 6.7, 7.3, 8.2, 8.3, 9.2, 9.4, 9.5. Plans 1 and 2 (`2026-10-04-gen5-evals-1-environment.md`, `2026-10-04-gen5-evals-2-suite.md`) must be complete and committed: this plan consumes replace-mode `SocEnvironment`, the committed bundles and manifest under `configs/evals/gen5/`, `scripts/gen5_instancer.py`, `scripts/gen5_reference_policies.py` (`plan_oracle`, `plan_policy`, `execute_python`, `score_records`, `run_policy_on_case`, `evaluate_gates`, `render_markdown`, `write_reports`, `command_run`, `command_calibrate`), `compose_soc_reward` and `evaluate_harbor_soc_trial` in `scripts/verify_harbor_soc.py` (with `--evalset-file`, `--manifest-file`, `--metrics-file`, `--split`), and the Gen 5 verifier kwargs (`prohibited_entities`, `liveness`, `generation`) with result fields `.inert` and `.prohibited_entity_violations`.

## Global Constraints

- Gen 3 is frozen. `tests/test_gen3_soc_environment_parity.py`, `tests/test_gen3_trajectory_verifier.py`, `tests/test_gen3_cost_engine.py`, `tests/test_verify_harbor_soc.py`, `tests/test_harbor_soc_tasks.py`, `tests/test_soc_sandbox_cli.py`, and every existing test in `tests/test_eval_soc_agent.py`, `tests/test_gepa_runbook_optimizer.py`, and `tests/test_hillclimb_harness.py` stay green after every task, except where a task below says exactly which assertion changes and why. Every Gen 5 branch is gated on `int(case.get("generation") or 0) >= 5` (per case) or `eval_gen >= 5` (per run); Gen 3 case dicts carry no `generation` key. `evals/harbor_soc/**` (the Gen 3 Harbor tree) is not regenerated and not edited.
- No model calls and no ledger writes from tests. Tests that exercise Gen 5 loaders set the `GEN5_EXPOSURE_LEDGER` environment variable (via `monkeypatch.setenv`) to a path under `tmp_path`, or pass `ledger=` explicitly. A test that appends to `configs/evals/gen5/exposure.jsonl` is a bug. Model-facing code paths in tests use `--judge-backend mock` plus patched agents, as `tests/test_eval_soc_agent.py` already does.
- `final_test` stays sealed through this plan. No task runs anything against `final_test` beyond the Harbor generator (which reads the bundle to render tasks and never appends to the ledger) and the reference policies (same). The committed ledger must have zero `final_test` entries at the end of every task; `tests/test_gen5_exposure.py` asserts it.
- The measurement gates of spec section 8.2 cost tokens and are owner-run. This plan prepares them (recipes, flags, reports, the pre-registration file) and ends with a printed checklist. It does not run them.
- ASCII only in code, tests, docs, generated task files, and commit messages. No emojis. No em dashes. Stage files by explicit path; never `git add .` or `git add -A`.
- Run tests with `.venv/bin/python -m pytest -q` from the repository root (`pytest.ini` sets `pythonpath = .`). Worktree: `gemma_deploy__worktrees/gen5_evals_v0001`, branch `gen5_evals_v0001`. Shell `grep` and `find` are blocked by a hook in this environment; use `awk`, Python, or the editor tools.
- `agent/hillclimb_harness.py` uses 2-space indentation; keep it. Everything else uses 4 spaces.
- Import direction: `scripts/verify_harbor_soc.py` must never import `scripts.eval_soc_agent` (it does not today), because `eval_soc_agent` imports `compose_soc_reward` from it, and `agent/gepa_runbook_optimizer.py` imports `evaluate_assertions` from `eval_soc_agent`. `scripts/gen5_reference_policies.py` is imported lazily inside the runner's mock branch, not at module top.
- The harness lock `.eval_harness_lock.json` is re-approved exactly once, in Task 7, after every protected file has reached its final bytes. Tasks 1 to 6 pass `--lock-file` under `tmp_path` in tests and never touch the committed lock.

---

## File map

| File | Responsibility |
|---|---|
| `scripts/gen5_exposure.py` (create) | bundle paths, split loader, family and difficulty filters, final_test seal, pre-registration check, ledger append and read |
| `configs/evals/gen5/exposure.jsonl` (create, empty) | the append-only ledger |
| `scripts/eval_soc_agent.py` (modify) | `--gen 5`, `--split`, `--families`, `--difficulty`, `--unseal-final-test`, `--purpose`, `--preregistration`, `--infra-retries`; Gen 5 scoring through `compose_soc_reward`; infra segregation; `summarize_gen5`; report section |
| `agent/gepa_runbook_optimizer.py` (modify) | `--train-split` / `--val-split`, manifest literal guard, Gen 5 verifier kwargs, inert and entity-violation fitness, no-overwrite save, `selection_reason`, `--noise-runs K`, `--noise-only`, `noise_floor.json`, staircase telemetry |
| `agent/hillclimb_harness.py` (modify) | `estimate_noise_floor(*runs)`, `NoiseFloorMetrics` K-run fields, `write_noise_floor_json`, `SHARED_SCORING_PATHS` / `GEN5_PROTECTED_PATHS` / `LEGACY_PROTECTED_PATHS`, directory expansion in `compute_manifest`, `CostRungResult` telemetry and `inert` |
| `scripts/harness_lock.py` (create) | `approve` and `verify` subcommands over `HarnessIntegrityGuard` with the default protected paths, no model code imported |
| `scripts/soc_sandbox_cli.py` (modify) | Gen 5 bundle discovery, `SOC_EVALSET_FILE`, strict lookup for `CASE-GEN5-` ids |
| `scripts/gen5_reference_policies.py` (modify) | `execute_soc_cli`, `--transport {python,soc-cli,both}`, transport parity gate in `evaluate_gates` and the report |
| `scripts/generate_harbor_soc_tasks.py` (modify) | Gen 5 mode (default): `--evalset`, `--split`, `--arms`, `--out`, `--check`, `--gen3` for the frozen recipe; state bundle; answer key under `tests/`; `solve.sh` from `plan_oracle`; tree manifest |
| `evals/harbor_soc_gen5/**` (generated, committed) | 100 tasks: `clean_skills` and `gepa_evolved_skills` times `validation` and `final_test` |
| `Justfile` (modify) | `harbor-soc-gen5-generate`, `harbor-soc-gen5-check`, `harbor-soc-gen5-test`, `gen5-noise`, `gen5-gradient`, `harness-approve`, `harness-verify`; `gen5-check` extended |
| `configs/experiments/gen5_campaign1.json` (create) | pre-registration from the evidence comparison template, approval fields null until the owner signs |
| `configs/evals/gen3/soc_tier1_interactive.json` (modify, description only) | `frozen: true` note |
| `.eval_harness_lock.json` (regenerate once, Task 7) | lock over shared scoring, Gen 5, and legacy paths |
| `docs/evals_gen5.md` (create) | build, check, calibrate, run, optimize, Harbor, gates |
| `docs/experiment_protocol.md`, `docs/index.md`, `docs/thoughts_on_evals.md` (modify) | split names to bundles, ledger and unseal flag, catalog rows, spec pointer |
| `tests/test_gen5_exposure.py`, `tests/test_gen5_eval_runner.py`, `tests/test_gen5_transport_parity.py`, `tests/test_harbor_soc_gen5_tasks.py`, `tests/test_harness_lock.py` (create); `tests/test_gepa_runbook_optimizer.py`, `tests/test_hillclimb_harness.py`, `tests/test_soc_sandbox_cli.py`, `tests/test_gen5_reference_policies.py`, `tests/test_justfile_recipes.py` (extend) | tests per task |

Line numbers below refer to the files at commit `0ac24cd` plus the commits of Plans 1 and 2. They shift as tasks land; the quoted code anchors do not.

---

## Decisions fixed by this plan

1. **Ledger scope.** Only model-facing loaders append: `run_evaluation` in Gen 5 mode and `gepa_runbook_optimizer.main`. The instancer, the reference policies, the Harbor generator, `soc-cli`, and tests read bundles directly and never append. An entry carries exactly the seven spec keys (`timestamp`, `run_id`, `git_sha`, `split`, `eval_ids_sha256`, `purpose`, `model`); a `final_test` entry adds an eighth key, `preregistration: {"path", "sha256"}`, because spec 8.2.5 requires the approval to be recorded in the ledger. `eval_ids_sha256` hashes the sorted eval ids actually loaded, so a filtered load hashes differently from the full split, which is the point.
2. **Final test seal.** `load_split("final_test", ...)` raises `FinalTestSealedError` unless `unseal_final_test=True`, `purpose` is non-empty, and `preregistration` points at a JSON file whose `acceptance.approved_by` and `acceptance.approved_at` are non-null and whose `gen5.hypotheses` list is non-empty. The gate runs before any agent construction or client creation.
3. **One scorer.** Gen 5 cases in the Python runner are scored by `compose_soc_reward` with the in-memory trajectory, the response text as the report, the parsed `soc_decision` block as `decision_data`, and a metrics dict (`tokens_in`, `tokens_out`, `latency_ms`, `infra_failure`). A case passes when `reward >= 0.80` and it is neither inert, safety-gated, nor an infra failure. `rubric_score` in the per-case record is `round(reward * 100, 1)` so the existing report columns keep working.
4. **Infrastructure segregation.** An exception from `agent.query` whose text matches an infra marker (429, `RESOURCE_EXHAUSTED`, quota, rate limit, timeout, deadline, 500, 502, 503, 504, unavailable, overloaded, connection) is retried `--infra-retries` times (default 2) with a module-level backoff constant tests set to 0. If every attempt fails, the case record has `infra_failure: true`, `gen5_reward: null`, `passed: false`, and is excluded from `calculate_aggregate_score` and from every mean in `summarize_gen5`. Any other exception propagates as today.
5. **GEPA fitness.** `calculate_case_fitness` weights are unchanged. For Gen 5 cases the adapter passes `prohibited_entities`, `liveness`, and `generation` to the verifier; an inert trajectory scores fitness 0.0 with `inert: true` in the trace; a prohibited-entity violation adds the prohibited-action loss through the new `calculate_loss_penalty(..., prohibited_violation=True)` argument (default `None` keeps Gen 3 numbers). The reflective dataset adds one feedback line for each of those two conditions.
6. **No-overwrite and selection reason.** `save_runbooks` is called only when a candidate other than the seed was selected. `selection_reason` is `highest_valid_validation_score` when a non-seed candidate was selected, `seed_retained_all_candidates_reverted` when candidates existed but none was accepted (or only the seed at index 0 was), and `seed_fallback_no_valid_candidates` when no valid candidate existed at all. `evolution_metadata.json` is always written and records `runbooks_written`, `run_id`, `train_split`, `val_split`, `exposure` (the two ledger entries), and `noise_floor` when measured.
7. **Noise floor.** `estimate_noise_floor(*runs, min_delta, multiplier)` accepts K >= 2 score lists; `run1_mean` / `run2_mean` keep their meaning for the first two runs, `aggregate_noise` becomes the mean spread (max minus min of the K run means), `mean_case_noise` stays the mean per-case spread (max minus min per case, which at K = 2 is today's absolute difference), a new `mean_case_std` carries the mean per-case standard deviation (spec 8.2.1), and `tau_accept = max(min_delta, multiplier * aggregate_noise)`. The K = 2 numbers equal today's. The optimizer writes `noise_floor.json` next to `evolution_metadata.json`, and `--noise-only` exits after writing it.
8. **Harness lock.** `DEFAULT_PROTECTED_HARNESS_PATHS = SHARED_SCORING_PATHS + GEN5_PROTECTED_PATHS + LEGACY_PROTECTED_PATHS`. Shared: `agent/soc_environment.py`, `scripts/eval_trajectory_verifier.py`, `scripts/eval_cost_engine.py`, `scripts/eval_soc_agent.py`, `scripts/verify_harbor_soc.py`. Gen 5: `configs/evals/gen5/manifest.json`, the three bundles, `families/`, `pools/`, `schema/`, `split_plan.json`, `scripts/gen5_instancer.py`. Legacy: `configs/evals/gen3/soc_tier1_interactive.json`. `compute_manifest` expands a directory into its sorted regular files. The lock is re-approved once in Task 7 with `scripts/harness_lock.py approve`.
9. **Harbor layout.** `evals/harbor_soc_gen5/<arm>/<split>/<case-slug>/` with `task.toml`, `instruction.md`, `solution/solve.sh`, `tests/test.sh`, `tests/case.json` (a one-case bundle: the answer key, present in the container only at verification time), `tests/manifest.json` (the Gen 5 manifest), and `environment/` holding the Dockerfile, the runtime modules, and `state_bundle.json`: the stripped cases of `validation` and `final_test` (prompt, environment state, fault injection, cmdb context; no oracle, assertions, reference, expected or prohibited lists, labels, liveness, or difficulty). The same bundle goes into every task, so the environment hash is identical across all 100 tasks. `evals/harbor_soc_gen5/manifest.json` records the generator version, the environment hash, the Gen 5 manifest sha256, arms, splits, and one row per task with `case_sha256`.
10. **Arms.** Default arms are `clean_skills` and `gepa_evolved_skills` (spec 9.4). `clean_skills` embeds `skills/secops-triage/SKILL.md` as Gen 3 does. `gepa_evolved_skills` embeds all four `CORE_RUNBOOKS` from `configs/runbooks/gepa_evolved/` under their own headers, with no per-case routing (the Gen 3 `GEPA_CASE_RUNBOOK_MAP` named the right runbook for each case, which is a hint the model should not get). `noisy_skills` and `no_skills` remain available behind `--arms`. In Gen 5 mode the default runbooks dir is the repo-relative `configs/runbooks/gepa_evolved`; the cross-worktree absolute default stays only on the `--gen3` path.
11. **Transport parity.** `gen5_reference_policies` gains `execute_soc_cli`, which drives `run_soc_cli` in-process with `SOC_EVALSET_FILE` pointing at a one-case bundle written from the full case, exactly what `test.sh` does with `soc-cli` in the container. `calibrate` defaults to `--transport both`; the parity gate requires Oracle and Shotgun per-case means to agree within 0.01 across transports and folds into `all_passed`. `GEN5_CALIBRATION.md` is regenerated with both transports in Task 5.

---

### Task 1: Exposure ledger and split loader

**Files:**
- Create: `scripts/gen5_exposure.py`
- Create: `configs/evals/gen5/exposure.jsonl` (empty)
- Create: `tests/test_gen5_exposure.py`

**Interfaces:**
- Produces: `GEN5_ROOT`, `SPLITS`, `LEDGER_KEYS`, `LEDGER_ENV_VAR = "GEN5_EXPOSURE_LEDGER"`, `DEFAULT_LEDGER_PATH`, `MANIFEST_PATH`, `FinalTestSealedError`, `ExposureError`, `ledger_path()`, `bundle_path(split, root)`, `read_bundle(split, root)`, `eval_ids_sha256(eval_ids)`, `git_sha()`, `new_run_id()`, `filter_cases(cases, families, difficulty)`, `check_preregistration(path)`, `expose_cases(...)`, `append_exposure(entry, ledger)`, `read_exposure(ledger)`, `final_test_exposures(ledger)`, `load_split(...)`.
- Consumes: the committed bundles from Plan 2.
- Consumed by: Task 2 (runner), Task 3 (optimizer), Task 7 (docs and the pre-registration file).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_gen5_exposure.py`:

```python
"""Tests for the Gen 5 exposure ledger and split loader (spec section 6.6)."""

import json
from pathlib import Path

import pytest

from scripts import gen5_exposure as ex

ROOT_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture
def ledger(tmp_path, monkeypatch) -> Path:
    path = tmp_path / "exposure.jsonl"
    monkeypatch.setenv(ex.LEDGER_ENV_VAR, str(path))
    return path


def _approved_prereg(tmp_path: Path) -> Path:
    path = tmp_path / "prereg.json"
    path.write_text(json.dumps({
        "schema_version": 1,
        "acceptance": {"approved_by": "owner", "approved_at": "2026-10-10T00:00:00Z"},
        "gen5": {"hypotheses": ["H1: evolved runbooks beat seed on validation by more than tau_accept"]},
    }), encoding="utf-8")
    return path


def test_split_names_and_bundle_paths_are_fixed() -> None:
    assert ex.SPLITS == ("train", "validation", "final_test")
    assert ex.bundle_path("validation") == ex.GEN5_ROOT / "validation.json"
    assert ex.DEFAULT_LEDGER_PATH == ex.GEN5_ROOT / "exposure.jsonl"
    for split in ex.SPLITS:
        assert ex.bundle_path(split).exists(), split


def test_ledger_path_honors_the_test_override(ledger: Path) -> None:
    assert ex.ledger_path() == ledger


def test_eval_ids_sha256_is_order_independent() -> None:
    assert ex.eval_ids_sha256(["b", "a", "c"]) == ex.eval_ids_sha256(["c", "b", "a"])
    assert ex.eval_ids_sha256(["a"]) != ex.eval_ids_sha256(["a", "b"])
    assert len(ex.eval_ids_sha256(["a"])) == 64


def test_filter_cases_by_family_and_difficulty() -> None:
    cases = [
        {"eval_id": "1", "family_id": "FAM-A", "difficulty": 1},
        {"eval_id": "2", "family_id": "FAM-B", "difficulty": 2},
        {"eval_id": "3", "family_id": "FAM-A", "difficulty": 3},
    ]
    assert [c["eval_id"] for c in ex.filter_cases(cases, families=["FAM-A"])] == ["1", "3"]
    assert [c["eval_id"] for c in ex.filter_cases(cases, families=["A"])] == ["1", "3"]
    assert [c["eval_id"] for c in ex.filter_cases(cases, difficulty=[2, 3])] == ["2", "3"]
    assert [c["eval_id"] for c in ex.filter_cases(cases, families=["FAM-A"], difficulty=[3])] == ["3"]
    assert ex.filter_cases(cases) == cases


def test_load_split_appends_exactly_the_spec_keys(ledger: Path) -> None:
    cases, entry = ex.load_split("validation", purpose="unit test", model="mock", run_id="run-1")
    assert len(cases) == 20
    assert tuple(entry) == ex.LEDGER_KEYS
    assert entry["split"] == "validation"
    assert entry["run_id"] == "run-1"
    assert entry["purpose"] == "unit test"
    assert entry["model"] == "mock"
    assert entry["eval_ids_sha256"] == ex.eval_ids_sha256([c["eval_id"] for c in cases])
    lines = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert lines == [entry]


def test_load_split_requires_a_purpose(ledger: Path) -> None:
    with pytest.raises(ex.ExposureError):
        ex.load_split("train", purpose="", model="mock")
    with pytest.raises(ex.ExposureError):
        ex.load_split("train", purpose="   ", model="mock")
    assert not ledger.exists()


def test_filtered_load_hashes_the_filtered_ids(ledger: Path) -> None:
    full, full_entry = ex.load_split("train", purpose="t", model="m", record=False)
    family = full[0]["family_id"]
    some, some_entry = ex.load_split("train", purpose="t", model="m", families=[family], record=False)
    assert 0 < len(some) < len(full)
    assert some_entry["eval_ids_sha256"] != full_entry["eval_ids_sha256"]
    assert not ledger.exists()


def test_final_test_is_sealed_by_default(ledger: Path) -> None:
    with pytest.raises(ex.FinalTestSealedError):
        ex.load_split("final_test", purpose="peek", model="mock")
    with pytest.raises(ex.FinalTestSealedError):
        ex.load_split("final_test", purpose="peek", model="mock", unseal_final_test=True)
    assert not ledger.exists()


def test_final_test_unseal_requires_an_approved_preregistration(ledger: Path, tmp_path: Path) -> None:
    unapproved = tmp_path / "unapproved.json"
    unapproved.write_text(json.dumps({"acceptance": {"approved_by": None, "approved_at": None}, "gen5": {"hypotheses": ["H1"]}}))
    with pytest.raises(ex.FinalTestSealedError):
        ex.load_split("final_test", purpose="campaign 1", model="m", unseal_final_test=True, preregistration=unapproved)
    assert not ledger.exists()

    prereg = _approved_prereg(tmp_path)
    cases, entry = ex.load_split("final_test", purpose="campaign 1", model="m", unseal_final_test=True, preregistration=prereg)
    assert len(cases) == 30
    assert tuple(entry) == ex.LEDGER_KEYS + ("preregistration",)
    assert entry["preregistration"]["sha256"] == ex.sha256_file(prereg)
    assert ex.final_test_exposures() == [entry]


def test_read_exposure_on_a_missing_ledger_is_empty(ledger: Path) -> None:
    assert ex.read_exposure() == []
    assert ex.final_test_exposures() == []


def test_committed_ledger_has_zero_final_test_entries() -> None:
    committed = ROOT_DIR / "configs" / "evals" / "gen5" / "exposure.jsonl"
    assert committed.exists()
    entries = ex.read_exposure(committed)
    assert [e for e in entries if e["split"] == "final_test"] == []
    for entry in entries:
        assert set(ex.LEDGER_KEYS) <= set(entry)


def test_new_run_id_is_unique_and_sortable() -> None:
    first, second = ex.new_run_id(), ex.new_run_id()
    assert first != second
    assert len(first.split("-")) == 2
```

- [ ] **Step 2: Run the tests to confirm they fail**

```bash
.venv/bin/python -m pytest tests/test_gen5_exposure.py -q 2>&1 | tail -5
```

Expected: `ModuleNotFoundError: No module named 'scripts.gen5_exposure'`.

- [ ] **Step 3: Create the empty ledger**

```bash
: > configs/evals/gen5/exposure.jsonl
```

- [ ] **Step 4: Write `scripts/gen5_exposure.py`**

```python
#!/usr/bin/env python3
"""Gen 5 split loader and exposure ledger (spec section 6.6).

Every model-facing loader of a Gen 5 split goes through `load_split`, which
appends one line to `configs/evals/gen5/exposure.jsonl`. `final_test` is
sealed: loading it requires `unseal_final_test=True`, a non-empty purpose, and
an approved pre-registration file (spec section 8.2.5). Nothing else in the
repository writes the ledger. Tests redirect it with the `GEN5_EXPOSURE_LEDGER`
environment variable.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import uuid
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
GEN5_ROOT = ROOT_DIR / "configs" / "evals" / "gen5"
MANIFEST_PATH = GEN5_ROOT / "manifest.json"
DEFAULT_LEDGER_PATH = GEN5_ROOT / "exposure.jsonl"
LEDGER_ENV_VAR = "GEN5_EXPOSURE_LEDGER"
SPLITS: Tuple[str, ...] = ("train", "validation", "final_test")
LEDGER_KEYS: Tuple[str, ...] = ("timestamp", "run_id", "git_sha", "split", "eval_ids_sha256", "purpose", "model")


class ExposureError(ValueError):
    """A split load was requested without the information the ledger needs."""


class FinalTestSealedError(RuntimeError):
    """final_test was requested without an explicit, pre-registered unseal."""


def ledger_path() -> Path:
    """The ledger file: the test override when set, else the committed path."""
    override = os.environ.get(LEDGER_ENV_VAR)
    return Path(override) if override else DEFAULT_LEDGER_PATH


def bundle_path(split: str, root: Path = GEN5_ROOT) -> Path:
    if split not in SPLITS:
        raise ExposureError(f"unknown split {split!r}; expected one of {SPLITS}")
    return Path(root) / f"{split}.json"


def read_bundle(split: str, root: Path = GEN5_ROOT) -> Dict[str, Any]:
    return json.loads(bundle_path(split, root).read_text(encoding="utf-8"))


def eval_ids_sha256(eval_ids: Iterable[str]) -> str:
    """SHA-256 over the sorted, newline-joined eval ids."""
    joined = "\n".join(sorted(str(eval_id) for eval_id in eval_ids))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, capture_output=True, text=True, check=True, timeout=10
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def new_run_id() -> str:
    """Timestamp plus a short random suffix: sortable in the ledger, unique across runs."""
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{uuid.uuid4().hex[:8]}"


def _normalize_family(value: str) -> str:
    text = str(value).strip().upper()
    return text if text.startswith("FAM-") else f"FAM-{text}"


def filter_cases(
    cases: Sequence[Dict[str, Any]],
    families: Optional[Sequence[str]] = None,
    difficulty: Optional[Sequence[int]] = None,
) -> List[Dict[str, Any]]:
    """Keeps the cases whose family is in `families` (short or full ids) and whose difficulty is in `difficulty`."""
    wanted_families = {_normalize_family(f) for f in families} if families else None
    wanted_difficulty = {int(d) for d in difficulty} if difficulty else None
    kept: List[Dict[str, Any]] = []
    for case in cases:
        if wanted_families is not None and _normalize_family(case.get("family_id", "")) not in wanted_families:
            continue
        if wanted_difficulty is not None and int(case.get("difficulty") or 0) not in wanted_difficulty:
            continue
        kept.append(case)
    return kept


def check_preregistration(path: Path) -> Dict[str, Any]:
    """Validates the pre-registration file and returns its ledger reference."""
    path = Path(path)
    if not path.exists():
        raise FinalTestSealedError(f"pre-registration file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as err:
        raise FinalTestSealedError(f"pre-registration file is not valid JSON: {path}: {err}") from err
    acceptance = data.get("acceptance") or {}
    hypotheses = (data.get("gen5") or {}).get("hypotheses") or []
    missing = [key for key in ("approved_by", "approved_at") if not acceptance.get(key)]
    if missing:
        raise FinalTestSealedError(
            f"pre-registration {path} is not approved: acceptance.{', acceptance.'.join(missing)} must be set"
        )
    if not hypotheses:
        raise FinalTestSealedError(f"pre-registration {path} lists no gen5.hypotheses")
    try:
        rel = str(path.resolve().relative_to(ROOT_DIR))
    except ValueError:
        rel = str(path)
    return {"path": rel, "sha256": sha256_file(path)}


def expose_cases(
    split: str,
    cases: Sequence[Dict[str, Any]],
    purpose: str,
    model: str,
    run_id: Optional[str] = None,
    unseal_final_test: bool = False,
    preregistration: Optional[Path] = None,
    record: bool = True,
    ledger: Optional[Path] = None,
) -> Dict[str, Any]:
    """Applies the final_test seal, builds the ledger entry, and appends it unless `record` is False."""
    if split not in SPLITS:
        raise ExposureError(f"unknown split {split!r}; expected one of {SPLITS}")
    if not str(purpose or "").strip():
        raise ExposureError("a non-empty purpose is required to load a Gen 5 split (use --purpose)")
    entry: Dict[str, Any] = {
        "timestamp": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "run_id": run_id or new_run_id(),
        "git_sha": git_sha(),
        "split": split,
        "eval_ids_sha256": eval_ids_sha256(case["eval_id"] for case in cases),
        "purpose": str(purpose).strip(),
        "model": str(model or "unknown"),
    }
    if split == "final_test":
        if not unseal_final_test:
            raise FinalTestSealedError(
                "final_test is sealed. Pass --unseal-final-test --purpose '...' --preregistration <file> "
                "after the pre-registration is approved (spec section 8.2.5)."
            )
        if preregistration is None:
            raise FinalTestSealedError("final_test requires --preregistration <approved comparison file>")
        entry["preregistration"] = check_preregistration(preregistration)
    if record:
        append_exposure(entry, ledger)
    return entry


def append_exposure(entry: Dict[str, Any], ledger: Optional[Path] = None) -> Path:
    path = Path(ledger) if ledger else ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=False) + "\n")
    return path


def read_exposure(ledger: Optional[Path] = None) -> List[Dict[str, Any]]:
    path = Path(ledger) if ledger else ledger_path()
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def final_test_exposures(ledger: Optional[Path] = None) -> List[Dict[str, Any]]:
    return [entry for entry in read_exposure(ledger) if entry.get("split") == "final_test"]


def load_split(
    split: str,
    purpose: str,
    model: str,
    root: Path = GEN5_ROOT,
    families: Optional[Sequence[str]] = None,
    difficulty: Optional[Sequence[int]] = None,
    run_id: Optional[str] = None,
    unseal_final_test: bool = False,
    preregistration: Optional[Path] = None,
    record: bool = True,
    ledger: Optional[Path] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Loads one split, applies the filters, and records the exposure. Returns (cases, ledger entry)."""
    bundle = read_bundle(split, root)
    cases = filter_cases(list(bundle.get("eval_cases", [])), families=families, difficulty=difficulty)
    if not cases:
        raise ExposureError(f"no cases of split {split!r} match families={families} difficulty={difficulty}")
    entry = expose_cases(
        split,
        cases,
        purpose=purpose,
        model=model,
        run_id=run_id,
        unseal_final_test=unseal_final_test,
        preregistration=preregistration,
        record=record,
        ledger=ledger,
    )
    return cases, entry
```

- [ ] **Step 5: Run the tests**

```bash
.venv/bin/python -m pytest tests/test_gen5_exposure.py -q 2>&1 | tail -5
```

Expected: all pass. `test_committed_ledger_has_zero_final_test_entries` reads the real (empty) ledger; every other test writes under `tmp_path`. Confirm the committed ledger is still empty:

```bash
wc -c configs/evals/gen5/exposure.jsonl
```

Expected: `0 configs/evals/gen5/exposure.jsonl`.

- [ ] **Step 6: Commit**

```bash
git add scripts/gen5_exposure.py configs/evals/gen5/exposure.jsonl tests/test_gen5_exposure.py
git commit -m "feat(gen5): add the exposure ledger and sealed split loader"
```

### Task 2: Gen 5 mode in `scripts/eval_soc_agent.py`

**Files:**
- Modify: `scripts/eval_soc_agent.py`
- Create: `tests/test_gen5_eval_runner.py`

**Interfaces:**
- Produces: `GEN5_PASS_THRESHOLD = 0.80`, `GEN5_SPLITS`, `INFRA_ERROR_MARKERS`, `INFRA_RETRY_BACKOFF_S`, `is_infra_error(exc)`, `query_with_infra_retries(agent, prompt, retries)`, `gen5_metrics(usage, latency_s, trajectory)`, `score_gen5_case(case, response_text, trajectory, usage, latency_s, split, jev_evaluator, jev_backend_name, manifest_path)`, `gen5_infra_record(case, split, error, attempts, latency_s)`, `summarize_gen5(results, split)`; `run_evaluation(...)` kwargs `split`, `families`, `difficulty`, `unseal_final_test`, `purpose`, `preregistration`, `infra_retries`; CLI flags `--gen 5`, `--split`, `--families`, `--difficulty`, `--unseal-final-test`, `--purpose`, `--preregistration`, `--infra-retries`; return dict keys `split` and `gen5_exposure`; `summary["gen5"]`.
- Consumes: Task 1; `compose_soc_reward` (Plan 2 Task 6); `plan_oracle`, `execute_python` (Plan 2 Task 7, lazily); `extract_soc_decision`.
- Consumed by: Task 7 recipes (`gen5-gradient`) and docs.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_gen5_eval_runner.py`. The tests patch `scripts.eval_soc_agent.genai.Client` the way `tests/test_eval_soc_agent.py` does, use `--judge-backend mock`, and redirect the ledger.

```python
"""Tests for the Gen 5 branch of scripts/eval_soc_agent.py: split flags, the ledger gate, scoring, infra segregation."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import scripts.eval_soc_agent as runner
from scripts import gen5_exposure as ex

ROOT_DIR = Path(__file__).resolve().parent.parent
GEN5 = ROOT_DIR / "configs" / "evals" / "gen5"


@pytest.fixture
def ledger(tmp_path, monkeypatch) -> Path:
    path = tmp_path / "exposure.jsonl"
    monkeypatch.setenv(ex.LEDGER_ENV_VAR, str(path))
    monkeypatch.setattr(runner, "INFRA_RETRY_BACKOFF_S", 0.0)
    return path


def _first_family(split: str) -> str:
    return json.loads((GEN5 / f"{split}.json").read_text())["eval_cases"][0]["family_id"]


@pytest.fixture
def mock_run(ledger):
    """Runs run_evaluation hermetically: mock judge, no network, real Gen 5 bundles."""
    def run(**kwargs):
        with patch("scripts.eval_soc_agent.genai.Client"), patch.object(runner.SocTier1Agent, "set_up", return_value=None):
            return runner.run_evaluation(
                evalset_path=GEN5 / f"{kwargs.get('split', 'validation')}.json",
                flavor="mock-flavor",
                judge_backend="mock",
                jev_backend="mock",
                purpose="unit test",
                **kwargs,
            )
    return run


def test_parse_args_accepts_gen5_flags() -> None:
    args = runner.parse_args([
        "--gen", "5", "--split", "validation", "--families", "FAM-A", "FAM-B", "--difficulty", "2", "3",
        "--unseal-final-test", "--purpose", "why", "--preregistration", "x.json", "--infra-retries", "4",
    ])
    assert args.gen == 5 and args.split == "validation"
    assert args.families == ["FAM-A", "FAM-B"] and args.difficulty == [2, 3]
    assert args.unseal_final_test is True and args.purpose == "why"
    assert args.preregistration == "x.json" and args.infra_retries == 4
    defaults = runner.parse_args([])
    assert defaults.gen == 3 and defaults.split is None and defaults.infra_retries == 2


def test_split_flag_resolves_the_gen5_bundle() -> None:
    assert runner.resolve_evalset_path(runner.parse_args(["--split", "train"])) == GEN5 / "train.json"
    assert runner.resolve_evalset_path(runner.parse_args(["--gen", "5"])) == GEN5 / "validation.json"
    gen3 = runner.resolve_evalset_path(runner.parse_args([]))
    assert gen3 == ROOT_DIR / "configs" / "evals" / "gen3" / "soc_tier1_interactive.json"


def test_mock_run_on_one_validation_family_scores_oracle_one(mock_run, ledger) -> None:
    family = _first_family("validation")
    out = mock_run(split="validation", families=[family])
    assert out["generation"] == 5 and out["split"] == "validation"
    assert out["case_results"], "expected at least one case"
    for row in out["case_results"]:
        assert row["family_id"] == family
        assert row["gen5_reward"] == 1.0 and row["passed"] is True
        assert row["infra_failure"] is False and row["inert"] is False
        assert row["rubric_score"] == 100.0
        assert row["case_sha256"] and row["manifest_sha256"]
        assert row["tokens_in"] is not None and row["latency_ms"] is not None
    g5 = out["summary"]["gen5"]
    assert g5["split"] == "validation" and g5["pass_threshold"] == 0.80
    assert g5["scored_cases"] == len(out["case_results"]) and g5["infra_failures"] == 0
    assert g5["mean_reward"] == 1.0 and family in g5["per_family"]
    entries = ex.read_exposure(ledger)
    assert len(entries) == 1 and entries[0]["split"] == "validation"
    assert entries[0]["model"] == "mock-flavor" and entries[0]["run_id"] == out["provenance"]["run_id"]
    assert out["gen5_exposure"] == entries[0]


def test_difficulty_filter_restricts_the_cases(mock_run) -> None:
    out = mock_run(split="train", difficulty=[3])
    assert out["case_results"] and all(row["difficulty"] == 3 for row in out["case_results"])


def test_final_test_is_refused_before_any_agent_setup(ledger) -> None:
    with patch("scripts.eval_soc_agent.genai.Client") as client, patch.object(runner.SocTier1Agent, "set_up") as set_up:
        with pytest.raises(ex.FinalTestSealedError):
            runner.run_evaluation(
                evalset_path=GEN5 / "final_test.json", flavor="m", judge_backend="mock", jev_backend="mock",
                split="final_test", purpose="peek",
            )
    set_up.assert_not_called()
    client.assert_not_called()
    assert not ledger.exists()


def test_gen5_rejects_the_legacy_judge(ledger) -> None:
    with pytest.raises(ValueError, match="jev or mock"):
        runner.run_evaluation(
            evalset_path=GEN5 / "validation.json", flavor="m", judge_backend="gemini-2.5-pro",
            split="validation", purpose="x",
        )
    assert not ledger.exists()


def test_is_infra_error_matches_the_markers() -> None:
    assert runner.is_infra_error(RuntimeError("429 RESOURCE_EXHAUSTED: quota exceeded"))
    assert runner.is_infra_error(TimeoutError("deadline exceeded"))
    assert runner.is_infra_error(RuntimeError("503 Service Unavailable"))
    assert not runner.is_infra_error(KeyError("prompt"))
    assert not runner.is_infra_error(ValueError("bad verdict"))


def test_infra_failures_are_retried_and_segregated(ledger) -> None:
    class FlakyAgent:  # not a MagicMock: the class name must not trigger the hermetic mock branch
        calls = 0

        def __init__(self, *args, **kwargs):
            self.environment = None

        def set_up(self):
            return None

        def query(self, prompt):
            FlakyAgent.calls += 1
            raise RuntimeError("429 Too Many Requests")

    family = _first_family("validation")
    with patch("scripts.eval_soc_agent.genai.Client"), patch.object(runner, "SocTier1Agent", FlakyAgent):
        out = runner.run_evaluation(
            evalset_path=GEN5 / "validation.json", flavor="m", judge_backend="jev", jev_backend="mock",
            split="validation", families=[family], purpose="x", infra_retries=2,
        )
    rows = out["case_results"]
    assert rows and all(row["infra_failure"] is True for row in rows)
    assert all(row["gen5_reward"] is None and row["passed"] is False for row in rows)
    assert all(row["infra_attempts"] == 3 for row in rows)
    assert FlakyAgent.calls == 3 * len(rows)
    g5 = out["summary"]["gen5"]
    assert g5["infra_failures"] == len(rows) and g5["scored_cases"] == 0 and g5["mean_reward"] is None
    assert out["summary"]["total_cases"] == 0


def test_non_infra_exceptions_propagate(ledger) -> None:
    class BrokenAgent:
        def __init__(self, *args, **kwargs):
            self.environment = None

        def set_up(self):
            return None

        def query(self, prompt):
            raise KeyError("boom")

    with patch("scripts.eval_soc_agent.genai.Client"), patch.object(runner, "SocTier1Agent", BrokenAgent):
        with pytest.raises(KeyError):
            runner.run_evaluation(
                evalset_path=GEN5 / "validation.json", flavor="m", judge_backend="jev", jev_backend="mock",
                split="validation", families=[_first_family("validation")], purpose="x",
            )


def test_inert_responses_score_zero_and_count_as_inert(ledger) -> None:
    class SilentAgent:
        def __init__(self, *args, **kwargs):
            self.environment = None

        def set_up(self):
            return None

        def query(self, prompt):
            return {"response": "", "trajectory": [], "usage": {"prompt_tokens": 1, "completion_tokens": 0, "total_tokens": 1}}

    family = _first_family("validation")
    with patch("scripts.eval_soc_agent.genai.Client"), patch.object(runner, "SocTier1Agent", SilentAgent):
        out = runner.run_evaluation(
            evalset_path=GEN5 / "validation.json", flavor="m", judge_backend="jev", jev_backend="mock",
            split="validation", families=[family], purpose="x",
        )
    rows = out["case_results"]
    assert rows and all(row["inert"] is True and row["gen5_reward"] == 0.0 and row["passed"] is False for row in rows)
    assert out["summary"]["gen5"]["inert_cases"] == len(rows)
    assert out["summary"]["total_cases"] == len(rows)  # inert cases are scored (0.0), not segregated


def test_summarize_gen5_breaks_down_by_family_and_difficulty() -> None:
    rows = [
        {"family_id": "FAM-A", "difficulty": 1, "gen5_reward": 1.0, "passed": True, "inert": False, "safety_gate_triggered": False, "infra_failure": False},
        {"family_id": "FAM-A", "difficulty": 2, "gen5_reward": 0.6, "passed": False, "inert": False, "safety_gate_triggered": True, "infra_failure": False},
        {"family_id": "FAM-B", "difficulty": 2, "gen5_reward": None, "passed": False, "inert": False, "safety_gate_triggered": False, "infra_failure": True},
    ]
    g5 = runner.summarize_gen5(rows, split="validation")
    assert g5["scored_cases"] == 2 and g5["infra_failures"] == 1 and g5["safety_gate_cases"] == 1
    assert g5["mean_reward"] == 0.8 and g5["pass_rate"] == 50.0
    assert g5["per_family"]["FAM-A"] == {"cases": 2, "mean_reward": 0.8, "passed": 1}
    assert "FAM-B" not in g5["per_family"]
    assert g5["per_difficulty"]["2"]["mean_reward"] == 0.6


def test_gen3_runs_do_not_touch_the_ledger_or_the_gen5_summary(ledger) -> None:
    gen3 = ROOT_DIR / "configs" / "evals" / "gen3" / "soc_tier1_interactive.json"
    with patch("scripts.eval_soc_agent.genai.Client"), patch.object(runner.SocTier1Agent, "set_up", return_value=None):
        out = runner.run_evaluation(evalset_path=gen3, flavor="m", judge_backend="mock", jev_backend="mock")
    assert out["generation"] == 3 and "gen5" not in out["summary"]
    assert out.get("gen5_exposure") is None
    assert not ledger.exists()


def test_markdown_report_renders_the_gen5_section(mock_run) -> None:
    out = mock_run(split="validation", families=[_first_family("validation")])
    text = runner.format_markdown_report(out)
    assert "## Gen 5 reward summary" in text
    assert "| Family |" in text and "Infra failures" in text
```

- [ ] **Step 2: Run the tests to confirm they fail**

```bash
.venv/bin/python -m pytest tests/test_gen5_eval_runner.py -q 2>&1 | tail -5
```

Expected: failures on `resolve_evalset_path`, `is_infra_error`, `summarize_gen5`, the Gen 5 flags, and `run_evaluation` kwargs.

- [ ] **Step 3: Add imports, constants, and the helpers**

In `scripts/eval_soc_agent.py`, after the existing `from scripts...` imports (L28-61), add:

```python
from scripts import gen5_exposure
from scripts.verify_harbor_soc import compose_soc_reward
```

After the module constants (near `ROOT_DIR`), add:

```python
GEN5_PASS_THRESHOLD = 0.80
GEN5_SPLITS = gen5_exposure.SPLITS
GEN5_MANIFEST_PATH = gen5_exposure.MANIFEST_PATH
INFRA_ERROR_MARKERS = (
    "429", "resource_exhausted", "quota", "rate limit", "too many requests",
    "timeout", "timed out", "deadline", "500", "502", "503", "504",
    "unavailable", "overloaded", "connection",
)
INFRA_RETRY_BACKOFF_S = 2.0


def is_infra_error(exc: BaseException) -> bool:
    """True when an exception looks like an endpoint, quota, or network failure rather than an agent failure."""
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return True
    text = f"{type(exc).__name__} {exc}".lower()
    return any(marker in text for marker in INFRA_ERROR_MARKERS)


def query_with_infra_retries(agent: Any, prompt: str, retries: int) -> Tuple[Optional[Dict[str, Any]], int, Optional[str]]:
    """Calls agent.query up to retries + 1 times on infra errors. Returns (result, attempts, last_error)."""
    attempts = 0
    last_error: Optional[str] = None
    while attempts <= max(0, int(retries)):
        attempts += 1
        try:
            return agent.query(prompt=prompt), attempts, None
        except Exception as exc:  # noqa: BLE001 - classified below
            if not is_infra_error(exc):
                raise
            last_error = f"{type(exc).__name__}: {exc}"
            if attempts <= retries and INFRA_RETRY_BACKOFF_S > 0:
                time.sleep(INFRA_RETRY_BACKOFF_S * attempts)
    return None, attempts, last_error


def gen5_metrics(usage: Dict[str, Any], latency_s: float, trajectory: List[Dict[str, Any]], infra_failure: bool = False) -> Dict[str, Any]:
    return {
        "tokens_in": int(usage.get("prompt_tokens", 0) or 0),
        "tokens_out": int(usage.get("completion_tokens", 0) or 0),
        "latency_ms": int(round(latency_s * 1000)),
        "tool_calls": len(trajectory),
        "infra_failure": bool(infra_failure),
    }


def score_gen5_case(
    case: Dict[str, Any],
    response_text: str,
    trajectory: List[Dict[str, Any]],
    usage: Dict[str, Any],
    latency_s: float,
    split: Optional[str],
    jev_evaluator: Any,
    jev_backend_name: str,
    manifest_path: Optional[Path] = GEN5_MANIFEST_PATH,
) -> Dict[str, Any]:
    """Scores one Gen 5 case with the shared composition and returns the per-case result record."""
    soc_dec = extract_soc_decision(response_text)
    decision_data = soc_dec.to_dict() if soc_dec else {}
    card = compose_soc_reward(
        case=case,
        trajectory=trajectory,
        report_text=response_text,
        decision_data=decision_data,
        jev_backend_name=jev_backend_name,
        case_id=case["eval_id"],
        manifest_path=manifest_path if manifest_path and Path(manifest_path).exists() else None,
        metrics=gen5_metrics(usage, latency_s, trajectory),
        split=split,
        jev_evaluator=jev_evaluator,
    )
    reward = float(card["reward"])
    passed = bool(reward >= GEN5_PASS_THRESHOLD and not card["inert"] and not card["safety_gate_triggered"])
    comp_tok = int(usage.get("completion_tokens", 0) or 0)
    tot_tok = int(usage.get("total_tokens", 0) or 0)
    return {
        "eval_id": case["eval_id"],
        "name": case.get("name", case["eval_id"]),
        "prompt": case["prompt"],
        "latency_s": latency_s,
        "usage": usage,
        "generation_tps": round(comp_tok / latency_s, 2) if latency_s > 0 else 0.0,
        "total_tps": round(tot_tok / latency_s, 2) if latency_s > 0 else 0.0,
        "trajectory": trajectory,
        "assert_passed": bool(card["assertions"]["all_passed"]),
        "assertion_failures": list(card["assertions"].get("missing", [])) + list(card["assertions"].get("forbidden_present", [])),
        "rubric_score": round(reward * 100.0, 1),
        "grounding_score": float(card["jev_evaluation"].get("grounding_score", 0.0) or 0.0),
        "passed": passed,
        "critique": card["jev_evaluation"].get("critique", ""),
        "response": response_text,
        "asset_criticality": case.get("asset_criticality", "STANDARD"),
        "ground_truth_label": str(case.get("ground_truth_label", "")).upper(),
        "decision_outcome": card["decision_outcome"],
        "trajectory_verification": card["trajectory_verification"],
        "soc_decision": decision_data or None,
        "epistemic_efficiency": card["epistemic_efficiency"],
        "expected_actions": case.get("expected_actions", []),
        "prohibited_actions": case.get("prohibited_actions", []),
        "counterfactual_pair_id": case.get("counterfactual_pair_id"),
        "case_loss_usd": card["operational_loss_usd"] if card["operational_loss_usd"] is not None else 0.0,
        "jev_choice": card["jev_evaluation"].get("primary_choice"),
        # Gen 5 fields (spec 7.2 and Plan 2 scoring decision 4)
        "gen5_reward": reward,
        "gen5_components": card["components"],
        "gen5_scorecard": card,
        "generation": card["generation"],
        "family_id": card["family_id"],
        "split": card["split"],
        "difficulty": card["difficulty"],
        "case_sha256": card["case_sha256"],
        "manifest_sha256": card["manifest_sha256"],
        "tokens_in": card["tokens_in"],
        "tokens_out": card["tokens_out"],
        "tool_calls": card["tool_calls"],
        "latency_ms": card["latency_ms"],
        "infra_failure": False,
        "infra_attempts": 1,
        "inert": bool(card["inert"]),
        "safety_gate_triggered": bool(card["safety_gate_triggered"]),
        "prohibited_entity_violations": card["prohibited_entity_violations"],
    }


def gen5_infra_record(case: Dict[str, Any], split: Optional[str], error: str, attempts: int, latency_s: float) -> Dict[str, Any]:
    """The record for a case whose every attempt ended in an infrastructure error. Never scored, never a pass."""
    return {
        "eval_id": case["eval_id"],
        "name": case.get("name", case["eval_id"]),
        "prompt": case["prompt"],
        "latency_s": latency_s,
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "generation_tps": 0.0,
        "total_tps": 0.0,
        "trajectory": [],
        "assert_passed": False,
        "assertion_failures": [],
        "rubric_score": 0.0,
        "grounding_score": 0.0,
        "passed": False,
        "critique": f"infrastructure failure after {attempts} attempt(s): {error}",
        "response": "",
        "asset_criticality": case.get("asset_criticality", "STANDARD"),
        "ground_truth_label": str(case.get("ground_truth_label", "")).upper(),
        "decision_outcome": None,
        "trajectory_verification": None,
        "soc_decision": None,
        "epistemic_efficiency": 0.0,
        "expected_actions": case.get("expected_actions", []),
        "prohibited_actions": case.get("prohibited_actions", []),
        "counterfactual_pair_id": case.get("counterfactual_pair_id"),
        "case_loss_usd": 0.0,
        "gen5_reward": None,
        "gen5_components": None,
        "gen5_scorecard": None,
        "generation": int(case.get("generation") or 0),
        "family_id": case.get("family_id"),
        "split": split,
        "difficulty": case.get("difficulty"),
        "case_sha256": None,
        "manifest_sha256": None,
        "tokens_in": None,
        "tokens_out": None,
        "tool_calls": 0,
        "latency_ms": int(round(latency_s * 1000)),
        "infra_failure": True,
        "infra_attempts": attempts,
        "infra_error": error,
        "inert": False,
        "safety_gate_triggered": False,
        "prohibited_entity_violations": [],
    }


def summarize_gen5(results: List[Dict[str, Any]], split: Optional[str]) -> Dict[str, Any]:
    """Gen 5 summary: infra failures excluded from every mean, inert and gated cases counted but scored."""
    scored = [r for r in results if not r.get("infra_failure")]
    rewards = [float(r["gen5_reward"]) for r in scored if r.get("gen5_reward") is not None]

    def _bucket(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        vals = [float(r["gen5_reward"]) for r in rows]
        return {
            "cases": len(rows),
            "mean_reward": round(sum(vals) / len(vals), 4) if vals else None,
            "passed": sum(1 for r in rows if r.get("passed")),
        }

    per_family: Dict[str, Any] = {}
    per_difficulty: Dict[str, Any] = {}
    for key in sorted({str(r.get("family_id")) for r in scored}):
        per_family[key] = _bucket([r for r in scored if str(r.get("family_id")) == key])
    for key in sorted({str(r.get("difficulty")) for r in scored}):
        per_difficulty[key] = _bucket([r for r in scored if str(r.get("difficulty")) == key])
    mean = round(sum(rewards) / len(rewards), 4) if rewards else None
    std = round((sum((x - mean) ** 2 for x in rewards) / len(rewards)) ** 0.5, 4) if rewards and mean is not None else None
    return {
        "split": split,
        "pass_threshold": GEN5_PASS_THRESHOLD,
        "total_cases": len(results),
        "scored_cases": len(scored),
        "infra_failures": len(results) - len(scored),
        "inert_cases": sum(1 for r in scored if r.get("inert")),
        "safety_gate_cases": sum(1 for r in scored if r.get("safety_gate_triggered")),
        "passed_cases": sum(1 for r in scored if r.get("passed")),
        "pass_rate": round(100.0 * sum(1 for r in scored if r.get("passed")) / len(scored), 1) if scored else 0.0,
        "mean_reward": mean,
        "std_reward": std,
        "per_family": per_family,
        "per_difficulty": per_difficulty,
    }
```

`Tuple` must be in the `typing` import; `extract_soc_decision` and `time` are already imported.

- [ ] **Step 4: Thread the Gen 5 flow through `run_evaluation`**

Signature (L300-321): add after `sxs_judge: bool = False,`:

```python
    split: Optional[str] = None,
    families: Optional[List[str]] = None,
    difficulty: Optional[List[int]] = None,
    unseal_final_test: bool = False,
    purpose: Optional[str] = None,
    preregistration: Optional[str] = None,
    infra_retries: int = 2,
```

Evalset load (L334-337) becomes the exposure gate. The gate runs before the banner, before `capture_provenance`, before any agent or client exists:

```python
    with open(evalset_path, "r", encoding="utf-8") as f:
        evalset = json.load(f)

    eval_gen = int(evalset.get("generation", gen))
    if split is not None and eval_gen < 5:
        raise ValueError(f"--split is a Gen 5 option; {evalset_path} is generation {eval_gen}")
    if eval_gen >= 5 and split is None:
        split = str(evalset.get("split") or "validation")

    gen5_entry: Optional[Dict[str, Any]] = None
    eval_cases: List[Dict[str, Any]] = list(evalset.get("eval_cases", []))
    if eval_gen >= 5:
        if judge_backend not in ("jev", "mock"):
            raise ValueError("Gen 5 scoring uses the shared composition; --judge-backend must be jev or mock")
        provenance_run_id = provenance_run_id or gen5_exposure.new_run_id()
        eval_cases, gen5_entry = gen5_exposure.load_split(
            split,
            purpose=purpose or "",
            model=flavor,
            root=Path(evalset_path).parent,
            families=families,
            difficulty=difficulty,
            run_id=provenance_run_id,
            unseal_final_test=unseal_final_test,
            preregistration=Path(preregistration) if preregistration else None,
        )
```

`gen5_exposure.load_split` raises `ExposureError` on an empty purpose and `FinalTestSealedError` on a sealed split; both propagate. Add `split` to the banner (`print(f" Split: {split} ({len(eval_cases)} cases)")` when `eval_gen >= 5`) and `"split": split` to the `capture_provenance` dict.

Environment gates: L382 `if not use_live_mcp and eval_gen == 3:` becomes `if not use_live_mcp and eval_gen in (3, 5):`; the same change at L431. The loop header L427 becomes `for case in eval_cases:`.

Hermetic mock branch (L435-460): wrap the existing Gen 3 synthesis in `if eval_gen >= 5: ... else: <existing code>`, where the Gen 5 branch is:

```python
            if eval_gen >= 5:
                from scripts.gen5_reference_policies import execute_python, plan_oracle  # lazy: keeps the import graph acyclic

                trial = plan_oracle(case)
                res = {
                    "response": trial.report_text,
                    "trajectory": execute_python(case, trial),
                    "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
                }
```

Agent call (L461-462):

```python
        else:
            if eval_gen >= 5:
                res, attempts, infra_error = query_with_infra_retries(agent, case["prompt"], infra_retries)
                if res is None:
                    latency = time.time() - start_time
                    print(f"  Result: INFRA  | {infra_error} after {attempts} attempt(s); excluded from quality metrics")
                    results.append(gen5_infra_record(case, split, infra_error or "unknown", attempts, latency))
                    continue
            else:
                res = agent.query(prompt=case["prompt"])
                attempts = 1
```

Gen 5 scoring branch, inserted after `tot_tps` (L471) and before `# Deterministic Assertions`:

```python
        if eval_gen >= 5:
            case_data = score_gen5_case(
                case, response_text, trajectory, usage, latency, split, jev_evaluator,
                "mock" if (judge_backend == "mock" or jev_backend == "mock") else jev_backend,
            )
            case_data["infra_attempts"] = attempts
            flags = " ".join(flag for flag, on in (("inert", case_data["inert"]), ("gate", case_data["safety_gate_triggered"])) if on)
            print(
                f"  Result: {'PASS' if case_data['passed'] else 'FAIL'} | Reward: {case_data['gen5_reward']:.4f} | "
                f"Outcome: {case_data['decision_outcome'] or 'INERT'} | Latency: {latency:.2f}s | "
                f"Tokens: {tot_tok} | Tool Calls: {len(trajectory)} {flags}"
            )
            results.append(case_data)
            continue
```

`attempts` must be defined on the mock path too (`attempts = 1` right after the hermetic `res = {...}`).

Aggregation (L649) becomes:

```python
    if eval_gen >= 5:
        scored_results = [r for r in results if not r.get("infra_failure")]
        summary = calculate_aggregate_score(scored_results, gen=eval_gen)
        summary["gen5"] = summarize_gen5(results, split)
    else:
        summary = calculate_aggregate_score(results, gen=eval_gen)
```

Console summary: after the SDT block, add for Gen 5:

```python
    if eval_gen >= 5:
        g5 = summary["gen5"]
        print("------------------------------------------------------------------")
        print(f" Gen 5 ({g5['split']}): mean reward {g5['mean_reward']} (std {g5['std_reward']}) | "
              f"pass rate {g5['pass_rate']}% at >= {g5['pass_threshold']} | scored {g5['scored_cases']} | "
              f"infra failures {g5['infra_failures']} | inert {g5['inert_cases']} | safety gate {g5['safety_gate_cases']}")
        for family_id, row in g5["per_family"].items():
            print(f"   {family_id:<36} cases={row['cases']:<3} mean={row['mean_reward']}  passed={row['passed']}")
```

The per-case table (L682-689) must tolerate `None` outcomes: `outcome_str = r.get("decision_outcome") or ("INFRA" if r.get("infra_failure") else "INERT")`.

Return dict (L694-706): add `"split": split,` and `"gen5_exposure": gen5_entry,`.

- [ ] **Step 5: Report section, CLI flags, and evalset resolution**

In `format_markdown_report`, after the existing summary tables and before the per-case section, add when `summary.get("gen5")`:

```python
    g5 = summary.get("gen5")
    if g5:
        lines += [
            "\n## Gen 5 reward summary",
            f"\n**Split:** `{g5['split']}` | **Pass threshold:** {g5['pass_threshold']} | "
            f"**Mean reward:** {g5['mean_reward']} (std {g5['std_reward']}) | **Pass rate:** {g5['pass_rate']}%",
            f"\nScored cases: {g5['scored_cases']} | Infra failures (excluded): {g5['infra_failures']} | "
            f"Inert: {g5['inert_cases']} | Safety gate: {g5['safety_gate_cases']}",
            "\n| Family | Cases | Mean reward | Passed |",
            "|---|---|---|---|",
        ]
        for family_id, row in g5["per_family"].items():
            lines.append(f"| {family_id} | {row['cases']} | {row['mean_reward']} | {row['passed']} |")
        lines += ["\n| Difficulty | Cases | Mean reward | Passed |", "|---|---|---|---|"]
        for level, row in g5["per_difficulty"].items():
            lines.append(f"| {level} | {row['cases']} | {row['mean_reward']} | {row['passed']} |")
```

`parse_args` (L960-1028): `--gen` choices become `[1, 2, 3, 5]` with help text extended by `, 5 for Gen 5 (family-instanced splits)`; add:

```python
    parser.add_argument("--split", choices=list(GEN5_SPLITS), default=None, help="Gen 5 split to load (implies --gen 5)")
    parser.add_argument("--families", nargs="+", default=None, help="Gen 5: keep only these family ids (FAM-... or the short form)")
    parser.add_argument("--difficulty", nargs="+", type=int, choices=[1, 2, 3], default=None, help="Gen 5: keep only these difficulty levels")
    parser.add_argument("--unseal-final-test", action="store_true", default=False, help="Gen 5: allow loading final_test (requires --purpose and --preregistration)")
    parser.add_argument("--purpose", default=None, help="Gen 5: why this split is being loaded; written to the exposure ledger")
    parser.add_argument("--preregistration", default=None, help="Gen 5: approved pre-registration file required to unseal final_test")
    parser.add_argument("--infra-retries", type=int, default=2, help="Gen 5: retries for 429, timeout, and endpoint errors before a case is marked infra_failure")
```

Extract the evalset resolution from `main` (L1036-1056) into `resolve_evalset_path(args) -> Path` and add the Gen 5 arm first:

```python
def resolve_evalset_path(args: argparse.Namespace) -> Path:
    """Default evalset for the requested generation; --split and --gen 5 resolve to the Gen 5 bundles."""
    if args.evalset:
        return Path(args.evalset)
    if args.split or args.gen == 5:
        return gen5_exposure.bundle_path(args.split or "validation")
    if args.gen == 1:
        ...  # existing branches unchanged
```

`main` calls `evalset_file = resolve_evalset_path(args)` and passes the new kwargs to `run_evaluation` (`split=args.split or (("validation") if args.gen == 5 and not args.evalset else None)`, `families=args.families`, `difficulty=args.difficulty`, `unseal_final_test=args.unseal_final_test`, `purpose=args.purpose`, `preregistration=args.preregistration`, `infra_retries=args.infra_retries`). The existing failure-artifact path in `main` catches exceptions; `FinalTestSealedError` and `ExposureError` must be printed to stderr with exit code 2 before any artifact is written, so add them to the first `except` clause as a distinct branch.

- [ ] **Step 6: Run the new tests, then the frozen ones**

```bash
.venv/bin/python -m pytest tests/test_gen5_eval_runner.py -q 2>&1 | tail -5
.venv/bin/python -m pytest tests/test_eval_soc_agent.py tests/test_eval_cli_failure.py tests/test_gen3_cost_engine.py tests/test_gen3_trajectory_verifier.py tests/test_verify_harbor_soc.py -q 2>&1 | tail -5
```

Expected: all pass. If `test_mock_run_on_one_validation_family_scores_oracle_one` reports a reward below 1.0, the mock Jev backend is not the one `compose_soc_reward` builds for the calibration; pass `jev_backend_name="mock"` with `jev_evaluator=None` for the `judge_backend == "mock"` path (so the composition builds the calibrated mock itself) rather than reusing the runner's `MockJevBackend` evaluator. Do not lower the assertion.

- [ ] **Step 7: Commit**

```bash
git add scripts/eval_soc_agent.py tests/test_gen5_eval_runner.py
git commit -m "feat(gen5): split flags, exposure gate, shared scoring, and infra segregation in the eval runner"
```

### Task 3: Hillclimb harness: K-run noise floor, protected path sets, staircase telemetry, lock CLI

**Files:**
- Modify: `agent/hillclimb_harness.py`
- Create: `scripts/harness_lock.py`
- Modify: `tests/test_hillclimb_harness.py`
- Create: `tests/test_harness_lock.py`

**Interfaces:**
- Produces: `SHARED_SCORING_PATHS`, `GEN5_PROTECTED_PATHS`, `LEGACY_PROTECTED_PATHS`, `DEFAULT_PROTECTED_HARNESS_PATHS` (the concatenation); `HarnessIntegrityGuard.compute_manifest` expanding directories; `NoiseFloorMetrics` fields `runs`, `run_means`, `per_case_spread`, `per_case_std`, `mean_case_std`, `case_ids`, and `to_dict()`; `estimate_noise_floor(*runs, min_delta=0.015, multiplier=1.5, case_ids=None)`; `write_noise_floor_json(metrics, path, extra=None)`; `CostRungResult` fields `tokens_in`, `tokens_out`, `latency_ms`, `scored_cases`, `inert_cases`, `inert`; `run_cost_staircase_walk` accepting a 2-tuple or 3-tuple evaluator; `scripts/harness_lock.py` with `approve | verify` and `--root`, `--lock-file`, `--path`.
- Consumes: nothing new.
- Consumed by: Task 4 (optimizer), Task 7 (lock re-approval, `just harness-approve`, `just harness-verify`).

- [ ] **Step 1: Extend the harness tests**

Append to `tests/test_hillclimb_harness.py` (2-space indentation, matching the file). Also add `write_noise_floor_json`, `run_cost_staircase_walk`, `DEFAULT_PROTECTED_HARNESS_PATHS`, `GEN5_PROTECTED_PATHS`, `LEGACY_PROTECTED_PATHS`, `SHARED_SCORING_PATHS` to the import block at the top.

```python
def test_estimate_noise_floor_accepts_k_runs_and_keeps_the_two_run_numbers():
  run1 = [0.80, 0.70, 0.90, 0.60]
  run2 = [0.82, 0.66, 0.90, 0.62]
  run3 = [0.84, 0.74, 0.94, 0.64]
  two = estimate_noise_floor(run1, run2, min_delta=0.015, multiplier=1.5)
  assert two.runs == 2 and two.run_means == pytest.approx((0.75, 0.75))
  assert two.aggregate_noise == pytest.approx(0.0) and two.mean_case_noise == pytest.approx(0.02)
  assert two.per_case_spread == pytest.approx((0.02, 0.04, 0.0, 0.02))
  assert two.per_case_std == pytest.approx((0.01, 0.02, 0.0, 0.01))

  three = estimate_noise_floor(run1, run2, run3, min_delta=0.015, multiplier=1.5, case_ids=["a", "b", "c", "d"])
  assert three.runs == 3 and three.case_ids == ("a", "b", "c", "d")
  assert three.run1_mean == pytest.approx(0.75) and three.run2_mean == pytest.approx(0.75)
  assert three.aggregate_noise == pytest.approx(0.04)  # max run mean 0.79 minus min 0.75
  assert three.tau_accept == pytest.approx(0.06)
  assert three.per_case_spread == pytest.approx((0.04, 0.08, 0.04, 0.04))
  assert three.mean_case_std == pytest.approx(sum(three.per_case_std) / 4)
  payload = three.to_dict()
  assert payload["runs"] == 3 and payload["per_case"][1] == {
      "case_id": "b", "scores": [0.70, 0.66, 0.74], "spread": pytest.approx(0.08), "std": pytest.approx(three.per_case_std[1])
  }


def test_estimate_noise_floor_rejects_fewer_than_two_runs_or_ragged_runs():
  with pytest.raises(ValueError):
    estimate_noise_floor([0.5, 0.6])
  with pytest.raises(ValueError):
    estimate_noise_floor([0.5, 0.6], [0.5])
  with pytest.raises(ValueError):
    estimate_noise_floor([], [])


def test_write_noise_floor_json_round_trips(tmp_path: Path):
  metrics = estimate_noise_floor([0.8, 0.7], [0.82, 0.66], [0.78, 0.72], case_ids=["x", "y"])
  path = write_noise_floor_json(metrics, tmp_path / "out" / "noise_floor.json", extra={"model": "mock", "split": "validation"})
  data = json.loads(path.read_text(encoding="utf-8"))
  assert data["model"] == "mock" and data["split"] == "validation"
  assert data["runs"] == 3 and data["tau_accept"] == pytest.approx(metrics.tau_accept)
  assert data["mean_spread"] == pytest.approx(metrics.aggregate_noise)
  assert [row["case_id"] for row in data["per_case"]] == ["x", "y"]


def test_default_protected_paths_cover_shared_gen5_and_legacy():
  assert DEFAULT_PROTECTED_HARNESS_PATHS == SHARED_SCORING_PATHS + GEN5_PROTECTED_PATHS + LEGACY_PROTECTED_PATHS
  assert "scripts/verify_harbor_soc.py" in SHARED_SCORING_PATHS
  assert "scripts/eval_soc_agent.py" in SHARED_SCORING_PATHS
  assert "configs/evals/gen5/manifest.json" in GEN5_PROTECTED_PATHS
  assert "configs/evals/gen5/families" in GEN5_PROTECTED_PATHS
  assert "scripts/gen5_instancer.py" in GEN5_PROTECTED_PATHS
  assert LEGACY_PROTECTED_PATHS == ("configs/evals/gen3/soc_tier1_interactive.json",)
  root = Path(__file__).resolve().parent.parent
  for rel in DEFAULT_PROTECTED_HARNESS_PATHS:
    assert (root / rel).exists(), rel


def test_compute_manifest_expands_directories(tmp_path: Path):
  (tmp_path / "families").mkdir()
  (tmp_path / "families" / "b.json").write_text("{}", encoding="utf-8")
  (tmp_path / "families" / "a.json").write_text("{}", encoding="utf-8")
  (tmp_path / "families" / "__pycache__").mkdir()
  (tmp_path / "families" / "__pycache__" / "x.pyc").write_bytes(b"\x00")
  (tmp_path / "grader.py").write_text("def grade(): return 1.0\n", encoding="utf-8")
  guard = HarnessIntegrityGuard(root_dir=tmp_path, lock_file=tmp_path / "lock.json", protected_paths=["families", "grader.py"])
  manifest = guard.compute_manifest()
  assert list(manifest) == ["families/a.json", "families/b.json", "grader.py"]
  guard.approve_and_save()
  (tmp_path / "families" / "c.json").write_text("{}", encoding="utf-8")
  with pytest.raises(HarnessTamperError, match="families/c.json"):
    guard.verify(auto_initialize=False)


def test_cost_staircase_marks_inert_rungs_and_records_telemetry():
  table = {
      "gemini-2.5-flash": ([0.90, 0.90], [1.0, 1.0], {"inert": [False, False], "tokens_in": [100, 120], "tokens_out": [40, 50], "latency_ms": [900, 1100]}),
      "gemma-4-31b-it": ([0.88, 0.88], [1.0, 1.0], {"inert": [False, False], "tokens_in": [100, 100], "tokens_out": [30, 30], "latency_ms": [500, 700]}),
      "gemma-3-1b-it": ([0.0, 0.0], [1.0, 1.0], {"inert": [True, True], "tokens_in": [100, 100], "tokens_out": [0, 0], "latency_ms": [100, 100]}),
  }

  def fake_eval(tier, candidate, cases):
    return table[tier]

  report = run_cost_staircase_walk(
      candidate={"basic_ioc_enrichment.md": "# Runbook"},
      eval_cases=[{"eval_id": "CASE-01"}, {"eval_id": "CASE-02"}],
      evaluator_fn=fake_eval,
      model_tiers=list(table),
      tolerance=0.05,
  )
  assert report.selected_model == "gemma-4-31b-it"
  top, mid, bottom = report.rungs
  assert top.tokens_in == 220 and top.tokens_out == 90 and top.latency_ms == 1000
  assert top.scored_cases == 2 and top.inert_cases == 0 and top.inert is False
  assert mid.latency_ms == 600
  assert bottom.inert is True and bottom.inert_cases == 2 and bottom.scored_cases == 0
  assert bottom.passed_safety is False and bottom.within_tolerance is False
  assert report.to_dict()["rungs"][2]["inert"] is True
```

Create `tests/test_harness_lock.py`:

```python
"""Tests for scripts/harness_lock.py: approve and verify without importing any model code."""

from pathlib import Path

from scripts import harness_lock


def _root(tmp_path: Path) -> Path:
  (tmp_path / "configs").mkdir()
  (tmp_path / "configs" / "a.json").write_text("{}", encoding="utf-8")
  (tmp_path / "grader.py").write_text("x = 1\n", encoding="utf-8")
  return tmp_path


def test_approve_then_verify_passes(tmp_path: Path, capsys) -> None:
  root = _root(tmp_path)
  lock = tmp_path / "lock.json"
  args = ["--root", str(root), "--lock-file", str(lock), "--path", "configs", "--path", "grader.py"]
  assert harness_lock.main(["approve", *args]) == 0
  assert lock.exists()
  assert harness_lock.main(["verify", *args]) == 0
  out = capsys.readouterr().out
  assert "composite_sha256" in out and "harness lock verified" in out


def test_verify_fails_after_tampering(tmp_path: Path, capsys) -> None:
  root = _root(tmp_path)
  lock = tmp_path / "lock.json"
  args = ["--root", str(root), "--lock-file", str(lock), "--path", "configs", "--path", "grader.py"]
  assert harness_lock.main(["approve", *args]) == 0
  (root / "grader.py").write_text("x = 2\n", encoding="utf-8")
  assert harness_lock.main(["verify", *args]) == 1
  assert "grader.py" in capsys.readouterr().err


def test_verify_without_a_lock_does_not_initialize(tmp_path: Path, capsys) -> None:
  root = _root(tmp_path)
  lock = tmp_path / "missing.json"
  assert harness_lock.main(["verify", "--root", str(root), "--lock-file", str(lock), "--path", "grader.py"]) == 1
  assert not lock.exists()


def test_default_paths_are_the_harness_defaults() -> None:
  from agent.hillclimb_harness import DEFAULT_PROTECTED_HARNESS_PATHS

  parser = harness_lock.build_parser()
  args = parser.parse_args(["verify"])
  assert harness_lock.resolve_paths(args) == list(DEFAULT_PROTECTED_HARNESS_PATHS)
```

- [ ] **Step 2: Run the tests to confirm they fail**

```bash
.venv/bin/python -m pytest tests/test_hillclimb_harness.py tests/test_harness_lock.py -q 2>&1 | tail -5
```

Expected: `ImportError` on the new names and `ModuleNotFoundError: scripts.harness_lock`.

- [ ] **Step 3: Protected path sets and directory expansion**

Replace `DEFAULT_PROTECTED_HARNESS_PATHS` (L15-21) with:

```python
SHARED_SCORING_PATHS: Tuple[str, ...] = (
    "agent/soc_environment.py",
    "scripts/eval_trajectory_verifier.py",
    "scripts/eval_cost_engine.py",
    "scripts/eval_soc_agent.py",
    "scripts/verify_harbor_soc.py",
)

GEN5_PROTECTED_PATHS: Tuple[str, ...] = (
    "configs/evals/gen5/manifest.json",
    "configs/evals/gen5/train.json",
    "configs/evals/gen5/validation.json",
    "configs/evals/gen5/final_test.json",
    "configs/evals/gen5/families",
    "configs/evals/gen5/pools",
    "configs/evals/gen5/schema",
    "configs/evals/gen5/split_plan.json",
    "scripts/gen5_instancer.py",
)

LEGACY_PROTECTED_PATHS: Tuple[str, ...] = (
    "configs/evals/gen3/soc_tier1_interactive.json",
)

# Shared scoring code, the Gen 5 inputs, and the frozen Gen 3 suite (spec section 6.7).
DEFAULT_PROTECTED_HARNESS_PATHS: Tuple[str, ...] = (
    SHARED_SCORING_PATHS + GEN5_PROTECTED_PATHS + LEGACY_PROTECTED_PATHS
)
```

Replace the body of `compute_manifest` (L55-66):

```python
  def _iter_protected_files(self) -> List[Tuple[str, Path]]:
    """Protected entries as (relative key, absolute file): directories expand to their sorted regular files."""
    files: List[Tuple[str, Path]] = []
    for p in self.protected_paths:
      rel_key, full_path = self._resolve_rel_key(p)
      if not full_path.exists():
        raise HarnessTamperError(
            f"Protected harness file is missing: {rel_key} ({full_path})"
        )
      if full_path.is_dir():
        for child in sorted(full_path.rglob("*")):
          if child.is_file() and "__pycache__" not in child.parts:
            files.append(self._resolve_rel_key(child))
      else:
        files.append((rel_key, full_path))
    return files

  def compute_manifest(self) -> Dict[str, str]:
    """Compute SHA-256 hex digests for all protected harness files (directories expanded)."""
    manifest: Dict[str, str] = {}
    for rel_key, full_path in self._iter_protected_files():
      manifest[rel_key] = hashlib.sha256(full_path.read_bytes()).hexdigest()
    return manifest
```

`verify` already reports files present in the lock but missing from the manifest and files whose digest changed; a new file inside a protected directory shows up as `families/c.json (expected None, got ...)`, which is what the new test matches.

- [ ] **Step 4: K-run noise floor**

Replace `NoiseFloorMetrics` (L123-131) and `estimate_noise_floor` (L146-178):

```python
@dataclass(frozen=True)
class NoiseFloorMetrics:
  """Noise floor from K >= 2 passes of the same candidate on the same cases.

  `run1_mean` and `run2_mean` are the first two run means (kept for the two-run
  callers). `aggregate_noise` is the mean spread: the largest run mean minus
  the smallest. `mean_case_noise` is the mean per-case spread (max minus min
  across runs), which equals the two-run per-case absolute difference.
  """

  run1_mean: float
  run2_mean: float
  aggregate_noise: float
  mean_case_noise: float
  tau_accept: float
  runs: int = 2
  run_means: Tuple[float, ...] = ()
  per_case_spread: Tuple[float, ...] = ()
  per_case_std: Tuple[float, ...] = ()
  mean_case_std: float = 0.0
  case_ids: Tuple[str, ...] = ()
  per_case_scores: Tuple[Tuple[float, ...], ...] = ()

  def to_dict(self) -> Dict[str, Any]:
    per_case = []
    for index, scores in enumerate(self.per_case_scores):
      per_case.append({
          "case_id": self.case_ids[index] if index < len(self.case_ids) else str(index),
          "scores": list(scores),
          "spread": self.per_case_spread[index],
          "std": self.per_case_std[index],
      })
    return {
        "runs": self.runs,
        "run_means": list(self.run_means),
        "run1_mean": self.run1_mean,
        "run2_mean": self.run2_mean,
        "mean_spread": self.aggregate_noise,
        "aggregate_noise": self.aggregate_noise,
        "mean_case_noise": self.mean_case_noise,
        "mean_case_std": self.mean_case_std,
        "tau_accept": self.tau_accept,
        "per_case": per_case,
    }


def estimate_noise_floor(
    *runs: Sequence[float],
    min_delta: float = 0.015,
    multiplier: float = 1.5,
    case_ids: Optional[Sequence[str]] = None,
) -> NoiseFloorMetrics:
  """Compute the noise floor from K >= 2 baseline passes on identical code and cases."""
  if len(runs) < 2:
    raise ValueError("estimate_noise_floor needs at least two runs.")
  n = len(runs[0])
  if n == 0 or any(len(run) != n for run in runs):
    raise ValueError("every run must be a non-empty sequence of the same length.")

  matrix = [tuple(float(x) for x in run) for run in runs]
  run_means = tuple(sum(run) / n for run in matrix)
  agg_noise = max(run_means) - min(run_means)
  per_case_scores = tuple(tuple(run[i] for run in matrix) for i in range(n))
  per_case_spread = tuple(max(scores) - min(scores) for scores in per_case_scores)
  per_case_std = tuple(
      (sum((s - sum(scores) / len(scores)) ** 2 for s in scores) / len(scores)) ** 0.5
      for scores in per_case_scores
  )
  tau_accept = max(float(min_delta), float(multiplier) * agg_noise)
  return NoiseFloorMetrics(
      run1_mean=run_means[0],
      run2_mean=run_means[1],
      aggregate_noise=agg_noise,
      mean_case_noise=sum(per_case_spread) / n,
      tau_accept=tau_accept,
      runs=len(runs),
      run_means=run_means,
      per_case_spread=per_case_spread,
      per_case_std=per_case_std,
      mean_case_std=sum(per_case_std) / n,
      case_ids=tuple(str(c) for c in case_ids) if case_ids else (),
      per_case_scores=per_case_scores,
  )


def write_noise_floor_json(
    metrics: NoiseFloorMetrics,
    path: Path,
    extra: Optional[Dict[str, Any]] = None,
) -> Path:
  """Write the noise floor report (spec 8.2 gate 1) as JSON; `extra` keys are added at the top level."""
  payload = dict(extra or {})
  payload.update(metrics.to_dict())
  payload["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
  path = Path(path)
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
  return path
```

The existing two-run assertions (`aggregate_noise`, `mean_case_noise`, `tau_accept`) hold unchanged: with two runs the spread equals the absolute difference.

- [ ] **Step 5: Staircase telemetry and inert rungs**

Replace `CostRungResult` (L308-316):

```python
@dataclass(frozen=True)
class CostRungResult:
  """Evaluation summary for a single model rung in the cost staircase."""

  model_tier: str
  mean_score: float
  min_loss_penalty: float
  passed_safety: bool
  within_tolerance: bool
  tokens_in: Optional[int] = None
  tokens_out: Optional[int] = None
  latency_ms: Optional[int] = None
  scored_cases: int = 0
  inert_cases: int = 0
  inert: bool = False
```

In `run_cost_staircase_walk`, the evaluator may return `(scores, loss_penalties)` or `(scores, loss_penalties, telemetry)`. Replace the loop body from `scores, loss_penalties = evaluator_fn(...)` through `rungs.append(rung)`:

```python
    outcome = evaluator_fn(tier, candidate, eval_cases)
    scores, loss_penalties = list(outcome[0]), list(outcome[1])
    telemetry: Dict[str, Any] = dict(outcome[2]) if len(outcome) > 2 and outcome[2] else {}
    inert_flags = [bool(x) for x in telemetry.get("inert", [])] or [False] * len(scores)
    scored = [s for s, inert_flag in zip(scores, inert_flags) if not inert_flag]
    inert_cases = sum(1 for flag in inert_flags if flag)
    rung_inert = not scored

    def _total(key: str) -> Optional[int]:
      values = [v for v in telemetry.get(key, []) if v is not None]
      return int(sum(values)) if values else None

    def _mean(key: str) -> Optional[int]:
      values = [v for v in telemetry.get(key, []) if v is not None]
      return int(round(sum(values) / len(values))) if values else None

    mean_score = sum(scored) / len(scored) if scored else 0.0
    min_loss_pen = min(loss_penalties) if loss_penalties else 0.0
    passed_safety = (min_loss_pen >= 0.999) and not rung_inert

    if idx == 0:
      ceiling_score = mean_score
      selected_score = mean_score

    within_tol = (not rung_inert) and mean_score >= (ceiling_score - tolerance - 1e-9)
    rung = CostRungResult(
        model_tier=tier,
        mean_score=mean_score,
        min_loss_penalty=min_loss_pen,
        passed_safety=passed_safety,
        within_tolerance=within_tol,
        tokens_in=_total("tokens_in"),
        tokens_out=_total("tokens_out"),
        latency_ms=_mean("latency_ms"),
        scored_cases=len(scored),
        inert_cases=inert_cases,
        inert=rung_inert,
    )
    rungs.append(rung)
```

The selection line `if passed_safety and within_tol:` stays. An inert rung is therefore never selected and never reported as a score; `mean_score` is 0.0 with `inert: true`, and consumers (Task 4 writes the report, Task 7 documents it) read the flag.

- [ ] **Step 6: Write `scripts/harness_lock.py`**

```python
#!/usr/bin/env python3
"""Approve or verify the evaluation harness lock without importing any model code.

`approve` recomputes the digests of the protected paths (shared scoring code,
the Gen 5 inputs, the frozen Gen 3 suite) and rewrites the lock file. `verify`
checks the current files against the lock and exits 1 on any mismatch. The
optimizer runs the same check before every hillclimb; this script exists so the
lock can be re-approved after an intentional change without spending a model
call on a dry run.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agent.hillclimb_harness import (  # noqa: E402
    DEFAULT_PROTECTED_HARNESS_PATHS,
    HarnessIntegrityGuard,
    HarnessTamperError,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Approve or verify .eval_harness_lock.json")
    parser.add_argument("command", choices=["approve", "verify"])
    parser.add_argument("--root", default=str(ROOT_DIR), help="repository root the protected paths are relative to")
    parser.add_argument("--lock-file", default=None, help="lock file path (default: <root>/.eval_harness_lock.json)")
    parser.add_argument(
        "--path", action="append", default=None,
        help="protected path relative to --root; repeatable; default: the harness defaults",
    )
    return parser


def resolve_paths(args: argparse.Namespace) -> List[str]:
    return list(args.path) if args.path else list(DEFAULT_PROTECTED_HARNESS_PATHS)


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve()
    lock_file = Path(args.lock_file).resolve() if args.lock_file else root / ".eval_harness_lock.json"
    guard = HarnessIntegrityGuard(root_dir=root, lock_file=lock_file, protected_paths=resolve_paths(args))
    try:
        if args.command == "approve":
            payload = guard.approve_and_save()
            print(f"approved {len(payload['files'])} protected file(s); composite_sha256={payload['composite_sha256']}")
            print(f"lock written to {lock_file}")
            return 0
        files = guard.verify(auto_initialize=False)
        print(f"harness lock verified: {len(files)} file(s), composite_sha256={guard.compute_composite_sha256()}")
        return 0
    except HarnessTamperError as err:
        print(f"error: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 7: Run the tests**

```bash
.venv/bin/python -m pytest tests/test_hillclimb_harness.py tests/test_harness_lock.py tests/test_gepa_runbook_optimizer.py -q 2>&1 | tail -5
```

Expected: all pass. `test_default_protected_paths_cover_shared_gen5_and_legacy` requires every Gen 5 path to exist, which Plan 2 guarantees. The optimizer tests still pass because they use `--evalset` under `tmp_path` (so `protected_paths = [evalset_path]`) or an explicit lock under `tmp_path`.

Do not run `scripts/harness_lock.py approve` against the repository root yet; the shared scoring files change again in Task 4, and the lock is re-approved once in Task 7.

- [ ] **Step 8: Commit**

```bash
git add agent/hillclimb_harness.py scripts/harness_lock.py tests/test_hillclimb_harness.py tests/test_harness_lock.py
git commit -m "feat(hillclimb): K-run noise floor, Gen 5 protected paths, inert staircase rungs, lock CLI"
```

### Task 4: GEPA optimizer: splits, manifest literal guard, Gen 5 fitness, no-overwrite, noise floor

**Files:**
- Modify: `agent/gepa_runbook_optimizer.py`
- Modify: `tests/test_gepa_runbook_optimizer.py`

**Interfaces:**
- Produces: `calculate_loss_penalty(..., prohibited_violation=None)`; `CASE_ID_REGEX` matching Gen 5 ids; `compile_forbidden_literals(literals)`, `load_forbidden_literals(manifest_path)`; `validate_runbook_candidate(..., forbidden_literals=None)`; `RunbookGEPAAdapter(..., forbidden_literals=None)`; traces with `inert`, `prohibited_entity_violations`, `generation`, `family_id`, `usage`, `latency_ms`; `write_evolution_metadata(output_dir, metadata)`; `select_candidate_outcome(selected_index, valid_count)`; CLI `--train-split`, `--val-split`, `--purpose`, `--manifest`, `--run-id`, `--noise-only`, `--evalset` default `None`; `noise_floor.json`; metadata keys `run_id`, `train_split`, `val_split`, `evalset`, `exposure`, `runbooks_written`, `forbidden_literals_count`, `noise_floor`, `selection_reason`.
- Consumes: Task 1 (`gen5_exposure`), Task 3 (`estimate_noise_floor(*runs)`, `write_noise_floor_json`, 3-tuple staircase evaluator), Plan 2 verifier kwargs and `manifest.forbidden_literals`.
- Consumed by: Task 7 (`just gen5-noise`, docs).

- [ ] **Step 1: Update and extend the optimizer tests**

In `tests/test_gepa_runbook_optimizer.py`:

1. `test_build_arg_parser_defaults` (L531-545): the `evalset` default assertion becomes `assert args.evalset is None`; add `assert args.train_split == "train" and args.val_split == "validation" and args.noise_only is False and args.manifest.endswith("configs/evals/gen5/manifest.json")`.
2. `optimizer_cli` fixture (L596-632): give `run` the keyword `gen5=False` and the extra arguments `extra=()`. When `gen5` is true, omit `--evalset`, set `monkeypatch.setenv("GEN5_EXPOSURE_LEDGER", str(tmp_path / "exposure.jsonl"))`, and always pass `--lock-file str(tmp_path / "lock.json") --noise-runs 0` plus `*extra`. Return the ledger path as a seventh element: `return run, output_dir, seed, optimize, adapter, reflection, tmp_path / "exposure.jsonl"`, and update the existing unpacking sites (`run, output_dir, ... = optimizer_cli` lines) to take seven values.
3. `test_cli_saves_highest_scoring_valid_candidate`: drop the `([0.9, 0.9, 0.3], [], 0)` parameter row (the seed can no longer be "saved"); add `assert metadata["runbooks_written"] is True` to the remaining rows.
4. `test_cli_falls_back_to_seed_without_claiming_a_selected_score`: replace the `read_text() == seed[...]` assertion with `assert not (output_dir / CORE_RUNBOOKS[0]).exists()`; keep the metadata assertions and add `assert metadata["runbooks_written"] is False`.
5. `test_cli_skips_malformed_candidates`: replace the `read_text()` assertion with `assert not (output_dir / CORE_RUNBOOKS[0]).exists()`; add `assert metadata["selection_reason"] == "seed_retained_all_candidates_reverted"` and `assert metadata["runbooks_written"] is False`.

Append these tests:

```python
def test_cli_keeps_the_seed_when_no_candidate_beats_it(optimizer_cli):
    run, output_dir, seed, _, _, _, _ = optimizer_cli
    output_dir.mkdir(parents=True)
    evolved = output_dir / CORE_RUNBOOKS[0]
    evolved.write_text("# Previously evolved\nKeep me.", encoding="utf-8")
    candidates = [seed, {name: f"# Worse\n{seed[name]}" for name in CORE_RUNBOOKS}]
    assert run(candidates, [0.9, 0.5]) == 0
    assert evolved.read_text(encoding="utf-8") == "# Previously evolved\nKeep me."
    metadata = json.loads((output_dir / "evolution_metadata.json").read_text())
    assert metadata["selected_candidate_index"] == 0
    assert metadata["selection_reason"] == "seed_retained_all_candidates_reverted"
    assert metadata["runbooks_written"] is False


def test_cli_writes_runbooks_only_when_a_non_seed_candidate_wins(optimizer_cli):
    run, output_dir, seed, _, _, _, _ = optimizer_cli
    better = {name: f"# Better\n{seed[name]}" for name in CORE_RUNBOOKS}
    assert run([seed, better], [0.5, 0.9]) == 0
    assert (output_dir / CORE_RUNBOOKS[0]).read_text() == better[CORE_RUNBOOKS[0]]
    metadata = json.loads((output_dir / "evolution_metadata.json").read_text())
    assert metadata["selection_reason"] == "highest_valid_validation_score"
    assert metadata["runbooks_written"] is True


def test_gen5_default_loads_train_and_validation_and_records_exposure(optimizer_cli):
    run, output_dir, seed, optimize, _, _, ledger = optimizer_cli
    better = {name: f"# Better\n{seed[name]}" for name in CORE_RUNBOOKS}
    assert run([seed, better], [0.5, 0.9], gen5=True) == 0
    kwargs = optimize.call_args.kwargs
    train_ids = {case["eval_id"] for case in kwargs["trainset"]}
    val_ids = {case["eval_id"] for case in kwargs["valset"]}
    assert len(train_ids) == 40 and len(val_ids) == 20 and train_ids.isdisjoint(val_ids)
    assert all(case["generation"] == 5 for case in kwargs["trainset"])
    entries = [json.loads(line) for line in ledger.read_text().splitlines()]
    assert [e["split"] for e in entries] == ["train", "validation"]
    assert len({e["run_id"] for e in entries}) == 1
    assert entries[0]["purpose"].endswith("(train)") and entries[1]["purpose"].endswith("(validation)")
    metadata = json.loads((output_dir / "evolution_metadata.json").read_text())
    assert metadata["train_split"] == "train" and metadata["val_split"] == "validation"
    assert metadata["run_id"] == entries[0]["run_id"] and metadata["exposure"] == entries
    assert metadata["forbidden_literals_count"] > 100


def test_gen5_rejects_identical_splits(optimizer_cli, capsys):
    run, _, seed, optimize, _, _, ledger = optimizer_cli
    assert run([seed], [0.5], gen5=True, extra=("--train-split", "validation", "--val-split", "validation")) == 1
    assert "must differ" in capsys.readouterr().err
    optimize.assert_not_called()
    assert not ledger.exists()


def test_gen5_never_optimizes_on_final_test(optimizer_cli, capsys):
    run, _, seed, optimize, _, _, ledger = optimizer_cli
    assert run([seed], [0.5], gen5=True, extra=("--val-split", "final_test")) == 1
    assert "sealed" in capsys.readouterr().err
    optimize.assert_not_called()
    entries = [json.loads(line) for line in ledger.read_text().splitlines()] if ledger.exists() else []
    assert [e["split"] for e in entries] in ([], ["train"])  # train may be recorded first; final_test never is


def test_cli_noise_only_writes_the_noise_floor_and_skips_optimization(optimizer_cli):
    from types import SimpleNamespace

    run, output_dir, seed, optimize, adapter, reflection, _ = optimizer_cli
    adapter.return_value.evaluate.side_effect = [
        SimpleNamespace(scores=[0.8, 0.7, 0.9, 0.6] * 5),
        SimpleNamespace(scores=[0.82, 0.66, 0.9, 0.62] * 5),
        SimpleNamespace(scores=[0.84, 0.74, 0.94, 0.64] * 5),
    ]
    assert run([seed], [0.5], gen5=True, extra=("--noise-runs", "3", "--noise-only")) == 0
    data = json.loads((output_dir / "noise_floor.json").read_text())
    assert data["runs"] == 3 and data["split"] == "validation" and len(data["per_case"]) == 20
    assert data["gate_mean_spread_max"] == 0.02 and data["gate_passed"] is False
    optimize.assert_not_called()
    reflection.assert_not_called()
    assert not (output_dir / CORE_RUNBOOKS[0]).exists()


def test_case_id_regex_matches_gen3_and_gen5_ids():
    from agent.gepa_runbook_optimizer import CASE_ID_REGEX

    for text in ("CASE-02", "CASE-GEN3-01", "CASE-GEN5-C2-INFOSTEALER-01", "case-33279"):
        assert CASE_ID_REGEX.search(text), text
    assert not CASE_ID_REGEX.search("CASE-STUDY")


def test_validate_runbook_candidate_rejects_manifest_literals():
    from agent.gepa_runbook_optimizer import load_forbidden_literals, validate_runbook_candidate

    manifest = Path("configs/evals/gen5/manifest.json")
    literals = load_forbidden_literals(manifest)
    hostname = next(x for x in literals if "-" in x and x.isupper())
    domain = next(x for x in literals if "." in x and x.islower() and not x[0].isdigit())
    clean = {name: "# Clean\nEnrich the alerted host, then decide." for name in CORE_RUNBOOKS}
    assert validate_runbook_candidate(clean, forbidden_literals=literals) == (True, [])

    leaky = dict(clean)
    leaky[CORE_RUNBOOKS[0]] = f"# Leaky\nIf the host is {hostname}, isolate it. Block {domain}."
    ok, violations = validate_runbook_candidate(leaky, forbidden_literals=literals)
    assert not ok and len(violations) == 2 and all("memorization" in v for v in violations)

    boundary = dict(clean)
    boundary[CORE_RUNBOOKS[0]] = f"# Boundary\nSee x{domain} and {hostname}X for unrelated names. Real mention: {domain}."
    ok, violations = validate_runbook_candidate(boundary, forbidden_literals=literals)
    assert not ok and len(violations) == 1 and domain in violations[0]


def test_calculate_loss_penalty_prohibited_entity_violation():
    from agent.gepa_runbook_optimizer import calculate_loss_penalty

    clean = calculate_loss_penalty("MALICIOUS", "MALICIOUS", ["isolate_host"], [])
    assert clean == pytest.approx(1.0)
    violated = calculate_loss_penalty("MALICIOUS", "MALICIOUS", ["isolate_host"], [], prohibited_violation=True)
    assert violated == pytest.approx(math.exp(-1.0))
    assert calculate_loss_penalty("MALICIOUS", "MALICIOUS", ["isolate_host"], [], prohibited_violation=False) == pytest.approx(1.0)


def _gen5_case(index: int = 0) -> dict:
    data = json.loads(Path("configs/evals/gen5/validation.json").read_text(encoding="utf-8"))
    return data["eval_cases"][index]


def _agent_factory_returning(trajectory, text):
    from types import SimpleNamespace

    class FakeAgent:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def query(self, prompt, max_iterations=None):
            return SimpleNamespace(response=text, trajectory=trajectory, usage={"prompt_tokens": 10, "completion_tokens": 5})

    return lambda **kwargs: FakeAgent(**kwargs)


def test_adapter_evaluate_gen5_inert_trajectory_scores_zero():
    from agent.gepa_runbook_optimizer import RunbookGEPAAdapter

    case = _gen5_case()
    adapter = RunbookGEPAAdapter(task_lm="mock", agent_factory=_agent_factory_returning([], ""))
    batch = adapter.evaluate([case], {name: "# Seed" for name in CORE_RUNBOOKS}, capture_traces=True)
    assert batch.scores == [0.0]
    trace = batch.trajectories[0]
    assert trace["inert"] is True and trace["generation"] == 5 and trace["family_id"] == case["family_id"]
    assert trace["usage"]["prompt_tokens"] == 10 and isinstance(trace["latency_ms"], int)


def test_adapter_evaluate_gen5_prohibited_entity_lowers_the_loss_penalty():
    from agent.gepa_runbook_optimizer import RunbookGEPAAdapter

    case = _gen5_case()
    victim = case["prohibited_entities"][0]
    first_lookup = case["oracle"]["lookups"][0]
    trajectory = [
        {"tool": first_lookup["tool"], "args": dict(first_lookup["args"]), "observation": {}},
        {"tool": "isolate_host", "args": {"hostname": victim}, "observation": {"status": "SUCCESS"}},
    ]
    text = "Contained.\n```soc_decision\n" + json.dumps({"verdict": case["ground_truth_label"], "recommended_actions": ["isolate_host"]}) + "\n```"
    adapter = RunbookGEPAAdapter(task_lm="mock", agent_factory=_agent_factory_returning(trajectory, text))
    batch = adapter.evaluate([case], {name: "# Seed" for name in CORE_RUNBOOKS}, capture_traces=True)
    trace = batch.trajectories[0]
    assert trace["prohibited_entity_violations"], "the verifier must flag the prohibited entity"
    assert trace["loss_penalty"] <= math.exp(-1.0) + 1e-9
    assert trace["inert"] is False
```

Add `import math` to the test module imports if missing. If the first validation case's `prohibited_entities[0]` is not a hostname (the isolate target key is `hostname`), pick the first entry that matches `^[A-Z]{2,4}-[A-Z]{3}-[0-9]{2}$` or switch to `block_indicator` with `{"indicator": victim}`; the point is a mutating action against a prohibited entity.

- [ ] **Step 2: Run the tests to confirm the new ones fail**

```bash
.venv/bin/python -m pytest tests/test_gepa_runbook_optimizer.py -q 2>&1 | tail -8
```

Expected: the new tests fail (`TypeError` on `gen5=`, missing names, old selection behavior); the untouched tests pass.

- [ ] **Step 3: Loss penalty, case id regex, literal guard**

`calculate_loss_penalty` (L124-162): add the parameter `prohibited_violation: Optional[bool] = None` and, after the executed-prohibited check (L150-152):

```python
    if prohibited_violation:
        # Gen 5: a mutating action against a prohibited entity weighs the same as a prohibited action.
        loss += 10000.0
```

Document it in the docstring. `CASE_ID_REGEX` (L270-272) becomes `r"\bCASE-(?:GEN\d+-[A-Z0-9-]*?\d+|\d+)\b"` so Gen 5 ids match.

After `CASE_ID_REGEX`, add:

```python
MIN_FORBIDDEN_LITERAL_LENGTH = 4


def compile_forbidden_literals(literals: Optional[Sequence[str]]) -> Optional[re.Pattern]:
    """One case-insensitive alternation over the manifest literals, longest first, bounded so that
    `evil.example` does not match inside `notevil.example` and `10.10.3.4` not inside `10.10.3.45`."""
    cleaned = sorted(
        {str(x).strip() for x in (literals or []) if len(str(x).strip()) >= MIN_FORBIDDEN_LITERAL_LENGTH},
        key=lambda s: (-len(s), s),
    )
    if not cleaned:
        return None
    body = "|".join(re.escape(x) for x in cleaned)
    return re.compile(rf"(?<![A-Za-z0-9-])(?:{body})(?![A-Za-z0-9-])", re.IGNORECASE)


def load_forbidden_literals(manifest_path: Path) -> List[str]:
    """`manifest.forbidden_literals` from the Gen 5 manifest (spec section 6.5)."""
    data = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    literals = data.get("forbidden_literals")
    if not isinstance(literals, list) or not literals:
        raise ValueError(f"{manifest_path} carries no forbidden_literals; rebuild with gen5_instancer.py build")
    return [str(x) for x in literals]
```

`validate_runbook_candidate` gains `forbidden_literals: Optional[Sequence[str]] = None`; compile once before the loop (`literal_pattern = compile_forbidden_literals(forbidden_literals)`) and, after the case id check inside the loop, add:

```python
        if literal_pattern is not None:
            for match in sorted({m.group(0) for m in literal_pattern.finditer(cleaned_content)}):
                violations.append(
                    f"{filename}: Contains instance literal '{match}' from the Gen 5 manifest forbidden_literals (memorization)."
                )
```

Add `Sequence` to the `typing` import if missing. Update the docstring's numbered list with item 6.

- [ ] **Step 4: Adapter: literal guard, Gen 5 verifier kwargs, inert, entity violations, telemetry**

`RunbookGEPAAdapter.__init__` (L343-378): add `forbidden_literals: Optional[Sequence[str]] = None` and store `self.forbidden_literals = list(forbidden_literals or [])`. In the validator call inside `evaluate` (L394-429) pass `forbidden_literals=self.forbidden_literals`.

Per case (L446-520):

```python
                is_gen5 = int(case.get("generation") or 0) >= 5
                t_query = time.time()
                response = agent.query(prompt, max_iterations=self.max_iterations)
                latency_ms = int(round((time.time() - t_query) * 1000))
                # (the existing lines between here and the verifier call, trajectory extraction and report parsing, stay unchanged)
                gen5_kwargs: Dict[str, Any] = {}
                if is_gen5:
                    gen5_kwargs = {
                        "prohibited_entities": case.get("prohibited_entities", []),
                        "liveness": case.get("liveness"),
                        "generation": int(case.get("generation") or 0),
                    }
                traj_verif = verify_agent_trajectory(
                    trajectory=agent_traj,
                    expected_actions=case.get("expected_actions", []),
                    prohibited_actions=case.get("prohibited_actions", []),
                    expected_entities=case.get("expected_entities", []),
                    response_text=resp_text,
                    **gen5_kwargs,
                )
                inert = bool(is_gen5 and getattr(traj_verif, "inert", False))
                entity_violations = list(getattr(traj_verif, "prohibited_entity_violations", []) or []) if is_gen5 else []
```

Epistemic points (L469): `required_steps = max(1, int(((case.get("liveness") or {}).get("min_epistemic_steps", 1)) or 1)) if is_gen5 else 1` and `epistemic_pts = 25.0 * min(1.0, traj_verif.epistemic_step_count / float(required_steps))`.

Loss penalty (L507-512): add `prohibited_violation=bool(entity_violations) if is_gen5 else None`.

Fitness (L515-520): after computing `fitness`, `if inert: fitness = 0.0`.

Trace dict (L526-543): add

```python
                        "inert": inert,
                        "prohibited_entity_violations": entity_violations,
                        "generation": int(case.get("generation") or 0),
                        "family_id": case.get("family_id"),
                        "usage": _response_usage(response),
                        "latency_ms": latency_ms,
```

with the module helper:

```python
def _response_usage(response: Any) -> Dict[str, Any]:
    usage = getattr(response, "usage", None)
    if usage is None and hasattr(response, "get"):
        usage = response.get("usage")
    return dict(usage) if isinstance(usage, dict) else {}
```

`import time` at the top if missing.

`make_reflective_dataset` (L576-651): where the feedback text for a trace is assembled, append `"The agent neither investigated nor decided (inert trajectory). The runbook must require at least one enrichment lookup before any conclusion and must always end with a verdict."` when `trace.get("inert")`, and `f"The agent took a containment action against an entity the case marks as out of scope ({', '.join(violations)}). The runbook must confirm the target is the alerted asset before isolating or blocking."` when `trace.get("prohibited_entity_violations")`.

- [ ] **Step 5: CLI, split loading, selection, save, noise floor**

`build_arg_parser` (L692-823): `--evalset` default `None` with help `"Explicit evalset JSON (legacy). When omitted, the Gen 5 --train-split and --val-split bundles are loaded through the exposure ledger."`; add

```python
    parser.add_argument("--train-split", choices=list(gen5_exposure.SPLITS), default="train", help="Gen 5 split for reflection minibatches")
    parser.add_argument("--val-split", choices=list(gen5_exposure.SPLITS), default="validation", help="Gen 5 split for Pareto selection, the noise floor, and the staircase")
    parser.add_argument("--purpose", default="gepa runbook hillclimb", help="Purpose recorded in the exposure ledger")
    parser.add_argument("--manifest", default=str(gen5_exposure.MANIFEST_PATH), help="Gen 5 manifest providing forbidden_literals")
    parser.add_argument("--run-id", default=None, help="Run id shared by the ledger entries and evolution_metadata.json (default: generated)")
    parser.add_argument("--noise-only", action="store_true", default=False, help="Measure the K-run seed noise floor on --val-split, write noise_floor.json, and exit")
```

and change the `--noise-runs` help to `"K >= 2 seed passes on the validation split for the noise floor (0 disables)"`.

`main` (L826-865) dataset block becomes:

```python
    run_id = parsed_args.run_id or gen5_exposure.new_run_id()
    exposure_entries: List[Dict[str, Any]] = []
    forbidden_literals: List[str] = []
    manifest_path = Path(parsed_args.manifest) if Path(parsed_args.manifest).is_absolute() else ROOT_DIR / parsed_args.manifest

    if parsed_args.evalset:
        evalset_path = ROOT_DIR / parsed_args.evalset if not Path(parsed_args.evalset).is_absolute() else Path(parsed_args.evalset)
        ...  # existing load, empty check, and --split-train-val slicing unchanged
        if manifest_path.exists():
            forbidden_literals = load_forbidden_literals(manifest_path)
        train_split_name, val_split_name = ("legacy[:6]", "legacy[6:]") if parsed_args.split_train_val else ("legacy", "legacy")
    else:
        if parsed_args.train_split == parsed_args.val_split:
            print("--train-split and --val-split must differ.", file=sys.stderr)
            return 1
        try:
            trainset, train_entry = gen5_exposure.load_split(
                parsed_args.train_split, purpose=f"{parsed_args.purpose} (train)", model=parsed_args.task_lm, run_id=run_id
            )
            valset, val_entry = gen5_exposure.load_split(
                parsed_args.val_split, purpose=f"{parsed_args.purpose} (validation)", model=parsed_args.task_lm, run_id=run_id
            )
        except (gen5_exposure.FinalTestSealedError, gen5_exposure.ExposureError) as err:
            print(f"Gen 5 split load refused: {err}", file=sys.stderr)
            return 1
        exposure_entries = [train_entry, val_entry]
        eval_cases = valset
        evalset_path = gen5_exposure.bundle_path(parsed_args.val_split)
        forbidden_literals = load_forbidden_literals(manifest_path)
        train_split_name, val_split_name = parsed_args.train_split, parsed_args.val_split
```

The optimizer never passes `unseal_final_test`, so `--val-split final_test` (or `--train-split final_test`) is refused by the loader; that is the intended behavior and the test asserts it. The guard block (L869-898) is unchanged: Gen 5 bundles live inside `ROOT_DIR`, so the default protected paths and the repo lock apply unless `--lock-file` is given.

Adapter construction gains `forbidden_literals=forbidden_literals`. Noise floor (L931-957) becomes:

```python
    tau_accept = float(parsed_args.min_delta)
    noise_metrics_dict: Optional[Dict[str, Any]] = None
    if parsed_args.noise_runs >= 2:
        runs: List[List[float]] = []
        for _ in range(int(parsed_args.noise_runs)):
            batch = adapter.evaluate(valset, seed_candidate, capture_traces=False)
            scores_k = getattr(batch, "scores", None)
            if (
                not isinstance(scores_k, list) or not scores_k
                or not all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in scores_k)
            ):
                runs = []
                break
            runs.append([float(x) for x in scores_k])
        if runs and len({len(r) for r in runs}) == 1:
            nf = estimate_noise_floor(
                *runs, min_delta=parsed_args.min_delta, case_ids=[str(c.get("eval_id", i)) for i, c in enumerate(valset)]
            )
            tau_accept = nf.tau_accept
            noise_metrics_dict = nf.to_dict()
            write_noise_floor_json(
                nf,
                output_dir / "noise_floor.json",
                extra={
                    "model": parsed_args.task_lm,
                    "split": val_split_name,
                    "run_id": run_id,
                    "git_sha": gen5_exposure.git_sha(),
                    "gate_mean_spread_max": 0.02,
                    "gate_passed": nf.aggregate_noise <= 0.02,
                },
            )
            print(
                f"Noise floor over {nf.runs} runs: mean spread {nf.aggregate_noise:.4f}, "
                f"mean per-case std {nf.mean_case_std:.4f}, tau_accept {nf.tau_accept:.4f} "
                f"(gate: spread <= 0.02 {'PASS' if nf.aggregate_noise <= 0.02 else 'FAIL'})"
            )
        else:
            print("Noise floor skipped: the adapter did not return numeric score lists.", file=sys.stderr)

    if parsed_args.noise_only:
        if noise_metrics_dict is None:
            print("--noise-only requires --noise-runs >= 2 and numeric scores.", file=sys.stderr)
            return 1
        metadata_only = {"run_id": run_id, "task_lm": parsed_args.task_lm, "train_split": train_split_name,
                         "val_split": val_split_name, "exposure": exposure_entries, "noise_floor": noise_metrics_dict,
                         "noise_only": True, "runbooks_written": False}
        write_evolution_metadata(output_dir, metadata_only)
        return 0
```

The old bare `except Exception: pass` goes away; the explicit validity check above is what kept the mocked tests quiet.

Candidate ranking loop: pass `forbidden_literals=forbidden_literals` to `validate_runbook_candidate` (L1010-1014) and count `valid_count += 1` after a candidate passes validation. Replace L1069-1087 and L1128-1134 with:

```python
    reason, write_runbooks = select_candidate_outcome(selected_index, valid_count)
    best_candidate = seed_candidate if selected_index in (None, 0) else candidates[selected_index]
    metadata: Dict[str, Any] = {
        "run_id": run_id,
        "task_lm": parsed_args.task_lm,
        "reflection_lm": parsed_args.reflection_lm,
        "max_metric_calls": parsed_args.max_metric_calls,
        "seed": parsed_args.seed,
        "evalset": str(evalset_path) if parsed_args.evalset else None,
        "train_split": train_split_name,
        "val_split": val_split_name,
        "exposure": exposure_entries,
        "forbidden_literals_count": len(forbidden_literals),
        "selected_candidate_index": selected_index,
        "selected_validation_score": selected_score,
        "best_score": selected_score,
        "selection_reason": reason,
        "runbooks_written": write_runbooks,
        "harness_composite_sha256": composite_sha,
        "tau_accept": tau_accept,
    }
    if noise_metrics_dict is not None:
        metadata["noise_floor"] = noise_metrics_dict
    ...  # staircase block unchanged except _staircase_eval (below)
    if write_runbooks:
        print(f"Saving evolved runbooks to {output_dir}...")
        save_runbooks(candidate=best_candidate, output_dir=output_dir, metadata=metadata)
    else:
        print(f"Seed retained ({reason}); runbooks in {output_dir} are left untouched.")
        write_evolution_metadata(output_dir, metadata)
    print("Runbook evolution complete.")
    return 0
```

with the module helpers (next to `save_runbooks`):

```python
def write_evolution_metadata(output_dir: Path, metadata: Dict[str, Any]) -> Path:
    """Writes evolution_metadata.json without touching any runbook file."""
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    meta_path = target_dir / "evolution_metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return meta_path


def select_candidate_outcome(selected_index: Optional[int], valid_count: int) -> Tuple[str, bool]:
    """(selection_reason, write_runbooks). Only a non-seed winner is ever written to disk."""
    if selected_index is not None and selected_index > 0:
        return "highest_valid_validation_score", True
    if valid_count > 0:
        return "seed_retained_all_candidates_reverted", False
    return "seed_fallback_no_valid_candidates", False
```

`_staircase_eval` (L1090-1111) returns the 3-tuple:

```python
            traces = list(batch_res.trajectories or [])
            telemetry = {
                "inert": [bool(t.get("inert", False)) for t in traces],
                "tokens_in": [(t.get("usage") or {}).get("prompt_tokens") for t in traces],
                "tokens_out": [(t.get("usage") or {}).get("completion_tokens") for t in traces],
                "latency_ms": [t.get("latency_ms") for t in traces],
            }
            return sc_list, lp_list, telemetry
```

- [ ] **Step 6: Run the optimizer tests and the neighbors**

```bash
.venv/bin/python -m pytest tests/test_gepa_runbook_optimizer.py tests/test_hillclimb_harness.py tests/test_gen5_exposure.py -q 2>&1 | tail -5
```

Expected: all pass. `test_cli_disciplined_hillclimber_flags_and_ledger` (L831-928) drives `--cost-staircase` with its own adapter; if it asserts on a two-element evaluator return, extend the assertion to accept the third element rather than removing telemetry. Confirm the committed ledger is still empty: `wc -c configs/evals/gen5/exposure.jsonl` prints `0`.

- [ ] **Step 7: Commit**

```bash
git add agent/gepa_runbook_optimizer.py tests/test_gepa_runbook_optimizer.py
git commit -m "feat(gepa): Gen 5 splits via the ledger, manifest literal guard, inert and entity-violation fitness, no seed overwrite, K-run noise floor"
```

### Task 5: `soc-cli` Gen 5 lookup and the transport parity gate

**Files:**
- Modify: `scripts/soc_sandbox_cli.py`
- Modify: `scripts/gen5_reference_policies.py`
- Modify: `Justfile` (`gen5-calibrate` passes `--transport both`)
- Create: `tests/test_gen5_transport_parity.py`
- Regenerate: `docs/soc_eval_results/GEN5_CALIBRATION.md`, `docs/soc_eval_results/GEN5_CALIBRATION.json`

**Interfaces:**
- Produces: `soc_sandbox_cli.GEN5_EVALSET_PATHS`, `DEFAULT_EVALSET_PATHS` extended, `SOC_EVALSET_FILE` honored by `run_soc_cli`, `load_eval_case(case_id, evalset_path=None, strict=None)` raising `LookupError` for unknown `CASE-GEN5-` ids, `reset` returning `(1, {"status": "ERROR", ...})` on that error; `gen5_reference_policies.TRANSPORTS`, `write_case_bundle(case, path)`, `execute_soc_cli(case, trial, workdir)`, `execute_trial(case, trial, transport, workdir)`, `run_policy_on_case(..., transport="python")` rows with `transport`, `evaluate_transport_parity(results_python, results_cli)`, `PARITY_TOLERANCE = 0.01`, `run --transport`, `calibrate --transport {python,soc-cli,both}` (default `both`), report JSON key `results_by_transport`, gate key `transport_parity`.
- Consumes: Plan 1 state snapshot round trip; Plan 2 Task 7 functions.
- Consumed by: Task 6 (`SOC_EVALSET_FILE`, strict lookup, `plan_oracle` rendering), Task 7 docs.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_gen5_transport_parity.py`:

```python
"""soc-cli reads Gen 5 cases, and the reference policies score the same through both transports."""

import json
from pathlib import Path

import pytest

from scripts import gen5_reference_policies as rp
from scripts.soc_sandbox_cli import DEFAULT_EVALSET_PATHS, load_eval_case, run_soc_cli

ROOT_DIR = Path(__file__).resolve().parent.parent
GEN5 = ROOT_DIR / "configs" / "evals" / "gen5"


def _validation_cases():
    return json.loads((GEN5 / "validation.json").read_text(encoding="utf-8"))["eval_cases"]


def _one_per_family(cases):
    seen, picked = set(), []
    for case in cases:
        if case["family_id"] not in seen:
            seen.add(case["family_id"])
            picked.append(case)
    return picked


def _env(tmp_path: Path, case_id: str, evalset_file: Path = None) -> dict:
    env = {
        "SOC_CASE_ID": case_id,
        "SOC_STATE_FILE": str(tmp_path / "state.json"),
        "SOC_TRAJECTORY_FILE": str(tmp_path / "trajectory.jsonl"),
    }
    if evalset_file is not None:
        env["SOC_EVALSET_FILE"] = str(evalset_file)
    return env


def test_default_evalset_paths_include_the_gen5_bundles_after_gen3() -> None:
    names = [p.name for p in DEFAULT_EVALSET_PATHS]
    assert names[0] == "soc_tier1_interactive.json"
    assert "state_bundle.json" in names
    assert {"validation.json", "final_test.json", "train.json"} <= set(names)


def test_soc_cli_resets_a_gen5_case_from_the_committed_bundles(tmp_path: Path) -> None:
    case = _validation_cases()[0]
    env = _env(tmp_path, case["eval_id"])
    rc, payload = run_soc_cli(["reset"], env=env)
    assert rc == 0 and payload["status"] == "RESET"
    hostname = next(iter(case["environment_state"]["hosts"]))
    rc, payload = run_soc_cli(["lookup_entity", "--entity_id", hostname], env=env)
    assert rc == 0 and payload.get("status") != "NOT_FOUND"
    assert hostname.lower() in json.dumps(payload).lower()
    records = [json.loads(line) for line in (tmp_path / "trajectory.jsonl").read_text().splitlines()]
    assert records[0]["tool"] == "lookup_entity"


def test_soc_cli_honors_soc_evalset_file(tmp_path: Path) -> None:
    case = dict(_validation_cases()[0])
    case["eval_id"] = "CASE-GEN5-TEST-01"
    bundle = tmp_path / "bundle.json"
    rp.write_case_bundle(case, bundle)
    rc, payload = run_soc_cli(["reset"], env=_env(tmp_path, "CASE-GEN5-TEST-01", bundle))
    assert rc == 0 and payload["case_id"] == "CASE-GEN5-TEST-01"


def test_soc_cli_refuses_an_unknown_gen5_case_id(tmp_path: Path) -> None:
    rc, payload = run_soc_cli(["reset"], env=_env(tmp_path, "CASE-GEN5-NOPE-99"))
    assert rc == 1 and payload["status"] == "ERROR" and "CASE-GEN5-NOPE-99" in payload["error"]
    assert not (tmp_path / "state.json").exists()


def test_gen3_lookup_keeps_the_stub_fallback() -> None:
    assert load_eval_case("CASE-UNKNOWN") == {"eval_id": "CASE-UNKNOWN"}
    with pytest.raises(LookupError):
        load_eval_case("CASE-UNKNOWN", strict=True)


@pytest.mark.parametrize("policy", ["oracle", "shotgun"])
def test_python_and_soc_cli_transports_agree_per_case(tmp_path: Path, policy: str) -> None:
    for case in _one_per_family(_validation_cases()):
        py = rp.run_policy_on_case(case, policy, 1, tmp_path / "py" / case["eval_id"], split="validation", transport="python")
        cli = rp.run_policy_on_case(case, policy, 1, tmp_path / "cli" / case["eval_id"], split="validation", transport="soc-cli")
        assert cli["transport"] == "soc-cli" and py["transport"] == "python"
        assert abs(py["mean"] - cli["mean"]) <= rp.PARITY_TOLERANCE, (case["eval_id"], py["mean"], cli["mean"])
        if policy == "oracle":
            assert cli["mean"] == 1.0, (case["eval_id"], cli["notes"])


def test_evaluate_transport_parity_flags_disagreements() -> None:
    py = {"oracle": [{"eval_id": "a", "mean": 1.0}, {"eval_id": "b", "mean": 1.0}], "shotgun": [{"eval_id": "a", "mean": 0.2}, {"eval_id": "b", "mean": 0.2}]}
    cli = {"oracle": [{"eval_id": "a", "mean": 1.0}, {"eval_id": "b", "mean": 0.95}], "shotgun": [{"eval_id": "a", "mean": 0.2}, {"eval_id": "b", "mean": 0.2}]}
    gate = rp.evaluate_transport_parity(py, cli)
    assert gate["passed"] is False and gate["failing_cases"] == ["oracle:b"] and gate["max_delta"] == pytest.approx(0.05)
    cli["oracle"][1]["mean"] = 1.0
    assert rp.evaluate_transport_parity(py, cli)["passed"] is True


def test_calibrate_both_transports_reports_parity(tmp_path: Path) -> None:
    report = tmp_path / "cal.md"
    report_json = tmp_path / "cal.json"
    rc = rp.main([
        "calibrate", "--trials", "1", "--splits", "validation", "--transport", "both",
        "--report", str(report), "--json", str(report_json),
    ])
    assert rc == 0
    data = json.loads(report_json.read_text(encoding="utf-8"))
    assert data["meta"]["transport"] == "both"
    assert set(data["results_by_transport"]) == {"python", "soc-cli"}
    assert data["gates"]["transport_parity"]["passed"] is True and data["gates"]["all_passed"] is True
    assert "Transport parity" in report.read_text(encoding="utf-8")


def test_run_command_accepts_the_soc_cli_transport(capsys) -> None:
    rc = rp.main(["run", "--policy", "oracle", "--split", "validation", "--limit", "2", "--transport", "soc-cli"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "oracle: 2 case(s), mean 1.0000" in out
```

- [ ] **Step 2: Run the tests to confirm they fail**

```bash
.venv/bin/python -m pytest tests/test_gen5_transport_parity.py -q 2>&1 | tail -5
```

Expected: failures on the missing bundle paths, `strict`, `write_case_bundle`, `transport`, and `evaluate_transport_parity`.

- [ ] **Step 3: `soc_sandbox_cli.py`**

Replace `DEFAULT_EVALSET_PATHS` (L18-21):

```python
GEN5_CONTAINER_STATE_BUNDLE = Path("/app/configs/evals/gen5/state_bundle.json")
GEN5_EVALSET_PATHS = [
    GEN5_CONTAINER_STATE_BUNDLE,
    ROOT_DIR / "configs" / "evals" / "gen5" / "validation.json",
    ROOT_DIR / "configs" / "evals" / "gen5" / "final_test.json",
    ROOT_DIR / "configs" / "evals" / "gen5" / "train.json",
]

DEFAULT_EVALSET_PATHS = [
    Path("/app/soc_tier1_interactive.json"),
    ROOT_DIR / "configs" / "evals" / "gen3" / "soc_tier1_interactive.json",
    *GEN5_EVALSET_PATHS,
]
```

Replace `load_eval_case` (L83-92):

```python
def load_eval_case(case_id: str, evalset_path: Optional[Path] = None, strict: Optional[bool] = None) -> Dict[str, Any]:
    """Loads a case dict by eval_id from the explicit evalset or the default search list.

    Gen 3 callers keep the stub fallback (`{"eval_id": case_id}`) so an unknown
    id still builds the overlay environment. Gen 5 ids (`CASE-GEN5-...`) are
    strict by default: a miss raises LookupError, because silently building a
    Gen 3 overlay for a Gen 5 case would score the wrong world.
    """
    if strict is None:
        strict = case_id.upper().startswith("CASE-GEN5-")
    candidate_paths = [Path(evalset_path)] if evalset_path else DEFAULT_EVALSET_PATHS
    for path in candidate_paths:
        if path and path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            for case in data.get("eval_cases", []):
                if case.get("eval_id") == case_id:
                    return dict(case)
    if strict:
        searched = ", ".join(str(p) for p in candidate_paths)
        raise LookupError(f"case {case_id} not found in any evalset ({searched})")
    return {"eval_id": case_id}
```

In `run_soc_cli` (L233-295): after `traj_path = ...` add

```python
    if evalset_path is None and runtime_env.get("SOC_EVALSET_FILE"):
        evalset_path = Path(runtime_env["SOC_EVALSET_FILE"])
```

and wrap the `reset` body and the two `_restore_environment` calls so a `LookupError` returns `1, {"status": "ERROR", "error": str(err), "case_id": case_id}`. The simplest shape is one helper:

```python
def _error_payload(err: Exception, case_id: str) -> Tuple[int, Dict[str, Any]]:
    return 1, {"status": "ERROR", "error": str(err), "case_id": case_id}
```

used as `except LookupError as err: return _error_payload(err, case_id)` at the three sites. `reset` must not write the state file before the lookup succeeds (it does not today: `load_eval_case` runs first).

- [ ] **Step 4: `gen5_reference_policies.py`: the soc-cli transport and the parity gate**

Add near the constants:

```python
TRANSPORTS = ("python", "soc-cli", "both")
PARITY_POLICIES = ("oracle", "shotgun")
PARITY_TOLERANCE = 0.01
```

Import `run_soc_cli` from `scripts.soc_sandbox_cli` (the module is already imported for `EPISTEMIC_TOOLS` and `load_eval_case` in Plan 2). Add after `execute_python`:

```python
def write_case_bundle(case: Dict[str, Any], path: Path) -> Path:
    """A one-case Gen 5 bundle: what the container's tests/case.json looks like."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    bundle = {"evalset_id": "soc_tier1_families", "generation": 5, "split": case.get("split"), "eval_cases": [case]}
    path.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def execute_soc_cli(case: Dict[str, Any], trial: PolicyTrial, workdir: Path) -> List[Dict[str, Any]]:
    """Runs the trial's steps through soc-cli in-process, the way solve.sh does in the container.

    Each step is one `run_soc_cli([tool, "--json", args])` call against a state
    file that persists between calls; the records come back from the trajectory
    JSONL soc-cli writes, so what is scored is what the CLI logged.
    """
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    bundle = write_case_bundle(case, workdir / "case_bundle.json")
    state_path = workdir / "state.json"
    traj_path = workdir / "cli_trajectory.jsonl"
    env = {
        "SOC_CASE_ID": case["eval_id"],
        "SOC_STATE_FILE": str(state_path),
        "SOC_TRAJECTORY_FILE": str(traj_path),
        "SOC_EVALSET_FILE": str(bundle),
    }
    rc, payload = run_soc_cli(["reset"], env=env)
    if rc != 0:
        raise RuntimeError(f"soc-cli reset failed for {case['eval_id']}: {payload}")
    for step in trial.steps:
        rc, payload = run_soc_cli([step["tool"], "--json", json.dumps(step["args"])], env=env)
        if rc != 0:
            raise RuntimeError(f"soc-cli {step['tool']} failed for {case['eval_id']}: {payload}")
    records = [json.loads(line) for line in traj_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [{"tool": r["tool"], "args": r["args"], "observation": r["observation"]} for r in records]


def execute_trial(case: Dict[str, Any], trial: PolicyTrial, transport: str, workdir: Path) -> List[Dict[str, Any]]:
    if transport == "python":
        return execute_python(case, trial)
    if transport == "soc-cli":
        return execute_soc_cli(case, trial, workdir)
    raise ValueError(f"unknown transport {transport!r}; expected python or soc-cli")
```

`run_policy_on_case` gains `transport: str = "python"`, calls `execute_trial(case, trial, transport, Path(workdir) / f"trial_{index}")`, and adds `"transport": transport` to the row. Add:

```python
def evaluate_transport_parity(results_python: Dict[str, List[Dict[str, Any]]], results_cli: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    """Oracle and Shotgun per-case means must agree within PARITY_TOLERANCE across transports (spec 8.1)."""
    failing: List[str] = []
    max_delta = 0.0
    for policy in PARITY_POLICIES:
        cli_by_id = {row["eval_id"]: row for row in results_cli.get(policy, [])}
        for row in results_python.get(policy, []):
            other = cli_by_id.get(row["eval_id"])
            delta = abs(float(row["mean"]) - float(other["mean"])) if other is not None else 1.0
            max_delta = max(max_delta, delta)
            if other is None or delta > PARITY_TOLERANCE:
                failing.append(f"{policy}:{row['eval_id']}")
    return {
        "rule": f"oracle and shotgun per-case means agree within {PARITY_TOLERANCE} between python and soc-cli",
        "passed": not failing,
        "failing_cases": failing,
        "max_delta": round(max_delta, 4),
    }
```

`command_run`: add `run.add_argument("--transport", choices=("python", "soc-cli"), default="python")` and pass `transport=args.transport`. `command_calibrate`: add `calibrate.add_argument("--transport", choices=TRANSPORTS, default="both")`; run the four policies once per selected transport into `results_by_transport[transport]`; `results = results_by_transport.get("python") or results_by_transport["soc-cli"]`; `gates = evaluate_gates(results)`; when both ran, `gates["transport_parity"] = evaluate_transport_parity(results_by_transport["python"], results_by_transport["soc-cli"])` and `gates["all_passed"] = gates["all_passed"] and gates["transport_parity"]["passed"]`; `meta["transport"] = args.transport`; the JSON payload gains `"results_by_transport": results_by_transport` (extend `write_reports` with an optional `extra` dict merged into the JSON). In `render_markdown`, after the gates table, add when `gates.get("transport_parity")`:

```python
        parity = gates["transport_parity"]
        lines += [
            "",
            f"Transport parity ({parity['rule']}): **{'PASS' if parity['passed'] else 'FAIL'}**, "
            f"max delta {parity['max_delta']:.4f}, failing: {', '.join(parity['failing_cases'][:8]) or '-'}.",
        ]
```

- [ ] **Step 5: Run the tests, then regenerate the calibration report**

```bash
.venv/bin/python -m pytest tests/test_gen5_transport_parity.py tests/test_soc_sandbox_cli.py tests/test_gen5_reference_policies.py tests/test_verify_harbor_soc.py tests/test_harbor_soc_tasks.py -q 2>&1 | tail -5
```

Expected: all pass. A parity failure means the state snapshot round trip in `SocEnvironment` (Plan 1) loses something between soc-cli calls, or `_parse_tool_args` renames an argument; fix the cause, never widen `PARITY_TOLERANCE`.

In the `Justfile`, make the `gen5-calibrate` recipe (Plan 2) pass the transport:

```make
# Run the four Gen 5 reference policies in both transports and apply the spec 8.1 gates (Usage: just gen5-calibrate [trials])
gen5-calibrate TRIALS="3":
    @.venv/bin/python scripts/gen5_reference_policies.py calibrate --trials {{TRIALS}} --transport both
```

Then regenerate and inspect:

```bash
just gen5-calibrate
awk '/Transport parity|all gates passed|GATE FAILURE/' docs/soc_eval_results/GEN5_CALIBRATION.md
```

Expected: `all gates passed` and a `PASS` parity line. `tests/test_justfile_recipes.py` may assert the recipe text; update its expectation if it does.

- [ ] **Step 6: Commit**

```bash
git add scripts/soc_sandbox_cli.py scripts/gen5_reference_policies.py Justfile tests/test_gen5_transport_parity.py docs/soc_eval_results/GEN5_CALIBRATION.md docs/soc_eval_results/GEN5_CALIBRATION.json
git commit -m "feat(gen5): soc-cli reads Gen 5 bundles; reference policies run in both transports with a parity gate"
```

---

### Task 6: Harbor generator Gen 5 mode and the committed `evals/harbor_soc_gen5/` tree

**Files:**
- Modify: `scripts/generate_harbor_soc_tasks.py`
- Create: `tests/test_harbor_soc_gen5_tasks.py`
- Generate and commit: `evals/harbor_soc_gen5/**` (100 task directories plus `evals/harbor_soc_gen5/manifest.json`)
- Modify: `Justfile` (`harbor-soc-gen5-generate`, `harbor-soc-gen5-check`, `harbor-soc-gen5-test`; `gen5-check` gains the Harbor `--check`)

**Interfaces:**
- Produces: constants `GEN5_ROOT`, `GEN5_MANIFEST_PATH`, `DEFAULT_GEN5_HARBOR_OUT`, `DEFAULT_GEN5_RUNBOOKS_DIR`, `DEFAULT_GEN5_ARMS = ("clean_skills", "gepa_evolved_skills")`, `GEN5_HARBOR_SPLITS = ("validation", "final_test")`, `GEN5_GENERATOR_VERSION`, `GEN5_CONTAINER_STATE_BUNDLE_REL = "configs/evals/gen5/state_bundle.json"`, `GEN5_STATE_KEYS`, `GEN5_EVOLVED_RUNBOOKS`, `GEN5_DIFFICULTY_NAMES`, `GEN5_DOCKERFILE_CONTENT`; functions `_case_slug` (generalized), `load_gen5_split(root, split)`, `strip_case_for_state(case)`, `build_state_bundle(cases)`, `_load_evolved_runbooks(rb_dir)`, `_build_gen5_task_toml(case, arm, split, slug, case_sha256)`, `_build_gen5_instruction_md(case, arm, clean_skill, noisy_skill, evolved_runbooks)`, `_build_gen5_solve_sh(case)`, `_build_gen5_test_sh()`, `_populate_gen5_environment(env_dir, state_bundle_text)`, `write_gen5_tree(output_root, evalset_root, splits, arms, gepa_runbooks_dir) -> summary`, `generate_harbor_soc_gen5_suite(...)` (same signature; removes and rewrites `output_root`), `check_gen5_tree(output_root, ...) -> List[str]`; CLI flags `--gen3`, `--evalset`, `--split`, `--arms`, `--out`, `--gepa-runbooks-dir`, `--check`.
- Consumes: the Plan 2 bundles and manifest; `scripts.gen5_instancer.sha256_text` and `canonical_json` (the same hash the manifest records); `scripts.gen5_reference_policies.plan_oracle` (Plan 2 Task 7); Task 5 `soc-cli` (`SOC_EVALSET_FILE`, strict lookup, `--json` arguments); the Plan 2 verifier flags `--evalset-file`, `--manifest-file`, `--metrics-file`, `--split`.
- Consumed by: Task 7 (docs, `gen5-check`, the owner checklist). `verify_harbor_soc.py` inside the container needs nothing new: the Dockerfile copies the same modules as Gen 3 plus the state bundle.

Why the tree looks the way it does (decision 9): the Gen 3 image shipped the whole evalset, answers included, into `/app`, which was acceptable for a 10-case suite whose answers were in every blog post. Gen 5 is a held-out suite. The image therefore carries `state_bundle.json`, which holds only what `SocEnvironment.from_eval_case` and the prompt need, and the answer key travels in `tests/case.json`, which Harbor copies in for verification only. `solve.sh` is rendered from `plan_oracle`, so the container oracle and the calibration oracle are one function. `test.sh` locates `case.json` and `manifest.json` relative to itself, so it does not depend on where Harbor mounts `tests/`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_harbor_soc_gen5_tasks.py`:

```python
"""Harbor Gen 5 tasks: layout, answer-key isolation, one environment hash, oracle reward, --check."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib

import pytest

from scripts import generate_harbor_soc_tasks as gen
from scripts.gen5_instancer import canonical_json, sha256_text
from scripts.soc_sandbox_cli import GEN5_CONTAINER_STATE_BUNDLE

ROOT_DIR = Path(__file__).resolve().parent.parent
GEN5 = ROOT_DIR / "configs" / "evals" / "gen5"
COMMITTED_TREE = ROOT_DIR / "evals" / "harbor_soc_gen5"
ANSWER_KEYS = (
    "oracle", "assertions", "reference", "expected_actions", "prohibited_actions",
    "expected_entities", "prohibited_entities", "ground_truth_label", "liveness",
    "difficulty", "family_id", "split", "name",
)


@pytest.fixture(scope="module")
def generated(tmp_path_factory) -> dict:
    out = tmp_path_factory.mktemp("harbor_gen5") / "tree"
    summary = gen.generate_harbor_soc_gen5_suite(output_root=out)
    return {"out": out, "summary": summary}


def _task_dirs(out: Path):
    return sorted(p.parent for p in out.rglob("task.toml"))


def _meta(task_dir: Path) -> dict:
    return tomllib.loads((task_dir / "task.toml").read_text(encoding="utf-8"))


def _full_case(task_dir: Path) -> dict:
    return json.loads((task_dir / "tests" / "case.json").read_text(encoding="utf-8"))["eval_cases"][0]


def _one_per_family(task_dirs):
    seen, picked = set(), []
    for task_dir in task_dirs:
        family = _full_case(task_dir)["family_id"]
        if family not in seen:
            seen.add(family)
            picked.append(task_dir)
    return picked


def test_slug_handles_gen3_and_gen5_ids() -> None:
    assert gen._case_slug("CASE-GEN3-01-LOKIBOT-C2") == "case-01-lokibot-c2"
    assert gen._case_slug("CASE-GEN5-C2-INFOSTEALER-01") == "case-c2-infostealer-01"


def test_container_bundle_path_matches_soc_cli() -> None:
    assert Path("/app") / gen.GEN5_CONTAINER_STATE_BUNDLE_REL == GEN5_CONTAINER_STATE_BUNDLE
    assert f"COPY state_bundle.json /app/{gen.GEN5_CONTAINER_STATE_BUNDLE_REL}" in gen.GEN5_DOCKERFILE_CONTENT
    assert "soc_tier1_interactive.json" not in gen.GEN5_DOCKERFILE_CONTENT


def test_evolved_runbook_list_mirrors_the_optimizer() -> None:
    from agent.gepa_runbook_optimizer import CORE_RUNBOOKS

    assert gen.GEN5_EVOLVED_RUNBOOKS == tuple(CORE_RUNBOOKS)
    for name in gen.GEN5_EVOLVED_RUNBOOKS:
        assert (gen.DEFAULT_GEN5_RUNBOOKS_DIR / name).exists(), name


def test_strip_case_for_state_keeps_only_world_state() -> None:
    case = gen.load_gen5_split(GEN5, "validation")[0]
    stripped = gen.strip_case_for_state(case)
    assert set(stripped) <= set(gen.GEN5_STATE_KEYS)
    assert stripped["eval_id"] == case["eval_id"] and stripped["generation"] == 5
    assert stripped["prompt"] == case["prompt"]
    assert stripped["environment_state"] == case["environment_state"]
    for key in ANSWER_KEYS:
        assert key not in stripped, key


def test_build_state_bundle_is_sorted_and_deterministic() -> None:
    cases = gen.load_gen5_split(GEN5, "validation") + gen.load_gen5_split(GEN5, "final_test")
    first = gen.build_state_bundle(cases)
    second = gen.build_state_bundle(list(reversed(cases)))
    assert first == second
    payload = json.loads(first)
    assert payload["generation"] == 5 and payload["split"] == "harbor_state"
    ids = [c["eval_id"] for c in payload["eval_cases"]]
    assert ids == sorted(ids) and len(ids) == 50


def test_default_tree_has_100_tasks_two_arms_two_splits(generated) -> None:
    summary = generated["summary"]
    assert summary["arms"] == list(gen.DEFAULT_GEN5_ARMS) == ["clean_skills", "gepa_evolved_skills"]
    assert summary["splits"] == list(gen.GEN5_HARBOR_SPLITS) == ["validation", "final_test"]
    assert summary["cases_per_split"] == {"validation": 20, "final_test": 30}
    assert summary["total_tasks"] == 100
    assert len(_task_dirs(generated["out"])) == 100
    for arm in gen.DEFAULT_GEN5_ARMS:
        for split in gen.GEN5_HARBOR_SPLITS:
            assert (generated["out"] / arm / split).is_dir()


def test_every_task_has_the_gen5_layout_and_one_environment_hash(generated) -> None:
    hashes = set()
    for task_dir in _task_dirs(generated["out"]):
        for rel in (
            "task.toml", "instruction.md", "solution/solve.sh", "tests/test.sh", "tests/case.json",
            "tests/manifest.json", "environment/Dockerfile", "environment/state_bundle.json",
            "environment/soc_environment.py", "environment/soc_sandbox_cli.py",
            "environment/verify_harbor_soc.py", "environment/eval_trajectory_verifier.py",
            "environment/eval_cost_engine.py", "environment/jev_judge.py", "environment/jev_evaluator.py",
        ):
            assert (task_dir / rel).exists(), f"{task_dir.name}: {rel}"
        assert not (task_dir / "environment" / "soc_tier1_interactive.json").exists()
        assert os.access(task_dir / "solution" / "solve.sh", os.X_OK)
        assert os.access(task_dir / "tests" / "test.sh", os.X_OK)
        hashes.add(gen.compute_environment_hash(task_dir / "environment"))
    assert len(hashes) == 1
    assert generated["summary"]["environment_hash"] in hashes


def test_tree_manifest_records_provenance_without_timestamps(generated) -> None:
    tree = json.loads((generated["out"] / "manifest.json").read_text(encoding="utf-8"))
    assert tree["generator_version"] == gen.GEN5_GENERATOR_VERSION
    assert tree["environment_hash"] == generated["summary"]["environment_hash"]
    assert tree["gen5_manifest_sha256"] == sha256_text((GEN5 / "manifest.json").read_text(encoding="utf-8"))
    assert tree["arms"] == list(gen.DEFAULT_GEN5_ARMS) and tree["splits"] == list(gen.GEN5_HARBOR_SPLITS)
    assert len(tree["tasks"]) == 100
    assert not any(key in tree for key in ("generated_at", "timestamp", "git_sha"))
    paths = [row["path"] for row in tree["tasks"]]
    assert paths == sorted(paths)
    for row in tree["tasks"]:
        assert set(row) == {"path", "arm", "split", "eval_id", "family_id", "difficulty", "case_sha256"}
        assert (generated["out"] / row["path"] / "task.toml").exists()


def test_task_toml_carries_split_family_difficulty_and_case_sha(generated) -> None:
    gen5_manifest = json.loads((GEN5 / "manifest.json").read_text(encoding="utf-8"))
    by_id = {row["eval_id"]: row for row in gen5_manifest["cases"]}
    for task_dir in _task_dirs(generated["out"]):
        meta = _meta(task_dir)
        arm, split = task_dir.parent.parent.name, task_dir.parent.name
        eval_id = meta["metadata"]["eval_id"]
        row = by_id[eval_id]
        assert meta["schema_version"] == "1.3"
        assert meta["task"]["name"] == f"secops/soc-gen5-{arm}-{split}-{task_dir.name}"
        assert split in meta["task"]["categories"] and arm in meta["task"]["categories"]
        assert meta["metadata"]["skill_arm"] == arm
        assert meta["metadata"]["generation"] == 5
        assert meta["metadata"]["split"] == split == row["split"]
        assert meta["metadata"]["family_id"] == row["family_id"]
        assert meta["metadata"]["difficulty_level"] == row["difficulty"]
        assert meta["metadata"]["difficulty"] == gen.GEN5_DIFFICULTY_NAMES[row["difficulty"]]
        assert meta["metadata"]["case_sha256"] == row["case_sha256"] == sha256_text(canonical_json(_full_case(task_dir)))
        assert "ground_truth_label" not in meta["metadata"]
        for section in ("environment", "agent", "verifier", "solution"):
            assert meta[section]["env"]["SOC_CASE_ID"] == eval_id
            assert meta[section]["env"]["SOC_SKILL_ARM"] == arm
            assert "SOC_EVALSET_FILE" not in meta[section]["env"]
        assert meta["verifier"]["env"]["SOC_SPLIT"] == split
        assert meta["verifier"]["env"]["SOC_JEV_BACKEND"] == "mock"


def test_state_bundle_in_the_image_carries_no_answer_key(generated) -> None:
    task_dir = _task_dirs(generated["out"])[0]
    bundle = json.loads((task_dir / "environment" / "state_bundle.json").read_text(encoding="utf-8"))
    ids = [c["eval_id"] for c in bundle["eval_cases"]]
    assert len(ids) == 50 and len(set(ids)) == 50
    for case in bundle["eval_cases"]:
        assert set(case) <= set(gen.GEN5_STATE_KEYS)
        assert "environment_state" in case and "prompt" in case
        for key in ANSWER_KEYS:
            assert key not in case, (case["eval_id"], key)


def test_tests_dir_holds_the_full_case_and_the_gen5_manifest(generated) -> None:
    manifest_text = (GEN5 / "manifest.json").read_text(encoding="utf-8")
    for task_dir in _task_dirs(generated["out"]):
        case_bundle = json.loads((task_dir / "tests" / "case.json").read_text(encoding="utf-8"))
        assert case_bundle["generation"] == 5 and len(case_bundle["eval_cases"]) == 1
        case = case_bundle["eval_cases"][0]
        assert case["eval_id"] == _meta(task_dir)["metadata"]["eval_id"]
        assert case_bundle["split"] == task_dir.parent.name
        assert "oracle" in case and "expected_actions" in case and "ground_truth_label" in case
        assert (task_dir / "tests" / "manifest.json").read_text(encoding="utf-8") == manifest_text


def test_instruction_md_shows_the_prompt_and_the_arm_but_not_the_family(generated) -> None:
    for task_dir in _task_dirs(generated["out"]):
        case = _full_case(task_dir)
        text = (task_dir / "instruction.md").read_text(encoding="utf-8")
        assert case["prompt"] in text
        assert f"`{case['eval_id']}`" in text
        assert case["family_id"] not in text
        assert "**Scenario:**" not in text
        assert "recommended_actions" in text and "soc_decision.json" in text
        arm = task_dir.parent.parent.name
        if arm == "clean_skills":
            assert "## Active Operational Skill (`secops-triage`)" in text
            assert "GEPA Evolved Runbook" not in text
        if arm == "gepa_evolved_skills":
            for name in gen.GEN5_EVOLVED_RUNBOOKS:
                assert f"### Runbook: {name}" in text


def test_solve_sh_is_rendered_from_the_oracle_block(generated) -> None:
    from scripts.gen5_reference_policies import plan_oracle

    for task_dir in _one_per_family(_task_dirs(generated["out"])):
        case = _full_case(task_dir)
        trial = plan_oracle(case)
        script = (task_dir / "solution" / "solve.sh").read_text(encoding="utf-8")
        assert script.startswith("#!/usr/bin/env bash\nset -euo pipefail\n")
        assert "$SOC_CLI reset" in script
        for step in trial.steps:
            assert f"$SOC_CLI {step['tool']} --json " in script
        assert trial.report_text.strip() in script
        decision = json.loads(script.split('soc_decision.json"\n', 1)[1].split("\nEOF_DECISION", 1)[0])
        assert decision["verdict"] == case["ground_truth_label"]
        assert decision["recommended_actions"] == trial.decision["recommended_actions"]
        assert decision["case_id"] == case["eval_id"]
```

Append the container round trip and the `--check` tests to the same file:

```python
def _run_oracle_then_verifier(task_dir: Path, trial_root: Path) -> dict:
    """Runs solve.sh then test.sh the way Harbor would, with soc-cli reading only the stripped bundle."""
    meta = _meta(task_dir)
    artifacts = trial_root / "logs" / "artifacts"
    verifier = trial_root / "logs" / "verifier"
    artifacts.mkdir(parents=True)
    verifier.mkdir(parents=True)
    run_env = dict(os.environ)
    run_env.update(meta["solution"]["env"])
    run_env.update(meta["verifier"]["env"])
    run_env.update({
        "SOC_STATE_FILE": str(trial_root / "state.json"),
        "SOC_TRAJECTORY_FILE": str(artifacts / "trajectory.jsonl"),
        "SOC_ARTIFACTS_DIR": str(artifacts),
        "SOC_VERIFIER_DIR": str(verifier),
        # In the container soc-cli finds /app/configs/evals/gen5/state_bundle.json through
        # DEFAULT_EVALSET_PATHS. Locally that path does not exist, so point the CLI at the
        # task's own stripped bundle: the oracle must succeed without the answer key.
        "SOC_EVALSET_FILE": str(task_dir / "environment" / "state_bundle.json"),
        "SOC_CLI_BIN": f"{sys.executable} {ROOT_DIR / 'scripts' / 'soc_sandbox_cli.py'}",
        "SOC_VERIFY_BIN": f"{sys.executable} {ROOT_DIR / 'scripts' / 'verify_harbor_soc.py'}",
    })
    solve = subprocess.run(["bash", str(task_dir / "solution" / "solve.sh")], env=run_env, capture_output=True, text=True, check=False)
    assert solve.returncode == 0, f"solve.sh failed for {task_dir.name}: {solve.stderr}"
    test = subprocess.run(["bash", str(task_dir / "tests" / "test.sh")], env=run_env, capture_output=True, text=True, check=False)
    assert test.returncode == 0, f"test.sh failed for {task_dir.name}: {test.stderr}"
    scorecard = json.loads((verifier / "scorecard.json").read_text(encoding="utf-8"))
    scorecard["_reward_txt"] = float((verifier / "reward.txt").read_text(encoding="utf-8").strip())
    return scorecard


def test_oracle_scores_through_the_container_scripts_on_one_task_per_family(generated, tmp_path) -> None:
    clean = [d for d in _task_dirs(generated["out"]) if d.parent.parent.name == "clean_skills"]
    picked = _one_per_family(clean)
    assert len(picked) == 16
    for idx, task_dir in enumerate(picked):
        scorecard = _run_oracle_then_verifier(task_dir, tmp_path / f"trial_{idx:02d}")
        assert scorecard["_reward_txt"] >= 0.95, (task_dir.name, scorecard["_reward_txt"])
        assert scorecard["reward"] == scorecard["_reward_txt"]
        assert scorecard["generation"] == 5
        assert scorecard["split"] == task_dir.parent.name
        assert scorecard["manifest_case_sha256_matches"] is True
        assert scorecard["inert"] is False and scorecard["safety_gate_triggered"] is False
        assert scorecard["prohibited_entity_violations"] == []


def test_check_passes_on_a_fresh_tree_and_reports_drift(tmp_path) -> None:
    out = tmp_path / "small"
    summary = gen.generate_harbor_soc_gen5_suite(output_root=out, arms=("clean_skills",), splits=("validation",))
    assert summary["total_tasks"] == 20
    assert gen.check_gen5_tree(output_root=out, arms=("clean_skills",), splits=("validation",)) == []

    victim = sorted(out.rglob("instruction.md"))[0]
    victim.write_text(victim.read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8")
    diffs = gen.check_gen5_tree(output_root=out, arms=("clean_skills",), splits=("validation",))
    assert diffs and any(str(victim.relative_to(out)) in line for line in diffs)

    gen.generate_harbor_soc_gen5_suite(output_root=out, arms=("clean_skills",), splits=("validation",))
    extra = out / "clean_skills" / "validation" / "stray.txt"
    extra.write_text("x", encoding="utf-8")
    diffs = gen.check_gen5_tree(output_root=out, arms=("clean_skills",), splits=("validation",))
    assert any("stray.txt" in line and "unexpected" in line for line in diffs)

    extra.unlink()
    missing = sorted(out.rglob("test.sh"))[0]
    missing.unlink()
    diffs = gen.check_gen5_tree(output_root=out, arms=("clean_skills",), splits=("validation",))
    assert any("test.sh" in line and "missing" in line for line in diffs)


def test_cli_check_passes_against_the_committed_tree() -> None:
    assert COMMITTED_TREE.exists(), "run: .venv/bin/python scripts/generate_harbor_soc_tasks.py"
    result = subprocess.run(
        [sys.executable, str(ROOT_DIR / "scripts" / "generate_harbor_soc_tasks.py"), "--check"],
        capture_output=True, text=True, check=False, cwd=ROOT_DIR,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    tree = json.loads((COMMITTED_TREE / "manifest.json").read_text(encoding="utf-8"))
    assert tree["total_tasks"] == 100
    assert tree["gen5_manifest_sha256"] == sha256_text((GEN5 / "manifest.json").read_text(encoding="utf-8"))


def test_cli_rejects_a_bad_split_and_keeps_gen3_behind_a_flag(tmp_path) -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT_DIR / "scripts" / "generate_harbor_soc_tasks.py"), "--split", "train", "--out", str(tmp_path / "x")],
        capture_output=True, text=True, check=False, cwd=ROOT_DIR,
    )
    assert result.returncode == 2 and "train" in result.stderr
    assert not (tmp_path / "x").exists()
    help_text = subprocess.run(
        [sys.executable, str(ROOT_DIR / "scripts" / "generate_harbor_soc_tasks.py"), "--help"],
        capture_output=True, text=True, check=False, cwd=ROOT_DIR,
    ).stdout
    assert "--gen3" in help_text and "--check" in help_text and "--split" in help_text
```

- [ ] **Step 2: Run the tests to confirm they fail**

```bash
.venv/bin/python -m pytest tests/test_harbor_soc_gen5_tasks.py -q 2>&1 | tail -5
```

Expected: `AttributeError` on `generate_harbor_soc_gen5_suite`, `GEN5_CONTAINER_STATE_BUNDLE_REL`, and friends; the committed-tree test fails on the missing directory.

- [ ] **Step 3: Constants, slug, state bundle, Dockerfile, and renderers**

In `scripts/generate_harbor_soc_tasks.py`, extend the imports:

```python
import re
import shlex
import tempfile
```

and after the `sys.path` guard add the Gen 5 imports (the generator may import these; nothing imports the generator):

```python
from scripts.gen5_instancer import canonical_json, sha256_text
from scripts.gen5_reference_policies import plan_oracle
```

After `SKILL_ARMS` (L24) add:

```python
# --- Gen 5 (spec sections 7.3 and 9.4; plan decision 9) ---

GEN5_ROOT = ROOT_DIR / "configs" / "evals" / "gen5"
GEN5_MANIFEST_PATH = GEN5_ROOT / "manifest.json"
DEFAULT_GEN5_HARBOR_OUT = ROOT_DIR / "evals" / "harbor_soc_gen5"
DEFAULT_GEN5_RUNBOOKS_DIR = ROOT_DIR / "configs" / "runbooks" / "gepa_evolved"
DEFAULT_GEN5_ARMS: Tuple[str, ...] = ("clean_skills", "gepa_evolved_skills")
GEN5_HARBOR_SPLITS: Tuple[str, ...] = ("validation", "final_test")
GEN5_GENERATOR_VERSION = "harbor-soc-gen5-1"
GEN5_CONTAINER_STATE_BUNDLE_REL = "configs/evals/gen5/state_bundle.json"
# What the image may know about a case: the world and the alert, never the answer key.
GEN5_STATE_KEYS: Tuple[str, ...] = (
    "eval_id", "generation", "prompt", "asset_criticality", "cmdb_context",
    "environment_state", "fault_injection",
)
# Mirrors CORE_RUNBOOKS in agent/gepa_runbook_optimizer.py; duplicated so the generator
# does not import the optimizer (and its model clients). A test asserts equality.
GEN5_EVOLVED_RUNBOOKS: Tuple[str, ...] = (
    "basic_ioc_enrichment.md",
    "suspicious_login_triage.md",
    "malware_triage.md",
    "lateral_movement_hunt_psexec_wmi.md",
)
GEN5_DIFFICULTY_NAMES = {1: "easy", 2: "medium", 3: "hard"}
GEN5_TASK_FILES: Tuple[str, ...] = (
    "task.toml", "instruction.md", "solution/solve.sh", "tests/test.sh", "tests/case.json", "tests/manifest.json",
)

GEN5_DOCKERFILE_CONTENT = """FROM python:3.11-slim

WORKDIR /app

COPY soc_environment.py /app/agent/soc_environment.py
COPY j_init.py /app/agent/__init__.py
COPY jev_judge.py /app/agent/jev_judge.py
COPY jev_evaluator.py /app/agent/jev_evaluator.py
COPY j_init.py /app/scripts/__init__.py
COPY eval_trajectory_verifier.py /app/scripts/eval_trajectory_verifier.py
COPY eval_cost_engine.py /app/scripts/eval_cost_engine.py
COPY soc_sandbox_cli.py /app/scripts/soc_sandbox_cli.py
COPY verify_harbor_soc.py /app/scripts/verify_harbor_soc.py
COPY state_bundle.json /app/configs/evals/gen5/state_bundle.json

RUN mkdir -p /var/lib/soc /logs/artifacts /logs/verifier && \\
    ln -sf /app/scripts/soc_sandbox_cli.py /usr/local/bin/soc-cli && \\
    chmod +x /app/scripts/soc_sandbox_cli.py /app/scripts/verify_harbor_soc.py /usr/local/bin/soc-cli
"""
```

(Two backslashes in the module source render as one in the Dockerfile, exactly as the existing `DOCKERFILE_CONTENT` does for its line continuations.) Replace `_case_slug` (L225-227) with the generalized form, which leaves Gen 3 slugs unchanged:

```python
def _case_slug(eval_id: str) -> str:
    """CASE-GEN3-01-LOKIBOT-C2 -> case-01-lokibot-c2; CASE-GEN5-C2-INFOSTEALER-01 -> case-c2-infostealer-01."""
    return re.sub(r"^case-gen\d+-", "case-", eval_id.lower())
```

After `_populate_identical_environment` add the Gen 5 data helpers:

```python
def load_gen5_split(root: Path, split: str) -> List[Dict[str, Any]]:
    """Reads one committed Gen 5 bundle; never touches the exposure ledger."""
    data = json.loads((Path(root) / f"{split}.json").read_text(encoding="utf-8"))
    return [dict(case) for case in data.get("eval_cases", [])]


def strip_case_for_state(case: Dict[str, Any]) -> Dict[str, Any]:
    """The image-side view of a case: enough for SocEnvironment.from_eval_case and the prompt."""
    stripped = {key: case[key] for key in GEN5_STATE_KEYS if key in case}
    stripped["generation"] = int(case.get("generation") or 5)
    return stripped


def build_state_bundle(cases: List[Dict[str, Any]]) -> str:
    """One deterministic bundle for every task, so the environment hash is identical across the tree."""
    ordered = sorted((strip_case_for_state(case) for case in cases), key=lambda c: c["eval_id"])
    bundle = {
        "evalset_id": "soc_tier1_families",
        "generation": 5,
        "split": "harbor_state",
        "description": "Gen 5 world state for the Harbor sandbox. Answer keys live in each task's tests/case.json.",
        "eval_cases": ordered,
    }
    return json.dumps(bundle, indent=2, sort_keys=True) + "\n"


def _load_evolved_runbooks(rb_dir: Path) -> Dict[str, str]:
    """All four evolved runbooks, by file name. Missing files become a one-line stub, as Gen 3 did."""
    runbooks: Dict[str, str] = {}
    for name in GEN5_EVOLVED_RUNBOOKS:
        path = Path(rb_dir) / name
        if path.exists():
            runbooks[name] = path.read_text(encoding="utf-8")
        else:
            runbooks[name] = f"# Security Operations GEPA Evolved Runbook: {name}\n"
    return runbooks


def _populate_gen5_environment(env_dir: Path, state_bundle_text: str) -> None:
    """The Gen 3 runtime modules plus the stripped state bundle; no evalset in the image."""
    env_dir.mkdir(parents=True, exist_ok=True)
    (env_dir / "Dockerfile").write_text(GEN5_DOCKERFILE_CONTENT, encoding="utf-8")
    (env_dir / "j_init.py").write_text('"""Package init."""\n', encoding="utf-8")
    file_map = {
        "soc_environment.py": ROOT_DIR / "agent" / "soc_environment.py",
        "jev_judge.py": ROOT_DIR / "agent" / "jev_judge.py",
        "jev_evaluator.py": ROOT_DIR / "agent" / "jev_evaluator.py",
        "eval_trajectory_verifier.py": ROOT_DIR / "scripts" / "eval_trajectory_verifier.py",
        "eval_cost_engine.py": ROOT_DIR / "scripts" / "eval_cost_engine.py",
        "soc_sandbox_cli.py": ROOT_DIR / "scripts" / "soc_sandbox_cli.py",
        "verify_harbor_soc.py": ROOT_DIR / "scripts" / "verify_harbor_soc.py",
    }
    for dest_name, src_path in file_map.items():
        shutil.copyfile(src_path, env_dir / dest_name)
    (env_dir / "state_bundle.json").write_text(state_bundle_text, encoding="utf-8")
```

Then the four renderers. The CLI usage block is the Gen 3 one, copied into a Gen 5 constant rather than factored out of `_build_instruction_md`, so the frozen Gen 3 function is not touched:

```python
GEN5_SOC_CLI_USAGE_MD = """## Sandbox Environment CLI (`soc-cli`)

Use `/usr/local/bin/soc-cli` to query telemetry and execute state-changing containment or case actions. Every command updates `/var/lib/soc/state.json` and logs to `/logs/artifacts/trajectory.jsonl`:

### Epistemic Investigation Tools (Read-Only)
- `soc-cli get_ip_report --ip <IP_ADDRESS>`
- `soc-cli get_domain_report --domain <DOMAIN>`
- `soc-cli get_file_report --file_hash <SHA256>`
- `soc-cli lookup_entity --entity_id <HOSTNAME_OR_IP>`
- `soc-cli list_cases [--query <FILTER>]`
- `soc-cli get_case --case_id <CASE_ID>`
- `soc-cli udm_search --query <QUERY>`

### Pragmatic State-Changing Actions (Interventions)
- `soc-cli isolate_host --hostname <HOSTNAME_OR_IP>`
- `soc-cli unblock_host --hostname <HOSTNAME_OR_IP>`
- `soc-cli block_indicator --indicator <DOMAIN_IP_OR_HASH>`
- `soc-cli update_case_comment --case_id <CASE_ID> --comment "<NOTES>"`
- `soc-cli close_case --case_id <CASE_ID> --verdict "<VERDICT>"`
"""


def _build_gen5_task_toml(case: Dict[str, Any], arm: str, split: str, slug: str, case_sha256: str) -> str:
    """Harbor 1.3 task.toml for a Gen 5 case: harness-side metadata, no label, no answer key."""
    eval_id = case["eval_id"]
    family_id = case["family_id"]
    difficulty = int(case.get("difficulty") or 2)
    difficulty_name = GEN5_DIFFICULTY_NAMES.get(difficulty, "medium")
    crit = case.get("asset_criticality", "STANDARD")
    env_lines = (
        f'SOC_CASE_ID = "{eval_id}"\n'
        f'SOC_SKILL_ARM = "{arm}"\n'
        'SOC_STATE_FILE = "/var/lib/soc/state.json"\n'
        'SOC_TRAJECTORY_FILE = "/logs/artifacts/trajectory.jsonl"\n'
    )
    return (
        'version = "1.0"\n'
        'schema_version = "1.3"\n\n'
        "[task]\n"
        f'name = "secops/soc-gen5-{arm}-{split}-{slug}"\n'
        f'description = "Gen 5 SOC Tier 1 interactive triage, {split} split ({arm} arm)"\n'
        f'categories = ["security", "soc-tier1", "gen5-families", "{split}", "{arm}"]\n\n'
        "[metadata]\n"
        'author_name = "Dan Dye"\n'
        'author_email = "dandye@google.com"\n'
        f'difficulty = "{difficulty_name}"\n'
        f"difficulty_level = {difficulty}\n"
        'category = "security-operations"\n'
        f'tags = ["secops", "soc-tier1", "harbor", "gen5", "{arm}", "{split}", "{eval_id}"]\n'
        f'eval_id = "{eval_id}"\n'
        "generation = 5\n"
        f'family_id = "{family_id}"\n'
        f'split = "{split}"\n'
        f'case_sha256 = "{case_sha256}"\n'
        f'skill_arm = "{arm}"\n'
        f'asset_criticality = "{crit}"\n\n'
        "[verifier]\n"
        "timeout_sec = 120.0\n\n"
        "[agent]\n"
        "timeout_sec = 300.0\n\n"
        "[environment]\n"
        'network_mode = "public"\n'
        "build_timeout_sec = 300.0\n"
        "cpus = 2\n"
        "memory_mb = 2048\n"
        "storage_mb = 4096\n"
        "allow_internet = false\n\n"
        f"[environment.env]\n{env_lines}\n"
        f"[agent.env]\n{env_lines}\n"
        f"[verifier.env]\n{env_lines}"
        f'SOC_SPLIT = "{split}"\n'
        'SOC_JEV_BACKEND = "mock"\n\n'
        f"[solution.env]\n{env_lines}"
    )


def _build_gen5_instruction_md(
    case: Dict[str, Any],
    arm: str,
    clean_skill: str,
    noisy_skill: str,
    evolved_runbooks: Dict[str, str],
) -> str:
    """instruction.md: the arm's skill text, the alert, the CLI usage, the deliverables. No scenario name."""
    skill_block = ""
    if arm == "clean_skills":
        skill_block = "## Active Operational Skill (`secops-triage`)\n\n" f"{clean_skill.strip()}\n\n---\n\n"
    elif arm == "noisy_skills":
        skill_block = "## Active Operational Skill (`secops-triage`)\n\n" f"{noisy_skill.strip()}\n\n---\n\n"
    elif arm == "gepa_evolved_skills":
        sections = "".join(
            f"### Runbook: {name}\n\n{text.strip()}\n\n" for name, text in evolved_runbooks.items()
        )
        skill_block = (
            "## Security Operations GEPA Evolved Runbooks\n\n"
            "Four runbooks follow. Pick whichever fits the alert; none is marked as the right one.\n\n"
            f"{sections}---\n\n"
        )
    return (
        "# Security Operations Center (SOC) Tier 1 Interactive Triage Task\n\n"
        f"{skill_block}## Incident Alert & Asset Context\n\n"
        f"- **Case ID:** `{case['eval_id']}`\n"
        f"- **Asset Criticality:** `{case.get('asset_criticality', 'STANDARD')}`\n\n"
        f"{case['prompt']}\n\n"
        f"{GEN5_SOC_CLI_USAGE_MD}\n"
        "## Required Deliverables\n\n"
        "1. Run at least one read-only investigation tool via `soc-cli` before any containment or closure action.\n"
        "2. Execute the state-changing action(s) the evidence supports via `soc-cli`, and avoid actions it does not.\n"
        "3. Write your final grounded investigation report to `/logs/artifacts/triage_report.md`.\n"
        "4. Write structured JSON decision metadata to `/logs/artifacts/soc_decision.json` with keys `verdict` "
        "(your threat verdict, for example `MALICIOUS` or `BENIGN`), `recommended_actions` (the `soc-cli` action "
        "names you executed or recommend), `target_entity`, and `rationale`.\n"
    )


def _build_gen5_solve_sh(case: Dict[str, Any]) -> str:
    """solution/solve.sh from the case's oracle block, through the planner the calibration uses."""
    trial = plan_oracle(case)
    cli_lines = "\n".join(
        f"$SOC_CLI {step['tool']} --json {shlex.quote(json.dumps(step['args'], sort_keys=True))}"
        for step in trial.steps
    )
    decision = {"case_id": case["eval_id"], **trial.decision}
    decision_json = json.dumps(decision, indent=2, sort_keys=True)
    return f"""#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${{SOC_CLI_BIN:-soc-cli}}"
ARTIFACTS_DIR="${{SOC_ARTIFACTS_DIR:-/logs/artifacts}}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
{cli_lines}

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
{trial.report_text.strip()}
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{decision_json}
EOF_DECISION
"""


def _build_gen5_test_sh() -> str:
    """tests/test.sh: the verifier reads the answer key and the manifest from its own directory."""
    return """#!/usr/bin/env bash
set -euo pipefail

TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERIFY_BIN="${SOC_VERIFY_BIN:-python3 /app/scripts/verify_harbor_soc.py}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
VERIFIER_DIR="${SOC_VERIFIER_DIR:-/logs/verifier}"
mkdir -p "$VERIFIER_DIR"

$VERIFY_BIN \\
  --case-id "${SOC_CASE_ID}" \\
  --state-file "${SOC_STATE_FILE:-/var/lib/soc/state.json}" \\
  --trajectory-file "${SOC_TRAJECTORY_FILE:-$ARTIFACTS_DIR/trajectory.jsonl}" \\
  --report-file "$ARTIFACTS_DIR/triage_report.md" \\
  --decision-file "$ARTIFACTS_DIR/soc_decision.json" \\
  --metrics-file "$ARTIFACTS_DIR/metrics.json" \\
  --evalset-file "$TESTS_DIR/case.json" \\
  --manifest-file "$TESTS_DIR/manifest.json" \\
  --split "${SOC_SPLIT:?SOC_SPLIT must be set by task.toml [verifier.env]}" \\
  --reward-dir "$VERIFIER_DIR"
"""
```

`shlex.quote` wraps each argument JSON in single quotes, so comments containing `$`, double quotes, or apostrophes survive bash unchanged; this replaces the Gen 3 hand-escaping of `$`. `_read_metrics` in the verifier returns `{}` for a missing metrics file, so passing `--metrics-file` for a file the agent never writes is harmless. The two backslashes at line ends are Python source escapes that render as one backslash in `test.sh`, the same as `_build_test_sh`.

- [ ] **Step 4: Tree writer, `--check`, and the CLI**

After the renderers add:

```python
def write_gen5_tree(
    output_root: Path,
    evalset_root: Path = GEN5_ROOT,
    splits: Tuple[str, ...] = GEN5_HARBOR_SPLITS,
    arms: Tuple[str, ...] = DEFAULT_GEN5_ARMS,
    gepa_runbooks_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Writes the Gen 5 task tree into output_root (which must not exist yet) and returns its summary."""
    output_root = Path(output_root)
    evalset_root = Path(evalset_root)
    for split in splits:
        if split not in GEN5_HARBOR_SPLITS:
            raise ValueError(f"split {split!r} is not generated for Harbor (allowed: {', '.join(GEN5_HARBOR_SPLITS)})")
    for arm in arms:
        if arm not in SKILL_ARMS:
            raise ValueError(f"unknown arm {arm!r} (allowed: {', '.join(SKILL_ARMS)})")

    manifest_text = (evalset_root / "manifest.json").read_text(encoding="utf-8")
    manifest = json.loads(manifest_text)
    manifest_rows = {row["eval_id"]: row for row in manifest.get("cases", [])}
    cases_by_split = {split: load_gen5_split(evalset_root, split) for split in splits}
    state_bundle_text = build_state_bundle([case for cases in cases_by_split.values() for case in cases])
    clean_skill = CLEAN_SKILL_PATH.read_text(encoding="utf-8")
    noisy_skill = NOISY_SKILL_PATH.read_text(encoding="utf-8")
    evolved = _load_evolved_runbooks(Path(gepa_runbooks_dir) if gepa_runbooks_dir else DEFAULT_GEN5_RUNBOOKS_DIR)

    output_root.mkdir(parents=True, exist_ok=False)
    env_hashes = set()
    rows: List[Dict[str, Any]] = []
    for arm in arms:
        for split in splits:
            for case in cases_by_split[split]:
                eval_id = case["eval_id"]
                case_sha = sha256_text(canonical_json(case))
                row = manifest_rows.get(eval_id)
                if row is None or row.get("case_sha256") != case_sha:
                    raise ValueError(f"{eval_id}: bundle case does not match manifest.json; run gen5_instancer.py check")
                slug = _case_slug(eval_id)
                task_dir = output_root / arm / split / slug
                (task_dir / "solution").mkdir(parents=True)
                (task_dir / "tests").mkdir(parents=True)

                (task_dir / "task.toml").write_text(_build_gen5_task_toml(case, arm, split, slug, case_sha), encoding="utf-8")
                (task_dir / "instruction.md").write_text(
                    _build_gen5_instruction_md(case, arm, clean_skill, noisy_skill, evolved), encoding="utf-8"
                )
                solve_sh = task_dir / "solution" / "solve.sh"
                solve_sh.write_text(_build_gen5_solve_sh(case), encoding="utf-8")
                _make_executable(solve_sh)
                test_sh = task_dir / "tests" / "test.sh"
                test_sh.write_text(_build_gen5_test_sh(), encoding="utf-8")
                _make_executable(test_sh)
                case_bundle = {"evalset_id": "soc_tier1_families", "generation": 5, "split": split, "eval_cases": [case]}
                (task_dir / "tests" / "case.json").write_text(json.dumps(case_bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                (task_dir / "tests" / "manifest.json").write_text(manifest_text, encoding="utf-8")

                env_dir = task_dir / "environment"
                _populate_gen5_environment(env_dir, state_bundle_text)
                env_hashes.add(compute_environment_hash(env_dir))
                rows.append({
                    "path": task_dir.relative_to(output_root).as_posix(),
                    "arm": arm,
                    "split": split,
                    "eval_id": eval_id,
                    "family_id": case["family_id"],
                    "difficulty": int(case.get("difficulty") or 0),
                    "case_sha256": case_sha,
                })

    if len(env_hashes) != 1:
        raise RuntimeError(f"expected one environment hash across the tree, got {len(env_hashes)}")
    rows.sort(key=lambda r: r["path"])
    tree_manifest = {
        "generator_version": GEN5_GENERATOR_VERSION,
        "evalset_id": manifest.get("evalset_id"),
        "pool_version": manifest.get("pool_version"),
        "gen5_manifest_sha256": sha256_text(manifest_text),
        "environment_hash": next(iter(env_hashes)),
        "arms": list(arms),
        "splits": list(splits),
        "cases_per_split": {split: len(cases_by_split[split]) for split in splits},
        "total_tasks": len(rows),
        "tasks": rows,
    }
    (output_root / "manifest.json").write_text(json.dumps(tree_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {key: value for key, value in tree_manifest.items() if key != "tasks"}
    summary["output_root"] = str(output_root)
    return summary


def generate_harbor_soc_gen5_suite(
    output_root: Path = DEFAULT_GEN5_HARBOR_OUT,
    evalset_root: Path = GEN5_ROOT,
    splits: Tuple[str, ...] = GEN5_HARBOR_SPLITS,
    arms: Tuple[str, ...] = DEFAULT_GEN5_ARMS,
    gepa_runbooks_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Replaces output_root with a freshly generated Gen 5 tree."""
    output_root = Path(output_root)
    if output_root.exists():
        shutil.rmtree(output_root)
    return write_gen5_tree(output_root, evalset_root=evalset_root, splits=splits, arms=arms, gepa_runbooks_dir=gepa_runbooks_dir)


def _tree_files(root: Path) -> Dict[str, Path]:
    return {
        p.relative_to(root).as_posix(): p
        for p in root.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    }


def check_gen5_tree(
    output_root: Path = DEFAULT_GEN5_HARBOR_OUT,
    evalset_root: Path = GEN5_ROOT,
    splits: Tuple[str, ...] = GEN5_HARBOR_SPLITS,
    arms: Tuple[str, ...] = DEFAULT_GEN5_ARMS,
    gepa_runbooks_dir: Optional[Path] = None,
) -> List[str]:
    """Regenerates into a temporary directory and lists every byte-level difference from output_root."""
    output_root = Path(output_root)
    if not output_root.exists():
        return [f"missing: {output_root} (run the generator first)"]
    with tempfile.TemporaryDirectory(prefix="harbor_soc_gen5_check_") as tmp:
        fresh = Path(tmp) / "tree"
        write_gen5_tree(fresh, evalset_root=evalset_root, splits=splits, arms=arms, gepa_runbooks_dir=gepa_runbooks_dir)
        expected = _tree_files(fresh)
        actual = _tree_files(output_root)
        diffs: List[str] = []
        for rel in sorted(set(expected) - set(actual)):
            diffs.append(f"missing: {rel}")
        for rel in sorted(set(actual) - set(expected)):
            diffs.append(f"unexpected: {rel}")
        for rel in sorted(set(expected) & set(actual)):
            if expected[rel].read_bytes() != actual[rel].read_bytes():
                diffs.append(f"differs: {rel}")
            elif rel.endswith(".sh") and not os.access(actual[rel], os.X_OK):
                diffs.append(f"not executable: {rel}")
        return diffs
```

(`import os` joins the imports.) Replace `main` (L577-593) so Gen 5 is the default and Gen 3 sits behind `--gen3` with its old flags intact:

```python
def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point. Gen 5 by default; --gen3 renders the frozen Gen 3 tree."""
    parser = argparse.ArgumentParser(
        description="Generate Harbor v1.3 SOC Tier 1 evaluation tasks (Gen 5 by default; --gen3 for the frozen Gen 3 recipe)"
    )
    parser.add_argument("--gen3", action="store_true", help="generate the frozen Gen 3 tree (evals/harbor_soc) instead of Gen 5")
    parser.add_argument("--evalset", default=str(GEN5_ROOT), help="Gen 5 directory holding validation.json, final_test.json, manifest.json")
    parser.add_argument("--split", nargs="+", default=list(GEN5_HARBOR_SPLITS), help="Gen 5 splits to render (validation, final_test)")
    parser.add_argument("--arms", nargs="+", default=None, help="skill arms (Gen 5 default: clean_skills gepa_evolved_skills; Gen 3 default: all four)")
    parser.add_argument("--out", default=None, help="output root (Gen 5 default: evals/harbor_soc_gen5; Gen 3 default: evals/harbor_soc)")
    parser.add_argument("--gepa-runbooks-dir", default=None, help="evolved runbooks directory (Gen 5 default: configs/runbooks/gepa_evolved)")
    parser.add_argument("--check", action="store_true", help="Gen 5 only: regenerate into a temp dir, diff against --out, exit 1 on any difference")
    parser.add_argument("--output-root", default=None, help=argparse.SUPPRESS)  # Gen 3 compatibility
    parser.add_argument("--evals-json-out", default=str(DEFAULT_EVALS_JSON_OUT), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.gen3:
        summary = generate_harbor_soc_suite(
            output_root=Path(args.out or args.output_root or DEFAULT_HARBOR_OUT),
            evals_json_out=Path(args.evals_json_out),
            gepa_runbooks_dir=Path(args.gepa_runbooks_dir) if args.gepa_runbooks_dir else None,
            arms=tuple(args.arms or SKILL_ARMS),
        )
        print(json.dumps(summary, indent=2))
        return 0

    bad = [split for split in args.split if split not in GEN5_HARBOR_SPLITS]
    if bad:
        parser.error(
            f"split(s) not generated for Harbor: {', '.join(bad)} "
            f"(allowed: {', '.join(GEN5_HARBOR_SPLITS)}; train never runs in the container)"
        )
    out = Path(args.out or DEFAULT_GEN5_HARBOR_OUT)
    kwargs = dict(
        evalset_root=Path(args.evalset),
        splits=tuple(args.split),
        arms=tuple(args.arms or DEFAULT_GEN5_ARMS),
        gepa_runbooks_dir=Path(args.gepa_runbooks_dir) if args.gepa_runbooks_dir else None,
    )
    if args.check:
        diffs = check_gen5_tree(output_root=out, **kwargs)
        if diffs:
            print(f"harbor_soc_gen5 check FAILED: {len(diffs)} difference(s) under {out}")
            for line in diffs[:50]:
                print(f"  {line}")
            return 1
        print(f"harbor_soc_gen5 check OK: {out}")
        return 0
    summary = generate_harbor_soc_gen5_suite(output_root=out, **kwargs)
    print(json.dumps(summary, indent=2))
    return 0
```

Update the module docstring (L2) to `"""Generates Harbor v1.3 SOC Tier 1 tasks: Gen 5 family-instanced splits by default, the frozen Gen 3 suite behind --gen3."""`. `generate_harbor_soc_suite` and everything Gen 3 above it stay byte-for-byte as they are; `tests/test_harbor_soc_tasks.py` calls the function directly and must still pass.

- [ ] **Step 5: Generate the committed tree, then run the tests**

```bash
.venv/bin/python scripts/generate_harbor_soc_tasks.py | head -20
.venv/bin/python scripts/generate_harbor_soc_tasks.py --check
.venv/bin/python - <<'PY'
from pathlib import Path
root = Path("evals/harbor_soc_gen5")
files = [p for p in root.rglob("*") if p.is_file()]
print("tasks:", len(list(root.rglob("task.toml"))), "files:", len(files))
PY
.venv/bin/python -m pytest tests/test_harbor_soc_gen5_tasks.py tests/test_harbor_soc_tasks.py tests/test_soc_sandbox_cli.py tests/test_gen5_transport_parity.py -q 2>&1 | tail -5
```

Expected: `total_tasks: 100`, exactly one `environment_hash`, `check OK`, 100 `task.toml`, 1,601 files (100 tasks times 16 files plus the tree manifest; spec 9.4 estimated 1,400 at the Gen 3 rate of 14 files per task, before `state_bundle.json` and `tests/case.json` and `tests/manifest.json` replaced the single evalset copy), and all tests green. The oracle test runs 16 `solve.sh` plus `test.sh` pairs through subprocesses and takes roughly 20 to 40 seconds; that is the price of proving the container scripts work without the answer key. If a case scores below 0.95 through the scripts but 1.0 in `gen5_reference_policies`, the difference is in `soc-cli` argument parsing of that case's oracle args (`_parse_tool_args`), not in the generator; fix the parser and regenerate.

Confirm the answer key stays out of the image one more way, with a literal search over `environment/` for the most specific answer-bearing strings of one case:

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path
task = sorted(Path("evals/harbor_soc_gen5/clean_skills/validation").iterdir())[0]
case = json.loads((task / "tests" / "case.json").read_text())["eval_cases"][0]
blob = "".join(p.read_text(errors="replace") for p in (task / "environment").iterdir())
leaks = [s for s in case["assertions"]["must_contain"] + case["expected_actions"] if s in blob and s not in case["prompt"]]
print("leaks:", leaks)
PY
```

Expected: `leaks: []`. (Entity names that appear in the prompt are legitimately in the world state; this checks for strings the agent could only learn from the answer key.) `expected_actions` names like `isolate_host` also appear in `soc_sandbox_cli.py` as tool names, so if the list is not empty, confirm each hit is a tool name in the CLI source before treating it as a leak; a real leak would be a `must_contain` phrase.

- [ ] **Step 6: Justfile recipes**

Point the Gen 3 recipe at `--gen3` (its meaning is unchanged; the default is now Gen 5) and add the Gen 5 recipes after it:

```make
# Generate the frozen Gen 3 Harbor tree (evals/harbor_soc): 4 arms x 10 cases, plus evals.json
harbor-soc-generate:
    @.venv/bin/python3 scripts/generate_harbor_soc_tasks.py --gen3

# Verify all 40 Gen 3 Harbor SOC tasks, SHA-256 environment deduplication, and 100% oracle calibration
harbor-soc-test:
    @.venv/bin/pytest tests/test_harbor_soc_skills.py tests/test_soc_sandbox_cli.py tests/test_verify_harbor_soc.py tests/test_harbor_soc_tasks.py -v

# Generate the Gen 5 Harbor tree (evals/harbor_soc_gen5): default arms clean_skills and gepa_evolved_skills x validation and final_test (Usage: just harbor-soc-gen5-generate ["clean_skills gepa_evolved_skills"])
harbor-soc-gen5-generate ARMS="clean_skills gepa_evolved_skills":
    @.venv/bin/python scripts/generate_harbor_soc_tasks.py --arms {{ARMS}}

# Regenerate the Gen 5 Harbor tree into a temp dir and fail on any byte-level drift from the committed tree
harbor-soc-gen5-check:
    @.venv/bin/python scripts/generate_harbor_soc_tasks.py --check

# Gen 5 Harbor layout, answer-key isolation, one environment hash, container oracle, --check
harbor-soc-gen5-test:
    @.venv/bin/python -m pytest tests/test_harbor_soc_gen5_tasks.py tests/test_gen5_transport_parity.py -q
```

Extend `gen5-check` (Plan 2) so one recipe covers both lockfile checks:

```make
# Verify the committed bundles and the Harbor tree match their generators, then run the schema and suite tests
gen5-check:
    @.venv/bin/python scripts/gen5_instancer.py check
    @.venv/bin/python scripts/generate_harbor_soc_tasks.py --check
    @.venv/bin/python -m pytest tests/test_gen5_schema.py tests/test_gen5_suite.py -q
```

Add help lines in the `default` menu next to the Harbor and Gen 5 groups:

```
    @printf "  \033[1;32mjust harbor-soc-gen5-generate [arms]\033[0m  \033[2mGenerate the Gen 5 Harbor tree (validation + final_test)\033[0m\n"
    @printf "  \033[1;32mjust harbor-soc-gen5-check\033[0m           \033[2mFail on drift between the generator and evals/harbor_soc_gen5\033[0m\n"
    @printf "  \033[1;32mjust harbor-soc-gen5-test\033[0m            \033[2mGen 5 Harbor layout, isolation, and container oracle tests\033[0m\n"
```

Append to `tests/test_justfile_recipes.py`, inside `TestJustfileRecipes`:

```python
    def test_justfile_contains_gen5_harbor_recipes(self):
        """Gen 5 Harbor recipes exist, are in the help menu, and gen5-check runs the Harbor --check."""
        content = (ROOT_DIR / "Justfile").read_text(encoding="utf-8")
        for recipe in ("harbor-soc-gen5-generate", "harbor-soc-gen5-check", "harbor-soc-gen5-test"):
            self.assertIn(f"{recipe}", content, f"Recipe '{recipe}' not defined in Justfile")
            self.assertIn(f"just {recipe}", content, f"Help menu missing 'just {recipe}'")
        self.assertIn("generate_harbor_soc_tasks.py --gen3", content, "harbor-soc-generate must keep the Gen 3 tree behind --gen3")
        self.assertIn("generate_harbor_soc_tasks.py --check", content, "gen5-check must run the Harbor --check")
```

Run:

```bash
just --list 2>&1 | awk '/harbor-soc|gen5/'
just harbor-soc-gen5-check
.venv/bin/python -m pytest tests/test_justfile_recipes.py -q 2>&1 | tail -3
```

Expected: the five Harbor recipes and the Gen 5 recipes listed; `check OK`; tests green.

- [ ] **Step 7: Commit**

```bash
git add scripts/generate_harbor_soc_tasks.py tests/test_harbor_soc_gen5_tasks.py tests/test_justfile_recipes.py Justfile evals/harbor_soc_gen5
git commit -m "feat(gen5): Harbor generator Gen 5 mode; commit evals/harbor_soc_gen5 (100 tasks, one environment hash, answer key under tests/)"
```

`git add evals/harbor_soc_gen5` is an explicit directory path, which is what the policy asks for (no `.`, no `-A`). Confirm with `git status --short | awk '!/^A  evals\/harbor_soc_gen5\//' ` that nothing outside the intended files is staged.

---

### Task 7: Docs, recipes, pre-registration, the Gen 3 frozen note, the harness lock, and the owner checklist

**Files:**
- Create: `docs/evals_gen5.md`
- Create: `configs/experiments/gen5_campaign1.json`
- Modify: `configs/evals/gen3/soc_tier1_interactive.json` (the `description` string only)
- Modify: `docs/experiment_protocol.md`, `docs/index.md`, `docs/thoughts_on_evals.md`
- Modify: `Justfile` (`eval-gen5`, `gen5-noise`, `gen5-gradient`, `harness-approve`, `harness-verify`, help lines)
- Regenerate: `.eval_harness_lock.json` (once, last)
- Modify: `tests/test_gen5_exposure.py`, `tests/test_harness_lock.py`, `tests/test_justfile_recipes.py`

**Interfaces:**
- Produces: the five recipes; the pre-registration file with `acceptance.approved_by` and `approved_at` null (so `check_preregistration` rejects it and `final_test` stays sealed) and `datasets.*.sha256` pinned to the committed bundles; the re-approved lock covering `DEFAULT_PROTECTED_HARNESS_PATHS`; the docs.
- Consumes: everything from Tasks 1 to 6 and Plans 1 and 2.
- Consumed by: the owner, who runs the measurement gates from the printed checklist.

Nothing in this task calls a model. The recipes that do (`eval-gen5`, `gen5-noise`, `gen5-gradient`) are written and syntax-checked with `just --list` and `just --dry-run`, not executed.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_gen5_exposure.py`:

```python
def test_committed_preregistration_is_unapproved_and_pinned_to_the_bundles() -> None:
    """The campaign file exists before unsealing, but approval fields stay null until the owner signs."""
    path = ROOT_DIR / "configs" / "experiments" / "gen5_campaign1.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["acceptance"]["approved_by"] is None and data["acceptance"]["approved_at"] is None
    assert len(data["gen5"]["hypotheses"]) >= 2
    assert data["gen5"]["repetitions"] >= 2
    with pytest.raises(ex.FinalTestSealedError, match="not approved"):
        ex.check_preregistration(path)
    for split in ex.SPLITS:
        entry = data["datasets"][split]
        assert entry["path"] == f"configs/evals/gen5/{split}.json"
        assert entry["sha256"] == ex.sha256_file(ex.bundle_path(split)), split
    assert data["holdout_attestation"]["dataset_sha256"] == data["datasets"]["final_test"]["sha256"]
```

Append to `tests/test_harness_lock.py`:

```python
def test_committed_lock_verifies_at_head() -> None:
    """Every protected path matches .eval_harness_lock.json. After an intended change: just harness-approve."""
    result = subprocess.run(
        [sys.executable, str(ROOT_DIR / "scripts" / "harness_lock.py"), "verify"],
        capture_output=True, text=True, check=False, cwd=ROOT_DIR,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_committed_lock_covers_the_gen5_inputs() -> None:
    lock = json.loads((ROOT_DIR / ".eval_harness_lock.json").read_text(encoding="utf-8"))
    locked = set(lock["files"]) if isinstance(lock.get("files"), dict) else {entry["path"] for entry in lock["files"]}
    for rel in (
        "configs/evals/gen5/manifest.json", "configs/evals/gen5/train.json", "configs/evals/gen5/validation.json",
        "configs/evals/gen5/final_test.json", "scripts/gen5_instancer.py", "scripts/verify_harbor_soc.py",
        "configs/evals/gen3/soc_tier1_interactive.json",
    ):
        assert rel in locked, rel
    assert any(path.startswith("configs/evals/gen5/families/") for path in locked)
```

(Adjust the `locked` expression to the lock's actual shape from Task 3; the two shapes above cover a `{"files": {path: sha}}` dict and a `{"files": [{"path": ..., "sha256": ...}]}` list. Add `import json`, `import subprocess`, `import sys` if the file lacks them.) Append to `tests/test_justfile_recipes.py`, inside the class:

```python
    def test_justfile_contains_gen5_runner_and_lock_recipes(self):
        """eval-gen5, gen5-noise, gen5-gradient, harness-approve, harness-verify exist and are in the help menu."""
        content = (ROOT_DIR / "Justfile").read_text(encoding="utf-8")
        for recipe in ("eval-gen5", "gen5-noise", "gen5-gradient", "harness-approve", "harness-verify"):
            self.assertTrue(f"\n{recipe} " in content or f"\n{recipe}:" in content, f"Recipe '{recipe}' not defined in Justfile")
            self.assertIn(f"just {recipe}", content, f"Help menu missing 'just {recipe}'")
        self.assertIn("--gen 5 --split", content, "eval-gen5 must select a Gen 5 split")
        self.assertIn("--noise-only --noise-runs", content, "gen5-noise must call the optimizer in noise-only mode")
        self.assertIn("harness_lock.py approve", content)
        self.assertIn("harness_lock.py verify", content)
```

(A recipe line starts at column 0 and is followed by a space, when it has parameters, or a colon.)

Run `.venv/bin/python -m pytest tests/test_gen5_exposure.py tests/test_harness_lock.py tests/test_justfile_recipes.py -q 2>&1 | tail -5`. Expected: the four new tests fail (missing file, stale lock, missing recipes); everything else passes.

- [ ] **Step 2: The pre-registration file**

Compute the bundle hashes and write `configs/experiments/gen5_campaign1.json` from the template in one step, so the hashes cannot be mistyped:

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path
from scripts.gen5_exposure import SPLITS, bundle_path, sha256_file

template = json.loads(Path("configs/experiments/evidence_comparison.template.json").read_text(encoding="utf-8"))
data = dict(template)
data["workflow"] = "gen5_campaign1: seed versus GEPA-evolved runbooks on the Gen 5 family-instanced SOC Tier 1 suite"
data["repetitions"] = 2
data["acceptance"] = dict(template["acceptance"], max_unsafe_action_rate=0.0)
data["configurations"]["managed_baseline"] = {"model_revision": "gemini-2.5-flash", "region": "us-central1", "parameters": {"temperature": 0.0}}
data["datasets"] = {
    split: {"path": f"configs/evals/gen5/{split}.json", "sha256": sha256_file(bundle_path(split))} for split in SPLITS
}
data["holdout_attestation"] = {
    "reviewer": None,
    "evidence": "configs/evals/gen5/exposure.jsonl carries zero final_test entries at approval time (tests/test_gen5_exposure.py asserts it); final_test instances were materialized by scripts/gen5_instancer.py and never loaded by a model-facing runner.",
    "never_used_for_optimization": None,
    "dataset_sha256": data["datasets"]["final_test"]["sha256"],
}
data["gen5"] = {
    "hypotheses": [
        "H1 (in-distribution): on the 10 final_test instances of the seen families, GEPA-evolved runbooks score above the seed runbooks by more than tau_accept from noise_floor.json.",
        "H2 (out of distribution): on the 20 final_test instances of the four held-out families, the evolved-minus-seed delta is reported; the campaign claims generalization only if it also exceeds tau_accept there.",
        "H3 (attribution): the in-distribution delta minus the OOD delta is reported as the in-distribution premium; a positive premium with a null OOD delta is read as learned family structure, not improved judgment.",
    ],
    "comparison": {
        "baseline": "seed runbooks (the four CORE_RUNBOOKS from third_party/ai-runbooks)",
        "candidate": "configs/runbooks/gepa_evolved at the commit recorded in its evolution_metadata.json",
        "model": "gemini-2.5-flash",
        "in_distribution": "final_test instances whose family_id is in split_plan.json role seen (10 cases)",
        "out_of_distribution": "final_test instances whose family_id is in split_plan.json role final_test_ood (20 cases)",
        "scorer": "scripts.verify_harbor_soc.compose_soc_reward, pass at reward >= 0.80, infra failures excluded",
    },
    "repetitions": 2,
    "max_metric_calls": None,
    "thresholds": {"noise_mean_spread_max": 0.02, "headroom_frontier_seed_max": 0.95, "tau_accept": None},
    "unseal_command": "just eval-gen5 gemini-2.5-flash final_test '' 'gen5_campaign1 final comparison' -- after acceptance.approved_by and approved_at are set",
}
Path("configs/experiments/gen5_campaign1.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
print("written")
PY
.venv/bin/python -m pytest tests/test_gen5_exposure.py -q 2>&1 | tail -3
```

Expected: `written`; the exposure tests pass, including the new one. `tau_accept` and `max_metric_calls` stay null until `gen5-noise` has run (the owner fills them from `noise_floor.json` before approval). The `unseal_command` string is documentation inside the file; the actual run adds `--unseal-final-test --preregistration configs/experiments/gen5_campaign1.json`, which `eval-gen5` does not pass by design, so unsealing is always a hand-typed command.

- [ ] **Step 3: The Gen 3 frozen note**

In `configs/evals/gen3/soc_tier1_interactive.json`, change only the `description` string (L5): append to its current text

```
 FROZEN (frozen: true, 2026-10-04): this Gen 3 suite is kept for reproducing Campaigns 1 to 5 and the Gen 3 Harbor tree; it is not extended. New work uses the Gen 5 family-instanced suite under configs/evals/gen5 (docs/evals_gen5.md).
```

Keep the JSON otherwise byte-identical (2-space indent, same key order). Run:

```bash
.venv/bin/python -c "import json; d=json.load(open('configs/evals/gen3/soc_tier1_interactive.json')); print(len(d['eval_cases']), 'frozen: true' in d['description'])"
.venv/bin/python -m pytest tests/test_gen3_soc_environment_parity.py tests/test_eval_soc_agent.py tests/test_harbor_soc_tasks.py -q 2>&1 | tail -3
```

Expected: `10 True`; green. (The committed Gen 3 Harbor tree keeps its old copy of the file and is not regenerated; `just harbor-soc-generate` would now produce a different environment hash, which is fine because that tree is frozen too.)

- [ ] **Step 4: Justfile recipes**

Add after the Gen 5 recipes from Plan 2 and Task 6:

```make
# Run the Gen 5 suite on one split through the exposure ledger (Usage: just eval-gen5 [flavor] [split] [endpoint] [purpose])
eval-gen5 FLAVOR="gemini-2.5-flash" SPLIT="validation" ENDPOINT="" PURPOSE="gen5 eval run":
    @.venv/bin/python -m scripts.eval_soc_agent --flavor "{{FLAVOR}}" --gen 5 --split {{SPLIT}} --purpose "{{PURPOSE}}" --agent-mode hierarchical {{ if ENDPOINT != "" { "--endpoint " + ENDPOINT } else { "--managed-model " + FLAVOR } }} --output-report "docs/soc_eval_results/gen5_{{SPLIT}}_{{FLAVOR}}_report.md" --output-json "docs/soc_eval_results/gen5_{{SPLIT}}_{{FLAVOR}}_report.json"

# Measurement gate 1: K seed passes on the validation split, writes noise_floor.json and exits (Usage: just gen5-noise [k] [task_lm])
gen5-noise K="3" TASK_LM="gemini-2.5-flash":
    @.venv/bin/python agent/gepa_runbook_optimizer.py --noise-only --noise-runs {{K}} --task-lm "{{TASK_LM}}" --val-split validation --purpose "measurement gate 1: seed noise floor (K={{K}})" --output-dir "docs/soc_eval_results/gen5_noise_{{TASK_LM}}"

# Measurement gate 4 (report): one capability rung on validation with the seed runbooks (Usage: just gen5-gradient [flavor] [endpoint])
gen5-gradient FLAVOR="gemini-2.5-flash" ENDPOINT="":
    @.venv/bin/python -m scripts.eval_soc_agent --flavor "{{FLAVOR}}" --gen 5 --split validation --purpose "measurement gate 4: capability gradient ({{FLAVOR}})" --agent-mode hierarchical {{ if ENDPOINT != "" { "--endpoint " + ENDPOINT } else { "--managed-model " + FLAVOR } }} --output-report "docs/soc_eval_results/gen5_gradient/{{FLAVOR}}.md" --output-json "docs/soc_eval_results/gen5_gradient/{{FLAVOR}}.json"

# Re-approve the harness lock after an intended change to a protected scoring or Gen 5 input file
harness-approve:
    @.venv/bin/python scripts/harness_lock.py approve

# Verify every protected path against .eval_harness_lock.json (exit 1 on drift)
harness-verify:
    @.venv/bin/python scripts/harness_lock.py verify
```

`--agent-mode hierarchical` with `--use-runbooks` at its default (on) and `--runbooks-dir` at its default (`None`, which the hierarchical agent resolves to the seed runbooks) is the seed configuration; the evolved arm adds `--runbooks-dir configs/runbooks/gepa_evolved`. `eval-gen5` deliberately has no way to pass `--unseal-final-test`; `SPLIT=final_test` exits 2 with the seal message, which is the intended behavior for a recipe anyone can run by accident.

Help lines, in the Gen 5 group of the `default` menu:

```
    @printf "  \033[1;32mjust eval-gen5 [flavor] [split]\033[0m        \033[2mRun the Gen 5 suite on a split through the exposure ledger\033[0m\n"
    @printf "  \033[1;32mjust gen5-noise [k] [task_lm]\033[0m          \033[2mMeasurement gate 1: K-run seed noise floor on validation\033[0m\n"
    @printf "  \033[1;32mjust gen5-gradient [flavor] [endpoint]\033[0m \033[2mMeasurement gate 4: one capability rung on validation\033[0m\n"
    @printf "  \033[1;32mjust harness-approve\033[0m                   \033[2mRe-approve .eval_harness_lock.json after intended changes\033[0m\n"
    @printf "  \033[1;32mjust harness-verify\033[0m                    \033[2mVerify protected scoring and Gen 5 inputs against the lock\033[0m\n"
```

Check syntax without running anything model-facing:

```bash
just --list 2>&1 | awk '/eval-gen5|gen5-|harness-/'
just --dry-run eval-gen5 2>&1 | head -3
just --dry-run gen5-noise 2>&1 | head -3
just --dry-run eval-gen5 gemini-2.5-flash final_test 2>&1 | head -3
.venv/bin/python -m pytest tests/test_justfile_recipes.py -q 2>&1 | tail -3
```

Expected: all five recipes listed; the dry runs print the expanded commands (the `final_test` one prints a command that would exit 2 if executed); tests green.

- [ ] **Step 5: `docs/evals_gen5.md`**

Create the file with this structure and content. Keep it factual: every number quoted comes from a committed artifact (`manifest.json`, `GEN5_CALIBRATION.md`, `evals/harbor_soc_gen5/manifest.json`), and the measurement gates are described as pending, with the recipe that produces each.

```markdown
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

Build gates (spec 8.1), from the committed calibration: <copy the Oracle, Inert, Shotgun, Close-all
rows and the parity line from docs/soc_eval_results/GEN5_CALIBRATION.md verbatim>.

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
```

- [ ] **Step 6: The three doc edits**

`docs/experiment_protocol.md`, section "Dataset split and holdout protection": after the paragraph that ends `...the experiment must stop at protocol preparation.` insert:

```markdown
For the SOC Tier 1 suite these inventories now exist by construction:
`configs/evals/gen5/{train,validation,final_test}.json`, materialized from scenario
families by `scripts/gen5_instancer.py` and pinned by `configs/evals/gen5/manifest.json`
(see [`evals_gen5.md`](evals_gen5.md)). Exposure history is the append-only ledger
`configs/evals/gen5/exposure.jsonl`, written by every model-facing load; `final_test`
loads only with `--unseal-final-test --preregistration <file>` against an approved
pre-registration such as
[`configs/experiments/gen5_campaign1.json`](../configs/experiments/gen5_campaign1.json).
```

`docs/index.md`, Catalog Index table: add three rows after the `experiment_protocol.md` row:

```markdown
| [`evals_gen5.md`](evals_gen5.md) | `guide` | Gen 5 family-instanced SOC suite: build, check, calibrate, run, optimize, Harbor, gates, ledger |
| [`superpowers/specs/2026-10-04-gen5-evals-design.md`](superpowers/specs/2026-10-04-gen5-evals-design.md) | `plan` | Design spec for the Gen 5 suite: families, instancer, splits, scoring, exposure ledger, Harbor policy |
| [`soc_eval_results/GEN5_CALIBRATION.md`](soc_eval_results/GEN5_CALIBRATION.md) | `analysis` | Reference-policy calibration (Oracle, Inert, Shotgun, Close-all) in both transports, generated by `just gen5-calibrate` |
```

`docs/thoughts_on_evals.md`, section "5. Strategic Roadmap & Next Steps": append item 5:

```markdown
5. **Measure on held-out, family-instanced cases:**
   * The Gen 3 suite's 10 cases are all exposed. The Gen 5 suite ([design spec](superpowers/specs/2026-10-04-gen5-evals-design.md), [guide](evals_gen5.md)) instances 16 scenario families into train / validation / final_test splits, so a capability gradient is measured against cases no prompt or runbook was tuned on, with a K-run noise floor under every claimed delta.
```

Check the links resolve:

```bash
.venv/bin/python - <<'PY'
import re
from pathlib import Path
for doc in ("docs/evals_gen5.md", "docs/experiment_protocol.md", "docs/index.md", "docs/thoughts_on_evals.md"):
    text = Path(doc).read_text(encoding="utf-8")
    for target in re.findall(r"\]\(([^)#]+)\)", text):
        if target.startswith(("http", "mailto")):
            continue
        if not (Path(doc).parent / target).exists():
            print(doc, "->", target, "MISSING")
print("link check done")
PY
```

Expected: only `link check done` (any `MISSING` line is a path to fix; `superpowers/specs/...` resolves from `docs/`).

- [ ] **Step 7: Re-approve the harness lock, then the whole suite**

Every protected file has now reached its final bytes for this branch (the Gen 3 description in Step 3 was the last one). Approve once and verify:

```bash
.venv/bin/python scripts/harness_lock.py approve
.venv/bin/python scripts/harness_lock.py verify
.venv/bin/python - <<'PY'
import json
lock = json.load(open(".eval_harness_lock.json"))
files = lock["files"]
paths = sorted(files) if isinstance(files, dict) else sorted(e["path"] for e in files)
print(len(paths), "files locked; composite:", lock.get("composite_sha256") or lock.get("composite"))
print([p for p in paths if "gen5" in p][:6], "...")
PY
git diff --stat .eval_harness_lock.json
```

Expected: `verify` exits 0; well over 30 files locked (5 shared, 16 families, pools, schemas, split plan, 3 bundles, manifest, instancer, the Gen 3 evalset); the diff shows the lock changed. Then the full suite, which is the branch's acceptance run:

```bash
.venv/bin/python -m pytest -q 2>&1 | tail -8
just gen5-check 2>&1 | tail -3
just harbor-soc-gen5-check
.venv/bin/python -c "from scripts import gen5_exposure as ex; print('final_test exposures:', len(ex.final_test_exposures()))"
```

Expected: all tests pass (the Gen 5 Harbor oracle test is the slow one); `gen5-check` clean; `check OK`; `final_test exposures: 0`.

- [ ] **Step 8: Commit**

```bash
git add docs/evals_gen5.md configs/experiments/gen5_campaign1.json configs/evals/gen3/soc_tier1_interactive.json docs/experiment_protocol.md docs/index.md docs/thoughts_on_evals.md Justfile .eval_harness_lock.json tests/test_gen5_exposure.py tests/test_harness_lock.py tests/test_justfile_recipes.py
git commit -m "docs(gen5): evals_gen5 guide, pre-registration file, recipes for the measurement gates; freeze Gen 3; re-approve harness lock"
git log --oneline -n 12
```

- [ ] **Step 9: Print the owner checklist**

The implementation ends here. Print this checklist in the final report to the user; none of it is run by the implementing agent, because every line spends tokens or needs a human signature:

```
Gen 5 owner checklist (spec 8.1 and 8.2)
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

---

## Done criteria for Plan 3

- `scripts/gen5_exposure.py` is the only ledger writer; `run_evaluation` (Gen 5) and `gepa_runbook_optimizer.main` go through `load_split`; the committed `configs/evals/gen5/exposure.jsonl` has zero `final_test` entries and `tests/test_gen5_exposure.py` asserts it; `final_test` requires `--unseal-final-test`, a purpose, and an approved pre-registration, checked before any agent or client is built.
- `scripts/eval_soc_agent.py --gen 5 --split {train,validation}` scores every case with `compose_soc_reward`, retries infra errors `--infra-retries` times, marks survivors `infra_failure: true` and excludes them from every mean, and writes the "Gen 5 reward summary" section; Gen 3 runs are unchanged.
- `agent/gepa_runbook_optimizer.py` trains on `train`, selects on `validation`, refuses identical splits and the sealed `final_test`, rejects candidates containing manifest literals, scores inert trajectories 0 and entity violations as prohibited-action loss, writes runbooks only when a non-seed candidate wins, reports one of the three `selection_reason` values, and writes `noise_floor.json` for K >= 2 (`--noise-only` exits after it).
- `agent/hillclimb_harness.py` generalizes the noise floor to K runs with per-case standard deviation, expands protected directories, and records tokens, latency, and inertness per staircase rung; `scripts/harness_lock.py approve|verify` works over `DEFAULT_PROTECTED_HARNESS_PATHS`.
- `soc-cli` resolves `CASE-GEN5-*` ids from the Gen 5 bundles or `SOC_EVALSET_FILE`, strictly; the reference policies run through both transports and `GEN5_CALIBRATION.md` shows the parity gate passing.
- `evals/harbor_soc_gen5/` is committed: 100 tasks, one environment hash, answer key only under `tests/`, `solve.sh` from `plan_oracle`, `generate_harbor_soc_tasks.py --check` clean, the container oracle scoring >= 0.95 on one task per family through the real scripts; the Gen 3 tree is untouched and `--gen3` still renders it.
- `docs/evals_gen5.md`, the pre-registration file (unapproved, hashes pinned), the recipes (`eval-gen5`, `gen5-noise`, `gen5-gradient`, `harness-approve`, `harness-verify`, `harbor-soc-gen5-*`, extended `gen5-check`), the Gen 3 frozen note, and the catalog rows exist; `.eval_harness_lock.json` verifies at HEAD and covers the Gen 5 inputs.
- `.venv/bin/python -m pytest -q` is green from the repository root; `just gen5-check` and `just harbor-soc-gen5-check` exit 0; no measurement gate has been run by the implementing agent, and the owner checklist has been printed.

