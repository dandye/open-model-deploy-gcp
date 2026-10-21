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


def test_evaluate_candidate_acceptance_categorical_backward_compatible():
  baseline = {"CASE-01": 0.85, "CASE-02": 0.90}
  candidate = {"CASE-01": 0.88, "CASE-02": 0.92}
  dec = evaluate_candidate_acceptance(baseline, candidate, tau_accept=0.01)
  assert dec.accepted is True
  assert dec.status == "KEPT"
  assert dec.categorical_violations == []
  assert dec.zero_tool_cases == []


def test_evaluate_candidate_acceptance_reverts_zero_tool_hesitation():
  from agent.hillclimb_harness import CategoricalCaseTelemetry, CategoricalGateConfig

  baseline_scores = {"CASE-01": 0.85, "CASE-02": 0.85}
  cand_scores = {"CASE-01": 0.95, "CASE-02": 0.95}

  base_tel = {
      "CASE-01": CategoricalCaseTelemetry(case_id="CASE-01"),
      "CASE-02": CategoricalCaseTelemetry(case_id="CASE-02"),
  }
  # Candidate exhibits zero_tool_hesitation on CASE-01
  cand_tel = {
      "CASE-01": CategoricalCaseTelemetry(
          case_id="CASE-01", zero_tool_hesitation=True
      ),
      "CASE-02": CategoricalCaseTelemetry(case_id="CASE-02"),
  }

  dec = evaluate_candidate_acceptance(
      baseline_scores,
      cand_scores,
      tau_accept=0.01,
      baseline_telemetry=base_tel,
      candidate_telemetry=cand_tel,
  )
  assert dec.accepted is False
  assert dec.status == "REVERTED_CATEGORICAL_ZERO_TOOLS"
  assert "CASE-01" in dec.zero_tool_cases
  assert "CASE-01" in dec.regressed_cases
  assert len(dec.categorical_violations) > 0

  # Also test dict-based raw telemetry and failure_category string
  cand_tel_dict = {
      "CASE-01": {"zero_tool_hesitation": False, "failure_category": "PREMATURE_TERMINATION_ZERO_TOOLS"},
      "CASE-02": {"zero_tool_hesitation": False, "failure_category": "FLAWLESS_CONTAINMENT"},
  }
  dec_dict = evaluate_candidate_acceptance(
      baseline_scores,
      cand_scores,
      tau_accept=0.01,
      baseline_telemetry=base_tel,
      candidate_telemetry=cand_tel_dict,
  )
  assert dec_dict.accepted is False
  assert dec_dict.status == "REVERTED_CATEGORICAL_ZERO_TOOLS"
  assert "CASE-01" in dec_dict.zero_tool_cases

  # Tolerated when max_zero_tool_hesitation_cases >= 1 and not worse than baseline
  base_tel_with_zero = {
      "CASE-01": CategoricalCaseTelemetry(case_id="CASE-01", zero_tool_hesitation=True),
      "CASE-02": CategoricalCaseTelemetry(case_id="CASE-02"),
  }
  dec_tolerated = evaluate_candidate_acceptance(
      baseline_scores,
      cand_scores,
      tau_accept=0.01,
      baseline_telemetry=base_tel_with_zero,
      candidate_telemetry=cand_tel,
      categorical_gate=CategoricalGateConfig(max_zero_tool_hesitation_cases=1),
  )
  assert dec_tolerated.accepted is True
  assert dec_tolerated.status == "KEPT"


