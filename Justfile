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
    @printf "  \033[1;32mjust env [secops|argolis]\033[0m              \033[2mSwitch active .env profile between projects\033[0m\n"
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
    @printf "  \033[1;32mjust tf-plan [flavor] [flags]\033[0m          \033[2mPlan Terraform infrastructure for model flavor\033[0m\n"
    @printf "  \033[1;32mjust tf-apply [flavor] [flags]\033[0m         \033[2mApply Terraform infrastructure for model flavor\033[0m\n"
    @printf "  \033[1;32mjust tf-destroy\033[0m                        \033[2mDestroy Terraform-managed infrastructure\033[0m\n\n"
    @printf "\033[1;33mVERTEX AI AGENT ENGINE (ADK & SOC AGENT):\033[0m\n"
    @printf "  \033[1;32mjust agent-test [prompt]\033[0m               \033[2mTest general Gemma ADK Agent locally\033[0m\n"
    @printf "  \033[1;32mjust agent-deploy\033[0m                      \033[2mDeploy general Gemma ADK Agent to Agent Engine\033[0m\n"
    @printf "  \033[1;32mjust agent-soc-test [prompt] [flavor]\033[0m  \033[2mTest SOC Tier 1 Agent locally against endpoint\033[0m\n"
    @printf "  \033[1;32mjust agent-soc-eval [flavor] [gen]\033[0m     \033[2mRun automated SOC eval suite (default Gen 3)\033[0m\n"
    @printf "  \033[1;32mjust eval-gen3 [flavor] [endpoint]\033[0m     \033[2mRun Gen 3 interactive eval with SDT & loss metrics\033[0m\n"
    @printf "  \033[1;32mjust eval-gen3-live [flavor] [project]\033[0m \033[2mRun Gen 3 live interactive eval with SecOps MCP\033[0m\n"
    @printf "  \033[1;32mjust gepa-evolve [max_calls] [task_lm]\033[0m \033[2mEvolve SOC runbooks via GEPA Pareto optimization\033[0m\n"
    @printf "  \033[1;32mjust gepa-compare [task_lm]\033[0m             \033[2mEvaluate SOC agent with GEPA-evolved runbooks\033[0m\n"
    @printf "  \033[1;32mjust agent-soc-deploy\033[0m                  \033[2mDeploy SOC Tier 1 Agent to Agent Engine\033[0m\n\n"
    @printf "\033[1;33mVERTEX AI CUSTOM JOBS (Ephemeral Benchmarks & \$0 Idle):\033[0m\n"
    @printf "  \033[1;32mjust custom-job-build [tag]\033[0m             \033[2mBuild & push runner Docker image to Artifact Registry\033[0m\n"
    @printf "  \033[1;32mjust custom-job-run [flavor] [dry_run]\033[0m  \033[2mSubmit single model evaluation CustomJob\033[0m\n"
    @printf "  \033[1;32mjust custom-job-sweep [models] [dry_run]\033[0m\033[2mExecute model evaluation CustomJob sweep\033[0m\n"
    @printf "  \033[1;32mjust custom-job-status\033[0m                  \033[2mList recent CustomJobs in active region\033[0m\n\n"
    @printf "\033[1;33mMASTER OVERNIGHT EVALUATION & BENCHMARK SWEEP:\033[0m\n"
    @printf "  \033[1;32mjust overnight-sweep [models] [dry_run]\033[0m \033[2mRun overnight benchmark & SOC eval sweep with logging\033[0m\n\n"
    @printf "\033[1;33mCOMPUTE ENGINE SPOT GPU VMS (Cost-Optimized Benchmarks):\033[0m\n"
    @printf "  \033[1;32mjust gce-spot-run [flavor] [dry_run]\033[0m   \033[2mRun single model benchmark on ephemeral Spot VM\033[0m\n"
    @printf "  \033[1;32mjust gce-spot-sweep [models] [dry_run]\033[0m \033[2mRun full or filtered benchmark sweep across Spot VMs\033[0m\n"
    @printf "  \033[1;32mjust gce-spot-status [zone]\033[0m            \033[2mList active GCE Spot GPU instances\033[0m\n"
    @printf "  \033[1;32mjust gce-spot-cleanup [zone]\033[0m           \033[2mDelete lingering Spot benchmark VMs\033[0m\n\n"
    @printf "\033[1;33mGKE RAY SERVE & KUEUE (Distributed Batch Benchmarks):\033[0m\n"
    @printf "  \033[1;32mjust gke-ray-init [cluster] [region]\033[0m   \033[2mInitialize Kueue queues & Ray operator on GKE\033[0m\n"
    @printf "  \033[1;32mjust gke-ray-run [flavor] [dry_run]\033[0m    \033[2mRun single model benchmark on GKE RayCluster\033[0m\n"
    @printf "  \033[1;32mjust gke-ray-sweep [models] [dry_run]\033[0m  \033[2mRun full or filtered benchmark sweep on GKE\033[0m\n"
    @printf "  \033[1;32mjust gke-ray-status [namespace]\033[0m        \033[2mQuery active RayClusters, Jobs & LocalQueues\033[0m\n"
    @printf "  \033[1;32mjust gke-ray-cleanup [namespace]\033[0m       \033[2mDelete Ray workloads to release GPU node pools\033[0m\n\n"
    @printf "\033[1;33mGEN 5 FAMILY-INSTANCED SOC EVALS (configs/evals/gen5):\033[0m\n"
    @printf "  \033[1;32mjust gen5-build\033[0m                        \033[2mBuild bundles and manifest from the family templates\033[0m\n"
    @printf "  \033[1;32mjust gen5-check\033[0m                        \033[2mLockfile check plus schema and suite tests\033[0m\n"
    @printf "  \033[1;32mjust gen5-calibrate [trials]\033[0m           \033[2mFour reference policies, gates, GEN5_CALIBRATION.md\033[0m\n"
    @printf "  \033[1;32mjust harbor-soc-gen5-generate [arms]\033[0m  \033[2mGenerate the Gen 5 Harbor tree (validation + final_test)\033[0m\n"
    @printf "  \033[1;32mjust harbor-soc-gen5-check\033[0m           \033[2mFail on drift between the generator and evals/harbor_soc_gen5\033[0m\n"
    @printf "  \033[1;32mjust harbor-soc-gen5-test\033[0m            \033[2mGen 5 Harbor layout, isolation, and container oracle tests\033[0m\n"
    @printf "  \033[1;32mjust eval-gen5 [flavor] [split]\033[0m        \033[2mRun the Gen 5 suite on a split through the exposure ledger\033[0m\n"
    @printf "  \033[1;32mjust gen5-noise [k] [task_lm]\033[0m          \033[2mMeasurement gate 1: K-run seed noise floor on validation\033[0m\n"
    @printf "  \033[1;32mjust gen5-gradient [flavor] [endpoint]\033[0m \033[2mMeasurement gate 4: one capability rung on validation\033[0m\n"
    @printf "  \033[1;32mjust harness-approve\033[0m                   \033[2mRe-approve .eval_harness_lock.json after intended changes\033[0m\n"
    @printf "  \033[1;32mjust harness-verify\033[0m                    \033[2mVerify protected scoring and Gen 5 inputs against the lock\033[0m\n\n"
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

