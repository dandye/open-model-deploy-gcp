"""Gemini Decisions API (gemini-decision-1) backend implementing Jev primitives.

Evaluates the four SOC judge primitives (one Score, two Noul gates, and one
7-way Choice) over the same serialized state in a single batched prefill call
against ``POST https://generativelanguage.googleapis.com/v1beta/decisions`` with
zero output tokens.

SDK compatibility: ``main/.venv`` currently pins ``google-genai==2.20.0``
without ``Client.decisions`` (introduced in SDK 3.2+). This module detects SDK
support at runtime and falls back cleanly to the REST endpoint via ``urllib``
using ``x-goog-api-key``.

Harness lock safety: ``agent/jev_backends.py`` and ``tests/test_jev_backends.py``
are left untouched; use ``build_decisions_api_backend``,
``register_decisions_api_backend``, or ``resolve_jev_backend`` from this module
to construct or register the backend.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import re
import time
import urllib.error
import urllib.request
from collections import OrderedDict
from collections.abc import Callable, Mapping
from typing import Any

from agent.jev_backends import build_jev_backend, describe_jev_backend
from agent.jev_evaluator import SOC_FAILURE_TAXONOMY
from agent.jev_judge import (
    BaseJevBackend,
    JevChoiceResult,
    JevNoulResult,
    JevScoreResult,
    calculate_expected_score,
)

BACKEND_NAME = "decisions_api"
DEFAULT_MODEL = "gemini-decision-1"
DEFAULT_ENDPOINT_URL = "https://generativelanguage.googleapis.com/v1beta/decisions"
DEFAULT_API_VERSION = "v1beta"
DEFAULT_CONTEXT_WINDOW_TOKENS = 262_144
MAX_QUESTIONS_PER_REQUEST = 1000
MAX_CHOICE_OPTIONS = 255
MAX_SCORE_LEVELS = 255
NOUL_MIN_PROB = 0.01
NOUL_MAX_PROB = 0.99
DEFAULT_PASS_THRESHOLD = 0.70
DEFAULT_GROUNDING_THRESHOLD = 0.70
DEFAULT_CACHE_SIZE = 16
DEFAULT_TIMEOUT_S = 30.0

SAFETY_BLOCK_CODES = frozenset(
    {
        "safety",
        "prohibited_content",
        "blocklist",
        "image_safety",
        "content_blocked",
    }
)
FORBIDDEN_CHOICE_KEYS = frozenset({"none_of_the_above"})
QUESTION_KEY_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

SCORE_QUESTION_KEY = "rubric_score"
GROUNDING_QUESTION_KEY = "noul_grounding"
PASS_QUESTION_KEY = "noul_pass"
CHOICE_QUESTION_KEY = "failure_mode"

GROUNDING_KEYWORDS = ("ground", "corroborat", "hallucinat")
PASS_KEYWORDS = (
    "mandatory soc triage",
    "containment standards",
    "did the agent satisfy",
    "did the agent pass",
)

SCORE_INSTRUCTIONS = (
    "On an ordered operational grading scale from 0 (total failure) to 10 "
    "(flawless expert containment), rate the agent response and tool execution "
    "trajectory against the operational grading rubric and ground truth reference."
)
SCORE_LEVEL_DESCRIPTIONS: tuple[str, ...] = (
    "0: Total operational failure, inert response, or dangerous ungrounded action.",
    "1: Severe failure with missed threat or prohibited destructive action.",
    "2: Major failure with critical omissions and uncorroborated claims.",
    "3: Poor triage missing essential enrichment and required verdict.",
    "4: Weak investigation with substantial procedural or grounding gaps.",
    "5: Partial triage with mixed evidence and incomplete containment.",
    "6: Fair triage identifying core issue but missing secondary actions.",
    "7: Acceptable triage meeting basic standards with minor gaps.",
    "8: Good triage with sound tool corroboration and accurate verdict.",
    "9: Strong containment with thorough grounding and clean execution.",
    "10: Flawless expert containment fully grounded in tool observations.",
)

GROUNDING_INSTRUCTIONS = (
    "Are all claims, IOC classifications, and forensic assertions in the agent "
    "response strictly grounded and corroborated by the actual tool execution "
    "trajectory without hallucination?"
)
GROUNDING_CRITERIA: dict[str, str] = {
    "true_description": (
        "Every cited indicator, entity, timestamp, and forensic claim is directly "
        "supported by the alert prompt or recorded tool observations."
    ),
    "false_description": (
        "At least one claim, indicator, or tool outcome in the response is "
        "fabricated, contradicted, or unsupported by tool observations."
    ),
}

PASS_INSTRUCTIONS = (
    "Did the agent satisfy mandatory SOC triage and containment standards for "
    "this incident without fatal operational errors?"
)
PASS_CRITERIA: dict[str, str] = {
    "true_description": (
        "The agent investigated with tools, reached an accurate verdict, and "
        "executed required actions without violating safety or runbook rules."
    ),
    "false_description": (
        "The agent missed a real threat, over-contained a benign asset, acted "
        "without tools, or violated mandatory operational standards."
    ),
}

CHOICE_INSTRUCTIONS = (
    "Which category best describes the agent's primary operational performance "
    "or failure mode?"
)
FAILURE_MODE_DESCRIPTIONS: dict[str, str] = {
    "FLAWLESS_CONTAINMENT": (
        "The agent investigated with tools, reached the correct verdict, and took "
        "the exact required containment or closure action."
    ),
    "UNGROUNDED_HALLUCINATED_CLAIM": (
        "The agent asserted facts, indicators, or tool observations not supported "
        "by the actual trajectory."
    ),
    "MISSED_MALICIOUS_BREACH": (
        "The agent treated a real threat as benign or closed the incident without "
        "required containment."
    ),
    "OVER_CONTAINMENT_FALSE_ALARM": (
        "The agent isolated hosts or blocked indicators that were benign, "
        "authorized, or prohibited."
    ),
    "PREMATURE_TERMINATION_ZERO_TOOLS": (
        "The agent terminated without investigating or invoked zero meaningful "
        "enrichment tools."
    ),
    "RUNBOOK_PROCEDURAL_VIOLATION": (
        "The agent skipped, misordered, or violated mandatory SOC runbook steps "
        "or decision schema requirements."
    ),
    "DEGRADED_MODE_FAILURE": (
        "The agent failed to adapt cleanly when a tool was unavailable, timed out, "
        "or returned an error."
    ),
}


class DecisionsApiError(RuntimeError):
    """Base error raised for Decisions API transport or response failures."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        code: str | None = None,
        payload: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.payload = payload or {}


