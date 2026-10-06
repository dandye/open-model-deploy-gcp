"""Unit tests for SOC Evaluation State Serializer and Jev System One Evaluator."""

import pytest
from agent.jev_evaluator import JevSocJudgeEvaluator, build_soc_evaluation_state
from agent.jev_judge import JevNoulResult, MockJevBackend


def test_build_soc_evaluation_state_contains_trajectory():
    traj = [
        {
            "step": 1,
            "tool": "search_threat_intelligence",
            "args": {"ioc": "198.51.100.22"},
            "observation": "Malicious C2",
        }
    ]
    state = build_soc_evaluation_state(
        prompt="Alert: Suspicious connection",
        response="I isolated the host.",
        reference={"ground_truth": "Malicious"},
        rubric="Must isolate host.",
        trajectory=traj,
    )
    assert "Tool Execution Trajectory" in state
    assert "search_threat_intelligence" in state
    assert "198.51.100.22" in state
    assert "Must isolate host." in state


def test_jev_soc_judge_evaluator_evaluates_case():
    backend = MockJevBackend(
        score_level=9,
        noul_pass_prob=0.92,
        noul_grounding_prob=0.96,
        choice_label="FLAWLESS_CONTAINMENT",
    )
    evaluator = JevSocJudgeEvaluator(backend=backend)
    res = evaluator.evaluate_case(
        prompt="Alert: ransomware",
        response="Contained host.",
        reference={"status": "malicious"},
        rubric="Isolate host immediately.",
    )
    assert res.rubric_score == 90.0
    assert res.passed is True
    assert res.grounding_score == 0.96
    assert "FLAWLESS_CONTAINMENT" in res.primary_choice
    assert "Jev System-One" in res.critique


def test_raw_metadata_shape_is_unchanged_for_backends_without_derivations():
    evaluator = JevSocJudgeEvaluator(backend=MockJevBackend())
    res = evaluator.evaluate_case(prompt="p", response="r", reference={}, rubric="rb")
    assert set(res.raw_metadata) == {"score_levels", "noul_pass_prob", "noul_grounding_prob", "choice_probs"}


def test_raw_metadata_records_noul_derivations_when_a_backend_reports_them():
    class DerivingBackend(MockJevBackend):
        def evaluate_noul(self, state, question):
            base = super().evaluate_noul(state, question)
            is_grounding = "ground" in question.lower()
            return JevNoulResult(
                probability=base.probability,
                verdict=base.verdict,
                details={"formula": "1 - P(UNGROUNDED_HALLUCINATED_CLAIM)" if is_grounding else "P(FLAWLESS_CONTAINMENT)"},
            )

    res = JevSocJudgeEvaluator(backend=DerivingBackend()).evaluate_case(prompt="p", response="r", reference={}, rubric="rb")
    assert res.raw_metadata["noul_derivations"] == {
        "pass": {"formula": "P(FLAWLESS_CONTAINMENT)"},
        "grounding": {"formula": "1 - P(UNGROUNDED_HALLUCINATED_CLAIM)"},
    }