# Switch active .env symlink (Usage: just env [secops|argolis])
env TARGET="secops":
    @if [ "{{TARGET}}" = "secops" ] || [ "{{TARGET}}" = "secops-demo-env" ]; then \
        ln -sf .env.secops-demo-env .env && echo "[OK] Active environment switched to .env.secops-demo-env (secops-demo-env)"; \
    elif [ "{{TARGET}}" = "argolis" ] || [ "{{TARGET}}" = "dandye-0324-chronicle" ]; then \
        ln -sf .env.argolis .env && echo "[OK] Active environment switched to .env.argolis (dandye-0324-chronicle)"; \
    else \
        echo "[ERROR] Unknown target '{{TARGET}}'. Use 'secops' or 'argolis'."; exit 1; \
    fi

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

# Deploy Hugging Face / Model Garden OpenModel via Vertex AI SDK (Usage: just openmodel-deploy [flavor] [dry_run])
openmodel-deploy FLAVOR="qwen3.8-27b" DRY_RUN="false": auth-check
    @uv run python3 scripts/deploy_open_model.py --flavor "{{FLAVOR}}" {{if DRY_RUN == "true" { "--dry-run" } else { "" }}}

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

# Run automated overnight benchmark & SOC evaluation sweep across Cloud Run single-GPU models
cloudrun-sweep MODELS="" DRY_RUN="false": auth-check
    @python3 scripts/run_cloudrun_sweep.py {{if MODELS != "" { "--models " + MODELS } else { "" }}} {{if DRY_RUN == "true" { "--dry-run" } else { "" }}}


