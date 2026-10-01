"""Unit tests for SOC Evaluation State Serializer and Jev System One Evaluator."""

import pytest
from agent.jev_evaluator import JevSocJudgeEvaluator, build_soc_evaluation_state
from agent.jev_judge import MockJevBackend


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
