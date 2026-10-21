# Compute Engine (GCE) Ephemeral Spot GPU VMs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete foundation and orchestration tooling for executing cost-optimized multi-model LLM benchmarking sweeps on Compute Engine Ephemeral Spot GPU Virtual Machines with Local NVMe SSD disk caching and programmatic self-deletion ($0.00 idle compute leaks).

**Architecture:** A lightweight orchestrator dynamically creates Spot GPU instances (`g2-standard-48` for 4x L4, `a2-highgpu-2g` for 2x A100) with attached Local NVMe SSD scratch disks. A self-terminating startup script mounts NVMe storage, syncs weights from regional Google Cloud Storage, launches vLLM in Docker, executes the SOC Tier 1 evaluation suite and latency/throughput benchmarks, uploads scorecards to GCS, and deletes the instance upon completion.

**Tech Stack:** Python 3.10+, Google Cloud Compute Engine (`google-cloud-compute` / `gcloud`), Docker, NVIDIA Container Toolkit, vLLM, Pytest, Justfile.

**Spec:** [`docs/benchmarking_gce_ephemeral_spot_vms.md`](../benchmarking_gce_ephemeral_spot_vms.md)

## Global Constraints

- Strictly NO EMOJIS anywhere in code, docstrings, comments, reports, or commits.
- Always define environment variables first (e.g. `PROJECT_ID="..."`) before expanding in shell snippets.
- Worktree-relative path resolution (`ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"`).
- Cost Awareness: Verify Spot VM provisioning (`--provisioning-model=SPOT`) and programmatic self-deletion ($0.00 idle compute).
- Working Directory: `gemma_deploy__worktrees/gce_spot_sweep_v0001`

---

### Task 1: Self-Terminating Startup Script & Template

**Files:**
- Create: `scripts/gce_startup_script.sh`
- Create: `scripts/templates/gce_startup_template.sh`
- Test: `tests/test_gce_startup_script.py`

**Interfaces:**
- Consumes: Metadata server endpoints (`http://metadata.google.internal/computeMetadata/v1/`), `scripts/eval_soc_agent.py`, `scripts/benchmark.py`.
- Produces: Executable startup script template formatting Local NVMe SSD, launching containerized vLLM, executing evaluations, syncing results to GCS, and deleting the VM instance.

- [ ] **Step 1: Write failing unit test for startup script validation**
```python
def test_startup_script_syntax_and_self_deletion():
    script_path = "scripts/gce_startup_script.sh"
    assert os.path.exists(script_path)
    content = open(script_path).read()
    assert "#!/usr/bin/env bash" in content
    assert "google-local-nvme-ssd" in content
    assert "vllm/vllm-openai:latest" in content
    assert "gcloud compute instances delete" in content
    assert not any(ord(char) > 127 for char in content)
```

- [ ] **Step 2: Run test to verify it fails**
Run: `.venv/bin/pytest -v tests/test_gce_startup_script.py`
Expected: FAIL (file not found)

- [ ] **Step 3: Implement `scripts/gce_startup_script.sh` and template**
Implement startup script with NVMe formatting, Docker vLLM execution, readiness check, evaluation suite execution, GCS sync, and `gcloud compute instances delete $(hostname) --zone=$ZONE --quiet`.

- [ ] **Step 4: Run test to verify it passes**
Run: `.venv/bin/pytest -v tests/test_gce_startup_script.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add scripts/gce_startup_script.sh scripts/templates/gce_startup_template.sh tests/test_gce_startup_script.py
git commit -m "feat(gce-spot): implement self-terminating startup script and template"
```

---

### Task 2: GCE Spot Sweep Orchestrator

**Files:**
- Create: `scripts/run_gce_spot_sweep.py`
- Test: `tests/test_gce_spot_orchestrator.py`

**Interfaces:**
- Consumes: `configs/models.json` and hardware profile catalog.
- Produces: `GCESpotTarget` and `GCESpotOrchestrator` (`create_instance_cmd()`, `launch_instance()`, `monitor_serial_output()`, `collect_results()`, `run_sweep()`).

- [ ] **Step 1: Write failing unit test for GCE Spot target hardware mapping and gcloud command builder**
```python
def test_gce_spot_command_builder_for_4x_l4():
    target = GCESpotTarget(
        flavor="gemma-3-27b-it",
        hf_repo="google/gemma-3-27b-it",
        machine_type="g2-standard-48",
        accelerator_type="nvidia-l4",
        accelerator_count=4,
        local_ssd_count=4,
    )
    cmd = build_gce_spot_create_command(target, "secops-demo-env", "europe-west4-a", "gs://bucket/out")
    assert "--provisioning-model=SPOT" in cmd
    assert "--machine-type=g2-standard-48" in cmd
    assert "--accelerator=type=nvidia-l4,count=4" in cmd
    assert cmd.count("--local-ssd=interface=NVME") == 4
```

- [ ] **Step 2: Run test to verify it fails**
Run: `.venv/bin/pytest -v tests/test_gce_spot_orchestrator.py`
Expected: FAIL

- [ ] **Step 3: Implement `scripts/run_gce_spot_sweep.py`**
Implement data classes, command generators, Spot retry logic, serial console log streaming, GCS result collection, and CLI argument parsing.

- [ ] **Step 4: Run test to verify it passes**
Run: `.venv/bin/pytest -v tests/test_gce_spot_orchestrator.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add scripts/run_gce_spot_sweep.py tests/test_gce_spot_orchestrator.py
git commit -m "feat(gce-spot): implement gce spot sweep orchestrator"
```

---

### Task 3: Justfile Integration, Verification & Documentation

**Files:**
- Modify: `Justfile`
- Test: `tests/test_justfile_recipes.py`
- Modify: `docs/benchmarking_gce_ephemeral_spot_vms.md`

**Interfaces:**
- Produces: `just gce-spot-run [flavor] [dry_run]`, `just gce-spot-sweep [models] [dry_run]`, `just gce-spot-status [zone]`, `just gce-spot-cleanup [zone]`.

- [ ] **Step 1: Write failing test in `tests/test_justfile_recipes.py` for new GCE Spot recipes**
```python
def test_justfile_contains_gce_spot_recipes(self):
    content = open("Justfile").read()
    assert "gce-spot-run" in content
    assert "gce-spot-sweep" in content
    assert "gce-spot-status" in content
    assert "gce-spot-cleanup" in content
```

- [ ] **Step 2: Run test to verify it fails**
Run: `.venv/bin/pytest -v tests/test_justfile_recipes.py::TestJustfileRecipes::test_justfile_contains_gce_spot_recipes`
Expected: FAIL

- [ ] **Step 3: Add recipes to `Justfile`**
Add recipes with explicit shell variables and help comments.

- [ ] **Step 4: Run test to verify it passes**
Run: `.venv/bin/pytest -v tests/test_justfile_recipes.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add Justfile tests/test_justfile_recipes.py docs/benchmarking_gce_ephemeral_spot_vms.md
git commit -m "feat(gce-spot): add justfile recipes and update documentation"
```

---

## Plan Verification Checklist
1. All 83+ existing unit tests continue to pass.
2. New tests for startup script, GCE Spot orchestrator, and Justfile recipes pass.
3. No emojis anywhere in code, docstrings, or tests.
4. Clean, isolated worktree state ready for cost-optimized Spot batch execution.
