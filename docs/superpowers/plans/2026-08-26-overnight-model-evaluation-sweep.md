# Overnight Comprehensive Model Evaluation & Benchmark Sweep Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and execute an automated, unattended overnight evaluation runner that sequentially deploys, benchmarks, evaluates on the un-spoiled SOC Tier 1 suite, and tears down every Gemma model in the catalog alongside frontier Gemini baselines with $0 idle cost leakage.

**Architecture:** A centralized Python orchestration runner (`scripts/run_overnight_sweep.py`) that iterates through all registered Gemma flavors (Gemma 2, Gemma 3, Gemma 4, FP8 & Speculative variants) and managed Gemini models. For each self-hosted model, it manages the full Vertex AI lifecycle (`deploy` -> wait with timeout -> run latency/throughput benchmarks -> execute 5-case un-spoiled SOC evaluation -> `undeploy/delete`), persisting granular JSON/Markdown reports and compiling a unified master scorecard in `docs/soc_model_comparative_evals.md`.

**Tech Stack:** Python 3.11+, Google GenAI SDK (`gemini-2.5-pro` judge), Vertex AI REST & gcloud APIs, Pytest, Justfile automation.

**Spec:** [`docs/thoughts_on_evals.md`](../../thoughts_on_evals.md), [`docs/soc_model_comparative_evals.md`](../../soc_model_comparative_evals.md), [`configs/models.json`](../../../configs/models.json).

## Global Constraints

- **No Emojis**: Never use emojis in code, logs, commits, comments, or generated evaluation reports.
- **Strict Teardown & Cost Safety**: Every deployment must be wrapped in guaranteed exception handling (`try ... finally`) and shell traps to ensure $0 active compute billing after each model completes.
- **Single Active GPU Constraint**: Models must be evaluated sequentially (one active endpoint at a time) to prevent quota exhaustion and cost spikes.
- **Un-Spoiled Evaluation Integrity**: All models must use the un-spoiled, principled persona in `agent/soc_tier1_agent.py` without alert-specific cheat sheets.
- **Worktree Portability**: All paths must resolve relative to repository root (`ROOT_DIR`).

---

## File Structure & Responsibilities

| File Path | Responsibility |
| :--- | :--- |
| `scripts/run_overnight_sweep.py` | Master orchestrator script managing sequential deployment, throughput benchmarking, SOC eval execution, teardown, and aggregate scorecard compilation. |
| `agent/soc_tier1_agent.py` | Un-spoiled SOC Tier 1 Agent with dynamic backend routing across self-hosted Gemma and managed Gemini models. |
| `scripts/eval_soc_agent.py` | Automated SOC evaluation runner executing test cases and grading responses via `gemini-2.5-pro` LLM judge. |
| `scripts/benchmark.py` | Latency and throughput benchmarking tool measuring P50/P90/P99, TTFT, and generation TPS. |
| `tests/test_overnight_sweep.py` | Unit tests verifying orchestrator execution logic, model queue validation, and mock deployment lifecycle error recovery. |
| `Justfile` | Recipe `just overnight-sweep` to launch unattended execution in background with logging. |
| `docs/soc_model_comparative_evals.md` | Master comparative evaluation documentation and cross-generational scorecard. |

---

## Model Evaluation Queue Order

```
[Phase 1: Frontier & Managed Baselines (Fast - 0 Deploy Time)]
  ├── gemini-3.5-flash-lite (Global Managed)
  ├── gemini-2.5-flash (MaaS)
  ├── gemini-2.5-pro (MaaS)
  └── gemini-3.7-flash (Global Managed)

[Phase 2: Gemma 4 Family (Edge & Flagship)]
  ├── gemma-4-e2b-it (1x L4, g2-standard-4, us-east1)
  ├── gemma-4-e4b-it (1x L4, g2-standard-8, us-east1)
  └── gemma-4-31b-it (2x A100 NVLink, a2-highgpu-2g, us-east1)

[Phase 3: Gemma 3 Family & Optimizations]
  ├── gemma-3-1b-it (1x L4, g2-standard-4, us-central1)
  ├── gemma-3-4b-it (1x L4, g2-standard-8, us-central1)
  ├── gemma-3-12b-it (4x L4, g2-standard-48, us-central1)
  ├── gemma-3-27b-it (4x L4, g2-standard-48, us-east1)
  ├── gemma-3-27b-it FP8 (4x L4, g2-standard-48, us-east1)
  └── gemma-3-27b-it FP8 + Speculative Decoding (4x L4, us-east1)

[Phase 4: Gemma 2 Family Baseline]
  ├── gemma-2-2b-it (1x L4, g2-standard-4, us-central1)
  ├── gemma-2-9b-it (1x L4, g2-standard-12, us-central1)
  └── gemma-2-27b-it (4x L4, g2-standard-48, us-east1)
```

