# ==============================================================================
# Justfile: Gemma Model Deployment & Quota Management
# ==============================================================================

# Default recipe: list available commands
default:
    @just --list

# Print unified live state dashboard of all Vertex AI and Cloud Run resources
status:
    @./scripts/gcp_status.sh

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
