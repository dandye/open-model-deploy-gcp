# Llama & Partner Models Experiment Status & Benchmarks

## 1. Experiment Registry & Model Enablement Status

This document records the empirical benchmarking and operational performance of Meta Llama, Model Garden partner models, and Hugging Face OpenModels on Google Cloud Vertex AI.

### Model Enablement & Availability Matrix

| Model Identifier | Provider | Model ID / Version | Serving Tier | Region | Model Garden Enablement | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `llama-4-scout-17b-16e-instruct-maas` | Meta | `publishers/meta/models/llama-4-scout-17b-16e-instruct-maas` | Vertex MaaS | `us-east5` | `ENABLEMENT_STATE_SUCCEEDED` | Evaluated (40% Pass, 77.0 Score) |
| `llama-4-maverick-17b-128e-instruct-maas` | Meta | `publishers/meta/models/llama-4-maverick-17b-128e-instruct-maas` | Vertex MaaS | `us-east5` | `ENABLEMENT_STATE_SUCCEEDED` | Evaluated (0% Pass, 62.0 Score) |
| `inkling-small` | Thinking Machines | `publishers/thinkingmachines/models/inkling` | Dedicated MG | `us-central1` | `ENABLEMENT_STATE_SUCCEEDED` | Ready for dedicated deploy (4x L4) |
| `nemotron-3.5-lightning-bf16` | NVIDIA | `publishers/nvidia/models/nemotron-3.5-lightning` | Dedicated MG | `us-central1` | `ENABLEMENT_STATE_SUCCEEDED` | Ready for dedicated deploy (4x L4) |
| `grok-4.6` | xAI | `publishers/xai/models/grok-4.6` | Vertex MaaS | `global` | Managed API | Configured in catalog |
| `qwen3.8-27b` | HF / Qwen | `hf-qwen/qwen3.8-27b@001` | OpenModel | `us-central1` | One-Click Deploy | Ready for deploy (1x RTX PRO 6000) |

---

## 2. Vertex AI MaaS Benchmark Summary

| Model Identifier | Provider | MoE Configuration | Region | Output TPS | Total TPS | Avg Latency | Avg Total Tokens |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `meta/llama-4-scout-17b-16e-instruct-maas` | Meta | 17B active (16 experts) | `us-east5` | 82.73 tok/s | 269.56 tok/s | 8.93 s | 2,406.6 tok/case |
| `meta/llama-4-maverick-17b-128e-instruct-maas` | Meta | 17B active (128 experts) | `us-east5` | 61.36 tok/s | 131.51 tok/s | 12.08 s | 1,589.0 tok/case |

---

## 3. Dedicated Model Garden Models in Catalog

| Model Identifier | Provider | Compute Type | Accelerator Count | Host RAM | Hourly Cost | Container Image |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `inkling-small` | Thinking Machines | `g2-standard-48` | 4x NVIDIA L4 | 192 GB | $3.32/hr | `pytorch-vllm-serve:20250312_0916_RC01` |
| `nemotron-3.5-lightning-bf16` | NVIDIA | `g2-standard-48` | 4x NVIDIA L4 | 192 GB | $3.32/hr | `pytorch-vllm-serve:20250312_0916_RC01` |
| `qwen3.8-27b` | Qwen / HF | `g4-standard-48` | 1x RTX PRO 6000 | 192 GB | $3.85/hr | `pytorch-vllm-serve:20260713_0916_RC01` |
| `grok-4.6` | xAI | Serverless MaaS | Serverless | Managed | On-Demand | Managed API (`global`) |

---

## 4. Operational Notes & Regional Availability

* **Meta Llama 4 MaaS (`us-east5`)**:
  - `llama-4-maverick-17b-128e-instruct-maas` and `llama-4-scout-17b-16e-instruct-maas` are hosted in region `us-east5`.
  - Accessible via `google-genai` Python SDK with `genai.Client(vertexai=True, location='us-east5')` using model string `meta/<model_id>`.
* **Model Garden Agreement Enablement**:
  - Successfully activated via `POST https://us-central1-aiplatform.googleapis.com/v1beta1/projects/{PROJECT}/{MODEL_ID}:enableModel` for `publishers/thinkingmachines/models/inkling` and `publishers/nvidia/models/nemotron-3.5-lightning`.
* **OpenModel One-Click Deploy**:
  - `qwen3.8-27b` uses `vertexai.model_garden.OpenModel("hf-qwen/qwen3.8-27b@001")` deployed via `just openmodel-deploy qwen3.8-27b`.