# ------------------------------------------------------------------------------
# Terraform Infrastructure as Code
# ------------------------------------------------------------------------------

# Initialize Terraform working directory
tf-init:
    @cd terraform && terraform init

# Plan Terraform infrastructure changes for specific model flavor (Usage: just tf-plan [flavor] [flags])
tf-plan FLAVOR="gemma-2-9b-it" FLAGS="":
    @cd terraform && terraform plan -var="model_flavor={{FLAVOR}}" {{if FLAGS != "" { "-var=\"extra_vllm_flags=" + FLAGS + "\"" } else { "" }}}

# Apply Terraform infrastructure changes for specific model flavor (Usage: just tf-apply [flavor] [flags])
tf-apply FLAVOR="gemma-2-9b-it" FLAGS="":
    @cd terraform && terraform apply -var="model_flavor={{FLAVOR}}" {{if FLAGS != "" { "-var=\"extra_vllm_flags=" + FLAGS + "\"" } else { "" }}} -auto-approve

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

# Run automated SOC evaluation suite with LLM judge against target Gemma flavor (Usage: just agent-soc-eval [flavor] [gen] [endpoint] [live_mcp])
agent-soc-eval FLAVOR="gemma-3-4b-it" GEN="3" ENDPOINT="" LIVE_MCP="false":
    @uv run python3 -m scripts.eval_soc_agent --flavor "{{FLAVOR}}" --gen {{GEN}} {{if ENDPOINT != "" { "--endpoint " + ENDPOINT } else { "" }}} {{if LIVE_MCP == "true" { "--live-mcp" } else { "" }}} --output-report "docs/soc_eval_results/gen{{GEN}}_{{FLAVOR}}_report.md"

# Run automated SOC evaluation suite against target Llama flavor (Usage: just eval-llama [flavor] [gen] [live_mcp])
eval-llama FLAVOR="llama-4-maverick-17b-128e-instruct-maas" GEN="3" LIVE_MCP="false":
    @uv run python3 -m scripts.eval_soc_agent --flavor "{{FLAVOR}}" --gen {{GEN}} {{if LIVE_MCP == "true" { "--live-mcp" } else { "" }}} --output-report "docs/soc_eval_results/gen{{GEN}}_{{FLAVOR}}_report.md"

# Run live evaluation suite against Google SecOps Remote MCP (Usage: just eval-live [flavor] [gen] [project] [customer_id])
eval-live FLAVOR="gemini-2.5-flash" GEN="3" PROJECT="secops-demo-env" CUSTOMER_ID="a13f6726-efed-452e-9008-8fe0d3cb0f75": auth-check
    @uv run python3 -m scripts.eval_soc_agent --flavor "{{FLAVOR}}" --gen {{GEN}} --use-live-mcp --chronicle-project "{{PROJECT}}" --chronicle-customer-id "{{CUSTOMER_ID}}" --output-report "docs/soc_eval_results/gen{{GEN}}_live_{{FLAVOR}}_report.md"

# Run live evaluation suite against target Llama flavor with Google SecOps Remote MCP
eval-live-llama FLAVOR="llama-4-maverick-17b-128e-instruct-maas" GEN="3" PROJECT="secops-demo-env" CUSTOMER_ID="a13f6726-efed-452e-9008-8fe0d3cb0f75": auth-check
    @uv run python3 -m scripts.eval_soc_agent --flavor "{{FLAVOR}}" --gen {{GEN}} --use-live-mcp --chronicle-project "{{PROJECT}}" --chronicle-customer-id "{{CUSTOMER_ID}}" --output-report "docs/soc_eval_results/gen{{GEN}}_live_{{FLAVOR}}_report.md"

# Run Gen 3 interactive SOC evaluation suite (Convenience shortcut for agent-soc-eval GEN=3)
eval-gen3 FLAVOR="gemma-3-4b-it" ENDPOINT="" LIVE_MCP="false":
    @uv run python3 -m scripts.eval_soc_agent --flavor "{{FLAVOR}}" --gen 3 {{if ENDPOINT != "" { "--endpoint " + ENDPOINT } else { "" }}} {{if LIVE_MCP == "true" { "--live-mcp" } else { "" }}} --output-report "docs/soc_eval_results/gen3_{{FLAVOR}}_report.md"

