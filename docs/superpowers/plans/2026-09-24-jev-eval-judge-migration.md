# Jev System-One Judge Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the slow, generative `gemini-2.5-pro` LLM-as-a-judge auto-rater in the SOC agent evaluation suite with Jev (System One Non-Generative Decision Model), achieving sub-second evaluation latency, calibrated posterior probabilities, and zero parse failures.

**Architecture:** Implement a modular `JevSocJudgeEvaluator` that serializes incident triage state (prompt, real tool execution trajectory, agent response, ground-truth reference, and operational rubric) and evaluates it against three Jev decision primitives: Score (ordered 10-level rubric expected value for continuous 0-100 scoring), Noul (calibrated boolean probabilities for grounding and containment pass/fail), and Choice (categorical failure taxonomy classification). The system connects via pluggable backends (`GeminiSystem1Backend` using logprobs/enums with minimal thinking tokens, `TypeSafeJevBackend` for external API, and `MockJevBackend` for hermetic testing) and integrates seamlessly into `scripts/eval_soc_agent.py` with backward-compatible CLI flags and side-by-side (SxS) comparison.

**Tech Stack:** Python 3.11+, Google GenAI SDK (`google.genai`), Pydantic v2, Pytest, Justfile automation.

**Spec:** [docs/superpowers/specs/2026-09-24-jev-eval-judge-design.md](file:///usr/local/google/home/dandye/Projects/gemma_deploy__worktrees/jev_evals_v0001/docs/superpowers/specs/2026-09-24-jev-eval-judge-design.md)

## Global Constraints

- Strictly NO EMOJIS anywhere in code, comments, docstrings, commit messages, or documentation.
- All paths must resolve relative to repository root (`ROOT_DIR`).
- Always define shell variables explicitly before expanding (e.g. `PROJECT_ID="..."`).
- Never hardcode Google Cloud project IDs or credentials.
- NEVER run `git add .`, `git add -A`, or `git add --all`. Always stage specific files by explicit path (`git add <file1> <file2>`) after checking `git status`.
- Preserve backward compatibility for `--judge-backend gemini-2.5-pro`.

---

### Task 1: Core Jev Primitives & Data Structures

**Files:**
- Create: `agent/jev_judge.py`
- Test: `tests/test_jev_judge_primitives.py`

**Interfaces:**
- Produces:
  - `JevScoreResult(expected_score: float, level_probs: dict[int, float], raw_level: int)`
  - `JevNoulResult(probability: float, verdict: bool)`
  - `JevChoiceResult(selected: str, candidate_probs: dict[str, float])`
  - `JevEvaluationOutput(rubric_score: float, passed: bool, grounding_score: float, primary_choice: str, critique: str, raw_metadata: dict[str, Any])`
  - `BaseJevBackend(ABC)`: abstract methods `evaluate_score`, `evaluate_noul`, `evaluate_choice`
  - `MockJevBackend(BaseJevBackend)`: deterministic test mock returning controllable calibrated primitives
  - `calculate_expected_score(level_probs: dict[int, float], scale_factor: float = 10.0) -> float`
  - `normalize_noul_probs(logprob_yes: float, logprob_no: float) -> float`

- [ ] **Step 1: Write failing tests for Jev primitives & math**

```python
# tests/test_jev_judge_primitives.py
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

    choice_res = backend.evaluate_choice("State", question="Failure mode?", options={"A": "FLAWLESS_CONTAINMENT", "B": "MISSED_BREACH"})
    assert choice_res.selected == "FLAWLESS_CONTAINMENT"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_jev_judge_primitives.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'agent.jev_judge'`

- [ ] **Step 3: Implement minimal classes in `agent/jev_judge.py`**

```python
# agent/jev_judge.py
"""Core Jev (System One) primitives, data models, and backend interfaces."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import math
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class JevScoreResult:
    """Output for a Jev Score primitive (ordered rubric expected value)."""
    expected_score: float
    level_probs: Dict[int, float]
    raw_level: int


@dataclass(frozen=True)
class JevNoulResult:
    """Output for a Jev Noul primitive (calibrated boolean probability)."""
    probability: float
    verdict: bool


@dataclass(frozen=True)
class JevChoiceResult:
    """Output for a Jev Choice primitive (categorical classification)."""
    selected: str
    candidate_probs: Dict[str, float]


@dataclass
class JevEvaluationOutput:
    """Consolidated Jev evaluation result matching SOC judge contract."""
    rubric_score: float
    passed: bool
    grounding_score: float
    primary_choice: str
    critique: str
    raw_metadata: Dict[str, Any] = field(default_factory=dict)


def normalize_noul_probs(logprob_yes: float, logprob_no: float) -> float:
    """Renormalizes log probabilities over {YES, NO} into calibrated P(YES)."""
    max_lp = max(logprob_yes, logprob_no)
    exp_yes = math.exp(logprob_yes - max_lp)
    exp_no = math.exp(logprob_no - max_lp)
    total = exp_yes + exp_no
    return exp_yes / total if total > 0.0 else 0.5


def calculate_expected_score(level_probs: Dict[int, float], scale_factor: float = 10.0) -> float:
    """Computes expected value sum(k * p_k) scaled to target score range."""
    exp_val = sum(float(k) * float(p) for k, p in level_probs.items())
    return round(exp_val * scale_factor, 2)


class BaseJevBackend(ABC):
    """Abstract interface for Jev System One evaluation backends."""

    @abstractmethod
    def evaluate_score(self, state: str, num_levels: int = 10) -> JevScoreResult:
        """Evaluates an ordered rubric score primitive."""

    @abstractmethod
    def evaluate_noul(self, state: str, question: str) -> JevNoulResult:
        """Evaluates a calibrated boolean probability primitive."""

    @abstractmethod
    def evaluate_choice(self, state: str, question: str, options: Dict[str, str]) -> JevChoiceResult:
        """Evaluates a categorical choice primitive."""


class MockJevBackend(BaseJevBackend):
    """Deterministic mock backend for testing and hermetic evaluation."""

    def __init__(
        self,
        score_level: int = 8,
        noul_pass_prob: float = 0.85,
        noul_grounding_prob: float = 0.90,
        choice_label: str = "FLAWLESS_CONTAINMENT",
    ):
        self.score_level = score_level
        self.noul_pass_prob = noul_pass_prob
        self.noul_grounding_prob = noul_grounding_prob
        self.choice_label = choice_label

    def evaluate_score(self, state: str, num_levels: int = 10) -> JevScoreResult:
        probs = {self.score_level: 1.0}
        return JevScoreResult(
            expected_score=float(self.score_level * 10),
            level_probs=probs,
            raw_level=self.score_level,
        )

    def evaluate_noul(self, state: str, question: str) -> JevNoulResult:
        prob = self.noul_grounding_prob if "ground" in question.lower() else self.noul_pass_prob
        return JevNoulResult(probability=prob, verdict=prob >= 0.70)

    def evaluate_choice(self, state: str, question: str, options: Dict[str, str]) -> JevChoiceResult:
        selected = self.choice_label if self.choice_label in options.values() else next(iter(options.values()))
        probs = {opt: (1.0 if opt == selected else 0.0) for opt in options.values()}
        return JevChoiceResult(selected=selected, candidate_probs=probs)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_jev_judge_primitives.py -v`  
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add agent/jev_judge.py tests/test_jev_judge_primitives.py
git commit -m "feat(eval): implement core Jev System One primitives and data structures"
```

---

### Task 2: Gemini System-1 Logprobs Jev Backend

**Files:**
- Create: `agent/jev_backend_gemini.py`
- Test: `tests/test_jev_backend_gemini.py`

**Interfaces:**
- Consumes: `agent/jev_judge.py` (`BaseJevBackend`, `JevScoreResult`, `JevNoulResult`, `JevChoiceResult`, `normalize_noul_probs`, `calculate_expected_score`)
- Produces:
  - `GeminiSystem1Backend(project_id: str, location: str = "us-central1", model: str = "gemini-2.5-flash", client: Optional[genai.Client] = None)`
  - Methods:
    - `_sample_logprobs_enum(prompt: str, enum_values: list[str]) -> dict[str, float]`
    - `evaluate_score(state: str, num_levels: int = 10) -> JevScoreResult`
    - `evaluate_noul(state: str, question: str) -> JevNoulResult`
    - `evaluate_choice(state: str, question: str, options: dict[str, str]) -> JevChoiceResult`

- [ ] **Step 1: Write failing tests with mocked `genai.Client`**

```python
# tests/test_jev_backend_gemini.py
import pytest
from unittest.mock import MagicMock
from agent.jev_backend_gemini import GeminiSystem1Backend

def create_mock_gemini_client(token_probs):
    client = MagicMock()
    mock_candidate = MagicMock()
    top_candidates = []
    for token, logprob in token_probs.items():
        tc = MagicMock()
        tc.token = token
        tc.log_probability = logprob
        top_candidates.append(tc)
    
    mock_logprob_item = MagicMock()
    mock_logprob_item.top_candidates = top_candidates
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_jev_backend_gemini.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'agent.jev_backend_gemini'`

- [ ] **Step 3: Implement `GeminiSystem1Backend` in `agent/jev_backend_gemini.py`**

```python
# agent/jev_backend_gemini.py
"""Gemini System-1 Logprobs Backend implementing Jev primitives."""

import math
from typing import Any, Dict, List, Optional
from google import genai
from google.genai import types

from agent.jev_judge import (
    BaseJevBackend,
    JevChoiceResult,
    JevNoulResult,
    JevScoreResult,
    calculate_expected_score,
    normalize_noul_probs,
)


class GeminiSystem1Backend(BaseJevBackend):
    """Executes Jev primitives using Gemini logprobs, constrained enums, and minimal thinking."""

    def __init__(
        self,
        project_id: str = "dandye-0324-chronicle",
        location: str = "us-central1",
        model: str = "gemini-2.5-flash",
        client: Optional[genai.Client] = None,
    ):
        self.project_id = project_id
        self.location = location
        self.model = model
        self.client = client or genai.Client(vertexai=True, project=project_id, location=location)

    def _sample_logprobs_enum(self, prompt: str, enum_values: List[str]) -> Dict[str, float]:
        """Calls Gemini API with constrained enum and logprobs, returning candidate probabilities."""
        config = types.GenerateContentConfig(
            temperature=0.0,
            max_output_tokens=5,
            response_mime_type="text/x.enum",
            response_schema=types.Schema(
                type=types.Type.STRING,
                enum=enum_values,
            ),
            response_logprobs=True,
            thinking_config=types.ThinkingConfig(thinking_level="MINIMAL"),
        )
        res = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=config,
        )

        probs: Dict[str, float] = {}
        candidate = res.candidates[0] if res.candidates else None
        if not candidate or not candidate.logprobs_result:
            # Fallback to chosen text if logprobs unavailable
            chosen = (res.text or "").strip()
            return {val: (1.0 if val == chosen else 0.0) for val in enum_values}

        # Extract top candidates from the active logprobs position
        top_cands = candidate.logprobs_result.top_candidates
        target_step = top_cands[-1] if top_cands else []
        logprob_map = {c.token.strip(): c.log_probability for c in target_step if c.token}

        # Normalize across the enum values
        exp_sum = 0.0
        exp_vals = {}
        for val in enum_values:
            lp = logprob_map.get(val, -20.0)
            e = math.exp(lp)
            exp_vals[val] = e
            exp_sum += e

        for val in enum_values:
            probs[val] = exp_vals[val] / exp_sum if exp_sum > 0.0 else (1.0 / len(enum_values))

        return probs

    def evaluate_score(self, state: str, num_levels: int = 10) -> JevScoreResult:
        enum_levels = [str(i) for i in range(num_levels + 1)]
        prompt = f"""State:
{state}

Question: On an ordered operational grading scale of 0 to {num_levels} (where 0 is total operational failure and {num_levels} is flawless expert containment), what score does this response earn?
Reply with a single digit from 0 to {num_levels}."""
        probs_str = self._sample_logprobs_enum(prompt, enum_levels)
        probs_int = {int(k): v for k, v in probs_str.items() if k.isdigit()}
        exp_score = calculate_expected_score(probs_int, scale_factor=10.0)
        best_level = max(probs_int.items(), key=lambda x: x[1])[0] if probs_int else 0
        return JevScoreResult(expected_score=exp_score, level_probs=probs_int, raw_level=best_level)

    def evaluate_noul(self, state: str, question: str) -> JevNoulResult:
        prompt = f"""State:
{state}

Question: {question}
Reply with YES or NO."""
        probs = self._sample_logprobs_enum(prompt, ["YES", "NO"])
        p_yes = probs.get("YES", 0.5)
        return JevNoulResult(probability=p_yes, verdict=p_yes >= 0.70)

    def evaluate_choice(self, state: str, question: str, options: Dict[str, str]) -> JevChoiceResult:
        keys = list(options.keys())
        options_text = "\n".join(f"{k}: {desc}" for k, desc in options.items())
        prompt = f"""State:
{state}

Question: {question}
Options:
{options_text}

Reply with the single option letter."""
        probs = self._sample_logprobs_enum(prompt, keys)
        best_key = max(probs.items(), key=lambda x: x[1])[0] if probs else keys[0]
        labeled_probs = {options[k]: probs.get(k, 0.0) for k in keys}
        return JevChoiceResult(selected=options[best_key], candidate_probs=labeled_probs)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_jev_backend_gemini.py -v`  
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add agent/jev_backend_gemini.py tests/test_jev_backend_gemini.py
git commit -m "feat(eval): implement Gemini System-1 logprobs backend for Jev judge"
```

