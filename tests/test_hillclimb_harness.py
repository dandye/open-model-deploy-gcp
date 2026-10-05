"""Unit tests for disciplined hillclimber harness integrity, noise floor, ledger, and cost staircase."""

import json
from pathlib import Path
import pytest

from agent.hillclimb_harness import (
    DEFAULT_PROTECTED_HARNESS_PATHS,
    GEN5_PROTECTED_PATHS,
    HarnessIntegrityGuard,
    HarnessTamperError,
    HillclimbLedger,
    LEGACY_PROTECTED_PATHS,
    SHARED_SCORING_PATHS,
    estimate_noise_floor,
    evaluate_candidate_acceptance,
    run_cost_staircase_walk,
    write_noise_floor_json,
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

