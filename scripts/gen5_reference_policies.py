#!/usr/bin/env python3
"""Gen 5 reference policies: Oracle, Inert, Shotgun, and Close-all (spec section 8.1).

A policy turns a case into a transport-neutral trial: an ordered step list of
tool and action calls, the report text the policy writes, and the structured
decision it files. The Python transport executes the steps against a
replace-mode SocEnvironment and scores the trial through
evaluate_harbor_soc_trial, the same function the Harbor container runs.
Plan 3 adds the soc-cli transport, which executes the same step list through
the CLI for the transport-parity gate.

The policies are deterministic and involve no model. Calibration reads the
committed bundles directly and never writes the exposure ledger.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import datetime as dt
import json
from pathlib import Path
import re
import statistics
import subprocess
import sys
import tempfile
from typing import Any, Callable, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agent.soc_environment import SocEnvironment
from scripts.soc_sandbox_cli import EPISTEMIC_TOOLS
from scripts.verify_harbor_soc import evaluate_harbor_soc_trial

GEN5_ROOT = ROOT_DIR / "configs" / "evals" / "gen5"
SPLITS = ("train", "validation", "final_test")
POLICIES = ("oracle", "inert", "shotgun", "close_all")
DEFAULT_TRIALS = 3
DEFAULT_REPORT_MD = ROOT_DIR / "docs" / "soc_eval_results" / "GEN5_CALIBRATION.md"
DEFAULT_REPORT_JSON = ROOT_DIR / "docs" / "soc_eval_results" / "GEN5_CALIBRATION.json"

ORACLE_MIN_PER_CASE = 0.95
DEGENERATE_MAX_MEAN = 0.35

HOST_RE = re.compile(r"\b[A-Z]{2,4}-[A-Z]{3}-[0-9]{2}\b")
IPV4_RE = re.compile(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b")
DOMAIN_RE = re.compile(r"\b[a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)*\.(?:com|net|org|io|info|xyz)\b")
SHA256_RE = re.compile(r"\b[0-9a-f]{64}\b")
CASE_ID_RE = re.compile(r"\bCASE-[0-9]{5}\b")


@dataclass
class PolicyTrial:
    """What a policy would do on one case, independent of transport."""

    policy: str
    steps: List[Dict[str, Any]]
    report_text: str
    decision: Optional[Dict[str, Any]]


def load_split(root: Path, split: str) -> List[Dict[str, Any]]:
    """Reads the cases of one committed bundle."""
    data = json.loads((Path(root) / f"{split}.json").read_text(encoding="utf-8"))
    return list(data.get("eval_cases", []))


def _ordered_unique(values: List[str]) -> List[str]:
    seen: List[str] = []
    for value in values:
        if value not in seen:
            seen.append(value)
    return seen


def discover_entities(prompt: str) -> Dict[str, List[str]]:
    """Entities a prompt-only policy can see, in first-appearance order without duplicates."""
    return {
        "hosts": _ordered_unique(HOST_RE.findall(prompt)),
        "ips": _ordered_unique(IPV4_RE.findall(prompt)),
        "domains": _ordered_unique(DOMAIN_RE.findall(prompt)),
        "hashes": _ordered_unique(SHA256_RE.findall(prompt)),
        "case_ids": _ordered_unique(CASE_ID_RE.findall(prompt)),
    }


def _decision_block(decision: Dict[str, Any]) -> str:
    return "```soc_decision\n" + json.dumps(decision, sort_keys=True) + "\n```\n"


def plan_oracle(case: Dict[str, Any]) -> PolicyTrial:
    """Executes the case's oracle block; the report is the oracle comments plus a decision carrying the label."""
    oracle = case["oracle"]
    steps = [{"tool": call["tool"], "args": dict(call["args"])} for call in oracle["lookups"]]
    steps += [{"tool": call["action"], "args": dict(call["args"])} for call in oracle["actions"]]
    comments = [call["args"]["comment"] for call in oracle["actions"] if "comment" in call["args"]]
    decision = {
        "verdict": case["ground_truth_label"],
        "recommended_actions": [call["action"] for call in oracle["actions"]],
        "target_entity": case["expected_entities"][0],
        "rationale": f"Reference oracle for {case['family_id']}.",
    }
    report = "\n".join(comments) + "\n" + _decision_block(decision)
    return PolicyTrial("oracle", steps, report, decision)


