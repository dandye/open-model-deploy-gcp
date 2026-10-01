# Disciplined Hillclimber (eval-hillclimb + Jev Judge + Harness Checksum) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade `agent/gepa_runbook_optimizer.py` into a disciplined hillclimber combining SHA-256 harness checksum locks (`--approve-harness`), Step 0 noise-floor gating, Two-Speed Jev System-One inner-loop grading + generative teacher outer-loop critique, anti-bloat/case-ID generalization guards, an append-only JSONL hillclimb ledger, and a `cost-hillclimb` model staircase walk.

**Architecture:** We introduce `agent/hillclimb_harness.py` containing `HarnessIntegrityGuard`, `NoiseFloorEstimator`, `evaluate_candidate_acceptance()`, `HillclimbLedger`, and `run_cost_staircase_walk()`. We then upgrade `agent/gepa_runbook_optimizer.py` (`validate_runbook_candidate` v2, `RunbookGEPAAdapter`, and `main`) to enforce harness checksum verification before every rollout, integrate Jev System-One (`JevSocJudgeEvaluator` from `2026-09-24-jev-eval-judge-migration.md`, with standalone fallback), gate candidate selection against the measured noise floor, and log every iteration to `hillclimb_ledger.jsonl`.

**Tech Stack:** Python 3.11+, Google GenAI SDK (`google.genai`), `gepa`, Pytest, Justfile.

