"""Unit tests for TypeSafe AI Jev Remote HTTP Client Backend."""

from unittest.mock import MagicMock, patch
import pytest
from agent.jev_backend_typesafe import TypeSafeJevBackend


@patch("urllib.request.urlopen")
def test_typesafe_jev_evaluate_noul(mock_urlopen):
    mock_resp = MagicMock()
    mock_resp.read.return_value = (
        b'{"results": [{"primitive": "noul", "probability": 0.94, "verdict": true}]}'
    )
    mock_urlopen.return_value.__enter__.return_value = mock_resp

    backend = TypeSafeJevBackend(api_key="test-key")
    res = backend.evaluate_noul("State text", "Is this response grounded?")
    assert res.probability == 0.94
    assert res.verdict is True


@patch("urllib.request.urlopen")
def test_typesafe_jev_evaluate_score(mock_urlopen):
    mock_resp = MagicMock()
    mock_resp.read.return_value = (
        b'{"results": [{"primitive": "score", "expected_value": 8.5, "distribution": {"8": 0.5, "9": 0.5}}]}'
    )
    mock_urlopen.return_value.__enter__.return_value = mock_resp

    backend = TypeSafeJevBackend(api_key="test-key")
    res = backend.evaluate_score("State text", num_levels=10)
    assert res.expected_score == 85.0