class DecisionsApiSafetyError(DecisionsApiError):
    """Raised when the Decisions API rejects input with an HTTP 400 safety block."""


class DecisionsApiValidationError(DecisionsApiError):
    """Raised for client-side or HTTP 400 schema/limit validation failures."""


def detect_sdk_decisions_support(client: Any | None = None) -> dict[str, Any]:
    """Detects whether ``google-genai`` exposes ``Client.decisions.create`` (SDK >= 3.2)."""
    version: str | None = None
    installed = False
    try:
        version = importlib.metadata.version("google-genai")
        installed = True
    except importlib.metadata.PackageNotFoundError:
        pass

    has_decisions = False
    if client is not None:
        decisions_attr = getattr(client, "decisions", None)
        has_decisions = callable(getattr(decisions_attr, "create", None))
    else:
        try:
            from google import genai  # type: ignore

            client_cls = getattr(genai, "Client", None)
            has_decisions = bool(client_cls is not None and hasattr(client_cls, "decisions"))
        except (ImportError, AttributeError):
            has_decisions = False

    return {
        "google_genai_installed": installed,
        "version": version,
        "has_client_decisions": has_decisions,
    }


def clamp_noul_probability(value: float) -> float:
    """Clamps a Decisions API noul probability to the documented [0.01, 0.99] band."""
    return min(max(float(value), NOUL_MIN_PROB), NOUL_MAX_PROB)