# Run Gen 3 live interactive evaluation suite against Google SecOps Remote MCP
eval-gen3-live FLAVOR="gemini-2.5-flash" PROJECT="secops-demo-env" CUSTOMER_ID="a13f6726-efed-452e-9008-8fe0d3cb0f75": auth-check
    @uv run python3 -m scripts.eval_soc_agent --flavor "{{FLAVOR}}" --gen 3 --use-live-mcp --chronicle-project "{{PROJECT}}" --chronicle-customer-id "{{CUSTOMER_ID}}" --output-report "docs/soc_eval_results/gen3_live_{{FLAVOR}}_report.md"

# Run Gen 3 SOC evaluation with GEPA tool descriptions from gusto-mcp-gepa (Usage: just eval-gepa [flavor] [gen])
eval-gepa FLAVOR="gemini-2.5-flash" GEN="3": auth-check
    @uv run python3 -m scripts.eval_soc_agent --flavor "{{FLAVOR}}" --gen {{GEN}} --mcp-provider gepa --output-report "docs/soc_eval_results/gen{{GEN}}_gepa_{{FLAVOR}}_report.md"

# Compare baseline default vs gusto-mcp-gepa on Gen 3 evaluation suite (Usage: just eval-compare-gepa [flavor])
eval-compare-gepa FLAVOR="gemini-2.5-flash": auth-check
    @echo "=== Running Baseline (Default MCP) ==="
    @uv run python3 -m scripts.eval_soc_agent --flavor "{{FLAVOR}}" --gen 3 --mcp-provider default --output-report "docs/soc_eval_results/gen3_baseline_{{FLAVOR}}_report.md"
    @echo "=== Running GEPA MCP (gusto-mcp-gepa) ==="
    @uv run python3 -m scripts.eval_soc_agent --flavor "{{FLAVOR}}" --gen 3 --mcp-provider gepa --output-report "docs/soc_eval_results/gen3_gepa_{{FLAVOR}}_report.md"

# Deploy SOC Tier 1 Agent to Vertex AI Agent Engine with Live Google SecOps Remote MCP
agent-soc-deploy LIVE_MCP="true":
    @USE_LIVE_MCP="{{LIVE_MCP}}" uv run python3 -m agent.deploy_soc_tier1

# Evolve SOC runbooks with GEPA on the Gen 5 splits (train for reflection, validation for selection) through the exposure ledger
gepa-evolve MAX_CALLS="15" TASK_LM="gemini-2.5-flash-lite" REFLECTION_LM="gemini-2.5-pro":
    @uv run python3 agent/gepa_runbook_optimizer.py --max-metric-calls {{MAX_CALLS}} --task-lm "{{TASK_LM}}" --reflection-lm "{{REFLECTION_LM}}" --output-dir configs/runbooks/gepa_evolved

# Compare and evaluate SOC agent against evalset using evolved runbooks
gepa-compare TASK_LM="gemini-2.5-flash-lite":
    @uv run python3 -m scripts.eval_soc_agent --flavor "{{TASK_LM}}" --managed-model "{{TASK_LM}}" --gen 3 --agent-mode hierarchical --use-runbooks --runbooks-dir configs/runbooks/gepa_evolved --evalset configs/evals/gen3/soc_tier1_interactive.json --output-report "docs/soc_eval_results/{{TASK_LM}}_gepa_evolved_report.md" --output-json "docs/soc_eval_results/{{TASK_LM}}_gepa_evolved_report.json"

# Run SOC Agent evaluation with Jev System-One judge
eval-soc-jev flavor="gemini-2.5-flash-lite" gen="3":
    @uv run python3 -m scripts.eval_soc_agent --flavor "{{flavor}}" --gen {{gen}} --judge-backend jev --output-report "docs/soc_eval_results/gen{{gen}}_jev_{{flavor}}_report.md"

# Run SOC Agent evaluation with Side-by-Side (SxS) Jev vs Gemini 2.5 Pro judges
eval-soc-sxs-judge flavor="gemini-2.5-flash-lite" gen="3":
    @uv run python3 -m scripts.eval_soc_agent --flavor "{{flavor}}" --gen {{gen}} --judge-backend jev --sxs-judge --output-report "docs/soc_eval_results/gen{{gen}}_sxs_{{flavor}}_report.md"

# ------------------------------------------------------------------------------
# Master Overnight Evaluation & Benchmark Sweep
# ------------------------------------------------------------------------------

