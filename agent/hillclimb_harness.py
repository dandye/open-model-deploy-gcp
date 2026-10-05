"""Disciplined Hillclimber Harness: Checksum Lock, Noise Floor Gate, JSONL Ledger, and Cost Staircase."""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


class HarnessTamperError(RuntimeError):
  """Raised when protected evaluation harness files or datasets change without --approve-harness."""


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
            f"{rel_key} (expected {str(expected_hash)[:12]}, got"
            f" {curr_hash[:12]})"
        )
    for rel_key in locked_files:
      if rel_key not in current_files:
        mismatches.append(f"{rel_key} (removed from protected list)")

    if mismatches:
      raise HarnessTamperError(
          "Evaluation harness integrity check failed. Modified files: "
          + ", ".join(mismatches)
          + ". Do not edit evaluation files during hillclimbing, or pass"
          " --approve-harness if intentional."
      )
    return current_files


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

  base_mean = sum(float(baseline_scores[k]) for k in common_keys) / len(
      common_keys
  )
  cand_mean = sum(float(candidate_scores[k]) for k in common_keys) / len(
      common_keys
  )
  mean_delta = cand_mean - base_mean

  if regressed:
    return AcceptanceDecision(
        accepted=False,
        status="REVERTED_REGRESSION",
        reason=(
            "Candidate regressed previously passing cases:"
            f" {', '.join(regressed)}"
        ),
        mean_delta=mean_delta,
        tau_accept=tau_accept,
        regressed_cases=regressed,
    )

  if mean_delta < tau_accept - 1e-9:
    return AcceptanceDecision(
        accepted=False,
        status="REVERTED_NOISE",
        reason=(
            f"Mean delta ({mean_delta:+.4f}) did not clear acceptance threshold"
            f" tau_accept ({tau_accept:.4f})."
        ),
        mean_delta=mean_delta,
        tau_accept=tau_accept,
    )

  return AcceptanceDecision(
      accepted=True,
      status="KEPT",
      reason=(
          f"Candidate cleared tau_accept ({mean_delta:+.4f} >="
          f" {tau_accept:.4f}) with zero regressions."
      ),
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
  tokens_in: Optional[int] = None
  tokens_out: Optional[int] = None
  latency_ms: Optional[int] = None
  scored_cases: int = 0
  inert_cases: int = 0
  inert: bool = False


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
    evaluator_fn: Callable[
        [str, Dict[str, str], List[Dict[str, Any]]],
        Tuple[Any, ...],
    ],
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
