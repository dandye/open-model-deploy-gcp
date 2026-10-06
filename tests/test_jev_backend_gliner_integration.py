"""Real-weights check for the GLiNER2.5-Decide judge.

Opt in with RUN_GLINER_JUDGE_TESTS=1: it loads the model (about 8 s) and scores
two reference-policy states (about 6 s each on this CPU), so it stays out of
the default suite. Everything else about the backend is covered hermetically
in tests/test_jev_backend_gliner.py.
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_GLINER_JUDGE_TESTS") != "1",
    reason="set RUN_GLINER_JUDGE_TESTS=1 to run the real GLiNER2.5-Decide judge",
)
pytest.importorskip("gliner2")

from agent.jev_backend_gliner import GlinerDecideBackend  # noqa: E402
from agent.jev_evaluator import JevSocJudgeEvaluator  # noqa: E402
from scripts.gen5_reference_policies import GEN5_ROOT, execute_python, load_split, plan_policy  # noqa: E402


def _judge(evaluator, case, policy):
    trial = plan_policy(case, policy)
    return evaluator.evaluate_case(
        prompt=case["prompt"],
        response=trial.report_text,
        reference=case["reference"],
        rubric=case["reference"].get("grading_rubric", ""),
        trajectory=execute_python(case, trial),
    )


def test_real_judge_separates_oracle_from_close_all_and_repeats_bit_for_bit():
    case = next(c for c in load_split(GEN5_ROOT, "validation") if c["ground_truth_label"] == "MALICIOUS")
    backend = GlinerDecideBackend()
    evaluator = JevSocJudgeEvaluator(backend=backend)

    oracle = _judge(evaluator, case, "oracle")
    close_all = _judge(evaluator, case, "close_all")

    assert oracle.primary_choice == "FLAWLESS_CONTAINMENT"
    assert close_all.primary_choice == "MISSED_MALICIOUS_BREACH"
    assert oracle.rubric_score > close_all.rubric_score
    assert oracle.raw_metadata["noul_pass_prob"] > close_all.raw_metadata["noul_pass_prob"]
    assert abs(sum(oracle.raw_metadata["choice_probs"].values()) - 1.0) < 1e-3
    assert abs(sum(oracle.raw_metadata["score_levels"].values()) - 1.0) < 1e-3
    assert oracle.raw_metadata["noul_derivations"]["pass"]["formula"] == "P(FLAWLESS_CONTAINMENT)"
    fit = oracle.raw_metadata["noul_derivations"]["pass"]["state_fit"]
    assert fit["tokens_before"] > 100 and fit["within_budget"] is True

    repeat = _judge(evaluator, case, "oracle")
    assert repeat.rubric_score == oracle.rubric_score
    assert repeat.raw_metadata["choice_probs"] == oracle.raw_metadata["choice_probs"]
    assert backend.fit_stats["states_judged"] == 2
    assert backend.engine.count_tokens("isolate host DESKTOP-FIN-08") < 15
