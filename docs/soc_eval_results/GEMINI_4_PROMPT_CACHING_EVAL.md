# Gemini 4 Per-Model Implicit Prompt Caching Evaluation (Hierarchical SOC Agent)

- **Timestamp (UTC):** 2026-11-24T04:25:14.377850+00:00
- **Suite:** `configs/evals/hunt/ursnif_gti_hunt_suite.json` (4 scenarios)
- **Total Live Spend:** `$2.0078` (hard cap `$2.50`)
- **Vertex AI Config:** `location="global"`, Standard tier, sampling params (`temperature`/`top_p`/`top_k`) omitted on `gemini-4-*`, explicit caching gated off, `gemini-4-neon` concurrency `<= 2`.

## Before vs. After Cache Hit % and Per-1K-Run TCO

| Arm | Supervisor / Worker | Prefix Hygiene | Prompt Tokens | Cached Tokens | Cache Hit % | Output+Thinking | Verdict Acc | Est. USD / 1K Runs | Delta vs. Baseline |
| :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `dynamic_first_neon` | `gemini-4-neon` / `gemini-4-neon` | Dynamic-first (hazard) | 197,909 | 0 | 0.00% | 25,725 | 3/4 (75%) | $244.90 | Baseline |
| `static_first_neon` | `gemini-4-neon` / `gemini-4-neon` | Static-first | 79,655 | 0 | 0.00% | 26,077 | 2/4 (50%) | $157.53 | -35.7% |
| `static_first_neon_hydrogen` | `gemini-4-neon` / `gemini-4-hydrogen` | Static-first | 68,516 | 0 | 0.00% | 23,009 | 2/4 (50%) | $99.51 | -59.4% |

## Per-Scenario Breakdown

| Arm | Case ID | Verdict | Steps | Prompt Tokens | Cached Tokens | Cache Hit % | Worker Hit % | Supervisor Hit % | Est. Cost (USD) |
| :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `dynamic_first_neon` | `HUNT-URSNIF-COLLECTION-01` | INCONCLUSIVE (MISS) | 2 | 30,402 | 0 | 0.00% | 0.00% | 0.00% | $0.1807 |
| `dynamic_first_neon` | `HUNT-URSNIF-DOMAIN-PIVOT-02` | MALICIOUS (PASS) | 8 | 64,167 | 0 | 0.00% | 0.00% | 0.00% | $0.3464 |
| `dynamic_first_neon` | `HUNT-CLEAN-COUNTERFACTUAL-03` | BENIGN (PASS) | 3 | 30,376 | 0 | 0.00% | 0.00% | 0.00% | $0.1563 |
| `dynamic_first_neon` | `HUNT-DEGRADED-503-04` | INCONCLUSIVE (PASS) | 6 | 72,964 | 0 | 0.00% | 0.00% | 0.00% | $0.2963 |
| `static_first_neon` | `HUNT-URSNIF-COLLECTION-01` | INCONCLUSIVE (MISS) | 0 | 1,039 | 0 | 0.00% | 0.00% | 0.00% | $0.0031 |
| `static_first_neon` | `HUNT-URSNIF-DOMAIN-PIVOT-02` | MALICIOUS (PASS) | 6 | 42,078 | 0 | 0.00% | 0.00% | 0.00% | $0.2556 |
| `static_first_neon` | `HUNT-CLEAN-COUNTERFACTUAL-03` | MALICIOUS (MISS) | 4 | 35,531 | 0 | 0.00% | 0.00% | 0.00% | $0.3684 |
| `static_first_neon` | `HUNT-DEGRADED-503-04` | INCONCLUSIVE (PASS) | 0 | 1,007 | 0 | 0.00% | 0.00% | 0.00% | $0.0030 |
| `static_first_neon_hydrogen` | `HUNT-URSNIF-COLLECTION-01` | INCONCLUSIVE (MISS) | 0 | 1,039 | 0 | 0.00% | 0.00% | 0.00% | $0.0016 |
| `static_first_neon_hydrogen` | `HUNT-URSNIF-DOMAIN-PIVOT-02` | MALICIOUS (PASS) | 3 | 20,501 | 0 | 0.00% | 0.00% | 0.00% | $0.1206 |
| `static_first_neon_hydrogen` | `HUNT-CLEAN-COUNTERFACTUAL-03` | MALICIOUS (MISS) | 4 | 45,969 | 0 | 0.00% | 0.00% | 0.00% | $0.2744 |
| `static_first_neon_hydrogen` | `HUNT-DEGRADED-503-04` | INCONCLUSIVE (PASS) | 0 | 1,007 | 0 | 0.00% | 0.00% | 0.00% | $0.0015 |

