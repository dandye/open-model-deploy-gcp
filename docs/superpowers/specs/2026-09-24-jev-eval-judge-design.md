# Jev System-One Judge Design Spec

**Date:** 2026-09-24  
**Status:** Draft / Proposed  
**Author:** dandye  
**Target Repository:** `gemma_deploy`  

---

## 1. Executive Summary & Problem Statement

In the current SOC agent evaluation framework (`scripts/eval_soc_agent.py`), semantic grading is performed by `gemini-2.5-pro` using an LLM-as-a-judge paradigm (`judge_response_with_llm`). While effective for subjective reviews, this generative approach introduces several critical engineering bottlenecks:

1. **High Latency:** Generative decoding takes 15 to 35 seconds per case. For a 10-case evaluation suite across multi-model overnight sweeps (32+ models), evaluation grading consumes hours of compute time.
2. **Token & Billing Overhead:** Every case requires generating hundreds of autoregressive completion tokens to output a structured JSON schema, inflating API costs.
3. **Generated Confidence vs. Calibrated Probability:** When an LLM outputs `"grounding_score": 0.95` or `"rubric_score": 85.0`, that number is produced by autoregressive token sampling rather than a mathematically calibrated posterior distribution.
4. **Parsing Fragility:** Despite structured schemas, chat models can occasionally truncate output, trigger safety filter fallbacks, or produce formatting artifacts under complex reasoning chains.

### The Jev (System One) Alternative
Jev is a non-generative, System 1 decision model architecture. Given a serialized State (alert prompt, executed tool trajectory, agent response, ground-truth reference, and operational rubric), Jev evaluates typed questions in a single forward pass without autoregressive text decoding. It exposes three core primitives:

- **Score:** An ordered rubric (e.g. 0 to 10 levels), returning a calibrated expected value $E[S] = \sum_{k=0}^K k \cdot P(S=k)$.
- **Noul:** A calibrated boolean probability $p \in [0.0, 1.0]$ derived directly from model output logits (e.g., $P(\text{YES})$ normalized over $\{\text{YES}, \text{NO}\}$).
- **Choice:** A categorical distribution over $N$ candidates (e.g., specific failure mode taxonomy or routing labels).

By replacing `gemini-2.5-pro` LLM-as-a-judge with Jev, evaluation grading drops from 25s per case to sub-second forward passes (or single-step logprob samplings), completely eliminates broken JSON decoding errors, and provides mathematically calibrated probabilities for grounding, containment pass/fail, and failure mode categorization.

---

## 2. Jev Primitives Mapping to SOC Evaluation

The Jev evaluation engine maps operational SOC triage grading into three typed primitives:

```
+---------------------------------------------------------------------------------------+
|                                    EVALUATION STATE                                   |
| - Incident Alert Prompt                                                               |
| - Actual Tool Execution Trajectory (Iter, Tool, Args, Observations)                   |
| - Agent Final Triage Response & Structured Decision                                  |
| - Reference Ground Truth & Grading Rubric                                            |
+---------------------------------------------------------------------------------------+
                                           |
                                           v
+---------------------------------------------------------------------------------------+
|                                  JEV DECISION ENGINE                                  |
+---------------------------------------------------------------------------------------+
        |                                  |                                   |
        v                                  v                                   v
+---------------+                  +---------------+                   +---------------+
|     SCORE     |                  |     NOUL      |                   |    CHOICE     |
| 10-tier rubric|                  | Boolean probs |                   | Categorical   |
+---------------+                  +---------------+                   +---------------+
        |                                  |                                   |
        | Rubric Level [0..10]             | 1. p_grounded                     | Primary       |
        | Expected Value E[S] * 10         | 2. p_pass                         | Failure Mode  |
        v                                  v                                   v
 Rubric Score [0..100]             Calibrated Verification             Diagnostic Tag
```

### 2.1 Score Primitive (Calibrated Rubric Score)
- **Levels (0 to 10):**
  - `0`: Complete failure, catastrophic hallucination, or unhandled crash.
  - `2`: Gross misclassification or prohibited disruption on critical asset.
  - `4`: Partial triage without required telemetry verification.
  - `6`: Plausible triage but missed key containment or investigative step.
  - `8`: Solid triage with corroborated telemetry and timely containment.
  - `10`: Flawless procedural execution matching expert analyst baseline.
- **Expected Value:**
  $$E[S] = \sum_{k=0}^{10} k \cdot P(S=k)$$
  $$\text{rubric\_score} = 10 \times E[S] \in [0.0, 100.0]$$

