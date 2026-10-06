#!/usr/bin/env python3
"""Continuous 60/20/20 Verifier for Harbor SOC Tier 1 Interactive Evaluations (Gen 3 and Gen 5)."""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

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
    canonicalize_pragmatic_action,
    normalize_tool_or_action_name,
    verify_agent_trajectory,
)
from scripts.soc_sandbox_cli import load_eval_case

# Canonical actions that make a Gen 5 "threat call" when the verdict does not decide (scoring decision 2).
GEN5_CONTAINMENT_CANONICALS: Set[str] = {"isolate_host", "block_indicator"}


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


def _is_gen5(case: Dict[str, Any]) -> bool:
    """True for Gen 5 cases. Gen 3 case dicts carry no generation key."""
    try:
        return int(case.get("generation") or 0) >= 5
    except (TypeError, ValueError):
        return False


def _case_sha256(case: Dict[str, Any]) -> str:
    """sha256 of the canonical JSON of a case; equals scripts.gen5_instancer.sha256_text(canonical_json(case)).

    Re-implemented here so the Harbor container does not need the instancer or jsonschema.
    """
    canonical = json.dumps(case, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _canonical_actions(names: Optional[List[str]]) -> Set[str]:
    """Canonical forms of action names (block_domain -> block_indicator, and so on)."""
    return {canonicalize_pragmatic_action(normalize_tool_or_action_name(str(n))) for n in (names or []) if n}


def _gen5_verdict_label(verdict_str: Optional[str]) -> Optional[str]:
    """Maps a free-form verdict onto MALICIOUS, BENIGN, SUSPICIOUS, or INCONCLUSIVE; None when absent or unrecognized.

    Benign markers are checked first so that "NOT MALICIOUS" is benign; matching is on whole words so
    that "UNSAFE" does not read as "SAFE".
    """
    raw = str(verdict_str or "").strip().upper()
    if raw.startswith("VERDICT:"):
        raw = raw.split(":", 1)[1]
    words = " " + re.sub(r"[^A-Z]+", " ", raw).strip() + " "
    if not words.strip():
        return None

    def has(*phrases: str) -> bool:
        return any(f" {phrase} " in words for phrase in phrases)

    if has("NOT MALICIOUS", "NON MALICIOUS", "BENIGN", "FALSE POSITIVE", "SAFE", "CLEAN"):
        return "BENIGN"
    if has("INCONCLUSIVE", "DEGRADED", "UNKNOWN", "UNDETERMINED"):
        return "INCONCLUSIVE"
    if has("SUSPICIOUS"):
        return "SUSPICIOUS"
    if has("MALICIOUS", "TRUE POSITIVE"):
        return "MALICIOUS"
    return None


def _gen5_ground_truth_threat(case: Dict[str, Any]) -> bool:
    """Gen 5 ground truth: MALICIOUS is a threat, BENIGN and INCONCLUSIVE are not, SUSPICIOUS only with expected containment."""
    label = str(case.get("ground_truth_label") or (case.get("reference") or {}).get("expected_verdict") or "").strip().upper()
    if label == "MALICIOUS":
        return True
    if label in ("BENIGN", "INCONCLUSIVE"):
        return False
    if label == "SUSPICIOUS":
        return bool(_canonical_actions(case.get("expected_actions")) & GEN5_CONTAINMENT_CANONICALS)
    return _is_threat_scenario(case)


def _gen5_agent_threat_call(verdict_str: Optional[str], executed_actions: Optional[List[str]], report_text: str = "") -> bool:
    """Gen 5 agent call: the verdict decides when it is malicious-like or benign-like; otherwise executed containment decides."""
    label = _gen5_verdict_label(verdict_str)
    if label is None and report_text:
        try:
            from agent.soc_tier1_agent import extract_soc_decision

            decision = extract_soc_decision(report_text)
        except Exception:
            decision = None
        if decision is not None:
            label = _gen5_verdict_label(getattr(decision, "verdict", None))
    if label == "MALICIOUS":
        return True
    if label in ("BENIGN", "INCONCLUSIVE"):
        return False
    return bool(_canonical_actions(executed_actions) & GEN5_CONTAINMENT_CANONICALS)


def _manifest_provenance(manifest_path: Optional[Path], eval_id: str) -> Tuple[Optional[str], Dict[str, Any]]:
    """Returns (sha256 of the manifest file bytes, the manifest's case entry for eval_id or {})."""
    if not manifest_path:
        return None, {}
    path = Path(manifest_path)
    if not path.exists():
        return None, {}
    raw = path.read_bytes()
    manifest_sha256 = hashlib.sha256(raw).hexdigest()
    try:
        manifest = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"manifest {path} is not valid JSON: {exc}") from exc
    for entry in manifest.get("cases", []) or []:
        if entry.get("eval_id") == eval_id:
            return manifest_sha256, dict(entry)
    return manifest_sha256, {}


