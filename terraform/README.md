# Gemma Deployment via Terraform

This directory provides Terraform (Infrastructure-as-Code) configurations to provision Gemma serving infrastructure on Google Cloud Platform.

---

## 1. Resources Managed

* **Vertex AI Endpoint** (`google_vertex_ai_endpoint`): Creates the dedicated online prediction endpoint resource.
* **Cloud Run with GPU Service** (`google_cloud_run_v2_service`): Deploys the vLLM OpenAI-compatible server on a 1x NVIDIA L4 GPU with `--min-instances=0` (scale-to-zero).
* **IAM Invocations** (`google_cloud_run_v2_service_iam_member`): Configures public/authenticated access policies.

---

## 2. Usage

### Initialize Terraform
```bash
cd terraform
terraform init
```

### Configure Variables
```bash
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your project ID and settings
```

### Plan and Apply
```bash
terraform plan
terraform apply
```

### Teardown
```bash
terraform destroy
```

---

## 3. Via Justfile

From the workspace root:

```bash
just tf-init
just tf-plan
just tf-apply
just tf-destroy
```
