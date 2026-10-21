# GEPA Runbook Evolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and execute a GEPA (Genetic Engine for Prompt Ad-hoc Optimization) system that evolves cybersecurity incident response runbooks to eliminate false alarms and maximize threat containment precision.

**Architecture:** Wrap the hierarchical SOC supervisor-worker agent in a custom `RunbookGEPAAdapter` that implements `gepa.GEPAAdapter`. Candidates are dictionaries of markdown runbooks evaluated against the 10-case Gen 3 benchmark. Diagnostic feedback on false alarms (RFC-5737 and Qualys scanners) and missed containment is fed to a reflection LM (`gemini-2.5-pro`) to propose Pareto-optimal mutations, saving the winning runbooks to `configs/runbooks/gepa_evolved/`.

**Tech Stack:** Python 3.11+, `gepa` (0.1.4), `google-genai`, `pytest`, `Justfile`.

**Spec:** [`docs/superpowers/specs/2026-09-04-gepa-runbook-evolution-design.md`](../specs/2026-09-04-gepa-runbook-evolution-design.md)

## Global Constraints

- Strictly NO EMOJIS anywhere in code, comments, docstrings, commit messages, or documentation.
- All paths must resolve relative to repository root (`ROOT_DIR`).
- Always define shell variables explicitly before expanding.
- Never hardcode Google Cloud project IDs or credentials.
- Use `gemini-2.5-flash-lite` for agent rollouts and `gemini-2.5-pro` for reflection.

---

### Task 1: Core Fitness Metric & Optimizer Data Structures

**Files:**
- Create: `agent/gepa_runbook_optimizer.py`
- Test: `tests/test_gepa_runbook_optimizer.py`

**Interfaces:**
- Consumes: `third_party/ai-runbooks/.clinerules/run_books/*.md`, `configs/evals/gen3/soc_tier1_interactive.json`
- Produces:
  - `load_seed_runbooks(runbooks_dir: Optional[Union[str, Path]] = None) -> dict[str, str]`
  - `save_runbooks(candidate: dict[str, str], output_dir: Union[str, Path], metadata: Optional[dict[str, Any]] = None) -> None`
  - `calculate_loss_penalty(expected_label: str, actual_verdict: str, executed_actions: list[str], prohibited_actions: list[str]) -> float`
  - `calculate_case_fitness(rubric_score: float, assertions_passed: bool, operator_compliance: float, loss_penalty: float) -> float`

- [ ] **Step 1: Write failing tests for candidate I/O and fitness calculation**

```python
# tests/test_gepa_runbook_optimizer.py
import pytest
from pathlib import Path
from agent.gepa_runbook_optimizer import (
    load_seed_runbooks,
    save_runbooks,
    calculate_loss_penalty,
    calculate_case_fitness,
)

def test_load_seed_runbooks_loads_four_core_playbooks():
    candidate = load_seed_runbooks()
    assert isinstance(candidate, dict)
    expected_keys = {
        "basic_ioc_enrichment.md",
        "suspicious_login_triage.md",
        "malware_triage.md",
        "lateral_movement_hunt_psexec_wmi.md",
    }
    for key in expected_keys:
        assert key in candidate
        assert len(candidate[key]) > 50
        assert not any(ord(char) > 127 for char in candidate[key] if ord(char) > 0x1F000)

def test_calculate_loss_penalty_severe_for_false_positive():
    penalty_clean = calculate_loss_penalty(
        expected_label="BENIGN",
        actual_verdict="BENIGN",
        executed_actions=["close_case"],
        prohibited_actions=["isolate_host", "block_ip"],
    )
    assert penalty_clean == pytest.approx(1.0)

    penalty_fp = calculate_loss_penalty(
        expected_label="BENIGN",
        actual_verdict="MALICIOUS",
        executed_actions=["isolate_host"],
        prohibited_actions=["isolate_host"],
    )
    assert penalty_fp < 0.40  # exp(-1) approx 0.368

def test_calculate_case_fitness_weights():
    # 0.40 * 1.0 + 0.20 * 1.0 + 0.20 * 1.0 + 0.20 * 1.0 = 1.0
    fitness = calculate_case_fitness(
        rubric_score=1.0,
        assertions_passed=True,
        operator_compliance=1.0,
        loss_penalty=1.0,
    )
    assert fitness == pytest.approx(1.0)

    # 0.40 * 0.5 + 0.20 * 0.0 + 0.20 * 0.5 + 0.20 * 0.368 = 0.2 + 0 + 0.1 + 0.0736 = 0.3736
    fitness_low = calculate_case_fitness(
        rubric_score=0.5,
        assertions_passed=False,
        operator_compliance=0.5,
        loss_penalty=0.368,
    )
    assert fitness_low == pytest.approx(0.3736, abs=1e-3)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest -v tests/test_gepa_runbook_optimizer.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent.gepa_runbook_optimizer'`