---

## Tasks

### Task 1: Create the Master Overnight Sweep Orchestrator (`scripts/run_overnight_sweep.py`)

**Files:**
- Create: `scripts/run_overnight_sweep.py`
- Test: `tests/test_overnight_sweep.py`

**Interfaces:**
- Consumes: `configs/models.json`, `scripts/eval_soc_agent.py`, `scripts/benchmark.py`, `scripts/vertex_deploy.sh`.
- Produces: JSON and Markdown evaluation reports in `docs/soc_eval_results/` and updates `docs/soc_model_comparative_evals.md`.

- [ ] **Step 1: Write the unit tests for sweep orchestration**

```python
import unittest
from unittest.mock import MagicMock, patch
from scripts.run_overnight_sweep import SweepOrchestrator, ModelTarget

class TestOvernightSweep(unittest.TestCase):
    def test_model_target_initialization(self):
        target = ModelTarget(
            flavor="gemma-4-e2b-it",
            target_type="vertex",
            region="us-east1",
            machine_type="g2-standard-4",
            gpu_count=1,
            gpu_type="nvidia-l4"
        )
        self.assertEqual(target.flavor, "gemma-4-e2b-it")
        self.assertEqual(target.region, "us-east1")
        self.assertEqual(target.target_type, "vertex")

    def test_build_model_queue_contains_expected_models(self):
        orchestrator = SweepOrchestrator(dry_run=True)
        queue = orchestrator.build_queue()
        flavors = [t.flavor for t in queue]
        self.assertIn("gemini-3.5-flash-lite", flavors)
        self.assertIn("gemma-4-e2b-it", flavors)
        self.assertIn("gemma-4-e4b-it", flavors)
        self.assertIn("gemma-3-4b-it", flavors)
        self.assertIn("gemma-3-27b-it", flavors)

    @patch("subprocess.run")
    def test_guaranteed_cleanup_on_exception(self, mock_sub):
        orchestrator = SweepOrchestrator(dry_run=False)
        target = ModelTarget(flavor="gemma-4-e2b-it", target_type="vertex", region="us-east1")
        with patch.object(orchestrator, "deploy_model", side_effect=RuntimeError("Deploy timeout")):
            with patch.object(orchestrator, "cleanup_endpoint") as mock_clean:
                with self.assertRaises(RuntimeError):
                    orchestrator.evaluate_model(target)
                mock_clean.assert_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_overnight_sweep.py -v`
Expected: FAIL with "No module named scripts.run_overnight_sweep"

- [ ] **Step 3: Implement `scripts/run_overnight_sweep.py`**

Implement `SweepOrchestrator` supporting:
- Queue generation covering all Gemma 2/3/4 models and Gemini managed baselines.
- Robust Vertex AI deployment polling with stage logging.
- Benchmark and SOC eval execution.
- Guaranteed teardown with error isolation (failure on one model does not abort the remaining queue).
- Auto-updating `docs/soc_model_comparative_evals.md`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_overnight_sweep.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/run_overnight_sweep.py tests/test_overnight_sweep.py
git commit -m "feat(evals): add master overnight sweep orchestrator"
```

---

### Task 2: Integrate Justfile Automation & Background Logging

**Files:**
- Modify: `Justfile:40-70`
- Test: `tests/test_justfile_recipes.py`

- [ ] **Step 1: Write test verifying `overnight-sweep` recipe exists**

```python
def test_justfile_contains_overnight_sweep_recipe():
    with open("Justfile", "r") as f:
        content = f.read()
    assert "overnight-sweep" in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_justfile_recipes.py -v`
Expected: FAIL

- [ ] **Step 3: Add `overnight-sweep` recipe to `Justfile`**

```makefile
# Run unattended overnight evaluation sweep across all models with logging
overnight-sweep:
    @mkdir -p logs
    @python3 scripts/run_overnight_sweep.py 2>&1 | tee "logs/overnight_sweep_$(shell date +%Y%m%d_%H%M%S).log"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_justfile_recipes.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add Justfile tests/test_justfile_recipes.py
git commit -m "feat(justfile): add overnight-sweep automation recipe"
```

---

### Task 3: Launch Unattended Execution

- [ ] **Step 1: Verify Google Cloud authentication and quota readiness**
- [ ] **Step 2: Launch `just overnight-sweep` as a background task**
- [ ] **Step 3: Verify execution logging and initial model dispatch**
- [ ] **Step 4: Commit and push final state**