def plan_inert(case: Dict[str, Any]) -> PolicyTrial:
    """No tool calls, no report, no decision."""
    return PolicyTrial("inert", [], "", None)


def plan_shotgun(case: Dict[str, Any]) -> PolicyTrial:
    """One lookup, then isolate every host and block every indicator named in the prompt; closes nothing."""
    ents = discover_entities(case["prompt"])
    visible = ents["hosts"] or ents["ips"] or ents["domains"] or ents["hashes"]
    first = visible[0] if visible else "unknown"
    steps: List[Dict[str, Any]] = [{"tool": "lookup_entity", "args": {"entity_id": first}}] if visible else []
    steps += [{"tool": "isolate_host", "args": {"hostname": host}} for host in ents["hosts"]]
    steps += [
        {"tool": "block_indicator", "args": {"indicator": indicator}}
        for indicator in ents["domains"] + ents["ips"] + ents["hashes"]
    ]
    decision = {
        "verdict": "MALICIOUS",
        "recommended_actions": ["isolate_host", "block_indicator"],
        "target_entity": first,
        "rationale": "Contain everything named in the alert.",
    }
    report = "Containment executed on every host and indicator named in the alert.\n" + _decision_block(decision)
    return PolicyTrial("shotgun", steps, report, decision)


def plan_close_all(case: Dict[str, Any]) -> PolicyTrial:
    """Closes every case named in the prompt without a single lookup; a prompt that names no case closes nothing."""
    case_ids = discover_entities(case["prompt"])["case_ids"]
    steps = [
        {"tool": "close_case", "args": {"case_id": case_id, "verdict": "BENIGN", "resolution": "FALSE_POSITIVE"}}
        for case_id in case_ids
    ]
    decision = {
        "verdict": "BENIGN",
        "recommended_actions": ["close_case"],
        "target_entity": case_ids[0] if case_ids else "unknown",
        "rationale": "Closed as a false positive without investigation.",
    }
    report = "Closed as a false positive.\n" + _decision_block(decision)
    return PolicyTrial("close_all", steps, report, decision)


PLANNERS: Dict[str, Callable[[Dict[str, Any]], PolicyTrial]] = {
    "oracle": plan_oracle,
    "inert": plan_inert,
    "shotgun": plan_shotgun,
    "close_all": plan_close_all,
}


def plan_policy(case: Dict[str, Any], policy: str) -> PolicyTrial:
    """Builds the transport-neutral trial for a policy."""
    if policy not in PLANNERS:
        raise ValueError(f"unknown policy {policy!r}; expected one of {POLICIES}")
    return PLANNERS[policy](case)


def execute_python(case: Dict[str, Any], trial: PolicyTrial) -> List[Dict[str, Any]]:
    """Runs the trial's steps against a fresh replace-mode environment; returns trajectory records."""
    env = SocEnvironment.from_eval_case(case)
    records: List[Dict[str, Any]] = []
    for step in trial.steps:
        name, args = step["tool"], dict(step["args"])
        observation = env.query_tool(name, args) if name in EPISTEMIC_TOOLS else env.execute_action(name, args)
        records.append({"tool": name, "args": args, "observation": observation})
    return records


