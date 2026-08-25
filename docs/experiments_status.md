---
title: "Gemma 4 Performance Optimization: Experiment Status & Live Tracker"
description: "Empirical results, logs, and benchmark progression for performance optimization experiments on Gemma 4 31B."
type: "status"
tags:
  - gemma4
  - experiments
  - benchmarks
  - performance-tracking
created: 2026-08-25
updated: 2026-08-25
---

# Gemma 4 Performance Optimization: Experiment Status & Live Tracker

This document tracks all optimization experiments for **Gemma 4 31B (`gemma-4-31b-it`)**, maintaining an empirical log of configurations tested, benchmark results, and teardown verifications.

---

## 1. Experiment Results Matrix

| Exp ID | Configuration / Optimization Hypothesis | Machine Type | GPU Setup | TP | Warmup Time | Avg Latency | Avg Output | TPS (tok/s) | TPM (tok/min) | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **EXP-00** | **Baseline (Eager Mode `--enforce-eager`)** | `g2-standard-48` | 4x L4 (96 GB) | 4 | 20.54 s | 12.76 s | 39 tok | **3.1 tok/s** | **183 tok/min** | Baseline Complete (Torn Down) |
| **EXP-01** | **Default Sampler Warmup (256 seqs, 0.90 mem)** | `g2-standard-48` | 4x L4 (96 GB) | 4 | N/A | N/A | N/A | N/A | N/A | Failed: Sampler CUDA OOM (Documented) |
| **EXP-01b**| **Tuned Sampler Warmup (`--max-num-seqs=8`, 0.85 mem, CUDA Graphs)** | `g2-standard-48` | 4x L4 (96 GB) | 4 | TBD | TBD | TBD | TBD | TBD | In Progress |
| **EXP-02** | **vLLM Engine Tuning (`--kv-cache-dtype=fp8` & Chunked Prefill)** | `g2-standard-48` | 4x L4 (96 GB) | 4 | TBD | TBD | TBD | TBD | TBD | Queued |
| **EXP-03** | **Single High-Bandwidth GPU Architecture** | `a2-ultragpu-1g` / `g4-standard-48` | 1x A100 / RTX 6000 | 1 | TBD | TBD | TBD | TBD | TBD | Queued |

---

## 2. Detailed Experiment Logs

### EXP-00: Baseline (Eager Mode)
* **Goal**: Establish baseline throughput on default Vertex AI container wrapper.
* **Configuration**:
  * Machine: `g2-standard-48` (4x NVIDIA L4, 96GB VRAM)
  * Container: `us-docker.pkg.dev/vertex-ai/vertex-vision-model-garden-dockers/pytorch-vllm-serve:gemma4`
  * Flags: `--enforce-eager`
* **Findings**:
  * Initialization: 10.14s weight download/load, instant startup in eager mode.
  * Inference: 3.1 tok/s due to sequential kernel dispatch and PCIe AllReduce synchronization.
* **Status**: Tested, verified, and torn down.

---

### EXP-01: Default Sampler Warmup Analysis
* **Goal**: Measure compiled CUDA graph speedup without eager mode.
* **Failure Analysis**:
  * Trace: `RuntimeError: CUDA out of memory occurred when warming up sampler with 256 dummy requests.`
  * Cause: On 24GB L4 GPUs, 15.89 GB weights + default 256 dummy request warmup exceeds remaining VRAM headroom.
  * Resolution: Bound warmup budget via `--max-num-seqs=8`, `--gpu-memory-utilization=0.85`, and `maxModelLen=4096`.
* **Status**: Completed root-cause analysis; proceeding to EXP-01b.

---