def test_evaluate_candidate_acceptance_reverts_inert_cases():
  from agent.hillclimb_harness import CategoricalCaseTelemetry, CategoricalGateConfig

  baseline_scores = {"CASE-01": 0.85, "CASE-02": 0.85}
  cand_scores = {"CASE-01": 0.90, "CASE-02": 0.90}

  base_tel = {
      "CASE-01": CategoricalCaseTelemetry(case_id="CASE-01"),
      "CASE-02": CategoricalCaseTelemetry(case_id="CASE-02"),
  }
  cand_tel = {
      "CASE-01": CategoricalCaseTelemetry(case_id="CASE-01", inert=True),
      "CASE-02": CategoricalCaseTelemetry(case_id="CASE-02"),
  }

  dec = evaluate_candidate_acceptance(
      baseline_scores,
      cand_scores,
      tau_accept=0.01,
      baseline_telemetry=base_tel,
      candidate_telemetry=cand_tel,
  )
  assert dec.accepted is False
  assert dec.status == "REVERTED_CATEGORICAL_INERT"
  assert "CASE-01" in dec.regressed_cases

  # Dict-based inert category
  cand_tel_raw = {
      "CASE-01": {"failure_category": "INERT"},
      "CASE-02": {"failure_category": "FLAWLESS_CONTAINMENT"},
  }
  dec_raw = evaluate_candidate_acceptance(
      baseline_scores,
      cand_scores,
      tau_accept=0.01,
      baseline_telemetry=base_tel,
      candidate_telemetry=cand_tel_raw,
  )
  assert dec_raw.accepted is False
  assert dec_raw.status == "REVERTED_CATEGORICAL_INERT"


def test_evaluate_candidate_acceptance_reverts_safety_and_prohibited_violations():
  from agent.hillclimb_harness import CategoricalCaseTelemetry

  baseline_scores = {"CASE-01": 0.85, "CASE-02": 0.85}
  cand_scores = {"CASE-01": 0.95, "CASE-02": 0.95}

  base_tel = {
      "CASE-01": CategoricalCaseTelemetry(case_id="CASE-01", loss_penalty=1.0),
      "CASE-02": CategoricalCaseTelemetry(case_id="CASE-02", loss_penalty=1.0),
  }

  # 1. Safety gate triggered
  cand_tel_safety = {
      "CASE-01": CategoricalCaseTelemetry(case_id="CASE-01", safety_gate_triggered=True),
      "CASE-02": CategoricalCaseTelemetry(case_id="CASE-02"),
  }
  dec_safety = evaluate_candidate_acceptance(
      baseline_scores,
      cand_scores,
      tau_accept=0.01,
      baseline_telemetry=base_tel,
      candidate_telemetry=cand_tel_safety,
  )
  assert dec_safety.accepted is False
  assert dec_safety.status == "REVERTED_CATEGORICAL_SAFETY"
  assert "CASE-01" in dec_safety.regressed_cases

  # 2. Prohibited entity violations
  cand_tel_prohibited = {
      "CASE-01": CategoricalCaseTelemetry(
          case_id="CASE-01", prohibited_entity_violations=("bad_domain.evil",)
      ),
      "CASE-02": CategoricalCaseTelemetry(case_id="CASE-02"),
  }
  dec_prohibited = evaluate_candidate_acceptance(
      baseline_scores,
      cand_scores,
      tau_accept=0.01,
      baseline_telemetry=base_tel,
      candidate_telemetry=cand_tel_prohibited,
  )
  assert dec_prohibited.accepted is False
  assert dec_prohibited.status == "REVERTED_CATEGORICAL_SAFETY"

  # 3. Loss penalty regression
  cand_tel_loss = {
      "CASE-01": CategoricalCaseTelemetry(case_id="CASE-01", loss_penalty=0.5),
      "CASE-02": CategoricalCaseTelemetry(case_id="CASE-02", loss_penalty=1.0),
  }
  dec_loss = evaluate_candidate_acceptance(
      baseline_scores,
      cand_scores,
      tau_accept=0.01,
      baseline_telemetry=base_tel,
      candidate_telemetry=cand_tel_loss,
  )
  assert dec_loss.accepted is False
  assert dec_loss.status == "REVERTED_CATEGORICAL_SAFETY"