def _validate_threshold(value: float, name: str) -> float:
    val = float(value)
    if not (NOUL_MIN_PROB <= val <= NOUL_MAX_PROB):
        raise ValueError(
            f"{name} must sit within [{NOUL_MIN_PROB}, {NOUL_MAX_PROB}] because "
            f"Decisions API noul probabilities never leave that band; got {value!r}."
        )
    return val


def _validate_question_key(key: str) -> str:
    if not QUESTION_KEY_RE.match(key):
        raise ValueError(
            f"Invalid Decisions API question key {key!r}: must match {QUESTION_KEY_RE.pattern}."
        )
    return key


def _validate_choice_criteria(criteria: Mapping[str, str]) -> dict[str, str]:
    if not (2 <= len(criteria) <= MAX_CHOICE_OPTIONS):
        raise ValueError(
            f"Decisions API choice criteria requires 2 to {MAX_CHOICE_OPTIONS} options; "
            f"got {len(criteria)}."
        )
    cleaned: dict[str, str] = {}
    for raw_key, raw_desc in criteria.items():
        key = str(raw_key)
        if not key or len(key) > 128 or len(key.encode("utf-8")) > 512:
            raise ValueError(f"Invalid Decisions API option key {key!r}: must be 1..128 chars (<=512 UTF-8 bytes).")
        if key != key.strip() or any(ord(ch) < 32 for ch in key):
            raise ValueError(f"Invalid Decisions API option key {key!r}: leading/trailing spaces or control chars disallowed.")
        if key.lower() in FORBIDDEN_CHOICE_KEYS:
            raise ValueError(
                f"Option key {key!r} is disallowed: Decisions API sorts option keys alphabetically, "
                "which places positional keys ahead of later options. Use explicit categories or 'other'."
            )
        cleaned[key] = str(raw_desc)
    return cleaned


def _validate_score_criteria(criteria: tuple[str, ...] | list[str]) -> list[str]:
    levels = [str(item).strip() for item in criteria]
    if not (2 <= len(levels) <= MAX_SCORE_LEVELS):
        raise ValueError(
            f"Decisions API score criteria requires 2 to {MAX_SCORE_LEVELS} levels; got {len(levels)}."
        )
    if any(not lvl for lvl in levels):
        raise ValueError("Decisions API score criteria levels must all be non-empty strings.")
    return levels


def _build_score_levels(num_levels: int) -> list[str]:
    if num_levels == 10:
        return list(SCORE_LEVEL_DESCRIPTIONS)
    if not (1 <= num_levels <= MAX_SCORE_LEVELS - 1):
        raise ValueError(
            f"num_levels must be between 1 and {MAX_SCORE_LEVELS - 1}; got {num_levels}."
        )
    return [f"Level {idx} of {num_levels} on the ordered operational rubric." for idx in range(num_levels + 1)]


def _normalize_sdk_answer(answer: Any) -> dict[str, Any]:
    if isinstance(answer, Mapping):
        return dict(answer)
    out: dict[str, Any] = {}
    for attr in ("type", "noul", "choice", "score", "confidence", "probabilities", "legend"):
        val = getattr(answer, attr, None)
        if val is not None:
            out[attr] = dict(val) if isinstance(val, Mapping) else val
    return out


def _normalize_sdk_response(response: Any) -> dict[str, Any]:
    if isinstance(response, Mapping):
        return dict(response)
    raw_answers = getattr(response, "answers", None) or {}
    answers = {str(k): _normalize_sdk_answer(v) for k, v in raw_answers.items()}
    usage_obj = getattr(response, "usage", None)
    usage: dict[str, Any] = {}
    if isinstance(usage_obj, Mapping):
        usage = dict(usage_obj)
    elif usage_obj is not None:
        for attr in ("total_input_tokens", "total_output_tokens", "total_tokens", "input_tokens_by_modality"):
            val = getattr(usage_obj, attr, None)
            if val is not None:
                usage[attr] = val
    return {"answers": answers, "usage": usage}