**Spec:** [docs/superpowers/specs/2026-10-01-disciplined-hillclimber-design.md](file:///usr/local/google/home/dandye/Projects/gemma_deploy__worktrees/disciplined_hillclimber_v0001/docs/superpowers/specs/2026-10-01-disciplined-hillclimber-design.md)
**Prerequisite / Companion Plan:** [docs/superpowers/plans/2026-09-24-jev-eval-judge-migration.md](file:///usr/local/google/home/dandye/Projects/gemma_deploy__worktrees/disciplined_hillclimber_v0001/docs/superpowers/plans/2026-09-24-jev-eval-judge-migration.md)

## Global Constraints

- Target Worktree: `/usr/local/google/home/dandye/Projects/gemma_deploy__worktrees/disciplined_hillclimber_v0001`
- Target Branch: `disciplined_hillclimber_v0001` (never use `/` in branch names; never use `feat` prefix).
- Strictly NO EMOJIS anywhere in code, comments, docstrings, commit messages, or documentation.
- All paths must resolve relative to repository root (`ROOT_DIR`).
- Always define shell variables explicitly before expanding (e.g. `PROJECT_ID="..."`).
- NEVER run `git add .`, `git add -A`, or `git add --all`. Always stage specific files by explicit path (`git add <file1> <file2>`) after checking `git status`.
- Always shut down any dedicated Vertex AI GPU endpoints immediately after live runs (`$0.00` idle compute leak).

---

### Task 0: Prerequisite Check — Jev System-One Judge Primitives (`agent/jev_judge.py` & `agent/jev_evaluator.py`)

**Files:**
- Check/Create: `agent/jev_judge.py`, `agent/jev_evaluator.py` (from [2026-09-24-jev-eval-judge-migration.md](file:///usr/local/google/home/dandye/Projects/gemma_deploy__worktrees/disciplined_hillclimber_v0001/docs/superpowers/plans/2026-09-24-jev-eval-judge-migration.md))
- Test: `tests/test_jev_judge_primitives.py`, `tests/test_jev_evaluator.py`

**Interfaces:**
- Produces:
  - `JevSocJudgeEvaluator.evaluate_case(prompt, response, reference, rubric, trajectory) -> JevEvaluationOutput`
  - `MockJevBackend`, `GeminiSystem1Backend`

- [ ] **Step 1: Check whether Task 1–4 of `2026-09-24-jev-eval-judge-migration.md` have been executed**

Run:
```bash
WORKTREE_DIR="/usr/local/google/home/dandye/Projects/gemma_deploy__worktrees/disciplined_hillclimber_v0001"
test -f "${WORKTREE_DIR}/agent/jev_evaluator.py" && echo "Jev present" || echo "Execute Tasks 1-4 of 2026-09-24-jev-eval-judge-migration.md first"
```
If `agent/jev_evaluator.py` is not yet created, execute Tasks 1 through 4 of `docs/superpowers/plans/2026-09-24-jev-eval-judge-migration.md` first so `agent/jev_judge.py` and `agent/jev_evaluator.py` are tested and committed.

---

### Task 1: Harness Checksum Lock (`HarnessIntegrityGuard`)

**Files:**
- Create: `agent/hillclimb_harness.py`
- Create: `tests/test_hillclimb_harness.py`

**Interfaces:**
- Produces:
  - `HarnessTamperError(RuntimeError)`
  - `HarnessIntegrityGuard(root_dir: Path, lock_file: Path, protected_paths: Optional[Sequence[Path]] = None)`
  - `HarnessIntegrityGuard.compute_manifest() -> Dict[str, str]`
  - `HarnessIntegrityGuard.approve_and_save() -> Dict[str, Any]`
  - `HarnessIntegrityGuard.verify(auto_initialize: bool = True) -> Dict[str, str]`

- [ ] **Step 1: Write failing tests for `HarnessIntegrityGuard`**

Create `tests/test_hillclimb_harness.py`:
```python
"""Unit tests for disciplined hillclimber harness integrity, noise floor, ledger, and cost staircase."""

import json
from pathlib import Path
import pytest

from agent.hillclimb_harness import (
    HarnessIntegrityGuard,
    HarnessTamperError,
)


def test_harness_integrity_guard_initializes_and_verifies(tmp_path: Path):
    eval_file = tmp_path / "evalset.json"
    grader_file = tmp_path / "grader.py"
    eval_file.write_text('{"eval_cases": []}', encoding="utf-8")
    grader_file.write_text("def grade(): return 1.0\n", encoding="utf-8")

    lock_file = tmp_path / ".eval_harness_lock.json"
    guard = HarnessIntegrityGuard(
        root_dir=tmp_path,
        lock_file=lock_file,
        protected_paths=[Path("evalset.json"), Path("grader.py")],
    )

    manifest = guard.verify(auto_initialize=True)
    assert lock_file.exists()
    assert "evalset.json" in manifest
    assert "grader.py" in manifest

    # Second verify with unchanged files succeeds
    manifest_again = guard.verify(auto_initialize=False)
    assert manifest_again == manifest


def test_harness_integrity_guard_blocks_tampering_until_approved(tmp_path: Path):
    eval_file = tmp_path / "evalset.json"
    eval_file.write_text('{"eval_cases": [{"id": "CASE-01"}]}', encoding="utf-8")
    lock_file = tmp_path / ".eval_harness_lock.json"

    guard = HarnessIntegrityGuard(
        root_dir=tmp_path,
        lock_file=lock_file,
        protected_paths=[Path("evalset.json")],
    )
    guard.approve_and_save()

    # Mutate evalset mid-climb
    eval_file.write_text('{"eval_cases": []}', encoding="utf-8")

    with pytest.raises(HarnessTamperError, match="evalset.json"):
        guard.verify(auto_initialize=False)

    # Approving updates the lockfile and allows verification to pass
    guard.approve_and_save()
    verified = guard.verify(auto_initialize=False)
    assert "evalset.json" in verified
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_hillclimb_harness.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent.hillclimb_harness'`

- [ ] **Step 3: Implement `HarnessIntegrityGuard` in `agent/hillclimb_harness.py`**

Create `agent/hillclimb_harness.py`:
```python
"""Disciplined Hillclimber Harness: Checksum Lock, Noise Floor Gate, JSONL Ledger, and Cost Staircase."""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


class HarnessTamperError(RuntimeError):
    """Raised when protected evaluation harness files or datasets change without --approve-harness."""


DEFAULT_PROTECTED_HARNESS_PATHS: Tuple[str, ...] = (
    "configs/evals/gen3/soc_tier1_interactive.json",
    "agent/soc_environment.py",
    "scripts/eval_trajectory_verifier.py",
    "scripts/eval_cost_engine.py",
    "scripts/eval_soc_agent.py",
)


class HarnessIntegrityGuard:
    """Locks SHA-256 digests of evaluation datasets and grading code to prevent reward hacking."""

    def __init__(
        self,
        root_dir: Path,
        lock_file: Optional[Path] = None,
        protected_paths: Optional[Sequence[Path | str]] = None,
    ) -> None:
        self.root_dir = Path(root_dir).resolve()
        self.lock_file = (
            Path(lock_file).resolve()
            if lock_file is not None
            else (self.root_dir / ".eval_harness_lock.json")
        )
        raw_paths = (
            protected_paths
            if protected_paths is not None
            else DEFAULT_PROTECTED_HARNESS_PATHS
        )
        self.protected_paths: List[Path] = [Path(p) for p in raw_paths]

    def _resolve_rel_key(self, path: Path) -> Tuple[str, Path]:
        full_path = path if path.is_absolute() else (self.root_dir / path)
        full_path = full_path.resolve()
        try:
            rel_key = str(full_path.relative_to(self.root_dir))
        except ValueError:
            rel_key = str(full_path)
        return rel_key, full_path

    def compute_manifest(self) -> Dict[str, str]:
        """Compute SHA-256 hex digests for all protected harness files."""
        manifest: Dict[str, str] = {}
        for p in self.protected_paths:
            rel_key, full_path = self._resolve_rel_key(p)
            if not full_path.exists():
                raise HarnessTamperError(
                    f"Protected harness file is missing: {rel_key} ({full_path})"
                )
            digest = hashlib.sha256(full_path.read_bytes()).hexdigest()
            manifest[rel_key] = digest
        return manifest

    def compute_composite_sha256(self) -> str:
        """Compute a single composite SHA-256 over the sorted manifest."""
        manifest = self.compute_manifest()
        canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def approve_and_save(self) -> Dict[str, Any]:
        """Approve current harness state and write lockfile to disk."""
        manifest = self.compute_manifest()
        payload = {
            "approved_at_utc": datetime.now(timezone.utc).isoformat(),
            "composite_sha256": self.compute_composite_sha256(),
            "files": manifest,
        }
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        self.lock_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    def verify(self, auto_initialize: bool = True) -> Dict[str, str]:
        """Verify current files against lockfile; raise HarnessTamperError on mismatch."""
        if not self.lock_file.exists():
            if auto_initialize:
                saved = self.approve_and_save()
                return saved["files"]
            raise HarnessTamperError(
                f"Harness lockfile does not exist at {self.lock_file}. "
                "Run with --approve-harness to initialize."
            )

        locked_data = json.loads(self.lock_file.read_text(encoding="utf-8"))
        locked_files: Dict[str, str] = locked_data.get("files", {})
        current_files = self.compute_manifest()

        mismatches: List[str] = []
        for rel_key, curr_hash in current_files.items():
            expected_hash = locked_files.get(rel_key)
            if expected_hash != curr_hash:
                mismatches.append(
                    f"{rel_key} (expected {str(expected_hash)[:12]}, got {curr_hash[:12]})"
                )
        for rel_key in locked_files:
            if rel_key not in current_files:
                mismatches.append(f"{rel_key} (removed from protected list)")

        if mismatches:
            raise HarnessTamperError(
                "Evaluation harness integrity check failed. Modified files: "
                + ", ".join(mismatches)
                + ". Do not edit evaluation files during hillclimbing, or pass --approve-harness if intentional."
            )
        return current_files
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_hillclimb_harness.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add agent/hillclimb_harness.py tests/test_hillclimb_harness.py
git commit -m "feat(eval): add HarnessIntegrityGuard SHA-256 lock for hillclimbing"
```

---

### Task 2: Step 0 Noise Floor Estimator & Acceptance Gate (`NoiseFloorEstimator` & `HillclimbLedger`)

**Files:**
- Modify: `agent/hillclimb_harness.py`
- Modify: `tests/test_hillclimb_harness.py`

**Interfaces:**
- Produces:
  - `NoiseFloorMetrics(run1_mean: float, run2_mean: float, aggregate_noise: float, mean_case_noise: float, tau_accept: float)`
  - `AcceptanceDecision(accepted: bool, status: str, reason: str, mean_delta: float, tau_accept: float, regressed_cases: List[str])`
  - `estimate_noise_floor(scores_run1: Sequence[float], scores_run2: Sequence[float], min_delta: float = 0.015, multiplier: float = 1.5) -> NoiseFloorMetrics`
  - `evaluate_candidate_acceptance(baseline_scores: Dict[str, float], candidate_scores: Dict[str, float], tau_accept: float, pass_threshold: float = 0.80) -> AcceptanceDecision`
  - `HillclimbLedger(ledger_path: Path)` with `.append_entry(...)` and `.read_entries() -> List[Dict[str, Any]]`

- [ ] **Step 1: Write failing tests for noise floor, acceptance gating, and JSONL ledger**

Append to `tests/test_hillclimb_harness.py`:
```python
from agent.hillclimb_harness import (
    HillclimbLedger,
    estimate_noise_floor,
    evaluate_candidate_acceptance,
)


def test_estimate_noise_floor_computes_tau_accept():
    run1 = [0.80, 0.70, 0.90, 0.60]  # mean 0.75
    run2 = [0.82, 0.66, 0.90, 0.62]  # mean 0.75
    metrics = estimate_noise_floor(run1, run2, min_delta=0.015, multiplier=1.5)
    assert metrics.aggregate_noise == pytest.approx(0.0)
    assert metrics.mean_case_noise == pytest.approx(0.02)
    assert metrics.tau_accept == pytest.approx(0.015)

    # When aggregate variance is 0.04, tau_accept scales to 1.5 * 0.04 = 0.06
    run3 = [0.84, 0.74, 0.94, 0.64]  # mean 0.79
    metrics_noisy = estimate_noise_floor(run1, run3, min_delta=0.015, multiplier=1.5)
    assert metrics_noisy.aggregate_noise == pytest.approx(0.04)
    assert metrics_noisy.tau_accept == pytest.approx(0.06)


def test_evaluate_candidate_acceptance_blocks_noise_and_regressions():
    baseline = {"CASE-01": 0.85, "CASE-02": 0.90, "CASE-03": 0.50}

    # 1. Gain within noise floor -> REVERTED_NOISE
    cand_noise = {"CASE-01": 0.85, "CASE-02": 0.90, "CASE-03": 0.52}
    dec_noise = evaluate_candidate_acceptance(baseline, cand_noise, tau_accept=0.02)
    assert dec_noise.accepted is False
    assert dec_noise.status == "REVERTED_NOISE"

    # 2. High mean gain but regresses CASE-01 below pass_threshold (0.80) -> REVERTED_REGRESSION
    cand_reg = {"CASE-01": 0.60, "CASE-02": 0.95, "CASE-03": 0.95}
    dec_reg = evaluate_candidate_acceptance(baseline, cand_reg, tau_accept=0.02, pass_threshold=0.80)
    assert dec_reg.accepted is False
    assert dec_reg.status == "REVERTED_REGRESSION"
    assert "CASE-01" in dec_reg.regressed_cases

    # 3. Clean gain above noise floor with zero regressions -> KEPT
    cand_good = {"CASE-01": 0.85, "CASE-02": 0.90, "CASE-03": 0.75}
    dec_good = evaluate_candidate_acceptance(baseline, cand_good, tau_accept=0.02, pass_threshold=0.80)
    assert dec_good.accepted is True
    assert dec_good.status == "KEPT"


def test_hillclimb_ledger_appends_and_reads(tmp_path: Path):
    ledger_file = tmp_path / "hillclimb_ledger.jsonl"
    ledger = HillclimbLedger(ledger_file)
    ledger.append_entry(
        iteration=1,
        harness_sha256="abc1234",
        train_score=0.72,
        val_score=0.81,
        tau_accept=0.02,
        decision="KEPT",
        rationale="Validation score improved by +0.09 above noise floor",
        metadata={"task_lm": "gemini-2.5-flash-lite"},
    )
    entries = ledger.read_entries()
    assert len(entries) == 1
    assert entries[0]["decision"] == "KEPT"
    assert entries[0]["val_score"] == pytest.approx(0.81)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_hillclimb_harness.py -v`
Expected: FAIL with `ImportError: cannot import name 'estimate_noise_floor'`

- [ ] **Step 3: Implement `NoiseFloorMetrics`, `AcceptanceDecision`, and `HillclimbLedger` in `agent/hillclimb_harness.py`**

Append to `agent/hillclimb_harness.py`:
```python
@dataclass(frozen=True)
class NoiseFloorMetrics:
    """Step 0 baseline noise floor calibration metrics."""

    run1_mean: float
    run2_mean: float
    aggregate_noise: float
    mean_case_noise: float
    tau_accept: float


@dataclass(frozen=True)
class AcceptanceDecision:
    """Result of gating a candidate against baseline scores and noise floor."""

    accepted: bool
    status: str
    reason: str
    mean_delta: float
    tau_accept: float
    regressed_cases: List[str] = field(default_factory=list)


def estimate_noise_floor(
    scores_run1: Sequence[float],
    scores_run2: Sequence[float],
    min_delta: float = 0.015,
    multiplier: float = 1.5,
) -> NoiseFloorMetrics:
    """Compute aggregate and per-case noise floor from two baseline passes on identical code."""
    if not scores_run1 or not scores_run2 or len(scores_run1) != len(scores_run2):
        raise ValueError("scores_run1 and scores_run2 must be non-empty sequences of equal length.")

    n = len(scores_run1)
    mean1 = sum(float(x) for x in scores_run1) / n
    mean2 = sum(float(x) for x in scores_run2) / n
    agg_noise = abs(mean1 - mean2)
    case_noise = sum(abs(float(a) - float(b)) for a, b in zip(scores_run1, scores_run2)) / n
    tau_accept = max(float(min_delta), float(multiplier) * agg_noise)
    return NoiseFloorMetrics(
        run1_mean=mean1,
        run2_mean=mean2,
        aggregate_noise=agg_noise,
        mean_case_noise=case_noise,
        tau_accept=tau_accept,
    )


def evaluate_candidate_acceptance(
    baseline_scores: Dict[str, float],
    candidate_scores: Dict[str, float],
    tau_accept: float,
    pass_threshold: float = 0.80,
) -> AcceptanceDecision:
    """Gate a candidate on zero case regressions and improvement above tau_accept."""
    if not baseline_scores or not candidate_scores:
        return AcceptanceDecision(
            accepted=False,
            status="REVERTED_EMPTY",
            reason="Empty baseline or candidate score dictionary.",
            mean_delta=0.0,
            tau_accept=tau_accept,
        )

    common_keys = sorted(set(baseline_scores.keys()) & set(candidate_scores.keys()))
    if not common_keys:
        return AcceptanceDecision(
            accepted=False,
            status="REVERTED_MISMATCH",
            reason="No overlapping case IDs between baseline and candidate.",
            mean_delta=0.0,
            tau_accept=tau_accept,
        )

    regressed: List[str] = []
    for k in common_keys:
        b_val = float(baseline_scores[k])
        c_val = float(candidate_scores[k])
        if b_val >= pass_threshold and c_val < pass_threshold:
            regressed.append(k)

    base_mean = sum(float(baseline_scores[k]) for k in common_keys) / len(common_keys)
    cand_mean = sum(float(candidate_scores[k]) for k in common_keys) / len(common_keys)
    mean_delta = cand_mean - base_mean

    if regressed:
        return AcceptanceDecision(
            accepted=False,
            status="REVERTED_REGRESSION",
            reason=f"Candidate regressed previously passing cases: {', '.join(regressed)}",
            mean_delta=mean_delta,
            tau_accept=tau_accept,
            regressed_cases=regressed,
        )

    if mean_delta < tau_accept - 1e-9:
        return AcceptanceDecision(
            accepted=False,
            status="REVERTED_NOISE",
            reason=(
                f"Mean delta ({mean_delta:+.4f}) did not clear acceptance threshold "
                f"tau_accept ({tau_accept:.4f})."
            ),
            mean_delta=mean_delta,
            tau_accept=tau_accept,
        )

    return AcceptanceDecision(
        accepted=True,
        status="KEPT",
        reason=f"Candidate cleared tau_accept ({mean_delta:+.4f} >= {tau_accept:.4f}) with zero regressions.",
        mean_delta=mean_delta,
        tau_accept=tau_accept,
    )


class HillclimbLedger:
    """Append-only JSONL ledger recording every hillclimbing iteration and decision."""

    def __init__(self, ledger_path: Path) -> None:
        self.ledger_path = Path(ledger_path)

    def append_entry(
        self,
        iteration: int,
        harness_sha256: str,
        train_score: Optional[float],
        val_score: Optional[float],
        tau_accept: float,
        decision: str,
        rationale: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "iteration": iteration,
            "harness_sha256": harness_sha256,
            "train_score": train_score,
            "val_score": val_score,
            "tau_accept": tau_accept,
            "decision": decision,
            "rationale": rationale,
            "metadata": metadata or {},
        }
        with open(self.ledger_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        return record

    def read_entries(self) -> List[Dict[str, Any]]:
        if not self.ledger_path.exists():
            return []
        lines = self.ledger_path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines if line.strip()]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_hillclimb_harness.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add agent/hillclimb_harness.py tests/test_hillclimb_harness.py
git commit -m "feat(eval): add Step 0 noise floor estimator, acceptance gate, and JSONL hillclimb ledger"
```

---

### Task 3: Cost-Hillclimb Model Staircase Walk (`run_cost_staircase_walk`)

**Files:**
- Modify: `agent/hillclimb_harness.py`
- Modify: `tests/test_hillclimb_harness.py`

**Interfaces:**
- Produces:
  - `DEFAULT_COST_STAIRCASE_TIERS: Tuple[str, ...]`
  - `CostRungResult(model_tier: str, mean_score: float, min_loss_penalty: float, passed_safety: bool, within_tolerance: bool)`
  - `CostStaircaseReport(ceiling_model: str, ceiling_score: float, selected_model: str, selected_score: float, tolerance: float, rungs: List[CostRungResult])`
  - `run_cost_staircase_walk(candidate: Dict[str, str], eval_cases: List[Dict[str, Any]], evaluator_fn: Callable[[str, Dict[str, str], List[Dict[str, Any]]], Tuple[List[float], List[float]]], model_tiers: Sequence[str] = DEFAULT_COST_STAIRCASE_TIERS, tolerance: float = 0.05) -> CostStaircaseReport`

- [ ] **Step 1: Write failing test for `run_cost_staircase_walk`**

Append to `tests/test_hillclimb_harness.py`:
```python
from agent.hillclimb_harness import run_cost_staircase_walk


def test_run_cost_staircase_walk_selects_cheapest_safe_tier():
    tiers = [
        "gemini-2.5-flash",
        "gemma-4-31b-it",
        "gemma-4-e4b-it",
        "gemma-3-4b-it",
        "gemma-3-1b-it",
    ]
    # Simulated scores and loss penalties per tier:
    # gemini-2.5-flash: 0.90 (safe) -> ceiling
    # gemma-4-31b-it:   0.88 (safe, within 0.05)
    # gemma-4-e4b-it:   0.87 (safe, within 0.05) -> should be selected!
    # gemma-3-4b-it:    0.86 (unsafe: loss_penalty 0.368 < 1.0) -> rejected by safety gate
    # gemma-3-1b-it:    0.55 (safe, but below 0.90 - 0.05 = 0.85) -> rejected by tolerance
    mock_table = {
        "gemini-2.5-flash": ([0.90, 0.90], [1.0, 1.0]),
        "gemma-4-31b-it": ([0.88, 0.88], [1.0, 1.0]),
        "gemma-4-e4b-it": ([0.87, 0.87], [1.0, 1.0]),
        "gemma-3-4b-it": ([0.86, 0.86], [1.0, 0.368]),
        "gemma-3-1b-it": ([0.55, 0.55], [1.0, 1.0]),
    }

    def fake_eval(tier: str, candidate: dict, cases: list):
        return mock_table[tier]

    report = run_cost_staircase_walk(
        candidate={"basic_ioc_enrichment.md": "# Runbook"},
        eval_cases=[{"eval_id": "CASE-01"}, {"eval_id": "CASE-02"}],
        evaluator_fn=fake_eval,
        model_tiers=tiers,
        tolerance=0.05,
    )
    assert report.ceiling_model == "gemini-2.5-flash"
    assert report.ceiling_score == pytest.approx(0.90)
    assert report.selected_model == "gemma-4-e4b-it"
    assert report.selected_score == pytest.approx(0.87)
    assert len(report.rungs) == 5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_hillclimb_harness.py -v`
Expected: FAIL with `ImportError: cannot import name 'run_cost_staircase_walk'`

- [ ] **Step 3: Implement `run_cost_staircase_walk` in `agent/hillclimb_harness.py`**

Append to `agent/hillclimb_harness.py`:
```python
DEFAULT_COST_STAIRCASE_TIERS: Tuple[str, ...] = (
    "gemini-2.5-flash",
    "gemma-4-31b-it",
    "gemma-4-e4b-it",
    "gemma-3-4b-it",
    "gemma-3-1b-it",
)


@dataclass(frozen=True)
class CostRungResult:
    """Evaluation summary for a single model rung in the cost staircase."""

    model_tier: str
    mean_score: float
    min_loss_penalty: float
    passed_safety: bool
    within_tolerance: bool


@dataclass(frozen=True)
class CostStaircaseReport:
    """Report produced by walking evolved runbooks down the model cost staircase."""

    ceiling_model: str
    ceiling_score: float
    selected_model: str
    selected_score: float
    tolerance: float
    rungs: List[CostRungResult]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def run_cost_staircase_walk(
    candidate: Dict[str, str],
    eval_cases: List[Dict[str, Any]],
    evaluator_fn: Callable[[str, Dict[str, str], List[Dict[str, Any]]], Tuple[List[float], List[float]]],
    model_tiers: Sequence[str] = DEFAULT_COST_STAIRCASE_TIERS,
    tolerance: float = 0.05,
) -> CostStaircaseReport:
    """Walk down ordered model tiers (expensive -> cheap) and select the lowest-cost safe tier."""
    if not model_tiers:
        raise ValueError("model_tiers must contain at least one model tier.")

    rungs: List[CostRungResult] = []
    ceiling_model = model_tiers[0]
    ceiling_score = 0.0
    selected_model = ceiling_model
    selected_score = 0.0

    for idx, tier in enumerate(model_tiers):
        scores, loss_penalties = evaluator_fn(tier, candidate, eval_cases)
        mean_score = sum(scores) / len(scores) if scores else 0.0
        min_loss_pen = min(loss_penalties) if loss_penalties else 0.0
        passed_safety = min_loss_pen >= 0.999

        if idx == 0:
            ceiling_score = mean_score
            selected_score = mean_score

        within_tol = mean_score >= (ceiling_score - tolerance - 1e-9)
        rung = CostRungResult(
            model_tier=tier,
            mean_score=mean_score,
            min_loss_penalty=min_loss_pen,
            passed_safety=passed_safety,
            within_tolerance=within_tol,
        )
        rungs.append(rung)

        if passed_safety and within_tol:
            selected_model = tier
            selected_score = mean_score

    return CostStaircaseReport(
        ceiling_model=ceiling_model,
        ceiling_score=ceiling_score,
        selected_model=selected_model,
        selected_score=selected_score,
        tolerance=tolerance,
        rungs=rungs,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_hillclimb_harness.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add agent/hillclimb_harness.py tests/test_hillclimb_harness.py
git commit -m "feat(eval): implement cost-hillclimb model staircase walk"
```

---

### Task 4: Upgrade `agent/gepa_runbook_optimizer.py` with Anti-Bloat, Case-ID Check, Harness Guard, and Jev Inner-Loop Scorer

**Files:**
- Modify: `agent/gepa_runbook_optimizer.py`
- Modify: `tests/test_gepa_runbook_optimizer.py`

**Interfaces:**
- Updates `validate_runbook_candidate(candidate, forbidden_hostnames=None, seed_candidate=None, max_growth_ratio=1.35) -> Tuple[bool, List[str]]` to block `CASE-\d+` identifiers and runbook bloat exceeding `max_growth_ratio`.
- Updates `RunbookGEPAAdapter.__init__` to accept `harness_guard: Optional[HarnessIntegrityGuard] = None`, `jev_evaluator: Optional[Any] = None`, `seed_candidate: Optional[Dict[str, str]] = None`, and `max_growth_ratio: float = 1.35`.
- Updates `RunbookGEPAAdapter.evaluate` to call `self.harness_guard.verify()` before running rollouts, blend Jev System-One `rubric_score` + `grounding_score` when `jev_evaluator` is provided, and attach `jev_choice` diagnosis to traces for `make_reflective_dataset()`.
- Updates `build_arg_parser()` and `main()` with `--lock-file`, `--approve-harness`, `--noise-runs`, `--min-delta`, `--max-growth-ratio`, and `--cost-staircase`.

- [ ] **Step 1: Write failing tests for `validate_runbook_candidate` v2, harness guard enforcement, and Jev scoring in `tests/test_gepa_runbook_optimizer.py`**

Append to `tests/test_gepa_runbook_optimizer.py`:
```python
def test_validate_runbook_candidate_rejects_case_id_and_bloat():
    from agent.gepa_runbook_optimizer import validate_runbook_candidate

    seed = {"basic_ioc_enrichment.md": "# Title\n" + ("Standard instruction line.\n" * 10)}

    # 1. Case-ID literal leakage
    cand_case_id = {
        "basic_ioc_enrichment.md": "# Title\nIn CASE-02 and CASE-10, do not isolate the host.\n"
    }
    ok_id, violations_id = validate_runbook_candidate(cand_case_id, seed_candidate=seed)
    assert ok_id is False
    assert any("CASE-02" in v for v in violations_id)

    # 2. Bloat exceeding 1.35x seed length
    cand_bloated = {
        "basic_ioc_enrichment.md": seed["basic_ioc_enrichment.md"] * 2
    }
    ok_bloat, violations_bloat = validate_runbook_candidate(
        cand_bloated, seed_candidate=seed, max_growth_ratio=1.35
    )
    assert ok_bloat is False
    assert any("growth ratio" in v.lower() for v in violations_bloat)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_gepa_runbook_optimizer.py -k "test_validate_runbook_candidate_rejects_case_id_and_bloat" -v`
Expected: FAIL

- [ ] **Step 3: Update `agent/gepa_runbook_optimizer.py`**

1. Add `CASE_ID_REGEX = re.compile(r"\bCASE-\d{2,}\b", re.IGNORECASE)` and `seed_candidate` / `max_growth_ratio` checks inside `validate_runbook_candidate()`.
2. Import `HarnessIntegrityGuard`, `HillclimbLedger`, `estimate_noise_floor`, `evaluate_candidate_acceptance`, and `run_cost_staircase_walk` from `agent.hillclimb_harness`.
3. In `RunbookGEPAAdapter.evaluate()`, call `if self.harness_guard is not None: self.harness_guard.verify(auto_initialize=False)` and pass `seed_candidate=self.seed_candidate, max_growth_ratio=self.max_growth_ratio` to `validate_runbook_candidate()`.
4. If `self.jev_evaluator is not None`, invoke `jev_out = self.jev_evaluator.evaluate_case(...)` to compute `rubric_normalized = 0.50 * rubric_normalized + 0.30 * (jev_out.rubric_score / 100.0) + 0.20 * jev_out.grounding_score` and record `"jev_choice": jev_out.primary_choice` in each trace; include `jev_choice` in `make_reflective_dataset()` feedback.
5. In `main()`, wire `--lock-file`, `--approve-harness`, `--noise-runs`, `--min-delta`, `--max-growth-ratio`, and `--cost-staircase`, logging all iterations to `output_dir / "hillclimb_ledger.jsonl"`.

- [ ] **Step 4: Run full test suite to verify all tests pass**

Run: `.venv/bin/pytest tests/test_hillclimb_harness.py tests/test_gepa_runbook_optimizer.py -v`
Expected: PASS (100% pass rate)

- [ ] **Step 5: Commit**

```bash
git add agent/gepa_runbook_optimizer.py tests/test_gepa_runbook_optimizer.py
git commit -m "feat(gepa): upgrade GEPA runbook optimizer into disciplined hillclimber"
```