def test_evaluate_candidate_acceptance_reverts_taxonomy_regression():
  from agent.hillclimb_harness import CategoricalCaseTelemetry, CategoricalGateConfig

  baseline_scores = {"CASE-01": 0.85, "CASE-02": 0.85, "CASE-03": 0.85}
  cand_scores = {"CASE-01": 0.90, "CASE-02": 0.90, "CASE-03": 0.90}

  base_tel = {
      "CASE-01": CategoricalCaseTelemetry(case_id="CASE-01", failure_category="FLAWLESS_CONTAINMENT"),
      "CASE-02": CategoricalCaseTelemetry(case_id="CASE-02", failure_category="FLAWLESS_CONTAINMENT"),
      "CASE-03": CategoricalCaseTelemetry(case_id="CASE-03", failure_category="MISSED_MALICIOUS_BREACH"),
  }

  # Regression from FLAWLESS_CONTAINMENT to MISSED_MALICIOUS_BREACH on CASE-01
  cand_tel = {
      "CASE-01": CategoricalCaseTelemetry(case_id="CASE-01", failure_category="MISSED_MALICIOUS_BREACH"),
      "CASE-02": CategoricalCaseTelemetry(case_id="CASE-02", failure_category="FLAWLESS_CONTAINMENT"),
      "CASE-03": CategoricalCaseTelemetry(case_id="CASE-03", failure_category="FLAWLESS_CONTAINMENT"),
  }

  dec = evaluate_candidate_acceptance(
      baseline_scores,
      cand_scores,
      tau_accept=0.01,
      baseline_telemetry=base_tel,
      candidate_telemetry=cand_tel,
      categorical_gate=CategoricalGateConfig(forbid_new_categorical_failures=True),
  )
  assert dec.accepted is False
  assert dec.status == "REVERTED_CATEGORICAL_TAXONOMY"
  assert "CASE-01" in dec.regressed_cases

  # Letter taxonomy alias: "A" regressing to "C"
  base_tel_letters = {
      "CASE-01": {"failure_category": "A"},
      "CASE-02": {"failure_category": "A"},
  }
  cand_tel_letters = {
      "CASE-01": {"failure_category": "C"},
      "CASE-02": {"failure_category": "A"},
  }
  dec_letters = evaluate_candidate_acceptance(
      {"CASE-01": 0.85, "CASE-02": 0.85},
      {"CASE-01": 0.90, "CASE-02": 0.90},
      tau_accept=0.01,
      baseline_telemetry=base_tel_letters,
      candidate_telemetry=cand_tel_letters,
  )
  assert dec_letters.accepted is False
  assert dec_letters.status == "REVERTED_CATEGORICAL_TAXONOMY"

  # Increased total count of OVER_CONTAINMENT_FALSE_ALARM
  base_tel_count = {
      "CASE-01": {"failure_category": "UNGROUNDED_HALLUCINATED_CLAIM"},
      "CASE-02": {"failure_category": "FLAWLESS_CONTAINMENT"},
  }
  cand_tel_count = {
      "CASE-01": {"failure_category": "OVER_CONTAINMENT_FALSE_ALARM"},
      "CASE-02": {"failure_category": "OVER_CONTAINMENT_FALSE_ALARM"},
  }
  dec_count = evaluate_candidate_acceptance(
      {"CASE-01": 0.85, "CASE-02": 0.85},
      {"CASE-01": 0.90, "CASE-02": 0.90},
      tau_accept=0.01,
      baseline_telemetry=base_tel_count,
      candidate_telemetry=cand_tel_count,
  )
  assert dec_count.accepted is False
  assert dec_count.status == "REVERTED_CATEGORICAL_TAXONOMY"
  assert "CASE-01" in dec_count.regressed_cases or "CASE-02" in dec_count.regressed_cases


