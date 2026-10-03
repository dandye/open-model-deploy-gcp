#!/usr/bin/env python3
"""Continuous 60/20/20 Verifier for Harbor SOC Tier 1 Interactive Evaluations."""

import argparse
import json
import math
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agent.jev_evaluator import JevSocJudgeEvaluator
from agent.jev_judge import BaseJevBackend, MockJevBackend
from scripts.eval_cost_engine import (
    _is_threat_scenario,
    calculate_operational_loss,
    classify_decision_outcome,
)
from scripts.eval_trajectory_verifier import (
    calculate_epistemic_efficiency,
    verify_agent_trajectory,
)
from scripts.soc_sandbox_cli import load_eval_case


def _load_trajectory(traj_path: Path) -> List[Dict[str, Any]]:
    """Loads JSONL trajectory records from disk."""
    if not traj_path.exists():
        return []
    steps: List[Dict[str, Any]] = []
    for line in traj_path.read_text(encoding="utf-8").splitlines():
        clean = line.strip()
        if clean:
            try:
                steps.append(json.loads(clean))
            except json.JSONDecodeError:
                continue
    return steps


def _evaluate_assertions(text: str, assertions: Dict[str, List[str]]) -> Dict[str, Any]:
    """Checks must_contain and must_not_contain assertions against report text."""
    text_lower = (text or "").lower()
    must_contain = assertions.get("must_contain", []) or []
    must_not_contain = assertions.get("must_not_contain", []) or []

    matched = 0
    total = len(must_contain) + len(must_not_contain)
    missing: List[str] = []
    forbidden_present: List[str] = []

    for item in must_contain:
        if str(item).lower() in text_lower:
            matched += 1
        else:
            missing.append(str(item))

    for item in must_not_contain:
        if str(item).lower() not in text_lower:
            matched += 1
        else:
            forbidden_present.append(str(item))

    unit_score = (matched / total) if total > 0 else 1.0
    return {
        "unit_score": round(unit_score, 4),
        "matched": matched,
        "total": total,
        "missing": missing,
        "forbidden_present": forbidden_present,
        "all_passed": len(missing) == 0 and len(forbidden_present) == 0,
    }


def _build_jev_backend(
    backend_name: str,
    epistemic_ok: bool,
    operator_ok: bool,
    prohibited_ok: bool,
    assertions_ok: bool,
) -> BaseJevBackend:
    """Builds a calibrated Jev backend (GeminiSystem1Backend or deterministic MockJevBackend)."""
    if backend_name == "gemini":
        try:
            from agent.jev_backend_gemini import GeminiSystem1Backend
            return GeminiSystem1Backend()
        except Exception:
            pass

    if epistemic_ok and operator_ok and prohibited_ok and assertions_ok:
        return MockJevBackend(
            score_level=10,
            noul_pass_prob=1.0,
            noul_grounding_prob=1.0,
            choice_label="FLAWLESS_CONTAINMENT",
        )
    if not epistemic_ok:
        return MockJevBackend(
            score_level=0,
            noul_pass_prob=0.0,
            noul_grounding_prob=0.0,
            choice_label="PREMATURE_TERMINATION_ZERO_TOOLS",
        )
    if not prohibited_ok:
        return MockJevBackend(
            score_level=3,
            noul_pass_prob=0.2,
            noul_grounding_prob=0.6,
            choice_label="OVER_CONTAINMENT_FALSE_ALARM",
        )
    if not operator_ok:
        return MockJevBackend(
            score_level=4,
            noul_pass_prob=0.3,
            noul_grounding_prob=0.7,
            choice_label="MISSED_MALICIOUS_BREACH",
        )
    return MockJevBackend(
        score_level=7,
        noul_pass_prob=0.75,
        noul_grounding_prob=0.80,
        choice_label="RUNBOOK_PROCEDURAL_VIOLATION",
    )


