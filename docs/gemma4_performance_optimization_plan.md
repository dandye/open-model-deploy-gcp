---
title: "Gemma 4 31B: Performance Analysis & Throughput Optimization Plan"
description: "Root cause analysis of baseline 3.1 tok/s generation throughput and systematic experimental roadmap to maximize serving speed on GCP."
type: "plan"
tags:
  - gemma4
  - performance-optimization
  - vllm-tuning
  - latency-reduction
  - throughput
created: 2026-08-25
status: "in-progress"
---

# Gemma 4 31B: Performance Analysis & Throughput Optimization Plan

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

## 3. Experimental Roadmap

### Experiment Track A: Compilation & Graph Execution
* **Hypothesis**: Replacing eager execution with CUDA graph capture or tuned `torch.compile` will eliminate Python kernel launch overhead, increasing generation speed from ~3 tok/s to ~8–12 tok/s.
* **Method**:
  1. Set container environment variables `VLLM_RPC_TIMEOUT=300` and `VLLM_TORCH_COMPILE_TIMEOUT=300`.
  2. Test compilation configuration flags (`--max-seq-len-to-capture=2048`, `--enable-chunked-prefill=true`).
  3. Compare latency, warmup time, and steady-state tokens/sec.

### Experiment Track B: KV Cache & Engine Parameter Tuning
* **Hypothesis**: Optimizing KV cache precision (`--kv-cache-dtype=fp8`) and batch execution parameters will reduce memory bus pressure and increase token throughput.
* **Method**:
  1. Benchmark `--kv-cache-dtype=fp8` vs default `auto`.
  2. Measure concurrency scaling across 1, 2, and 4 parallel requests.

### Experiment Track C: Quantization & Compression (FP8 / AWQ)
* **Hypothesis**: Using FP8 (W8A8) quantized weights reduces memory transfer from 62 GB/step to ~31 GB/step, leveraging native Ada Lovelace 4th-gen Tensor Core FP8 acceleration for a 2x–3x speedup.
* **Method**:
  1. Test FP8 model variants if available in Model Garden / vLLM.
  2. Measure accuracy/perplexity impact and throughput gain.

### Experiment Track D: Single High-Bandwidth Accelerator Architecture
* **Hypothesis**: Serving on a single high-memory GPU (A100 80GB, H100 80GB, or RTX 6000 Ada 96GB) completely eliminates PCIe AllReduce latency, enabling 25–50 tok/s.
* **Method**:
  1. Check quota and deployability of `a2-ultragpu-1g` / `g4-standard-48`.
  2. Compare price-performance efficiency ($/1M tokens).

---

## 4. Experiment Success Criteria

| Metric | Baseline (Eager 4x L4) | Target (Optimized 4x L4) | Target (Single High-VRAM GPU) |
| :--- | :--- | :--- | :--- |
| **Generation Speed (TPS)** | 3.1 tok/s | **>= 10.0 tok/s** | **>= 25.0 tok/s** |
| **Tokens Per Minute (TPM)** | 183 tok/min | **>= 600 tok/min** | **>= 1,500 tok/min** |
| **Warm Step Latency (50 tok)** | ~16.0 s | **<= 5.0 s** | **<= 2.0 s** |
| **Cost / Million Tokens** | $306.01 | **<= $93.00** | **<= $40.00** |