- [ ] **Step 3: Implement candidate I/O and fitness calculation**

Write implementation in `agent/gepa_runbook_optimizer.py` including `load_seed_runbooks`, `save_runbooks`, `calculate_loss_penalty`, and `calculate_case_fitness`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest -v tests/test_gepa_runbook_optimizer.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agent/gepa_runbook_optimizer.py tests/test_gepa_runbook_optimizer.py
git commit -m "feat(gepa): implement candidate IO and multi-objective fitness calculation"
```

---

### Task 2: In-Memory & Custom Directory Runbook Support in Agents

**Files:**
- Modify: `agent/hierarchical_soc_agent.py`
- Modify: `scripts/eval_soc_agent.py`
- Test: `tests/test_gen4_hierarchical_agent.py`

**Interfaces:**
- Consumes: `load_runbook`, `HierarchicalSOCTier1Agent`
- Produces:
  - `load_runbook(runbook_name: str, runbooks_dir: Optional[Path] = None, runbooks_dict: Optional[Dict[str, str]] = None) -> str`
  - `HierarchicalSOCTier1Agent.__init__(..., runbooks_dict: Optional[Dict[str, str]] = None, runbooks_dir: Optional[Union[Path, str]] = None)`
  - `scripts/eval_soc_agent.py` `--runbooks-dir` CLI option.

- [ ] **Step 1: Write failing tests for in-memory and custom runbook loading**

Add tests to `tests/test_gen4_hierarchical_agent.py`:
- Test that `load_runbook` returns content from `runbooks_dict` when provided.
- Test that `HierarchicalSOCTier1Agent` dispatches worker with runbook text from `runbooks_dict`.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest -v tests/test_gen4_hierarchical_agent.py -k "test_runbooks_dict"`
Expected: FAIL

- [ ] **Step 3: Update `hierarchical_soc_agent.py` and `eval_soc_agent.py`**

Update `load_runbook` to check `runbooks_dict` first, then `runbooks_dir`, then `DEFAULT_RUNBOOKS_DIR`.
Pass `runbooks_dict` and `runbooks_dir` into `HierarchicalSOCTier1Agent` and `SOCSupervisorAgent`.
Update `scripts/eval_soc_agent.py` to add `--runbooks-dir` argument and pass it when initializing `HierarchicalSOCTier1Agent`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest -v tests/test_gen4_hierarchical_agent.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agent/hierarchical_soc_agent.py scripts/eval_soc_agent.py tests/test_gen4_hierarchical_agent.py
git commit -m "feat(agent): support in-memory runbooks_dict and custom runbooks_dir in hierarchical agent"
```

---

### Task 3: Implement RunbookGEPAAdapter and GoogleGenAILM

**Files:**
- Modify: `agent/gepa_runbook_optimizer.py`
- Test: `tests/test_gepa_runbook_optimizer.py`

**Interfaces:**
- Consumes: `gepa.GEPAAdapter`, `gepa.EvaluationBatch`, `HierarchicalSOCTier1Agent`, `SocEnvironment`
- Produces:
  - `GoogleGenAILM`: Callable `(prompt: str | list[dict[str, Any]]) -> str` wrapping Google GenAI SDK.
  - `RunbookGEPAAdapter(GEPAAdapter)`:
    - `evaluate(batch, candidate, capture_traces)`
    - `make_reflective_dataset(candidate, eval_batch, components_to_update)`

- [ ] **Step 1: Write failing tests for `RunbookGEPAAdapter` and `GoogleGenAILM`**

Add unit tests in `tests/test_gepa_runbook_optimizer.py`:
- Test `RunbookGEPAAdapter.evaluate()` with mocked agent execution.
- Test `RunbookGEPAAdapter.make_reflective_dataset()` correctly builds diagnostic records for RFC-5737 false positives and Qualys scanner false positives.
- Test `GoogleGenAILM` initialization and calling structure.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest -v tests/test_gepa_runbook_optimizer.py -k "test_adapter"`
Expected: FAIL

- [ ] **Step 3: Implement `RunbookGEPAAdapter` and `GoogleGenAILM`**

