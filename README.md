# Gemma Multi-Model Deployment on Google Cloud

Automated deployment scripts, Terraform modules, and Justfile recipes for deploying the entire Google Gemma model family (Gemma 2 2B/9B/27B, Gemma 3 1B/4B/12B/27B) across Vertex AI Online Prediction and Cloud Run with GPU.

---

## 1. Multi-Model Architecture & Central Catalog

The repository uses a single declarative source of truth at [`configs/models.json`](configs/models.json) that defines the exact compute hardware, VRAM, context length, and target environments for each Gemma flavor:

| Flavor | Parameters | Recommended Compute | GPU Count | Hourly Cost | Supported Targets |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`gemma-3-1b-it`** | 1.0B | `g2-standard-4` | 1x NVIDIA L4 | **$0.70 / hr** | Vertex AI, Cloud Run |
| **`gemma-2-2b-it`** | 2.6B | `g2-standard-4` | 1x NVIDIA L4 | **$0.70 / hr** | Vertex AI, Cloud Run |
| **`gemma-3-4b-it`** | 4.0B | `g2-standard-8` | 1x NVIDIA L4 | **$0.76 / hr** | Vertex AI, Cloud Run |
| **`gemma-2-9b-it`** | 9.2B | `g2-standard-12` | 1x NVIDIA L4 | **$0.83 / hr** | Vertex AI, Cloud Run |
| **`gemma-3-12b-it`**| 12.0B | `g2-standard-48` | 4x NVIDIA L4 | **$3.36 / hr** | Vertex AI |
| **`gemma-2-27b-it`**| 27.2B | `g2-standard-48` | 4x NVIDIA L4 | **$3.36 / hr** | Vertex AI |
| **`gemma-3-27b-it`**| 27.0B | `g2-standard-48` | 4x NVIDIA L4 | **$3.36 / hr** | Vertex AI |

---

## 2. Quick Start (`Justfile`)

```bash
# Display categorized command menu
just

# View models in catalog and Model Registry
just model-list

# View infrastructure pricing matrix across all models
just cost-list
```

### Deploying Any Flavor

```bash
# Deploy Gemma 2 9B to Vertex AI (auto-selects g2-standard-12, 1x L4)
just vertex-deploy gemma-2-9b-it

# Deploy Gemma 3 12B Multimodal to Vertex AI (auto-selects g2-standard-48, 4x L4)
just vertex-deploy gemma-3-12b-it

# Deploy Gemma 2 2B to Cloud Run with Scale-to-Zero ($0 idle)
just cloudrun-deploy gemma-2-2b-it

# Query the active model endpoint
just predict "Why is the sky blue?"
```

---

## 3. Repository Structure

```text
├── configs/
│   └── models.json               # Central Gemma catalog & hardware specifications
├── scripts/
│   ├── lib/
│   │   └── model_catalog.sh      # Catalog lookup helper library
│   ├── vertex_deploy.sh          # Model-aware Vertex AI deployer
│   ├── vertex_model_register.sh  # Model Registry uploader
│   ├── vertex_status.sh          # Deployment status & operation inspector
│   ├── vertex_undeploy.sh        # Endpoint undeployer
│   ├── cloudrun_deploy.sh        # Model-aware Cloud Run deployer
│   ├── cloudrun_quota_check.sh   # Quota checker
│   ├── cloudrun_status.sh        # Cloud Run status inspector
│   ├── model_list.sh             # Interactive catalog list
│   ├── cost_list.sh              # Terminal pricing matrix
│   ├── auth_check.sh             # Preflight credentials checker
│   └── predict.sh                # Smart inference test client
├── terraform/
│   ├── locals.tf                 # Reads configs/models.json via jsondecode()
│   ├── variables.tf              # Accepts var.model_flavor
│   ├── vertex.tf                 # Vertex AI endpoint resources
│   └── cloudrun.tf               # Cloud Run service resources
└── docs/
    ├── cost_analysis.md          # Hardware sizing & pricing breakdown
    ├── cloudrun_deploy.md        # Cloud Run deployment guide
    └── vertex_deployment_notes.md# Vertex AI deployment guide
```

---

## 4. Documentation Reference

* [Model Deployment Status & Matrix](docs/deployment_status.md)
* [Cost Analysis & Hardware Sizing](docs/cost_analysis.md)
* [Vertex AI Deployment Guide & Lessons Learned](docs/vertex_deployment_notes.md)
* [Cloud Run GPU Deployment Guide](docs/cloudrun_deploy.md)
* [Terraform Infrastructure Guide](terraform/README.md)
