"""Cross-Model Transfer & Cost Staircase Benchmark for Gen 5 Tier 1 Runbooks.

Compares three runbook arms on the 20-case Gen 5 validation split across
gemini-2.5-flash-lite, gemini-2.5-flash, and gemini-3.5-flash-lite:
  1. seed_runbooks: Upstream seed runbooks (third_party/ai-runbooks/.clinerules/run_books)
  2. gepa_single_proposer: Single-proposer GEPA evolved runbooks (dspy__context-engineering)
  3. harness2_k2_evolved: k=2 Harness^2 Propose-Probe-Compose evolved runbooks

Computes Harbor 60/20/20 composite, GEPA fitness, per-verdict scores
(MALICIOUS, BENIGN, SUSPICIOUS, INCONCLUSIVE), Signal Detection Theory
sensitivity (d') and criterion bias (c), operational financial loss ($L),
word counts, tool call counts, token usage/cost, and executes the Cost
Staircase walk across the evaluated model tiers.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
  sys.path.insert(0, str(ROOT_DIR))

from agent.aqua_diagnostics import extract_trace_diagnosis
from agent.gepa_runbook_optimizer import (
    CORE_RUNBOOKS,
    DEFAULT_RUNBOOKS_DIR,
    calculate_loss_penalty,
    load_forbidden_literals,
    load_seed_runbooks,
    resolve_implicated_runbook,
)
from agent.hierarchical_soc_agent import HierarchicalSOCTier1Agent
from agent.hillclimb_harness import (
    BudgetLedger,
    CostStaircaseReport,
    HarnessIntegrityGuard,
    estimate_model_cost_usd,
    run_cost_staircase_walk,
)
from agent.jev_backends import build_jev_backend
from agent.jev_evaluator import JevSocJudgeEvaluator
from agent.soc_environment import SocEnvironment
from agent.soc_tier1_agent import extract_soc_decision
from scripts import gen5_exposure
from scripts.eval_cost_engine import (
    DecisionOutcome,
    _is_threat_scenario,
    calculate_expected_loss_matrix,
    calculate_sdt_metrics,
    classify_decision_outcome,
)
from scripts.eval_soc_agent import evaluate_assertions
from scripts.eval_trajectory_verifier import verify_agent_trajectory
from scripts.verify_harbor_soc import compose_soc_reward


DEFAULT_TRANSFER_MODELS: Tuple[str, ...] = (
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-3.5-flash-lite",
)

DEFAULT_STAIRCASE_TIERS: Tuple[str, ...] = (
    "gemini-2.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-2.5-flash-lite",
)

ARM_SPECS: Dict[str, Dict[str, Any]] = {
    "seed_runbooks": {
        "label": "Seed Runbooks (Upstream .clinerules)",
        "path": DEFAULT_RUNBOOKS_DIR,
    },
    "gepa_single_proposer": {
        "label": "Single-Proposer GEPA (dspy__context-engineering)",
        "path": (
            ROOT_DIR
            / "docs"
            / "soc_eval_results"
            / "dspy_overnight"
            / "candidates"
            / "r1_gepa_gen5_gemini-2_5-flash-lite_w550_s202"
        ),
    },
    "harness2_k2_evolved": {
        "label": "Harness^2 k=2 Evolved (Propose-Probe-Compose)",
        "path": (
            ROOT_DIR
            / "docs"
            / "soc_eval_results"
            / "harness2_8h_campaign"
            / "gen5_flash_lite"
        ),
    },
}


def load_arm_runbooks(arm_name: str) -> Tuple[Dict[str, str], Dict[str, int]]:
  """Load the 4 core runbooks for the specified arm and count words per file."""
  if arm_name not in ARM_SPECS:
    raise ValueError(f"Unknown arm: {arm_name}")
  arm_dir = Path(ARM_SPECS[arm_name]["path"])
  runbooks = load_seed_runbooks(arm_dir)
  word_counts = {name: len(text.split()) for name, text in runbooks.items()}
  return runbooks, word_counts


def classify_gen5_operational_outcome(
    expected_verdict: str,
    actual_verdict: str,
    operator_actions_matched: bool,
    prohibited_actions_avoided: bool,
) -> DecisionOutcome:
  """Classify Gen 5 4-verdict decision and containment accuracy into SDT outcomes.

  - MALICIOUS: TP if verdict == MALICIOUS and required primary containment matched
    and prohibited avoided; otherwise FN (uncontained breach).
  - SUSPICIOUS: TP if verdict == SUSPICIOUS and prohibited actions (isolate_host,
    close_case) avoided; FP if over-contained (MALICIOUS or isolate_host); FN if
    dismissed as BENIGN/INCONCLUSIVE.
  - BENIGN / INCONCLUSIVE: TN if verdict matches expected and prohibited containment
    avoided; FP if disruptive containment or MALICIOUS/SUSPICIOUS verdict issued.
  """
  exp = str(expected_verdict or "").strip().upper()
  act = str(actual_verdict or "").strip().upper()
  if exp in ("MALICIOUS", "CRITICAL_MALICIOUS"):
    if (
        act in ("MALICIOUS", "CRITICAL_MALICIOUS")
        and operator_actions_matched
        and prohibited_actions_avoided
    ):
      return DecisionOutcome.TRUE_POSITIVE
    return DecisionOutcome.FALSE_NEGATIVE
  if exp == "SUSPICIOUS":
    if act == "SUSPICIOUS" and prohibited_actions_avoided:
      return DecisionOutcome.TRUE_POSITIVE
    if act in ("MALICIOUS", "CRITICAL_MALICIOUS") or not prohibited_actions_avoided:
      return DecisionOutcome.FALSE_POSITIVE
    return DecisionOutcome.FALSE_NEGATIVE
  if act == exp and prohibited_actions_avoided:
    return DecisionOutcome.TRUE_NEGATIVE
  return DecisionOutcome.FALSE_POSITIVE


def compute_w350_context_debt_penalty(
    candidate: Mapping[str, str],
    seed_frozen: Sequence[str] = (
        "basic_ioc_enrichment.md",
        "suspicious_login_triage.md",
    ),
    max_words: int = 350,
) -> float:
  """Compute the intrinsic context-debt regularizer (0.008 per un-cleaned/over-budget active runbook)."""
  debt_count = 0
  frozen_set = set(seed_frozen)
  for name, text in candidate.items():
    if name in frozen_set:
      continue
    has_vars = bool(re.search(r"\$\{[A-Za-z0-9_]+\}", text))
    has_mermaid = bool(re.search(r"```\{?mermaid\}?|sequenceDiagram", text))
    has_pseudo = bool(
        re.search(
            r"\b(ask_followup_question|attempt_completion|write_to_file|generate_report_file\.md)\b",
            text,
        )
    )
    over_words = len(text.split()) > max_words
    if has_vars or has_mermaid or has_pseudo or over_words:
      debt_count += 1
  return 0.008 * debt_count


def evaluate_single_gen5_case(
    case: Dict[str, Any],
    candidate: Dict[str, str],
    model: str,
    project_id: Optional[str],
    region: str,
    jev_evaluator: JevSocJudgeEvaluator,
    forbidden_literals: Sequence[str],
    budget_ledger: Optional[BudgetLedger],
    context_debt_penalty: float,
    max_iterations: int = 8,
) -> Dict[str, Any]:
  """Evaluate a single Gen 5 validation case and return full trajectory telemetry."""
  cid = str(case.get("eval_id") or case.get("id") or "unknown")
  if budget_ledger is not None:
    budget_ledger.assert_can_spend()

  env = SocEnvironment.from_eval_case(case)
  agent = HierarchicalSOCTier1Agent(
      runbooks_dict=candidate,
      environment=env,
      managed_model=model,
      project_id=project_id,
      region=region,
      use_live_mcp=False,
  )

  t0 = time.time()
  prompt = case.get("prompt", "")
  response = agent.query(prompt, max_iterations=max_iterations)
  latency_ms = int(round((time.time() - t0) * 1000))

  raw_usage = getattr(response, "usage", None) or {}
  prompt_tokens = int(raw_usage.get("prompt_tokens") or 0)
  completion_tokens = int(raw_usage.get("completion_tokens") or 0)
  total_tokens = int(
      raw_usage.get("total_tokens") or (prompt_tokens + completion_tokens)
  )

  if budget_ledger is not None:
    budget_ledger.record(
        model=model,
        prompt_tokens=prompt_tokens or 500,
        completion_tokens=completion_tokens or 200,
        note=f"gen5_transfer:{model}:{cid}",
    )

  resp_text = getattr(response, "response", "") or ""
  agent_traj = getattr(response, "trajectory", []) or []

  traj_verif = verify_agent_trajectory(
      trajectory=agent_traj,
      expected_actions=case.get("expected_actions", []),
      prohibited_actions=case.get("prohibited_actions", []),
      expected_entities=case.get("expected_entities", []),
      response_text=resp_text,
      prohibited_entities=case.get("prohibited_entities", []),
      liveness=case.get("liveness"),
      generation=int(case.get("generation") or 5),
  )
  inert = bool(getattr(traj_verif, "inert", False))
  entity_violations = list(
      getattr(traj_verif, "prohibited_entity_violations", []) or []
  )

  assertions = case.get("assertions", {}) or {}
  assert_passed, _ = evaluate_assertions(
      resp_text,
      must_contain=assertions.get("must_contain", []),
      must_not_contain=assertions.get("must_not_contain", []),
  )

  decision_obj = extract_soc_decision(resp_text)
  actual_verdict = str(getattr(response, "verdict", "") or "")
  if not actual_verdict and decision_obj is not None:
    actual_verdict = str(getattr(decision_obj, "verdict", "") or "")
  recommended_actions = (
      list(getattr(decision_obj, "recommended_actions", []) or [])
      if decision_obj is not None
      else []
  )

  loss_penalty = calculate_loss_penalty(
      expected_label=case.get("ground_truth_label", ""),
      actual_verdict=actual_verdict,
      executed_actions=traj_verif.executed_actions,
      prohibited_actions=case.get("prohibited_actions", []),
      prohibited_violation=bool(entity_violations),
  )

  decision_dict = (
      decision_obj.to_dict()
      if decision_obj is not None
      else ({"verdict": actual_verdict} if actual_verdict else None)
  )
  card = compose_soc_reward(
      case=case,
      trajectory=agent_traj,
      report_text=resp_text,
      decision_data=decision_dict,
      jev_evaluator=jev_evaluator,
      jev_backend_name="mock",
      manifest_path=gen5_exposure.MANIFEST_PATH,
      metrics={
          "tokens_in": prompt_tokens,
          "tokens_out": completion_tokens,
          "latency_ms": latency_ms,
          "infra_failure": False,
      },
  )
  harbor_reward = float(card["reward"])
  inert = bool(card.get("inert", inert))
  entity_violations = list(
      card.get("prohibited_entity_violations", entity_violations) or []
  )
  jev_choice = (card.get("jev_evaluation") or {}).get("primary_choice")

  zero_tool_hesitation = bool(
      not inert and traj_verif.epistemic_step_count == 0 and len(agent_traj) == 0
  )
  if inert:
    harbor_reward = 0.0
    gepa_fitness = 0.0
    jev_choice = "INERT"
  elif zero_tool_hesitation:
    harbor_reward = 0.0
    gepa_fitness = 0.0
    jev_choice = "PREMATURE_TERMINATION_ZERO_TOOLS"
  else:
    gepa_fitness = max(0.0, harbor_reward - context_debt_penalty)

  safety_gate_triggered = bool(
      (not traj_verif.prohibited_actions_avoided) or entity_violations
  )
  implicated_runbook = resolve_implicated_runbook({
      "component_name": getattr(response, "runbook", ""),
      "alert_type": case.get(
          "alert_type", getattr(response, "classification", "")
      ),
      "case_id": cid,
      "name": case.get("name", ""),
      "prompt": prompt,
  })

  # Classify SDT decision outcome for operational financial loss and d'/c
  sdt_outcome = classify_gen5_operational_outcome(
      expected_verdict=str(case.get("ground_truth_label", "")),
      actual_verdict=actual_verdict,
      operator_actions_matched=bool(traj_verif.operator_actions_matched),
      prohibited_actions_avoided=bool(traj_verif.prohibited_actions_avoided),
  )
  cmdb_ctx = case.get("cmdb_context") or {}
  criticality = str(
      case.get("criticality_tier")
      or case.get("asset_criticality")
      or cmdb_ctx.get("criticality")
      or "STANDARD"
  ).upper()

  trace_entry: Dict[str, Any] = {
      "case_id": cid,
      "family_id": case.get("family_id", ""),
      "alert_type": case.get(
          "alert_type", getattr(response, "classification", "")
      ),
      "expected_verdict": str(case.get("ground_truth_label", "")).upper(),
      "actual_verdict": actual_verdict.upper(),
      "verdict_exact_match": (
          actual_verdict.strip().upper()
          == str(case.get("ground_truth_label", "")).strip().upper()
      ),
      "harbor_reward": round(harbor_reward, 6),
      "score": round(gepa_fitness, 6),
      "loss_penalty": round(loss_penalty, 6),
      "assert_passed": bool(assert_passed),
      "operator_actions_matched": bool(traj_verif.operator_actions_matched),
      "prohibited_actions_avoided": bool(traj_verif.prohibited_actions_avoided),
      "executed_actions": list(traj_verif.executed_actions),
      "recommended_actions": recommended_actions,
      "epistemic_step_count": int(traj_verif.epistemic_step_count),
      "tool_call_count": len(agent_traj),
      "inert": inert,
      "zero_tool_hesitation": zero_tool_hesitation,
      "prohibited_entity_violations": entity_violations,
      "safety_gate_triggered": safety_gate_triggered,
      "implicated_runbook": implicated_runbook,
      "decision_outcome": sdt_outcome.value,
      "criticality": criticality,
      "usage": {
          "prompt_tokens": prompt_tokens,
          "completion_tokens": completion_tokens,
          "total_tokens": total_tokens,
      },
      "token_cost_usd": round(
          estimate_model_cost_usd(
              model,
              prompt_tokens=prompt_tokens,
              completion_tokens=completion_tokens,
          ),
          6,
      ),
      "latency_ms": latency_ms,
      "jev_choice": jev_choice,
      "gen5_components": card.get("components"),
  }
  diag = extract_trace_diagnosis(
      trace_entry, forbidden_literals=forbidden_literals
  )
  trace_entry["failure_category"] = diag.failure_category
  return trace_entry


def aggregate_arm_metrics(
    traces: Sequence[Dict[str, Any]],
    model: str,
    arm_name: str,
    word_counts: Mapping[str, int],
    context_debt_penalty: float,
) -> Dict[str, Any]:
  """Aggregate 20-case Gen 5 validation metrics including Harbor, GEPA, SDT, and Loss."""
  n = len(traces)
  if n == 0:
    raise ValueError("Cannot aggregate empty traces.")

  harbor_mean = sum(float(t["harbor_reward"]) for t in traces) / n
  gepa_mean = sum(float(t["score"]) for t in traces) / n
  pass_count = sum(1 for t in traces if float(t["harbor_reward"]) >= 0.80)
  verdict_matches = sum(1 for t in traces if t.get("verdict_exact_match"))

  by_verdict: Dict[str, List[float]] = {}
  by_runbook: Dict[str, List[float]] = {}
  for t in traces:
    ev = str(t.get("expected_verdict") or "UNKNOWN").upper()
    by_verdict.setdefault(ev, []).append(float(t["harbor_reward"]))
    rb = str(t.get("implicated_runbook") or "unknown")
    by_runbook.setdefault(rb, []).append(float(t["harbor_reward"]))

  per_verdict_scores = {
      k: round(sum(vals) / len(vals), 4) for k, vals in sorted(by_verdict.items())
  }
  per_runbook_scores = {
      k: round(sum(vals) / len(vals), 4) for k, vals in sorted(by_runbook.items())
  }

  for t in traces:
    t["decision_outcome"] = classify_gen5_operational_outcome(
        expected_verdict=str(t.get("expected_verdict", "")),
        actual_verdict=str(t.get("actual_verdict", "")),
        operator_actions_matched=bool(t.get("operator_actions_matched", True)),
        prohibited_actions_avoided=bool(t.get("prohibited_actions_avoided", True)),
    ).value

  hits = sum(
      1
      for t in traces
      if t.get("decision_outcome") == DecisionOutcome.TRUE_POSITIVE.value
  )
  misses = sum(
      1
      for t in traces
      if t.get("decision_outcome") == DecisionOutcome.FALSE_NEGATIVE.value
  )
  false_alarms = sum(
      1
      for t in traces
      if t.get("decision_outcome") == DecisionOutcome.FALSE_POSITIVE.value
  )
  correct_rejections = sum(
      1
      for t in traces
      if t.get("decision_outcome") == DecisionOutcome.TRUE_NEGATIVE.value
  )
  sdt = calculate_sdt_metrics(
      hits=hits,
      misses=misses,
      false_alarms=false_alarms,
      correct_rejections=correct_rejections,
  )
  loss_card = calculate_expected_loss_matrix(list(traces))

  total_prompt_tokens = sum(
      int((t.get("usage") or {}).get("prompt_tokens") or 0) for t in traces
  )
  total_completion_tokens = sum(
      int((t.get("usage") or {}).get("completion_tokens") or 0) for t in traces
  )
  total_token_cost_usd = sum(float(t.get("token_cost_usd") or 0.0) for t in traces)
  mean_tool_calls = sum(int(t.get("tool_call_count") or 0) for t in traces) / n
  mean_epistemic_steps = (
      sum(int(t.get("epistemic_step_count") or 0) for t in traces) / n
  )
  mean_latency_ms = sum(int(t.get("latency_ms") or 0) for t in traces) / n
  safety_violations = sum(
      1 for t in traces if t.get("safety_gate_triggered")
  )
  zero_tool_cases = sum(1 for t in traces if t.get("zero_tool_hesitation"))
  inert_cases = sum(1 for t in traces if t.get("inert"))

  return {
      "model": model,
      "arm": arm_name,
      "arm_label": ARM_SPECS[arm_name]["label"],
      "cases_evaluated": n,
      "harbor_60_20_20": round(harbor_mean, 4),
      "gepa_fitness": round(gepa_mean, 4),
      "context_debt_penalty": round(context_debt_penalty, 4),
      "pass_rate": round(pass_count / n, 4),
      "verdict_accuracy": round(verdict_matches / n, 4),
      "per_verdict_scores": per_verdict_scores,
      "per_runbook_scores": per_runbook_scores,
      "sdt_metrics": {
          "d_prime": round(sdt.d_prime, 4),
          "criterion_c": round(sdt.criterion_c, 4),
          "hit_rate": round(sdt.hit_rate, 4),
          "false_alarm_rate": round(sdt.false_alarm_rate, 4),
          "hits": hits,
          "misses": misses,
          "false_alarms": false_alarms,
          "correct_rejections": correct_rejections,
      },
      "operational_loss": {
          "total_loss_usd": round(loss_card.total_loss_usd, 2),
          "fp_loss_usd": round(loss_card.fp_loss_usd, 2),
          "fn_loss_usd": round(loss_card.fn_loss_usd, 2),
          "investigation_cost_usd": round(loss_card.investigation_cost_usd, 4),
      },
      "word_counts": dict(word_counts),
      "total_words": sum(word_counts.values()),
      "mean_tool_calls": round(mean_tool_calls, 2),
      "mean_epistemic_steps": round(mean_epistemic_steps, 2),
      "mean_latency_ms": round(mean_latency_ms, 1),
      "prompt_tokens": total_prompt_tokens,
      "completion_tokens": total_completion_tokens,
      "token_cost_usd": round(total_token_cost_usd, 6),
      "safety_violations": safety_violations,
      "zero_tool_cases": zero_tool_cases,
      "inert_cases": inert_cases,
      "cases": list(traces),
  }


def render_markdown_scorecard(
    summary: Mapping[str, Any],
    staircase: CostStaircaseReport,
) -> str:
  """Render Markdown scorecard for the Gen 5 cross-model transfer and cost staircase."""
  lines: List[str] = [
      "# Gen 5 Tier 1 Cross-Model Transfer & Cost Staircase Scorecard",
      "",
      f"- **Run ID**: `{summary.get('run_id')}`",
      f"- **Split**: Gen 5 `{summary.get('val_split')}` (`{summary.get('num_cases')}` cases)",
      f"- **Harness Composite SHA-256**: `{summary.get('harness_composite_sha256')}`",
      "",
      "## 1. Cross-Model Transfer Matrix (3 Models x 3 Runbook Arms)",
      "",
      "| Model | Runbook Arm | Words | Harbor 60/20/20 | GEPA Fitness | MALICIOUS | BENIGN | SUSPICIOUS | INCONCLUSIVE | $d'$ | $c$ | Total Loss (USD) | Mean Tools | Token Cost (USD) |",
      "| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
  ]
  for entry in summary.get("matrix", []):
    pv = entry.get("per_verdict_scores") or {}
    sdt = entry.get("sdt_metrics") or {}
    loss = entry.get("operational_loss") or {}
    lines.append(
        f"| `{entry['model']}` | `{entry['arm']}` | {entry['total_words']} "
        f"| **{entry['harbor_60_20_20']:.4f}** | {entry['gepa_fitness']:.4f} "
        f"| {pv.get('MALICIOUS', 0.0):.4f} | {pv.get('BENIGN', 0.0):.4f} "
        f"| {pv.get('SUSPICIOUS', 0.0):.4f} | {pv.get('INCONCLUSIVE', 0.0):.4f} "
        f"| {sdt.get('d_prime', 0.0):.2f} | {sdt.get('criterion_c', 0.0):.2f} "
        f"| \\${loss.get('total_loss_usd', 0.0):,.2f} | {entry['mean_tool_calls']:.2f} "
        f"| \\${entry['token_cost_usd']:.4f} |"
    )

  lines.extend([
      "",
      "## 2. 3-Model Aggregate Summary by Runbook Arm",
      "",
      "| Runbook Arm | Total Words | Mean Harbor 60/20/20 | Mean GEPA Fitness | Mean $d'$ | Mean Total Loss (USD) | Mean Tools | Total Safety Violations |",
      "| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
  ])
  for arm_name, agg in (summary.get("arm_aggregates") or {}).items():
    lines.append(
        f"| `{arm_name}` | {agg['total_words']} "
        f"| **{agg['mean_harbor_60_20_20']:.4f}** | {agg['mean_gepa_fitness']:.4f} "
        f"| {agg['mean_d_prime']:.2f} | \\${agg['mean_total_loss_usd']:,.2f} "
        f"| {agg['mean_tool_calls']:.2f} | {agg['total_safety_violations']} |"
    )

  lines.extend([
      "",
      "## 3. Per-Runbook Component Breakdown (`harness2_k2_evolved` vs `seed_runbooks`)",
      "",
      "| Model | Arm | `basic_ioc_enrichment.md` | `malware_triage.md` | `suspicious_login_triage.md` | `lateral_movement_hunt_psexec_wmi.md` |",
      "| :--- | :--- | ---: | ---: | ---: | ---: |",
  ])
  for entry in summary.get("matrix", []):
    pr = entry.get("per_runbook_scores") or {}
    def _fmt_rb(rb_name: str) -> str:
      val = pr.get(rb_name)
      return f"{val:.4f}" if isinstance(val, (int, float)) else "frozen (train-only)"
    lines.append(
        f"| `{entry['model']}` | `{entry['arm']}` "
        f"| {_fmt_rb('basic_ioc_enrichment.md')} "
        f"| {_fmt_rb('malware_triage.md')} "
        f"| {_fmt_rb('suspicious_login_triage.md')} "
        f"| {_fmt_rb('lateral_movement_hunt_psexec_wmi.md')} |"
    )

  sc_dict = staircase.to_dict()
  lines.extend([
      "",
      "## 4. Cost Staircase Walk (`harness2_k2_evolved` on Gen 5 `validation`)",
      "",
      f"- **Ceiling Model**: `{sc_dict['ceiling_model']}` (`{sc_dict['ceiling_score']:.4f}`)",
      f"- **Selected Most Cost-Effective Model**: `{sc_dict['selected_model']}` (`{sc_dict['selected_score']:.4f}`, tolerance `{sc_dict['tolerance']:.2f}`)",
      "",
      "| Rung Model Tier | Mean Score | Min Loss Penalty | Passed Safety | Within Tolerance | Tokens In | Tokens Out | Mean Latency (ms) |",
      "| :--- | ---: | ---: | :---: | :---: | ---: | ---: | ---: |",
  ])
  for rung in sc_dict.get("rungs", []):
    lines.append(
        f"| `{rung['model_tier']}` | **{rung['mean_score']:.4f}** "
        f"| {rung['min_loss_penalty']:.2f} | {rung['passed_safety']} "
        f"| {rung['within_tolerance']} | {rung.get('tokens_in', 0)} "
        f"| {rung.get('tokens_out', 0)} | {rung.get('latency_ms', 0.0):.1f} |"
    )
  lines.append("")
  return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
  parser = argparse.ArgumentParser(
      description="Run Gen 5 cross-model transfer and cost staircase benchmark."
  )
  parser.add_argument(
      "--models",
      nargs="+",
      default=list(DEFAULT_TRANSFER_MODELS),
      help="Models to evaluate.",
  )
  parser.add_argument(
      "--arms",
      nargs="+",
      default=list(ARM_SPECS.keys()),
      help="Runbook arms to evaluate.",
  )
  parser.add_argument(
      "--val-split",
      default="validation",
      help="Gen 5 validation split name (never final_test).",
  )
  parser.add_argument(
      "--output-dir",
      default="docs/soc_eval_results/harness2_8h_campaign/gen5_transfer",
      help="Output directory for transfer scorecard and staircase report.",
  )
  parser.add_argument(
      "--project-id",
      default=os.environ.get("PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT"),
  )
  parser.add_argument(
      "--region",
      default=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
  )
  parser.add_argument(
      "--max-workers",
      type=int,
      default=4,
      help="Parallel case evaluation workers per (model, arm).",
  )
  parser.add_argument(
      "--budget-limit-usd",
      type=float,
      default=4.0,
      help="Hard USD budget ceiling for this transfer benchmark.",
  )
  parser.add_argument(
      "--cost-tolerance",
      type=float,
      default=0.05,
      help="Max score drop below ceiling model allowed on cost staircase.",
  )
  parser.add_argument(
      "--resume-existing",
      action="store_true",
      help="Reuse already completed (model, arm) entries in summary.json.",
  )
  args = parser.parse_args(argv)

  guard = HarnessIntegrityGuard(ROOT_DIR)
  guard.verify(auto_initialize=False)
  composite_sha = guard.compute_composite_sha256()

  run_id = gen5_exposure.new_run_id()
  valset, exposure_entry = gen5_exposure.load_split(
      args.val_split,
      purpose="harness2_gen5_cross_model_transfer",
      model=",".join(args.models),
      run_id=run_id,
  )
  forbidden_literals = load_forbidden_literals(gen5_exposure.MANIFEST_PATH)
  jev_evaluator = JevSocJudgeEvaluator(backend=build_jev_backend("mock"))

  out_dir = (
      Path(args.output_dir)
      if Path(args.output_dir).is_absolute()
      else ROOT_DIR / args.output_dir
  )
  out_dir.mkdir(parents=True, exist_ok=True)
  summary_path = out_dir / "summary.json"
  budget_ledger = BudgetLedger(
      out_dir / "budget_ledger.json",
      limit_usd=float(args.budget_limit_usd),
  )

  existing_by_key: Dict[Tuple[str, str], Dict[str, Any]] = {}
  if args.resume_existing and summary_path.exists():
    try:
      prev = json.loads(summary_path.read_text(encoding="utf-8"))
      for item in prev.get("matrix", []):
        if (
            isinstance(item, dict)
            and item.get("cases_evaluated") == len(valset)
        ):
          existing_by_key[(str(item["model"]), str(item["arm"]))] = item
    except Exception:
      pass

  matrix_results: List[Dict[str, Any]] = []
  for model in args.models:
    for arm_name in args.arms:
      key = (model, arm_name)
      if key in existing_by_key:
        _, word_counts = load_arm_runbooks(arm_name)
        resumed_entry = aggregate_arm_metrics(
            traces=existing_by_key[key]["cases"],
            model=model,
            arm_name=arm_name,
            word_counts=word_counts,
            context_debt_penalty=float(
                existing_by_key[key].get("context_debt_penalty", 0.0)
            ),
        )
        existing_by_key[key] = resumed_entry
        print(
            f"[RESUME] Reusing completed ({model}, {arm_name}): "
            f"Harbor={resumed_entry['harbor_60_20_20']:.4f}, "
            f"GEPA={resumed_entry['gepa_fitness']:.4f}, "
            f"d'={resumed_entry['sdt_metrics']['d_prime']:.2f}, "
            f"Loss=${resumed_entry['operational_loss']['total_loss_usd']:,.2f}"
        )
        matrix_results.append(resumed_entry)
        continue

      runbooks, word_counts = load_arm_runbooks(arm_name)
      debt_pen = compute_w350_context_debt_penalty(runbooks)
      print(
          f"[EVAL] model={model} arm={arm_name} words={sum(word_counts.values())} "
          f"debt_pen={debt_pen:.4f} cases={len(valset)}..."
      )
      t_arm = time.time()
      ordered_traces: List[Optional[Dict[str, Any]]] = [None] * len(valset)
      with ThreadPoolExecutor(max_workers=max(1, args.max_workers)) as pool:
        fut_to_idx = {
            pool.submit(
                evaluate_single_gen5_case,
                case=case,
                candidate=runbooks,
                model=model,
                project_id=args.project_id,
                region=args.region,
                jev_evaluator=jev_evaluator,
                forbidden_literals=forbidden_literals,
                budget_ledger=budget_ledger,
                context_debt_penalty=debt_pen,
            ): idx
            for idx, case in enumerate(valset)
        }
        for fut in as_completed(fut_to_idx):
          idx = fut_to_idx[fut]
          ordered_traces[idx] = fut.result()

      traces = [t for t in ordered_traces if t is not None]
      arm_entry = aggregate_arm_metrics(
          traces=traces,
          model=model,
          arm_name=arm_name,
          word_counts=word_counts,
          context_debt_penalty=debt_pen,
      )
      elapsed_s = time.time() - t_arm
      print(
          f"  -> DONE ({model}, {arm_name}) in {elapsed_s:.1f}s: "
          f"Harbor={arm_entry['harbor_60_20_20']:.4f}, "
          f"GEPA={arm_entry['gepa_fitness']:.4f}, "
          f"d'={arm_entry['sdt_metrics']['d_prime']:.2f}, "
          f"Loss=${arm_entry['operational_loss']['total_loss_usd']:,.2f}"
      )
      matrix_results.append(arm_entry)
      existing_by_key[key] = arm_entry

      partial_payload = {
          "run_id": run_id,
          "val_split": args.val_split,
          "num_cases": len(valset),
          "harness_composite_sha256": composite_sha,
          "exposure": exposure_entry,
          "matrix": matrix_results,
      }
      summary_path.write_text(
          json.dumps(partial_payload, indent=2), encoding="utf-8"
      )

  # Compute 3-model arm aggregates
  arm_aggregates: Dict[str, Any] = {}
  for arm_name in args.arms:
    arm_rows = [r for r in matrix_results if r["arm"] == arm_name]
    if not arm_rows:
      continue
    m = len(arm_rows)
    arm_aggregates[arm_name] = {
        "models_evaluated": m,
        "total_words": arm_rows[0]["total_words"],
        "mean_harbor_60_20_20": round(
            sum(r["harbor_60_20_20"] for r in arm_rows) / m, 4
        ),
        "mean_gepa_fitness": round(
            sum(r["gepa_fitness"] for r in arm_rows) / m, 4
        ),
        "mean_d_prime": round(
            sum(r["sdt_metrics"]["d_prime"] for r in arm_rows) / m, 4
        ),
        "mean_criterion_c": round(
            sum(r["sdt_metrics"]["criterion_c"] for r in arm_rows) / m, 4
        ),
        "mean_total_loss_usd": round(
            sum(r["operational_loss"]["total_loss_usd"] for r in arm_rows) / m,
            2,
        ),
        "mean_tool_calls": round(
            sum(r["mean_tool_calls"] for r in arm_rows) / m, 2
        ),
        "total_safety_violations": sum(
            int(r["safety_violations"]) for r in arm_rows
        ),
    }

  # Execute Cost Staircase walk on harness2_k2_evolved using the evaluated traces
  staircase_tiers = [t for t in DEFAULT_STAIRCASE_TIERS if t in args.models]
  if not staircase_tiers:
    staircase_tiers = list(args.models)

  def _staircase_eval(
      tier: str, cand: Dict[str, str], cases: List[Dict[str, Any]]
  ) -> Tuple[List[float], List[float], Dict[str, Any]]:
    entry = existing_by_key.get((tier, "harness2_k2_evolved"))
    if entry is None:
      raise RuntimeError(
          f"Missing evaluated traces for ({tier}, harness2_k2_evolved)"
      )
    case_traces = entry["cases"]
    sc_list = [float(t["harbor_reward"]) for t in case_traces]
    lp_list = [float(t["loss_penalty"]) for t in case_traces]
    telemetry = {
        "inert": [bool(t.get("inert", False)) for t in case_traces],
        "tokens_in": [
            int((t.get("usage") or {}).get("prompt_tokens") or 0)
            for t in case_traces
        ],
        "tokens_out": [
            int((t.get("usage") or {}).get("completion_tokens") or 0)
            for t in case_traces
        ],
        "latency_ms": [float(t.get("latency_ms") or 0.0) for t in case_traces],
    }
    return sc_list, lp_list, telemetry

  h2_runbooks, _ = load_arm_runbooks("harness2_k2_evolved")
  staircase_report = run_cost_staircase_walk(
      candidate=h2_runbooks,
      eval_cases=valset,
      evaluator_fn=_staircase_eval,
      model_tiers=staircase_tiers,
      tolerance=float(args.cost_tolerance),
  )

  staircase_path = out_dir / "cost_staircase_report.json"
  staircase_path.write_text(
      json.dumps(staircase_report.to_dict(), indent=2), encoding="utf-8"
  )

  # Also copy cost_staircase_report.json to gen5_flash_lite output dir
  gen5_fl_staircase = (
      ROOT_DIR
      / "docs"
      / "soc_eval_results"
      / "harness2_8h_campaign"
      / "gen5_flash_lite"
      / "cost_staircase_report.json"
  )
  gen5_fl_staircase.write_text(
      json.dumps(staircase_report.to_dict(), indent=2), encoding="utf-8"
  )

  full_summary = {
      "run_id": run_id,
      "val_split": args.val_split,
      "num_cases": len(valset),
      "harness_composite_sha256": composite_sha,
      "exposure": exposure_entry,
      "arm_aggregates": arm_aggregates,
      "cost_staircase": staircase_report.to_dict(),
      "budget_spent_usd": budget_ledger.spent_usd,
      "matrix": matrix_results,
  }
  summary_path.write_text(
      json.dumps(full_summary, indent=2), encoding="utf-8"
  )

  scorecard_md = render_markdown_scorecard(full_summary, staircase_report)
  scorecard_path = out_dir / "GEN5_TRANSFER_SCORECARD.md"
  scorecard_path.write_text(scorecard_md, encoding="utf-8")

  guard.verify(auto_initialize=False)
  print(f"Saved Gen 5 transfer summary to {summary_path}")
  print(f"Saved Cost Staircase report to {staircase_path}")
  print(f"Saved Markdown scorecard to {scorecard_path}")
  return 0


if __name__ == "__main__":
  sys.exit(main())
