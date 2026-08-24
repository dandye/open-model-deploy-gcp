# Gemma Deploy Workspace Guide (GEMINI.md)

This file provides architectural context, commands, and project conventions for AI agents working within this repository.

---

## 1. Project Overview & Architecture

This repository contains automation scripts, `Justfile` recipes, and documentation for deploying Google Gemma models on Google Cloud Platform across two runtime environments:

1. **Vertex AI Online Prediction**: Dedicated GPU virtual machines (`g2-standard-24`, 2x NVIDIA L4 GPUs, 96 GiB RAM) for persistent, high-throughput model serving.
2. **Cloud Run with GPU**: Serverless containers (`1x NVIDIA L4 GPU`, `--min-instances=0`) enabling true scale-to-zero when idle ($0 idle cost).

---

## 2. Key Architectural Constraints & Lessons Learned

### Vertex AI Prediction
* **Swap Space & Host RAM**: Model Garden vLLM containers default to `--swap-space 64` (64 GiB host RAM). Machine types with <= 64 GB RAM (e.g., `g2-standard-4`, `g2-standard-16`) crash at startup with `ValueError: Too large swap space`. Use **`g2-standard-24`** (96 GiB RAM).
* **Accelerator Count Mappings**: On GCP `g2` instances:
  * `g2-standard-4`, `g2-standard-8`, `g2-standard-12`, `g2-standard-16`: Exactly **1x L4** (`count=1`).
  * `g2-standard-24`: Exactly **2x L4** (`count=2`).
  * `g2-standard-48`: Exactly **4x L4** (`count=4`).
* **Model IDs**: `gcloud ai endpoints deploy-model` requires the **numeric/registered Model ID** from Vertex AI Model Registry (e.g. `gemma-3-12b-it-1747240724884`), not a Hugging Face URI.
* **Billing**: Dedicated GPU endpoints do **not** support `min-replica-count=0`. To stop billing, run `./scripts/vertex_undeploy.sh` (or `just vertex-undeploy`).

### Cloud Run GPU
* **Scale-to-Zero**: Cloud Run supports `--min-instances=0` with NVIDIA L4 GPUs.
* **Quota Requirement**: Cloud Run GPU quota (`run.googleapis.com`) is separate from Compute Engine/Vertex AI quota and defaults to `0` until requested via `just cloudrun-quota-request` or the Cloud Quotas console.
* **Dependency Check**: `just cloudrun-deploy` depends on `cloudrun-quota-check` to verify quota before attempting deployment.

---

## 3. Style & Engineering Conventions

* **Big-Endian Naming**: All scripts, docs, and Just recipes use category-first / big-endian naming:
  * `vertex-deploy`, `vertex-undeploy`
  * `cloudrun-deploy`, `cloudrun-quota-request`, `cloudrun-quota-reset`, `cloudrun-quota-check`
  * `scripts/vertex_*.sh`, `scripts/cloudrun_*.sh`
  * `docs/vertex_*.md`, `docs/cloudrun_*.md`
* **Configuration**: Scripts must source `${ROOT_DIR}/.env` if present, with hardcoded fallback defaults for every variable.
* **No Emojis**: Do not use emojis in scripts, console outputs, error messages, or documentation files. Use plain text indicators like `[OK]` and `[WARNING]`.

---

## 4. Primary Commands (`Justfile`)

| Recipe | Action |
| :--- | :--- |
| `just` | List all available recipes with descriptions |
| `just vertex-deploy` | Deploy Gemma to Vertex AI endpoint |
| `just vertex-status` | Check deployment status and active operations |
| `just vertex-undeploy` | Undeploy Gemma from Vertex AI endpoint |
| `just cloudrun-quota-check` | Verify Cloud Run GPU quota in region |
| `just cloudrun-quota-request` | Request Cloud Run NVIDIA L4 GPU quota |
| `just cloudrun-quota-reset` | Reset Cloud Run GPU quota preference back to 0 |
| `just cloudrun-deploy` | Deploy Gemma to Cloud Run with scale-to-zero (checks quota first) |

---

## 5. File Tree

* [`Justfile`](Justfile): Command definitions.
* [`.env.example`](.env.example): Environment variable template.
* [`scripts/`](scripts/): Bash scripts for all operations.
* [`docs/`](docs/): Detailed operational, architectural, and cost analysis documentation.
