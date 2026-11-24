"""Gemini 4 per-model implicit prompt caching policy, prefix hygiene, and TCO helpers.

Centralizes:
- Gemini 4 model detection (`gemini-4-hydrogen`, `gemini-4-neon`, `gemini-4-carbon`).
- Explicit caching removal guardrail (Gemini 4 returns HTTP 400 on `caches.create` / `cached_content`).
- Parameter hygiene (omit `temperature`, `top_p`, `top_k`, and Flex tier on `gemini-4-*`).
- Vertex AI global routing and `gemini-4-neon` concurrency cap (`<= 2`).
- Token-0 prefix hazard detection for `system_instruction` strings.
- Cached-input pricing (95% discount above 4,096 shared prefix tokens) and per-1K-run TCO.
"""

from __future__ import annotations

from contextlib import contextmanager
import re
import threading
from typing import Any, Dict, Iterator, List, Mapping, Optional, Tuple


GEMINI_4_IMPLICIT_CACHE_MIN_TOKENS: int = 4096
GEMINI_4_NEON_MAX_CONCURRENCY: int = 2

# Standard Vertex AI per-1M-token USD pricing for Gemini 4 models.
# Cached input receives a 95% discount above 4,096 shared prefix tokens.
# Output and thinking tokens are billed at the output rate.
GEMINI_4_PRICING_PER_1M: Dict[str, Dict[str, float]] = {
    "gemini-4-hydrogen": {
        "input": 1.50,
        "cached_input": 0.075,
        "output": 7.50,
    },
    "gemini-4-neon": {
        "input": 3.00,
        "cached_input": 0.150,
        "output": 15.00,
    },
    "gemini-4-carbon": {
        "input": 4.00,
        "cached_input": 0.200,
        "output": 20.00,
    },
}

_NEON_CONCURRENCY_SEMAPHORE = threading.BoundedSemaphore(GEMINI_4_NEON_MAX_CONCURRENCY)

# Token-0 prefix hazard patterns that break implicit KV cache matching when
# placed inside `system_instruction` instead of trailing user `contents`.
_TOKEN0_HAZARD_PATTERNS: Tuple[Tuple[str, re.Pattern[str]], ...] = (
    (
        "dynamic_timestamp",
        re.compile(
            r"(?:RequestTimestamp\s*=|\b20\d{2}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b)",
            re.IGNORECASE,
        ),
    ),
    (
        "dynamic_turn_counter",
        re.compile(
            r"(?:\[\s*Turn\s*=\s*\d+|\b(?:Turn|Iteration|Step)\s*[:=]\s*\d+\b)",
            re.IGNORECASE,
        ),
    ),
    (
        "dynamic_request_or_session_id",
        re.compile(
            r"\b(?:RequestId|Request_ID|SessionId|Session_ID|TraceId|Trace_ID)\s*[:=]\s*[A-Za-z0-9_.\-]+\b",
            re.IGNORECASE,
        ),
    ),
    (
        "per_case_id",
        re.compile(r"\bCASE-[A-Z0-9]+(?:-[A-Z0-9]+)*\b"),
    ),
    (
        "per_case_cmdb_block",
        re.compile(r"\[CMDB Asset Context:", re.IGNORECASE),
    ),
    (
        "per_case_alert_payload",
        re.compile(r"(?:^|\n)(?:Original Alert|Alert To Investigate):\s*\n", re.IGNORECASE),
    ),
)


def normalize_model_name(model: Optional[str]) -> str:
    """Normalize a Vertex AI or MaaS model identifier to lowercase basename."""
    raw = str(model or "").strip().lower()
    if "/models/" in raw:
        raw = raw.rsplit("/models/", 1)[-1]
    return raw


def is_gemini_4_model(model: Optional[str]) -> bool:
    """Return True if the model belongs to the Gemini 4 family."""
    norm = normalize_model_name(model)
    return norm.startswith("gemini-4-") or "gemini-4-" in norm


