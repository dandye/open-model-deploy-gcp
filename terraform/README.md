# Multi-Model & Gemma Deployment via Terraform

This directory provides Terraform (Infrastructure-as-Code) configurations to provision Gemma, Llama, and frontier partner model serving infrastructure on Google Cloud Platform across Vertex AI Online Prediction and Cloud Run with GPU.

---

## 1. Multi-Model Catalog Integration

Configurations dynamically resolve compute, accelerator count, VRAM, context length, swap space, and container images from the centralized model catalog at `configs/models.json`.

Supported dedicated GPU models:
* **Google Gemma**: `gemma-2-2b-it` (1x L4), `gemma-2-9b-it` (1x L4), `gemma-2-27b-it` (4x L4), `gemma-3-1b-it` (1x L4), `gemma-3-4b-it` (1x L4), `gemma-3-12b-it` (4x L4), `gemma-3-27b-it` (4x L4), `gemma-4-e2b-it` (1x L4), `gemma-4-e4b-it` (1x L4), `gemma-4-31b-it` (2x A100 80GB)
* **Meta Llama**: `llama-3.2-3b-instruct` (1x L4), `llama-guard-3-8b` (1x L4), `llama-3.1-nemotron-70b-instruct` (4x L4)
* **OpenModels & Partner Model Garden**: `qwen3.8-27b` (1x RTX 6000), `qwen2.5-coder-32b-instruct` (4x L4), `qwen3.8-flash-next` (1x L4), `qwen3.8-flash-next-fp8` (1x L4), `qwen3.8-2.4t-a95b-fp8` (1x RTX 6000), `glm-5.3-flash` (1x L4), `deepseek-v4-pro` (1x RTX 6000), `deepseek-r1-distill-qwen-32b` (4x L4), `kimi-k3` (1x RTX 6000), `inkling-small` (4x L4), `nemotron-3.5-lightning-bf16` (4x L4), `nemotron-3.5-super-vl-nvfp4` (1x RTX 6000), `nemotron-3.5-super-vl-bf16` (4x RTX 6000), `ministral-3b-2410` (1x L4), `phi-4` (1x L4)

---

## 2. Target Environment Compatibility

| Target Environment | Supported Models | GPU Scaling | Notes |
| :--- | :--- | :--- | :--- |
| **Vertex AI Prediction** | All 28 dedicated compute models | 1x to 4x GPUs | Dedicated VM serving; requires undeploy to stop billing. |
| **Cloud Run with GPU** | Single-GPU models (1B to 9B, E2B, E4B) | 1x NVIDIA L4 | Scale-to-zero (`--min-instances=0`) for $0 idle cost. Multi-GPU models are automatically skipped. |

---

## 3. Resources Managed

* **Vertex AI Endpoint** (`google_vertex_ai_endpoint`): Creates dedicated online prediction endpoint with model metadata labels and dynamic sizing descriptions.
* **Cloud Run GPU Service** (`google_cloud_run_v2_service`): Deploys vLLM server on 1x NVIDIA L4 GPU with scale-to-zero, dynamic context length, swap space, and optional optimization flags.
* **Cloud Run IAM Policy** (`google_cloud_run_v2_service_iam_member`): Configures public/authenticated invocation access.

---

## 4. Runtime Optimization Flags (`extra_vllm_flags`)

Pass extra runtime optimization flags via the `extra_vllm_flags` variable:
* Native FP8 Quantization: `extra_vllm_flags = "--quantization=fp8"`
* Prompt Lookup (N-gram) Speculative Decoding: `extra_vllm_flags = "--speculative-model=[ngram] --num-speculative-tokens=5"`
* Prefix Caching: `extra_vllm_flags = "--enable-prefix-caching"`
* Chunked Prefill: `extra_vllm_flags = "--enable-chunked-prefill"`

---

## 5. Usage

### Via Justfile (Recommended)

```bash
# Initialize Terraform
just tf-init

# Plan deployment for specific model flavor
just tf-plan gemma-3-4b-it

# Plan with FP8 quantization
just tf-plan gemma-3-27b-it "--quantization=fp8"

# Plan partner open model
just tf-plan qwen3.8-27b

# Apply deployment
just tf-apply gemma-3-4b-it

# Destroy provisioned infrastructure
just tf-destroy
```

### Direct Terraform CLI

```bash
cd terraform

# Initialize
terraform init

# Copy example variables
cp terraform.tfvars.example terraform.tfvars

# Plan
terraform plan -var="model_flavor=gemma-3-4b-it"

# Apply
terraform apply -var="model_flavor=gemma-3-4b-it" -auto-approve

# Teardown
terraform destroy
```