### 2.2 Noul Primitives (Calibrated Boolean Probabilities)
1. **`p_grounded` (Grounding Probability):**
   - Question: *"Are all claims, IOC classifications, and forensic assertions in the agent response strictly corroborated by the actual tool execution trajectory?"*
   - Returns calibrated probability $p \in [0.0, 1.0]$.
   - Replaces LLM-generated `grounding_score`.
2. **`p_pass` (Operational Pass Probability):**
   - Question: *"Did the agent satisfy mandatory SOC triage and containment standards for this incident without fatal operational errors?"*
   - Returns calibrated probability $p \in [0.0, 1.0]$.

### 2.3 Choice Primitive (Diagnostic Taxonomy)
- Rather than parsing unstructured critique prose, Jev selects the primary diagnostic verdict from a fixed taxonomy:
  - `A`: `FLAWLESS_CONTAINMENT`
  - `B`: `UNGROUNDED_HALLUCINATED_CLAIM`
  - `C`: `MISSED_MALICIOUS_BREACH` (False Negative)
  - `D`: `OVER_CONTAINMENT_FALSE_ALARM` (False Positive)
  - `E`: `PREMATURE_TERMINATION_ZERO_TOOLS`
  - `F`: `RUNBOOK_PROCEDURAL_VIOLATION`
  - `G`: `DEGRADED_MODE_FAILURE`
- Output includes top predicted category, confidence, and candidate distribution dictionary.

---

## 3. Architecture & Pluggable Backends

To maximize portability across local environments, Google Cloud projects, and standalone deployments, the Jev judge supports a pluggable backend interface:

```
                      +-----------------------------+
                      |        BaseJevBackend       |
                      +-----------------------------+
                      | + evaluate_score(...)       |
                      | + evaluate_noul(...)        |
                      | + evaluate_choice(...)      |
                      | + evaluate_state(...)       |
                      +-----------------------------+
                                     ^
                                     |
         +---------------------------+---------------------------+
         |                           |                           |
+------------------+       +-------------------+       +-------------------+
|  GeminiSystem1   |       |    TypeSafeJev    |       |      MockJev      |
|     Backend      |       |      Backend      |       |      Backend      |
+------------------+       +-------------------+       +-------------------+
| Uses Gemini      |       | Calls external    |       | Offline unit test |
| logprobs + enum  |       | TypeSafe AI API   |       | & hermetic CI     |
| (5 output tokens)|       | /v1/systemone     |       | deterministic     |
+------------------+       +-------------------+       +-------------------+
```

### 3.1 Backend 1: Gemini System-1 (Logprobs + Constrained Enum)
Implemented via Google GenAI SDK (`google.genai`):
- `response_mime_type="text/x.enum"`
- `response_logprobs=True`
- `thinking_level="MINIMAL"` (or effort 0)
- `max_output_tokens=5` (bypassing the 4 structural thought tokens directly into the enum logprob distribution)
- Softmax over target candidate tokens extracts calibrated probabilities.

### 3.2 Backend 2: TypeSafe Jev API
Calls `https://api.typesafe.ai/v1/systemone` using JSON payload:
- State string + array of questions (Score, Noul, Choice).
- Authenticated via `TYPE_SAFE_API_KEY` or `JEV_API_KEY`.

### 3.3 Backend 3: Mock Jev Backend
Hermetic, offline test provider for unit tests and local development when network or credentials are unavailable.

---

## 4. Integration with `eval_soc_agent.py`

1. **CLI Arguments:**
   - `--judge-backend`: Enum `["jev", "gemini-2.5-pro", "mock"]` (default: `"jev"`).
   - `--jev-backend`: Enum `["gemini_system1", "typesafe", "mock"]` (default: `"gemini_system1"`).
   - `--sxs-judge`: Boolean flag enabling side-by-side comparative execution of both Jev and Gemini 2.5 Pro for validation.
2. **Backward Compatibility:**
   - `SemanticJudgeResult` schema is preserved, enriched with Jev calibrated fields:
     - `rubric_score: float` (from Jev Score expected value)
     - `passed: bool` (from Jev Noul $p_{\text{pass}} \ge 0.70$)
     - `grounding_score: float` (from Jev Noul $p_{\text{grounded}}$)
     - `critique: str` (rendered from Jev Choice taxonomy + calibrated probabilities)
     - `jev_metadata: Optional[Dict[str, Any]]` (raw distribution probabilities, ECE data, and entropy)
3. **Scoring Summary & Reporting:**
   - Markdown and JSON scorecards include Jev calibration metrics and speedup multipliers.