def test_evaluate_candidate_acceptance_int_keys_and_worsened_partial_loss():
  from agent.hillclimb_harness import CategoricalCaseTelemetry

  # 1. Integer keys from GEPA ListDataLoader regressing must not raise TypeError
  dec_int = evaluate_candidate_acceptance(
      {0: 0.90, 1: 0.90},
      {0: 0.50, 1: 0.95},
      tau_accept=0.01,
  )
  assert dec_int.accepted is False
  assert dec_int.status == "REVERTED_REGRESSION"
  assert "0" in dec_int.regressed_cases

  # 2. Worsening an already partial loss_penalty (e.g. 0.6065 -> 0.2231) must trigger REVERTED_CATEGORICAL_SAFETY
  base_tel = {
      "CASE-01": CategoricalCaseTelemetry(case_id="CASE-01", loss_penalty=0.6065),
  }
  cand_tel = {
      "CASE-01": CategoricalCaseTelemetry(case_id="CASE-01", loss_penalty=0.2231),
  }
  dec_loss = evaluate_candidate_acceptance(
      {"CASE-01": 0.60},
      {"CASE-01": 0.75},
      tau_accept=0.01,
      baseline_telemetry=base_tel,
      candidate_telemetry=cand_tel,
  )
  assert dec_loss.accepted is False
  assert dec_loss.status == "REVERTED_CATEGORICAL_SAFETY"
  assert "CASE-01" in dec_loss.regressed_cases



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


def test_budget_ledger_enforces_limit_and_persists(tmp_path: Path):
  from agent.hillclimb_harness import (
      BudgetExceeded,
      BudgetLedger,
      estimate_model_cost_usd,
      redact,
  )

  ledger_path = tmp_path / "budget.json"
  ledger = BudgetLedger(ledger_path, limit_usd=0.01)
  assert ledger.spent_usd == 0.0
  assert ledger.remaining_usd == pytest.approx(0.01)

  entry = ledger.record(
      model="gemini-2.5-flash",
      prompt_tokens=10_000,
      completion_tokens=1_000,
      note="contact with sk-1234567890abcdef12345678",
  )
  assert "sk-[REDACTED]" in entry["note"]
  assert ledger.spent_usd > 0.0

  reloaded = BudgetLedger(ledger_path, limit_usd=0.01)
  assert reloaded.spent_usd == pytest.approx(ledger.spent_usd)

  reloaded.record(
      model="gemini-2.5-pro",
      prompt_tokens=100_000,
      completion_tokens=10_000,
      note="push over limit",
  )
  with pytest.raises(BudgetExceeded):
    reloaded.assert_can_spend()

  assert estimate_model_cost_usd("gemma-4-e4b-it", 5000, 1000) == 0.0
  assert redact("token sk-1234567890abcdef1234") == "token sk-[REDACTED]"


def test_filter_balanced_traces_balances_verdict_classes():
  from agent.hillclimb_harness import filter_balanced_traces

  traces = [
      {"case_id": f"M-{i}", "expected_verdict": "MALICIOUS", "actual_verdict": "MALICIOUS", "score": 0.90 + 0.01 * i, "inert": False, "zero_tool_hesitation": False, "safety_gate_triggered": False}
      for i in range(6)
  ] + [
      {"case_id": f"B-{i}", "expected_verdict": "BENIGN", "actual_verdict": "BENIGN", "score": 0.85 + 0.01 * i, "inert": False, "zero_tool_hesitation": False, "safety_gate_triggered": False}
      for i in range(4)
  ] + [
      {"case_id": f"S-{i}", "expected_verdict": "SUSPICIOUS", "actual_verdict": "SUSPICIOUS", "score": 0.82 + 0.01 * i, "inert": False, "zero_tool_hesitation": False, "safety_gate_triggered": False}
      for i in range(2)
  ] + [
      {"case_id": "BAD-1", "expected_verdict": "MALICIOUS", "actual_verdict": "BENIGN", "score": 0.99, "inert": False, "zero_tool_hesitation": False, "safety_gate_triggered": False},
      {"case_id": "BAD-2", "expected_verdict": "MALICIOUS", "actual_verdict": "MALICIOUS", "score": 0.99, "inert": True, "zero_tool_hesitation": False, "safety_gate_triggered": False},
  ]

  balanced = filter_balanced_traces(traces, min_examples_per_class=2, min_score=0.80)
  assert len(balanced) == 6
  counts = {}
  for t in balanced:
    counts[t["expected_verdict"]] = counts.get(t["expected_verdict"], 0) + 1
  assert counts == {"BENIGN": 2, "MALICIOUS": 2, "SUSPICIOUS": 2}


