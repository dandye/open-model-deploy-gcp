# Gemma Deployment on Google Cloud

Automated deployment scripts, Justfile recipes, and architectural guides for deploying Google Gemma models on Google Cloud Platform using Vertex AI Online Prediction and Cloud Run with GPU.

---

## 1. Overview & Deployment Modes

This repository provides two deployment architectures for Gemma models:

| Mode | Target Platform | Hardware Configuration | Billing Model | Scale-to-Zero |
| :--- | :--- | :--- | :--- | :--- |
| **Dedicated Endpoint** | **Vertex AI Prediction** | `g2-standard-24` (2x NVIDIA L4, 96GB RAM) | Hourly while deployed (~$1.68/hr) | Manual (`vertex-undeploy`) |
| **Serverless GPU** | **Cloud Run with GPU** | 1x NVIDIA L4, 8 vCPUs, 32GB RAM | Per-request seconds ($0 when idle) | Automatic (`min-instances=0`) |

---

## 2. Prerequisites & Setup

### Requirements
* Google Cloud SDK (`gcloud`) installed and authenticated
* `just` command runner
* Active Google Cloud project with billing enabled
* `terraform` (optional, for Infrastructure-as-Code workflows)

### Configuration
1. Copy the example environment configuration:
   ```bash
   cp .env.example .env
   ```
2. Edit `.env` to customize your project ID, model ID, or hardware parameters:
   ```bash
   GCP_PROJECT_ID="dandye-0324-chronicle"
   GCP_REGION="us-central1"
   HF_TOKEN="<YOUR_HUGGING_FACE_TOKEN>"  # Optional: for gated models
   ```

---

## 3. Quick Start Commands

All operations are managed through the `Justfile`:

```bash
# Display categorized, color-coded command menu
just
```

### Global & Dashboard
```bash
# Print unified live state dashboard of all Vertex AI and Cloud Run resources
just status
  just model-list              List Model Registry models & reference catalog
  just cost-list               Display hardware pricing & sizing table in terminal
  just predict "<prompt>"      Send a test query to active endpoint
```

### Vertex AI Online Prediction (Dedicated GPU VM)
```bash
# Deploy model to Vertex AI endpoint (g2-standard-24, 2x NVIDIA L4)
just vertex-deploy

# Check deployment progress and active operations
just vertex-status

# Undeploy model from Vertex AI endpoint (stops GPU billing immediately)
just vertex-undeploy
```

### Cloud Run (Serverless Scale-to-Zero)
```bash
# Check Cloud Run service status and active revisions
just cloudrun-status

# Verify Cloud Run NVIDIA L4 GPU quota in region
just cloudrun-quota-check

# Request Cloud Run NVIDIA L4 GPU quota increase (us-central1)
just cloudrun-quota-request

# Deploy to Cloud Run (automatically verifies quota first)
just cloudrun-deploy

# Reset / Tear down Cloud Run GPU quota preference back to 0
just cloudrun-quota-reset
```

### Terraform (Infrastructure as Code)
```bash
# Initialize Terraform working directory
just tf-init

# Plan Terraform infrastructure changes
just tf-plan

# Apply Terraform infrastructure changes
just tf-apply

# Destroy Terraform-managed infrastructure
just tf-destroy
```

---

## 4. Testing Endpoints

### Calling Cloud Run:
```bash
SERVICE_URL=$(gcloud run services describe gemma-cloudrun-service \
  --project="dandye-0324-chronicle" \
  --region="us-central1" \
  --format="value(status.url)")

curl "$SERVICE_URL/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "google/gemma-2-9b-it",
    "messages": [
      {"role": "user", "content": "Explain quantum computing in 2 sentences."}
    ]
  }'
```

---

## 5. Repository Structure

```text
├── .env.example                  # Environment configuration template
├── GEMINI.md                     # Agent guidance & architectural context
├── Justfile                      # Command runner recipes
├── README.md                     # Project documentation
├── docs/
│   ├── cloudrun_deploy.md        # Cloud Run deployment & quota guide
│   ├── cost_analysis.md          # Hardware sizing & pricing breakdown
│   ├── vertex_cleanup_strategies.md # Automated shutdown patterns
│   └── vertex_deployment_notes.md# Vertex AI deployment guide & solutions
├── scripts/
│   ├── cloudrun_deploy.sh        # Deploy to Cloud Run with GPU
│   ├── cloudrun_quota_check.sh   # Verify Cloud Run GPU quota
│   ├── cloudrun_quota_request.sh # Request Cloud Run GPU quota
│   ├── cloudrun_quota_reset.sh   # Reset Cloud Run GPU quota
│   ├── cloudrun_status.sh        # Check Cloud Run service status
│   ├── gcp_status.sh             # Unified live dashboard
│   ├── vertex_deploy.sh          # Deploy to Vertex AI endpoint
│   ├── vertex_status.sh          # Check Vertex AI deployment status
│   └── vertex_undeploy.sh        # Undeploy from Vertex AI endpoint
└── terraform/
    ├── README.md                 # Terraform usage guide
    ├── cloudrun.tf               # Cloud Run service & IAM resources
    ├── outputs.tf                # Endpoint & service output definitions
    ├── terraform.tfvars.example  # Example variable assignments
    ├── variables.tf              # Input variable declarations
    ├── versions.tf               # Terraform & provider requirements
    └── vertex.tf                 # Vertex AI endpoint resources
```

---

## 6. Documentation Reference

* [Cost Analysis & Hardware Sizing](docs/cost_analysis.md)
* [Vertex AI Deployment Guide & Lessons Learned](docs/vertex_deployment_notes.md)
* [Vertex AI Automated Cleanup Strategies](docs/vertex_cleanup_strategies.md)
* [Cloud Run GPU Deployment Guide](docs/cloudrun_deploy.md)
* [Terraform Infrastructure Guide](terraform/README.md)
