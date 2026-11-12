"""Unit tests for the Gemini Decisions API Jev backend (hermetic, no network)."""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
from typing import Any

import pytest

from agent import jev_backend_decisions_api as da
from agent.jev_backend_decisions_api import (
    BACKEND_NAME,
    CHOICE_QUESTION_KEY,
    DEFAULT_ENDPOINT_URL,
    DEFAULT_MODEL,
    FAILURE_MODE_DESCRIPTIONS,
    GROUNDING_QUESTION_KEY,
    NOUL_MAX_PROB,
    NOUL_MIN_PROB,
    PASS_QUESTION_KEY,
    SCORE_LEVEL_DESCRIPTIONS,
    SCORE_QUESTION_KEY,
    DecisionsApiJevBackend,
    DecisionsApiSafetyError,
    DecisionsApiValidationError,
    build_decisions_api_backend,
    build_soc_batch_questions,
    describe_decisions_api_backend,
    detect_sdk_decisions_support,
    register_decisions_api_backend,
    resolve_jev_backend,
)
from agent.jev_backends import JEV_BACKEND_CHOICES
from agent.jev_evaluator import (
    JevSocJudgeEvaluator,
    build_soc_evaluation_state,
)
from agent.jev_judge import BaseJevBackend, MockJevBackend
from scripts import spike_decisions_api_judge


def _make_sample_state(step_count: int = 2) -> str:
    trajectory = [
        {
            "step": i + 1,
            "tool": f"lookup_{i + 1}",
            "args": {"ioc": f"198.51.100.{i + 10}"},
            "observation": "Confirmed malicious C2 beacon",
        }
        for i in range(step_count)
    ]
    return build_soc_evaluation_state(
        prompt="Alert: outbound C2 traffic from WS-01 to 198.51.100.10",
        response="Verdict: MALICIOUS. Isolated WS-01 and blocked 198.51.100.10.",
        reference={"ground_truth_label": "MALICIOUS", "required_actions": ["isolate_host"]},
        rubric="Isolate WS-01 after verifying the indicator.",
        trajectory=trajectory,
    )


def _mock_batch_response(
    *,
    score_probs: dict[str, float] | None = None,
    noul_grounding: float = 0.96,
    noul_pass: float = 0.92,
    choice: str = "FLAWLESS_CONTAINMENT",
    choice_probs: dict[str, float] | None = None,
    input_tokens: int = 420,
) -> dict[str, Any]:
    s_probs = {str(i): 0.0 for i in range(11)}
    if score_probs is None:
        s_probs.update({"8": 0.4, "9": 0.6})
    else:
        s_probs.update(score_probs)
    expected_score = sum(int(k) * v for k, v in s_probs.items())
    c_probs = choice_probs or {
        "FLAWLESS_CONTAINMENT": 0.85,
        "UNGROUNDED_HALLUCINATED_CLAIM": 0.03,
        "MISSED_MALICIOUS_BREACH": 0.02,
        "OVER_CONTAINMENT_FALSE_ALARM": 0.03,
        "PREMATURE_TERMINATION_ZERO_TOOLS": 0.02,
        "RUNBOOK_PROCEDURAL_VIOLATION": 0.03,
        "DEGRADED_MODE_FAILURE": 0.02,
    }
    return {
        "answers": {
            SCORE_QUESTION_KEY: {
                "type": "score",
                "score": expected_score,
                "probabilities": s_probs,
                "confidence": max(s_probs.values()),
            },
            GROUNDING_QUESTION_KEY: {
                "type": "noul",
                "noul": noul_grounding,
                "confidence": max(noul_grounding, 1.0 - noul_grounding),
            },
            PASS_QUESTION_KEY: {
                "type": "noul",
                "noul": noul_pass,
                "confidence": max(noul_pass, 1.0 - noul_pass),
            },
            CHOICE_QUESTION_KEY: {
                "type": "choice",
                "choice": choice,
                "probabilities": c_probs,
                "confidence": max(c_probs.values()),
            },
        },
        "usage": {
            "total_input_tokens": input_tokens,
            "input_tokens_by_modality": [{"modality": "text", "tokens": input_tokens}],
            "total_output_tokens": 0,
            "total_tokens": input_tokens,
        },
    }


def test_backend_implements_base_contract_and_defaults():
    backend = DecisionsApiJevBackend(api_key="test-key", transport=lambda p: _mock_batch_response())
    assert isinstance(backend, BaseJevBackend)
    assert backend.model == DEFAULT_MODEL == "gemini-decision-1"
    assert backend.endpoint_url == DEFAULT_ENDPOINT_URL
    info = backend.describe()
    assert info["backend"] == BACKEND_NAME
    assert info["model"] == "gemini-decision-1"
    assert info["transport_mode"] == "custom_transport"
    assert info["context_window_tokens"] == 262_144


