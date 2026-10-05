"""Unit tests for Jev System One primitives and probability math."""

import pytest
from agent.jev_judge import (
    BaseJevBackend,
    JevChoiceResult,
    JevEvaluationOutput,
    JevNoulResult,
    JevScoreResult,
    MockJevBackend,
    calculate_expected_score,
    normalize_noul_probs,
)


def test_normalize_noul_probs_equal():
    p = normalize_noul_probs(logprob_yes=-0.6931, logprob_no=-0.6931)
    assert p == pytest.approx(0.5, abs=1e-3)


def test_normalize_noul_probs_high_yes():
    # log(0.9) = -0.1053, log(0.1) = -2.3025
    p = normalize_noul_probs(logprob_yes=-0.1053, logprob_no=-2.3025)
    assert p == pytest.approx(0.9, abs=1e-3)


def test_calculate_expected_score_ten_levels():
    # Uniform across level 8 and level 10: expected level 9 -> score 90.0
    probs = {8: 0.5, 10: 0.5}
    score = calculate_expected_score(probs, scale_factor=10.0)
    assert score == pytest.approx(90.0)


def test_mock_jev_backend_returns_calibrated_primitives():
    backend = MockJevBackend(
        score_level=8,
        noul_pass_prob=0.88,
        noul_grounding_prob=0.95,
        choice_label="FLAWLESS_CONTAINMENT",
    )
    score_res = backend.evaluate_score("State", num_levels=10)
    assert score_res.expected_score == pytest.approx(80.0)

    pass_res = backend.evaluate_noul("State", question="Did the agent pass?")
    assert pass_res.probability == pytest.approx(0.88)
    assert pass_res.verdict is True

    choice_res = backend.evaluate_choice(
        "State",
        question="Failure mode?",
        options={"A": "FLAWLESS_CONTAINMENT", "B": "MISSED_BREACH"},
    )
    assert choice_res.selected == "FLAWLESS_CONTAINMENT"
