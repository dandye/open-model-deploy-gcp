#!/usr/bin/env python3
"""
Gemma Deployment Benchmark & Metrics Collector
Measures Latency (P50, P90, P99), first-network-chunk timing, ITL,
actual or estimated generated tokens, Tokens/Sec (TPS), and Tokens/Min (TPM)
against Vertex AI Endpoints
with single-stream, concurrent multi-stream, and prefix caching evaluation modes.
"""

import base64
import os
from pathlib import Path
import struct
import sys
import json
import math
import time
import zlib
import subprocess
import argparse
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Tuple


def get_adc_token() -> str:
    """Retrieve and refresh Google Cloud ADC access token with gcloud CLI fallback."""
    try:
        import google.auth
        import google.auth.transport.requests
        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        if not getattr(credentials, "valid", False) or not getattr(credentials, "token", None):
            credentials.refresh(google.auth.transport.requests.Request())
        if getattr(credentials, "token", None):
            return str(credentials.token).strip()
    except Exception:
        pass
    res = subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        capture_output=True,
        text=True,
        check=True,
    )
    return res.stdout.strip()


def _load_models_catalog() -> Dict[str, Any]:
    """Load configs/models.json safely for MaaS flavor auto-detection."""
    catalog_path = Path(__file__).resolve().parent.parent / "configs" / "models.json"
    if not catalog_path.exists():
        return {}
    try:
        with open(catalog_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def resolve_open_maas_target(
    maas_model: Optional[str] = None,
    flavor: Optional[str] = None,
    region: str = "us-central1",
    catalog: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[str], str]:
    """Resolve OpenMaaS model ID and target region from --maas-model or --flavor."""
    cat = _load_models_catalog() if catalog is None else catalog
    explicit_maas = (maas_model or "").strip()
    flavor_key = (flavor or "").strip()
    resolved_region = (region or "us-central1").strip()

    if explicit_maas:
        entry = cat.get(explicit_maas) if isinstance(cat.get(explicit_maas), dict) else None
        if entry is None:
            for cand in cat.values():
                if isinstance(cand, dict) and explicit_maas in (
                    cand.get("maasModelId"),
                    cand.get("modelId"),
                ):
                    entry = cand
                    break
        model_id = (
            str(entry.get("maasModelId") or entry.get("modelId") or explicit_maas).strip()
            if entry
            else explicit_maas
        )
        if (
            "/" not in model_id
            and model_id.lower().startswith("deepseek-")
            and model_id.lower().endswith("-maas")
        ):
            model_id = f"deepseek-ai/{model_id}"
        cat_region = str(entry.get("region") or "").strip() if entry else ""
        if cat_region == "global" or resolved_region == "us-central1":
            resolved_region = cat_region or "global"
        return model_id, resolved_region

    if flavor_key:
        entry = cat.get(flavor_key) if isinstance(cat.get(flavor_key), dict) else None
        if entry is not None and entry.get("type") == "maas":
            cand_id = str(entry.get("maasModelId") or entry.get("modelId") or "").strip()
            if entry.get("maasModelId") or ("/" in cand_id and cand_id.lower().endswith("-maas")):
                cat_region = str(entry.get("region") or "").strip()
                if cat_region == "global" or resolved_region == "us-central1":
                    resolved_region = cat_region or "global"
                return cand_id, resolved_region
        if flavor_key.lower().startswith("deepseek-") and flavor_key.lower().endswith("-maas"):
            if resolved_region == "us-central1":
                resolved_region = "global"
            return f"deepseek-ai/{flavor_key}", resolved_region
        if "/" in flavor_key and flavor_key.lower().endswith("-maas"):
            if resolved_region == "us-central1":
                resolved_region = "global"
            return flavor_key, resolved_region

    return None, resolved_region


def build_open_maas_url(project_id: str, region: str = "global") -> str:
    """Build Vertex AI OpenAPI chat completions endpoint URL."""
    loc = (region or "global").strip()
    if loc == "global":
        return (
            f"https://aiplatform.googleapis.com/v1/projects/{project_id}"
            "/locations/global/endpoints/openapi/chat/completions"
        )
    return (
        f"https://{loc}-aiplatform.googleapis.com/v1/projects/{project_id}"
        f"/locations/{loc}/endpoints/openapi/chat/completions"
    )


def build_compact_test_png_data_url(width: int = 16, height: int = 16) -> str:
    """Build a spec-compliant compact RGB PNG data:image/png;base64,... URL."""
    def _png_chunk(chunk_type: bytes, chunk_data: bytes) -> bytes:
        crc = zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF
        return (
            struct.pack(">I", len(chunk_data))
            + chunk_type
            + chunk_data
            + struct.pack(">I", crc)
        )

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    scanline = b"\x00" + (b"\x20\x68\xb8" * width)
    idat = zlib.compress(scanline * height, level=9)
    png_bytes = sig + _png_chunk(b"IHDR", ihdr) + _png_chunk(b"IDAT", idat) + _png_chunk(b"IEND", b"")
    return f"data:image/png;base64,{base64.b64encode(png_bytes).decode('ascii')}"


def _parse_open_maas_output(
    res_body: Optional[Dict[str, Any]],
) -> Tuple[str, int, str, Dict[str, int]]:
    """Extract text, completion token count, provenance, and usage dict from OpenMaaS response."""
    empty_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    if not res_body or not isinstance(res_body, dict):
        return "", 0, "none", empty_usage

    text_out = ""
    choices = res_body.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        msg = choices[0].get("message") or choices[0].get("delta") or {}
        if isinstance(msg, dict):
            content = msg.get("content")
            if isinstance(content, str) and content:
                text_out = content
            elif isinstance(content, list):
                text_out = "".join(
                    p.get("text", "") if isinstance(p, dict) else str(p) for p in content
                )
            if not text_out and isinstance(msg.get("reasoning_content"), str):
                text_out = msg["reasoning_content"]
            if not text_out and msg.get("tool_calls"):
                text_out = json.dumps(msg["tool_calls"])
    elif isinstance(res_body.get("predictions"), list) and res_body["predictions"]:
        text_out = _prediction_text(res_body["predictions"][0])

    raw_usage = res_body.get("usage")
    if isinstance(raw_usage, dict) and raw_usage.get("completion_tokens") is not None:
        prompt_tok = int(raw_usage.get("prompt_tokens") or 0)
        comp_tok = int(raw_usage.get("completion_tokens") or 0)
        tot_tok = int(raw_usage.get("total_tokens") or (prompt_tok + comp_tok))
        usage_out: Dict[str, int] = {
            "prompt_tokens": prompt_tok,
            "completion_tokens": comp_tok,
            "total_tokens": tot_tok,
        }
        details = raw_usage.get("completion_tokens_details")
        if isinstance(details, dict) and details.get("reasoning_tokens") is not None:
            usage_out["reasoning_tokens"] = int(details["reasoning_tokens"])
        elif raw_usage.get("reasoning_tokens") is not None:
            usage_out["reasoning_tokens"] = int(raw_usage["reasoning_tokens"])
        return text_out.strip(), comp_tok, "actual", usage_out

    if not text_out.strip():
        return "", 0, "none", empty_usage
    est = max(1, int(len(text_out) / 3.8))
    return text_out.strip(), est, "estimated", {
        "prompt_tokens": 0,
        "completion_tokens": est,
        "total_tokens": est,
    }


def send_open_maas_request(
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    max_retries: int = 4,
) -> Tuple[float, Optional[Dict[str, Any]], Optional[str], int]:
    """Send non-streaming OpenMaaS chat completions request with fast-fail on 401/403/404."""
    encoded = json.dumps(payload).encode("utf-8")
    last_elapsed = 0.0
    for attempt in range(max_retries):
        req = urllib.request.Request(url, data=encoded, headers=headers, method="POST")
        start_time = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=300) as response:
                status = int(getattr(response, "status", 200) or 200)
                body = json.loads(response.read().decode("utf-8"))
                elapsed = time.perf_counter() - start_time
                return elapsed, body, None, status
        except urllib.error.HTTPError as e:
            elapsed = time.perf_counter() - start_time
            last_elapsed = elapsed
            code = int(getattr(e, "code", 0) or 0)
            err_body = ""
            try:
                raw_err = e.read()
                err_body = (
                    raw_err.decode("utf-8", errors="replace").strip()
                    if isinstance(raw_err, bytes)
                    else str(raw_err or "").strip()
                )
            except Exception:
                err_body = ""
            detail = err_body or str(e)
            if code in (401, 403, 404):
                return elapsed, None, f"HTTP {code}: {detail}", code
            if code in (429, 503, 504) and attempt < max_retries - 1:
                time.sleep((2 ** attempt) * 2)
                continue
            return elapsed, None, f"HTTP {code}: {detail}", code
        except Exception as e:
            elapsed = time.perf_counter() - start_time
            return elapsed, None, str(e), 0
    return last_elapsed, None, "Max retries exceeded", 0


def _sse_event_has_delta_token(event: Dict[str, Any]) -> bool:
    """Return True when an OpenAI SSE event carries non-empty content, reasoning_content, or tool_calls."""
    choices = event.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return False
    delta = choices[0].get("delta")
    if not isinstance(delta, dict):
        return False
    content = delta.get("content")
    if isinstance(content, str) and len(content) > 0:
        return True
    if isinstance(content, list) and len(content) > 0:
        return True
    reasoning = delta.get("reasoning_content")
    if isinstance(reasoning, str) and len(reasoning) > 0:
        return True
    tool_calls = delta.get("tool_calls")
    if isinstance(tool_calls, list) and len(tool_calls) > 0:
        return True
    return False