---

### Task 3: TypeSafe Jev Remote Client Backend

**Files:**
- Create: `agent/jev_backend_typesafe.py`
- Test: `tests/test_jev_backend_typesafe.py`

**Interfaces:**
- Consumes: `agent/jev_judge.py` (`BaseJevBackend`, `JevScoreResult`, `JevNoulResult`, `JevChoiceResult`)
- Produces:
  - `TypeSafeJevBackend(api_key: Optional[str] = None, endpoint_url: str = "https://api.typesafe.ai/v1/systemone")`
  - Methods:
    - `evaluate_score(state: str, num_levels: int = 10) -> JevScoreResult`
    - `evaluate_noul(state: str, question: str) -> JevNoulResult`
    - `evaluate_choice(state: str, question: str, options: dict[str, str]) -> JevChoiceResult`

- [ ] **Step 1: Write failing tests for TypeSafe Jev API backend with mock requests**

```python
# tests/test_jev_backend_typesafe.py
import pytest
from unittest.mock import patch, MagicMock
from agent.jev_backend_typesafe import TypeSafeJevBackend

@patch("urllib.request.urlopen")
def test_typesafe_jev_evaluate_noul(mock_urlopen):
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"results": [{"primitive": "noul", "probability": 0.94, "verdict": true}]}'
    mock_urlopen.return_value.__enter__.return_value = mock_resp

    backend = TypeSafeJevBackend(api_key="test-key")
    res = backend.evaluate_noul("State text", "Is this response grounded?")
    assert res.probability == 0.94
    assert res.verdict is True

@patch("urllib.request.urlopen")
def test_typesafe_jev_evaluate_score(mock_urlopen):
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"results": [{"primitive": "score", "expected_value": 8.5, "distribution": {"8": 0.5, "9": 0.5}}]}'
    mock_urlopen.return_value.__enter__.return_value = mock_resp

    backend = TypeSafeJevBackend(api_key="test-key")
    res = backend.evaluate_score("State text", num_levels=10)
    assert res.expected_score == 85.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_jev_backend_typesafe.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'agent.jev_backend_typesafe'`

