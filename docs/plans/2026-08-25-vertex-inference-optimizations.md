# Vertex AI Advanced Inference Optimizations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement, benchmark, and evaluate advanced vLLM inference optimizations on Vertex AI dedicated GPU clusters (FP8 quantization, chunked prefill, prefix caching, and speculative decoding) across Gemma 2 and Gemma 3 models.

**Architecture:** Extend `configs/models.json`, `scripts/lib/model_catalog.sh`, and `scripts/deploy_vertex.sh` to support dynamic optimization flags (`--quantization=fp8`, `--enable-chunked-prefill`, `--enable-prefix-caching`, `--speculative-config`), upgrade `scripts/benchmark.py` to capture Time-to-First-Token (TTFT) and Inter-Token Latency (ITL), execute empirical experiments (`EXP-12`, `EXP-13`, `EXP-08b`), and record results in `docs/experiments_status.md`.

**Tech Stack:** Bash, Python 3.13, Google Cloud Vertex AI Online Prediction, vLLM / Google Model Garden PyTorch serving containers, NVIDIA L4 GPUs (`g2-standard-48`).

**Spec:** [`docs/gemma4_performance_optimization_plan.md`](../gemma4_performance_optimization_plan.md) and [`docs/experiments_status.md`](../experiments_status.md).

## Global Constraints

* **No Emojis**: Never use emojis in code, logs, commits, comments, or documentation.
* **Shell Variables**: Always define shell variables explicitly before expanding.
* **Worktree Portability**: Resolve all script paths relative to repository root (`ROOT_DIR`).
* **Cost Awareness**: Always cleanly undeploy models and delete endpoints immediately after benchmark runs (`just vertex-undeploy`).

---

### Task 1: Model Catalog & Deployment Script Optimization Flags

**Files:**
- Modify: `scripts/lib/model_catalog.sh`
- Modify: `scripts/deploy_vertex.sh`
- Test: `tests/test_model_catalog.sh` or `tests/test_deploy_vertex.py`

**Interfaces:**
- Consumes: Model catalog definitions from `configs/models.json`
- Produces: CLI argument builder supporting `--quantization`, `--enable-chunked-prefill`, `--enable-prefix-caching`, `--speculative-model` / `--speculative-config`

- [ ] **Step 1: Write the failing test for optimization flag passing**

```python
# tests/test_optimization_flags.py
import subprocess
import pytest

def test_model_catalog_extracts_extra_args():
    res = subprocess.run(
        ["bash", "-c", 'source scripts/lib/model_catalog.sh && get_runtime_extra_args "gemma-3-27b-it"'],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert "--limit_mm_per_prompt=image=5" in res.stdout
```

- [ ] **Step 2: Run test to verify it fails or passes**

Run: `pytest tests/test_optimization_flags.py -v`

- [ ] **Step 3: Update `scripts/deploy_vertex.sh` to allow runtime override flags**

Allow passing `EXTRA_VLLM_FLAGS` environment variable to append custom flags into the container arguments array.

- [ ] **Step 4: Verify test passes**

Run: `pytest tests/test_optimization_flags.py -v`

- [ ] **Step 5: Commit**

```bash
git add scripts/deploy_vertex.sh scripts/lib/model_catalog.sh tests/test_optimization_flags.py
git commit -m "feat(deploy): allow custom vLLM optimization flags in vertex deployment script"
```

---

### Task 2: Streaming Benchmark Metrics in `scripts/benchmark.py`

**Files:**
- Modify: `scripts/benchmark.py`
- Test: `tests/test_benchmark_metrics.py`

**Interfaces:**
- Consumes: Endpoint URL / prediction responses
- Produces: Structured metrics including `ttft_ms`, `itl_ms`, `tokens_per_sec`, `p50_latency`, `p90_latency`, `p99_latency`

- [ ] **Step 1: Write failing unit test for TTFT and ITL computation**

```python
# tests/test_benchmark_metrics.py
import pytest
from scripts.benchmark import BenchmarkRunner

def test_calculate_streaming_metrics():
    runner = BenchmarkRunner(endpoint_id="123", region="us-central1")
    latencies = [1.2, 1.0, 1.1, 1.05]
    metrics = runner.calculate_summary(token_counts=[50, 50, 50, 50], latencies=latencies)
    assert "tps" in metrics
    assert "tpm" in metrics
    assert "avg_latency_s" in metrics
```

- [ ] **Step 2: Run test to verify**

Run: `pytest tests/test_benchmark_metrics.py -v`

- [ ] **Step 3: Implement streaming metrics calculation in `scripts/benchmark.py`**

- [ ] **Step 4: Run test to verify passes**

Run: `pytest tests/test_benchmark_metrics.py -v`

- [ ] **Step 5: Commit**

```bash
git add scripts/benchmark.py tests/test_benchmark_metrics.py
git commit -m "feat(benchmarking): add streaming TTFT and percentile latency metrics"
```

---

### Task 3: Execute `EXP-12` (Native Hardware FP8 vs BF16 on 4x L4)

**Files:**
- Modify: `docs/experiments_status.md`

**Interfaces:**
- Consumes: Target model `gemma-2-27b-it` or `gemma-3-27b-it` deployed with `--quantization=fp8`
- Produces: Empirical benchmark results logged in Section 1 and Section 3 of `docs/experiments_status.md`

- [ ] **Step 1: Register and deploy model with `--quantization=fp8` on `g2-standard-48`**

Run: `EXTRA_VLLM_FLAGS="--quantization=fp8" just vertex-deploy gemma-3-27b-it`

- [ ] **Step 2: Run multi-stream concurrency benchmark ($N=1, 2, 4, 8$)**

Run: `python3 scripts/benchmark.py --streams 1,2,4,8 --prompt "Explain the mechanics of zero-trust network architectures in enterprise cloud environments."`

- [ ] **Step 3: Record empirical results, latency, and throughput in `docs/experiments_status.md`**

- [ ] **Step 4: Cleanly undeploy model and delete endpoint**

Run: `just vertex-undeploy`

- [ ] **Step 5: Commit**

```bash
git add docs/experiments_status.md
git commit -m "docs: record EXP-12 native FP8 quantization benchmark results"
```

---

### Task 4: Execute `EXP-13` (Chunked Prefill & Prefix Caching)

**Files:**
- Modify: `docs/experiments_status.md`

**Interfaces:**
- Consumes: Model deployed with `--enable-chunked-prefill` and `--enable-prefix-caching`
- Produces: Benchmark comparisons for cold vs cached multi-turn prompt context

- [ ] **Step 1: Deploy model with prefix caching flags**

Run: `EXTRA_VLLM_FLAGS="--enable-chunked-prefill --enable-prefix-caching" just vertex-deploy gemma-3-27b-it`

- [ ] **Step 2: Run multi-turn benchmark workload with repetitive shared system prompt**

Run: `python3 scripts/benchmark.py --prefix-caching-test`

- [ ] **Step 3: Record speedup and TTFT reduction in `docs/experiments_status.md`**

- [ ] **Step 4: Cleanly undeploy model and delete endpoint**

Run: `just vertex-undeploy`

- [ ] **Step 5: Commit**

```bash
git add docs/experiments_status.md
git commit -m "docs: record EXP-13 chunked prefill and prefix caching benchmark results"
```
