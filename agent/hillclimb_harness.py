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
  if (
      not scores_run1
      or not scores_run2
      or len(scores_run1) != len(scores_run2)
  ):
    raise ValueError(
        "scores_run1 and scores_run2 must be non-empty sequences of equal"
        " length."
    )

  n = len(scores_run1)
  mean1 = sum(float(x) for x in scores_run1) / n
  mean2 = sum(float(x) for x in scores_run2) / n
  agg_noise = abs(mean1 - mean2)
  case_noise = (
      sum(abs(float(a) - float(b)) for a, b in zip(scores_run1, scores_run2))
      / n
  )
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
        Tuple[List[float], List[float]],
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