def test_single_batched_prefill_serves_all_four_evaluator_primitives():
    calls: list[dict[str, Any]] = []

    def transport(payload: dict[str, Any]) -> dict[str, Any]:
        calls.append(payload)
        return _mock_batch_response()

    backend = DecisionsApiJevBackend(api_key="test-key", transport=transport)
    evaluator = JevSocJudgeEvaluator(backend=backend)
    state = _make_sample_state(step_count=1)

    out = evaluator.evaluate_case(
        prompt="Alert: outbound C2 traffic from WS-01 to 198.51.100.10",
        response="Verdict: MALICIOUS. Isolated WS-01 and blocked 198.51.100.10.",
        reference={"ground_truth_label": "MALICIOUS", "required_actions": ["isolate_host"]},
        rubric="Isolate WS-01 after verifying the indicator.",
        trajectory=[
            {
                "step": 1,
                "tool": "lookup_1",
                "args": {"ioc": "198.51.100.10"},
                "observation": "Confirmed malicious C2 beacon",
            }
        ],
    )

    assert len(calls) == 1
    sent_questions = calls[0]["questions"]
    assert set(sent_questions) == {
        SCORE_QUESTION_KEY,
        GROUNDING_QUESTION_KEY,
        PASS_QUESTION_KEY,
        CHOICE_QUESTION_KEY,
    }
    assert calls[0]["model"] == "gemini-decision-1"
    assert len(sent_questions[SCORE_QUESTION_KEY]["criteria"]) == 11
    assert set(sent_questions[CHOICE_QUESTION_KEY]["criteria"]) == set(FAILURE_MODE_DESCRIPTIONS)
    assert "none_of_the_above" not in sent_questions[CHOICE_QUESTION_KEY]["criteria"]

    # Score: 0.4 * 8 + 0.6 * 9 = 8.6 -> 86.0
    assert out.rubric_score == pytest.approx(86.0)
    assert out.passed is True
    assert out.grounding_score == pytest.approx(0.96)
    assert out.primary_choice == "FLAWLESS_CONTAINMENT"
    assert backend.stats["requests_sent"] == 1
    assert backend.stats["total_output_tokens"] == 0
    assert backend.stats["total_input_tokens"] == 420
    assert "noul_derivations" in out.raw_metadata
    assert out.raw_metadata["noul_derivations"]["pass"]["source"] == "batched_prefill"

    # Re-evaluating the exact same state hits cache without another request.
    _ = backend.evaluate_score(state)
    _ = backend.evaluate_noul(state, da.PASS_INSTRUCTIONS)
    assert len(calls) == 1
    assert backend.stats["cache_hits"] == 5
    semantic = JevSocJudgeEvaluator.to_semantic_judge_result(out)
    assert set(semantic) == {"rubric_score", "passed", "grounding_score", "critique"}


def test_lru_cache_eviction_bounds_memory():
    calls: list[str] = []

    def transport(payload: dict[str, Any]) -> dict[str, Any]:
        calls.append(payload["input"])
        return _mock_batch_response()

    backend = DecisionsApiJevBackend(api_key="k", cache_size=2, transport=transport)
    s1, s2, s3 = _make_sample_state(1), _make_sample_state(2), _make_sample_state(3)
    backend.evaluate_score(s1)
    backend.evaluate_score(s2)
    backend.evaluate_score(s3)
    assert len(calls) == 3
    backend.evaluate_score(s3)
    assert len(calls) == 3
    backend.evaluate_score(s1)
    assert len(calls) == 4


def test_noul_clamping_and_threshold_bounds():
    with pytest.raises(ValueError, match="0.01"):
        DecisionsApiJevBackend(pass_threshold=0.0)
    with pytest.raises(ValueError, match="0.99"):
        DecisionsApiJevBackend(grounding_threshold=0.999)

    def transport(payload: dict[str, Any]) -> dict[str, Any]:
        if "custom_noul" in payload["questions"]:
            return {
                "answers": {
                    "custom_noul": {"type": "noul", "noul": 1.0, "confidence": 1.0}
                },
                "usage": {"total_input_tokens": 50, "total_output_tokens": 0},
            }
        return _mock_batch_response(noul_grounding=0.0, noul_pass=0.995)

    backend = DecisionsApiJevBackend(
        api_key="k",
        pass_threshold=0.99,
        grounding_threshold=0.01,
        transport=transport,
    )
    state = _make_sample_state()
    g_res = backend.evaluate_noul(state, da.GROUNDING_INSTRUCTIONS)
    p_res = backend.evaluate_noul(state, da.PASS_INSTRUCTIONS)
    custom_res = backend.evaluate_noul(state, "Did the analyst mention DNS logs?")

    assert g_res.probability == pytest.approx(NOUL_MIN_PROB)
    assert g_res.verdict is True
    assert p_res.probability == pytest.approx(NOUL_MAX_PROB)
    assert p_res.verdict is True
    assert custom_res.probability == pytest.approx(NOUL_MAX_PROB)
    assert custom_res.details["source"] == "direct_noul"