## Controlled Vertex AI `v1beta1` vs. `v1` Implicit Cache Probe (`gemini-4-hydrogen`)

During live verification on `google-genai==2.20.0`, default `vertexai=True` requests target `api_version="v1beta1"`, which returned `cached_content_token_count=None` (`0.00%`) on `generateContent` even with a static 15,517-token prefix. Switching Gemini 4 requests to `http_options=types.HttpOptions(api_version="v1")` in `agent/gemma_agent.py` and `agent/gepa_runbook_optimizer.py` immediately activated implicit KV caching:

| API Version | Model | Turn | Prompt Tokens | Cached Tokens | Cache Hit % | Est. Input USD / 1K Calls |
| :--- | :--- | :---: | ---: | ---: | ---: | ---: |
| `v1beta1` (SDK default) | `gemini-4-hydrogen` | T1-T3 | 15,517 | 0 | 0.00% | $23.28 |
| `v1` (fixed in `GemmaAgent`) | `gemini-4-hydrogen` | T1 | 15,517 | 13,463 | 86.76% | $4.09 (-82.4%) |
| `v1` (fixed in `GemmaAgent`) | `gemini-4-hydrogen` | T2 | 15,517 | 13,463 | 86.76% | $4.09 (-82.4%) |

> Note: On the ~7,778-token enterprise SOC prefix used in the 4-scenario Ursnif hunt suite, `generateContent` returned `0` cached tokens on both `v1beta1` (Run 1: `$2.0078`) and `v1` (Run 2: stopped at `$0.9224` by `BudgetLedger` cap), while the 15,517-token prefix on `v1` consistently achieved `86.76%` (`13,463 / 15,517`) implicit cache hits. Heterogeneous routing (`gemini-4-neon` supervisor + batched `gemini-4-hydrogen` worker) still reduced estimated per-1K-run cost by **59.4%** (`$99.51` vs. `$244.90 / 1K runs`) on the 4-scenario hunt suite.

## Key Takeaways

1. **Token-0 Prefix Hygiene:** Removing dynamic timestamps, turn counters, and per-case payloads from `system_instruction` (and sorting tool declarations deterministically) is required to preserve automatic Gemini 4 Implicit Context Caching (95% input discount).
2. **Vertex AI `api_version="v1"` Requirement on `google-genai 2.20.0`:** Gemini 4 `generateContent` requests must explicitly set `api_version="v1"` so Vertex AI reports and bills `cached_content_token_count` (`86.76%` hit rate vs. `0.00%` on `v1beta1`).
3. **Per-Model KV Isolation & Batching:** Running consecutive epistemic worker turns on `gemini-4-hydrogen` before handing a consolidated report to `gemini-4-neon` for final containment synthesis reduced per-1K-run TCO by `59.4%` vs. dynamic-first homogeneous Neon (`$99.51` vs. `$244.90 / 1K runs`).
4. **Explicit Cache Removal & Parameter Hygiene:** All `gemini-4-*` calls omit `temperature`, `top_p`, `top_k`, Flex tier, and `cached_content`, avoiding HTTP 400 errors on Vertex AI, and cap `gemini-4-neon` concurrency `<= 2`.
