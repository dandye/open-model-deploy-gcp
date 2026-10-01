"""Unit tests for Gemini System-1 Logprobs Jev Backend."""

from unittest.mock import MagicMock
import pytest
from agent.jev_backend_gemini import GeminiSystem1Backend


def create_mock_gemini_client(token_probs):
    client = MagicMock()
    top_candidates = []
    for token, logprob in token_probs.items():
        tc = MagicMock()
        tc.token = token
        tc.log_probability = logprob
        top_candidates.append(tc)

    mock_logprobs_result = MagicMock()
    # 4 thoughts tokens + 1 enum token at index 4
    mock_logprobs_result.chosen_candidates = [MagicMock()] * 5
    mock_logprobs_result.top_candidates = [top_candidates]

    mock_response = MagicMock()
    mock_response.candidates = [MagicMock(logprobs_result=mock_logprobs_result)]
    mock_response.text = list(token_probs.keys())[0]
    client.models.generate_content.return_value = mock_response
    return client


def test_gemini_system1_evaluate_noul():
    # YES: -0.223 (0.80), NO: -1.609 (0.20)
    mock_client = create_mock_gemini_client({"YES": -0.223, "NO": -1.609})
    backend = GeminiSystem1Backend(project_id="test-proj", client=mock_client)
    res = backend.evaluate_noul("State context", "Did agent contain incident?")
    assert res.probability == pytest.approx(0.80, abs=0.05)
    assert res.verdict is True


def test_gemini_system1_evaluate_score():
    # 8: -0.356, 9: -1.204
    mock_client = create_mock_gemini_client({"8": -0.356, "9": -1.204})
    backend = GeminiSystem1Backend(project_id="test-proj", client=mock_client)
    res = backend.evaluate_score("State context", num_levels=10)
    assert 80.0 <= res.expected_score <= 90.0
