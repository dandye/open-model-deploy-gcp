# Jev System-One Judge vs. Legacy Gemini 2.5 Pro CoT Evaluation

## 1. Architectural Overview

Traditional LLM-as-a-Judge evaluation pipelines rely on System-2 Chain-of-Thought (CoT) generation (`gemini-2.5-pro` generating 200-500 tokens of free-text reasoning before emitting a discrete score). While expressive, System-2 CoT judges introduce three critical failure modes for autonomous optimization loops:

1. **Quantization Jitter**: Sampling discrete integer scores (e.g., 70 vs. 80) across runs creates step-function variance that obscures small prompt improvements.
2. **Decode Latency & Token Cost**: Generating hundreds of reasoning tokens per test case dominates wall-clock evaluation time.
3. **Post-Hoc Rationalization**: Autoregressive CoT generation can drift depending on early sampled tokens, compounding stochasticity.

The **Jev System-One Judge** replaces autoregressive CoT decoding with single-token (`max_output_tokens=1`, `temperature=0.0`) prefill logprob extraction across three mathematical primitives: **Score**, **Noul**, and **Choice**.

---

## 2. Mathematical Primitives

### 2.1 Score Primitive (`evaluate_score`)

Evaluates fine-grained quality across ordinal levels $k \in \{0, 1, 2, 3, 4\}$ mapped to weights $w_k \in \{0.0, 0.25, 0.50, 0.75, 1.0\}$. Given top-$K$ first-token logprobs $\ell_k = \log P(\text{token} = k \mid \text{State}, \text{Criteria})$, normalized probabilities are computed via log-sum-exp:

$$P(k) = \frac{\exp(\ell_k - \max_j \ell_j)}{\sum_{m=0}^{4} \exp(\ell_m - \max_j \ell_j)}$$

The continuous expected rubric score on $[0, 100]$ is:

$$\mathbb{E}[\text{Score}] = 100 \times \sum_{k=0}^{4} w_k P(k)$$

Because $\mathbb{E}[\text{Score}]$ is a continuous expectation over the logit distribution, small shifts in model confidence produce smooth, differentiable-like signal for hillclimbing (`gepa_runbook_optimizer.py`) without quantization jumps.

### 2.2 Noul Primitive (`evaluate_noul`)

Evaluates binary compliance and factual grounding invariants by contrasting the log-probabilities of affirmative (`Yes`) vs. negative (`No`) single-token completions:

$$P(\text{Yes}) = \frac{\exp(\ell_{\text{Yes}})}{\exp(\ell_{\text{Yes}}) + \exp(\ell_{\text{No}})} = \sigma(\ell_{\text{Yes}} - \ell_{\text{No}})$$

Used in `JevSocJudgeEvaluator` for two independent checks:
- **Overall Rubric Compliance** (`noul_pass`): Whether the response satisfies all required SOC triage criteria.
- **Telemetry Grounding** (`noul_grounding`): Whether every IP, domain, hash, and timestamp cited in the report is grounded in the prompt or executed tool observations.

### 2.3 Choice Primitive (`evaluate_choice`)

Evaluates mutually exclusive diagnostic taxonomy categories by mapping options to single-token index labels (`A`, `B`, `C`, ...) and extracting the categorical distribution over the failure taxonomy (`SOC_FAILURE_TAXONOMY`):

- `COMPLIANT_TRIAGE`
- `HALLUCINATED_TELEMETRY`
- `MISSED_CONTAINMENT_ACTION`
- `OVER_CONTAINMENT_FALSE_POSITIVE`
- `INSUFFICIENT_TOOL_INVESTIGATION`
- `REDUNDANT_TOOL_LOOP`
- `MALFORMED_DECISION_BLOCK`

---

## 3. Latency & Calibration Comparison

| Metric | Legacy Gemini 2.5 Pro CoT Judge | Jev System-One Judge (`gemini_system1`) | Improvement |
| :--- | :--- | :--- | :--- |
| **Output Tokens per Primitive** | 250 - 600 tokens | 1 token (`max_output_tokens=1`) | >99% decode reduction |
| **Judge Latency per Case** | 4.5s - 12.0s | 0.25s - 0.60s | 10x - 25x speedup |
| **Score Continuity** | Discrete integer steps | Continuous logit expectation $[0, 100]$ | Zero sampling jitter at $T=0$ |
| **Diagnostic Taxonomy** | Unstructured free-text critique | Calibrated categorical distribution (`Choice`) | Structured GEPA feedback |

---

## 4. Operational Usage

```bash
# Run Gen 3 evaluation with Jev System-One Judge (default)
just eval-soc-jev gemini-2.5-flash-lite 3

# Run Side-by-Side (SxS) comparison of Jev vs. Gemini 2.5 Pro
just eval-soc-sxs-judge gemini-2.5-flash-lite 3

# Dry-run verification with deterministic MockJevBackend
uv run python3 -m scripts.eval_soc_agent --flavor gemini-2.5-flash-lite --gen 3 --judge-backend mock
```