def is_gemini_4_neon(model: Optional[str]) -> bool:
    """Return True if the model is `gemini-4-neon` (concurrency capped <= 2)."""
    norm = normalize_model_name(model)
    return "gemini-4-neon" in norm


def supports_explicit_caching(model: Optional[str]) -> bool:
    """Return False for Gemini 4 models, which reject `caches.create` / `cached_content` with HTTP 400."""
    return not is_gemini_4_model(model)


def assert_explicit_caching_allowed(model: Optional[str]) -> None:
    """Guardrail preventing explicit `client.caches.create` calls on Gemini 4 models."""
    if not supports_explicit_caching(model):
        raise ValueError(
            f"Model '{model}' uses automatic Implicit Context Caching and does not "
            "support explicit caching (`client.caches.create` / `cached_content` returns HTTP 400)."
        )


def resolve_gemini_location(model: Optional[str], region: str = "us-central1") -> str:
    """Resolve Vertex AI location, routing Gemini 4 (and Gemini 3 / Gemma 4 default) to `global`."""
    norm = normalize_model_name(model)
    if is_gemini_4_model(norm):
        return "global"
    if (
        "gemini-3.7" in norm
        or "gemini-3.5" in norm
        or "gemini-3.1" in norm
        or "gemini-3-" in norm
        or "gemma-4" in norm
    ) and region == "us-central1":
        return "global"
    return region


def sanitize_generate_content_config_kwargs(
    model: Optional[str],
    config_kwargs: Mapping[str, Any],
) -> Dict[str, Any]:
    """Return a sanitized `GenerateContentConfig` kwargs dict respecting Gemini 4 constraints.

    For `gemini-4-*`:
    - Omits `temperature`, `top_p`, and `top_k`.
    - Gates off `cached_content` (explicit caching returns HTTP 400).
    - Removes Flex service tier overrides (`gemini-4-hydrogen` rejects Flex PayGo with HTTP 400).
    """
    cleaned = {k: v for k, v in config_kwargs.items() if v is not None}
    if is_gemini_4_model(model):
        for forbidden_key in ("temperature", "top_p", "top_k", "cached_content"):
            cleaned.pop(forbidden_key, None)
        tier = cleaned.get("service_tier")
        if tier is not None and "flex" in str(tier).lower():
            cleaned.pop("service_tier", None)
    return cleaned


@contextmanager
def neon_concurrency_guard(model: Optional[str]) -> Iterator[None]:
    """Enforce `gemini-4-neon` concurrency <= 2 across threads in this process."""
    if not is_gemini_4_neon(model):
        yield
        return
    _NEON_CONCURRENCY_SEMAPHORE.acquire()
    try:
        yield
    finally:
        _NEON_CONCURRENCY_SEMAPHORE.release()


def get_gemini_4_rates(model: Optional[str]) -> Optional[Dict[str, float]]:
    """Look up per-1M-token USD rates for a Gemini 4 model, or None if not Gemini 4."""
    norm = normalize_model_name(model)
    if norm in GEMINI_4_PRICING_PER_1M:
        return dict(GEMINI_4_PRICING_PER_1M[norm])
    for key, rates in GEMINI_4_PRICING_PER_1M.items():
        if key in norm:
            return dict(rates)
    return None


def extract_usage_metrics(
    usage_metadata: Any,
    prompt_fallback: int = 0,
    completion_fallback: int = 0,
) -> Dict[str, Any]:
    """Extract normalized token counts and cache hit rate from GenAI `usage_metadata`."""
    def _int_attr(name: str, default: int = 0) -> int:
        val = getattr(usage_metadata, name, None)
        if val is None and isinstance(usage_metadata, Mapping):
            val = usage_metadata.get(name)
        try:
            return max(0, int(val)) if val is not None else default
        except (TypeError, ValueError):
            return default

    prompt_tokens = _int_attr("prompt_token_count", prompt_fallback)
    cached_tokens = min(prompt_tokens, _int_attr("cached_content_token_count", 0))
    completion_tokens = _int_attr("candidates_token_count", completion_fallback)
    thoughts_tokens = _int_attr("thoughts_token_count", 0)
    total_tokens = _int_attr(
        "total_token_count",
        prompt_tokens + completion_tokens + thoughts_tokens,
    )
    cache_hit_rate = round(cached_tokens / prompt_tokens, 4) if prompt_tokens > 0 else 0.0
    return {
        "prompt_tokens": prompt_tokens,
        "cached_tokens": cached_tokens,
        "completion_tokens": completion_tokens,
        "thoughts_tokens": thoughts_tokens,
        "total_tokens": total_tokens,
        "cache_hit_rate": cache_hit_rate,
    }


