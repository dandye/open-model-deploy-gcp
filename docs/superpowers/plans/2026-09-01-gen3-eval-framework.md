# Gen 3 Agentic Evaluation Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Gen 3 Agentic Evaluation Framework featuring an interactive SOC state-machine sandbox, cost-weighted blast radius loss engine (Signal Detection Theory $d'$ & $c$), epistemic trajectory & action verifier, and Gen 3 interactive dataset suites.

**Architecture:** A 4-subsystem architecture separating dynamic environment state (`agent/soc_environment.py`), decision loss and SDT modeling (`scripts/eval_cost_engine.py`), action trajectory verification (`scripts/eval_trajectory_verifier.py`), and unified CLI/Justfile orchestration (`scripts/eval_soc_agent.py`).

**Tech Stack:** Python 3.11+, Pydantic, NumPy/SciPy (Signal Detection Theory), Google Cloud Vertex AI GenAI SDK.

**Spec:** [`docs/superpowers/specs/2026-09-01-gen3-eval-framework-design.md`](file:///usr/local/google/home/dandye/Projects/gemma_deploy__worktrees/gen3_evals_v0001/docs/superpowers/specs/2026-09-01-gen3-eval-framework-design.md)

## Global Constraints

- Strictly NO EMOJIS anywhere in code, comments, docstrings, commits, or documentation.
- Explicit Python variable and shell variable definitions.
- Worktree-relative path resolution (`ROOT_DIR = Path(__file__).resolve().parent.parent`).
- Backward compatibility with Gen 1 and Gen 2 evaluation modes (`--gen 1`, `--gen 2`, `--gen 3`).
- 100% test coverage with zero regressions across the 173 existing unit tests.

---

### Task 1: Interactive SOC Sandbox & Dynamic State Machine

**Files:**
- Create: `agent/soc_environment.py`
- Test: `tests/test_gen3_soc_environment.py`

**Interfaces:**
- Produces: `SocEnvironment`, `HostEntity`, `DomainEntity`, `HashEntity`, `CaseEntity`, `EnvironmentAction`
- Consumes: Standard Python types, dataclasses, typing

- [ ] **Step 1: Write failing unit tests for `SocEnvironment`**

```python
# tests/test_gen3_soc_environment.py
import pytest
from agent.soc_environment import SocEnvironment, HostEntity, DomainEntity, HashEntity, CaseEntity

def test_soc_environment_initialization():
    env = SocEnvironment()
    assert len(env.hosts) > 0
    assert len(env.domains) > 0

def test_soc_environment_host_isolation_action():
    env = SocEnvironment()
    res = env.execute_action("isolate_host", {"hostname": "DESKTOP-FIN-08"})
    assert res["status"] == "SUCCESS"
    assert env.hosts["DESKTOP-FIN-08"].isolated is True

def test_soc_environment_tool_failure_injection():
    env = SocEnvironment()
    env.inject_fault("get_domain_report", status_code=503, error="Service Unavailable")
    res = env.query_tool("get_domain_report", {"domain": "error-503.service-unavailable.org"})
    assert res.get("status_code") == 503
```

- [ ] **Step 2: Run test to verify failure**

Run: `.venv/bin/pytest tests/test_gen3_soc_environment.py -v`
Expected: FAIL (module `agent.soc_environment` does not exist)

- [ ] **Step 3: Implement `SocEnvironment` in `agent/soc_environment.py`**

Implement dataclasses `HostEntity`, `DomainEntity`, `HashEntity`, `CaseEntity`, and `SocEnvironment` with methods `query_tool()`, `execute_action()`, `inject_fault()`, `reset()`, and `get_state_snapshot()`.

- [ ] **Step 4: Run tests to verify pass**

Run: `.venv/bin/pytest tests/test_gen3_soc_environment.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agent/soc_environment.py tests/test_gen3_soc_environment.py
git commit -m "feat(evals): implement interactive SOC state-machine sandbox"
```

---

### Task 2: Cost-Weighted Signal Detection & Decision Loss Engine

**Files:**
- Create: `scripts/eval_cost_engine.py`
- Test: `tests/test_gen3_cost_engine.py`

**Interfaces:**
- Produces: `SignalDetectionMetrics`, `OperationalLossScorecard`, `calculate_sdt_metrics()`, `calculate_operational_loss()`
- Consumes: `math`, `typing`, `pydantic`, `dataclasses`

- [ ] **Step 1: Write failing unit tests for SDT & Cost Engine**

```python
# tests/test_gen3_cost_engine.py
import pytest
from scripts.eval_cost_engine import (
    calculate_sdt_metrics,
    calculate_operational_loss,
    AssetCriticality,
    DecisionOutcome,
)

def test_sdt_metrics_calculation():
    # 8 hits out of 10 targets, 1 false alarm out of 10 non-targets
    res = calculate_sdt_metrics(hits=8, misses=2, false_alarms=1, correct_rejections=9)
    assert res.d_prime > 1.5
    assert isinstance(res.criterion_c, float)

def test_operational_loss_asymmetric_blast_radius():
    # False positive on Critical asset costs $50,000
    loss_crit = calculate_operational_loss(
        outcome=DecisionOutcome.FALSE_POSITIVE,
        criticality=AssetCriticality.CRITICAL,
    )
    # False positive on Dev asset costs $50
    loss_dev = calculate_operational_loss(
        outcome=DecisionOutcome.FALSE_POSITIVE,
        criticality=AssetCriticality.LOW,
    )
    assert loss_crit == 50000.0
    assert loss_dev == 50.0
```

- [ ] **Step 2: Run test to verify failure**

Run: `.venv/bin/pytest tests/test_gen3_cost_engine.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `scripts/eval_cost_engine.py`**

Implement `calculate_sdt_metrics()`, `calculate_operational_loss()`, `calculate_expected_loss_matrix()`, and cost structures for all criticality tiers (`LOW`, `STANDARD`, `HIGH`, `CRITICAL`).

- [ ] **Step 4: Run tests to verify pass**

Run: `.venv/bin/pytest tests/test_gen3_cost_engine.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/eval_cost_engine.py tests/test_gen3_cost_engine.py
git commit -m "feat(evals): implement cost-weighted decision loss and SDT engine"
```

---

### Task 3: Epistemic Trajectory & Action Verifier

**Files:**
- Create: `scripts/eval_trajectory_verifier.py`
- Test: `tests/test_gen3_trajectory_verifier.py`

**Interfaces:**
- Produces: `TrajectoryVerificationResult`, `verify_agent_trajectory()`, `calculate_epistemic_efficiency()`
- Consumes: `agent/soc_environment.py`, `scripts/eval_cost_engine.py`

- [ ] **Step 1: Write failing unit tests for Trajectory Verifier**

```python
# tests/test_gen3_trajectory_verifier.py
import pytest
from scripts.eval_trajectory_verifier import verify_agent_trajectory

def test_verify_agent_trajectory_action_matching():
    trajectory = [
        {"iteration": 1, "tool": "get_ip_address_report", "args": {"ip": "192.0.2.100"}, "observation": "{}"},
        {"iteration": 2, "tool": "isolate_host", "args": {"hostname": "DESKTOP-FIN-08"}, "observation": "{}"},
    ]
    res = verify_agent_trajectory(
        trajectory=trajectory,
        expected_actions=["isolate_host"],
        prohibited_actions=["delete_log"],
    )
    assert res.actions_matched is True
    assert res.prohibited_actions_avoided is True
```

- [ ] **Step 2: Run test to verify failure**

Run: `.venv/bin/pytest tests/test_gen3_trajectory_verifier.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `scripts/eval_trajectory_verifier.py`**

Implement `verify_agent_trajectory()`, `calculate_epistemic_efficiency()`, loop detection, degraded-mode error handling checks, and action compliance validation.

- [ ] **Step 4: Run tests to verify pass**

Run: `.venv/bin/pytest tests/test_gen3_trajectory_verifier.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/eval_trajectory_verifier.py tests/test_gen3_trajectory_verifier.py
git commit -m "feat(evals): implement epistemic trajectory and action verifier"
```

---

### Task 4: Gen 3 Evaluation Datasets & Counterfactual Pairs

**Files:**
- Create: `configs/evals/gen3/soc_tier1_interactive.json`
- Create: `configs/evals/gen3/soc_live_mcp_interactive.json`
- Test: `tests/test_eval_config_schema.py`

**Interfaces:**
- Produces: 10 interactive scenarios with asset criticality tiers, expected actions, counterfactual branches, and asymmetric loss values.

- [ ] **Step 1: Write failing schema tests in `tests/test_eval_config_schema.py`**

Add tests validating Gen 3 schema: `test_gen3_evalset_structure()`, `test_gen3_evalset_criticality_tiers()`, `test_gen3_evalset_no_emojis()`.

- [ ] **Step 2: Run test to verify failure**

Run: `.venv/bin/pytest tests/test_eval_config_schema.py -v`
Expected: FAIL (Gen 3 files missing)

- [ ] **Step 3: Author Gen 3 datasets**

Write `configs/evals/gen3/soc_tier1_interactive.json` and `configs/evals/gen3/soc_live_mcp_interactive.json` containing 10 rich cases with asset criticality, expected programmatic actions, fault injection hooks, and counterfactual flags.

- [ ] **Step 4: Run schema tests to verify pass**

Run: `.venv/bin/pytest tests/test_eval_config_schema.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add configs/evals/gen3/ tests/test_eval_config_schema.py
git commit -m "feat(evals): add Gen 3 interactive evaluation datasets"
```

---

### Task 5: Gen 3 Evaluation Runner & Justfile Integration

**Files:**
- Modify: `scripts/eval_soc_agent.py`
- Modify: `Justfile`
- Test: `tests/test_justfile_recipes.py`

**Interfaces:**
- Connects `SocEnvironment`, `eval_cost_engine`, and `eval_trajectory_verifier` into `eval_soc_agent.py` for `--gen 3` execution.

- [ ] **Step 1: Update `scripts/eval_soc_agent.py`**

Add Gen 3 runner execution branch, SDT matrix calculation, operational financial loss scoring, and formatted terminal/markdown matrix reports.

- [ ] **Step 2: Update `Justfile`**

Add `eval-gen3` and `eval-gen3-live` recipes with `GEN="3"` default.

- [ ] **Step 3: Run full test suite**

Run: `.venv/bin/pytest -v`
Expected: PASS (100% test pass rate)

- [ ] **Step 4: Commit**

```bash
git add scripts/eval_soc_agent.py Justfile tests/test_justfile_recipes.py
git commit -m "feat(evals): wire Gen 3 evaluation runner and Justfile recipes"
```

---

### Task 6: Full Verification & Gen 3 Baseline Run

**Files:**
- Output: `docs/soc_eval_results/gen3_gemini_2_5_flash_report.md`
- Output: `docs/soc_eval_results/gen3_gemini_2_5_flash.json`

- [ ] **Step 1: Execute Gen 3 evaluation on `gemini-2.5-flash`**

Run: `.venv/bin/python -m scripts.eval_soc_agent --flavor "gemini-2.5-flash" --gen 3 --project-id "secops-demo-env"`

- [ ] **Step 2: Verify scorecard outputs**

Confirm generation of $d'$ sensitivity index, criterion bias $c$, operational loss (\$ score), and action trajectory verifications.

- [ ] **Step 3: Commit baseline results**

```bash
git add docs/soc_eval_results/gen3_*
git commit -m "docs(evals): record Gen 3 baseline benchmark results for Gemini 2.5 Flash"
```
