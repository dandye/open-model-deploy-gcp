# Gen 3 Comprehensive Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate artificial token truncation limits, decouple primary vs secondary action verification, support multi-syntax tool calling with exemplars, upgrade telemetry fidelity with realistic noisy fields, supply explicit CMDB business context, and score counterfactual consistency across the Gen 3 suite.

**Architecture:** Unbounded token allocation in backend drivers, tiered primary/secondary action matching, JSON & ReAct multi-parser with few-shot exemplars, rich UDM/VT telemetry payloads, CMDB asset context, and counterfactual pair scoring.

**Tech Stack:** Python 3.11+, Pytest, Google GenAI SDK, Signal Detection Theory ($d'$, $c$).

**Spec:** [`docs/superpowers/specs/2026-09-02-gen3-comprehensive-enhancement-design.md`](../specs/2026-09-02-gen3-comprehensive-enhancement-design.md)

## Global Constraints

- Strictly NO EMOJIS anywhere in code, comments, docstrings, JSON datasets, or documentation.
- Explicit variable definitions.
- Worktree-relative path resolution.
- 100% backward compatibility for existing Gen 1, Gen 2, and Gen 3 callers.
- All 230+ repository unit tests must pass green.

---

## File Structure & Responsibilities

| File Path | Responsibility |
| :--- | :--- |
| [`agent/gemma_agent.py`](../../agent/gemma_agent.py) | Updates `max_tokens` default to `None`; omits `max_output_tokens` on Vertex MaaS to allow full reasoning window; sets 8192 headroom for vLLM/endpoints. |
| [`agent/soc_tier1_agent.py`](../../agent/soc_tier1_agent.py) | Updates `query()` and `_call_llm_step()` to unbounded tokens; enhances `_parse_action()` for JSON function calls; adds few-shot tool exemplars to persona. |
| [`scripts/eval_trajectory_verifier.py`](../../scripts/eval_trajectory_verifier.py) | Implements tiered action matching (`primary_actions_matched`, `secondary_actions_matched`) so models are graded on security containment rather than administrative comment tokens. |
| [`agent/soc_environment.py`](../../agent/soc_environment.py) | Enriches mock sandbox environment with realistic telemetry (VT detection ratios, WHOIS registrar, RFC classifications, process hierarchies). |
| [`agent/soc_tools.py`](../../agent/soc_tools.py) | Enriches local fallback tools with realistic telemetry payloads. |
| [`scripts/eval_cost_engine.py`](../../scripts/eval_cost_engine.py) | Adds `calculate_counterfactual_consistency()` evaluating discrimination between threats and ambiguous/benign pairs. |
| [`configs/evals/gen3/soc_tier1_interactive.json`](../../configs/evals/gen3/soc_tier1_interactive.json) | Provides explicit CMDB asset owner and operational downtime blast-radius context in case prompts. |
| [`tests/test_gen3_trajectory_verifier.py`](../../tests/test_gen3_trajectory_verifier.py) | Tests tiered primary vs secondary action verification. |
| [`tests/test_soc_tier1_agent.py`](../../tests/test_soc_tier1_agent.py) | Tests JSON function calling parsing and unbounded token queries. |
| [`tests/test_gen3_cost_engine.py`](../../tests/test_gen3_cost_engine.py) | Tests counterfactual consistency calculations. |

---

### Task 1: Unbounded Generation Token Budgeting

**Files:**
- Modify: `agent/gemma_agent.py`
- Modify: `agent/soc_tier1_agent.py`
- Modify: `tests/test_soc_tier1_agent.py`

**Interfaces:**
- `GemmaAgent.query(prompt: str, max_tokens: Optional[int] = None, temperature: float = 0.7) -> Dict[str, Any]`
- `SocTier1Agent.query(prompt: str, max_iterations: int = 5, max_tokens: Optional[int] = None, temperature: float = 0.2) -> Dict[str, Any]`
- `_call_llm_step(prompt: str, max_tokens: Optional[int] = None, temperature: float = 0.2) -> Tuple[str, Dict[str, int]]`

- [ ] **Step 1: Write failing unit test for unbounded token pass-through**
- [ ] **Step 2: Update `agent/gemma_agent.py` and `agent/soc_tier1_agent.py` to support `max_tokens=None`**
- [ ] **Step 3: Run `pytest tests/test_soc_tier1_agent.py` to verify**
- [ ] **Step 4: Commit changes**

---

### Task 2: Tiered Action Matching (Primary vs Secondary Actions)

**Files:**
- Modify: `scripts/eval_trajectory_verifier.py`
- Modify: `tests/test_gen3_trajectory_verifier.py`

**Interfaces:**
- `TrajectoryVerificationResult`: add `primary_actions_matched: bool`, `secondary_actions_matched: bool`
- `verify_agent_trajectory(..., expected_actions: List[str], prohibited_actions: List[str], response_text: str)`: evaluates `primary_actions_matched` against `PRIMARY_ACTIONS` (`isolate_host`, `unblock_host`, `block_indicator`, `close_case`) and sets `actions_matched = primary_actions_matched`.

- [ ] **Step 1: Write failing unit test verifying primary action satisfaction without requiring secondary comment**
- [ ] **Step 2: Implement tiered action matching in `scripts/eval_trajectory_verifier.py`**
- [ ] **Step 3: Run `pytest tests/test_gen3_trajectory_verifier.py` to verify**
- [ ] **Step 4: Commit changes**

---

### Task 3: Multi-Syntax Tool Parsing & Few-Shot Prompt Exemplars

**Files:**
- Modify: `agent/soc_tier1_agent.py`
- Modify: `tests/test_soc_tier1_agent.py`

**Interfaces:**
- `_parse_action(step_output: str) -> Optional[Tuple[str, Dict[str, Any]]]`: supports ReAct syntax, JSON objects (`{"name": "...", "arguments": {...}}`), and fenced tool call blocks.
- `SOC_TIER1_PERSONA`: add few-shot ReAct and JSON tool exemplars.

- [ ] **Step 1: Write failing unit tests for JSON and fenced tool call parsing**
- [ ] **Step 2: Implement multi-syntax tool parsing and few-shot exemplars in `agent/soc_tier1_agent.py`**
- [ ] **Step 3: Run `pytest tests/test_soc_tier1_agent.py` to verify**
- [ ] **Step 4: Commit changes**

---

### Task 4: High-Fidelity Telemetry Payloads & Counterfactual Consistency

**Files:**
- Modify: `agent/soc_environment.py`
- Modify: `agent/soc_tools.py`
- Modify: `scripts/eval_cost_engine.py`
- Modify: `tests/test_gen3_soc_environment.py`
- Modify: `tests/test_gen3_cost_engine.py`

**Interfaces:**
- `calculate_counterfactual_consistency(case_results: List[Dict[str, Any]], eval_cases: List[Dict[str, Any]]) -> Dict[str, Any]`
- Telemetry outputs contain `vt_positives`, `vt_total`, `registrar`, `creation_date`, `rfc_status`, `parent_process`, `logon_type`.

- [ ] **Step 1: Write failing unit tests for realistic telemetry and counterfactual scoring**
- [ ] **Step 2: Implement rich telemetry payloads in `agent/soc_environment.py` and `agent/soc_tools.py`**
- [ ] **Step 3: Implement `calculate_counterfactual_consistency` in `scripts/eval_cost_engine.py`**
- [ ] **Step 4: Run tests to verify**
- [ ] **Step 5: Commit changes**

---

### Task 5: Explicit CMDB Asset Context in Gen 3 Dataset

**Files:**
- Modify: `configs/evals/gen3/soc_tier1_interactive.json`
- Modify: `tests/test_eval_config_schema.py`

**Interfaces:**
- Each test case prompt in `soc_tier1_interactive.json` includes CMDB asset role, owner, and business blast-radius context.

- [ ] **Step 1: Update schema tests to verify CMDB context inclusion**
- [ ] **Step 2: Update `configs/evals/gen3/soc_tier1_interactive.json` with CMDB asset metadata**
- [ ] **Step 3: Run `pytest tests/test_eval_config_schema.py` to verify**
- [ ] **Step 4: Commit changes**

---

### Task 6: Verification & Benchmark Re-Runs on Baseline & Frontier Models

**Files:**
- Run: `gemini-2.5-pro` on unbounded tokens (verify resolution of token truncation issue)
- Run: `gemini-3.5-flash-lite` on enhanced suite (verify Case 3 pass with tiered actions)
- Update: `docs/soc_model_comparative_evals.md`
- Push to PR #7

- [ ] **Step 1: Re-evaluate `gemini-2.5-pro` with unbounded tokens**
- [ ] **Step 2: Re-evaluate `gemini-3.5-flash-lite` with tiered action matching**
- [ ] **Step 3: Rebuild master scorecard and verify 100% test pass rate**
- [ ] **Step 4: Commit and push changes to PR #7**