# Run automated evaluation sweep across new partner & OpenModels (Usage: just sweep-new [models...])
sweep-new *MODELS: auth-check
    @uv run python3 scripts/overnight_model_sweep.py {{if MODELS == "" { "" } else { "--models " + MODELS }}}

# Run master overnight comprehensive model evaluation & benchmark sweep (Usage: just overnight-sweep [models] [dry_run])
overnight-sweep MODELS="" DRY_RUN="false":
    @mkdir -p logs
    @LOGFILE="logs/overnight_sweep_$(date +%Y%m%d_%H%M%S).log"; \
    echo "Starting overnight sweep. Logging to $LOGFILE"; \
    uv run python3 scripts/run_overnight_sweep.py {{if MODELS != "" { "--models " + MODELS } else { "" }}} {{if DRY_RUN == "true" { "--dry-run" } else { "" }}} 2>&1 | tee "$LOGFILE"

# Run complete end-to-end sweep: Gemma models followed immediately by partner & OpenModels
overnight-full-sweep: auth-check
    @mkdir -p logs
    @LOGFILE="logs/overnight_full_sweep_$(date +%Y%m%d_%H%M%S).log"; \
    echo "Starting full overnight sweep (Gemma + Non-Gemma OpenModels). Logging to $LOGFILE"; \
    uv run python3 scripts/run_overnight_sweep.py 2>&1 | tee "$LOGFILE"; \
    echo "Gemma sweep complete. Starting Non-Gemma Partner & OpenModels sweep..." | tee -a "$LOGFILE"; \
    uv run python3 scripts/overnight_model_sweep.py 2>&1 | tee -a "$LOGFILE"; \
    uv run python3 scripts/run_overnight_sweep.py --rebuild-scorecard | tee -a "$LOGFILE"

# ------------------------------------------------------------------------------
# Compute Engine Spot GPU VMs (Cost-Optimized Ephemeral Benchmarks)
# ------------------------------------------------------------------------------

# Run a single model benchmark on an ephemeral Spot VM (Usage: just gce-spot-run [flavor] [dry_run])
gce-spot-run FLAVOR="gemma-3-4b-it" DRY_RUN="false": auth-check
    @uv run python3 scripts/run_gce_spot_sweep.py --models "{{FLAVOR}}" {{if DRY_RUN == "true" { "--dry-run" } else { "" }}}

# Run a full or filtered benchmark sweep across Spot VMs (Usage: just gce-spot-sweep [models] [dry_run])
gce-spot-sweep MODELS="" DRY_RUN="false": auth-check
    @uv run python3 scripts/run_gce_spot_sweep.py {{if MODELS != "" { "--models " + MODELS } else { "" }}} {{if DRY_RUN == "true" { "--dry-run" } else { "" }}}

# List active GCE Spot GPU instances (Usage: just gce-spot-status [zone])
gce-spot-status ZONE="":
    @ZONE_FLAG="{{if ZONE != "" { "--zone=" + ZONE } else { "" }}}"; \
    gcloud compute instances list --filter="scheduling.provisioningModel=SPOT" $$ZONE_FLAG

# Forcefully delete any lingering Spot benchmark VMs (Usage: just gce-spot-cleanup [zone])
gce-spot-cleanup ZONE="":
    @ZONE_FLAG="{{if ZONE != "" { "--zone=" + ZONE } else { "" }}}"; \
    INSTANCES=$$(gcloud compute instances list --filter="name:(spot-* OR gemma-spot-*)" --format="value(name)" $$ZONE_FLAG); \
    if [ -n "$$INSTANCES" ]; then \
        echo "Deleting lingering GCE Spot benchmark instances:"; \
        echo "$$INSTANCES"; \
        gcloud compute instances delete $$INSTANCES $$ZONE_FLAG --quiet; \
    else \
        echo "No lingering GCE Spot benchmark instances found."; \
    fi

# ------------------------------------------------------------------------------
# Vertex AI Custom Jobs (Ephemeral Compute & Guaranteed $0 Idle)
# ------------------------------------------------------------------------------