def test_attribute_candidate_edits_marks_multi_component_overlapping_edit_confounded():
  from agent.hillclimb_harness import (
      HARNESS2_ATTRIBUTION_LABELS,
      attribute_candidate_edits,
  )

  assert HARNESS2_ATTRIBUTION_LABELS == (
      "helped",
      "hurt",
      "no_observed_effect",
      "confounded",
  )

  base = {
      "basic_ioc_enrichment.md": "# Seed IOC",
      "malware_triage.md": "# Seed Malware",
      "suspicious_login_triage.md": "# Seed Login",
  }
  cand = {
      "basic_ioc_enrichment.md": "# Edited IOC",
      "malware_triage.md": "# Edited Malware",
      "suspicious_login_triage.md": "# Seed Login",
  }
  base_scores = {"CASE-01": 0.60, "CASE-02": 0.60}
  cand_scores = {"CASE-01": 0.90, "CASE-02": 0.90}

  # Without isolated per-component telemetry (or with overlapping case mappings),
  # changing two components together must be labeled confounded.
  attrs = attribute_candidate_edits(
      base_candidate=base,
      candidate=cand,
      baseline_scores=base_scores,
      candidate_scores=cand_scores,
      tau_accept=0.02,
  )
  assert attrs["basic_ioc_enrichment.md"].changed is True
  assert attrs["basic_ioc_enrichment.md"].label == "confounded"
  assert attrs["malware_triage.md"].changed is True
  assert attrs["malware_triage.md"].label == "confounded"
  assert attrs["suspicious_login_triage.md"].changed is False
  assert attrs["suspicious_login_triage.md"].label == "no_observed_effect"


def test_attribute_candidate_edits_labels_isolated_helped_hurt_and_disjoint_cases():
  from agent.hillclimb_harness import attribute_candidate_edits

  base = {
      "basic_ioc_enrichment.md": "# Seed IOC",
      "malware_triage.md": "# Seed Malware",
  }
  # 1. Single-component helped
  cand_helped = {
      "basic_ioc_enrichment.md": "# Better IOC",
      "malware_triage.md": "# Seed Malware",
  }
  helped_attrs = attribute_candidate_edits(
      base_candidate=base,
      candidate=cand_helped,
      baseline_scores={"CASE-01": 0.60, "CASE-02": 0.80},
      candidate_scores={"CASE-01": 0.85, "CASE-02": 0.80},
      tau_accept=0.02,
  )
  assert helped_attrs["basic_ioc_enrichment.md"].label == "helped"
  assert helped_attrs["basic_ioc_enrichment.md"].mean_delta == pytest.approx(0.125)
  assert helped_attrs["malware_triage.md"].label == "no_observed_effect"

  # 2. Single-component hurt via regression
  cand_hurt = {
      "basic_ioc_enrichment.md": "# Regressed IOC",
      "malware_triage.md": "# Seed Malware",
  }
  hurt_attrs = attribute_candidate_edits(
      base_candidate=base,
      candidate=cand_hurt,
      baseline_scores={"CASE-01": 0.85, "CASE-02": 0.60},
      candidate_scores={"CASE-01": 0.50, "CASE-02": 0.95},
      tau_accept=0.02,
  )
  assert hurt_attrs["basic_ioc_enrichment.md"].label == "hurt"
  assert "CASE-01" in hurt_attrs["basic_ioc_enrichment.md"].regressed_cases

  # 3. Single-component no_observed_effect within noise floor
  cand_flat = {
      "basic_ioc_enrichment.md": "# Slightly reworded IOC",
      "malware_triage.md": "# Seed Malware",
  }
  flat_attrs = attribute_candidate_edits(
      base_candidate=base,
      candidate=cand_flat,
      baseline_scores={"CASE-01": 0.80},
      candidate_scores={"CASE-01": 0.805},
      tau_accept=0.02,
  )
  assert flat_attrs["basic_ioc_enrichment.md"].label == "no_observed_effect"

  # 4. Two changed components with strictly disjoint evaluated case sets in telemetry
  cand_disjoint = {
      "basic_ioc_enrichment.md": "# Better IOC",
      "malware_triage.md": "# Worse Malware",
  }
  base_tel = {
      "CASE-01": {"case_id": "CASE-01", "implicated_runbook": "basic_ioc_enrichment.md"},
      "CASE-02": {"case_id": "CASE-02", "implicated_runbook": "malware_triage.md"},
  }
  cand_tel = {
      "CASE-01": {"case_id": "CASE-01", "implicated_runbook": "basic_ioc_enrichment.md"},
      "CASE-02": {"case_id": "CASE-02", "implicated_runbook": "malware_triage.md"},
  }
  disjoint_attrs = attribute_candidate_edits(
      base_candidate=base,
      candidate=cand_disjoint,
      baseline_scores={"CASE-01": 0.60, "CASE-02": 0.80},
      candidate_scores={"CASE-01": 0.90, "CASE-02": 0.50},
      tau_accept=0.02,
      baseline_telemetry=base_tel,
      candidate_telemetry=cand_tel,
  )
  assert disjoint_attrs["basic_ioc_enrichment.md"].label == "helped"
  assert disjoint_attrs["basic_ioc_enrichment.md"].evaluated_cases == ("CASE-01",)
  assert disjoint_attrs["malware_triage.md"].label == "hurt"
  assert disjoint_attrs["malware_triage.md"].evaluated_cases == ("CASE-02",)