- [ ] **Step 3: Implement `TypeSafeJevBackend` in `agent/jev_backend_typesafe.py`**

```python
# agent/jev_backend_typesafe.py
"""TypeSafe AI Jev Remote HTTP Client Backend."""

import json
import os
from typing import Any, Dict, List, Optional
import urllib.request
import urllib.error

from agent.jev_judge import (
    BaseJevBackend,
    JevChoiceResult,
    JevNoulResult,
    JevScoreResult,
)


class TypeSafeJevBackend(BaseJevBackend):
    """Executes Jev primitives via TypeSafe AI System One REST API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint_url: str = "https://api.typesafe.ai/v1/systemone",
    ):
        self.api_key = api_key or os.environ.get("TYPE_SAFE_API_KEY") or os.environ.get("JEV_API_KEY", "")
        self.endpoint_url = endpoint_url

    def _post_systemone(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Sends POST request to TypeSafe System One API."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.endpoint_url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"TypeSafe Jev API HTTP Error {e.code}: {e.read().decode('utf-8')}") from e
        except Exception as e:
            raise RuntimeError(f"TypeSafe Jev API request failed: {e}") from e

    def evaluate_score(self, state: str, num_levels: int = 10) -> JevScoreResult:
        payload = {
            "state": state,
            "questions": [{
                "primitive": "score",
                "rubric_levels": num_levels,
            }],
        }
        res = self._post_systemone(payload)
        item = res.get("results", [{}])[0]
        exp_val = float(item.get("expected_value", 0.0))
        dist = {int(k): float(v) for k, v in item.get("distribution", {}).items()}
        return JevScoreResult(
            expected_score=round(exp_val * 10.0, 2),
            level_probs=dist,
            raw_level=int(round(exp_val)),
        )

    def evaluate_noul(self, state: str, question: str) -> JevNoulResult:
        payload = {
            "state": state,
            "questions": [{
                "primitive": "noul",
                "question": question,
            }],
        }
        res = self._post_systemone(payload)
        item = res.get("results", [{}])[0]
        prob = float(item.get("probability", 0.5))
        return JevNoulResult(probability=prob, verdict=prob >= 0.70)

    def evaluate_choice(self, state: str, question: str, options: Dict[str, str]) -> JevChoiceResult:
        payload = {
            "state": state,
            "questions": [{
                "primitive": "choice",
                "question": question,
                "candidates": list(options.values()),
            }],
        }
        res = self._post_systemone(payload)
        item = res.get("results", [{}])[0]
        selected = str(item.get("selected", next(iter(options.values()))))
        cand_probs = {str(k): float(v) for k, v in item.get("candidate_probs", {}).items()}
        return JevChoiceResult(selected=selected, candidate_probs=cand_probs)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_jev_backend_typesafe.py -v`  
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add agent/jev_backend_typesafe.py tests/test_jev_backend_typesafe.py
git commit -m "feat(eval): implement TypeSafe Jev remote API client backend"
```

---

### Task 4: SOC Evaluation State Serializer & Jev Evaluator

**Files:**
- Create: `agent/jev_evaluator.py`
- Test: `tests/test_jev_evaluator.py`

**Interfaces:**
- Consumes: `agent/jev_judge.py` (`BaseJevBackend`, `JevEvaluationOutput`, `MockJevBackend`)
- Produces:
  - `build_soc_evaluation_state(prompt: str, response: str, reference: dict[str, Any], rubric: str, trajectory: Optional[list[dict[str, Any]]] = None) -> str`
  - `JevSocJudgeEvaluator(backend: BaseJevBackend)`
  - Methods:
    - `evaluate_case(prompt: str, response: str, reference: dict[str, Any], rubric: str, trajectory: Optional[list[dict[str, Any]]] = None) -> JevEvaluationOutput`
    - `to_semantic_judge_result(output: JevEvaluationOutput) -> Any` (compatible with `SemanticJudgeResult`)

- [ ] **Step 1: Write failing tests for SOC state builder and evaluator**

```python
# tests/test_jev_evaluator.py
import pytest
from agent.jev_judge import MockJevBackend
from agent.jev_evaluator import JevSocJudgeEvaluator, build_soc_evaluation_state