# Build and push benchmark runner container image to Artifact Registry (Usage: just custom-job-build [tag] [region])
custom-job-build TAG="latest" REGION="us-central1": auth-check
    @PROJECT_ID="$(gcloud config get-value project 2>/dev/null || echo 'dandye-0324-chronicle')"; \
    IMAGE_URI="{{REGION}}-docker.pkg.dev/${PROJECT_ID}/gemma-benchmarks/runner:{{TAG}}"; \
    echo "Building runner image ${IMAGE_URI}..."; \
    docker build -f docker/Dockerfile.custom_job -t "${IMAGE_URI}" . && \
    echo "Pushing runner image ${IMAGE_URI}..."; \
    docker push "${IMAGE_URI}"

# Submit single model evaluation CustomJob on Vertex AI (Usage: just custom-job-run [flavor] [dry_run])
custom-job-run FLAVOR="gemma-3-4b-it" DRY_RUN="false": auth-check
    @uv run python3 scripts/run_vertex_custom_job_sweep.py --models "{{FLAVOR}}" {{if DRY_RUN == "true" { "--dry-run" } else { "" }}}

# Execute CustomJob evaluation sweep across models (Usage: just custom-job-sweep [models] [dry_run])
custom-job-sweep MODELS="" DRY_RUN="false": auth-check
    @uv run python3 scripts/run_vertex_custom_job_sweep.py {{if MODELS != "" { "--models " + MODELS } else { "" }}} {{if DRY_RUN == "true" { "--dry-run" } else { "" }}}

# List recent Vertex AI CustomJobs in the active region (Usage: just custom-job-status [region])
custom-job-status REGION="us-central1":
    @PROJECT_ID="$(gcloud config get-value project 2>/dev/null || echo 'dandye-0324-chronicle')"; \
    gcloud ai custom-jobs list --region="{{REGION}}" --project="${PROJECT_ID}" --limit=10
# ------------------------------------------------------------------------------
# GKE Ray Serve & Kueue (Distributed Batch Benchmarks)
# ------------------------------------------------------------------------------

# Initialize GKE cluster Kueue queues and Ray operator (Usage: just gke-ray-init [cluster] [region])
gke-ray-init CLUSTER="" REGION="":
    @if [ -n "{{CLUSTER}}" ] && [ -n "{{REGION}}" ]; then \
        gcloud container clusters get-credentials "{{CLUSTER}}" --region="{{REGION}}"; \
    fi
    @kubectl apply -f k8s/kueue_queues.yaml

# Run single model benchmark on GKE RayCluster (Usage: just gke-ray-run [flavor] [dry_run])
gke-ray-run FLAVOR="gemma-3-4b-it" DRY_RUN="false":
    @uv run python3 scripts/run_gke_ray_sweep.py --models "{{FLAVOR}}" {{if DRY_RUN == "true" { "--dry-run" } else { "" }}}

# Run full or filtered benchmark sweep across GKE RayClusters (Usage: just gke-ray-sweep [models] [dry_run])
gke-ray-sweep MODELS="" DRY_RUN="false":
    @uv run python3 scripts/run_gke_ray_sweep.py {{if MODELS != "" { "--models " + MODELS } else { "" }}} {{if DRY_RUN == "true" { "--dry-run" } else { "" }}}

# Query active RayClusters, Kueue LocalQueues, and batch Jobs (Usage: just gke-ray-status [namespace])
gke-ray-status NAMESPACE="gemma-benchmarks":
    @kubectl get rayclusters,jobs,localqueues -n "{{NAMESPACE}}"

# Forcefully delete RayClusters and batch Jobs in namespace to release GPU node pools (Usage: just gke-ray-cleanup [namespace])
gke-ray-cleanup NAMESPACE="gemma-benchmarks":
    @echo "Cleaning up GKE Ray workloads in namespace '{{NAMESPACE}}'..."
    @kubectl delete rayclusters,jobs --all -n "{{NAMESPACE}}" --ignore-not-found=true

# ------------------------------------------------------------------------------
# Harbor Framework SOC Tier 1 Skills Evaluation Suite (harbor-gke-ext v1.3)
# ------------------------------------------------------------------------------

# Generate the frozen Gen 3 Harbor tree (evals/harbor_soc): 4 arms x 10 cases, plus evals.json
harbor-soc-generate:
    @.venv/bin/python3 scripts/generate_harbor_soc_tasks.py --gen3

# Verify all 40 Gen 3 Harbor SOC tasks, SHA-256 environment deduplication, and 100% oracle calibration
harbor-soc-test:
    @.venv/bin/pytest tests/test_harbor_soc_skills.py tests/test_soc_sandbox_cli.py tests/test_verify_harbor_soc.py tests/test_harbor_soc_tasks.py -v