def test_experience_library_records_only_isolated_helped_and_renders_markdown(tmp_path: Path):
  from agent.hillclimb_harness import (
      ExperienceLibrary,
      attribute_candidate_edits,
  )

  lib = ExperienceLibrary(tmp_path / "experience")
  base = {
      "basic_ioc_enrichment.md": "# Seed IOC",
      "malware_triage.md": "# Seed Malware",
  }
  confounded_cand = {
      "basic_ioc_enrichment.md": "# Edited IOC",
      "malware_triage.md": "# Edited Malware",
  }
  confounded_attrs = attribute_candidate_edits(
      base_candidate=base,
      candidate=confounded_cand,
      baseline_scores={"CASE-01": 0.60},
      candidate_scores={"CASE-01": 0.95},
      tau_accept=0.02,
  )
  skipped = lib.record_from_attributions(
      attributions=confounded_attrs,
      cue="RFC-5737 documentation subnet check",
      lesson="Verify routing scope before containment.",
      evidence="Score rose on CASE-01.",
  )
  assert skipped is None
  assert lib.read_entries() == []

  helped_cand = {
      "basic_ioc_enrichment.md": "# Seed IOC\nCheck Stage B network routing before isolation.",
      "malware_triage.md": "# Seed Malware",
  }
  helped_attrs = attribute_candidate_edits(
      base_candidate=base,
      candidate=helped_cand,
      baseline_scores={"CASE-01": 0.55},
      candidate_scores={"CASE-01": 0.92},
      tau_accept=0.02,
  )
  saved = lib.record_from_attributions(
      attributions=helped_attrs,
      cue="Documentation IP false alarm",
      lesson="Query get_ip_address_report in Stage B before host containment.",
      evidence="Baseline 0.55 -> Probe 0.92 (+0.37) on CASE-01 with sk-1234567890abcdef1234.",
      scope="DOM",
  )
  assert saved is not None
  assert saved.component_name == "basic_ioc_enrichment.md"
  assert saved.attribution_label == "helped"
  assert "sk-[REDACTED]" in saved.evidence

  md_path = tmp_path / "experience" / "EXPERIENCE.md"
  assert md_path.exists()
  md_text = md_path.read_text(encoding="utf-8")
  assert "Documentation IP false alarm" in md_text
  assert "Query get_ip_address_report" in md_text

  hits = lib.retrieve_for_component("basic_ioc_enrichment.md")
  assert len(hits) == 1
  assert hits[0].cue == "Documentation IP false alarm"



