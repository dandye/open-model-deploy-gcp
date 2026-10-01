"""Unit tests for disciplined hillclimber harness integrity, noise floor, ledger, and cost staircase."""

import json
from pathlib import Path
import pytest

from agent.hillclimb_harness import (
    HarnessIntegrityGuard,
    HarnessTamperError,
    HillclimbLedger,
    estimate_noise_floor,
    evaluate_candidate_acceptance,
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


def test_harness_integrity_guard_blocks_tampering_until_approved(
    tmp_path: Path,
):
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


def test_estimate_noise_floor_computes_tau_accept():
  run1 = [0.80, 0.70, 0.90, 0.60]  # mean 0.75
  run2 = [0.82, 0.66, 0.90, 0.62]  # mean 0.75
  metrics = estimate_noise_floor(run1, run2, min_delta=0.015, multiplier=1.5)
  assert metrics.aggregate_noise == pytest.approx(0.0)
  assert metrics.mean_case_noise == pytest.approx(0.02)
  assert metrics.tau_accept == pytest.approx(0.015)

  # When aggregate variance is 0.04, tau_accept scales to 1.5 * 0.04 = 0.06
  run3 = [0.84, 0.74, 0.94, 0.64]  # mean 0.79
  metrics_noisy = estimate_noise_floor(
      run1, run3, min_delta=0.015, multiplier=1.5
  )
  assert metrics_noisy.aggregate_noise == pytest.approx(0.04)
  assert metrics_noisy.tau_accept == pytest.approx(0.06)


def test_evaluate_candidate_acceptance_blocks_noise_and_regressions():
  baseline = {"CASE-01": 0.85, "CASE-02": 0.90, "CASE-03": 0.50}

  # 1. Gain within noise floor -> REVERTED_NOISE
  cand_noise = {"CASE-01": 0.85, "CASE-02": 0.90, "CASE-03": 0.52}
  dec_noise = evaluate_candidate_acceptance(
      baseline, cand_noise, tau_accept=0.02
  )
  assert dec_noise.accepted is False
  assert dec_noise.status == "REVERTED_NOISE"

  # 2. High mean gain but regresses CASE-01 below pass_threshold (0.80) -> REVERTED_REGRESSION
  cand_reg = {"CASE-01": 0.60, "CASE-02": 0.95, "CASE-03": 0.95}
  dec_reg = evaluate_candidate_acceptance(
      baseline, cand_reg, tau_accept=0.02, pass_threshold=0.80
  )
  assert dec_reg.accepted is False
  assert dec_reg.status == "REVERTED_REGRESSION"
  assert "CASE-01" in dec_reg.regressed_cases

  # 3. Clean gain above noise floor with zero regressions -> KEPT
  cand_good = {"CASE-01": 0.85, "CASE-02": 0.90, "CASE-03": 0.75}
  dec_good = evaluate_candidate_acceptance(
      baseline, cand_good, tau_accept=0.02, pass_threshold=0.80
  )
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


def test_run_cost_staircase_walk_selects_cheapest_safe_tier():
  from agent.hillclimb_harness import run_cost_staircase_walk

  tiers = [
      "gemini-2.5-flash",
      "gemma-4-31b-it",
      "gemma-4-e4b-it",
      "gemma-3-4b-it",
      "gemma-3-1b-it",
  ]
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