def estimate_cached_cost_usd(
    model: Optional[str],
    prompt_tokens: int = 0,
    cached_tokens: int = 0,
    completion_tokens: int = 0,
    thoughts_tokens: int = 0,
    default_input_rate: float = 0.30,
    default_output_rate: float = 2.50,
    default_cached_input_rate: Optional[float] = None,
) -> float:
    """Compute USD cost accounting for uncached input, cached input, and output+thinking tokens."""
    p_tok = max(0, int(prompt_tokens or 0))
    c_hit = min(p_tok, max(0, int(cached_tokens or 0)))
    uncached_p = max(0, p_tok - c_hit)
    out_tok = max(0, int(completion_tokens or 0)) + max(0, int(thoughts_tokens or 0))

    g4 = get_gemini_4_rates(model)
    if g4 is not None:
        in_rate = g4["input"]
        cached_rate = g4["cached_input"]
        out_rate = g4["output"]
    else:
        in_rate = float(default_input_rate)
        out_rate = float(default_output_rate)
        cached_rate = (
            float(default_cached_input_rate)
            if default_cached_input_rate is not None
            else in_rate * 0.25
        )

    return (
        uncached_p * in_rate + c_hit * cached_rate + out_tok * out_rate
    ) / 1_000_000.0


def compute_cache_telemetry(
    usage: Mapping[str, Any],
    model: Optional[str],
    runs: int = 1,
) -> Dict[str, Any]:
    """Compute summary cache hit percentage and per-1K-run TCO telemetry from a usage dict."""
    p_tok = max(0, int(usage.get("prompt_tokens") or 0))
    c_hit = min(p_tok, max(0, int(usage.get("cached_tokens") or 0)))
    comp_tok = max(0, int(usage.get("completion_tokens") or 0))
    thoughts_tok = max(0, int(usage.get("thoughts_tokens") or 0))
    cost_usd = estimate_cached_cost_usd(
        model=model,
        prompt_tokens=p_tok,
        cached_tokens=c_hit,
        completion_tokens=comp_tok,
        thoughts_tokens=thoughts_tok,
    )
    run_count = max(1, int(runs or 1))
    hit_rate = (c_hit / p_tok) if p_tok > 0 else 0.0
    return {
        "model": str(model or ""),
        "prompt_tokens": p_tok,
        "cached_tokens": c_hit,
        "uncached_prompt_tokens": max(0, p_tok - c_hit),
        "completion_tokens": comp_tok,
        "thoughts_tokens": thoughts_tok,
        "output_and_thinking_tokens": comp_tok + thoughts_tok,
        "cache_hit_rate": round(hit_rate, 4),
        "cache_hit_pct": round(hit_rate * 100.0, 2),
        "estimated_cost_usd": round(cost_usd, 6),
        "estimated_cost_per_1k_runs_usd": round((cost_usd / run_count) * 1000.0, 4),
    }


def detect_token0_prefix_hazards(system_instruction: Optional[str]) -> List[str]:
    """Detect dynamic per-turn/per-case fields inside `system_instruction` that break implicit caching."""
    if not system_instruction:
        return []
    text = str(system_instruction)
    found: List[str] = []
    for label, pattern in _TOKEN0_HAZARD_PATTERNS:
        if pattern.search(text):
            found.append(label)
    return found