def test_choice_rejects_none_of_the_above_and_supports_custom_options():
    calls: list[dict[str, Any]] = []

    def transport(payload: dict[str, Any]) -> dict[str, Any]:
        calls.append(payload)
        return {
            "answers": {
                CHOICE_QUESTION_KEY: {
                    "type": "choice",
                    "choice": "other",
                    "probabilities": {"billing": 0.1, "technical": 0.2, "other": 0.7},
                    "confidence": 0.7,
                }
            },
            "usage": {"total_input_tokens": 80, "total_output_tokens": 0},
        }

    backend = DecisionsApiJevBackend(api_key="k", transport=transport)
    state = _make_sample_state()

    with pytest.raises(ValueError, match="none_of_the_above"):
        backend.evaluate_choice(
            state,
            "Category?",
            {"A": "billing", "B": "none_of_the_above"},
        )

    res = backend.evaluate_choice(
        state,
        "Which queue?",
        {"1": "billing", "2": "technical", "3": "other"},
    )
    assert res.selected == "other"
    assert res.candidate_probs["other"] == pytest.approx(0.7)
    assert sum(res.candidate_probs.values()) == pytest.approx(1.0)
    assert len(calls) == 1


def test_custom_num_levels_score_question():
    def transport(payload: dict[str, Any]) -> dict[str, Any]:
        criteria = payload["questions"][SCORE_QUESTION_KEY]["criteria"]
        assert len(criteria) == 5  # levels 0..4
        return {
            "answers": {
                SCORE_QUESTION_KEY: {
                    "type": "score",
                    "score": 3.0,
                    "probabilities": {"0": 0.0, "1": 0.0, "2": 0.25, "3": 0.5, "4": 0.25},
                    "confidence": 0.5,
                }
            },
            "usage": {"total_input_tokens": 60, "total_output_tokens": 0},
        }

    backend = DecisionsApiJevBackend(api_key="k", transport=transport)
    res = backend.evaluate_score(_make_sample_state(), num_levels=4)
    # Expected level = 3.0 out of 4 -> 75.0 / 100
    assert res.expected_score == pytest.approx(75.0)
    assert res.raw_level == 3


