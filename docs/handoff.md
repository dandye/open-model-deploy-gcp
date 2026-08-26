---
title: "Project Session Handoff & State Summary"
description: "Operational state, active cloud resources, PR status, benchmark findings, and next milestones for gemma_deploy."
type: "guide"
tags:
  - handoff
  - operational-state
  - gemma
  - vertex-ai
  - agent-engine
created: 2026-08-26
updated: 2026-08-26
---

# Project Session Handoff & State Summary

This document captures the operational state, active cloud endpoints, PR status, architectural conventions, and recommended next steps for engineering sessions working in `gemma_deploy`.

---

## 1. Repository & Branch Status

* **Workspace Directory**: `/usr/local/google/home/dandye/Projects/gemma_deploy__worktrees/agent_engine`
* **Active Branch**: `agent_engine`
* **Pull Request**: [PR #1 (agent_engine -> main)](https://depot.code.corp.goog/personal/gemma_deploy/pull/1)
* **Conflict Status**: **0 conflicts** (Fully rebased and merged with `origin/main`).
* **Test Verification**: **63 / 63 tests passing** (`uv run pytest -v`).
* **Latest Merge Commit**: [`98c998a`](https://depot.code.corp.goog/personal/gemma_deploy/commit/98c998a)

---

## 2. Active Cloud Infrastructure & Live State

> [!IMPORTANT]
> **Active Dedicated GPU Endpoint Running**:
> Do NOT automatically tear down the endpoint unless directed by the user. Active endpoint was kept alive to support rapid iteration.

* **GCP Project**: `dandye-0324-chronicle`
* **Vertex AI Endpoint ID**: `4868079485641031680`
* **Endpoint Display Name**: `gemma-3-4b-it-endpoint-20260825-2220`
* **Region**: `us-central1`
* **Hardware**: `g2-standard-8` (1x NVIDIA L4 GPU, 32 GB Host RAM, 24 GB VRAM)
* **Deployed Model ID**: `8991380031196364800` (`gemma-3-4b-it-model-garden`)
* **Cost Rate**: ~$0.84 / hour ($20.16 / day).
* **Teardown Command (when iteration concludes)**:
  ```bash
  just vertex-undeploy
  ```

---

## 3. Core Architectural Conventions & Guardrails

1. **Un-Spoiled Evaluation Philosophy** ([`docs/thoughts_on_evals.md`](thoughts_on_evals.md)):
   * The system prompt in [`agent/soc_tier1_agent.py`](../agent/soc_tier1_agent.py) must remain general and principled (Evidence-Based Investigation, Grounded Attribution, Decisive Containment, Case Lifecycle Management, Structured Output).
   * **Never hardcode alert-specific runbooks or cheat sheets in the agent persona** so the benchmark remains discriminative across model capacities.
2. **ReAct Tool Execution Architecture**:
   * Robust multi-format parsing supports raw JSON actions, markdown code blocks, and structured action syntax with auto-recovery.
3. **Vertex AI Global Endpoint Routing**:
   * Next-generation preview/managed models (`gemini-3.7-flash` and `gemini-3.5-flash-lite`) must route through `location="global"` (`genai.Client(vertexai=True, location='global')`).
4. **Project Coding Rules**:
   * **Zero emojis** anywhere in code, markdown, docstrings, or commit messages.
   * Path resolutions must be repository-root relative (`ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"`).

---

## 4. Benchmark Summary Matrix

| Metric | `gemma-3-4b-it` (1x L4 Dedicated) | `gemini-2.5-flash` (Managed MaaS) | `gemini-2.5-pro` (Managed MaaS Pro) | `gemini-3.5-flash-lite` (Managed Global) | `gemini-3.7-flash` (Managed Global) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Model Generation** | Open Weights (4B) | Gemini 2.5 Flash | Gemini 2.5 Pro | Gemini 3.5 Flash-Lite | Gemini 3.7 Flash |
| **Pass Rate** | **0.0%** (0/5) | **40.0%** (2/5) | **40.0%** (2/5) | **100.0%** (5/5) | **40.0%** (2/5) |
| **Average Score** | **48.0 / 100** | **69.0 / 100** | **48.0 / 100** | **97.0 / 100** | **64.0 / 100** |
| **Average Latency** | **27.59 s** | **10.28 s** | **27.57 s** | **11.36 s** | **24.20 s** |
| **Output Speed (Gen TPS)**| **13.88 tok/s** | **64.48 tok/s** | **51.77 tok/s** | **70.22 tok/s** | **40.46 tok/s** |
| **Total Tool Invocations**| **2 tool calls** | **4 tool calls** | **9 tool calls** | **5 tool calls** | **10 tool calls** |

* Detailed comparative analysis: [`docs/soc_model_comparative_evals.md`](soc_model_comparative_evals.md)
* Individual run logs: [`docs/soc_eval_results/`](soc_eval_results/)

---

## 5. Immediate Next Milestones

1. **Merge Pull Request #1**:
   * Complete review and merge [PR #1](https://depot.code.corp.goog/personal/gemma_deploy/pull/1) into `main`.
2. **Model Parameter Sweep with Larger Gemmas**:
   * Evaluate `gemma-2-9b-it` (1x L4) and `gemma-3-27b-it` FP8 (4x L4) under the un-spoiled benchmark to observe where open-weights models achieve frontier-level multi-hop tool chaining.
3. **Agent Fine-Tuning & Few-Shot Investigation**:
   * Test few-shot prompting or fine-tuning datasets to teach smaller Gemma models (1B–4B) epistemic tool discipline without hardcoded cheat sheets.
4. **Endpoint Teardown**:
   * When testing and iteration conclude, run `just vertex-undeploy` to return to $0/hr active compute billing.