def test_build_soc_evaluation_state_contains_trajectory():
    traj = [{"step": 1, "tool": "search_threat_intelligence", "args": {"ioc": "198.51.100.22"}, "observation": "Malicious C2"}]
    state = build_soc_evaluation_state(
        prompt="Alert: Suspicious connection",
        response="I isolated the host.",
        reference={"ground_truth": "Malicious"},
        rubric="Must isolate host.",
        trajectory=traj,
    )
    assert "Tool Execution Trajectory" in state
    assert "search_threat_intelligence" in state
    assert "198.51.100.22" in state
    assert "Must isolate host." in state

def test_jev_soc_judge_evaluator_evaluates_case():
    backend = MockJevBackend(score_level=9, noul_pass_prob=0.92, noul_grounding_prob=0.96, choice_label="FLAWLESS_CONTAINMENT")
    evaluator = JevSocJudgeEvaluator(backend=backend)
    res = evaluator.evaluate_case(
        prompt="Alert: ransomware",
        response="Contained host.",
        reference={"status": "malicious"},
        rubric="Isolate host immediately.",
    )
    assert res.rubric_score == 90.0
    assert res.passed is True
    assert res.grounding_score == 0.96
    assert "FLAWLESS_CONTAINMENT" in res.primary_choice
    assert "Jev System-One" in res.critique
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_jev_evaluator.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'agent.jev_evaluator'`

- [ ] **Step 3: Implement `JevSocJudgeEvaluator` in `agent/jev_evaluator.py`**

```python
# agent/jev_evaluator.py
"""SOC Evaluation State Serializer and Jev System One Judge Evaluator."""

