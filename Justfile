# ==============================================================================
# Justfile: Gemma Model Deployment & Quota Management
# ==============================================================================

# Default recipe: formatted and colorized help menu
default:
    @printf "\033[1;36m==============================================================================\033[0m\n"
    @printf " \033[1;37mGemma Model Deployment Manager\033[0m\n"
    @printf "\033[1;36m==============================================================================\033[0m\n\n"
    @printf "\033[1;33mUSAGE:\033[0m\n"
    @printf "  just <command>\n\n"
    @printf "\033[1;33mDISCOVERY & DASHBOARDS:\033[0m\n"
    @printf "  \033[1;32mjust status\033[0m                  \033[2mPrint unified live dashboard of all GCP resources\033[0m\n"
    @printf "  \033[1;32mjust model-list\033[0m              \033[2mList Model Registry models & reference catalog\033[0m\n"
    @printf "  \033[1;32mjust cost-list\033[0m               \033[2mDisplay hardware pricing & sizing table in terminal\033[0m\n"
    @printf "  \033[1;32mjust predict \"<prompt>\"\033[0m      \033[2mSend a test query to whichever endpoint is active\033[0m\n\n"
    @printf "\033[1;33mVERTEX AI ONLINE PREDICTION (Dedicated GPU VMs):\033[0m\n"
    @printf "  \033[1;32mjust vertex-deploy\033[0m           \033[2mDeploy Gemma to Vertex AI endpoint (2x NVIDIA L4)\033[0m\n"
    @printf "  \033[1;32mjust vertex-status\033[0m           \033[2mCheck deployment progress and active operations\033[0m\n"
    @printf "  \033[1;32mjust vertex-undeploy\033[0m         \033[2mUndeploy model from endpoint (stops GPU billing)\033[0m\n\n"
    @printf "\033[1;33mCLOUD RUN WITH GPU (Serverless Scale-to-Zero):\033[0m\n"
    @printf "  \033[1;32mjust cloudrun-deploy\033[0m         \033[2mDeploy Gemma with scale-to-zero (checks quota first)\033[0m\n"
    @printf "  \033[1;32mjust cloudrun-status\033[0m         \033[2mCheck Cloud Run service status and active revisions\033[0m\n"
    @printf "  \033[1;32mjust cloudrun-quota-check\033[0m    \033[2mVerify Cloud Run NVIDIA L4 GPU quota in region\033[0m\n"
    @printf "  \033[1;32mjust cloudrun-quota-request\033[0m  \033[2mRequest Cloud Run NVIDIA L4 GPU quota increase\033[0m\n"
    @printf "  \033[1;32mjust cloudrun-quota-reset\033[0m    \033[2mReset Cloud Run GPU quota preference back to 0\033[0m\n\n"
    @printf "\033[1;33mTERRAFORM (Infrastructure as Code):\033[0m\n"
    @printf "  \033[1;32mjust tf-init\033[0m                 \033[2mInitialize Terraform working directory\033[0m\n"
    @printf "  \033[1;32mjust tf-plan\033[0m                 \033[2mPlan Terraform infrastructure changes\033[0m\n"
    @printf "  \033[1;32mjust tf-apply\033[0m                \033[2mApply Terraform infrastructure changes\033[0m\n"
    @printf "  \033[1;32mjust tf-destroy\033[0m              \033[2mDestroy Terraform-managed infrastructure\033[0m\n\n"
    @printf "\033[1;36m==============================================================================\033[0m\n"

# ------------------------------------------------------------------------------
# Discovery, State & Testing
# ------------------------------------------------------------------------------

# Print unified live state dashboard of all Vertex AI and Cloud Run resources
status:
    @./scripts/gcp_status.sh

# List registered models in Model Registry and reference hardware sizing catalog
model-list:
    @./scripts/model_list.sh

# Display infrastructure cost and sizing matrix in terminal
cost-list:
    @./scripts/cost_list.sh

# Query active endpoint with a test prompt (Usage: just predict "your prompt")
predict PROMPT="Hello Gemma! Explain quantum computing in two sentences.":
    @./scripts/predict.sh "{{PROMPT}}"

# ------------------------------------------------------------------------------
# Vertex AI Endpoints (Dedicated GPU VMs)
# ------------------------------------------------------------------------------

# Deploy Gemma to a Vertex AI Endpoint (g2-standard-24, 2x NVIDIA L4)
vertex-deploy:
    @./scripts/vertex_deploy.sh

# Check Vertex AI endpoint deployment status and active operations
vertex-status:
    @./scripts/vertex_status.sh

# Undeploy Gemma from Vertex AI Endpoint (stops GPU billing immediately)
vertex-undeploy:
    @./scripts/vertex_undeploy.sh

# ------------------------------------------------------------------------------
# Cloud Run (Serverless GPU Scale-to-Zero)
# ------------------------------------------------------------------------------

# Check Cloud Run service status and active revisions
cloudrun-status:
    @./scripts/cloudrun_status.sh

# Check if Cloud Run NVIDIA L4 GPU quota is active in us-central1
cloudrun-quota-check:
    @./scripts/cloudrun_quota_check.sh

# Request Cloud Run NVIDIA L4 GPU quota increase (us-central1)
cloudrun-quota-request:
    @./scripts/cloudrun_quota_request.sh

# Reset / Tear down Cloud Run GPU quota preference back to 0
cloudrun-quota-reset:
    @./scripts/cloudrun_quota_reset.sh

# Deploy Gemma to Cloud Run with 1x NVIDIA L4 (checks quota first)
cloudrun-deploy: cloudrun-quota-check
    @./scripts/cloudrun_deploy.sh

# ------------------------------------------------------------------------------
# Terraform Infrastructure as Code
# ------------------------------------------------------------------------------

# Initialize Terraform working directory
tf-init:
    @cd terraform && terraform init

# Plan Terraform infrastructure changes
tf-plan:
    @cd terraform && terraform plan

# Apply Terraform infrastructure changes
tf-apply:
    @cd terraform && terraform apply

# Destroy Terraform-managed infrastructure
tf-destroy:
    @cd terraform && terraform destroy