Implement the full adapter in `agent/gepa_runbook_optimizer.py`:
- `evaluate()` creates an isolated `SocEnvironment`, runs `HierarchicalSOCTier1Agent(runbooks_dict=candidate, environment=env)`, and calculates per-case scores and trajectories.
- `make_reflective_dataset()` detects failure modes (prohibited action executed, expected entity omitted, low score) and formats structured feedback records for the relevant runbook.
- `GoogleGenAILM` calls `google.genai.Client` with model `gemini-2.5-pro` (or configured model).

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest -v tests/test_gepa_runbook_optimizer.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agent/gepa_runbook_optimizer.py tests/test_gepa_runbook_optimizer.py
git commit -m "feat(gepa): implement RunbookGEPAAdapter and GoogleGenAILM reflection wrapper"
```

---

### Task 4: CLI Entrypoint and Justfile Integration

**Files:**
- Modify: `agent/gepa_runbook_optimizer.py`
- Modify: `Justfile`
- Test: `tests/test_gepa_runbook_optimizer.py`

**Interfaces:**
- Consumes: `gepa.optimize`, `RunbookGEPAAdapter`, `GoogleGenAILM`
- Produces:
  - CLI `main()` with flags `--max-metric-calls`, `--task-lm`, `--reflection-lm`, `--evalset`, `--output-dir`.
  - Justfile recipes: `just gepa-evolve`, `just gepa-compare`.

- [ ] **Step 1: Write test for CLI argument parsing**

Add test in `tests/test_gepa_runbook_optimizer.py`:
- Test `parse_args()` returns valid default parameters.

- [ ] **Step 2: Implement CLI `main()` and Justfile recipes**

In `agent/gepa_runbook_optimizer.py`:
- Parse CLI arguments.
- Load seed runbooks from `third_party/ai-runbooks/.clinerules/run_books/`.
- Load dataset from `configs/evals/gen3/soc_tier1_interactive.json`.
- Configure custom reflection prompt template.
- Execute `gepa.optimize(...)`.
- Save Pareto-optimal results to `--output-dir` (default `configs/runbooks/gepa_evolved/`).

In `Justfile`:
- Add `gepa-evolve` recipe.
- Add `gepa-compare` recipe.

- [ ] **Step 3: Run tests to verify they pass**

Run: `.venv/bin/pytest -v tests/test_gepa_runbook_optimizer.py`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add agent/gepa_runbook_optimizer.py Justfile tests/test_gepa_runbook_optimizer.py
git commit -m "feat(gepa): add CLI optimizer entrypoint and Justfile recipes"
```

---

### Task 5: Execute Evolution & Comparative Evaluation Report

**Files:**
- Output: `configs/runbooks/gepa_evolved/*.md`
- Output: `configs/runbooks/gepa_evolved/evolution_metadata.json`
- Output: `docs/soc_eval_results/GEPA_RUNBOOK_EVALUATION_ANALYSIS.md`

**Interfaces:**
- Consumes: `agent/gepa_runbook_optimizer.py`, `scripts/eval_soc_agent.py`
- Produces:
  - Verified evolved runbooks in `configs/runbooks/gepa_evolved/`.
  - Head-to-head empirical evaluation comparing Baseline, Raw Runbooks, and GEPA-Evolved Runbooks on `gemini-2.5-flash-lite`.
  - Comprehensive analytical report in `docs/soc_eval_results/GEPA_RUNBOOK_EVALUATION_ANALYSIS.md`.

- [ ] **Step 1: Run GEPA optimization loop**

Run:
```bash
.venv/bin/python3 agent/gepa_runbook_optimizer.py --max-metric-calls 15 --task-lm gemini-2.5-flash-lite --reflection-lm gemini-2.5-pro --output-dir configs/runbooks/gepa_evolved
```
Verify generated markdown files exist, have zero emojis, and include boundary conditions for RFC-5737 and Qualys scanners.

- [ ] **Step 2: Run evaluation of GEPA-evolved runbooks on `gemini-2.5-flash-lite`**

Run:
```bash
.venv/bin/python3 -m scripts.eval_soc_agent --flavor gemini-2.5-flash-lite --managed-model gemini-2.5-flash-lite --gen 3 --agent-mode hierarchical --use-runbooks --runbooks-dir configs/runbooks/gepa_evolved --evalset configs/evals/gen3/soc_tier1_interactive.json --output-report docs/soc_eval_results/gemini-2.5-flash-lite_gepa_evolved_report.md --output-json docs/soc_eval_results/gemini-2.5-flash-lite_gepa_evolved_report.json
```

- [ ] **Step 3: Analyze results and generate comparative report**

Generate `docs/soc_eval_results/GEPA_RUNBOOK_EVALUATION_ANALYSIS.md` contrasting:
- Single Agent Baseline (No runbooks)
- Hierarchical Control (No runbooks)
- Hierarchical + Static Playbooks (`third_party/ai-runbooks`)
- Hierarchical + GEPA-Evolved Playbooks (`configs/runbooks/gepa_evolved`)

- [ ] **Step 4: Run full test suite and commit**

Run: `.venv/bin/pytest`
Commit:
```bash
git add configs/runbooks/gepa_evolved/ docs/soc_eval_results/
git commit -m "feat(gepa): evolve incident response runbooks and produce comparative evaluation analysis"
```