# Generate the Gen 5 Harbor tree (evals/harbor_soc_gen5): default arms clean_skills and gepa_evolved_skills x validation and final_test (Usage: just harbor-soc-gen5-generate ["clean_skills gepa_evolved_skills"])
harbor-soc-gen5-generate ARMS="clean_skills gepa_evolved_skills":
    @.venv/bin/python scripts/generate_harbor_soc_tasks.py --arms {{ARMS}}

# Regenerate the Gen 5 Harbor tree into a temp dir and fail on any byte-level drift from the committed tree
harbor-soc-gen5-check:
    @.venv/bin/python scripts/generate_harbor_soc_tasks.py --check

# Gen 5 Harbor layout, answer-key isolation, one environment hash, container oracle, --check
harbor-soc-gen5-test:
    @.venv/bin/python -m pytest tests/test_harbor_soc_gen5_tasks.py tests/test_gen5_transport_parity.py -q

# ------------------------------------------------------------------------------
# Gen 5 Family-Instanced SOC Evaluation Suite (configs/evals/gen5)
# ------------------------------------------------------------------------------

# Build the Gen 5 bundles and manifest from the family templates (no-op when up to date)
gen5-build:
    @.venv/bin/python scripts/gen5_instancer.py build

# Verify the committed bundles and the Harbor tree match their generators, then run the schema and suite tests
gen5-check:
    @.venv/bin/python scripts/gen5_instancer.py check
    @.venv/bin/python scripts/generate_harbor_soc_tasks.py --check
    @.venv/bin/python -m pytest tests/test_gen5_schema.py tests/test_gen5_suite.py -q

# Run the four Gen 5 reference policies in both transports and apply the spec 8.1 gates (Usage: just gen5-calibrate [trials])
gen5-calibrate TRIALS="3":
    @.venv/bin/python scripts/gen5_reference_policies.py calibrate --trials {{TRIALS}} --transport both

# Run the Gen 5 suite on one split through the exposure ledger (Usage: just eval-gen5 [flavor] [split] [endpoint] [purpose])
eval-gen5 FLAVOR="gemini-2.5-flash" SPLIT="validation" ENDPOINT="" PURPOSE="gen5 eval run":
    @.venv/bin/python -m scripts.eval_soc_agent --flavor "{{FLAVOR}}" --gen 5 --split {{SPLIT}} --purpose "{{PURPOSE}}" --agent-mode hierarchical {{ if ENDPOINT != "" { "--endpoint " + ENDPOINT } else { "--managed-model " + FLAVOR } }} --output-report "docs/soc_eval_results/gen5_{{SPLIT}}_{{FLAVOR}}_report.md" --output-json "docs/soc_eval_results/gen5_{{SPLIT}}_{{FLAVOR}}_report.json"

# Measurement gate 1: K seed passes on the validation split, writes noise_floor.json and exits (Usage: just gen5-noise [k] [task_lm])
gen5-noise K="3" TASK_LM="gemini-2.5-flash":
    @.venv/bin/python agent/gepa_runbook_optimizer.py --noise-only --noise-runs {{K}} --task-lm "{{TASK_LM}}" --val-split validation --purpose "measurement gate 1: seed noise floor (K={{K}})" --output-dir "docs/soc_eval_results/gen5_noise_{{TASK_LM}}"

# Measurement gate 4 (report): one capability rung on validation with the seed runbooks (Usage: just gen5-gradient [flavor] [endpoint])
gen5-gradient FLAVOR="gemini-2.5-flash" ENDPOINT="":
    @.venv/bin/python -m scripts.eval_soc_agent --flavor "{{FLAVOR}}" --gen 5 --split validation --purpose "measurement gate 4: capability gradient ({{FLAVOR}})" --agent-mode hierarchical {{ if ENDPOINT != "" { "--endpoint " + ENDPOINT } else { "--managed-model " + FLAVOR } }} --output-report "docs/soc_eval_results/gen5_gradient/{{FLAVOR}}.md" --output-json "docs/soc_eval_results/gen5_gradient/{{FLAVOR}}.json"

# Re-approve the harness lock after an intended change to a protected scoring or Gen 5 input file
harness-approve:
    @.venv/bin/python scripts/harness_lock.py approve

# Verify every protected path against .eval_harness_lock.json (exit 1 on drift)
harness-verify:
    @.venv/bin/python scripts/harness_lock.py verify