def send_open_maas_streaming_request(
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    max_retries: int = 4,
) -> Tuple[float, Optional[float], List[float], Optional[Dict[str, Any]], Optional[str], int]:
    """Send streaming SSE OpenMaaS request, measuring exact delta TTFT, inter-chunk ITL, and usage."""
    stream_headers = dict(headers)
    stream_headers["Accept"] = "text/event-stream, application/json"
    encoded = json.dumps(payload).encode("utf-8")

    for attempt in range(max_retries):
        req = urllib.request.Request(url, data=encoded, headers=stream_headers, method="POST")
        start_time = time.perf_counter()
        ttft_s: Optional[float] = None
        prev_delta_s: Optional[float] = None
        itl_chunks_ms: List[float] = []
        content_parts: List[str] = []
        reasoning_parts: List[str] = []
        tool_call_fragments: List[Any] = []
        merged_usage: Dict[str, Any] = {}
        stream_error: Optional[str] = None
        line_buffer = b""

        def _process_sse_data(data_str: str, arrival_s: float) -> None:
            nonlocal ttft_s, prev_delta_s, stream_error
            clean = data_str.strip()
            if not clean or clean == "[DONE]":
                return
            try:
                ev = json.loads(clean)
            except Exception:
                return
            if not isinstance(ev, dict):
                return
            err_msg = _stream_error_message(ev)
            if err_msg and stream_error is None:
                stream_error = err_msg
            if _sse_event_has_delta_token(ev):
                if ttft_s is None:
                    ttft_s = arrival_s
                elif prev_delta_s is not None:
                    itl_chunks_ms.append(max(0.0, (arrival_s - prev_delta_s) * 1000.0))
                prev_delta_s = arrival_s
                delta = ev["choices"][0]["delta"]
                if isinstance(delta.get("content"), str) and delta["content"]:
                    content_parts.append(delta["content"])
                if isinstance(delta.get("reasoning_content"), str) and delta["reasoning_content"]:
                    reasoning_parts.append(delta["reasoning_content"])
                if isinstance(delta.get("tool_calls"), list) and delta["tool_calls"]:
                    tool_call_fragments.extend(delta["tool_calls"])
            usage = ev.get("usage")
            if isinstance(usage, dict):
                merged_usage.update(usage)

        try:
            with urllib.request.urlopen(req, timeout=300) as response:
                status = int(getattr(response, "status", 200) or 200)
                read_available = getattr(response, "read1", response.read)
                while True:
                    chunk = read_available(64)
                    if not chunk:
                        break
                    now_offset = time.perf_counter() - start_time
                    line_buffer += chunk
                    while b"\n" in line_buffer:
                        raw_line, line_buffer = line_buffer.split(b"\n", 1)
                        line_txt = raw_line.decode("utf-8", errors="ignore").strip()
                        if line_txt.startswith("data:"):
                            _process_sse_data(line_txt[5:].lstrip(), now_offset)

                if line_buffer.strip():
                    now_offset = time.perf_counter() - start_time
                    rem_txt = line_buffer.decode("utf-8", errors="ignore").strip()
                    if rem_txt.startswith("data:"):
                        _process_sse_data(rem_txt[5:].lstrip(), now_offset)

                elapsed = time.perf_counter() - start_time
                combined_content = "".join(content_parts)
                combined_reasoning = "".join(reasoning_parts)
                msg_out: Dict[str, Any] = {"role": "assistant", "content": combined_content}
                if combined_reasoning:
                    msg_out["reasoning_content"] = combined_reasoning
                if tool_call_fragments:
                    msg_out["tool_calls"] = tool_call_fragments
                body_out: Dict[str, Any] = {"choices": [{"message": msg_out}]}
                if merged_usage:
                    body_out["usage"] = merged_usage
                if status >= 400:
                    stream_error = f"HTTP {status}: {stream_error}" if stream_error else f"HTTP {status}"
                return elapsed, ttft_s, itl_chunks_ms, body_out, stream_error, status
        except urllib.error.HTTPError as e:
            elapsed = time.perf_counter() - start_time
            code = int(getattr(e, "code", 0) or 0)
            err_body = ""
            try:
                raw_err = e.read()
                err_body = (
                    raw_err.decode("utf-8", errors="replace").strip()
                    if isinstance(raw_err, bytes)
                    else str(raw_err or "").strip()
                )
            except Exception:
                err_body = ""
            detail = err_body or str(e)
            if code in (401, 403, 404):
                return elapsed, ttft_s, itl_chunks_ms, None, f"HTTP {code}: {detail}", code
            if code in (429, 503, 504) and attempt < max_retries - 1:
                time.sleep((2 ** attempt) * 2)
                continue
            return elapsed, ttft_s, itl_chunks_ms, None, f"HTTP {code}: {detail}", code
        except Exception as e:
            elapsed = time.perf_counter() - start_time
            return elapsed, ttft_s, itl_chunks_ms, None, str(e), 0
    return 0.0, None, [], None, "Max retries exceeded", 0


def calculate_percentile(data: List[float], percentile: float) -> float:
    """
    Calculate percentile value from numeric data using linear interpolation.
    Percentile must be between 0 and 100.
    """
    if not data:
        return 0.0
    sorted_data = sorted(data)
    n = len(sorted_data)
    if n == 1:
        return float(sorted_data[0])
    if percentile <= 0:
        return float(sorted_data[0])
    if percentile >= 100:
        return float(sorted_data[-1])

    k = (n - 1) * (percentile / 100.0)
    f = int(k)
    c = f + 1
    if c >= n:
        return float(sorted_data[-1])
    d = k - f
    return float(sorted_data[f] + d * (sorted_data[c] - sorted_data[f]))