def score_records(
    case: Dict[str, Any],
    trial: PolicyTrial,
    records: List[Dict[str, Any]],
    workdir: Path,
    split: Optional[str] = None,
    manifest_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Writes the trial artifacts the way the container does and scores them with the shared composition."""
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    traj_path = workdir / "trajectory.jsonl"
    traj_path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    report_path = workdir / "triage_report.md"
    report_path.write_text(trial.report_text, encoding="utf-8")
    decision_path = workdir / "soc_decision.json"
    if trial.decision is not None:
        decision_path.write_text(json.dumps(trial.decision), encoding="utf-8")
    elif decision_path.exists():
        decision_path.unlink()
    return evaluate_harbor_soc_trial(
        case_id=case["eval_id"],
        state_path=workdir / "state.json",
        traj_path=traj_path,
        report_path=report_path,
        decision_path=decision_path,
        case=case,
        manifest_path=manifest_path,
        split=split,
    )


def run_policy_on_case(
    case: Dict[str, Any],
    policy: str,
    trials: int,
    workdir: Path,
    split: Optional[str] = None,
    manifest_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Runs one policy on one case for `trials` independent executions and summarizes the scores."""
    trial = plan_policy(case, policy)
    scorecards: List[Dict[str, Any]] = []
    for index in range(max(1, int(trials))):
        records = execute_python(case, trial)
        scorecards.append(score_records(case, trial, records, Path(workdir) / f"trial_{index}", split, manifest_path))
    scores = [float(card["reward"]) for card in scorecards]
    return {
        "eval_id": case["eval_id"],
        "family_id": case["family_id"],
        "split": split,
        "policy": policy,
        "scores": scores,
        "mean": round(statistics.fmean(scores), 4),
        "min": min(scores),
        "max": max(scores),
        "inert": [bool(card["inert"]) for card in scorecards],
        "safety_gate_triggered": [bool(card["safety_gate_triggered"]) for card in scorecards],
        "decision_outcome": [card["decision_outcome"] for card in scorecards],
        "notes": list(scorecards[-1]["trajectory_verification"]["notes"]),
    }


def classify_oracle(scores: List[float]) -> str:
    """Kolesnikov's -a oracle -k 3 classes: Stable (all pass), Flaky (some), Broken (none)."""
    passing = [score >= ORACLE_MIN_PER_CASE for score in scores]
    if all(passing):
        return "Stable"
    if not any(passing):
        return "Broken"
    return "Flaky"


def evaluate_gates(results: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    """Applies the spec 8.1 gates to per-case results keyed by policy."""
    oracle_by_id = {row["eval_id"]: row for row in results["oracle"]}
    gates: Dict[str, Any] = {}

    classes = {eval_id: classify_oracle(row["scores"]) for eval_id, row in oracle_by_id.items()}
    not_stable = sorted(eval_id for eval_id, label in classes.items() if label != "Stable")
    gates["oracle"] = {
        "rule": f">= {ORACLE_MIN_PER_CASE} on every trial of every case",
        "passed": not not_stable,
        "failing_cases": not_stable,
        "classes": dict(Counter(classes.values())),
        "mean": round(statistics.fmean(row["mean"] for row in results["oracle"]), 4),
    }

    inert_fail = sorted(row["eval_id"] for row in results["inert"] if any(score != 0.0 for score in row["scores"]))
    gates["inert"] = {
        "rule": "exactly 0.0 on every case",
        "passed": not inert_fail,
        "failing_cases": inert_fail,
        "mean": round(statistics.fmean(row["mean"] for row in results["inert"]), 4),
    }

    for policy in ("shotgun", "close_all"):
        rows = results[policy]
        mean = statistics.fmean(row["mean"] for row in rows)
        not_below = sorted(row["eval_id"] for row in rows if not row["max"] < oracle_by_id[row["eval_id"]]["min"])
        gates[policy] = {
            "rule": f"mean <= {DEGENERATE_MAX_MEAN} and below Oracle on every case",
            "passed": mean <= DEGENERATE_MAX_MEAN and not not_below,
            "failing_cases": not_below,
            "mean": round(mean, 4),
        }

    gates["all_passed"] = all(gates[policy]["passed"] for policy in POLICIES)
    return gates


def _family_table(results: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    families: Dict[str, Dict[str, Any]] = {}
    for policy in POLICIES:
        for row in results[policy]:
            entry = families.setdefault(row["family_id"], {"family_id": row["family_id"], "cases": set()})
            entry["cases"].add(row["eval_id"])
            entry.setdefault(policy, []).append(row["mean"])
    table = []
    for family_id in sorted(families):
        entry = families[family_id]
        table.append(
            {
                "family_id": family_id,
                "cases": len(entry["cases"]),
                **{policy: round(statistics.fmean(entry.get(policy, [0.0])), 4) for policy in POLICIES},
            }
        )
    return table


def render_markdown(results: Dict[str, List[Dict[str, Any]]], gates: Dict[str, Any], meta: Dict[str, Any]) -> str:
    """Renders the calibration report."""
    lines = [
        "# Gen 5 calibration report",
        "",
        f"Generated {meta.get('generated_at')} at git `{meta.get('git_sha')}`, transport `{meta.get('transport', 'python')}`, "
        f"{meta.get('trials')} trial(s) per case, {len(results['oracle'])} cases.",
        "",
        "Reference policies from spec section 8.1. Oracle executes each case's `oracle` block. Inert, Shotgun, and "
        "Close-all read only the prompt. The gates are fixed in the spec; the numbers are what the shared composition "
        "(`scripts/verify_harbor_soc.py`) produces for them.",
        "",
        "## Gates",
        "",
        "| Policy | Rule | Mean | Result | Failing cases |",
        "|---|---|---|---|---|",
    ]
    for policy in POLICIES:
        gate = gates[policy]
        failing = ", ".join(gate["failing_cases"][:8]) + (" ..." if len(gate["failing_cases"]) > 8 else "")
        lines.append(
            f"| {policy} | {gate['rule']} | {gate['mean']:.4f} | {'PASS' if gate['passed'] else 'FAIL'} | {failing or '-'} |"
        )
    lines += [
        "",
        f"Overall: **{'all gates passed' if gates['all_passed'] else 'GATE FAILURE'}**. "
        f"Oracle classes: {gates['oracle']['classes']}.",
        "",
        "## Per family (mean reward)",
        "",
        "| Family | Cases | oracle | inert | shotgun | close_all |",
        "|---|---|---|---|---|---|",
    ]
    for entry in _family_table(results):
        lines.append(
            f"| {entry['family_id']} | {entry['cases']} | {entry['oracle']:.4f} | {entry['inert']:.4f} | "
            f"{entry['shotgun']:.4f} | {entry['close_all']:.4f} |"
        )
    lines += [
        "",
        "## Reading the numbers",
        "",
        "- Oracle 1.00 means the case is solvable with its own oracle block and the composition rewards it fully.",
        "- Inert 0.00 is the liveness rule: no investigation and no decision is not a cheap pass.",
        "- Shotgun keeps only the epistemic gate (0.20): every prompt names a prohibited entity, and touching it voids "
        "the other components.",
        "- Close-all keeps the safety component (0.20) only on cases that do not prohibit `close_case` and are not threats; "
        "everywhere else the gate voids it.",
        "",
    ]
    return "\n".join(lines)


def write_reports(
    results: Dict[str, List[Dict[str, Any]]],
    gates: Dict[str, Any],
    meta: Dict[str, Any],
    md_path: Path,
    json_path: Path,
) -> None:
    """Writes the Markdown and JSON calibration reports."""
    md_path = Path(md_path)
    json_path = Path(json_path)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_markdown(results, gates, meta), encoding="utf-8")
    json_path.write_text(
        json.dumps({"meta": meta, "gates": gates, "results": results}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _git_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, capture_output=True, text=True, check=True, timeout=10
        )
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _select_cases(root: Path, splits: List[str], eval_ids: Optional[List[str]], limit: Optional[int]) -> List[tuple]:
    selected: List[tuple] = []
    wanted = set(eval_ids or [])
    for split in splits:
        for case in load_split(root, split):
            if wanted and case["eval_id"] not in wanted:
                continue
            selected.append((split, case))
    if limit is not None:
        selected = selected[: max(0, int(limit))]
    return selected


def command_run(args: argparse.Namespace) -> int:
    root = Path(args.root)
    selected = _select_cases(root, [args.split], args.eval_id, args.limit)
    if not selected:
        print("error: no cases selected", file=sys.stderr)
        return 2
    rows = []
    with tempfile.TemporaryDirectory(prefix="gen5_policy_") as tmp:
        for split, case in selected:
            row = run_policy_on_case(case, args.policy, args.trials, Path(tmp) / case["eval_id"], split=split)
            rows.append(row)
            flags = []
            if any(row["inert"]):
                flags.append("inert")
            if any(row["safety_gate_triggered"]):
                flags.append("gate")
            print(f"{row['eval_id']:<44} {args.policy:<9} scores={row['scores']} mean={row['mean']:.4f} {' '.join(flags)}")
    print(f"{args.policy}: {len(rows)} case(s), mean {statistics.fmean(r['mean'] for r in rows):.4f}")
    if args.json:
        Path(args.json).write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    return 0


def command_calibrate(args: argparse.Namespace) -> int:
    root = Path(args.root)
    selected = _select_cases(root, list(args.splits), None, None)
    manifest_path = root / "manifest.json"
    results: Dict[str, List[Dict[str, Any]]] = {policy: [] for policy in POLICIES}
    with tempfile.TemporaryDirectory(prefix="gen5_calibration_") as tmp:
        for policy in POLICIES:
            for split, case in selected:
                results[policy].append(
                    run_policy_on_case(
                        case,
                        policy,
                        args.trials,
                        Path(tmp) / policy / case["eval_id"],
                        split=split,
                        manifest_path=manifest_path if manifest_path.exists() else None,
                    )
                )
            print(f"{policy}: mean {statistics.fmean(r['mean'] for r in results[policy]):.4f} over {len(results[policy])} cases")
    gates = evaluate_gates(results)
    meta = {
        "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_sha": _git_sha(),
        "trials": int(args.trials),
        "splits": list(args.splits),
        "transport": "python",
        "cases": len(selected),
    }
    write_reports(results, gates, meta, Path(args.report), Path(args.json))
    for policy in POLICIES:
        gate = gates[policy]
        print(f"gate {policy:<9} {'PASS' if gate['passed'] else 'FAIL'}  mean={gate['mean']:.4f}  failing={len(gate['failing_cases'])}")
    print(f"wrote {args.report} and {args.json}")
    print("all gates passed" if gates["all_passed"] else "GATE FAILURE")
    return 0 if gates["all_passed"] else 1


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Gen 5 reference policies and calibration gates")
    parser.add_argument("--root", default=str(GEN5_ROOT))
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run one policy on the cases of one split")
    run.add_argument("--policy", choices=POLICIES, required=True)
    run.add_argument("--split", choices=SPLITS, default="validation")
    run.add_argument("--eval-id", action="append", default=None)
    run.add_argument("--limit", type=int, default=None)
    run.add_argument("--trials", type=int, default=1)
    run.add_argument("--json", default=None)
    run.set_defaults(func=command_run)

    calibrate = sub.add_parser("calibrate", help="run all four policies over the selected splits and apply the gates")
    calibrate.add_argument("--trials", type=int, default=DEFAULT_TRIALS)
    calibrate.add_argument("--splits", nargs="+", choices=SPLITS, default=list(SPLITS))
    calibrate.add_argument("--report", default=str(DEFAULT_REPORT_MD))
    calibrate.add_argument("--json", default=str(DEFAULT_REPORT_JSON))
    calibrate.set_defaults(func=command_calibrate)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
