#!/usr/bin/env python3
"""Continuous 9-hour overnight DSPy Context Engineering experimentation loop for gemma_deploy.

Executes multi-wave A/B ablations, constrained GEPA runbook optimization sweeps,
Harbor 60/20/20 verifier parity checks, and balanced teacher trace harvesting
with a hard USD budget ceiling, auditable decisions.tsv logging, and continuous
MORNING_REPORT.md updates.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
  sys.path.insert(0, str(ROOT_DIR))

from agent.aqua_diagnostics import cluster_trace_diagnoses
from agent.gepa_runbook_optimizer import (
    CORE_RUNBOOKS,
    RunbookGEPAAdapter,
    load_forbidden_literals,
    load_seed_runbooks,
    main as gepa_main,
    validate_runbook_candidate,
)
from agent.hierarchical_soc_agent import (
    HierarchicalSOCTier1Agent,
    strip_runbook_scaffolding,
)
from agent.hillclimb_harness import (
    BudgetExceeded,
    BudgetLedger,
    evaluate_candidate_acceptance,
    filter_balanced_traces,
)
from agent.soc_tier1_agent import extract_soc_decision
from scripts.verify_harbor_soc import compose_soc_reward


DECISIONS_TSV = ROOT_DIR / "decisions.tsv"
LOG_SH = (
    Path.home()
    / ".gemini"
    / "config"
    / "plugins"
    / "pstack"
    / "skills"
    / "show-me-your-work"
    / "scripts"
    / "log.sh"
)


def log_decision(
    phase: str,
    scope: str,
    decision: str,
    rationale: str,
    evidence: str,
    result: str,
) -> None:
  """Append a row to decisions.tsv using show-me-your-work log.sh or atomic TSV fallback."""
  combined_decision = f"[{scope}] {decision}" if scope else decision
  if LOG_SH.exists():
    try:
      subprocess.run(
          [
              str(LOG_SH),
              str(DECISIONS_TSV),
              phase,
              combined_decision,
              rationale,
              evidence,
              result,
          ],
          check=True,
          capture_output=True,
          text=True,
      )
      return
    except Exception:
      pass
  ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
  header = "ts\tphase\tdecision\twhy\tevidence\tresult\n"
  if not DECISIONS_TSV.exists():
    DECISIONS_TSV.write_text(header, encoding="utf-8")
  fields = [ts, phase, combined_decision, rationale, evidence, result]
  clean = [
      str(f).replace("\t", " ").replace("\n", " ").strip() for f in fields
  ]
  with DECISIONS_TSV.open("a", encoding="utf-8") as fh:
    fh.write("\t".join(clean) + "\n")


def load_raw_seed_runbooks() -> Dict[str, str]:
  """Load raw upstream runbooks from third_party/ai-runbooks."""
  return load_seed_runbooks()


def load_clean_seed_runbooks() -> Dict[str, str]:
  """Load de-scaffolded seed runbooks (Mermaid, Cline pseudo-tools, and ${VAR} stripped)."""
  raw = load_seed_runbooks()
  return {
      name: strip_runbook_scaffolding(text, normalize_template_vars=True)
      for name, text in raw.items()
  }


def evaluate_candidate_with_harbor_parity(
    candidate: Dict[str, str],
    cases: List[Dict[str, Any]],
    task_lm: str,
    budget_ledger: BudgetLedger,
    normalize_scaffolding: bool = True,
    max_iterations: int = 5,
) -> Dict[str, Any]:
  """Evaluate a runbook candidate on a case bundle and compute both GEPA fitness and Harbor 60/20/20 reward."""
  import importlib
  import agent.hierarchical_soc_agent as hsa_mod
  importlib.reload(hsa_mod)

  def _agent_factory(**kwargs: Any) -> Any:
    return hsa_mod.HierarchicalSOCTier1Agent(**kwargs)

  adapter = RunbookGEPAAdapter(
      task_lm=task_lm,
      max_iterations=max_iterations,
      agent_factory=_agent_factory,
      seed_candidate=candidate,
      budget_ledger=budget_ledger,
  )
  batch = adapter.evaluate(cases, candidate, capture_traces=True)
  traces = list(batch.trajectories or [])
  outputs = list(batch.outputs or [])
  fitness_scores = [float(x) for x in (batch.scores or [])]

  harbor_rewards: List[float] = []
  harbor_breakdowns: List[Dict[str, Any]] = []
  for idx, case in enumerate(cases):
    tr = traces[idx] if idx < len(traces) else {}
    out_text = outputs[idx] if idx < len(outputs) else ""
    dec_obj = extract_soc_decision(out_text)
    dec_dict = {
        "verdict": getattr(dec_obj, "verdict", None) or tr.get("actual_verdict", ""),
        "recommended_actions": (
            getattr(dec_obj, "recommended_actions", None)
            or tr.get("executed_actions", [])
        ),
    }
    reward_info = compose_soc_reward(
        case=case,
        trajectory=tr.get("trajectory", []),
        report_text=out_text,
        decision_data=dec_dict,
        jev_backend_name="mock",
    )
    harbor_rewards.append(float(reward_info.get("reward", 0.0)))
    harbor_breakdowns.append(reward_info)
    tr["harbor_reward"] = float(reward_info.get("reward", 0.0))

  mean_fitness = (
      sum(fitness_scores) / len(fitness_scores) if fitness_scores else 0.0
  )
  mean_harbor = (
      sum(harbor_rewards) / len(harbor_rewards) if harbor_rewards else 0.0
  )
  zero_tool_count = sum(1 for t in traces if t.get("zero_tool_hesitation"))
  inert_count = sum(1 for t in traces if t.get("inert"))
  safety_violations = sum(1 for t in traces if t.get("safety_gate_triggered"))
  mean_loss_penalty = (
      sum(float(t.get("loss_penalty", 1.0)) for t in traces) / len(traces)
      if traces
      else 1.0
  )

  by_verdict: Dict[str, List[float]] = {}
  for t in traces:
    v = str(t.get("expected_verdict", "UNKNOWN")).upper()
    by_verdict.setdefault(v, []).append(float(t.get("harbor_reward", t.get("score", 0.0))))
  verdict_means = {
      k: round(sum(vals) / len(vals), 4) for k, vals in sorted(by_verdict.items()) if vals
  }

  total_words = sum(len(str(text).split()) for text in candidate.values())

  return {
      "task_lm": task_lm,
      "case_count": len(cases),
      "total_words": total_words,
      "mean_gepa_fitness": round(mean_fitness, 4),
      "mean_harbor_reward": round(mean_harbor, 4),
      "mean_loss_penalty": round(mean_loss_penalty, 4),
      "zero_tool_count": zero_tool_count,
      "inert_count": inert_count,
      "safety_violations": safety_violations,
      "verdict_harbor_means": verdict_means,
      "traces": traces,
  }


def check_zero_gpu_endpoints() -> Dict[str, Any]:
  """Verify zero dedicated Vertex AI GPU endpoints are running to prevent overnight billing leaks."""
  project_id = (
      os.environ.get("PROJECT_ID")
      or os.environ.get("GCP_PROJECT_ID")
      or os.environ.get("GOOGLE_CLOUD_PROJECT")
      or ""
  )
  region = os.environ.get("REGION", "us-central1")
  if not project_id:
    return {"checked": False, "active_endpoints": 0, "status": "no_project_id"}
  try:
    proc = subprocess.run(
        [
            "gcloud",
            "ai",
            "endpoints",
            "list",
            f"--project={project_id}",
            f"--region={region}",
            "--format=json",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if proc.returncode != 0:
      return {
          "checked": True,
          "active_endpoints": 0,
          "status": "gcloud_non_zero",
      }
    endpoints = json.loads(proc.stdout or "[]")
    deployed = [
        ep.get("displayName", ep.get("name", "unknown"))
        for ep in endpoints
        if ep.get("deployedModels")
    ]
    return {
        "checked": True,
        "active_endpoints": len(deployed),
        "deployed_names": deployed,
        "status": "OK" if not deployed else "WARNING_ACTIVE_ENDPOINT",
    }
  except Exception as exc:
    return {"checked": False, "active_endpoints": 0, "status": f"err:{exc}"}


def write_morning_report(
    output_dir: Path,
    summary_state: Dict[str, Any],
    budget_ledger: BudgetLedger,
) -> Path:
  """Generate or update MORNING_REPORT.md and campaign_summary.json."""
  output_dir.mkdir(parents=True, exist_ok=True)
  summary_state["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
  summary_state["budget"] = {
      "limit_usd": budget_ledger.limit_usd,
      "spent_usd": round(budget_ledger.spent_usd, 4),
      "remaining_usd": round(budget_ledger.remaining_usd, 4),
  }
  summary_path = output_dir / "campaign_summary.json"
  summary_path.write_text(
      json.dumps(summary_state, indent=2), encoding="utf-8"
  )

  lines: List[str] = [
      "# Overnight DSPy Context Engineering Campaign Report",
      "",
      f"- **Updated (UTC)**: `{summary_state['updated_at_utc']}`",
      f"- **Elapsed Hours**: `{summary_state.get('elapsed_hours', 0.0):.2f}h` / `{summary_state.get('target_hours', 9.0):.2f}h`",
      f"- **Budget Spent**: `${budget_ledger.spent_usd:.4f}` / `${budget_ledger.limit_usd:.2f}` (`${budget_ledger.remaining_usd:.4f}` remaining)",
      f"- **Completed Experiments**: `{len(summary_state.get('experiments', []))}`",
      f"- **Balanced SFT Traces Harvested**: `{summary_state.get('balanced_trace_count', 0)}`",
      f"- **Vertex AI GPU Endpoint Audit**: `{summary_state.get('gpu_audit', {}).get('status', 'unchecked')}` (active endpoints: `{summary_state.get('gpu_audit', {}).get('active_endpoints', 0)}`)",
      "",
      "## 1. Experiment Leaderboard (Sorted by Harbor 60/20/20 Reward)",
      "",
      "| Exp ID | Wave | Dataset | Task Model | Max Words | Total Words | GEPA Fitness | Harbor 60/20/20 | Zero-Tool | Safety Viol | Status |",
      "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
  ]

  exps = sorted(
      summary_state.get("experiments", []),
      key=lambda x: (
          str(x.get("dataset", "")),
          float(x.get("mean_harbor_reward", 0.0)),
          -int(x.get("total_words", 2376)),
      ),
      reverse=True,
  )
  for exp in exps:
    lines.append(
        f"| `{exp.get('exp_id')}` | {exp.get('wave')} | `{exp.get('dataset')}` | "
        f"`{exp.get('task_lm')}` | `{exp.get('max_words', 'none')}` | "
        f"`{exp.get('total_words', 2376)}` | "
        f"`{exp.get('mean_gepa_fitness', 0.0):.4f}` | "
        f"`{exp.get('mean_harbor_reward', 0.0):.4f}` | "
        f"`{exp.get('zero_tool_count', 0)}` | "
        f"`{exp.get('safety_violations', 0)}` | "
        f"`{exp.get('status', 'DONE')}` |"
    )

  lines.extend([
      "",
      "## 2. Per-Verdict Harbor Reward Breakdown",
      "",
      "| Exp ID | Dataset | Task Model | MALICIOUS | BENIGN | SUSPICIOUS | INCONCLUSIVE |",
      "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
  ])
  for exp in exps:
    vm = exp.get("verdict_harbor_means", {}) or {}
    lines.append(
        f"| `{exp.get('exp_id')}` | `{exp.get('dataset')}` | `{exp.get('task_lm')}` | "
        f"`{vm.get('MALICIOUS', '-')}` | `{vm.get('BENIGN', '-')}` | "
        f"`{vm.get('SUSPICIOUS', '-')}` | `{vm.get('INCONCLUSIVE', '-')}` |"
    )

  if summary_state.get("best_runbooks_dir"):
    lines.extend([
        "",
        "## 3. Best Promoted Runbook Candidate",
        "",
        f"- **Directory**: `{summary_state['best_runbooks_dir']}`",
        f"- **Best Gen 5 Validation Harbor Reward**: `{summary_state.get('best_gen5_harbor_reward', 0.0):.4f}`",
        f"- **Best Gen 3 Interactive Harbor Reward**: `{summary_state.get('best_gen3_harbor_reward', 0.0):.4f}`",
    ])

  report_path = output_dir / "MORNING_REPORT.md"
  report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
  return report_path


def main(argv: Optional[List[str]] = None) -> int:
  parser = argparse.ArgumentParser(
      description="Run continuous 9-hour DSPy Context Engineering experimentation campaign."
  )
  parser.add_argument(
      "--hours",
      type=float,
      default=9.0,
      help="Total wall-clock duration in hours for continuous experimentation (default: 9.0).",
  )
  parser.add_argument(
      "--budget-limit-usd",
      type=float,
      default=20.0,
      help="Hard USD spend ceiling enforced across all waves (default: 20.0).",
  )
  parser.add_argument(
      "--output-dir",
      type=str,
      default="docs/soc_eval_results/dspy_overnight",
      help="Campaign output directory (default: docs/soc_eval_results/dspy_overnight).",
  )
  args = parser.parse_args(argv)

  out_dir = (
      Path(args.output_dir)
      if Path(args.output_dir).is_absolute()
      else ROOT_DIR / args.output_dir
  )
  out_dir.mkdir(parents=True, exist_ok=True)

  # Isolate exploratory Gen 5 exposure ledger inside campaign output directory
  os.environ["GEN5_EXPOSURE_LEDGER"] = str(out_dir / "exploratory_exposure.jsonl")

  budget_ledger = BudgetLedger(
      out_dir / "global_budget_ledger.json",
      limit_usd=float(args.budget_limit_usd),
  )

  gen3_path = ROOT_DIR / "configs" / "evals" / "gen3" / "soc_tier1_interactive.json"
  gen5_val_path = ROOT_DIR / "configs" / "evals" / "gen5" / "validation.json"
  gen3_cases = json.loads(gen3_path.read_text(encoding="utf-8")).get("eval_cases", [])
  gen5_val_cases = json.loads(gen5_val_path.read_text(encoding="utf-8")).get("eval_cases", [])

  start_ts = time.time()
  deadline_ts = start_ts + float(args.hours) * 3600.0

  summary_state: Dict[str, Any] = {
      "started_at_utc": datetime.now(timezone.utc).isoformat(),
      "target_hours": float(args.hours),
      "elapsed_hours": 0.0,
      "experiments": [],
      "balanced_trace_count": 0,
      "best_gen5_harbor_reward": 0.0,
      "best_gen3_harbor_reward": 0.0,
      "best_runbooks_dir": None,
      "gpu_audit": check_zero_gpu_endpoints(),
  }
  all_harvested_traces: List[Dict[str, Any]] = []
  existing_summary_path = out_dir / "campaign_summary.json"
  if existing_summary_path.exists():
    try:
      loaded_summary = json.loads(existing_summary_path.read_text(encoding="utf-8"))
      if isinstance(loaded_summary, dict) and isinstance(loaded_summary.get("experiments"), list):
        summary_state.update(loaded_summary)
    except Exception:
      pass
  existing_sft_path = out_dir / "balanced_sft_traces.jsonl"
  if existing_sft_path.exists():
    try:
      for line in existing_sft_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
          all_harvested_traces.append(json.loads(line))
    except Exception:
      pass
  completed_exp_ids = {
      str(e.get("exp_id")) for e in summary_state.get("experiments", []) if e.get("exp_id")
  }

  def _record_exp(exp_record: Dict[str, Any], traces: List[Dict[str, Any]]) -> None:
    all_harvested_traces.extend(traces)
    summary_state["experiments"].append(exp_record)
    summary_state["elapsed_hours"] = (time.time() - start_ts) / 3600.0
    summary_state["gpu_audit"] = check_zero_gpu_endpoints()
    try:
      balanced = filter_balanced_traces(
          all_harvested_traces, min_examples_per_class=1, min_score=0.80
      )
      summary_state["balanced_trace_count"] = len(balanced)
      sft_path = out_dir / "balanced_sft_traces.jsonl"
      with sft_path.open("w", encoding="utf-8") as fh:
        for row in balanced:
          fh.write(json.dumps(row) + "\n")
    except ValueError:
      pass
    write_morning_report(out_dir, summary_state, budget_ledger)

  try:
    # =========================================================================
    # WAVE 1: Clean Seed Runbooks Baseline across Gen 3 & Gen 5 Validation
    # =========================================================================
    clean_seed = load_clean_seed_runbooks()
    clean_seed_dir = out_dir / "candidates" / "wave1_clean_seed"
    clean_seed_dir.mkdir(parents=True, exist_ok=True)
    for rname, rtext in clean_seed.items():
      (clean_seed_dir / rname).write_text(rtext, encoding="utf-8")

    for model_name in ("gemini-2.5-flash-lite", "gemini-2.5-flash"):
      if time.time() >= deadline_ts:
        break
      budget_ledger.assert_can_spend()

      # 1A. Gen 3 evaluation
      exp_id_g3 = f"w1_clean_seed_gen3_{model_name.replace('.', '_')}"
      if exp_id_g3 not in completed_exp_ids:
        print(f"[Wave 1] Running {exp_id_g3}...", flush=True)
        res_g3 = evaluate_candidate_with_harbor_parity(
            candidate=clean_seed,
            cases=gen3_cases,
            task_lm=model_name,
            budget_ledger=budget_ledger,
        )
        traces_g3 = res_g3.pop("traces", [])
        if res_g3["mean_harbor_reward"] > summary_state["best_gen3_harbor_reward"]:
          summary_state["best_gen3_harbor_reward"] = res_g3["mean_harbor_reward"]
          if summary_state["best_runbooks_dir"] is None:
            summary_state["best_runbooks_dir"] = str(clean_seed_dir)
        _record_exp(
            {
                "exp_id": exp_id_g3,
                "wave": "Wave 1 (Context Hygiene Seed)",
                "dataset": "gen3_10",
                "max_words": "clean_seed",
                "status": "BASELINE",
                **res_g3,
            },
            traces_g3,
        )
        completed_exp_ids.add(exp_id_g3)
        log_decision(
            "result",
            exp_id_g3,
            f"Evaluated de-scaffolded seed runbooks on Gen 3 with {model_name}",
            "Measure baseline Harbor 60/20/20 reward after stripping Mermaid and ${VAR} scaffolding",
            f"gepa_fitness={res_g3['mean_gepa_fitness']:.4f}, harbor_reward={res_g3['mean_harbor_reward']:.4f}, zero_tool={res_g3['zero_tool_count']}",
            "baseline_recorded",
        )

      # 1B. Gen 5 validation evaluation
      if time.time() >= deadline_ts:
        break
      budget_ledger.assert_can_spend()
      exp_id_g5 = f"w1_clean_seed_gen5val_{model_name.replace('.', '_')}"
      if exp_id_g5 not in completed_exp_ids:
        print(f"[Wave 1] Running {exp_id_g5}...", flush=True)
        res_g5 = evaluate_candidate_with_harbor_parity(
            candidate=clean_seed,
            cases=gen5_val_cases,
            task_lm=model_name,
            budget_ledger=budget_ledger,
        )
        traces_g5 = res_g5.pop("traces", [])
        if res_g5["mean_harbor_reward"] > summary_state["best_gen5_harbor_reward"]:
          summary_state["best_gen5_harbor_reward"] = res_g5["mean_harbor_reward"]
          summary_state["best_runbooks_dir"] = str(clean_seed_dir)
        _record_exp(
            {
                "exp_id": exp_id_g5,
                "wave": "Wave 1 (Context Hygiene Seed)",
                "dataset": "gen5_val_20",
                "max_words": "clean_seed",
                "status": "BASELINE",
                **res_g5,
            },
            traces_g5,
        )
        completed_exp_ids.add(exp_id_g5)
        log_decision(
            "result",
            exp_id_g5,
            f"Evaluated de-scaffolded seed runbooks on Gen 5 validation with {model_name}",
            "Establish Gen 5 validation baseline with de-scaffolded runbooks",
            f"gepa_fitness={res_g5['mean_gepa_fitness']:.4f}, harbor_reward={res_g5['mean_harbor_reward']:.4f}, zero_tool={res_g5['zero_tool_count']}",
            "baseline_recorded",
        )

      # 1C. Re-evaluate Clean Seed v2 (with temperature=0.0, 1500-char observation window, and Gen 5 target resolution)
      exp_id_g3_v2 = f"w1b_clean_seed_v2_gen3_{model_name.replace('.', '_')}"
      if exp_id_g3_v2 not in completed_exp_ids:
        print(f"[Wave 1B] Running {exp_id_g3_v2}...", flush=True)
        res_g3_v2 = evaluate_candidate_with_harbor_parity(
            candidate=clean_seed,
            cases=gen3_cases,
            task_lm=model_name,
            budget_ledger=budget_ledger,
        )
        traces_g3_v2 = res_g3_v2.pop("traces", [])
        if res_g3_v2["mean_harbor_reward"] > summary_state["best_gen3_harbor_reward"]:
          summary_state["best_gen3_harbor_reward"] = res_g3_v2["mean_harbor_reward"]
        _record_exp(
            {
                "exp_id": exp_id_g3_v2,
                "wave": "Wave 1B (Context Hygiene + Temp0 + 1500c)",
                "dataset": "gen3_10",
                "max_words": "clean_seed_v2",
                "status": "BASELINE_V2",
                **res_g3_v2,
            },
            traces_g3_v2,
        )
        completed_exp_ids.add(exp_id_g3_v2)
        log_decision(
            "result",
            exp_id_g3_v2,
            f"Evaluated Clean Seed v2 (temp=0.0, 1500-char obs, target resolution) on Gen 3 with {model_name}",
            "Measure baseline lift from temperature=0.0 + 1500-char observation window + Gen 5 target resolution",
            f"gepa_fitness={res_g3_v2['mean_gepa_fitness']:.4f}, harbor_reward={res_g3_v2['mean_harbor_reward']:.4f}, zero_tool={res_g3_v2['zero_tool_count']}",
            "baseline_v2_recorded",
        )

      exp_id_g5_v2 = f"w1b_clean_seed_v2_gen5val_{model_name.replace('.', '_')}"
      if exp_id_g5_v2 not in completed_exp_ids:
        print(f"[Wave 1B] Running {exp_id_g5_v2}...", flush=True)
        res_g5_v2 = evaluate_candidate_with_harbor_parity(
            candidate=clean_seed,
            cases=gen5_val_cases,
            task_lm=model_name,
            budget_ledger=budget_ledger,
        )
        traces_g5_v2 = res_g5_v2.pop("traces", [])
        if res_g5_v2["mean_harbor_reward"] > summary_state["best_gen5_harbor_reward"]:
          summary_state["best_gen5_harbor_reward"] = res_g5_v2["mean_harbor_reward"]
          summary_state["best_runbooks_dir"] = str(clean_seed_dir)
        _record_exp(
            {
                "exp_id": exp_id_g5_v2,
                "wave": "Wave 1B (Context Hygiene + Temp0 + 1500c)",
                "dataset": "gen5_val_20",
                "max_words": "clean_seed_v2",
                "status": "BASELINE_V2",
                **res_g5_v2,
            },
            traces_g5_v2,
        )
        completed_exp_ids.add(exp_id_g5_v2)
        log_decision(
            "result",
            exp_id_g5_v2,
            f"Evaluated Clean Seed v2 (temp=0.0, 1500-char obs, compose_soc_reward) on Gen 5 validation with {model_name}",
            "Measure Gen 5 validation baseline lift from temperature=0.0 + 1500-char observation window + compose_soc_reward",
            f"gepa_fitness={res_g5_v2['mean_gepa_fitness']:.4f}, harbor_reward={res_g5_v2['mean_harbor_reward']:.4f}, zero_tool={res_g5_v2['zero_tool_count']}",
            "baseline_v2_recorded",
        )

      # 1D. Re-evaluate Clean Seed v3 (with report assertion hygiene + Gen 3 case resolution)
      exp_id_g3_v3 = f"w1c_clean_seed_v3_gen3_{model_name.replace('.', '_')}"
      if exp_id_g3_v3 not in completed_exp_ids:
        print(f"[Wave 1C] Running {exp_id_g3_v3}...", flush=True)
        res_g3_v3 = evaluate_candidate_with_harbor_parity(
            candidate=clean_seed,
            cases=gen3_cases,
            task_lm=model_name,
            budget_ledger=budget_ledger,
        )
        traces_g3_v3 = res_g3_v3.pop("traces", [])
        if res_g3_v3["mean_harbor_reward"] > summary_state["best_gen3_harbor_reward"]:
          summary_state["best_gen3_harbor_reward"] = res_g3_v3["mean_harbor_reward"]
        _record_exp(
            {
                "exp_id": exp_id_g3_v3,
                "wave": "Wave 1C (Assertion Hygiene + Gen3 Case Resolution)",
                "dataset": "gen3_10",
                "max_words": "clean_seed_v3",
                "status": "BASELINE_V3",
                **res_g3_v3,
            },
            traces_g3_v3,
        )
        completed_exp_ids.add(exp_id_g3_v3)
        log_decision(
            "result",
            exp_id_g3_v3,
            f"Evaluated Clean Seed v3 (assertion hygiene + Gen 3 case resolution) on Gen 3 with {model_name}",
            "Measure Gen 3 lift from resolving default SOAR case IDs on CMDB alerts and sanitizing negated substring collisions",
            f"gepa_fitness={res_g3_v3['mean_gepa_fitness']:.4f}, harbor_reward={res_g3_v3['mean_harbor_reward']:.4f}, zero_tool={res_g3_v3['zero_tool_count']}",
            "baseline_v3_recorded",
        )

      exp_id_g5_v3 = f"w1c_clean_seed_v3_gen5val_{model_name.replace('.', '_')}"
      if exp_id_g5_v3 not in completed_exp_ids:
        print(f"[Wave 1C] Running {exp_id_g5_v3}...", flush=True)
        res_g5_v3 = evaluate_candidate_with_harbor_parity(
            candidate=clean_seed,
            cases=gen5_val_cases,
            task_lm=model_name,
            budget_ledger=budget_ledger,
        )
        traces_g5_v3 = res_g5_v3.pop("traces", [])
        if res_g5_v3["mean_harbor_reward"] > summary_state["best_gen5_harbor_reward"]:
          summary_state["best_gen5_harbor_reward"] = res_g5_v3["mean_harbor_reward"]
          summary_state["best_runbooks_dir"] = str(clean_seed_dir)
        _record_exp(
            {
                "exp_id": exp_id_g5_v3,
                "wave": "Wave 1C (Assertion Hygiene + Gen3 Case Resolution)",
                "dataset": "gen5_val_20",
                "max_words": "clean_seed_v3",
                "status": "BASELINE_V3",
                **res_g5_v3,
            },
            traces_g5_v3,
        )
        completed_exp_ids.add(exp_id_g5_v3)
        log_decision(
            "result",
            exp_id_g5_v3,
            f"Evaluated Clean Seed v3 (assertion hygiene + active SOAR case notes) on Gen 5 validation with {model_name}",
            "Measure Gen 5 validation lift from report assertion hygiene and active SOAR case note inclusion",
            f"gepa_fitness={res_g5_v3['mean_gepa_fitness']:.4f}, harbor_reward={res_g5_v3['mean_harbor_reward']:.4f}, zero_tool={res_g5_v3['zero_tool_count']}",
            "baseline_v3_recorded",
        )

    # 1E. Re-evaluate promoted GEPA candidates with clean_seed hygiene + v3 fixes
    promoted_rechecks = [
        (
            "r1_gepa_gen3_gemini-2_5-flash_w450_s42",
            "gemini-2.5-flash",
            "450",
        ),
        (
            "r1_gepa_gen3_gemini-2_5-flash-lite_w550_s202",
            "gemini-2.5-flash-lite",
            "550",
        ),
    ]
    for src_exp_id, model_name, max_w_label in promoted_rechecks:
      src_dir = out_dir / "candidates" / src_exp_id
      if not src_dir.exists():
        continue
      recheck_exp_id = f"{src_exp_id}_v3_hygiene"
      if recheck_exp_id in completed_exp_ids:
        continue
      hygienic_cand: Dict[str, str] = {}
      recheck_dir = out_dir / "candidates" / recheck_exp_id
      recheck_dir.mkdir(parents=True, exist_ok=True)
      for name in CORE_RUNBOOKS:
        p = src_dir / name
        raw_txt = p.read_text(encoding="utf-8") if p.exists() else clean_seed[name]
        cleaned_txt = strip_runbook_scaffolding(
            raw_txt, normalize_template_vars=True
        )
        hygienic_cand[name] = cleaned_txt
        (recheck_dir / name).write_text(cleaned_txt, encoding="utf-8")

      print(f"[Wave 1C] Running {recheck_exp_id}...", flush=True)
      res_recheck = evaluate_candidate_with_harbor_parity(
          candidate=hygienic_cand,
          cases=gen3_cases,
          task_lm=model_name,
          budget_ledger=budget_ledger,
      )
      traces_recheck = res_recheck.pop("traces", [])
      if res_recheck["mean_harbor_reward"] > summary_state["best_gen3_harbor_reward"]:
        summary_state["best_gen3_harbor_reward"] = res_recheck["mean_harbor_reward"]
        summary_state["best_runbooks_dir"] = str(recheck_dir)
      _record_exp(
          {
              "exp_id": recheck_exp_id,
              "wave": "Wave 2/3 (GEPA+Harbor r1 + v3 Hygiene)",
              "dataset": "gen3_10",
              "max_words": max_w_label,
              "status": "PROMOTED",
              **res_recheck,
          },
          traces_recheck,
      )
      completed_exp_ids.add(recheck_exp_id)
      log_decision(
          "promotion",
          recheck_exp_id,
          f"Re-evaluated promoted GEPA candidate {src_exp_id} with strip_runbook_scaffolding on unmutated files and v3 case resolution",
          "Combine GEPA-evolved runbook instructions with clean_seed hygiene on untouched runbooks and Gen 3 CMDB case resolution",
          f"words={res_recheck['total_words']}, gepa_fitness={res_recheck['mean_gepa_fitness']:.4f}, harbor_reward={res_recheck['mean_harbor_reward']:.4f}",
          "promoted_v3_hygiene",
      )

    # =========================================================================
    # WAVE 2 & 3: Continuous Constrained GEPA Sweeps + Harbor Parity Audits
    # =========================================================================
    # Structured curriculum of (dataset_mode, task_lm, max_words, seed, max_metric_calls)
    sweep_configs: List[Tuple[str, str, int, int, int]] = [
        ("gen3", "gemini-2.5-flash-lite", 450, 42, 55),
        ("gen5", "gemini-2.5-flash-lite", 450, 42, 100),
        ("gen3", "gemini-2.5-flash-lite", 350, 101, 55),
        ("gen5", "gemini-2.5-flash-lite", 350, 101, 100),
        ("gen3", "gemini-2.5-flash", 450, 42, 55),
        ("gen5", "gemini-2.5-flash", 450, 42, 100),
        ("gen3", "gemini-2.5-flash-lite", 550, 202, 55),
        ("gen5", "gemini-2.5-flash-lite", 550, 202, 100),
        ("gen3", "gemini-2.5-flash", 350, 101, 55),
        ("gen5", "gemini-2.5-flash", 350, 101, 100),
        ("gen5", "gemini-2.5-flash-lite", 400, 303, 100),
        ("gen5", "gemini-2.5-flash", 400, 303, 100),
    ]

    round_num = 1
    while time.time() < deadline_ts:
      for ds_mode, task_lm, max_words, seed_val, metric_calls in sweep_configs:
        if time.time() >= deadline_ts:
          break
        budget_ledger.assert_can_spend(reserve_usd=0.25)

        actual_seed = seed_val + (round_num - 1) * 1000
        exp_id = (
            f"r{round_num}_gepa_{ds_mode}_{task_lm.replace('.', '_')}"
            f"_w{max_words}_s{actual_seed}"
        )
        if exp_id in completed_exp_ids:
          continue
        cand_out_dir = out_dir / "candidates" / exp_id
        cand_out_dir.mkdir(parents=True, exist_ok=True)

        gepa_args = [
            "--task-lm",
            task_lm,
            "--reflection-lm",
            "gemini-2.5-pro",
            "--max-metric-calls",
            str(metric_calls),
            "--seed",
            str(actual_seed),
            "--noise-runs",
            "0",
            "--min-delta",
            "0.005",
            "--max-words",
            str(max_words),
            "--forbid-template-vars",
            "--forbid-mermaid",
            "--forbid-pseudotools",
            "--no-freeze-passing-runbooks",
            "--budget-limit-usd",
            str(round(budget_ledger.remaining_usd, 2)),
            "--output-dir",
            str(cand_out_dir),
        ]
        if ds_mode == "gen3":
          gepa_args.extend([
              "--evalset",
              str(gen3_path),
              "--split-train-val",
          ])
        else:
          gepa_args.extend([
              "--train-split",
              "train",
              "--val-split",
              "validation",
          ])

        print(f"[Wave 2] Running GEPA optimization {exp_id}...", flush=True)
        rc = gepa_main(gepa_args)

        # Load sub-ledger spend into global budget ledger
        sub_budget_file = cand_out_dir / "budget_ledger.json"
        if sub_budget_file.exists():
          try:
            sub_data = json.loads(sub_budget_file.read_text(encoding="utf-8"))
            sub_spent = float(sub_data.get("spent_usd", 0.0))
            if sub_spent > 0:
              budget_ledger.record(
                  run_key=exp_id,
                  delta_usd=sub_spent,
                  meta={"wave": "Wave 2 GEPA", "rc": rc},
              )
          except Exception:
            pass

        # Load evolved runbooks if written, else clean_seed
        evolved_candidate: Dict[str, str] = {}
        wrote_evolved = all((cand_out_dir / name).exists() for name in CORE_RUNBOOKS)
        if wrote_evolved:
          for name in CORE_RUNBOOKS:
            evolved_candidate[name] = (cand_out_dir / name).read_text(encoding="utf-8")
        else:
          evolved_candidate = dict(clean_seed)

        # Wave 3: Evaluate on full target dataset with Harbor 60/20/20 parity
        target_cases = gen3_cases if ds_mode == "gen3" else gen5_val_cases
        ds_label = "gen3_10" if ds_mode == "gen3" else "gen5_val_20"
        parity_res = evaluate_candidate_with_harbor_parity(
            candidate=evolved_candidate,
            cases=target_cases,
            task_lm=task_lm,
            budget_ledger=budget_ledger,
        )
        traces = parity_res.pop("traces", [])
        status_label = "PROMOTED" if wrote_evolved else "SEED_RETAINED"

        if (
            ds_mode == "gen5"
            and parity_res["zero_tool_count"] == 0
            and parity_res["safety_violations"] == 0
            and (
                parity_res["mean_harbor_reward"] > summary_state["best_gen5_harbor_reward"]
                or (
                    wrote_evolved
                    and parity_res["mean_harbor_reward"] >= summary_state["best_gen5_harbor_reward"] - 0.0025
                    and parity_res.get("total_words", 1845) < int(summary_state.get("best_runbooks_total_words", 1845))
                )
            )
        ):
          if parity_res["mean_harbor_reward"] > summary_state["best_gen5_harbor_reward"]:
            summary_state["best_gen5_harbor_reward"] = parity_res["mean_harbor_reward"]
          summary_state["best_runbooks_dir"] = str(cand_out_dir if wrote_evolved else clean_seed_dir)
          summary_state["best_runbooks_total_words"] = int(parity_res.get("total_words", 1845))
          best_dest = out_dir / "best_promoted_runbooks"
          best_dest.mkdir(parents=True, exist_ok=True)
          for name, text in evolved_candidate.items():
            (best_dest / name).write_text(text, encoding="utf-8")

        _record_exp(
            {
                "exp_id": exp_id,
                "wave": f"Wave 2/3 (GEPA+Harbor r{round_num})",
                "dataset": ds_label,
                "max_words": max_words,
                "status": status_label,
                **parity_res,
            },
            traces,
        )
        completed_exp_ids.add(exp_id)
        log_decision(
            "result",
            exp_id,
            f"Completed constrained GEPA + Harbor parity on {ds_label} ({task_lm}, max_words={max_words})",
            f"WordLimitReflectionLM(max_words={max_words}) + anti-scaffolding validators",
            f"status={status_label}, gepa_fitness={parity_res['mean_gepa_fitness']:.4f}, harbor_reward={parity_res['mean_harbor_reward']:.4f}, spent=${budget_ledger.spent_usd:.4f}",
            status_label.lower(),
        )
      round_num += 1

  except BudgetExceeded as exc:
    print(f"[Budget Guardrail] Stopping cleanly: {exc}", flush=True)
    log_decision(
        "finding",
        "BudgetLedger",
        "Halted overnight loop cleanly at hard USD budget cap",
        str(exc),
        f"spent_usd=${budget_ledger.spent_usd:.4f}",
        "budget_cap_reached",
    )
  except Exception as exc:
    import traceback
    traceback.print_exc()
    log_decision(
        "finding",
        "OvernightLoop",
        f"Exception in overnight loop: {type(exc).__name__}",
        str(exc),
        f"spent_usd=${budget_ledger.spent_usd:.4f}",
        "error_logged",
    )

  summary_state["elapsed_hours"] = (time.time() - start_ts) / 3600.0
  summary_state["gpu_audit"] = check_zero_gpu_endpoints()
  report_path = write_morning_report(out_dir, summary_state, budget_ledger)
  print(f"Overnight campaign report written to {report_path}", flush=True)
  return 0


if __name__ == "__main__":
  sys.exit(main())
