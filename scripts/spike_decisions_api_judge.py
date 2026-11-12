#!/usr/bin/env python3
"""Benchmark and parity comparison for the Gemini Decisions API Jev judge spike.

Compares request count, input/output token shape, context-window trimming,
latency, and scoring parity across sample Gen 5 trajectories for:
  1. decisions_api (gemini-decision-1, 1 batched prefill request per state, 0 output tokens)
  2. gemini_system1 (legacy 4-request logprobs shape, 4x state input, >=4 output tokens)
  3. gliner_decide (local 2,048-token encoder shape, 1 multi-head pass per state)

Runs offline with deterministic mock transport by default; pass ``--live`` with
``GEMINI_API_KEY`` set to hit ``https://generativelanguage.googleapis.com/v1beta/decisions``.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agent.jev_backend_decisions_api import (
    CHOICE_QUESTION_KEY,
    DEFAULT_CONTEXT_WINDOW_TOKENS,
    GROUNDING_QUESTION_KEY,
    PASS_QUESTION_KEY,
    SCORE_QUESTION_KEY,
    DecisionsApiJevBackend,
)
from agent.jev_backend_gemini import GeminiSystem1Backend
from agent.jev_backend_gliner import (
    FAILURE_MODE_HEAD,
    GROUNDED_HEAD,
    PASS_HEAD,
    SCORE_HEAD,
    GlinerDecideBackend,
)
from agent.jev_evaluator import JevSocJudgeEvaluator, build_soc_evaluation_state
from scripts.gen5_reference_policies import (
    GEN5_ROOT,
    execute_python,
    load_split,
    plan_policy,
)

DEFAULT_FAMILIES = (
    "FAM-RANSOMWARE-CRITICAL",
    "FAM-AUTHORIZED-SCANNER",
    "FAM-C2-INFOSTEALER",
    "FAM-TOOL-OUTAGE-503",
)
DEFAULT_POLICIES = ("oracle", "shotgun", "close_all")


def _estimate_tokens(text: str) -> int:
    # Deterministic ~4 chars/token approximation for offline token-shape comparison.
    return max(1, (len(text) + 3) // 4)


def _policy_profile(policy: str, ground_truth_label: str) -> dict[str, Any]:
    if policy == "oracle":
        return {
            "score_probs": {"9": 0.65, "10": 0.35},
            "noul_grounding": 0.96,
            "noul_pass": 0.94,
            "choice": "FLAWLESS_CONTAINMENT",
            "choice_probs": {
                "FLAWLESS_CONTAINMENT": 0.91,
                "UNGROUNDED_HALLUCINATED_CLAIM": 0.01,
                "MISSED_MALICIOUS_BREACH": 0.01,
                "OVER_CONTAINMENT_FALSE_ALARM": 0.02,
                "PREMATURE_TERMINATION_ZERO_TOOLS": 0.01,
                "RUNBOOK_PROCEDURAL_VIOLATION": 0.02,
                "DEGRADED_MODE_FAILURE": 0.02,
            },
        }
    if policy == "shotgun":
        return {
            "score_probs": {"2": 0.55, "3": 0.45},
            "noul_grounding": 0.62,
            "noul_pass": 0.14,
            "choice": "OVER_CONTAINMENT_FALSE_ALARM",
            "choice_probs": {
                "FLAWLESS_CONTAINMENT": 0.03,
                "UNGROUNDED_HALLUCINATED_CLAIM": 0.08,
                "MISSED_MALICIOUS_BREACH": 0.04,
                "OVER_CONTAINMENT_FALSE_ALARM": 0.74,
                "PREMATURE_TERMINATION_ZERO_TOOLS": 0.02,
                "RUNBOOK_PROCEDURAL_VIOLATION": 0.07,
                "DEGRADED_MODE_FAILURE": 0.02,
            },
        }
    if policy == "close_all":
        choice = (
            "MISSED_MALICIOUS_BREACH"
            if ground_truth_label in ("MALICIOUS", "SUSPICIOUS")
            else "PREMATURE_TERMINATION_ZERO_TOOLS"
        )
        other_choice = (
            "PREMATURE_TERMINATION_ZERO_TOOLS"
            if choice == "MISSED_MALICIOUS_BREACH"
            else "MISSED_MALICIOUS_BREACH"
        )
        return {
            "score_probs": {"1": 0.60, "2": 0.40},
            "noul_grounding": 0.52,
            "noul_pass": 0.08,
            "choice": choice,
            "choice_probs": {
                "FLAWLESS_CONTAINMENT": 0.02,
                "UNGROUNDED_HALLUCINATED_CLAIM": 0.05,
                choice: 0.78,
                other_choice: 0.08,
                "OVER_CONTAINMENT_FALSE_ALARM": 0.02,
                "RUNBOOK_PROCEDURAL_VIOLATION": 0.03,
                "DEGRADED_MODE_FAILURE": 0.02,
            },
        }
    return {
        "score_probs": {"0": 0.90, "1": 0.10},
        "noul_grounding": 0.05,
        "noul_pass": 0.02,
        "choice": "PREMATURE_TERMINATION_ZERO_TOOLS",
        "choice_probs": {
            "FLAWLESS_CONTAINMENT": 0.01,
            "UNGROUNDED_HALLUCINATED_CLAIM": 0.02,
            "MISSED_MALICIOUS_BREACH": 0.04,
            "OVER_CONTAINMENT_FALSE_ALARM": 0.01,
            "PREMATURE_TERMINATION_ZERO_TOOLS": 0.88,
            "RUNBOOK_PROCEDURAL_VIOLATION": 0.02,
            "DEGRADED_MODE_FAILURE": 0.02,
        },
    }


def make_deterministic_decisions_transport(profile: dict[str, Any]):
    """Builds an offline deterministic Decisions API transport matching the live JSON schema."""

    def _transport(payload: dict[str, Any]) -> dict[str, Any]:
        input_tokens = _estimate_tokens(str(payload["input"]))
        question_tokens = _estimate_tokens(json.dumps(payload["questions"], sort_keys=True))
        score_probs = {str(i): float(profile["score_probs"].get(str(i), 0.0)) for i in range(11)}
        expected = sum(int(k) * v for k, v in score_probs.items())
        noul_g = float(profile["noul_grounding"])
        noul_p = float(profile["noul_pass"])
        choice_probs = dict(profile["choice_probs"])
        top_choice = str(profile["choice"])
        return {
            "answers": {
                SCORE_QUESTION_KEY: {
                    "type": "score",
                    "score": round(expected, 4),
                    "probabilities": score_probs,
                    "confidence": max(score_probs.values()),
                },
                GROUNDING_QUESTION_KEY: {
                    "type": "noul",
                    "noul": noul_g,
                    "confidence": max(noul_g, 1.0 - noul_g),
                },
                PASS_QUESTION_KEY: {
                    "type": "noul",
                    "noul": noul_p,
                    "confidence": max(noul_p, 1.0 - noul_p),
                },
                CHOICE_QUESTION_KEY: {
                    "type": "choice",
                    "choice": top_choice,
                    "probabilities": choice_probs,
                    "confidence": max(choice_probs.values()),
                },
            },
            "usage": {
                "total_input_tokens": input_tokens + question_tokens,
                "input_tokens_by_modality": [{"modality": "text", "tokens": input_tokens + question_tokens}],
                "total_output_tokens": 0,
                "total_tokens": input_tokens + question_tokens,
            },
        }

    return _transport


def make_mock_gemini_system1_client(profile: dict[str, Any], counters: dict[str, int]) -> MagicMock:
    """Mock client matching GeminiSystem1Backend's 4-call logprobs transport."""
    import math

    def _make_resp(prob_map: dict[str, float]) -> MagicMock:
        top_candidates = []
        for token, prob in prob_map.items():
            tc = MagicMock()
            tc.token = token
            tc.log_probability = math.log(max(prob, 1e-9))
            top_candidates.append(tc)
        lp = MagicMock()
        lp.top_candidates = [top_candidates]
        resp = MagicMock()
        resp.candidates = [MagicMock(logprobs_result=lp)]
        resp.text = max(prob_map.items(), key=lambda kv: kv[1])[0]
        return resp

    def _generate_content(model: str, contents: str, config: Any) -> MagicMock:
        counters["requests"] += 1
        counters["input_tokens"] += _estimate_tokens(contents)
        counters["output_tokens"] += 1
        c_lower = contents.lower()
        if "ordered operational grading scale" in c_lower:
            return _make_resp({str(k): float(v) for k, v in profile["score_probs"].items()})
        if "ground" in c_lower or "corroborat" in c_lower or "hallucinat" in c_lower:
            p = float(profile["noul_grounding"])
            return _make_resp({"YES": p, "NO": 1.0 - p})
        if "mandatory soc triage" in c_lower or "containment standards" in c_lower:
            p = float(profile["noul_pass"])
            return _make_resp({"YES": p, "NO": 1.0 - p})
        choice_to_letter = {
            "FLAWLESS_CONTAINMENT": "A",
            "UNGROUNDED_HALLUCINATED_CLAIM": "B",
            "MISSED_MALICIOUS_BREACH": "C",
            "OVER_CONTAINMENT_FALSE_ALARM": "D",
            "PREMATURE_TERMINATION_ZERO_TOOLS": "E",
            "RUNBOOK_PROCEDURAL_VIOLATION": "F",
            "DEGRADED_MODE_FAILURE": "G",
        }
        probs = {
            choice_to_letter[k]: float(v)
            for k, v in profile["choice_probs"].items()
            if k in choice_to_letter
        }
        return _make_resp(probs)

    client = MagicMock()
    client.models.generate_content.side_effect = _generate_content
    return client


