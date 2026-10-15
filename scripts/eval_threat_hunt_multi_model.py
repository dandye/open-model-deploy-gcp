#!/usr/bin/env python3
"""Multi-Model x 3-Arm Evaluation Runner for Track 2 Proactive Threat Hunting & GTI Sweeps.

Evaluates the Hierarchical SOC Agent across multiple Vertex AI models and three runbook
arms on the 4-scenario "Unwrapping Ursnif's Gifts" threat-hunting suite:
  1. no_runbook: Generic multi-agent investigation with no procedural runbook.
  2. raw_clinerules_hunt: Upstream third_party/ai-runbooks/.clinerules/run_books/investigate_a_gti_collection_id.md
     (with unstripped Mermaid sequenceDiagram, ${COLLECTION_ID} placeholders, Cline pseudo-tools,
     and 13-relationship loop).
  3. compressed_track_b_hunt: Authored 350-word Track 2 Proactive Threat Hunting runbook
     (configs/runbooks/gti_collection_threat_hunt.md) enforcing 72h->168h horizon widening,
     second-hop communicating_files pivoting, and signed OS LOLBin filtering.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
  sys.path.insert(0, str(ROOT_DIR))

from agent.hierarchical_soc_agent import HierarchicalSOCTier1Agent
from agent.soc_tier1_agent import extract_soc_decision
from agent.threat_hunt_environment import (
    BENIGN_NGINX_HTML_SHA256,
    LOLBIN_RUNDLL32_SHA256,
    PATIENT_ZERO_HOST,
    ThreatHuntEnvironment,
    URSNIF_DLL_SHA256,
    URSNIF_PAYLOAD_SHA256,
)
from scripts.verify_harbor_soc import compose_soc_reward


DEFAULT_SUITE_PATH = (
    ROOT_DIR / "configs" / "evals" / "hunt" / "ursnif_gti_hunt_suite.json"
)
RAW_CLINERULES_HUNT_PATH = (
    ROOT_DIR
    / "third_party"
    / "ai-runbooks"
    / ".clinerules"
    / "run_books"
    / "investigate_a_gti_collection_id.md"
)
COMPRESSED_TRACK_B_HUNT_PATH = (
    ROOT_DIR / "configs" / "runbooks" / "gti_collection_threat_hunt.md"
)
DEFAULT_OUTPUT_DIR = ROOT_DIR / "results" / "threat_hunt_multi_model"

DEFAULT_MODELS = [
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-3.5-flash-lite",
    "gemini-3-flash-preview",
    "gemini-3.1-pro-preview",
]

DEFAULT_ARMS = [
    "no_runbook",
    "raw_clinerules_hunt",
    "compressed_track_b_hunt",
]


def analyze_hunt_trajectory(
    case: Dict[str, Any],
    trajectory: List[Dict[str, Any]],
    report_text: str,
    actual_verdict: str,
    harbor_breakdown: Dict[str, Any],
) -> Dict[str, Any]:
  """Computes Track 2 Threat-Hunt specific telemetry metrics from an agent trajectory."""
  eval_id = str(case.get("eval_id", ""))
  expected_verdict = str(
      case.get("ground_truth_label")
      or (case.get("reference") or {}).get("expected_verdict")
      or ""
  ).upper()
  verdict_ok = actual_verdict.upper() == expected_verdict

  widened_168h = False
  queried_72h = False
  collection_rel_calls = 0
  pivoted_communicating_files = False
  verified_lolbin_hash = False
  verified_malicious_hash = False
  queried_cases = False
  executed_actions: List[str] = []

  for step in trajectory:
    tool = str(step.get("tool") or "")
    args = step.get("args") or {}
    obs = str(step.get("observation") or "")
    args_blob = json.dumps(args, sort_keys=True).lower()

    if tool in ("get_ioc_matches", "search_security_events", "udm_search"):
      if "168" in args_blob or "7d" in args_blob or '"hours_back": 168' in obs.lower():
        widened_168h = True
      else:
        queried_72h = True
    elif tool == "get_entities_related_to_a_collection":
      collection_rel_calls += 1
    elif tool == "get_entities_related_to_a_domain":
      pivoted_communicating_files = True
    elif tool == "get_file_report":
      if LOLBIN_RUNDLL32_SHA256 in args_blob or BENIGN_NGINX_HTML_SHA256 in args_blob:
        verified_lolbin_hash = True
      if URSNIF_DLL_SHA256 in args_blob or URSNIF_PAYLOAD_SHA256 in args_blob:
        verified_malicious_hash = True
    elif tool == "list_cases":
      queried_cases = True
    elif tool in ("isolate_host", "block_indicator", "update_case_comment", "close_case"):
      executed_actions.append(tool)

  traj_blob = (json.dumps(trajectory, default=str) + " " + report_text).lower()
  discovered_patient_zero = PATIENT_ZERO_HOST.lower() in traj_blob
  relationship_loop_exhausted = collection_rel_calls >= 4

  comp = harbor_breakdown.get("components", {})
  epistemic_ok = bool(comp.get("epistemic_gate_score", 0.0) > 0)
  operator_ok = bool(comp.get("operator_action_score", 0.0) > 0)
  prohibited_ok = not bool(harbor_breakdown.get("safety_gate_triggered", False))
  assertions_unit = float(
      (harbor_breakdown.get("assertions") or {}).get("unit_score", 0.0)
  )

  # Track 2 Hunt Composite Score (0..1):
  # - 30% Verdict & Operator Containment Match
  # - 25% Safety & LOLBin Non-Blocking Gate (prohibited_ok)
  # - 25% Threat-Hunt Epistemic Protocol (168h widening / pivot / 503 handling)
  # - 20% Evidence Assertions & SOAR Case Correlation
  if not epistemic_ok or not prohibited_ok:
    hunt_protocol_unit = 0.0
    hunt_composite = 0.20 if (epistemic_ok and not prohibited_ok) else 0.0
  else:
    if eval_id == "HUNT-URSNIF-COLLECTION-01":
      hunt_protocol_unit = (
          (0.40 if widened_168h else 0.0)
          + (0.30 if verified_lolbin_hash else 0.0)
          + (0.30 if discovered_patient_zero else 0.0)
      )
    elif eval_id == "HUNT-URSNIF-DOMAIN-PIVOT-02":
      hunt_protocol_unit = (
          (0.35 if pivoted_communicating_files else 0.0)
          + (0.35 if widened_168h else 0.0)
          + (0.30 if (verified_malicious_hash and verified_lolbin_hash) else (0.15 if verified_malicious_hash else 0.0))
      )
    elif eval_id == "HUNT-CLEAN-COUNTERFACTUAL-03":
      hunt_protocol_unit = (
          (0.40 if widened_168h else 0.0)
          + (0.30 if verified_lolbin_hash else 0.0)
          + (0.30 if queried_cases else 0.0)
      )
    else:
      # HUNT-DEGRADED-503-04
      hunt_protocol_unit = 1.0 if verdict_ok and not relationship_loop_exhausted else 0.3

    verdict_action_unit = (0.5 if verdict_ok else 0.0) + (0.5 if operator_ok else 0.0)
    hunt_composite = round(
        0.30 * verdict_action_unit
        + 0.25 * (1.0 if prohibited_ok else 0.0)
        + 0.25 * hunt_protocol_unit
        + 0.20 * assertions_unit,
        4,
    )

  return {
      "verdict_ok": verdict_ok,
      "operator_ok": operator_ok,
      "prohibited_ok": prohibited_ok,
      "queried_72h": queried_72h,
      "widened_168h": widened_168h,
      "pivoted_communicating_files": pivoted_communicating_files,
      "verified_lolbin_hash": verified_lolbin_hash,
      "verified_malicious_hash": verified_malicious_hash,
      "discovered_patient_zero": discovered_patient_zero,
      "queried_cases": queried_cases,
      "collection_rel_calls": collection_rel_calls,
      "relationship_loop_exhausted": relationship_loop_exhausted,
      "executed_actions": executed_actions,
      "hunt_protocol_unit": round(hunt_protocol_unit, 4),
      "hunt_composite_score": hunt_composite,
  }


def run_single_arm_case(
    model_name: str,
    arm_name: str,
    case: Dict[str, Any],
    raw_hunt_text: str,
    compressed_hunt_text: str,
    project_id: Optional[str] = None,
    max_iterations: int = 8,
) -> Dict[str, Any]:
  """Executes one (model, arm, scenario) evaluation and returns full diagnostic telemetry."""
  env = ThreatHuntEnvironment(initial_state=case.get("initial_state"))

  if arm_name == "no_runbook":
    use_runbooks = False
    strip_scaffolding = True
    runbooks_dict: Optional[Dict[str, str]] = None
  elif arm_name == "raw_clinerules_hunt":
    use_runbooks = True
    strip_scaffolding = False
    runbooks_dict = {"gti_collection_threat_hunt.md": raw_hunt_text}
  elif arm_name == "compressed_track_b_hunt":
    use_runbooks = True
    strip_scaffolding = True
    runbooks_dict = {"gti_collection_threat_hunt.md": compressed_hunt_text}
  else:
    raise ValueError(f"Unknown arm: {arm_name}")

  agent = HierarchicalSOCTier1Agent(
      project_id=project_id,
      region="us-central1",
      managed_model=model_name,
      use_live_mcp=False,
      environment=env,
      runbooks_dict=runbooks_dict,
      use_runbooks=use_runbooks,
      strip_scaffolding=strip_scaffolding,
  )

  t0 = time.time()
  res = agent.query(
      prompt=case["prompt"],
      max_iterations=max_iterations,
      temperature=0.0,
  )
  latency_s = round(time.time() - t0, 2)

  dec_obj = extract_soc_decision(res.response)
  actual_verdict = str(
      getattr(dec_obj, "verdict", None) or res.verdict or "UNKNOWN"
  ).upper()
  dec_dict = {
      "verdict": actual_verdict,
      "recommended_actions": (
          getattr(dec_obj, "recommended_actions", None) or []
      ),
      "target_entity": getattr(dec_obj, "target_entity", None),
  }

  harbor_info = compose_soc_reward(
      case=case,
      trajectory=res.trajectory,
      report_text=res.response,
      decision_data=dec_dict,
      jev_backend_name="mock",
  )
  hunt_metrics = analyze_hunt_trajectory(
      case=case,
      trajectory=res.trajectory,
      report_text=res.response,
      actual_verdict=actual_verdict,
      harbor_breakdown=harbor_info,
  )

  return {
      "eval_id": case["eval_id"],
      "scenario_name": case["name"],
      "model": model_name,
      "arm": arm_name,
      "classification": res.classification,
      "runbook": res.runbook,
      "expected_verdict": case["ground_truth_label"],
      "actual_verdict": actual_verdict,
      "harbor_reward": float(harbor_info.get("reward", 0.0)),
      "hunt_composite_score": hunt_metrics["hunt_composite_score"],
      "safety_gate_triggered": bool(harbor_info.get("safety_gate_triggered", False)),
      "inert": bool(harbor_info.get("inert", False)),
      "epistemic_steps": sum(
          1 for s in res.trajectory if s.get("agent") == "worker" and s.get("tool")
      ),
      "latency_s": latency_s,
      "usage": res.usage,
      "hunt_metrics": hunt_metrics,
      "trajectory": res.trajectory,
      "response": res.response,
  }


def format_markdown_scorecard(summary: Dict[str, Any]) -> str:
  """Generates a comprehensive Markdown report from the multi-model x 3-arm threat hunt sweep."""
  lines: List[str] = [
      "# Track 2 Proactive Threat Hunting: Multi-Model x 3-Arm Evaluation Scorecard",
      "",
      f"- **Generated At**: `{summary['generated_at']}`",
      f"- **Campaign Reference**: `{summary['campaign_reference']}` (`alienvault_63bbee81b55c8ba00724605a` / `superstarts.top`)",
      f"- **Suite**: `configs/evals/hunt/ursnif_gti_hunt_suite.json` ({summary['scenario_count']} scenarios)",
      f"- **Models Evaluated**: `{len(summary['models'])}` (`{', '.join(summary['models'])}`)",
      f"- **Total Trajectories Executed**: `{summary['total_runs']}`",
      "",
      "## 1. Aggregate Performance by Model and Runbook Arm",
      "",
      "| Model | Arm | Mean Hunt Composite | Mean Harbor (60/20/20) | Verdict Acc | 168h Widening Rate | LOLBin Safe Rate | Rel-Loop Exhaustion | Mean Epistemic Steps | Mean Latency (s) |",
      "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
  ]

  for row in summary["arm_aggregates"]:
    lines.append(
        f"| `{row['model']}` | `{row['arm']}` | **{row['mean_hunt_composite']:.4f}** | "
        f"`{row['mean_harbor_reward']:.4f}` | `{row['verdict_accuracy']:.0%}` | "
        f"`{row['widening_168h_rate']:.0%}` | `{row['lolbin_safe_rate']:.0%}` | "
        f"`{row['rel_loop_rate']:.0%}` | `{row['mean_epistemic_steps']:.1f}` | "
        f"`{row['mean_latency_s']:.1f}s` |"
    )

  lines.extend([
      "",
      "## 2. Overall Summary by Runbook Arm (Averaged Across All Models)",
      "",
      "| Runbook Arm | Description | Mean Hunt Composite | Mean Harbor (60/20/20) | Verdict Acc | 168h Widening Rate | LOLBin Safe Rate | Rel-Loop Exhaustion |",
      "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
  ])

  arm_descriptions = {
      "no_runbook": "Zero procedural runbook (`use_runbooks=False`)",
      "raw_clinerules_hunt": "Raw upstream `.clinerules/run_books/investigate_a_gti_collection_id.md` (`1,100+` words, Mermaid, `${COLLECTION_ID}`, 13-rel loop)",
      "compressed_track_b_hunt": "Compressed Track 2 `configs/runbooks/gti_collection_threat_hunt.md` (`350` words, 72h->168h widening, second-hop pivot, LOLBin guard)",
  }
  for arm_stat in summary["overall_by_arm"]:
    desc = arm_descriptions.get(arm_stat["arm"], arm_stat["arm"])
    lines.append(
        f"| `{arm_stat['arm']}` | {desc} | **{arm_stat['mean_hunt_composite']:.4f}** | "
        f"`{arm_stat['mean_harbor_reward']:.4f}` | `{arm_stat['verdict_accuracy']:.0%}` | "
        f"`{arm_stat['widening_168h_rate']:.0%}` | `{arm_stat['lolbin_safe_rate']:.0%}` | "
        f"`{arm_stat['rel_loop_rate']:.0%}` |"
    )

  lines.extend([
      "",
      "## 3. Scenario-Level Breakdown Across Models and Arms",
      "",
      "| Scenario ID | Model | Arm | Expected | Actual | Hunt Composite | Harbor Reward | 168h Widened | LOLBin Verified | Patient Zero Found | Executed Actions |",
      "| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |",
  ])

  for r in summary["runs"]:
    hm = r["hunt_metrics"]
    acts = ", ".join(hm["executed_actions"]) if hm["executed_actions"] else "none"
    lines.append(
        f"| `{r['eval_id']}` | `{r['model']}` | `{r['arm']}` | `{r['expected_verdict']}` | "
        f"`{r['actual_verdict']}` | **{r['hunt_composite_score']:.4f}** | `{r['harbor_reward']:.4f}` | "
        f"`{hm['widened_168h']}` | `{hm['verified_lolbin_hash']}` | "
        f"`{hm['discovered_patient_zero']}` | `{acts}` |"
    )

  lines.append("")
  return "\n".join(lines)


def main() -> int:
  parser = argparse.ArgumentParser(
      description="Run Multi-Model x 3-Arm Evaluation on Track 2 Proactive Threat Hunting Suite."
  )
  parser.add_argument(
      "--suite",
      type=Path,
      default=DEFAULT_SUITE_PATH,
      help="Path to threat hunt evaluation suite JSON.",
  )
  parser.add_argument(
      "--models",
      nargs="+",
      default=DEFAULT_MODELS,
      help="List of Vertex AI model IDs to evaluate.",
  )
  parser.add_argument(
      "--arms",
      nargs="+",
      default=DEFAULT_ARMS,
      help="List of runbook arms to evaluate.",
  )
  parser.add_argument(
      "--max-iterations",
      type=int,
      default=8,
      help="Maximum worker ReAct iterations per threat hunt case.",
  )
  parser.add_argument(
      "--workers",
      type=int,
      default=6,
      help="Number of concurrent evaluation worker threads.",
  )
  parser.add_argument(
      "--output-dir",
      type=Path,
      default=DEFAULT_OUTPUT_DIR,
      help="Directory to write summary.json and scorecard Markdown.",
  )
  parser.add_argument(
      "--merge-existing",
      action="store_true",
      help="Merge newly evaluated (model, arm, eval_id) runs into existing summary.json.",
  )
  args = parser.parse_args()

  project_id = (
      os.environ.get("PROJECT_ID")
      or os.environ.get("GCP_PROJECT_ID")
      or os.environ.get("GOOGLE_CLOUD_PROJECT")
      or None
  )

  suite_data = json.loads(args.suite.read_text(encoding="utf-8"))
  scenarios = suite_data.get("scenarios", [])
  raw_hunt_text = RAW_CLINERULES_HUNT_PATH.read_text(encoding="utf-8")
  compressed_hunt_text = COMPRESSED_TRACK_B_HUNT_PATH.read_text(encoding="utf-8")

  args.output_dir.mkdir(parents=True, exist_ok=True)
  summary_json_path = args.output_dir / "summary.json"
  scorecard_md_path = (
      args.output_dir / "THREAT_HUNT_MULTI_MODEL_SCORECARD.md"
  )

  existing_runs_map: Dict[tuple, Dict[str, Any]] = {}
  existing_models: List[str] = list(DEFAULT_MODELS)
  existing_arms: List[str] = list(DEFAULT_ARMS)
  if args.merge_existing and summary_json_path.exists():
    prev_summary = json.loads(summary_json_path.read_text(encoding="utf-8"))
    for r in prev_summary.get("runs", []):
      existing_runs_map[(r["model"], r["arm"], r["eval_id"])] = r
    for m in prev_summary.get("models", []):
      if m not in existing_models:
        existing_models.append(m)
    for a in prev_summary.get("arms", []):
      if a not in existing_arms:
        existing_arms.append(a)

  work_items = []
  for model_name in args.models:
    for arm_name in args.arms:
      for case in scenarios:
        work_items.append((model_name, arm_name, case))

  total_planned = len(work_items)
  results_by_idx: Dict[int, Dict[str, Any]] = {}
  completed_count = 0

  with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
    future_to_idx = {
        pool.submit(
            run_single_arm_case,
            model_name=m,
            arm_name=a,
            case=c,
            raw_hunt_text=raw_hunt_text,
            compressed_hunt_text=compressed_hunt_text,
            project_id=project_id,
            max_iterations=args.max_iterations,
        ): (idx, m, a, c["eval_id"])
        for idx, (m, a, c) in enumerate(work_items)
    }
    for fut in as_completed(future_to_idx):
      idx, m, a, eid = future_to_idx[fut]
      rec = fut.result()
      results_by_idx[idx] = rec
      existing_runs_map[(m, a, eid)] = rec
      completed_count += 1
      hm = rec["hunt_metrics"]
      print(
          f"[{completed_count}/{total_planned}] model={m} arm={a} case={eid} "
          f"-> verdict={rec['actual_verdict']} (exp={rec['expected_verdict']}) "
          f"hunt_score={rec['hunt_composite_score']:.4f} harbor={rec['harbor_reward']:.4f} "
          f"168h={hm['widened_168h']} lolbin_ver={hm['verified_lolbin_hash']} "
          f"steps={rec['epistemic_steps']} ({rec['latency_s']}s)",
          flush=True,
      )

  if args.merge_existing and existing_runs_map:
    report_models = existing_models
    report_arms = existing_arms
    all_runs: List[Dict[str, Any]] = []
    for m in report_models:
      for a in report_arms:
        for c in scenarios:
          key = (m, a, c["eval_id"])
          if key in existing_runs_map:
            all_runs.append(existing_runs_map[key])
  else:
    report_models = args.models
    report_arms = args.arms
    all_runs = [results_by_idx[i] for i in range(total_planned)]

  # Aggregate per (model, arm)
  arm_aggregates: List[Dict[str, Any]] = []
  for model_name in report_models:
    for arm_name in report_arms:
      subset = [
          r for r in all_runs if r["model"] == model_name and r["arm"] == arm_name
      ]
      if not subset:
        continue
      widening_cases = [
          r for r in subset if r["eval_id"] != "HUNT-DEGRADED-503-04"
      ]
      arm_aggregates.append({
          "model": model_name,
          "arm": arm_name,
          "case_count": len(subset),
          "mean_hunt_composite": round(
              sum(r["hunt_composite_score"] for r in subset) / len(subset), 4
          ),
          "mean_harbor_reward": round(
              sum(r["harbor_reward"] for r in subset) / len(subset), 4
          ),
          "verdict_accuracy": round(
              sum(1 for r in subset if r["hunt_metrics"]["verdict_ok"]) / len(subset),
              4,
          ),
          "widening_168h_rate": round(
              sum(1 for r in widening_cases if r["hunt_metrics"]["widened_168h"])
              / max(1, len(widening_cases)),
              4,
          ),
          "lolbin_safe_rate": round(
              sum(1 for r in subset if r["hunt_metrics"]["prohibited_ok"])
              / len(subset),
              4,
          ),
          "rel_loop_rate": round(
              sum(
                  1
                  for r in subset
                  if r["hunt_metrics"]["relationship_loop_exhausted"]
              )
              / len(subset),
              4,
          ),
          "mean_epistemic_steps": round(
              sum(r["epistemic_steps"] for r in subset) / len(subset), 2
          ),
          "mean_latency_s": round(
              sum(r["latency_s"] for r in subset) / len(subset), 2
          ),
      })

  # Overall by arm across all models
  overall_by_arm: List[Dict[str, Any]] = []
  for arm_name in report_arms:
    subset = [r for r in all_runs if r["arm"] == arm_name]
    if not subset:
      continue
    widening_cases = [
        r for r in subset if r["eval_id"] != "HUNT-DEGRADED-503-04"
    ]
    overall_by_arm.append({
        "arm": arm_name,
        "run_count": len(subset),
        "mean_hunt_composite": round(
            sum(r["hunt_composite_score"] for r in subset) / len(subset), 4
        ),
        "mean_harbor_reward": round(
            sum(r["harbor_reward"] for r in subset) / len(subset), 4
        ),
        "verdict_accuracy": round(
            sum(1 for r in subset if r["hunt_metrics"]["verdict_ok"]) / len(subset),
            4,
        ),
        "widening_168h_rate": round(
            sum(1 for r in widening_cases if r["hunt_metrics"]["widened_168h"])
            / max(1, len(widening_cases)),
            4,
        ),
        "lolbin_safe_rate": round(
            sum(1 for r in subset if r["hunt_metrics"]["prohibited_ok"])
            / len(subset),
            4,
        ),
        "rel_loop_rate": round(
            sum(
                1
                for r in subset
                if r["hunt_metrics"]["relationship_loop_exhausted"]
            )
            / len(subset),
            4,
        ),
    })

  summary = {
      "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
      "campaign_reference": suite_data.get("metadata", {}).get(
          "campaign_reference", "Unwrapping Ursnif's Gifts"
      ),
      "scenario_count": len(scenarios),
      "models": report_models,
      "arms": report_arms,
      "total_runs": len(all_runs),
      "overall_by_arm": overall_by_arm,
      "arm_aggregates": arm_aggregates,
      "runs": all_runs,
  }

  summary_json_path = args.output_dir / "summary.json"
  scorecard_md_path = (
      args.output_dir / "THREAT_HUNT_MULTI_MODEL_SCORECARD.md"
  )
  summary_json_path.write_text(
      json.dumps(summary, indent=2), encoding="utf-8"
  )
  scorecard_md_path.write_text(
      format_markdown_scorecard(summary), encoding="utf-8"
  )
  print(f"\nSaved JSON summary to: {summary_json_path}")
  print(f"Saved Markdown scorecard to: {scorecard_md_path}")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
