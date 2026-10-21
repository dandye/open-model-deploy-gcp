# GKE with Ray Serve & Kueue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete foundation and orchestration tooling for executing distributed multi-model LLM benchmarking sweeps on Google Kubernetes Engine (GKE) using Ray Serve, vLLM, and Kueue batch job queuing with automated scale-to-zero GPU node pools ($0.00 idle compute leaks).

**Architecture:** A Python orchestrator generates Kubernetes manifests for a KubeRay `RayCluster` (serving vLLM with configurable Tensor Parallelism) and an evaluation batch `Job` (executing SOC Tier 1 triage and throughput benchmarks). Manifests are submitted to Kueue, which schedules GPU capacity across GKE node pools, executes evaluations, syncs scorecards to Cloud Storage, and deprovisions GPU nodes when the queue drains.

**Tech Stack:** Python 3.10+, Kubernetes (`kubectl` / PyYAML), KubeRay Operator, Kueue Batch Scheduler, Ray Serve, vLLM, Google Cloud Storage, Pytest, Justfile.

**Spec:** [`docs/benchmarking_gke_ray_serve.md`](../benchmarking_gke_ray_serve.md)

## Global Constraints

- Strictly NO EMOJIS anywhere in code, docstrings, comments, reports, or commits.
- Always define environment variables first (e.g. `PROJECT_ID="..."`) before expanding in shell snippets.
- Worktree-relative path resolution (`ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"`).
- Cost Awareness: Verify Kueue queue draining and GKE Cluster Autoscaler scale-to-zero ($0.00 idle compute).
- Working Directory: `gemma_deploy__worktrees/gke_ray_sweep_v0001`

---

### Task 1: Kubernetes Manifests & Resource Templates

**Files:**
- Create: `k8s/kueue_queues.yaml`
- Create: `k8s/templates/ray_vllm_cluster_template.yaml`
- Create: `k8s/templates/eval_job_template.yaml`
- Test: `tests/test_gke_manifest_templates.py`

**Interfaces:**
- Consumes: `docs/benchmarking_gke_ray_serve.md` spec, `configs/evals/soc_tier1_evalset.json`.
- Produces: Valid Kubernetes YAML manifests for Kueue queues, RayCluster vLLM serving pods, and batch evaluation jobs.

- [ ] **Step 1: Write failing unit test for manifest templates validation**
```python
def test_kueue_and_ray_templates_exist_and_no_emojis():
    for f in ["k8s/kueue_queues.yaml", "k8s/templates/ray_vllm_cluster_template.yaml", "k8s/templates/eval_job_template.yaml"]:
        assert os.path.exists(f)
        content = open(f).read()
        assert "apiVersion:" in content
        assert not any(ord(char) > 127 for char in content)
```

- [ ] **Step 2: Run test to verify it fails**
Run: `.venv/bin/pytest -v tests/test_gke_manifest_templates.py`
Expected: FAIL (file not found)

- [ ] **Step 3: Implement `k8s/kueue_queues.yaml` and template manifests**
Implement Kueue ClusterQueue/LocalQueue, RayCluster vLLM template with configurable GPU requests/limits, shared memory (`dshm`), and evaluation batch Job template with GCS output volume.

- [ ] **Step 4: Run test to verify it passes**
Run: `.venv/bin/pytest -v tests/test_gke_manifest_templates.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add k8s/ tests/test_gke_manifest_templates.py
git commit -m "feat(gke-ray): implement kueue queues and raycluster manifest templates"
```

---

### Task 2: GKE Ray & Kueue Sweep Orchestrator

**Files:**
- Create: `scripts/run_gke_ray_sweep.py`
- Test: `tests/test_gke_ray_orchestrator.py`

**Interfaces:**
- Consumes: `configs/models.json` and hardware profile catalog.
- Produces: `GKERayTarget` and `GKERayOrchestrator` (`render_ray_cluster()`, `render_eval_job()`, `submit_job()`, `monitor_job()`, `collect_results()`, `run_sweep()`).

- [ ] **Step 1: Write failing unit test for GKE Ray target mapping and manifest rendering**
```python
def test_render_ray_cluster_manifest_for_4x_l4():
    target = GKERayTarget(
        flavor="gemma-3-27b-it",
        hf_repo="google/gemma-3-27b-it",
        gpu_count=4,
        gpu_type="nvidia-l4",
        tensor_parallel_size=4,
    )
    manifest = render_ray_cluster_manifest(target, "secops-eval-ns", "ray-gemma-27b")
    assert manifest["spec"]["workerGroupSpecs"][0]["template"]["spec"]["containers"][0]["resources"]["limits"]["nvidia.com/gpu"] == 4
```

- [ ] **Step 2: Run test to verify it fails**
Run: `.venv/bin/pytest -v tests/test_gke_ray_orchestrator.py`
Expected: FAIL

- [ ] **Step 3: Implement `scripts/run_gke_ray_sweep.py`**
Implement data classes, manifest generators, `kubectl` executor, job log streaming, GCS result collection, and CLI argument parsing with `--dry-run` and `--models`.

- [ ] **Step 4: Run test to verify it passes**
Run: `.venv/bin/pytest -v tests/test_gke_ray_orchestrator.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add scripts/run_gke_ray_sweep.py tests/test_gke_ray_orchestrator.py
git commit -m "feat(gke-ray): implement gke ray and kueue sweep orchestrator"
```

---

### Task 3: Justfile Integration, Verification & Documentation

**Files:**
- Modify: `Justfile`
- Test: `tests/test_justfile_recipes.py`
- Modify: `docs/benchmarking_gke_ray_serve.md`

**Interfaces:**
- Produces: `just gke-ray-init [cluster]`, `just gke-ray-run [flavor] [dry_run]`, `just gke-ray-sweep [models] [dry_run]`, `just gke-ray-status`, `just gke-ray-cleanup`.

- [ ] **Step 1: Write failing test in `tests/test_justfile_recipes.py` for new GKE Ray recipes**
```python
def test_justfile_contains_gke_ray_recipes(self):
    content = open("Justfile").read()
    assert "gke-ray-init" in content
    assert "gke-ray-run" in content
    assert "gke-ray-sweep" in content
    assert "gke-ray-status" in content
    assert "gke-ray-cleanup" in content
```

- [ ] **Step 2: Run test to verify it fails**
Run: `.venv/bin/pytest -v tests/test_justfile_recipes.py::TestJustfileRecipes::test_justfile_contains_gke_ray_recipes`
Expected: FAIL

- [ ] **Step 3: Add recipes to `Justfile`**
Add recipes with explicit shell variables and help comments.

- [ ] **Step 4: Run test to verify it passes**
Run: `.venv/bin/pytest -v tests/test_justfile_recipes.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add Justfile tests/test_justfile_recipes.py docs/benchmarking_gke_ray_serve.md
git commit -m "feat(gke-ray): add justfile recipes and update documentation"
```

---

## Plan Verification Checklist
1. All 83+ existing unit tests continue to pass.
2. New tests for Kubernetes manifest rendering, GKE Ray orchestrator, and Justfile recipes pass.
3. No emojis anywhere in code, docstrings, or tests.
4. Clean, isolated worktree state ready for distributed GKE batch execution.