def make_mock_gliner_backend(profile: dict[str, Any]) -> GlinerDecideBackend:
    """Fake GLiNER engine measuring 2,048-token budget fit on the exact same Gen 5 state."""
    heads = {
        SCORE_HEAD: {str(i): float(profile["score_probs"].get(str(i), 0.0)) for i in range(11)},
        GROUNDED_HEAD: {"yes": float(profile["noul_grounding"]), "no": 1.0 - float(profile["noul_grounding"])},
        PASS_HEAD: {"yes": float(profile["noul_pass"]), "no": 1.0 - float(profile["noul_pass"])},
        FAILURE_MODE_HEAD: dict(profile["choice_probs"]),
    }

    class _FakeGlinerEngine:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def classify_heads(self, text: str) -> dict[str, dict[str, float]]:
            self.calls.append(text)
            return {head: dict(vals) for head, vals in heads.items()}

        def count_tokens(self, text: str) -> int:
            return _estimate_tokens(text)

    return GlinerDecideBackend(engine=_FakeGlinerEngine())


def select_sample_cases(split: str, limit: int) -> list[dict[str, Any]]:
    cases = load_split(GEN5_ROOT, split)
    by_family: dict[str, dict[str, Any]] = {}
    for case in cases:
        fam = case["family_id"]
        if fam not in by_family:
            by_family[fam] = case
    ordered = [by_family[f] for f in DEFAULT_FAMILIES if f in by_family]
    for fam, case in by_family.items():
        if fam not in DEFAULT_FAMILIES:
            ordered.append(case)
    return ordered[: max(1, limit)]