import json
from typing import Any, Dict, List, Optional
from agent.jev_judge import BaseJevBackend, JevEvaluationOutput

# Standard SOC Failure Mode Taxonomy for Jev Choice primitive
SOC_FAILURE_TAXONOMY: Dict[str, str] = {
    "A": "FLAWLESS_CONTAINMENT",
    "B": "UNGROUNDED_HALLUCINATED_CLAIM",
    "C": "MISSED_MALICIOUS_BREACH",
    "D": "OVER_CONTAINMENT_FALSE_ALARM",
    "E": "PREMATURE_TERMINATION_ZERO_TOOLS",
    "F": "RUNBOOK_PROCEDURAL_VIOLATION",
    "G": "DEGRADED_MODE_FAILURE",
}


def build_soc_evaluation_state(
    prompt: str,
    response: str,
    reference: Dict[str, Any],
    rubric: str,
    trajectory: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Serializes alert, trajectory, response, reference, and rubric into Jev state."""
    if trajectory and len(trajectory) > 0:
        traj_lines = []
        for step in trajectory:
            t_num = step.get("iteration", step.get("step", "?"))
            t_name = step.get("tool", "unknown")
            t_in = json.dumps(step.get("args", step.get("input", {})))
            t_obs = str(step.get("observation", ""))[:500]
            traj_lines.append(f"Step {t_num}: Tool '{t_name}' invoked with {t_in} -> Observation: {t_obs}")
        traj_str = "\n".join(traj_lines)
    else:
        traj_str = "NO TOOLS WERE INVOKED DURING THIS INVESTIGATION (0 tool calls executed)."

    return f"""### Incident Alert Prompt:
{prompt.strip()}

### Actual Tool Execution Trajectory:
{traj_str}

### Agent Response:
{response.strip()}

### Ground Truth Reference:
{json.dumps(reference, indent=2)}

### Operational Grading Rubric:
{rubric.strip()}
"""


class JevSocJudgeEvaluator:
    """Evaluates SOC triage episodes using Jev decision primitives."""

    def __init__(self, backend: BaseJevBackend):
        self.backend = backend

    def evaluate_case(
        self,
        prompt: str,
        response: str,
        reference: Dict[str, Any],
        rubric: str,
        trajectory: Optional[List[Dict[str, Any]]] = None,
    ) -> JevEvaluationOutput:
        """Executes Score, Noul, and Choice primitives across serialized state."""
        state = build_soc_evaluation_state(
            prompt=prompt,
            response=response,
            reference=reference,
            rubric=rubric,
            trajectory=trajectory,
        )

        # 1. Score Primitive (Continuous 0-100 rubric expected score)
        score_res = self.backend.evaluate_score(state, num_levels=10)

        # 2. Noul Primitives (Calibrated Grounding and Operational Pass probabilities)
        noul_ground = self.backend.evaluate_noul(
            state,
            question="Are all claims, IOC classifications, and forensic assertions in the agent response strictly corroborated by the actual tool execution trajectory without hallucination?",
        )
        noul_pass = self.backend.evaluate_noul(
            state,
            question="Did the agent satisfy mandatory SOC triage and containment standards for this incident without fatal operational errors?",
        )

        # 3. Choice Primitive (Diagnostic Taxonomy)
        choice_res = self.backend.evaluate_choice(
            state,
            question="Which category best describes the agent's primary operational performance or failure mode?",
            options=SOC_FAILURE_TAXONOMY,
        )

        critique = (
            f"[Jev System-One Decision] Diagnosis: {choice_res.selected} | "
            f"Pass Probability: {noul_pass.probability:.1%} | "
            f"Grounding Probability: {noul_ground.probability:.1%} | "
            f"Rubric Expected Score: {score_res.expected_score:.1f}/100"
        )

        return JevEvaluationOutput(
            rubric_score=score_res.expected_score,
            passed=noul_pass.verdict and score_res.expected_score >= 70.0,
            grounding_score=round(noul_ground.probability, 3),
            primary_choice=choice_res.selected,
            critique=critique,
            raw_metadata={
                "score_levels": score_res.level_probs,
                "noul_pass_prob": noul_pass.probability,
                "noul_grounding_prob": noul_ground.probability,
                "choice_probs": choice_res.candidate_probs,
            },
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_jev_evaluator.py -v`  
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add agent/jev_evaluator.py tests/test_jev_evaluator.py
git commit -m "feat(eval): implement SOC evaluation state builder and Jev evaluator"
```

---

### Task 5: Integrate Jev Judge into `scripts/eval_soc_agent.py`

**Files:**
- Modify: `scripts/eval_soc_agent.py`
- Modify: `tests/test_eval_soc_agent.py`

**Interfaces:**
- CLI Flags added:
  - `--judge-backend`: Choices `["jev", "gemini-2.5-pro", "mock"]` (default: `"jev"`).
  - `--jev-backend`: Choices `["gemini_system1", "typesafe", "mock"]` (default: `"gemini_system1"`).
  - `--sxs-judge`: Store both Jev and Gemini 2.5 Pro scores side-by-side for comparison.
- Summary and Markdown reporting updated to display Jev metrics (pass probability, grounding probability, diagnostic taxonomy choice).

- [ ] **Step 1: Write failing tests in `tests/test_eval_soc_agent.py` for `--judge-backend` argument parsing and mock execution**

```python
# In tests/test_eval_soc_agent.py
def test_eval_soc_agent_parser_supports_judge_backend_flags():
    from scripts.eval_soc_agent import parse_args
    args = parse_args(["--flavor", "gemini-2.5-flash-lite", "--judge-backend", "jev", "--jev-backend", "mock"])
    assert args.judge_backend == "jev"
    assert args.jev_backend == "mock"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_eval_soc_agent.py -k "test_eval_soc_agent_parser_supports_judge_backend_flags" -v`  
Expected: FAIL with unrecognized arguments

- [ ] **Step 3: Modify `scripts/eval_soc_agent.py`**

1. Import `JevSocJudgeEvaluator`, `MockJevBackend`, `GeminiSystem1Backend`, `TypeSafeJevBackend`.
2. Add `--judge-backend`, `--jev-backend`, `--sxs-judge` to `argparse`.
3. In `run_evaluation`:
   - Initialize appropriate judge: if `judge_backend == "jev"`, instantiate backend and `JevSocJudgeEvaluator`.
   - Call Jev evaluator during case evaluation loop, creating a `SemanticJudgeResult` populated with calibrated Jev outputs.
   - If `--sxs-judge` is enabled, call both Jev and `judge_response_with_llm`, recording the delta in latency and score.
4. Update `calculate_aggregate_score` and Markdown scorecard rendering to display Jev metrics.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_eval_soc_agent.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/eval_soc_agent.py tests/test_eval_soc_agent.py
git commit -m "feat(eval): wire Jev judge into SOC evaluation runner with CLI flags and reports"
```

---

### Task 6: Update Justfile Recipes, Sweeps, and Documentation

**Files:**
- Modify: `Justfile`
- Modify: `scripts/run_overnight_sweep.py`
- Create: `tests/test_jev_justfile_recipes.py`
- Create: `docs/jev_vs_gemini_judge_evaluation.md`

**Interfaces:**
- Justfile recipes:
  - `eval-soc-jev flavor="gemini-2.5-flash-lite" gen="3"`
  - `eval-soc-sxs-judge flavor="gemini-2.5-flash-lite" gen="3"`
- Overnight sweep supports `--judge-backend jev`.
- Documentation comparing Jev vs Gemini 2.5 Pro latency (10x-50x speedup), zero decode tokens, and calibration metrics.

- [ ] **Step 1: Write test for Justfile recipe validation**

```python
# tests/test_jev_justfile_recipes.py
from pathlib import Path

def test_justfile_contains_jev_recipes():
    justfile_path = Path(__file__).resolve().parent.parent / "Justfile"
    content = justfile_path.read_text(encoding="utf-8")
    assert "eval-soc-jev" in content
    assert "--judge-backend" in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_jev_justfile_recipes.py -v`  
Expected: FAIL

- [ ] **Step 3: Implement recipes in `Justfile`, update sweep runner, and write doc**

Add recipes:
```just
# Run SOC Agent evaluation with Jev System-One judge
eval-soc-jev flavor="gemini-2.5-flash-lite" gen="3":
    @uv run python3 -m scripts.eval_soc_agent --flavor "{{flavor}}" --gen {{gen}} --judge-backend jev --output-report "docs/soc_eval_results/gen{{gen}}_jev_{{flavor}}_report.md"

# Run SOC Agent evaluation with Side-by-Side (SxS) Jev vs Gemini 2.5 Pro judges
eval-soc-sxs-judge flavor="gemini-2.5-flash-lite" gen="3":
    @uv run python3 -m scripts.eval_soc_agent --flavor "{{flavor}}" --gen {{gen}} --judge-backend jev --sxs-judge --output-report "docs/soc_eval_results/gen{{gen}}_sxs_{{flavor}}_report.md"
```
Create `docs/jev_vs_gemini_judge_evaluation.md` with architectural analysis, math formulas for Score/Noul/Choice, latency benchmarks, and operational guidance.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_jev_justfile_recipes.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add Justfile scripts/run_overnight_sweep.py tests/test_jev_justfile_recipes.py docs/jev_vs_gemini_judge_evaluation.md
git commit -m "feat(eval): add Justfile recipes, sweep support, and documentation for Jev judge"
```

---

### Task 7: End-to-End Verification & Baseline Dry-Run

**Files:**
- Execute dry-run: `python3 -m scripts.eval_soc_agent --flavor gemini-2.5-flash-lite --gen 3 --judge-backend mock --evalset configs/evals/gen3/soc_tier1_interactive.json`
- Full test suite: `.venv/bin/pytest`

- [ ] **Step 1: Execute test suite across all repo tests**

Run: `.venv/bin/pytest tests/test_jev_*.py tests/test_eval_soc_agent.py -v`  
Expected: PASS with 100% success rate.

- [ ] **Step 2: Run dry-run evaluation with `--judge-backend mock`**

Run:
```bash
python3 -m scripts.eval_soc_agent --flavor gemini-2.5-flash-lite --gen 3 --judge-backend mock --evalset configs/evals/gen3/soc_tier1_interactive.json --output-report "docs/soc_eval_results/test_jev_dryrun.md" --output-json "docs/soc_eval_results/test_jev_dryrun.json"
```
Expected: Completed 10 cases with Jev System-One evaluation metrics, zero errors.

- [ ] **Step 3: Commit final verification artifacts**

```bash
git add docs/soc_eval_results/test_jev_dryrun.md docs/soc_eval_results/test_jev_dryrun.json
git commit -m "test(eval): verify end-to-end evaluation pipeline with Jev System One judge"
```
