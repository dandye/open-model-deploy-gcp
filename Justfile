# ==============================================================================
# Justfile: Gemma Model Deployment & Quota Management
# ==============================================================================

# Default recipe: formatted and colorized help menu
default:
    @printf "\033[1;36m==============================================================================\033[0m\n"
    @printf " \033[1;37mGemma Multi-Model Deployment Manager\033[0m\n"
    @printf "\033[1;36m==============================================================================\033[0m\n\n"
    @printf "\033[1;33mUSAGE:\033[0m\n"
    @printf "  just <command> [model_flavor]\n\n"
    @printf "\033[1;33mDISCOVERY, CATALOG & DASHBOARDS:\033[0m\n"
    @printf "  \033[1;32mjust status\033[0m                            \033[2mPrint unified live dashboard of all GCP resources\033[0m\n"
    @printf "  \033[1;32mjust auth-check\033[0m                        \033[2mVerify gcloud account, project, and ADC validity\033[0m\n"
    @printf "  \033[1;32mjust model-list\033[0m                        \033[2mList models in catalog (configs/models.json) & registry\033[0m\n"
    @printf "  \033[1;32mjust cost-list\033[0m                         \033[2mDisplay pricing and compute requirements table\033[0m\n"
    @printf "  \033[1;32mjust predict \"<prompt>\" [model]\033[0m        \033[2mSend a test query to active endpoint\033[0m\n\n"
    @printf "\033[1;33mVERTEX AI ONLINE PREDICTION (Dedicated GPU VMs):\033[0m\n"
    @printf "  \033[1;32mjust vertex-register [flavor]\033[0m          \033[2mRegister model in Vertex AI Model Registry\033[0m\n"
    @printf "  \033[1;32mjust vertex-deploy [flavor]\033[0m            \033[2mDeploy model to Vertex AI endpoint (auto-sizes compute)\033[0m\n"
    @printf "  \033[1;32mjust vertex-status\033[0m                     \033[2mCheck deployment progress and active operations\033[0m\n"
    @printf "  \033[1;32mjust vertex-undeploy\033[0m                   \033[2mUndeploy model from endpoint (stops GPU billing)\033[0m\n\n"
    @printf "\033[1;33mCLOUD RUN WITH GPU (Serverless Scale-to-Zero):\033[0m\n"
    @printf "  \033[1;32mjust cloudrun-deploy [flavor]\033[0m          \033[2mDeploy single-GPU model with scale-to-zero\033[0m\n"
    @printf "  \033[1;32mjust cloudrun-status\033[0m                   \033[2mCheck Cloud Run service status and active revisions\033[0m\n"
    @printf "  \033[1;32mjust cloudrun-quota-check\033[0m              \033[2mVerify Cloud Run NVIDIA L4 GPU quota in region\033[0m\n"
    @printf "  \033[1;32mjust cloudrun-quota-request\033[0m            \033[2mRequest Cloud Run NVIDIA L4 GPU quota increase\033[0m\n"
    @printf "  \033[1;32mjust cloudrun-quota-reset\033[0m              \033[2mReset Cloud Run GPU quota preference back to 0\033[0m\n\n"
    @printf "\033[1;33mTERRAFORM (Infrastructure as Code):\033[0m\n"
    @printf "  \033[1;32mjust tf-init\033[0m                           \033[2mInitialize Terraform working directory\033[0m\n"
    @printf "  \033[1;32mjust tf-plan [flavor]\033[0m                  \033[2mPlan Terraform infrastructure for model flavor\033[0m\n"
    @printf "  \033[1;32mjust tf-apply [flavor]\033[0m                 \033[2mApply Terraform infrastructure for model flavor\033[0m\n"
    @printf "  \033[1;32mjust tf-destroy\033[0m                        \033[2mDestroy Terraform-managed infrastructure\033[0m\n\n"
    @printf "\033[1;33mVERTEX AI AGENT ENGINE (ADK & SOC AGENT):\033[0m\n"
    @printf "  \033[1;32mjust agent-test [prompt]\033[0m               \033[2mTest general Gemma ADK Agent locally\033[0m\n"
    @printf "  \033[1;32mjust agent-deploy\033[0m                      \033[2mDeploy general Gemma ADK Agent to Agent Engine\033[0m\n"
    @printf "  \033[1;32mjust agent-soc-test [prompt] [flavor]\033[0m  \033[2mTest SOC Tier 1 Agent locally against endpoint\033[0m\n"
    @printf "  \033[1;32mjust agent-soc-eval [flavor] [endpoint]\033[0m \033[2mRun automated SOC eval suite with LLM judge\033[0m\n"
    @printf "  \033[1;32mjust agent-soc-deploy\033[0m                  \033[2mDeploy SOC Tier 1 Agent to Agent Engine\033[0m\n\n"
    @printf "\033[1;36m==============================================================================\033[0m\n"