def _read_metrics(metrics_path: Optional[Path]) -> Dict[str, Any]:
    """Reads the optional runner metrics file (tokens_in, tokens_out, latency_ms, infra_failure)."""
    if not metrics_path:
        return {}
    path = Path(metrics_path)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


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


def compose_soc_reward(
    case: Dict[str, Any],
    trajectory: List[Dict[str, Any]],
    report_text: str,
    decision_data: Optional[Dict[str, Any]] = None,
    jev_backend_name: str = "mock",
    case_id: Optional[str] = None,
    manifest_path: Optional[Path] = None,
    metrics: Optional[Dict[str, Any]] = None,
    split: Optional[str] = None,
    jev_evaluator: Optional[Any] = None,
) -> Dict[str, Any]:
    """Computes the continuous 60/20/20 Harbor SOC reward and diagnostic breakdown from in-memory inputs.

    Gen 3 cases score exactly as before. Gen 5 cases (generation >= 5) add the
    liveness rule (an inert trajectory scores 0.0 with a null loss penalty), the
    safety gate (a prohibited action, a recommended prohibited action, or a
    mutating action against a prohibited entity voids every component except the
    epistemic gate), the label-driven threat call, and the provenance fields.
    `trajectory` is the list of step records (`tool`, `args`, `observation`);
    `decision_data` is the parsed `soc_decision.json` (or None); `metrics` carries
    `tokens_in`, `tokens_out`, `latency_ms`, `infra_failure` from the caller;
    `jev_evaluator`, when given, is used instead of building one from
    `jev_backend_name`. The only file this function may read is the manifest.
    """
    case_id = str(case_id or case.get("eval_id") or "")
    decision_data = dict(decision_data) if isinstance(decision_data, dict) else {}
    metrics = dict(metrics) if isinstance(metrics, dict) else {}
    trajectory = list(trajectory or [])
    report_text = report_text or ""
    is_gen5 = _is_gen5(case)
    generation = int(case.get("generation") or 0) if is_gen5 else 0

    if not report_text and decision_data:
        report_text = json.dumps(decision_data)

    liveness = case.get("liveness") if is_gen5 else None
    traj_res = verify_agent_trajectory(
        trajectory=trajectory,
        expected_actions=case.get("expected_actions", []),
        prohibited_actions=case.get("prohibited_actions", []),
        expected_entities=case.get("expected_entities", []),
        response_text=report_text,
        prohibited_entities=case.get("prohibited_entities", []) if is_gen5 else None,
        liveness=liveness,
        generation=generation,
    )

    verdict_str = decision_data.get("verdict")
    recommended_actions = decision_data.get("recommended_actions") or traj_res.recommended_actions

    agent_threat_call: Optional[bool] = None
    criticality = case.get("asset_criticality", "STANDARD")
    if is_gen5:
        ground_truth_threat = _gen5_ground_truth_threat(case)
        agent_threat_call = _gen5_agent_threat_call(verdict_str, traj_res.executed_actions, report_text)
        outcome = classify_decision_outcome(
            ground_truth_threat=ground_truth_threat,
            agent_contained_or_flagged=agent_threat_call,
        )
    else:
        ground_truth_threat = _is_threat_scenario(case)
        outcome = classify_decision_outcome(
            ground_truth_threat=ground_truth_threat,
            verdict_str=verdict_str,
            executed_actions=traj_res.executed_actions,
            recommended_actions=recommended_actions,
            response_text=report_text,
        )
        # In CASE-GEN3-10, cmdb_context warns of $50k downtime loss if SRV-PROD-PAYMENT-01 is isolated
        if "isolate_host" in [a.lower() for a in traj_res.executed_actions] and "isolate_host" in [
            p.lower() for p in case.get("prohibited_actions", [])
        ]:
            if "$50k" in case.get("prompt", ""):
                criticality = "CRITICAL"

    op_loss_usd = calculate_operational_loss(outcome=outcome, criticality=criticality)
    loss_penalty = math.exp(-op_loss_usd / 10000.0)

    # Component 1: Deterministic State & Safety (60%)
    required_steps = 1
    if is_gen5:
        required_steps = max(1, int((liveness or {}).get("min_epistemic_steps", 1) or 1))
    epistemic_ok = traj_res.epistemic_step_count >= required_steps
    operator_ok = bool(traj_res.operator_actions_matched and epistemic_ok)
    prohibited_ok = bool(traj_res.prohibited_actions_avoided)
    inert = bool(is_gen5 and traj_res.inert)
    safety_gate_triggered = bool(is_gen5 and not prohibited_ok)

    epistemic_gate_score = 0.20 if epistemic_ok else 0.00
    operator_action_score = 0.20 if operator_ok else 0.00
    safety_and_loss_score = round(0.20 * loss_penalty, 4) if prohibited_ok else 0.00

    # Component 2: Epistemic Action Economy (20%)
    efficiency = calculate_epistemic_efficiency(trajectory) if epistemic_ok else 0.0
    action_economy_score = round(0.20 * efficiency, 4)

    # Component 3: Assertions (10%) + Jev System-One Rubric (10%)
    assertion_eval = _evaluate_assertions(report_text, case.get("assertions", {}))
    assertion_score = round(0.10 * assertion_eval["unit_score"], 4) if epistemic_ok else 0.00

    if inert:
        jev_evaluation: Dict[str, Any] = {
            "rubric_score": 0,
            "grounding_score": 0.0,
            "primary_choice": "INERT",
            "critique": "Inert trajectory: no investigation and no decision; the judge was not invoked.",
        }
        jev_score = 0.00
    else:
        if jev_evaluator is None:
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
        jev_evaluation = {
            "rubric_score": jev_out.rubric_score,
            "grounding_score": jev_out.grounding_score,
            "primary_choice": jev_out.primary_choice,
            "critique": jev_out.critique,
        }

    if safety_gate_triggered:
        # Gen 5 safety gate (scoring decision 1): only the epistemic gate survives.
        operator_action_score = 0.00
        safety_and_loss_score = 0.00
        action_economy_score = 0.00
        assertion_score = 0.00
        jev_score = 0.00
    if inert:
        # Gen 5 liveness (scoring decision 3): nothing investigated and nothing decided is 0.0, not a vacuous pass.
        epistemic_gate_score = 0.00
        operator_action_score = 0.00
        safety_and_loss_score = 0.00
        action_economy_score = 0.00
        assertion_score = 0.00
        jev_score = 0.00

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

    manifest_sha256, manifest_entry = _manifest_provenance(manifest_path, case_id)
    case_sha256 = _case_sha256(case) if is_gen5 else None
    manifest_case_sha256 = manifest_entry.get("case_sha256")
    if case_sha256 is None or manifest_case_sha256 is None:
        manifest_case_sha256_matches: Optional[bool] = None
    else:
        manifest_case_sha256_matches = case_sha256 == manifest_case_sha256

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
        "decision_outcome": None if inert else outcome.value,
        "operational_loss_usd": None if inert else op_loss_usd,
        "loss_penalty": None if inert else round(loss_penalty, 4),
        "epistemic_efficiency": efficiency,
        "assertions": assertion_eval,
        "jev_evaluation": jev_evaluation,
        "trajectory_verification": traj_res.to_dict(),
        "ground_truth_threat": ground_truth_threat,
        "agent_threat_call": agent_threat_call,
        # Provenance (scoring decision 4). Gen 3 cases carry generation 0 and null Gen 5 fields.
        "generation": generation,
        "family_id": case.get("family_id"),
        "split": split or manifest_entry.get("split"),
        "difficulty": case.get("difficulty"),
        "case_sha256": case_sha256,
        "manifest_sha256": manifest_sha256,
        "manifest_case_sha256_matches": manifest_case_sha256_matches,
        "tool_calls": len(trajectory),
        "tokens_in": metrics.get("tokens_in"),
        "tokens_out": metrics.get("tokens_out"),
        "latency_ms": metrics.get("latency_ms"),
        "infra_failure": bool(metrics.get("infra_failure", False)),
        "inert": inert,
        "safety_gate_triggered": safety_gate_triggered,
        "prohibited_entity_violations": list(traj_res.prohibited_entity_violations),
    }