def _as_non_negative_int(value: Any) -> Optional[int]:
    """Return an integer token count when a response field is trustworthy."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer() or value < 0:
            return None
        return int(value)
    if not isinstance(value, str) or not value.strip() or not value.strip().isdigit():
        return None
    return int(value.strip())


def _find_actual_token_count(value: Any, context: str = "root") -> Optional[int]:
    """Find a provider-reported generated-token count without counting prompt tokens."""
    if isinstance(value, dict):
        # These fields are completion/output-specific across Vertex, OpenAI, and
        # vLLM-compatible responses. Generic ``tokens`` and ``token_count`` are
        # intentionally excluded because they can describe prompt/input tokens.
        completion_keys = (
            "completion_tokens",
            "output_tokens",
            "generated_tokens",
            "candidatesTokenCount",
            "completionTokenCount",
        )
        if context in {"usage", "prediction_details"}:
            for key in completion_keys:
                count = _as_non_negative_int(value.get(key))
                if count is not None:
                    return count
        # A response's candidate metadata is a known Vertex location for
        # candidatesTokenCount, while arbitrary token_count remains ambiguous.
        if context == "root":
            count = _as_non_negative_int(value.get("candidatesTokenCount"))
            if count is not None:
                return count
        for key, child in value.items():
            if key in {"prompt_tokens", "input_tokens", "promptTokenCount", "inputTokenCount", "total_tokens"}:
                continue
            child_context = context
            if key in {"usage", "usageMetadata", "usage_metadata", "tokenUsage", "token_usage"}:
                child_context = "usage"
            elif key in {"details", "token_details"}:
                child_context = "prediction_details"
            child_count = _find_actual_token_count(
                child,
                child_context,
            )
            if child_count is not None:
                return child_count
    elif isinstance(value, list):
        for child in value:
            child_count = _find_actual_token_count(child, context)
            if child_count is not None:
                return child_count
    return None


def _prediction_text(prediction: Any) -> str:
    """Extract text from common Vertex/OpenAI/vLLM prediction shapes."""
    if isinstance(prediction, str):
        return prediction
    if not isinstance(prediction, dict):
        return str(prediction)
    content = prediction.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and isinstance(part.get("text"), str):
                parts.append(part["text"])
        if parts:
            return "".join(parts)
    message = prediction.get("message")
    if isinstance(message, dict):
        message_text = _prediction_text(message)
        if message_text:
            return message_text
    delta = prediction.get("delta")
    if isinstance(delta, dict):
        delta_text = _prediction_text(delta)
        if delta_text:
            return delta_text
    for key in ("text", "generated_text", "output"):
        if isinstance(prediction.get(key), str):
            return prediction[key]
    return ""


def parse_output_details(res_body: Optional[Dict[str, Any]]) -> Tuple[str, int, str]:
    """Parse text, token count, and provenance (``actual``/``estimated``/``none``)."""
    if not res_body or not isinstance(res_body, dict):
        return "", 0, "none"
    predictions = res_body.get("predictions", [])
    if not predictions:
        # Also accept OpenAI-compatible responses used by local serving tests.
        predictions = res_body.get("choices", [])
    if not predictions:
        return "", 0, "none"

    output_text = _prediction_text(predictions[0]).strip()
    if isinstance(predictions[0], str) and "Output:\n" in output_text:
        output_text = output_text.split("Output:\n", 1)[1].strip()

    actual_tokens = _find_actual_token_count(res_body)
    if actual_tokens is not None:
        return output_text, actual_tokens, "actual"
    if not output_text:
        return "", 0, "none"
    return output_text, max(1, int(len(output_text) / 3.8)), "estimated"


def parse_output(res_body: Optional[Dict[str, Any]]) -> Tuple[str, int]:
    """Backward-compatible text and token-count parser.

    The second value is provider-reported when available and otherwise an
    explicitly estimated count. Use :func:`parse_output_details` when the
    provenance label is needed.
    """
    output_text, token_count, _ = parse_output_details(res_body)
    return output_text, token_count


def calculate_summary(
    latencies: List[float],
    token_counts: List[int],
    ttfts: Optional[List[float]] = None,
    concurrency: int = 1,
    endpoint_id: str = "",
    region: str = "",
    sample_output: str = "",
    wall_clock_s: Optional[float] = None,
    first_token_times: Optional[List[Optional[float]]] = None,
    token_count_sources: Optional[List[str]] = None,
    failed_requests: int = 0,
) -> Dict[str, Any]:
    """
    Calculate summary metrics including latency percentiles, throughput, and
    separately labelled first-chunk/first-token timing.
    """
    source_labels = [s for s in (token_count_sources or []) if s]
    if not source_labels:
        token_source = "none"
    elif all(s == "actual" for s in source_labels):
        token_source = "actual"
    elif all(s == "estimated" for s in source_labels):
        token_source = "estimated"
    else:
        token_source = "mixed"

    empty_summary = {
        "endpoint_id": endpoint_id,
        "region": region,
        "concurrency": concurrency,
        "total_requests": 0,
        "successful_requests": 0,
        "failed_requests": failed_requests,
        "avg_latency_s": 0.0,
        "p50_latency_s": 0.0,
        "p90_latency_s": 0.0,
        "p99_latency_s": 0.0,
        "avg_tokens": 0.0,
        "token_count_source": token_source,
        "request_normalized_tps": 0.0,
        "request_normalized_tpm": 0.0,
        "aggregate_tps": 0.0 if wall_clock_s is not None else None,
        "aggregate_tpm": 0.0 if wall_clock_s is not None else None,
        "wall_clock_s": round(wall_clock_s, 3) if wall_clock_s is not None else None,
        "wall_clock_source": "observed" if wall_clock_s is not None else "unavailable",
        "throughput_source": "observed_wall_clock" if wall_clock_s is not None else "request_service_time_legacy",
        "tps": 0.0,
        "tpm": 0.0,
        "sample_output": sample_output,
    }
    if not latencies:
        return empty_summary

    if len(token_counts) != len(latencies):
        raise ValueError("latencies and token_counts must have equal lengths")
    if token_count_sources and len(token_count_sources) != len(latencies):
        raise ValueError("token_count_sources must have one label per request")

    total_reqs = len(latencies)
    avg_latency = sum(latencies) / total_reqs
    p50_lat = calculate_percentile(latencies, 50)
    p90_lat = calculate_percentile(latencies, 90)
    p99_lat = calculate_percentile(latencies, 99)

    avg_tokens = sum(token_counts) / total_reqs if token_counts else 0.0

    total_tokens = sum(token_counts)
    request_time = sum(latencies)
    measured_wall_clock = wall_clock_s if wall_clock_s is not None and wall_clock_s > 0 else None
    request_tps = total_tokens / request_time if request_time > 0 else 0.0
    aggregate_tps = total_tokens / measured_wall_clock if measured_wall_clock else None
    # ``tps`` remains the historical request-normalized rate unless the caller
    # supplies an observed wall-clock interval. Aggregate rate is then explicit.
    tps = aggregate_tps if aggregate_tps is not None else request_tps
    tpm = tps * 60.0

    summary: Dict[str, Any] = {
        "endpoint_id": endpoint_id,
        "region": region,
        "concurrency": concurrency,
        "total_requests": total_reqs,
        "avg_latency_s": round(avg_latency, 3),
        "p50_latency_s": round(p50_lat, 3),
        "p90_latency_s": round(p90_lat, 3),
        "p99_latency_s": round(p99_lat, 3),
        "avg_tokens": round(avg_tokens, 1),
        "successful_requests": total_reqs,
        "failed_requests": failed_requests,
        "token_count_source": token_source,
        "wall_clock_s": round(measured_wall_clock, 3) if measured_wall_clock is not None else None,
        "wall_clock_source": "observed" if measured_wall_clock is not None else "unavailable",
        "throughput_source": "observed_wall_clock" if measured_wall_clock is not None else "request_service_time_legacy",
        "request_normalized_tps": round(request_tps, 1),
        "request_normalized_tpm": round(request_tps * 60.0, 0),
        "aggregate_tps": round(aggregate_tps, 1) if aggregate_tps is not None else None,
        "aggregate_tpm": round(aggregate_tps * 60.0, 0) if aggregate_tps is not None else None,
        "tps": round(tps, 1),
        "tpm": round(tpm, 0),
        "sample_output": sample_output,
    }

    if ttfts and len(ttfts) == total_reqs:
        avg_ttft_s = sum(ttfts) / total_reqs
        summary["first_chunk_ms"] = round(avg_ttft_s * 1000.0, 1)
        # Keep ttft_ms as a compatibility alias. It is deliberately labelled
        # so callers do not mistake a network chunk for a generated token.
        summary["ttft_ms"] = round(avg_ttft_s * 1000.0, 1)
        summary["ttft_source"] = "first_network_chunk"

        itl_values = []
        for lat, ttft, tok in zip(latencies, ttfts, token_counts):
            if tok > 1:
                itl_s = (lat - ttft) / (tok - 1)
            else:
                itl_s = lat - ttft
            itl_values.append(itl_s * 1000.0)

        avg_itl_ms = sum(itl_values) / len(itl_values) if itl_values else 0.0
        summary["itl_ms"] = round(avg_itl_ms, 1)
        summary["itl_source"] = "first_network_chunk"

    if first_token_times and len(first_token_times) == total_reqs:
        verified_times = [t for t in first_token_times if t is not None]
        if verified_times:
            summary["first_token_ms"] = round(sum(verified_times) / len(verified_times) * 1000.0, 1)
            summary["first_token_observed_requests"] = len(verified_times)
            summary["first_token_source"] = (
                "verified_generated_token"
                if len(verified_times) == total_reqs
                else "verified_generated_token_partial"
            )
        else:
            summary["first_token_ms"] = None
            summary["first_token_source"] = "unavailable"

    return summary


def format_benchmark_table(summary: Dict[str, Any]) -> str:
    """Format benchmark results into a clear ASCII metrics table."""
    lines = []
    lines.append("=" * 60)
    lines.append(" Benchmark Summary:")
    lines.append(f"   Endpoint ID:      {summary.get('endpoint_id', 'N/A')}")
    lines.append(f"   Region:           {summary.get('region', 'N/A')}")
    lines.append(f"   Concurrency:      {summary.get('concurrency', 1)}")
    lines.append(f"   Total Runs:       {summary.get('total_requests', 'N/A')}")
    lines.append("-" * 60)
    lines.append(f"   Avg Latency:      {summary.get('avg_latency_s', 0.0):.2f} s")
    lines.append(f"   P50 Latency:      {summary.get('p50_latency_s', 0.0):.2f} s")
    lines.append(f"   P90 Latency:      {summary.get('p90_latency_s', 0.0):.2f} s")
    lines.append(f"   P99 Latency:      {summary.get('p99_latency_s', 0.0):.2f} s")
    wall_clock = summary.get("wall_clock_s")
    if wall_clock is None:
        lines.append("   Wall-Clock Time:  unavailable")
    else:
        lines.append(f"   Wall-Clock Time:  {wall_clock:.2f} s")
    lines.append("-" * 60)
    lines.append(f"   Avg Output Len:   {summary.get('avg_tokens', 0.0):.0f} tokens")
    lines.append(f"   Token Count:      {summary.get('token_count_source', 'none')}")
    aggregate_tps = summary.get("aggregate_tps")
    if aggregate_tps is None:
        lines.append("   Aggregate Rate:   unavailable (wall-clock not supplied)")
    else:
        lines.append(f"   Aggregate Rate:   {aggregate_tps:.1f} tokens/sec (TPS)")
    request_tps = summary.get("request_normalized_tps", summary.get("tps", 0.0))
    lines.append(f"   Request-Normalized: {request_tps:.1f} tokens/sec (TPS)")
    aggregate_tpm = summary.get("aggregate_tpm")
    if aggregate_tpm is None:
        lines.append("   Aggregate Rate:   unavailable (wall-clock not supplied)")
    else:
        lines.append(f"   Aggregate Rate:   {aggregate_tpm:,.0f} tokens/min (TPM)")

    if "ttft_ms" in summary:
        lines.append("-" * 60)
        lines.append(f"   First Chunk:      {summary.get('first_chunk_ms', summary.get('ttft_ms', 0.0)):.1f} ms")
        lines.append(f"   Timing Label:      {summary.get('ttft_source', 'first_network_chunk')}")
    if "first_token_ms" in summary:
        lines.append(f"   First Token:      {summary.get('first_token_ms') if summary.get('first_token_ms') is not None else 'unavailable'} ms")
    if "itl_ms" in summary:
        lines.append(f"   Avg ITL:          {summary.get('itl_ms', 0.0):.1f} ms")

    lines.append("=" * 60)
    return "\n".join(lines)


def send_single_request(
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    stream: bool = False,
) -> Tuple[float, Optional[Dict[str, Any]], Optional[str]]:
    """
    Send HTTP POST request to prediction endpoint.
    Returns (elapsed_time, response_body, error_message).
    """
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    start_time = time.perf_counter()
    try:
        with urllib.request.urlopen(req) as response:
            res_body = json.loads(response.read().decode("utf-8"))
            elapsed = time.perf_counter() - start_time
            return elapsed, res_body, None
    except Exception as e:
        elapsed = time.perf_counter() - start_time
        return elapsed, None, str(e)


def _generated_text_from_value(value: Any) -> str:
    """Extract generated text from one decoded streaming event."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(_generated_text_from_value(item) for item in value)
    if not isinstance(value, dict):
        return ""

    # Prefer delta/text fields so transport metadata cannot be mistaken for a
    # generated token. Prediction/content is included for Vertex responses.
    for key in ("text", "generated_text", "delta", "content", "output"):
        child = value.get(key)
        if isinstance(child, str) and child.strip():
            return child
        if isinstance(child, (dict, list)):
            text = _generated_text_from_value(child)
            if text.strip():
                return text
    for key in ("choices", "predictions", "candidates"):
        child = value.get(key)
        text = _generated_text_from_value(child)
        if text.strip():
            return text
    return ""