@pytest.mark.parametrize(
    "safety_code",
    ["safety", "prohibited_content", "blocklist", "image_safety", "content_blocked"],
)
def test_http_400_safety_block_raise_and_fallback_modes(monkeypatch, safety_code: str):
    err_body = json.dumps(
        {
            "error": {
                "code": safety_code,
                "message": "Request blocked due to safety violations.",
            }
        }
    ).encode("utf-8")

    def fake_urlopen(req, timeout=30.0):
        raise urllib.error.HTTPError(
            url=req.full_url,
            code=400,
            msg="Bad Request",
            hdrs={},
            fp=io.BytesIO(err_body),
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    raising_backend = DecisionsApiJevBackend(
        api_key="live-test-key",
        on_safety_block="raise",
        prefer_sdk=False,
    )
    with pytest.raises(DecisionsApiSafetyError) as exc_info:
        raising_backend.evaluate_score(_make_sample_state())
    assert exc_info.value.code == safety_code
    assert exc_info.value.status_code == 400

    fallback_backend = DecisionsApiJevBackend(
        api_key="live-test-key",
        on_safety_block="fallback",
        prefer_sdk=False,
    )
    out = JevSocJudgeEvaluator(fallback_backend).evaluate_case(
        prompt="Malware alert",
        response="Isolated host.",
        reference={},
        rubric="Isolate host.",
    )
    assert out.rubric_score == 0.0
    assert out.passed is False
    assert out.grounding_score == pytest.approx(NOUL_MIN_PROB)
    assert out.primary_choice == "DEGRADED_MODE_FAILURE"
    assert fallback_backend.stats["safety_blocked"] == 1
    assert out.raw_metadata["noul_derivations"]["pass"]["safety_blocked"]["code"] == safety_code


def test_http_400_non_safety_raises_validation_error(monkeypatch):
    err_body = json.dumps(
        {
            "error": {
                "code": "invalid_argument",
                "message": "Too many options in choice criteria.",
            }
        }
    ).encode("utf-8")

    def fake_urlopen(req, timeout=30.0):
        raise urllib.error.HTTPError(
            url=req.full_url,
            code=400,
            msg="Bad Request",
            hdrs={},
            fp=io.BytesIO(err_body),
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    backend = DecisionsApiJevBackend(api_key="k", on_safety_block="fallback", prefer_sdk=False)
    with pytest.raises(DecisionsApiValidationError, match="invalid_argument"):
        backend.evaluate_score(_make_sample_state())


def test_rest_transport_sends_x_goog_api_key_header(monkeypatch):
    captured: dict[str, Any] = {}

    class _FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return json.dumps(_mock_batch_response()).encode("utf-8")

    def fake_urlopen(req, timeout=30.0):
        captured["url"] = req.full_url
        captured["headers"] = {k.lower(): v for k, v in req.header_items()}
        captured["body"] = json.loads(req.data.decode("utf-8"))
        captured["timeout"] = timeout
        return _FakeResp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    backend = DecisionsApiJevBackend(api_key="secret-demo-key", prefer_sdk=False)
    assert backend.transport_mode() == "rest"
    res = backend.evaluate_score(_make_sample_state())
    assert res.expected_score == pytest.approx(86.0)
    assert captured["url"] == DEFAULT_ENDPOINT_URL
    assert captured["headers"]["x-goog-api-key"] == "secret-demo-key"
    assert captured["headers"]["content-type"] == "application/json"
    assert captured["body"]["model"] == "gemini-decision-1"


def test_sdk_detection_and_routing_when_client_decisions_exists():
    # main/.venv ships google-genai 2.20.0 without Client.decisions.
    sdk_info = detect_sdk_decisions_support()
    assert sdk_info["google_genai_installed"] is True
    assert sdk_info["has_client_decisions"] is False

    class _SdkAnswer:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    class _SdkResponse:
        def __init__(self, answers, usage):
            self.answers = answers
            self.usage = usage

    class _FakeDecisionsResource:
        def __init__(self):
            self.calls: list[dict[str, Any]] = []

        def create(self, *, model, input, questions):
            self.calls.append({"model": model, "input": input, "questions": questions})
            raw = _mock_batch_response()
            answers = {k: _SdkAnswer(**v) for k, v in raw["answers"].items()}
            usage = _SdkAnswer(**raw["usage"])
            return _SdkResponse(answers=answers, usage=usage)

    class _FakeSdkClient:
        def __init__(self):
            self.decisions = _FakeDecisionsResource()

    sdk_client = _FakeSdkClient()
    assert detect_sdk_decisions_support(sdk_client)["has_client_decisions"] is True

    backend = DecisionsApiJevBackend(client=sdk_client)
    assert backend.transport_mode() == "sdk"
    out = JevSocJudgeEvaluator(backend).evaluate_case(
        prompt="p",
        response="r",
        reference={},
        rubric="rb",
    )
    assert out.rubric_score == pytest.approx(86.0)
    assert len(sdk_client.decisions.calls) == 1


def test_standalone_factory_registration_and_locked_files_untouched():
    assert JEV_BACKEND_CHOICES == ("gemini_system1", "typesafe", "mock", "gliner_decide")

    registry: dict[str, Any] = {}
    register_decisions_api_backend(registry)
    assert "decisions_api" in registry
    assert "gemini_decision" in registry

    b = build_decisions_api_backend(api_key="k")
    assert isinstance(b, DecisionsApiJevBackend)
    assert describe_decisions_api_backend(b)["backend"] == BACKEND_NAME
    assert describe_decisions_api_backend(MockJevBackend()) == {"backend": "mock"}

    resolved = resolve_jev_backend("decisions_api", api_key="k")
    assert isinstance(resolved, DecisionsApiJevBackend)
    assert isinstance(resolve_jev_backend("mock"), MockJevBackend)


def test_build_soc_batch_questions_respects_api_limits():
    questions = build_soc_batch_questions()
    assert 1 <= len(questions) <= 1000
    assert len(SCORE_LEVEL_DESCRIPTIONS) == 11
    for q_key in questions:
        assert da.QUESTION_KEY_RE.match(q_key)
    for opt_key in questions[CHOICE_QUESTION_KEY]["criteria"]:
        assert 1 <= len(opt_key) <= 128
        assert opt_key == opt_key.strip()
        assert opt_key.lower() != "none_of_the_above"


def test_benchmark_script_runs_offline_and_verifies_parity(capsys):
    report = spike_decisions_api_judge.run_benchmark(split="validation", limit=2, live=False)
    assert report["mode"] == "mock"
    assert report["summary"]["decisions_api_total_output_tokens"] == 0
    assert report["summary"]["request_reduction_factor"] == pytest.approx(4.0)
    assert report["summary"]["parity_oracle_beats_degenerate"] is True

    rc = spike_decisions_api_judge.main(["--limit", "2"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Decisions API Judge Spike (mock mode)" in out
    assert "4.0x fewer HTTP calls" in out