def _parse_error_payload(raw_body: str) -> tuple[str | None, str, dict[str, Any]]:
    try:
        parsed = json.loads(raw_body) if raw_body else {}
    except json.JSONDecodeError:
        return None, raw_body or "Unknown Decisions API error", {}
    if not isinstance(parsed, dict):
        return None, str(parsed), {}
    err = parsed.get("error")
    if isinstance(err, dict):
        code = err.get("code")
        msg = str(err.get("message") or raw_body)
        return (str(code) if code is not None else None), msg, parsed
    return None, raw_body, parsed


def build_soc_batch_questions(
    num_levels: int = 10,
    choice_criteria: Mapping[str, str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Builds the 4-question SOC judge payload evaluated in one Decisions API prefill pass."""
    score_levels = _validate_score_criteria(_build_score_levels(num_levels))
    choice_map = _validate_choice_criteria(choice_criteria or FAILURE_MODE_DESCRIPTIONS)
    questions = {
        SCORE_QUESTION_KEY: {
            "type": "score",
            "instructions": SCORE_INSTRUCTIONS,
            "criteria": score_levels,
        },
        GROUNDING_QUESTION_KEY: {
            "type": "noul",
            "instructions": GROUNDING_INSTRUCTIONS,
            "criteria": dict(GROUNDING_CRITERIA),
        },
        PASS_QUESTION_KEY: {
            "type": "noul",
            "instructions": PASS_INSTRUCTIONS,
            "criteria": dict(PASS_CRITERIA),
        },
        CHOICE_QUESTION_KEY: {
            "type": "choice",
            "instructions": CHOICE_INSTRUCTIONS,
            "criteria": choice_map,
        },
    }
    for key in questions:
        _validate_question_key(key)
    return questions


class DecisionsApiJevBackend(BaseJevBackend):
    """Jev System-One backend powered by Gemini Decisions API (``gemini-decision-1``).

    A single ``JevSocJudgeEvaluator.evaluate_case`` call invokes ``evaluate_score``,
    ``evaluate_noul`` (grounding), ``evaluate_noul`` (pass), and ``evaluate_choice``
    over the same state. This backend batches those four standard primitives into
    one ``POST /v1beta/decisions`` request per state (cached in a bounded LRU)
    with ``total_output_tokens == 0``.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        endpoint_url: str = DEFAULT_ENDPOINT_URL,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        pass_threshold: float = DEFAULT_PASS_THRESHOLD,
        grounding_threshold: float = DEFAULT_GROUNDING_THRESHOLD,
        on_safety_block: str = "fallback",
        cache_size: int = DEFAULT_CACHE_SIZE,
        client: Any | None = None,
        transport: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        prefer_sdk: bool = True,
    ):
        self.api_key = (
            api_key
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
            or ""
        )
        self.model = model
        self.endpoint_url = endpoint_url
        self.timeout_s = float(timeout_s)
        self.pass_threshold = _validate_threshold(pass_threshold, "pass_threshold")
        self.grounding_threshold = _validate_threshold(grounding_threshold, "grounding_threshold")
        if on_safety_block not in ("fallback", "raise"):
            raise ValueError(f"on_safety_block must be 'fallback' or 'raise'; got {on_safety_block!r}.")
        self.on_safety_block = on_safety_block
        self.cache_size = max(1, int(cache_size))
        self.client = client
        self.transport = transport
        self.prefer_sdk = bool(prefer_sdk)

        self._cache: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self.stats: dict[str, Any] = {
            "requests_sent": 0,
            "cache_hits": 0,
            "safety_blocked": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_latency_ms": 0.0,
        }

    def transport_mode(self) -> str:
        """Reports which transport path this instance will execute."""
        if self.transport is not None:
            return "custom_transport"
        if self.client is not None and detect_sdk_decisions_support(self.client)["has_client_decisions"]:
            return "sdk"
        if self.prefer_sdk and detect_sdk_decisions_support()["has_client_decisions"]:
            return "sdk"
        return "rest"

    def describe(self) -> dict[str, Any]:
        """Static judge provenance for run metadata and experiment logs."""
        return {
            "backend": BACKEND_NAME,
            "model": self.model,
            "endpoint_url": self.endpoint_url,
            "transport_mode": self.transport_mode(),
            "context_window_tokens": DEFAULT_CONTEXT_WINDOW_TOKENS,
            "pass_threshold": self.pass_threshold,
            "grounding_threshold": self.grounding_threshold,
            "on_safety_block": self.on_safety_block,
            "sdk_support": detect_sdk_decisions_support(self.client),
        }

    def _ensure_sdk_client(self) -> Any:
        if self.client is not None:
            return self.client
        from google import genai  # type: ignore

        kwargs: dict[str, Any] = {"http_options": {"api_version": DEFAULT_API_VERSION}}
        if self.api_key:
            kwargs["api_key"] = self.api_key
        self.client = genai.Client(**kwargs)
        return self.client

    def _post_rest(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            raise DecisionsApiValidationError(
                "GEMINI_API_KEY (or GOOGLE_API_KEY) is required for live Decisions API REST calls.",
                code="missing_api_key",
            )
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint_url,
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raw_err = exc.read().decode("utf-8", errors="replace")
            code, msg, parsed = _parse_error_payload(raw_err)
            if exc.code == 400 and code and code.lower() in SAFETY_BLOCK_CODES:
                raise DecisionsApiSafetyError(
                    f"Decisions API input blocked by safety filter ({code}): {msg}",
                    status_code=400,
                    code=code,
                    payload=parsed,
                ) from exc
            if exc.code == 400:
                raise DecisionsApiValidationError(
                    f"Decisions API HTTP 400 ({code or 'bad_request'}): {msg}",
                    status_code=400,
                    code=code,
                    payload=parsed,
                ) from exc
            raise DecisionsApiError(
                f"Decisions API HTTP {exc.code}: {msg}",
                status_code=exc.code,
                code=code,
                payload=parsed,
            ) from exc
        except urllib.error.URLError as exc:
            raise DecisionsApiError(f"Decisions API connection failed: {exc}") from exc

    def call_decisions_api(
        self,
        state: str,
        questions: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, Any]:
        """Executes a single Decisions API call over ``state`` and ``questions``."""
        if not isinstance(state, str) or not state.strip():
            raise DecisionsApiValidationError("Decisions API input state cannot be empty.", code="empty_input")
        if not (1 <= len(questions) <= MAX_QUESTIONS_PER_REQUEST):
            raise DecisionsApiValidationError(
                f"Decisions API accepts 1 to {MAX_QUESTIONS_PER_REQUEST} questions per request; got {len(questions)}.",
                code="too_many_questions",
            )
        for key in questions:
            _validate_question_key(key)

        payload: dict[str, Any] = {
            "model": self.model,
            "input": state,
            "questions": dict(questions),
        }

        t0 = time.perf_counter()
        mode = self.transport_mode()
        if mode == "custom_transport":
            assert self.transport is not None
            raw = self.transport(payload)
            if isinstance(raw, Mapping) and isinstance(raw.get("error"), Mapping):
                err = raw["error"]
                code = str(err.get("code") or "error")
                msg = str(err.get("message") or "Decisions API error")
                if code.lower() in SAFETY_BLOCK_CODES:
                    raise DecisionsApiSafetyError(
                        f"Decisions API input blocked by safety filter ({code}): {msg}",
                        status_code=400,
                        code=code,
                        payload=dict(raw),
                    )
                raise DecisionsApiValidationError(
                    f"Decisions API error ({code}): {msg}",
                    status_code=400,
                    code=code,
                    payload=dict(raw),
                )
            normalized = _normalize_sdk_response(raw)
        elif mode == "sdk":
            client = self._ensure_sdk_client()
            raw = client.decisions.create(
                model=self.model,
                input=state,
                questions=dict(questions),
            )
            normalized = _normalize_sdk_response(raw)
        else:
            normalized = _normalize_sdk_response(self._post_rest(payload))

        latency_ms = round((time.perf_counter() - t0) * 1000.0, 3)
        usage = normalized.get("usage") or {}
        self.stats["requests_sent"] += 1
        self.stats["total_input_tokens"] += int(usage.get("total_input_tokens", 0) or 0)
        self.stats["total_output_tokens"] += int(usage.get("total_output_tokens", 0) or 0)
        self.stats["total_latency_ms"] += latency_ms
        normalized["latency_ms"] = latency_ms
        return normalized

    def _safety_fallback_response(self, exc: DecisionsApiSafetyError) -> dict[str, Any]:
        self.stats["safety_blocked"] += 1
        probs = {str(i): (1.0 if i == 0 else 0.0) for i in range(11)}
        choice_probs = {
            label: (1.0 if label == "DEGRADED_MODE_FAILURE" else 0.0)
            for label in FAILURE_MODE_DESCRIPTIONS
        }
        return {
            "answers": {
                SCORE_QUESTION_KEY: {
                    "type": "score",
                    "score": 0.0,
                    "probabilities": probs,
                    "confidence": 1.0,
                },
                GROUNDING_QUESTION_KEY: {
                    "type": "noul",
                    "noul": NOUL_MIN_PROB,
                    "confidence": NOUL_MAX_PROB,
                },
                PASS_QUESTION_KEY: {
                    "type": "noul",
                    "noul": NOUL_MIN_PROB,
                    "confidence": NOUL_MAX_PROB,
                },
                CHOICE_QUESTION_KEY: {
                    "type": "choice",
                    "choice": "DEGRADED_MODE_FAILURE",
                    "probabilities": choice_probs,
                    "confidence": 1.0,
                },
            },
            "usage": {"total_input_tokens": 0, "total_output_tokens": 0, "total_tokens": 0},
            "latency_ms": 0.0,
            "safety_blocked": {
                "code": exc.code,
                "message": exc.message,
                "status_code": exc.status_code,
            },
        }

    def evaluate_soc_batch(self, state: str) -> dict[str, Any]:
        """Evaluates all 4 standard SOC primitives in one cached batched request."""
        key = hashlib.sha256(state.encode("utf-8")).hexdigest()
        cached = self._cache.get(key)
        if cached is not None:
            self._cache.move_to_end(key)
            self.stats["cache_hits"] += 1
            return cached

        questions = build_soc_batch_questions(num_levels=10)
        try:
            entry = self.call_decisions_api(state, questions)
        except DecisionsApiSafetyError as exc:
            if self.on_safety_block == "raise":
                raise
            entry = self._safety_fallback_response(exc)

        self._cache[key] = entry
        while len(self._cache) > self.cache_size:
            self._cache.popitem(last=False)
        return entry

    def get_cached_batch_metadata(self, state: str) -> dict[str, Any] | None:
        """Returns cached raw response metadata (usage, latency_ms, confidences) for ``state``."""
        key = hashlib.sha256(state.encode("utf-8")).hexdigest()
        return self._cache.get(key)

    @staticmethod
    def _parse_score_answer(answer: Mapping[str, Any], num_levels: int) -> JevScoreResult:
        raw_probs = answer.get("probabilities") or {}
        level_probs: dict[int, float] = {}
        for idx in range(num_levels + 1):
            level_probs[idx] = float(raw_probs.get(str(idx), raw_probs.get(idx, 0.0)))
        total_p = sum(level_probs.values())
        scale_factor = 100.0 / float(num_levels)
        if total_p > 0.0:
            norm_probs = {k: v / total_p for k, v in level_probs.items()}
            expected_score = calculate_expected_score(norm_probs, scale_factor=scale_factor)
            raw_level = max(norm_probs.items(), key=lambda kv: kv[1])[0]
            return JevScoreResult(
                expected_score=expected_score,
                level_probs=level_probs,
                raw_level=raw_level,
            )
        api_score = float(answer.get("score", 0.0))
        return JevScoreResult(
            expected_score=round(api_score * scale_factor, 2),
            level_probs=level_probs,
            raw_level=round(api_score),
        )

    def evaluate_score(self, state: str, num_levels: int = 10) -> JevScoreResult:
        if num_levels == 10:
            entry = self.evaluate_soc_batch(state)
            ans = entry["answers"][SCORE_QUESTION_KEY]
            return self._parse_score_answer(ans, num_levels=10)

        levels = _validate_score_criteria(_build_score_levels(num_levels))
        questions = {
            SCORE_QUESTION_KEY: {
                "type": "score",
                "instructions": SCORE_INSTRUCTIONS,
                "criteria": levels,
            }
        }
        try:
            res = self.call_decisions_api(state, questions)
            ans = res["answers"][SCORE_QUESTION_KEY]
        except DecisionsApiSafetyError:
            if self.on_safety_block == "raise":
                raise
            self.stats["safety_blocked"] += 1
            ans = {
                "type": "score",
                "score": 0.0,
                "probabilities": {str(i): (1.0 if i == 0 else 0.0) for i in range(num_levels + 1)},
            }
        return self._parse_score_answer(ans, num_levels=num_levels)

    def evaluate_noul(self, state: str, question: str) -> JevNoulResult:
        q_lower = question.lower()
        is_grounding = question.strip() == GROUNDING_INSTRUCTIONS or any(
            kw in q_lower for kw in GROUNDING_KEYWORDS
        )
        is_pass = question.strip() == PASS_INSTRUCTIONS or any(
            kw in q_lower for kw in PASS_KEYWORDS
        )

        if is_grounding or is_pass:
            entry = self.evaluate_soc_batch(state)
            q_key = GROUNDING_QUESTION_KEY if is_grounding else PASS_QUESTION_KEY
            threshold = self.grounding_threshold if is_grounding else self.pass_threshold
            ans = entry["answers"][q_key]
            prob = clamp_noul_probability(float(ans.get("noul", 0.5)))
            details: dict[str, Any] = {
                "source": "batched_prefill",
                "question_key": q_key,
                "model": self.model,
                "confidence": float(ans.get("confidence", max(prob, 1.0 - prob))),
                "threshold": threshold,
                "usage": dict(entry.get("usage") or {}),
                "latency_ms": entry.get("latency_ms"),
            }
            if entry.get("safety_blocked"):
                details["safety_blocked"] = dict(entry["safety_blocked"])
            return JevNoulResult(probability=prob, verdict=prob >= threshold, details=details)

        questions = {
            "custom_noul": {
                "type": "noul",
                "instructions": question,
            }
        }
        try:
            entry = self.call_decisions_api(state, questions)
            ans = entry["answers"]["custom_noul"]
            prob = clamp_noul_probability(float(ans.get("noul", 0.5)))
            details = {
                "source": "direct_noul",
                "question_key": "custom_noul",
                "model": self.model,
                "confidence": float(ans.get("confidence", max(prob, 1.0 - prob))),
                "threshold": self.pass_threshold,
                "usage": dict(entry.get("usage") or {}),
                "latency_ms": entry.get("latency_ms"),
            }
        except DecisionsApiSafetyError as exc:
            if self.on_safety_block == "raise":
                raise
            self.stats["safety_blocked"] += 1
            prob = NOUL_MIN_PROB
            details = {
                "source": "direct_noul",
                "question_key": "custom_noul",
                "model": self.model,
                "confidence": NOUL_MAX_PROB,
                "threshold": self.pass_threshold,
                "safety_blocked": {
                    "code": exc.code,
                    "message": exc.message,
                    "status_code": exc.status_code,
                },
            }
        return JevNoulResult(probability=prob, verdict=prob >= self.pass_threshold, details=details)

    def evaluate_choice(
        self, state: str, question: str, options: dict[str, str]
    ) -> JevChoiceResult:
        if not options:
            raise ValueError("options mapping cannot be empty.")
        for k, v in options.items():
            if str(k).lower() in FORBIDDEN_CHOICE_KEYS or str(v).lower() in FORBIDDEN_CHOICE_KEYS:
                raise ValueError(
                    "Option 'none_of_the_above' is disallowed on Decisions API because alphabetical "
                    "key sorting places it ahead of later options. Use explicit categories or 'other'."
                )

        is_standard_taxonomy = set(options.values()) == set(SOC_FAILURE_TAXONOMY.values())
        if is_standard_taxonomy:
            entry = self.evaluate_soc_batch(state)
            ans = entry["answers"][CHOICE_QUESTION_KEY]
            raw_probs = ans.get("probabilities") or {}
            candidate_probs = {
                label: float(raw_probs.get(label, 0.0)) for label in options.values()
            }
            selected = str(ans.get("choice") or max(candidate_probs.items(), key=lambda kv: kv[1])[0])
            if selected not in candidate_probs:
                selected = max(candidate_probs.items(), key=lambda kv: kv[1])[0]
            return JevChoiceResult(selected=selected, candidate_probs=candidate_probs)

        criteria: dict[str, str] = {}
        key_to_label: dict[str, str] = {}
        for opt_key, opt_val in options.items():
            label = str(opt_val)
            if len(label) <= 128 and len(label.encode("utf-8")) <= 512 and label == label.strip():
                api_key = label
                desc = "" if str(opt_key) == label else f"Option {opt_key}: {label}"
            else:
                api_key = str(opt_key)
                desc = label
            criteria[api_key] = desc
            key_to_label[api_key] = label

        validated = _validate_choice_criteria(criteria)
        questions = {
            CHOICE_QUESTION_KEY: {
                "type": "choice",
                "instructions": question,
                "criteria": validated,
            }
        }
        try:
            entry = self.call_decisions_api(state, questions)
            ans = entry["answers"][CHOICE_QUESTION_KEY]
            raw_probs = ans.get("probabilities") or {}
            candidate_probs = {
                key_to_label[api_k]: float(raw_probs.get(api_k, 0.0))
                for api_k in validated
            }
            chosen_api_key = str(ans.get("choice") or "")
            selected = key_to_label.get(
                chosen_api_key,
                max(candidate_probs.items(), key=lambda kv: kv[1])[0],
            )
        except DecisionsApiSafetyError:
            if self.on_safety_block == "raise":
                raise
            self.stats["safety_blocked"] += 1
            labels = list(options.values())
            selected = labels[0]
            candidate_probs = {lbl: (1.0 if lbl == selected else 0.0) for lbl in labels}
        return JevChoiceResult(selected=selected, candidate_probs=candidate_probs)


def build_decisions_api_backend(**kwargs: Any) -> DecisionsApiJevBackend:
    """Standalone factory for ``DecisionsApiJevBackend``."""
    return DecisionsApiJevBackend(**kwargs)


def describe_decisions_api_backend(backend: BaseJevBackend) -> dict[str, Any]:
    """Provenance helper matching ``agent.jev_backends.describe_jev_backend``."""
    if isinstance(backend, DecisionsApiJevBackend):
        return backend.describe()
    return describe_jev_backend(backend)


def register_decisions_api_backend(
    registry: dict[str, Callable[..., BaseJevBackend]] | None = None,
) -> dict[str, Callable[..., BaseJevBackend]]:
    """Registers ``decisions_api`` (and alias ``gemini_decision``) into a backend registry dict."""
    target = {} if registry is None else registry
    target[BACKEND_NAME] = build_decisions_api_backend
    target["gemini_decision"] = build_decisions_api_backend
    return target


def resolve_jev_backend(
    name: str,
    project_id: str | None = None,
    location: str = "us-central1",
    client: Any | None = None,
    **decisions_kwargs: Any,
) -> BaseJevBackend:
    """Resolves either Decisions API or any existing backend from ``agent.jev_backends``."""
    if name in (BACKEND_NAME, "gemini_decision"):
        return build_decisions_api_backend(client=client, **decisions_kwargs)
    return build_jev_backend(name=name, project_id=project_id, location=location, client=client)