# ------------------------------------------------------------------------------
# Discovery, State & Testing
# ------------------------------------------------------------------------------

# Print unified live state dashboard of all Vertex AI and Cloud Run resources
status:
    @./scripts/gcp_status.sh

# Verify gcloud account, project configuration, and Application Default Credentials (ADC)
auth-check:
    @./scripts/auth_check.sh

# List registered models in Model Registry and reference hardware sizing catalog
model-list:
    @./scripts/model_list.sh

# Display infrastructure cost and sizing matrix in terminal
cost-list:
    @./scripts/cost_list.sh

# Query active endpoint with a test prompt (Usage: just predict "prompt" [model_flavor])
predict PROMPT="Hello Gemma! Explain quantum computing in two sentences." MODEL="":
    @./scripts/predict.sh "{{PROMPT}}" "{{MODEL}}"

# ------------------------------------------------------------------------------
# Vertex AI Endpoints (Dedicated GPU VMs)
# ------------------------------------------------------------------------------

# Register a Gemma model in Vertex AI Model Registry (Usage: just vertex-register [flavor])
vertex-register FLAVOR="gemma-2-9b-it":
    @./scripts/vertex_model_register.sh "{{FLAVOR}}"

# Deploy Gemma to a Vertex AI Endpoint (Usage: just vertex-deploy [flavor])
vertex-deploy FLAVOR="gemma-2-9b-it" REGION="": auth-check
    @./scripts/vertex_deploy.sh "{{FLAVOR}}" "{{REGION}}"

# Check Vertex AI endpoint deployment status and active operations
vertex-status:
    @./scripts/vertex_status.sh

# Undeploy Gemma from Vertex AI Endpoint (stops GPU billing immediately)
vertex-undeploy:
    @./scripts/vertex_undeploy.sh

# Request Compute / Vertex AI NVIDIA A100 80GB GPU quota increase (Usage: just vertex-quota-request-a100 [region] [count])
vertex-quota-request-a100 REGION="us-central1" COUNT="1":
    @./scripts/a100_quota_request.sh "{{REGION}}" "{{COUNT}}"

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

# Deploy Gemma to Cloud Run with scale-to-zero (Usage: just cloudrun-deploy [flavor])
cloudrun-deploy FLAVOR="gemma-2-9b-it": auth-check cloudrun-quota-check
    @./scripts/cloudrun_deploy.sh "{{FLAVOR}}"

# ------------------------------------------------------------------------------
# Terraform Infrastructure as Code
# ------------------------------------------------------------------------------

# Initialize Terraform working directory
tf-init:
    @cd terraform && terraform init

# Plan Terraform infrastructure changes for specific model flavor
tf-plan FLAVOR="gemma-2-9b-it":
    @cd terraform && terraform plan -var="model_flavor={{FLAVOR}}"

# Apply Terraform infrastructure changes for specific model flavor
tf-apply FLAVOR="gemma-2-9b-it":
    @cd terraform && terraform apply -var="model_flavor={{FLAVOR}}" -auto-approve

# Destroy Terraform-managed infrastructure
tf-destroy:
    @cd terraform && terraform destroy

# ------------------------------------------------------------------------------
# Vertex AI Agent Engine (ADK Agent & SOC Triage)
# ------------------------------------------------------------------------------

# Test Gemma ADK Agent locally (Usage: just agent-test [prompt])
agent-test PROMPT="Explain quantum computing in two concise sentences.":
    @uv run python3 agent/test_agent.py "{{PROMPT}}"

# Deploy Gemma ADK Agent to Vertex AI Agent Engine
agent-deploy:
    @uv run python3 agent/deploy.py

# Test SOC Tier 1 Agent locally against active Gemma endpoint or SecOps MCP (Usage: just agent-soc-test [prompt] [live_mcp])
agent-soc-test PROMPT="Triage alert for IP 192.0.2.100" LIVE_MCP="false":
    @uv run python3 -m agent.test_agent "{{PROMPT}}" --soc {{if LIVE_MCP == "true" { "--live-mcp" } else { "" }}}

# Run automated SOC evaluation suite with LLM judge against target Gemma flavor (Usage: just agent-soc-eval [flavor] [endpoint] [live_mcp])
agent-soc-eval FLAVOR="gemma-3-4b-it" ENDPOINT="" LIVE_MCP="false":
    @uv run python3 -m scripts.eval_soc_agent --flavor "{{FLAVOR}}" {{if ENDPOINT != "" { "--endpoint " + ENDPOINT } else { "" }}} {{if LIVE_MCP == "true" { "--live-mcp" } else { "" }}} --output-report "docs/soc_eval_results/{{FLAVOR}}_report.md"


# Deploy SOC Tier 1 Agent to Vertex AI Agent Engine with Live Google SecOps Remote MCP
agent-soc-deploy LIVE_MCP="true":
    @USE_LIVE_MCP="{{LIVE_MCP}}" uv run python3 -m agent.deploy_soc_tier1