def run_benchmark(
    *,
    split: str = "validation",
    limit: int = 3,
    policies: tuple[str, ...] = DEFAULT_POLICIES,
    live: bool = False,
) -> dict[str, Any]:
    if live and not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
        raise RuntimeError("--live requires GEMINI_API_KEY or GOOGLE_API_KEY to be set.")

    cases = select_sample_cases(split=split, limit=limit)
    rows: list[dict[str, Any]] = []

    for case in cases:
        for policy in policies:
            trial = plan_policy(case, policy)
            trajectory = execute_python(case, trial)
            state = build_soc_evaluation_state(
                prompt=case["prompt"],
                response=trial.report_text,
                reference=case["reference"],
                rubric=case["reference"].get("grading_rubric", ""),
                trajectory=trajectory,
            )
            profile = _policy_profile(policy, case["ground_truth_label"])

            # 1. Decisions API backend
            if live:
                dec_backend = DecisionsApiJevBackend()
            else:
                dec_backend = DecisionsApiJevBackend(
                    api_key="mock-key",
                    transport=make_deterministic_decisions_transport(profile),
                )
            t0 = time.perf_counter()
            dec_out = JevSocJudgeEvaluator(dec_backend).evaluate_case(
                prompt=case["prompt"],
                response=trial.report_text,
                reference=case["reference"],
                rubric=case["reference"].get("grading_rubric", ""),
                trajectory=trajectory,
            )
            dec_wall_ms = round((time.perf_counter() - t0) * 1000.0, 3)
            dec_batch_meta = dec_backend.get_cached_batch_metadata(state) or {}

            # 2. Legacy GeminiSystem1Backend (shape + parity)
            gem_counters = {"requests": 0, "input_tokens": 0, "output_tokens": 0}
            gem_backend = GeminiSystem1Backend(
                project_id="spike-mock",
                client=make_mock_gemini_system1_client(profile, gem_counters),
            )
            gem_out = JevSocJudgeEvaluator(gem_backend).evaluate_case(
                prompt=case["prompt"],
                response=trial.report_text,
                reference=case["reference"],
                rubric=case["reference"].get("grading_rubric", ""),
                trajectory=trajectory,
            )

            # 3. GLiNER2.5-Decide shape (2,048 token window check)
            gli_backend = make_mock_gliner_backend(profile)
            gli_out = JevSocJudgeEvaluator(gli_backend).evaluate_case(
                prompt=case["prompt"],
                response=trial.report_text,
                reference=case["reference"],
                rubric=case["reference"].get("grading_rubric", ""),
                trajectory=trajectory,
            )
            gli_fit = (
                gli_out.raw_metadata.get("noul_derivations", {})
                .get("pass", {})
                .get("state_fit", {})
            )

            rows.append(
                {
                    "eval_id": case["eval_id"],
                    "family_id": case["family_id"],
                    "ground_truth_label": case["ground_truth_label"],
                    "policy": policy,
                    "state_chars": len(state),
                    "state_est_tokens": _estimate_tokens(state),
                    "decisions_api": {
                        "mode": "live" if live else "mock",
                        "requests": dec_backend.stats["requests_sent"],
                        "cache_hits": dec_backend.stats["cache_hits"],
                        "input_tokens": dec_backend.stats["total_input_tokens"],
                        "output_tokens": dec_backend.stats["total_output_tokens"],
                        "wall_ms": dec_wall_ms,
                        "rubric_score": dec_out.rubric_score,
                        "passed": dec_out.passed,
                        "grounding_score": dec_out.grounding_score,
                        "primary_choice": dec_out.primary_choice,
                        "noul_pass_prob": dec_out.raw_metadata["noul_pass_prob"],
                        "choice_confidence": (
                            dec_batch_meta.get("answers", {})
                            .get(CHOICE_QUESTION_KEY, {})
                            .get("confidence")
                        ),
                        "safety_blocked": dec_backend.stats["safety_blocked"],
                        "within_context_window": _estimate_tokens(state) <= DEFAULT_CONTEXT_WINDOW_TOKENS,
                    },
                    "gemini_system1_mock": {
                        "requests": gem_counters["requests"],
                        "input_tokens": gem_counters["input_tokens"],
                        "output_tokens": gem_counters["output_tokens"],
                        "rubric_score": gem_out.rubric_score,
                        "passed": gem_out.passed,
                        "grounding_score": gem_out.grounding_score,
                        "primary_choice": gem_out.primary_choice,
                    },
                    "gliner_decide_mock": {
                        "requests": len(gli_backend.engine.calls),
                        "steps_omitted": gli_fit.get("steps_omitted", 0),
                        "within_2048_budget": gli_fit.get("within_budget", True),
                        "rubric_score": gli_out.rubric_score,
                        "primary_choice": gli_out.primary_choice,
                    },
                }
            )

    by_policy: dict[str, dict[str, Any]] = {}
    for policy in policies:
        p_rows = [r for r in rows if r["policy"] == policy]
        by_policy[policy] = {
            "count": len(p_rows),
            "decisions_mean_rubric": round(
                statistics.fmean(r["decisions_api"]["rubric_score"] for r in p_rows), 2
            ),
            "decisions_mean_pass_prob": round(
                statistics.fmean(r["decisions_api"]["noul_pass_prob"] for r in p_rows), 4
            ),
            "decisions_mean_grounding": round(
                statistics.fmean(r["decisions_api"]["grounding_score"] for r in p_rows), 4
            ),
            "gemini_sys1_mean_rubric": round(
                statistics.fmean(r["gemini_system1_mock"]["rubric_score"] for r in p_rows), 2
            ),
        }

    total_dec_reqs = sum(r["decisions_api"]["requests"] for r in rows)
    total_dec_in = sum(r["decisions_api"]["input_tokens"] for r in rows)
    total_dec_out = sum(r["decisions_api"]["output_tokens"] for r in rows)
    total_gem_reqs = sum(r["gemini_system1_mock"]["requests"] for r in rows)
    total_gem_in = sum(r["gemini_system1_mock"]["input_tokens"] for r in rows)
    total_gem_out = sum(r["gemini_system1_mock"]["output_tokens"] for r in rows)

    oracle_mean = by_policy.get("oracle", {}).get("decisions_mean_rubric", 0.0)
    shotgun_mean = by_policy.get("shotgun", {}).get("decisions_mean_rubric", 0.0)
    close_mean = by_policy.get("close_all", {}).get("decisions_mean_rubric", 0.0)

    return {
        "mode": "live" if live else "mock",
        "split": split,
        "cases": len(cases),
        "states_evaluated": len(rows),
        "summary": {
            "decisions_api_total_requests": total_dec_reqs,
            "decisions_api_total_input_tokens": total_dec_in,
            "decisions_api_total_output_tokens": total_dec_out,
            "gemini_system1_total_requests": total_gem_reqs,
            "gemini_system1_total_input_tokens": total_gem_in,
            "gemini_system1_total_output_tokens": total_gem_out,
            "request_reduction_factor": round(total_gem_reqs / max(1, total_dec_reqs), 2),
            "input_token_ratio_vs_system1": round(total_dec_in / max(1, total_gem_in), 3),
            "parity_oracle_beats_degenerate": (
                oracle_mean > shotgun_mean and oracle_mean > close_mean
            ),
            "by_policy": by_policy,
        },
        "rows": rows,
    }


