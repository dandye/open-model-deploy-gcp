# Vertex AI Custom Jobs Benchmarking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete foundation and orchestration tooling for executing multi-model LLM benchmarking and autonomous SOC agent evaluation sweeps on ephemeral Vertex AI Custom Jobs with guaranteed $0.00 idle compute leaks.

**Architecture:** A containerized benchmark runner packaged with vLLM, `eval_soc_agent.py`, and `benchmark.py` is dynamically launched as an ephemeral `aiplatform.CustomJob` on the required hardware profile (1x L4, 4x L4, 2x A100). The job initializes local inference on `localhost:8080`, executes evaluation suites, writes markdown and JSON reports to a Google Cloud Storage bucket, and terminates compute upon completion.

**Tech Stack:** Python 3.10+, Google Cloud Vertex AI (`google-cloud-aiplatform`), vLLM, Docker, Google Cloud Storage (`google-cloud-storage`), Pytest, Justfile.

**Spec:** [docs/benchmarking_vertex_custom_jobs.md](file:///usr/local/google/home/dandye/Projects/gemma_deploy__worktrees/vertex_custom_jobs_v0001/docs/benchmarking_vertex_custom_jobs.md)

## Global Constraints

- Strictly NO EMOJIS anywhere in code, docstrings, comments, reports, or commits.
- Always define environment variables first (e.g. `PROJECT_ID="..."`) before expanding in shell snippets.
- Worktree-relative path resolution (`ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"`).
- Cost Awareness: Verify automated compute node termination ($0.00 idle compute).
- Working Directory: `/usr/local/google/home/dandye/Projects/gemma_deploy__worktrees/vertex_custom_jobs_v0001`

---

### Task 1: Job Container Entrypoint & Dockerfile Specification

**Files:**
- Create: `docker/Dockerfile.custom_job`
- Create: `scripts/custom_job_entrypoint.sh`
- Test: `tests/test_custom_job_container.py`

**Interfaces:**
- Consumes: `scripts/eval_soc_agent.py`, `scripts/benchmark.py`, `configs/evals/soc_tier1_evalset.json`.
- Produces: Executable container image entrypoint accepting `MODEL_FLAVOR`, `HF_REPO`, `TP_SIZE`, `EXTRA_FLAGS`, and `OUTPUT_GCS_PATH`.

- [ ] **Step 1: Write failing unit test for entrypoint script validation**
```python
def test_entrypoint_script_syntax_and_no_emojis():
    script_path = "scripts/custom_job_entrypoint.sh"
    assert os.path.exists(script_path)
    content = open(script_path).read()
    assert "#!/usr/bin/env bash" in content
    assert "eval_soc_agent.py" in content
    assert "gsutil" in content or "google-cloud-storage" in content or "gcloud storage" in content
    assert not any(ord(char) > 127 for char in content)
```

- [ ] **Step 2: Run test to verify it fails**
Run: `/usr/local/google/home/dandye/Projects/gemma_deploy__worktrees/main/.venv/bin/pytest -v tests/test_custom_job_container.py`
Expected: FAIL (file not found)

- [ ] **Step 3: Implement `scripts/custom_job_entrypoint.sh` and `docker/Dockerfile.custom_job`**
```bash
#!/usr/bin/env bash
set -euo pipefail

MODEL_FLAVOR="${1:-gemma-3-4b-it}"
HF_REPO="${2:-google/gemma-3-4b-it}"
TENSOR_PARALLEL_SIZE="${3:-1}"
EXTRA_FLAGS="${4:-}"
OUTPUT_GCS_PATH="${5:-gs://secops-eval-results/custom_jobs}"
```

- [ ] **Step 4: Run test to verify it passes**
Run: `/usr/local/google/home/dandye/Projects/gemma_deploy__worktrees/main/.venv/bin/pytest -v tests/test_custom_job_container.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add docker/Dockerfile.custom_job scripts/custom_job_entrypoint.sh tests/test_custom_job_container.py
git commit -m "feat(custom-jobs): add container entrypoint script and dockerfile"
```

---

### Task 2: Vertex AI Custom Job Sweep Orchestrator

**Files:**
- Create: `scripts/run_vertex_custom_job_sweep.py`
- Test: `tests/test_vertex_custom_jobs_orchestrator.py`

**Interfaces:**
- Consumes: Model definitions from `configs/models.json` and hardware profile catalog.
- Produces: `VertexCustomJobOrchestrator` with `build_worker_pool_spec()`, `submit_job()`, `poll_job()`, and `run_sweep()`.

- [ ] **Step 1: Write failing unit test for orchestrator hardware mapping and worker pool generator**
```python
def test_worker_pool_spec_for_4x_l4_model():
    target = VertexCustomJobTarget(
        flavor="gemma-3-27b-it",
        hf_repo="google/gemma-3-27b-it",
        machine_type="g2-standard-48",
        accelerator_type="NVIDIA_L4",
        accelerator_count=4,
        tensor_parallel_size=4,
    )
    spec = build_worker_pool_spec(target, "image:latest", "gs://bucket/out")
    assert spec["machine_spec"]["machine_type"] == "g2-standard-48"
    assert spec["machine_spec"]["accelerator_count"] == 4
    assert spec["machine_spec"]["accelerator_type"] == "NVIDIA_L4"
```

- [ ] **Step 2: Run test to verify it fails**
Run: `/usr/local/google/home/dandye/Projects/gemma_deploy__worktrees/main/.venv/bin/pytest -v tests/test_vertex_custom_jobs_orchestrator.py`
Expected: FAIL

- [ ] **Step 3: Implement `scripts/run_vertex_custom_job_sweep.py`**
Implement data classes, worker pool generators, and job submission logic with `--dry-run`, `--models`, `--project-id`, and `--region` CLI options.

- [ ] **Step 4: Run test to verify it passes**
Run: `/usr/local/google/home/dandye/Projects/gemma_deploy__worktrees/main/.venv/bin/pytest -v tests/test_vertex_custom_jobs_orchestrator.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add scripts/run_vertex_custom_job_sweep.py tests/test_vertex_custom_jobs_orchestrator.py
git commit -m "feat(custom-jobs): implement vertex custom job sweep orchestrator"
```

---

### Task 3: Justfile Integration, Verification & Documentation

**Files:**
- Modify: `Justfile`
- Test: `tests/test_justfile_recipes.py`
- Modify: `docs/benchmarking_vertex_custom_jobs.md`

**Interfaces:**
- Produces: `just custom-job-build`, `just custom-job-run [flavor]`, `just custom-job-sweep [models]`, `just custom-job-status`.

- [ ] **Step 1: Write failing test in `tests/test_justfile_recipes.py` for new custom-job recipes**
```python
def test_justfile_contains_custom_job_recipes(self):
    content = open("Justfile").read()
    assert "custom-job-build" in content
    assert "custom-job-run" in content
    assert "custom-job-sweep" in content
    assert "custom-job-status" in content
```

- [ ] **Step 2: Run test to verify it fails**
Run: `/usr/local/google/home/dandye/Projects/gemma_deploy__worktrees/main/.venv/bin/pytest -v tests/test_justfile_recipes.py::TestJustfileRecipes::test_justfile_contains_custom_job_recipes`
Expected: FAIL

- [ ] **Step 3: Add recipes to `Justfile`**
Add recipes with explicit shell variables and help comments.

- [ ] **Step 4: Run test to verify it passes**
Run: `/usr/local/google/home/dandye/Projects/gemma_deploy__worktrees/main/.venv/bin/pytest -v tests/test_justfile_recipes.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add Justfile tests/test_justfile_recipes.py docs/benchmarking_vertex_custom_jobs.md
git commit -m "feat(custom-jobs): add justfile recipes and update documentation"
```

---

## Plan Verification Checklist
1. All 83+ existing unit tests continue to pass.
2. New tests for container spec, orchestrator worker pools, and Justfile recipes pass.
3. No emojis anywhere in code, docstrings, or tests.
4. Clean, isolated worktree state ready for overnight batch execution.
