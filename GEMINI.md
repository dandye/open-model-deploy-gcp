# Gemma Deploy Workspace Guide (GEMINI.md)

This file provides architectural context, commands, and project conventions for AI agents working within this repository.

---

## 1. Project Overview & Architecture

This repository contains automation scripts, Terraform modules, `Justfile` recipes, and documentation for deploying Google Gemma models on Google Cloud Platform across two runtime environments:

1. **Vertex AI Online Prediction**: Dedicated GPU virtual machines (`g2-standard-4`, `g2-standard-8`, `g2-standard-12`, `g2-standard-48`) for persistent model serving.
2. **Cloud Run with GPU**: Serverless containers (`1x NVIDIA L4 GPU`, `--min-instances=0`) enabling scale-to-zero when idle ($0 idle cost).

---

## 2. Multi-Model Architecture & Centralized Catalog

The repository uses a single source of truth at [`configs/models.json`](configs/models.json) defining compute, runtime, VRAM, and target environment compatibility for all supported Gemma variants:
* **Gemma 2 2B / 9B / 27B** (`gemma-2-2b-it`, `gemma-2-9b-it`, `gemma-2-27b-it`)
* **Gemma 3 1B / 4B / 12B / 27B** (`gemma-3-1b-it`, `gemma-3-4b-it`, `gemma-3-12b-it`, `gemma-3-27b-it`)
* **Gemma 4 E2B / E4B / 31B** (`gemma-4-e2b-it`, `gemma-4-e4b-it`, `gemma-4-31b-it`)


All bash scripts, Terraform modules, and CLI commands read dynamically from this catalog via [`scripts/lib/model_catalog.sh`](scripts/lib/model_catalog.sh) and Terraform `jsondecode()`.

---

## 3. Project Conventions & Agent Guardrails

* **No Emojis**: Never use emojis in code, commits, comments, or documentation.
* **Shell Variables**: Always define shell variables explicitly (`PROJECT_ID="..."`) before expanding (`$PROJECT_ID`).
* **Worktree Portability**: All scripts and tools must resolve paths relative to the repository root (`ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"`).
* **Cost Awareness**: Dedicated GPU endpoints do not support scale-to-zero. Always run `just vertex-undeploy` after testing to stop active GPU billing.

---

## 4. Key Architectural Constraints & Lessons Learned

### Vertex AI Prediction
* **Host RAM & Swap Space**: Custom Model Garden container specifications must set `--swap-space` appropriately (`8` for <=32GB RAM, `16` for 48GB RAM, `32` for 192GB RAM) to avoid `ValueError: Too large swap space`.
* **Gemma 4 Custom Container**: `gemma-4-31b-it` uses a dedicated container image (`us-docker.pkg.dev/vertex-ai/vertex-vision-model-garden-dockers/pytorch-vllm-serve:gemma4`) with `swapSpaceGb: 0` and omits `--disable-log-stats`.
* **Multimodal Configuration**: Gemma 3 12B and 27B require multimodal CLI arguments in vLLM (`--limit_mm_per_prompt=image=5` and `--max-num-seqs=4`).
* **Accelerator Count Mappings**: On GCP `g2` instances:
  * `g2-standard-4`, `g2-standard-8`, `g2-standard-12`, `g2-standard-16`: Exactly **1x L4** (`count=1`).
  * `g2-standard-48`: Exactly **4x L4** (`count=4`).
* **Container Entrypoint**: Do **not** override `command` in `gcloud ai models upload` when using Google Model Garden images; allow Google's default container wrapper to download `gs://` weights locally before launching vLLM.
* **Model IDs**: `gcloud ai endpoints deploy-model` requires the **numeric/registered Model ID** from Vertex AI Model Registry.
* **Billing**: Dedicated GPU endpoints do **not** support `min-replica-count=0`. To stop billing, run `just vertex-undeploy`.

### Cloud Run GPU
* **Scale-to-Zero**: Cloud Run supports `--min-instances=0` with NVIDIA L4 GPUs.
* **Single-GPU Constraint**: Cloud Run GPU currently supports 1x GPU per instance. Only single-GPU models (`gemma-2-2b-it`, `gemma-2-9b-it`, `gemma-3-1b-it`, `gemma-3-4b-it`) can be deployed to Cloud Run.
* **Quota Requirement**: Cloud Run GPU quota (`run.googleapis.com`) is separate from Vertex AI quota and defaults to `0` until requested.