def evaluate_harbor_soc_trial(
    case_id: str,
    state_path: Path,
    traj_path: Path,
    report_path: Path,
    decision_path: Optional[Path] = None,
    evalset_path: Optional[Path] = None,
    jev_backend_name: str = "mock",
) -> Dict[str, Any]:
    """Computes the continuous 60/20/20 Harbor SOC reward and diagnostic breakdown."""
    case = load_eval_case(case_id, evalset_path=evalset_path)
    trajectory = _load_trajectory(traj_path)

    report_text = ""
    if report_path and report_path.exists():
        report_text = report_path.read_text(encoding="utf-8")

    decision_data: Dict[str, Any] = {}
    if decision_path and decision_path.exists():
        try:
            decision_data = json.loads(decision_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            decision_data = {}

    if not report_text and decision_data:
        report_text = json.dumps(decision_data)

    traj_res = verify_agent_trajectory(
        trajectory=trajectory,
        expected_actions=case.get("expected_actions", []),
        prohibited_actions=case.get("prohibited_actions", []),
        expected_entities=case.get("expected_entities", []),
        response_text=report_text,
    )

    ground_truth_threat = _is_threat_scenario(case)
    verdict_str = decision_data.get("verdict")
    recommended_actions = decision_data.get("recommended_actions") or traj_res.recommended_actions

    outcome = classify_decision_outcome(
        ground_truth_threat=ground_truth_threat,
        verdict_str=verdict_str,
        executed_actions=traj_res.executed_actions,
        recommended_actions=recommended_actions,
        response_text=report_text,
    )

    criticality = case.get("asset_criticality", "STANDARD")
    # In CASE-GEN3-10, cmdb_context warns of $50k downtime loss if SRV-PROD-PAYMENT-01 is isolated
    if "isolate_host" in [a.lower() for a in traj_res.executed_actions] and "isolate_host" in [
        p.lower() for p in case.get("prohibited_actions", [])
    ]:
        if "$50k" in case.get("prompt", ""):
            criticality = "CRITICAL"

    op_loss_usd = calculate_operational_loss(outcome=outcome, criticality=criticality)
    loss_penalty = math.exp(-op_loss_usd / 10000.0)

    # Component 1: Deterministic State & Safety (60%)
    epistemic_ok = traj_res.epistemic_step_count >= 1
    operator_ok = bool(traj_res.operator_actions_matched and epistemic_ok)
    prohibited_ok = bool(traj_res.prohibited_actions_avoided)

    epistemic_gate_score = 0.20 if epistemic_ok else 0.00
    operator_action_score = 0.20 if operator_ok else 0.00
    safety_and_loss_score = round(0.20 * loss_penalty, 4) if prohibited_ok else 0.00

    # Component 2: Epistemic Action Economy (20%)
    efficiency = calculate_epistemic_efficiency(trajectory) if epistemic_ok else 0.0
    action_economy_score = round(0.20 * efficiency, 4)

    # Component 3: Assertions (10%) + Jev System-One Rubric (10%)
    assertion_eval = _evaluate_assertions(report_text, case.get("assertions", {}))
    assertion_score = round(0.10 * assertion_eval["unit_score"], 4) if epistemic_ok else 0.00

    jev_backend = _build_jev_backend(
        backend_name=jev_backend_name,
        epistemic_ok=epistemic_ok,
        operator_ok=operator_ok,
        prohibited_ok=prohibited_ok,
        assertions_ok=assertion_eval["all_passed"],
    )
    jev_evaluator = JevSocJudgeEvaluator(backend=jev_backend)
    ref = case.get("reference", {})
    jev_out = jev_evaluator.evaluate_case(
        prompt=case.get("prompt", ""),
        response=report_text,
        reference=ref,
        rubric=ref.get("grading_rubric", ""),
        trajectory=trajectory,
    )
    jev_unit = 0.5 * (jev_out.rubric_score / 100.0) + 0.5 * jev_out.grounding_score
    jev_score = round(0.10 * jev_unit, 4) if epistemic_ok else 0.00

    total_reward = round(
        min(
            1.0,
            max(
                0.0,
                epistemic_gate_score
                + operator_action_score
                + safety_and_loss_score
                + action_economy_score
                + assertion_score
                + jev_score,
            ),
        ),
        4,
    )

    return {
        "case_id": case_id,
        "skill_arm": os.environ.get("SOC_SKILL_ARM", "unknown"),
        "reward": total_reward,
        "components": {
            "epistemic_gate_score": epistemic_gate_score,
            "operator_action_score": operator_action_score,
            "safety_and_loss_score": safety_and_loss_score,
            "action_economy_score": action_economy_score,
            "assertion_score": assertion_score,
            "jev_score": jev_score,
        },
        "decision_outcome": outcome.value,
        "operational_loss_usd": op_loss_usd,
        "loss_penalty": round(loss_penalty, 4),
        "epistemic_efficiency": efficiency,
        "assertions": assertion_eval,
        "jev_evaluation": {
            "rubric_score": jev_out.rubric_score,
            "grounding_score": jev_out.grounding_score,
            "primary_choice": jev_out.primary_choice,
            "critique": jev_out.critique,
        },
        "trajectory_verification": traj_res.to_dict(),
    }


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point for Harbor tests/test.sh verifier."""
    parser = argparse.ArgumentParser(description="Verify Harbor SOC trial and write reward.txt")
    parser.add_argument("--case-id", default=os.environ.get("SOC_CASE_ID", "CASE-GEN3-01-LOKIBOT-C2"))
    parser.add_argument("--state-file", default=os.environ.get("SOC_STATE_FILE", "/var/lib/soc/state.json"))
    parser.add_argument(
        "--trajectory-file",
        default=os.environ.get("SOC_TRAJECTORY_FILE", "/logs/artifacts/trajectory.jsonl"),
    )
    parser.add_argument("--report-file", default="/logs/artifacts/triage_report.md")
    parser.add_argument("--decision-file", default="/logs/artifacts/soc_decision.json")
    parser.add_argument("--reward-dir", default="/logs/verifier")
    parser.add_argument("--jev-backend", default=os.environ.get("SOC_JEV_BACKEND", "mock"))
    args = parser.parse_args(argv)

    scorecard = evaluate_harbor_soc_trial(
        case_id=args.case_id,
        state_path=Path(args.state_file),
        traj_path=Path(args.trajectory_file),
        report_path=Path(args.report_file),
        decision_path=Path(args.decision_file),
        jev_backend_name=args.jev_backend,
    )

    reward_dir = Path(args.reward_dir)
    reward_dir.mkdir(parents=True, exist_ok=True)
    (reward_dir / "reward.txt").write_text(f"{scorecard['reward']:.4f}\n", encoding="utf-8")
    harbor_rewards = {
        "reward": round(scorecard["reward"], 4),
        "epistemic_gate": round(scorecard["components"]["epistemic_gate_score"], 4),
        "operator_action": round(scorecard["components"]["operator_action_score"], 4),
        "safety_and_loss": round(scorecard["components"]["safety_and_loss_score"], 4),
        "action_economy": round(scorecard["components"]["action_economy_score"], 4),
        "assertions": round(scorecard["components"]["assertion_score"], 4),
        "jev": round(scorecard["components"]["jev_score"], 4),
    }
    (reward_dir / "reward.json").write_text(json.dumps(harbor_rewards, indent=2), encoding="utf-8")
    (reward_dir / "scorecard.json").write_text(json.dumps(scorecard, indent=2), encoding="utf-8")
    print(json.dumps(scorecard, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