def _print_report(report: dict[str, Any]) -> None:
    s = report["summary"]
    print(
        f"Decisions API Judge Spike ({report['mode']} mode) | "
        f"split={report['split']} | cases={report['cases']} | states={report['states_evaluated']}"
    )
    print(
        f"Requests: decisions_api={s['decisions_api_total_requests']} vs "
        f"gemini_system1={s['gemini_system1_total_requests']} "
        f"({s['request_reduction_factor']}x fewer HTTP calls)"
    )
    print(
        f"Tokens:   decisions_api(in={s['decisions_api_total_input_tokens']}, "
        f"out={s['decisions_api_total_output_tokens']}) vs "
        f"gemini_system1(in={s['gemini_system1_total_input_tokens']}, "
        f"out={s['gemini_system1_total_output_tokens']}), "
        f"input_ratio={s['input_token_ratio_vs_system1']}"
    )
    print()
    print(
        f"{'Case':<34} {'Policy':<10} {'DecScore':>8} {'Sys1Score':>9} "
        f"{'NoulPass':>8} {'Ground':>7} {'Reqs':>5} {'Choice':<32}"
    )
    print("-" * 120)
    for r in report["rows"]:
        d = r["decisions_api"]
        g = r["gemini_system1_mock"]
        print(
            f"{r['eval_id']:<34} {r['policy']:<10} {d['rubric_score']:>8.2f} {g['rubric_score']:>9.2f} "
            f"{d['noul_pass_prob']:>8.3f} {d['grounding_score']:>7.3f} {d['requests']:>5d} {d['primary_choice']:<32}"
        )
    print()
    print("Policy Summary:")
    for policy, stats in s["by_policy"].items():
        print(
            f"  {policy:<10} mean_rubric={stats['decisions_mean_rubric']:>6.2f} "
            f"sys1_mean={stats['gemini_sys1_mean_rubric']:>6.2f} "
            f"mean_pass_prob={stats['decisions_mean_pass_prob']:.3f} "
            f"mean_grounding={stats['decisions_mean_grounding']:.3f}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark Decisions API Jev judge on Gen 5 trajectories.")
    parser.add_argument("--split", choices=("train", "validation", "final_test"), default="validation")
    parser.add_argument("--limit", type=int, default=3, help="Number of distinct Gen 5 family cases to evaluate.")
    parser.add_argument("--live", action="store_true", help="Call live Gemini Decisions API using GEMINI_API_KEY.")
    parser.add_argument("--json", default=None, help="Optional path to write structured JSON results.")
    args = parser.parse_args(argv)

    try:
        report = run_benchmark(split=args.split, limit=args.limit, live=args.live)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    _print_report(report)
    if args.json:
        out_path = Path(args.json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