def _fragment_contains_generated_text(fragment: bytes) -> bool:
    """Check a complete JSON/SSE fragment for verifiable generated content."""
    text = fragment.decode("utf-8", errors="ignore").strip()
    if not text:
        return False
    candidates = [text]
    if text.startswith("data:"):
        candidates = [line[5:].strip() for line in text.splitlines() if line.startswith("data:")]
    for candidate in candidates:
        if candidate in {"[DONE]", ""}:
            continue
        try:
            decoded = json.loads(candidate)
        except (TypeError, ValueError):
            continue
        if _generated_text_from_value(decoded).strip():
            return True
    return False


def _append_stream_text(current: str, fragment: str) -> str:
    """Merge delta or cumulative streaming text without duplicating prefixes."""
    fragment = fragment or ""
    if not fragment:
        return current
    if not current:
        return fragment
    if fragment.startswith(current):
        return fragment
    if current.startswith(fragment):
        return current
    return current + fragment


def _stream_text_and_mode(value: Dict[str, Any]) -> Tuple[str, str]:
    """Return stream text and whether the provider sends deltas or cumulative text."""
    choices = value.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        choice = choices[0]
        if isinstance(choice.get("delta"), dict):
            return _prediction_text(choice["delta"]), "delta"
        if isinstance(choice.get("text"), str):
            return choice["text"], "delta"
        if isinstance(choice.get("message"), dict):
            return _prediction_text(choice["message"]), "replace"

    predictions = value.get("predictions")
    if isinstance(predictions, list) and predictions:
        return _prediction_text(predictions[0]), "cumulative"
    return _generated_text_from_value(value), "delta"


def _stream_error_message(value: Any) -> Optional[str]:
    """Extract an explicit provider error from common SSE/envelope shapes."""
    if not isinstance(value, dict):
        return None
    error = value.get("error")
    if isinstance(error, str) and error.strip():
        return error.strip()
    if isinstance(error, dict):
        message = error.get("message") or error.get("detail") or error.get("type")
        if message:
            code = error.get("code") or error.get("status")
            return f"{message} ({code})" if code else str(message)
        code = error.get("code") or error.get("status")
        return f"provider error ({code})" if code else "provider error"
    if str(value.get("event", "")).lower() == "error":
        data = value.get("data")
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except ValueError:
                return data.strip() or "stream error"
        nested = _stream_error_message(data)
        return nested or (str(data).strip() if data else "stream error")
    for key in ("data", "response", "body"):
        nested = _stream_error_message(value.get(key))
        if nested:
            return nested
    return None


