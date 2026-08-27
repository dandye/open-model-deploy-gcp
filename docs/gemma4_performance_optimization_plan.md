---
title: "Gemma 4 31B: Performance Analysis & Optimization Empirical Roadmap"
description: "Root cause analysis of baseline 3.1 tok/s generation throughput and empirical results from CUDA graphs, FP8 quantization, single A100 80GB, and 2x A100 NVLink serving."
type: "plan"
tags:
  - gemma4
  - performance-optimization
  - vllm-tuning
  - latency-reduction
  - throughput
  - benchmarks
created: 2026-08-25
updated: 2026-08-25
status: "completed"
---

# Gemma 4 31B: Performance Analysis & Optimization Empirical Roadmap

## 1. Baseline Performance Summary

During initial baseline testing on Google Cloud Vertex AI dedicated prediction endpoints, **Gemma 4 31B Instruct (`gemma-4-31b-it`)** exhibited the following metrics on **`g2-standard-48`** (4x NVIDIA L4 GPUs, 96GB VRAM total):

* **Generation Speed**: **3.1 tokens / second** (183 tokens / minute)
* **Warm Step Latency**: **12.76 seconds** (for 39 generated tokens)
* **Cold Start Latency**: **20.54 seconds**
* **Hourly Cost**: **$3.36 / hour**
* **Cost per 1M Generated Tokens**: **$306.01 / 1M tokens**

---

## 2. Root Cause Analysis

```
+-----------------------------------------------------------------------------------+
|                           Root Causes of Latency Bottleneck                       |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  1. Eager Mode (No CUDA Graphs)                                                   |
|     +-- Launched with --enforce-eager to bypass 60s IPC EngineCore timeout.      |
|     +-- Dispatches individual kernels sequentially via Python interpreter.       |
|     +-- Adds ~15-20ms of host CPU launch latency per token generation step.      |
|                                                                                   |
|  2. PCIe Interconnect Overhead (4-Way Tensor Parallelism)                         |
|     +-- g2-standard-48 connects 4x L4 GPUs over standard PCIe Gen4 (no NVLink).  |
|     +-- Requires AllReduce communication barrier across PCIe on every layer.     |
|     +-- 64+ transformer layers * 2 syncs/layer = 128+ PCIe syncs per token.      |
|                                                                                   |
|  3. Memory Bandwidth Saturation (BF16 Full Weights)                               |
|     +-- 31B parameters in BF16 = ~62 GB of weights read per token step.          |
|     +-- L4 VRAM bandwidth is 300 GB/s per card (~1,200 GB/s aggregate).          |
|     +-- Theoretical max speed: 1,200 GB/s / 62 GB = ~19 tok/s (ideal).           |
|                                                                                   |
+-----------------------------------------------------------------------------------+
```

---

## 3. Empirical Results Across Experimental Tracks

For detailed per-run logs, refer to [`experiments_status.md`](experiments_status.md) and [`cost_analysis.md`](cost_analysis.md).

### Track A: Compilation & CUDA Graph Execution (`EXP-01b`)
* **Hypothesis**: Replacing eager execution with CUDA graph capture eliminates Python kernel launch overhead.
* **Result**:
  * Steady-state warm generation latency improved from **12.76s to 10.20s**.
  * Generation speed increased from **3.1 to 3.8 tok/s (+23% speedup)**.
  * Ceiling identified: 128+ PCIe `AllReduce` communication barriers across the 4 L4 cards remained the primary bottleneck.

### Track B: KV Cache Tuning (`EXP-02`)
* **Hypothesis**: Quantizing KV cache to 8-bit (`--kv-cache-dtype=fp8`) reduces memory footprint and cache memory pressure.
* **Result**: Reduced KV cache memory consumption by **50%** with zero numerical divergence. Single-stream speed remained 3.8 tok/s due to PCIe AllReduce limits.

### Track C: Quantization on Diverse GPU Architectures (`EXP-05` vs `EXP-06`)
* **Ampere (A100, `EXP-05`)**: Triton/Inductor autotuning failed with `ValueError: type fp8e4nv not supported in this architecture`. Ampere lacks hardware tensor core support for `fp8e4nv` (E4M3), requiring native BF16 or BitsAndBytes INT8.
* **Ada Lovelace (L4, `EXP-06`)**: Native 4th-Gen FP8 Tensor Cores accelerated weight execution, pushing 4x L4 throughput from **3.1 tok/s to 7.1 tok/s (+129% speedup)** and **424 tok/min**. Note: Dynamic uncalibrated scaling on BF16 weights requires static scale factors to avoid output token repetition.

### Track D: High-Bandwidth Dedicated Interconnects (`EXP-04` & `EXP-07b`)
* **Single A100 80GB (`a2-ultragpu-1g`, TP=1, `EXP-04`)**:
  * Completely eliminated multi-GPU PCIe AllReduce syncs.
  * Latency cut in half: **6.36 s** (vs 12.76s baseline, **-50%**).
  * Throughput doubled: **6.1 tok/s** / **368 tok/min** (**+97%** vs baseline) with pristine output quality.
* **2x A100 40GB with 600 GB/s NVLink (`a2-highgpu-2g`, TP=2, `EXP-07b`)**:
  * Replaced ~32 GB/s PCIe with a **600 GB/s bidirectional NVLink bridge**.
  * Latency dropped to **4.29 s** (vs 12.76s baseline, **-66% latency reduction / 3x faster response**).
  * Generation speed reached **up to 23.0 tokens/second** (averaging **12.4 tok/s** / **745 tok/min**).

---

## 4. Final Optimization Scorecard

| Experiment Track | Machine Type | GPU / Interconnect | TP | Hourly Cost | Steady Latency | Generation Speed | Throughput (TPM) | Cost / 1M Tokens | Optimization Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Baseline (Eager)** | `g2-standard-48` | 4x L4 (PCIe Gen4) | 4 | $3.36 / hr | 12.76 s | 3.1 tok/s | 183 tok/min | $306.01 | Baseline Measured |
| **CUDA Graphs** | `g2-standard-48` | 4x L4 (PCIe Gen4) | 4 | $3.36 / hr | 10.20 s | 3.8 tok/s | 229 tok/min | $243.48 | +23% Speedup |
| **Native FP8 (Ada)** | `g2-standard-48` | 4x L4 (Ada Lovelace) | 4 | $3.36 / hr | 10.06 s | 7.1 tok/s | 424 tok/min | $132.08 | +129% Speedup |
| **Single Die A100** | `a2-ultragpu-1g` | 1x A100 80GB (Single Die)| 1 | $3.67 / hr | 6.36 s | 6.1 tok/s | 368 tok/min | $166.21 | -50% Latency, +97% Speedup |
| **2-GPU NVLink Mesh** | `a2-highgpu-2g` | 2x A100 40GB (600 GB/s NVLink)| 2 | $7.34 / hr | 4.29 s | 12.4 – 23.0 tok/s | 745 – 1,382 tok/min | $164.20 | -66% Latency, 3x-7x Faster |
| **NVLink Concurrency Scaling ($N=8$)**| `a2-highgpu-2g` | 2x A100 40GB (600 GB/s NVLink)| 2 | $7.34 / hr | 4.58 s (warm)| **77.9 – 90.1 tok/s** | **4,676 – 5,403 tok/min**| **$26.15** | **+2,850% throughput vs baseline** |
