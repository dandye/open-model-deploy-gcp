# Gen 3 Evaluation Framework In-Place Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the Gen 3 Agentic Evaluation Framework in-place to bridge the Advisor vs. Operator role disconnect, eliminate substring regex fallback bugs, purge brittle assertions, and calibrate composite pass/fail criteria so models are accurately evaluated on real SOC capabilities.

**Architecture:** Implement structured decision extraction (`soc_decision` schema), dual-action trajectory verification (matching both executed and recommended actions), context-aware decision outcome classification with negation handling, sanitized dataset assertions, and a calibrated composite pass rule.

**Tech Stack:** Python 3.11+, Pydantic v2, Pytest, Gemini 2.5 Pro (LLM Judge), Signal Detection Theory ($d'$, $c$).

**Spec:** [`docs/superpowers/specs/2026-09-02-gen3-eval-refactor-design.md`](../specs/2026-09-02-gen3-eval-refactor-design.md)

## Global Constraints

- Strictly NO EMOJIS anywhere in code, comments, docstrings, JSON datasets, or documentation.
- Explicit variable definitions.
- Worktree-relative path resolution.
- 100% backward compatibility for `--gen 1` and `--gen 2`.
- All 209+ tests must pass green.

---

## File Structure & Responsibilities

| File Path | Responsibility |
| :--- | :--- |
| [`agent/soc_tier1_agent.py`](../../agent/soc_tier1_agent.py) | Updates persona prompt to instruct structured `soc_decision` block; implements `extract_soc_decision()`. |
| [`scripts/eval_trajectory_verifier.py`](../../scripts/eval_trajectory_verifier.py) | Refactors `verify_agent_trajectory()` to recognize both executed tool actions and structured recommended actions; tracks `recommended_actions`. |
| [`scripts/eval_cost_engine.py`](../../scripts/eval_cost_engine.py) | Enhances `classify_decision_outcome()` with explicit verdict parsing, action intent, and context-aware negation handling. |
| [`configs/evals/gen3/soc_tier1_interactive.json`](../../configs/evals/gen3/soc_tier1_interactive.json) | Sanitizes assertions across 10 cases (removes brittle substring checks like `"escalat"`, `"Qualys"`, `"BENIGN"`). |
| [`scripts/eval_soc_agent.py`](../../scripts/eval_soc_agent.py) | Integrates structured decision extraction and calibrated composite pass evaluation. |
| [`tests/test_gen3_trajectory_verifier.py`](../../tests/test_gen3_trajectory_verifier.py) | Adds tests for dual action verification (executed vs recommended actions). |
| [`tests/test_gen3_cost_engine.py`](../../tests/test_gen3_cost_engine.py) | Adds tests for negation resilience, structured verdict parsing, and decision loss classification. |
| [`tests/test_eval_soc_agent.py`](../../tests/test_eval_soc_agent.py) | Tests calibrated pass evaluation and scorecard rendering. |

---

### Task 1: Structured Decision Schema & Dual-Action Trajectory Verification

**Files:**
- Modify: `agent/soc_tier1_agent.py`
- Modify: `scripts/eval_trajectory_verifier.py`
- Modify: `tests/test_gen3_trajectory_verifier.py`

**Interfaces:**
- `extract_soc_decision(response_text: str) -> Optional[Dict[str, Any]]`
- `TrajectoryVerificationResult`: add `recommended_actions: List[str]`
- `verify_agent_trajectory(..., response_text: str = "")`: extracts both executed and recommended actions, matching expected actions against `all_actions = set(executed) | set(recommended)`.

- [ ] **Step 1: Write failing unit tests for dual action trajectory verification**

```python
# tests/test_gen3_trajectory_verifier.py
def test_dual_action_verification_recommended_actions():
    response = """
    [Analysis & Verdict]
    Verdict: BENIGN
    [Action & Escalation]
    - Close alert as benign false positive.
    ```soc_decision
    {
      "verdict": "BENIGN",
      "recommended_actions": ["close_case"],
      "target_entity": "192.0.2.100"
    }
    ```
    """
    res = verify_agent_trajectory(
        trajectory=[{"iteration": 1, "tool": "get_ip_address_report", "args": {"ip": "192.0.2.100"}}],
        expected_actions=["close_case"],
        prohibited_actions=["isolate_host"],
        response_text=response,
    )
    assert res.actions_matched is True
    assert "close_case" in res.recommended_actions
    assert res.prohibited_actions_avoided is True
```

- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement `extract_soc_decision` in `agent/soc_tier1_agent.py` and dual-action verification in `scripts/eval_trajectory_verifier.py`**
- [ ] **Step 4: Run tests and ensure they pass**
- [ ] **Step 5: Commit changes**

---

### Task 2: Context-Aware Decision Outcome Classifier & Negation Handling

**Files:**
- Modify: `scripts/eval_cost_engine.py`
- Modify: `tests/test_gen3_cost_engine.py`

**Interfaces:**
- `classify_decision_outcome(ground_truth_threat: bool, verdict_str: Optional[str] = None, executed_actions: Optional[List[str]] = None, recommended_actions: Optional[List[str]] = None, response_text: Optional[str] = None) -> DecisionOutcome`

- [ ] **Step 1: Write failing unit test for negation and verdict parsing**

```python
# tests/test_gen3_cost_engine.py
def test_classify_decision_outcome_negation_not_threat():
    # Ground truth is benign, response says "No containment or blocking actions are required"
    outcome = classify_decision_outcome(
        ground_truth_threat=False,
        response_text="No containment or blocking actions are required. Close the alert as benign false positive.",
    )
    assert outcome == DecisionOutcome.TRUE_NEGATIVE

def test_classify_decision_outcome_with_structured_verdict():
    outcome = classify_decision_outcome(
        ground_truth_threat=False,
        verdict_str="BENIGN",
        recommended_actions=["close_case"],
    )
    assert outcome == DecisionOutcome.TRUE_NEGATIVE
```

- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement context-aware verdict classification with negation precedence in `scripts/eval_cost_engine.py`**
- [ ] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Commit changes**

---

### Task 3: Assertion Sanitization & Gen 3 Dataset Refinement

**Files:**
- Modify: `configs/evals/gen3/soc_tier1_interactive.json`
- Modify: `tests/test_eval_config_schema.py`

**Interfaces:**
- Retain objective entity/indicator strings (`DESKTOP-FIN-08`, `192.0.2.100`, `update-service-win32.com`, `10.0.5.23`, `CASE-33279`, `10.0.8.99`).
- Remove subjective substring requirements (`escalat`, `Qualys`).
- Remove brittle negative substring checks (`must_not_contain: ["BENIGN"]`) that trip over natural negation (`"not benign"`).

- [ ] **Step 1: Update schema test to verify sanitized assertions**
- [ ] **Step 2: Sanitize `configs/evals/gen3/soc_tier1_interactive.json`**
- [ ] **Step 3: Run `pytest tests/test_eval_config_schema.py` to verify passing**
- [ ] **Step 4: Commit changes**

---

### Task 4: Calibrated Composite Pass Logic in Evaluation Runner

**Files:**
- Modify: `scripts/eval_soc_agent.py`
- Modify: `tests/test_eval_soc_agent.py`

**Interfaces:**
- `run_evaluation()`: extracts `soc_decision`, passes `response_text` to `verify_agent_trajectory`, classifies decision outcome via `classify_decision_outcome` with structured verdict and actions, and evaluates composite `case_passed`.

- [x] **Step 1: Write unit tests verifying calibrated pass logic**
- [x] **Step 2: Implement calibrated pass logic in `scripts/eval_soc_agent.py`**
- [x] **Step 3: Run tests and verify 100% green**
- [x] **Step 4: Commit changes**

---

### Task 5: End-to-End Re-Evaluation Verification & Leaderboard Update

**Files:**
- Run: `scripts/eval_soc_agent.py` on baseline `gemini-2.5-flash`
- Rebuild scorecard in `docs/soc_model_comparative_evals.md`
- Push updated branch to PR #7

- [x] **Step 1: Run Gen 3 evaluation on `gemini-2.5-flash`**
- [x] **Step 2: Verify that valid triage cases with 100/100 scores now PASS with TRUE_NEGATIVE and no false penalties**
- [x] **Step 3: Run full test suite across all modules**
- [x] **Step 4: Commit and push updates to PR #7**