def _decode_stream_response_detailed(raw_text: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Decode JSON, SSE, or newline-delimited JSON and report explicit errors."""
    try:
        decoded = json.loads(raw_text)
        if not isinstance(decoded, dict):
            return None, "stream response must be a JSON object"
        return decoded, _stream_error_message(decoded)
    except (TypeError, ValueError):
        pass

    events = []
    malformed_lines = False
    event_name = ""
    data_lines = []

    def flush_sse_event() -> None:
        nonlocal event_name, data_lines, malformed_lines
        if not data_lines:
            event_name = ""
            return
        candidate = "\n".join(data_lines).strip()
        try:
            event = json.loads(candidate)
        except (TypeError, ValueError):
            malformed_lines = True
            event_name = ""
            data_lines = []
            return
        if isinstance(event, dict):
            if event_name:
                # Set the protocol event name after copying the payload so a
                # payload's own ``event`` field cannot overwrite it.
                wrapped = dict(event)
                wrapped["event"] = event_name
                wrapped["data"] = event
                event = wrapped
            events.append(event)
        else:
            malformed_lines = True
        event_name = ""
        data_lines = []

    for line in raw_text.splitlines():
        candidate = line.strip()
        if not candidate:
            flush_sse_event()
            continue
        if candidate.startswith(":"):
            continue
        if candidate.startswith("event:"):
            event_name = candidate[6:].strip()
            continue
        if candidate.startswith(("id:", "retry:")):
            continue
        if candidate.startswith("data:"):
            data_value = candidate[5:].lstrip()
            if data_value == "[DONE]":
                data_lines = []
                event_name = ""
            else:
                data_lines.append(data_value)
            continue
        if not candidate or candidate == "[DONE]":
            continue
        # A non-SSE line is a complete NDJSON event. Any pending SSE data is
        # terminated before parsing it.
        flush_sse_event()
        try:
            event = json.loads(candidate)
        except (TypeError, ValueError):
            malformed_lines = True
            continue
        if isinstance(event, dict):
            events.append(event)
        else:
            malformed_lines = True
    flush_sse_event()
    if not events:
        return None, "malformed or empty streaming response"

    generated = ""
    merged_usage: Dict[str, Any] = {}
    merged_usage_metadata: Dict[str, Any] = {}
    stream_error = None
    for event in events:
        stream_error = stream_error or _stream_error_message(event)
        event_text, mode = _stream_text_and_mode(event)
        if mode == "cumulative":
            generated = _append_stream_text(generated, event_text)
        elif mode == "replace":
            generated = event_text
        else:
            # Delta events are appended verbatim. Repeated text is meaningful
            # output (for example, ``ha`` followed by ``ha``).
            generated += event_text
        for key in ("usage", "usage_metadata"):
            usage = event.get(key)
            if isinstance(usage, dict):
                merged_usage.update(usage)
        usage_metadata = event.get("usageMetadata")
        if isinstance(usage_metadata, dict):
            merged_usage_metadata.update(usage_metadata)

    body: Dict[str, Any] = {"predictions": [{"content": generated}]} if generated else {"predictions": []}
    if merged_usage:
        body["usage"] = merged_usage
    if merged_usage_metadata:
        body["usageMetadata"] = merged_usage_metadata
    if malformed_lines and stream_error is None:
        stream_error = "malformed streaming event"
    return body, stream_error


def _decode_stream_response(raw_text: str) -> Optional[Dict[str, Any]]:
    """Backward-compatible stream decoder that omits explicit error metadata."""
    body, _ = _decode_stream_response_detailed(raw_text)
    return body


def send_streaming_request_detailed(
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
) -> Tuple[float, float, Optional[float], Optional[Dict[str, Any]], Optional[str]]:
    """
    Send HTTP POST request with streaming first-network-chunk measurement.
    Returns elapsed time, first network chunk time, verified first generated-token
    time (when observable), response body, and error message. A first network
    chunk is never silently presented as a generated token.
    """
    stream_headers = dict(headers)
    stream_headers["Accept"] = "text/event-stream, application/json"

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=stream_headers,
        method="POST",
    )
    start_time = time.perf_counter()
    ttft_time = 0.0
    first_token_time: Optional[float] = None
    first_chunk_received = False
    chunks = []
    fragment_buffer = b""

    try:
        with urllib.request.urlopen(req) as response:
            response_status = getattr(response, "status", 200)
            # HTTPResponse.read(n) fills n bytes across HTTP chunks, delaying
            # observations until later tokens arrive. read1 returns available
            # bytes after at most one underlying read. Keep read for adapters
            # that do not expose the buffered-reader API.
            read_available = getattr(response, "read1", response.read)
            while True:
                chunk = read_available(64)
                if not chunk:
                    break
                if not first_chunk_received:
                    ttft_time = time.perf_counter() - start_time
                    first_chunk_received = True
                chunks.append(chunk)
                fragment_buffer += chunk
                if first_token_time is None:
                    # Parse complete newline-delimited events as they arrive.
                    lines = fragment_buffer.splitlines(keepends=True)
                    complete = b"".join(line for line in lines if line.endswith((b"\n", b"\r")))
                    fragment_buffer = b"".join(line for line in lines if not line.endswith((b"\n", b"\r")))
                    if complete and _fragment_contains_generated_text(complete):
                        first_token_time = time.perf_counter() - start_time

            elapsed = time.perf_counter() - start_time
            if not first_chunk_received:
                ttft_time = elapsed

            raw_text = b"".join(chunks).decode("utf-8", errors="ignore")
            # Decode JSON/SSE while retaining usage metadata that may arrive in
            # a final event after all generated text fragments.
            res_body, stream_error = _decode_stream_response_detailed(raw_text)
            if res_body is None:
                res_body = {"predictions": []}
            if isinstance(response_status, int) and response_status >= 400:
                status_error = f"HTTP {response_status}"
                stream_error = f"{status_error}: {stream_error}" if stream_error else status_error

            # A non-delimited JSON response can only verify generated content
            # once the body has arrived. Record that fact as a late observation,
            # rather than reporting the first transport chunk as first-token time.
            if first_token_time is None and _fragment_contains_generated_text(raw_text.encode("utf-8")):
                first_token_time = elapsed

            return elapsed, ttft_time, first_token_time, res_body, stream_error
    except urllib.error.HTTPError as e:
        elapsed = time.perf_counter() - start_time
        diagnostic = str(e)
        try:
            raw_text = e.read().decode("utf-8", errors="ignore")
            body, stream_error = _decode_stream_response_detailed(raw_text)
            if stream_error:
                diagnostic = f"{diagnostic}: {stream_error}"
            return elapsed, ttft_time if first_chunk_received else elapsed, first_token_time, body, diagnostic
        except Exception:
            return elapsed, ttft_time if first_chunk_received else elapsed, first_token_time, None, diagnostic
    except Exception as e:
        elapsed = time.perf_counter() - start_time
        return elapsed, ttft_time if first_chunk_received else elapsed, first_token_time, None, str(e)


def send_streaming_request(
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
) -> Tuple[float, float, Optional[Dict[str, Any]], Optional[str]]:
    """Backward-compatible streaming API; see detailed timing metadata helper."""
    elapsed, first_chunk, _, res_body, error = send_streaming_request_detailed(url, headers, payload)
    return elapsed, first_chunk, res_body, error


class BenchmarkRunner:
    """
    Orchestrates latency, throughput, streaming, concurrency sweeps,
    and prefix caching benchmarks against Vertex AI endpoints.
    """

    def __init__(
        self,
        project_id: str = "dandye-0324-chronicle",
        region: str = "us-central1",
        endpoint_id: Optional[str] = None,
        prompt: str = "Explain the core principles of quantum computing in 3 concise paragraphs.",
        max_tokens: int = 150,
        runs: int = 3,
        concurrency: int = 1,
        stream: bool = False,
        prefix_prompt: Optional[str] = None,
        maas_model: Optional[str] = None,
        flavor: Optional[str] = None,
        vision_check: bool = False,
        output_json: Optional[str] = None,
    ):
        self.project_id = project_id
        resolved_maas, resolved_region = resolve_open_maas_target(
            maas_model=maas_model, flavor=flavor, region=region
        )
        self.maas_model: Optional[str] = resolved_maas
        self.flavor: Optional[str] = flavor
        self.region = resolved_region if resolved_maas else region
        self.endpoint_id = endpoint_id or os.environ.get("VERTEX_ENDPOINT_ID", "")
        self.prompt = prompt
        self.max_tokens = max_tokens
        self.runs = runs
        self.concurrency = concurrency
        self.stream = stream
        self.prefix_prompt = prefix_prompt
        self.vision_check = vision_check
        self.output_json = output_json
        self._token: Optional[str] = None
        self._token_fetched_at: float = 0.0
        self._credentials: Any = None
        self.dedicated_endpoint_dns: Optional[str] = os.environ.get("VERTEX_DEDICATED_ENDPOINT_DNS", "").strip() or None

    def get_token(self, force_refresh: bool = False) -> str:
        """Get or refresh ADC access token cleanly across runs."""
        try:
            import google.auth
            import google.auth.transport.requests
            if self._credentials is None:
                self._credentials, _ = google.auth.default(
                    scopes=["https://www.googleapis.com/auth/cloud-platform"]
                )
            if (
                force_refresh
                or not getattr(self._credentials, "valid", False)
                or not getattr(self._credentials, "token", None)
            ):
                self._credentials.refresh(google.auth.transport.requests.Request())
            if getattr(self._credentials, "token", None):
                self._token = str(self._credentials.token).strip()
                self._token_fetched_at = time.monotonic()
                return self._token
        except Exception:
            self._credentials = None

        now = time.monotonic()
        if not self._token or force_refresh or (now - self._token_fetched_at) > 1800.0:
            self._token = get_adc_token()
            self._token_fetched_at = now
        return self._token

    def get_open_maas_url(self) -> str:
        """Resolve Vertex AI OpenMaaS chat completions endpoint URL."""
        return build_open_maas_url(self.project_id, self.region)

    def get_predict_url(self, endpoint_id: str) -> str:
        """Resolve Vertex AI prediction URL, using dedicatedEndpointDns when applicable."""
        if self.dedicated_endpoint_dns:
            return (
                f"https://{self.dedicated_endpoint_dns}/v1/projects/{self.project_id}"
                f"/locations/{self.region}/endpoints/{endpoint_id}:predict"
            )
        if endpoint_id and endpoint_id.isdigit() and len(endpoint_id) >= 15:
            try:
                res = subprocess.run(
                    [
                        "gcloud",
                        "ai",
                        "endpoints",
                        "describe",
                        endpoint_id,
                        f"--region={self.region}",
                        f"--project={self.project_id}",
                        "--format=value(dedicatedEndpointDns)",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                dns = (res.stdout or "").strip()
                if dns:
                    self.dedicated_endpoint_dns = dns
                    return (
                        f"https://{dns}/v1/projects/{self.project_id}"
                        f"/locations/{self.region}/endpoints/{endpoint_id}:predict"
                    )
            except Exception:
                pass
        return (
            f"https://{self.region}-aiplatform.googleapis.com/v1/projects/{self.project_id}"
            f"/locations/{self.region}/endpoints/{endpoint_id}:predict"
        )

    def discover_endpoint_id(self) -> str:
        """Discover active Vertex AI Endpoint ID if not explicitly specified."""
        if self.endpoint_id:
            return self.endpoint_id

        env_id = os.environ.get("VERTEX_ENDPOINT_ID", "").strip()
        if env_id:
            self.endpoint_id = env_id
            return self.endpoint_id

        print(f"[INFO] Discovering active Vertex AI endpoint in {self.region}...", flush=True)
        try:
            res = subprocess.run(
                [
                    "gcloud",
                    "ai",
                    "endpoints",
                    "list",
                    f"--region={self.region}",
                    f"--project={self.project_id}",
                    "--format=value(name.basename())",
                    "--limit=1",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            found = res.stdout.strip()
            if found:
                self.endpoint_id = found.split()[0]
                print(f"[INFO] Auto-discovered Endpoint ID: {self.endpoint_id}", flush=True)
                return self.endpoint_id
        except Exception as e:
            print(f"[WARNING] Endpoint auto-discovery failed: {e}", flush=True)

        return ""

    def calculate_summary(
        self,
        token_counts: List[int],
        latencies: List[float],
        ttfts: Optional[List[float]] = None,
        sample_output: str = "",
        wall_clock_s: Optional[float] = None,
        first_token_times: Optional[List[Optional[float]]] = None,
        token_count_sources: Optional[List[str]] = None,
        failed_requests: int = 0,
    ) -> Dict[str, Any]:
        """Calculate summary metrics for current runner configuration."""
        return calculate_summary(
            latencies=latencies,
            token_counts=token_counts,
            ttfts=ttfts,
            concurrency=self.concurrency,
            endpoint_id=self.endpoint_id or "",
            region=self.region,
            sample_output=sample_output,
            wall_clock_s=wall_clock_s,
            first_token_times=first_token_times,
            token_count_sources=token_count_sources,
            failed_requests=failed_requests,
        )

    def calculate_prefix_caching_summary(
        self,
        cold_run: Dict[str, Any],
        warm_runs: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Compute comparative metrics for Cold (uncached) vs Warm (prefix cached) runs.
        """
        cold_lat = cold_run.get("latency", 0.0)
        cold_ttft_s = cold_run.get("ttft", cold_run.get("ttft_ms", 0.0) / 1000.0 if "ttft_ms" in cold_run else cold_lat)
        cold_ttft_ms = cold_ttft_s * 1000.0 if cold_ttft_s < 50 else cold_ttft_s
        cold_tps = cold_run.get("tps", 0.0)

        warm_lats = [w.get("latency", 0.0) for w in warm_runs]
        warm_ttfts_ms = []
        for w in warm_runs:
            t = w.get("ttft", w.get("ttft_ms", 0.0) / 1000.0 if "ttft_ms" in w else w.get("latency", 0.0))
            warm_ttfts_ms.append(t * 1000.0 if t < 50 else t)
        warm_tps_list = [w.get("tps", 0.0) for w in warm_runs]

        warm_avg_lat = sum(warm_lats) / len(warm_lats) if warm_lats else 0.0
        warm_avg_ttft_ms = sum(warm_ttfts_ms) / len(warm_ttfts_ms) if warm_ttfts_ms else 0.0
        warm_avg_tps = sum(warm_tps_list) / len(warm_tps_list) if warm_tps_list else 0.0

        latency_speedup = cold_lat / warm_avg_lat if warm_avg_lat > 0 else 1.0
        ttft_reduction_pct = (
            ((cold_ttft_ms - warm_avg_ttft_ms) / cold_ttft_ms) * 100.0 if cold_ttft_ms > 0 else 0.0
        )
        tps_improvement_pct = (
            ((warm_avg_tps - cold_tps) / cold_tps) * 100.0 if cold_tps > 0 else 0.0
        )

        return {
            "cold_latency_s": round(cold_lat, 3),
            "warm_avg_latency_s": round(warm_avg_lat, 3),
            "latency_speedup_ratio": round(latency_speedup, 2),
            "cold_ttft_ms": round(cold_ttft_ms, 1),
            "warm_avg_ttft_ms": round(warm_avg_ttft_ms, 1),
            "cold_first_chunk_ms": round(cold_ttft_ms, 1),
            "warm_avg_first_chunk_ms": round(warm_avg_ttft_ms, 1),
            "ttft_reduction_pct": round(ttft_reduction_pct, 1),
            "cold_tps": round(cold_tps, 1),
            "warm_avg_tps": round(warm_avg_tps, 1),
            "tps_improvement_pct": round(tps_improvement_pct, 1),
            "token_count_source": (
                "actual"
                if cold_run.get("token_count_source") == "actual"
                and warm_runs
                and all(w.get("token_count_source") == "actual" for w in warm_runs)
                else "estimated"
                if cold_run.get("token_count_source") == "estimated"
                and warm_runs
                and all(w.get("token_count_source") == "estimated" for w in warm_runs)
                else "mixed"
            ),
            "ttft_source": "first_network_chunk",
        }

    def run(
        self,
        concurrency: Optional[int] = None,
        runs: Optional[int] = None,
        prompt: Optional[str] = None,
        stream: Optional[bool] = None,
    ) -> Optional[Dict[str, Any]]:
        """Run benchmark execution with given concurrency and repetitions."""
        c = concurrency or self.concurrency
        r = runs or self.runs
        p = prompt or self.prompt
        use_stream = self.stream if stream is None else stream

        if self.maas_model:
            return self._run_open_maas(c=c, r=r, p=p, use_stream=use_stream)

        endpoint_id = self.discover_endpoint_id()
        if not endpoint_id:
            print("[ERROR] No Vertex AI Endpoint specified or discovered.", flush=True)
            return None

        token = self.get_token()
        url = self.get_predict_url(endpoint_id)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        payload = {
            "instances": [
                {
                    "prompt": p,
                    "max_tokens": self.max_tokens,
                    "temperature": 0.2,
                    "top_p": 0.95,
                }
            ]
        }

        print("=" * 60, flush=True)
        print(f" Benchmarking Endpoint: {endpoint_id} ({self.region})", flush=True)
        print(f' Prompt: "{p[:80]}..."' if len(p) > 80 else f' Prompt: "{p}"', flush=True)
        print(f" Max Tokens: {self.max_tokens} | Repetitions: {r} | Concurrency: {c} | Streaming: {use_stream}", flush=True)
        print("=" * 60, flush=True)

        latencies: List[float] = []
        token_counts: List[int] = []
        ttfts: List[float] = []
        first_token_times: List[Optional[float]] = []
        token_count_sources: List[str] = []
        failed_requests = 0
        wall_clock_s = 0.0
        sample_output = ""

        if c == 1:
            for i in range(r):
                if use_stream:
                    elapsed, ttft, first_token_time, res_body, err = send_streaming_request_detailed(url, headers, payload)
                else:
                    elapsed, res_body, err = send_single_request(url, headers, payload)
                    first_token_time = None
                wall_clock_s += elapsed

                if err:
                    failed_requests += 1
                    print(f"  Run {i+1}: [ERROR] {err}", flush=True)
                    continue

                output_text, token_count, token_source = parse_output_details(res_body)
                if token_source == "none":
                    failed_requests += 1
                    print(f"  Run {i+1}: [ERROR] Empty prediction response", flush=True)
                    continue
                if not sample_output and output_text:
                    sample_output = output_text

                tps = token_count / elapsed if elapsed > 0 else 0
                latencies.append(elapsed)
                token_counts.append(token_count)
                token_count_sources.append(token_source)
                if use_stream:
                    ttfts.append(ttft)
                    first_token_times.append(first_token_time)

                ttft_str = f" | First Network Chunk = {ttft*1000:.0f}ms" if use_stream else ""
                print(
                    f"  Run {i+1}: Latency = {elapsed:.2f}s{ttft_str} | {token_source.title()} Tokens = {token_count} | TPS = {tps:.1f} tok/s | TPM = {tps*60:,.0f} tok/min",
                    flush=True,
                )
        else:
            for iteration in range(r):
                print(f"\n--- Concurrency Test (Batch {iteration+1}/{r} with {c} parallel streams) ---", flush=True)
                batch_start = time.perf_counter()
                with ThreadPoolExecutor(max_workers=c) as executor:
                    if use_stream:
                        futures = [executor.submit(send_streaming_request_detailed, url, headers, payload) for _ in range(c)]
                    else:
                        futures = [executor.submit(send_single_request, url, headers, payload) for _ in range(c)]

                    batch_tokens = 0
                    batch_latencies: List[float] = []
                    for f in as_completed(futures):
                        try:
                            res = f.result()
                        except Exception as exc:
                            failed_requests += 1
                            print(f"    Stream failed: {exc}", flush=True)
                            continue
                        if use_stream:
                            elapsed, ttft, first_token_time, res_body, err = res
                        else:
                            elapsed, res_body, err = res
                            ttft = None
                            first_token_time = None

                        if err:
                            failed_requests += 1
                            print(f"    Stream failed: {err}", flush=True)
                            continue

                        output_text, token_count, token_source = parse_output_details(res_body)
                        if token_source == "none":
                            failed_requests += 1
                            print("    Stream failed: Empty prediction response", flush=True)
                            continue
                        if not sample_output and output_text:
                            sample_output = output_text
                        batch_tokens += token_count
                        latencies.append(elapsed)
                        batch_latencies.append(elapsed)
                        token_counts.append(token_count)
                        token_count_sources.append(token_source)
                        if use_stream:
                            ttfts.append(ttft)
                            first_token_times.append(first_token_time)

                batch_total_time = time.perf_counter() - batch_start
                wall_clock_s += batch_total_time
                batch_tps = batch_tokens / batch_total_time if batch_total_time > 0 else 0
                successful_in_batch = len(batch_latencies)
                avg_stream_lat = sum(batch_latencies) / successful_in_batch if successful_in_batch else 0.0

                print(f"  Total Batch Time: {batch_total_time:.2f}s | Avg Stream Latency: {avg_stream_lat:.2f}s")
                print(f"  Batch Output:     {batch_tokens} total tokens across {successful_in_batch} streams")
                print(f"  Aggregate Rate:   {batch_tps:.1f} tokens/sec (TPS) | {batch_tps*60:,.0f} tokens/min (TPM)")

        if not latencies:
            print("[ERROR] No successful benchmark runs.", flush=True)
            return None

        summary = calculate_summary(
            latencies=latencies,
            token_counts=token_counts,
            ttfts=ttfts if use_stream else None,
            first_token_times=first_token_times if use_stream else None,
            token_count_sources=token_count_sources,
            wall_clock_s=wall_clock_s,
            failed_requests=failed_requests,
            concurrency=c,
            endpoint_id=endpoint_id,
            region=self.region,
            sample_output=sample_output,
        )

        print(format_benchmark_table(summary), flush=True)
        return summary

    def run_concurrency_sweep(
        self,
        stream_counts: Tuple[int, ...] = (1, 2, 4, 8),
        runs: int = 3,
        prompt: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Run benchmark sweep over multiple concurrency stream counts."""
        results = []
        print("\n" + "=" * 70)
        print(" STARTING MULTI-STREAM CONCURRENCY SWEEP")
        print(f" Stream counts: {stream_counts}")
        print("=" * 70 + "\n")

        for c in stream_counts:
            summary = self.run(concurrency=c, runs=runs, prompt=prompt)
            if summary:
                results.append(summary)

        # Print consolidated comparison table
        print("\n" + "=" * 78)
        print(" CONCURRENCY SWEEP SUMMARY TABLE")
        print("=" * 78)
        print(f"{'Streams':<10}{'Avg Lat (s)':<14}{'P50 (s)':<10}{'P90 (s)':<10}{'P99 (s)':<10}{'TPS':<12}{'TPM':<12}")
        print("-" * 78)
        for r in results:
            print(
                f"{r.get('concurrency', 1):<10}"
                f"{r.get('avg_latency_s', 0.0):<14.2f}"
                f"{r.get('p50_latency_s', 0.0):<10.2f}"
                f"{r.get('p90_latency_s', 0.0):<10.2f}"
                f"{r.get('p99_latency_s', 0.0):<10.2f}"
                f"{r.get('tps', 0.0):<12.1f}"
                f"{r.get('tpm', 0.0):<12,.0f}"
            )
        print("=" * 78 + "\n")
        return results

    def run_prefix_caching_test(
        self,
        prefix_prompt: Optional[str] = None,
        user_prompts: Optional[List[str]] = None,
        runs: int = 3,
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluate vLLM Prefix Caching efficiency.
        Runs a Cold Request (large shared system prefix), followed by Warm Requests
        sharing the identical prefix to quantify first-chunk reduction and TPS gains.
        """
        endpoint_id = self.discover_endpoint_id()
        if not endpoint_id:
            print("[ERROR] No Vertex AI Endpoint specified or discovered.", flush=True)
            return None

        # Long shared prefix (~1,200 tokens / 4.5KB text) simulating realistic multi-turn system prompt
        default_prefix = (
            prefix_prompt
            or self.prefix_prompt
            or """System Context & Security Operations Runbook:
You are an expert AI Cloud Security Architect specializing in enterprise Google Cloud Platform environments.
Reference Specifications:
1. Zero Trust Architecture: All network flows must verify explicit identity, continuous posture assessment, and least-privilege RBAC.
2. Perimeter Controls: VPC Service Controls (VPC-SC) enforce cryptographic service perimeters around sensitive BigQuery datasets and GCS buckets.
3. Cryptographic Keys: Customer-Managed Encryption Keys (CMEK) backed by Cloud HSM with 90-day automatic key rotation policies.
4. Logging & Telemetry: All administrative, data access, and system event logs stream in real-time via Pub/Sub to Google SecOps Chronicle SIEM.
5. Incident Response Protocol: Sev-1 data exfiltration alerts trigger automated Chronicle SOAR playbooks to revoke IAM credentials and isolate target Compute Engine instances.
Operational Guidelines: Provide concise, technically rigorous, step-by-step diagnostic and remediation instructions formatted in structured markdown.
"""
        )

        test_queries = user_prompts or [
            "Query 1: Explain the step-by-step remediation procedure for an anomalous CMEK key access pattern alert in Chronicle SIEM.",
            "Query 2: Describe how VPC Service Controls perimeters prevent unauthorized exfiltration from Vertex AI custom endpoints.",
            "Query 3: Outline the automated containment workflow when a compromised service account token is detected accessing BigQuery.",
        ]

        token = self.get_token()
        url = self.get_predict_url(endpoint_id)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        print("=" * 70, flush=True)
        print(" PREFIX CACHING EVALUATION BENCHMARK", flush=True)
        print(f" Endpoint: {endpoint_id} ({self.region})", flush=True)
        print(f" Shared Prefix Length: {len(default_prefix)} characters (~{int(len(default_prefix)/3.8)} tokens)", flush=True)
        print("=" * 70, flush=True)

        # Run 1: Cold Request (Prefix not cached yet)
        cold_query = test_queries[0]
        cold_full_prompt = f"{default_prefix}\n\n{cold_query}"
        cold_payload = {
            "instances": [
                {
                    "prompt": cold_full_prompt,
                    "max_tokens": self.max_tokens,
                    "temperature": 0.0,
                    "top_p": 1.0,
                }
            ]
        }

        print("\n[Phase 1] Executing Cold Request (Uncached System Prefix)...", flush=True)
        cold_elapsed, cold_ttft, cold_res, cold_err = send_streaming_request(url, headers, cold_payload)
        if cold_err:
            print(f"[ERROR] Cold request failed: {cold_err}", flush=True)
            return None

        _, cold_tokens, cold_token_source = parse_output_details(cold_res)
        if cold_token_source == "none":
            print("[ERROR] Cold request returned an empty prediction response", flush=True)
            return None
        cold_tps = cold_tokens / cold_elapsed if cold_elapsed > 0 else 0.0
        cold_run = {
            "latency": cold_elapsed,
            "ttft": cold_ttft,
            "tokens": cold_tokens,
            "token_count_source": cold_token_source,
            "tps": cold_tps,
        }
        print(f"  Cold Run Result: Latency = {cold_elapsed:.2f}s | First Network Chunk = {cold_ttft*1000:.0f}ms | Tokens = {cold_tokens} ({cold_token_source}) | TPS = {cold_tps:.1f} tok/s")

        # Phase 2: Warm Requests (Prefix should hit KV cache in vLLM)
        print("\n[Phase 2] Executing Warm Requests (Reusing Cached System Prefix)...", flush=True)
        warm_runs = []
        for idx in range(1, len(test_queries)):
            warm_query = test_queries[idx]
            warm_full_prompt = f"{default_prefix}\n\n{warm_query}"
            warm_payload = {
                "instances": [
                    {
                        "prompt": warm_full_prompt,
                        "max_tokens": self.max_tokens,
                        "temperature": 0.0,
                        "top_p": 1.0,
                    }
                ]
            }
            w_elapsed, w_ttft, w_res, w_err = send_streaming_request(url, headers, warm_payload)
            if w_err:
                print(f"  Warm Run {idx}: [ERROR] {w_err}", flush=True)
                continue
            _, w_tokens, w_token_source = parse_output_details(w_res)
            if w_token_source == "none":
                print(f"  Warm Run {idx}: [ERROR] Empty prediction response", flush=True)
                continue
            w_tps = w_tokens / w_elapsed if w_elapsed > 0 else 0.0
            warm_runs.append({
                "latency": w_elapsed,
                "ttft": w_ttft,
                "tokens": w_tokens,
                "token_count_source": w_token_source,
                "tps": w_tps,
            })
            print(f"  Warm Run {idx} Result: Latency = {w_elapsed:.2f}s | First Network Chunk = {w_ttft*1000:.0f}ms | Tokens = {w_tokens} ({w_token_source}) | TPS = {w_tps:.1f} tok/s")

        if not warm_runs:
            print("[ERROR] No successful warm runs completed.", flush=True)
            return None

        comparison = self.calculate_prefix_caching_summary(cold_run=cold_run, warm_runs=warm_runs)

        print("\n" + "=" * 70)
        print(" PREFIX CACHING EFFICIENCY SUMMARY")
        print("=" * 70)
        print(f"   Cold Latency:            {comparison['cold_latency_s']:.2f} s")
        print(f"   Warm Avg Latency:        {comparison['warm_avg_latency_s']:.2f} s")
        print(f"   Latency Speedup:         {comparison['latency_speedup_ratio']:.2f}x")
        print("-" * 70)
        print(f"   Cold First Network Chunk: {comparison['cold_ttft_ms']:.0f} ms")
        print(f"   Warm Avg First Chunk:     {comparison['warm_avg_ttft_ms']:.0f} ms")
        print(f"   First Chunk Reduction:    {comparison['ttft_reduction_pct']:.1f}%")
        print("-" * 70)
        print(f"   Cold TPS:                {comparison['cold_tps']:.1f} tok/s")
        print(f"   Warm Avg TPS:            {comparison['warm_avg_tps']:.1f} tok/s")
        print(f"   TPS Improvement:         {comparison['tps_improvement_pct']:.1f}%")
        print("=" * 70 + "\n")

        return comparison

    def _run_open_maas(
        self,
        c: int,
        r: int,
        p: str,
        use_stream: bool,
    ) -> Optional[Dict[str, Any]]:
        """Execute single-stream, concurrent, or SSE streaming benchmarks against Vertex OpenMaaS."""
        url = self.get_open_maas_url()
        token = self.get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {
            "model": self.maas_model,
            "messages": [{"role": "user", "content": p}],
            "max_tokens": self.max_tokens,
            "temperature": 0.2,
        }
        if use_stream:
            payload["stream"] = True
            payload["stream_options"] = {"include_usage": True}

        print("=" * 60, flush=True)
        print(f" Benchmarking OpenMaaS Model: {self.maas_model} ({self.region})", flush=True)
        print(f" Max Tokens: {self.max_tokens} | Repetitions: {r} | Concurrency: {c} | Streaming: {use_stream}", flush=True)
        print("=" * 60, flush=True)

        latencies: List[float] = []
        token_counts: List[int] = []
        ttfts: List[float] = []
        first_token_times: List[Optional[float]] = []
        all_itl_chunks_ms: List[float] = []
        token_count_sources: List[str] = []
        usage_records: List[Dict[str, int]] = []
        failed_requests = 0
        wall_clock_s = 0.0
        sample_output = ""
        fatal_status: Optional[int] = None
        fatal_error: Optional[str] = None

        if c == 1:
            for i in range(r):
                headers["Authorization"] = f"Bearer {self.get_token()}"
                if use_stream:
                    elapsed, ttft_s, itl_ms_list, res_body, err, status_code = (
                        send_open_maas_streaming_request(url, headers, payload)
                    )
                else:
                    elapsed, res_body, err, status_code = send_open_maas_request(url, headers, payload)
                    ttft_s = None
                    itl_ms_list = []

                wall_clock_s += elapsed
                if status_code in (401, 403, 404):
                    fatal_status = status_code
                    fatal_error = err or f"HTTP {status_code}"
                    failed_requests += 1
                    print(f"  Run {i+1}: [FATAL {status_code}] {fatal_error}", flush=True)
                    break

                if err:
                    failed_requests += 1
                    print(f"  Run {i+1}: [ERROR] {err}", flush=True)
                    continue

                out_text, tok_cnt, tok_src, usage_dict = _parse_open_maas_output(res_body)
                if tok_src == "none":
                    failed_requests += 1
                    print(f"  Run {i+1}: [ERROR] Empty OpenMaaS response", flush=True)
                    continue

                if not sample_output and out_text:
                    sample_output = out_text
                latencies.append(elapsed)
                token_counts.append(tok_cnt)
                token_count_sources.append(tok_src)
                usage_records.append(usage_dict)
                if use_stream:
                    effective_ttft = ttft_s if ttft_s is not None else elapsed
                    ttfts.append(effective_ttft)
                    first_token_times.append(ttft_s)
                    all_itl_chunks_ms.extend(itl_ms_list)
        else:
            for iteration in range(r):
                headers["Authorization"] = f"Bearer {self.get_token()}"
                batch_start = time.perf_counter()
                with ThreadPoolExecutor(max_workers=c) as executor:
                    if use_stream:
                        futures = [
                            executor.submit(send_open_maas_streaming_request, url, dict(headers), payload)
                            for _ in range(c)
                        ]
                    else:
                        futures = [
                            executor.submit(send_open_maas_request, url, dict(headers), payload)
                            for _ in range(c)
                        ]
                    for fut in as_completed(futures):
                        res = fut.result()
                        if use_stream:
                            elapsed, ttft_s, itl_ms_list, res_body, err, status_code = res
                        else:
                            elapsed, res_body, err, status_code = res
                            ttft_s = None
                            itl_ms_list = []

                        if status_code in (401, 403, 404):
                            fatal_status = status_code
                            fatal_error = err or f"HTTP {status_code}"
                            failed_requests += 1
                            continue
                        if err:
                            failed_requests += 1
                            continue
                        out_text, tok_cnt, tok_src, usage_dict = _parse_open_maas_output(res_body)
                        if tok_src == "none":
                            failed_requests += 1
                            continue
                        if not sample_output and out_text:
                            sample_output = out_text
                        latencies.append(elapsed)
                        token_counts.append(tok_cnt)
                        token_count_sources.append(tok_src)
                        usage_records.append(usage_dict)
                        if use_stream:
                            ttfts.append(ttft_s if ttft_s is not None else elapsed)
                            first_token_times.append(ttft_s)
                            all_itl_chunks_ms.extend(itl_ms_list)
                wall_clock_s += time.perf_counter() - batch_start
                if fatal_status is not None:
                    break

        if fatal_status is not None and not latencies:
            gate_tag = "MAAS_ACCESS_GATED" if fatal_status in (403, 404) else "MAAS_AUTH_ERROR"
            return {
                "status": gate_tag,
                "status_code": fatal_status,
                "error": fatal_error,
                "maas_model": self.maas_model,
                "endpoint_id": self.maas_model or "",
                "region": self.region,
                "url": url,
                "concurrency": c,
                "total_requests": failed_requests,
                "successful_requests": 0,
                "failed_requests": failed_requests,
                "token_count_source": "none",
            }

        if not latencies:
            print("[ERROR] No successful OpenMaaS benchmark runs.", flush=True)
            return None

        summary = calculate_summary(
            latencies=latencies,
            token_counts=token_counts,
            ttfts=ttfts if use_stream else None,
            first_token_times=first_token_times if use_stream else None,
            token_count_sources=token_count_sources,
            wall_clock_s=wall_clock_s,
            failed_requests=failed_requests,
            concurrency=c,
            endpoint_id=self.maas_model or "",
            region=self.region,
            sample_output=sample_output,
        )
        summary["status"] = "OK"
        summary["maas_model"] = self.maas_model
        summary["url"] = url

        if usage_records:
            tot_prompt = sum(u.get("prompt_tokens", 0) for u in usage_records)
            tot_comp = sum(u.get("completion_tokens", 0) for u in usage_records)
            tot_all = sum(u.get("total_tokens", 0) for u in usage_records)
            summary["usage_summary"] = {
                "total_prompt_tokens": tot_prompt,
                "total_completion_tokens": tot_comp,
                "total_tokens": tot_all,
                "avg_prompt_tokens": round(tot_prompt / len(usage_records), 1),
                "avg_completion_tokens": round(tot_comp / len(usage_records), 1),
            }

        if use_stream and ttfts:
            ttft_ms_vals = [t * 1000.0 for t in ttfts]
            summary["ttft_ms"] = round(sum(ttft_ms_vals) / len(ttft_ms_vals), 1)
            summary["ttft_p50_ms"] = round(calculate_percentile(ttft_ms_vals, 50), 1)
            summary["ttft_p95_ms"] = round(calculate_percentile(ttft_ms_vals, 95), 1)
            summary["ttft_source"] = "sse_first_token_delta"
            if all_itl_chunks_ms:
                itl_mean = sum(all_itl_chunks_ms) / len(all_itl_chunks_ms)
                summary["itl_mean_ms"] = round(itl_mean, 2)
                summary["itl_ms"] = round(itl_mean, 2)
                summary["itl_p50_ms"] = round(calculate_percentile(all_itl_chunks_ms, 50), 2)
                summary["itl_p95_ms"] = round(calculate_percentile(all_itl_chunks_ms, 95), 2)
                summary["itl_source"] = "sse_inter_chunk_delta"
            else:
                fallback_itl = summary.get("itl_ms", 0.0)
                summary["itl_mean_ms"] = fallback_itl
                summary["itl_p50_ms"] = fallback_itl
                summary["itl_p95_ms"] = fallback_itl

        if self.vision_check:
            summary["vision_check"] = self.run_vision_check()

        print(format_benchmark_table(summary), flush=True)
        return summary

    def run_vision_check(
        self,
        prompt: str = "Describe the color and geometry of this compact test image in one concise sentence.",
        image_data_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Measure multimodal image_url vision latency and actual token usage against OpenMaaS."""
        target_model = self.maas_model or "deepseek-ai/deepseek-v4.1-flash-1017-maas"
        url = self.get_open_maas_url()
        token = self.get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        data_url = image_data_url or build_compact_test_png_data_url()
        payload: Dict[str, Any] = {
            "model": target_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            "max_tokens": min(self.max_tokens, 128),
            "temperature": 0.1,
        }
        elapsed, res_body, err, status_code = send_open_maas_request(url, headers, payload)
        if status_code in (401, 403, 404):
            gate_tag = "MAAS_ACCESS_GATED" if status_code in (403, 404) else "MAAS_AUTH_ERROR"
            return {
                "status": gate_tag,
                "status_code": status_code,
                "latency_s": round(elapsed, 4),
                "latency_ms": round(elapsed * 1000.0, 1),
                "maas_model": target_model,
                "region": self.region,
                "error": err,
                "token_count_source": "none",
            }
        if err:
            return {
                "status": "ERROR",
                "status_code": status_code,
                "latency_s": round(elapsed, 4),
                "latency_ms": round(elapsed * 1000.0, 1),
                "maas_model": target_model,
                "region": self.region,
                "error": err,
                "token_count_source": "none",
            }
        out_text, _, tok_src, usage_dict = _parse_open_maas_output(res_body)
        return {
            "status": "OK",
            "status_code": status_code or 200,
            "latency_s": round(elapsed, 4),
            "latency_ms": round(elapsed * 1000.0, 1),
            "maas_model": target_model,
            "region": self.region,
            "response_snippet": out_text[:300],
            "token_count_source": tok_src,
            "usage": usage_dict,
        }


def run_benchmark(
    project_id: str,
    region: str,
    endpoint_id: str,
    prompt: str,
    max_tokens: int = 150,
    runs: int = 3,
    concurrency: int = 1,
    stream: bool = False,
    maas_model: Optional[str] = None,
    flavor: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Convenience function maintaining backwards compatibility."""
    runner = BenchmarkRunner(
        project_id=project_id,
        region=region,
        endpoint_id=endpoint_id,
        prompt=prompt,
        max_tokens=max_tokens,
        runs=runs,
        concurrency=concurrency,
        stream=stream,
        maas_model=maas_model,
        flavor=flavor,
    )
    return runner.run()


def main():
    parser = argparse.ArgumentParser(description="Gemma & OpenMaaS Latency & Throughput Benchmark Suite")
    parser.add_argument("--project", default="dandye-0324-chronicle", help="Google Cloud project ID")
    parser.add_argument("--region", default="us-central1", help="Vertex AI region (auto-routes global for OpenMaaS)")
    parser.add_argument("--endpoint", default="", help="Vertex AI Endpoint ID (auto-discovered if omitted)")
    parser.add_argument("--maas-model", default="", help="Serverless Vertex OpenMaaS model ID (e.g. deepseek-ai/deepseek-v4.1-flash-1017-maas)")
    parser.add_argument("--flavor", default="", help="Catalog flavor key from configs/models.json (auto-detects type=maas)")
    parser.add_argument("--vision-check", action="store_true", help="Run multimodal base64 PNG image_url latency check")
    parser.add_argument("--output-json", default=None, help="Optional file path to persist benchmark JSON report")
    parser.add_argument("--prompt", default="Explain the core principles of quantum computing in 3 concise paragraphs.")
    parser.add_argument("--max-tokens", type=int, default=150, help="Maximum generated tokens")
    parser.add_argument("--runs", type=int, default=3, help="Benchmark repetition count")
    parser.add_argument("--concurrency", "-c", type=int, default=1, help="Concurrent parallel streams count")
    parser.add_argument("--streams", type=str, default="", help="Comma-separated stream counts for sweep, e.g. '1,2,4,8'")
    parser.add_argument("--stream", "--streaming", action="store_true", help="Measure streaming first-chunk / SSE TTFT & ITL metrics")
    parser.add_argument("--prefix-caching-test", action="store_true", help="Run prefix caching evaluation test")
    parser.add_argument("--prefix-prompt", type=str, default=None, help="Custom prefix text for prefix caching test")
    args = parser.parse_args()

    runner = BenchmarkRunner(
        project_id=args.project,
        region=args.region,
        endpoint_id=args.endpoint,
        prompt=args.prompt,
        max_tokens=args.max_tokens,
        runs=args.runs,
        concurrency=args.concurrency,
        stream=args.stream,
        prefix_prompt=args.prefix_prompt,
        maas_model=args.maas_model or None,
        flavor=args.flavor or None,
        vision_check=args.vision_check,
        output_json=args.output_json,
    )

    result_payload: Any = None
    if args.prefix_caching_test:
        result_payload = runner.run_prefix_caching_test(prefix_prompt=args.prefix_prompt, runs=args.runs)
    elif args.streams:
        stream_counts = tuple(int(x.strip()) for x in args.streams.split(",") if x.strip())
        result_payload = runner.run_concurrency_sweep(stream_counts=stream_counts, runs=args.runs, prompt=args.prompt)
    else:
        result_payload = runner.run()

    if args.output_json and result_payload is not None:
        out_path = Path(args.output_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result_payload, f, indent=2)
        print(f"[INFO] Saved benchmark JSON report to {out_path}", flush=True)


if __name__ == "__main__":
    main()