---

## 5. Primary Commands (`Justfile`)

| Recipe | Action |
| :--- | :--- |
| `just` | Display categorized help menu |
| `just status` | Print unified live dashboard of all Vertex AI and Cloud Run resources |
| `just auth-check` | Verify gcloud account, project configuration & ADC token validity |
| `just model-list` | List models in catalog (`configs/models.json`) & registered models |
| `just cost-list` | Display hardware pricing & sizing table in terminal |
| `just predict "<prompt>" [flavor]` | Send test prompt to active endpoint |
| `just vertex-register [flavor]` | Register a Gemma flavor in Vertex AI Model Registry |
| `just vertex-deploy [flavor]` | Deploy specific Gemma flavor to Vertex AI (auto-sizes compute) |
| `just vertex-status` | Check deployment progress and active operations |
| `just vertex-undeploy` | Undeploy Gemma from Vertex AI endpoint |
| `just cloudrun-deploy [flavor]` | Deploy Gemma to Cloud Run with scale-to-zero (checks quota first) |
| `just cloudrun-status` | Check Cloud Run service status and active revisions |
| `just cloudrun-quota-check` | Verify Cloud Run GPU quota in region |
| `just cloudrun-quota-request` | Request Cloud Run NVIDIA L4 GPU quota |
| `just cloudrun-quota-reset` | Reset Cloud Run GPU quota preference back to 0 |
| `just tf-init` | Initialize Terraform working directory |
| `just tf-plan [flavor]` | Plan Terraform infrastructure for specific model flavor |
| `just tf-apply [flavor]` | Apply Terraform infrastructure for specific model flavor |
| `just tf-destroy` | Destroy Terraform-managed infrastructure |
| `just agent-test [prompt]` | Test Gemma ADK Agent locally (auto-discovers active endpoints) |
| `just agent-deploy` | Deploy Gemma ADK Agent to Vertex AI Agent Engine |

---

## 6. File Tree

* [`configs/models.json`](configs/models.json): Central model specifications & compute catalog.
* [`Justfile`](Justfile): Command definitions.
* [`.env.example`](.env.example): Environment variable template.
* [`agent/`](agent/): ADK Agent for Vertex AI Agent Engine with dynamic Gemma backend resolution.
* [`scripts/lib/model_catalog.sh`](scripts/lib/model_catalog.sh): Model catalog helper library.
* [`scripts/`](scripts/): Automation scripts for deployment, quota management, and query operations.
  * [`scripts/benchmark.py`](scripts/benchmark.py): Model latency and throughput benchmarking tool.
* [`terraform/`](terraform/): Terraform Infrastructure-as-Code definitions.
* [`docs/`](docs/): Operational, architectural, and cost analysis documentation.
  * [`docs/deployment_status.md`](docs/deployment_status.md): Active deployment registry and operational tracking.
  * [`docs/experiments_status.md`](docs/experiments_status.md): Vertex AI optimization experiment tracking and benchmarks.
  * [`docs/cloudrun_experiments_status.md`](docs/cloudrun_experiments_status.md): Cloud Run GPU experiment tracking and benchmarks.
  * [`docs/cost_analysis.md`](docs/cost_analysis.md): Hardware pricing and sizing breakdown.
  * [`docs/vertex_cleanup_strategies.md`](docs/vertex_cleanup_strategies.md): Endpoint and resource cleanup guide.
  * [`docs/cloudrun_deploy.md`](docs/cloudrun_deploy.md): Cloud Run GPU guide and scale-to-zero mechanics.
  * [`docs/speculative_decoding.md`](docs/speculative_decoding.md): Speculative decoding guide, N-gram prompt lookup mechanics & Vertex AI benchmarks.
  * [`docs/model_registry_catalog.md`](docs/model_registry_catalog.md): Authoritative Vertex AI Model Registry inventory & creation commands.
  * [`docs/quota_requests.md`](docs/quota_requests.md): Cloud GPU quota requests and tracking log.