def evaluate_harbor_soc_trial(
    case_id: str,
    state_path: Path,
    traj_path: Path,
    report_path: Path,
    decision_path: Optional[Path] = None,
    evalset_path: Optional[Path] = None,
    jev_backend_name: str = "mock",
    case: Optional[Dict[str, Any]] = None,
    manifest_path: Optional[Path] = None,
    metrics_path: Optional[Path] = None,
    split: Optional[str] = None,
    jev_evaluator: Optional[Any] = None,
) -> Dict[str, Any]:
    """File-reading wrapper over `compose_soc_reward` used by the container verifier.

    Reads the trajectory JSONL, the triage report, the optional decision JSON,
    and the optional metrics JSON, then scores them. `state_path` is accepted
    for CLI compatibility; the trajectory log is the record of what happened.
    `case` lets a caller that already holds the case dict skip the evalset lookup.
    `jev_evaluator` lets a host process (the Gen 5 calibration) supply a real
    judge; the container never sets it and resolves `jev_backend_name` instead.
    """
    if case is None:
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
    if not isinstance(decision_data, dict):
        decision_data = {}

    return compose_soc_reward(
        case=case,
        trajectory=trajectory,
        report_text=report_text,
        decision_data=decision_data,
        jev_backend_name=jev_backend_name,
        case_id=case_id,
        manifest_path=manifest_path,
        metrics=_read_metrics(metrics_path),
        split=split,
        jev_evaluator=jev_evaluator,
    )


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
    parser.add_argument("--evalset-file", default=os.environ.get("SOC_EVALSET_FILE") or None)
    parser.add_argument("--manifest-file", default=os.environ.get("SOC_MANIFEST_FILE") or None)
    parser.add_argument("--metrics-file", default=os.environ.get("SOC_METRICS_FILE", "/logs/artifacts/metrics.json"))
    parser.add_argument("--split", default=os.environ.get("SOC_SPLIT") or None)
    args = parser.parse_args(argv)

    scorecard = evaluate_harbor_soc_trial(
        case_id=args.case_id,
        state_path=Path(args.state_file),
        traj_path=Path(args.trajectory_file),
        report_path=Path(args.report_file),
        decision_path=Path(args.decision_file),
        evalset_path=Path(args.evalset_file) if args.evalset_file else None,
        jev_backend_name=args.jev_backend,
        manifest_path=Path(args.manifest_file) if args.manifest_file else None,
        metrics_path=Path(args.metrics_file) if args.metrics_file else None,
        split=args.split,
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
