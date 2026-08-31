# Gemma & Multi-Model Deployment on Google Cloud

Automated deployment scripts, Terraform modules, and Justfile recipes for deploying the entire Google Gemma family (Gemma 2 2B/9B/27B, Gemma 3 1B/4B/12B/27B, Gemma 4 E2B/E4B/31B, FP8, and Speculative Decoding variants), Meta Llama models (Llama 4, Llama 3.x, Llama Guard), and frontier open-weight partner models (Thinking Machines Inkling, NVIDIA Nemotron, Qwen 3.8 / 2.5, Zhipu GLM, DeepSeek V4, Moonshot Kimi) across Vertex AI Online Prediction and Cloud Run with GPU, alongside managed Gemini comparative evaluation benchmarks.


<img width="793" height="766" alt="Screenshot 2026-08-27 at 8 32 30 AM" src="https://depot.code.corp.goog/user-attachments/assets/451c3c09-882e-478c-8478-b11555a856b3" />

---

## 1. Multi-Model Architecture & Central Catalog

The repository uses a single declarative source of truth at [`configs/models.json`](configs/models.json) that defines the exact compute hardware, VRAM, context length, and target environments for each model flavor:

### Google Gemma Family
| Flavor | Architecture / Scale | Recommended Compute | GPU Hardware | Hourly Cost | Target Environments |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`gemma-2-2b-it`** | 2.6B Dense | `g2-standard-4` | 1x NVIDIA L4 | **$0.70 / hr** | Vertex AI, Cloud Run ($0 idle) |
| **`gemma-2-9b-it`** | 9.2B Dense | `g2-standard-12` | 1x NVIDIA L4 | **$0.83 / hr** | Vertex AI, Cloud Run ($0 idle) |
| **`gemma-2-27b-it`**| 27.2B Dense | `g2-standard-48` | 4x NVIDIA L4 | **$3.36 / hr** | Vertex AI |
| **`gemma-3-1b-it`** | 1.0B Dense | `g2-standard-4` | 1x NVIDIA L4 | **$0.70 / hr** | Vertex AI, Cloud Run ($0 idle) |
| **`gemma-3-4b-it`** | 4.0B Dense | `g2-standard-8` | 1x NVIDIA L4 | **$0.76 / hr** | Vertex AI, Cloud Run ($0 idle) |
| **`gemma-3-12b-it`**| 12.0B Multimodal | `g2-standard-48` | 4x NVIDIA L4 | **$3.36 / hr** | Vertex AI |
| **`gemma-3-27b-it`**| 27.0B Multimodal | `g2-standard-48` | 4x NVIDIA L4 | **$3.36 / hr** | Vertex AI |
| **`gemma-3-27b-it-fp8`** | 27.0B (FP8 Quantized) | `g2-standard-48` | 4x NVIDIA L4 | **$3.36 / hr** | Vertex AI |
| **`gemma-3-27b-it-speculative`** | 27.0B (FP8 + Prompt Lookup) | `g2-standard-48` | 4x NVIDIA L4 | **$3.36 / hr** | Vertex AI |
| **`gemma-4-e2b-it`**| 2.3B eff / 5.1B MoE | `g2-standard-4` | 1x NVIDIA L4 | **$0.70 / hr** | Vertex AI, Cloud Run ($0 idle) |
| **`gemma-4-e4b-it`**| 4.5B eff / 8.0B MoE | `g2-standard-8` | 1x NVIDIA L4 | **$0.76 / hr** | Vertex AI, Cloud Run ($0 idle) |
| **`gemma-4-31b-it`**| 31.0B Reasoner | `a2-highgpu-2g` | 2x NVIDIA A100 | **$7.34 / hr** | Vertex AI |

### Meta Llama & Partner Model Garden / OpenModels
| Flavor | Provider | Model Type | Recommended Compute | Hardware / Tier |
| :--- | :--- | :--- | :--- | :--- |
| **`llama-4-scout-17b-16e-instruct-maas`** | Meta | 17B active MoE | Serverless MaaS | `us-east5` |
| **`llama-4-maverick-17b-128e-instruct-maas`** | Meta | 17B active MoE | Serverless MaaS | `us-east5` |
| **`llama-3.1-nemotron-70b-instruct`** | NVIDIA / Meta | 70B Aligned Dense | `g2-standard-48` | 4x NVIDIA L4 ($3.32/hr) |
| **`llama-guard-3-8b`** | Meta | 8B Safety Classifier | `g2-standard-12` | 1x NVIDIA L4 ($1.01/hr) |
| **`llama-3.2-3b-instruct`** | Meta | 3.2B Compact Dense | `g2-standard-8` | 1x NVIDIA L4 ($0.83/hr) |
| **`inkling-small`** | Thinking Machines | OpenModel | `g2-standard-48` | 4x NVIDIA L4 ($3.32/hr) |
| **`nemotron-3.5-lightning-bf16`** | NVIDIA | 30B MoE | `g2-standard-48` | 4x NVIDIA L4 ($3.32/hr) |
| **`qwen3.8-27b`** | Qwen / HF | 27B OpenModel | `g4-standard-48` | 1x RTX PRO 6000 ($3.85/hr) |
| **`qwen3.8-flash-next`** | Qwen / HF | OpenModel | `g2-standard-12` | 1x NVIDIA L4 ($1.01/hr) |
| **`qwen3.8-flash-next-fp8`** | Qwen / HF | FP8 OpenModel | `g2-standard-8` | 1x NVIDIA L4 ($0.83/hr) |
| **`qwen3.8-2.4t-a95b-fp8`** | Qwen / HF | 2.4T / A95B MoE FP8 | `g4-standard-48` | 1x RTX PRO 6000 ($3.85/hr) |
| **`glm-5.3-flash`** | Zhipu AI / THUDM | OpenModel | `g2-standard-12` | 1x NVIDIA L4 ($1.01/hr) |
| **`deepseek-v4-pro`** | DeepSeek | OpenModel | `g4-standard-48` | 1x RTX PRO 6000 ($3.85/hr) |
| **`kimi-k3`** | Moonshot AI | OpenModel | `g4-standard-48` | 1x RTX PRO 6000 ($3.85/hr) |

---

## 2. Master Comparative Evaluation Leaderboard

All models evaluated on the un-spoiled SOC Tier 1 Benchmark Suite (expanded 10-case evaluation suite covering C2 malware beaconing, RFC-5737 documentation grounding, phishing credential harvesting, SOAR deduplication, critical ransomware escalation, borderline DNS tunnels, lateral movement, supply chain revoked certs, threat intelligence HTTP 503 outage resilience, and authorized vulnerability scanner noise):

| Rank | Model Flavor | Provider / Serving | Pass Rate | Avg Rubric | Latency | Gen TPS | Total TPS | Tool Calls |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | **`gemini-3.5-flash-lite`** | Google MaaS | **100.0% (5/5)** | **97.0 / 100** | 11.36 s | 70.22 tok/s | 241.65 tok/s | 5 |
| 2 | **`gemma-3-12b-it`** | Vertex AI Dedicated (4x L4) | **60.0% (3/5)** | **91.0 / 100** | 25.19 s | 19.30 tok/s | 71.63 tok/s | 4 |
| 3 | **`gemma-4-e4b-it`** | Vertex AI Dedicated (1x L4) | **80.0% (4/5)** | **91.0 / 100** | 40.24 s | 15.27 tok/s | 44.56 tok/s | 3 |
| 4 | **`qwen3.8-27b`** | Dedicated OpenModel (1x RTX 6000) | **60.0% (3/5)** | **88.4 / 100** | 29.12 s | 26.50 tok/s | 101.02 tok/s | 5 |
| 5 | **`llama-3.1-nemotron-70b-instruct`** | Dedicated Model Garden (4x L4) | **60.0% (3/5)** | **86.0 / 100** | 18.83 s | 43.93 tok/s | 190.58 tok/s | 6 |
| 6 | **`inkling-small`** | Dedicated Model Garden (4x L4) | **60.0% (3/5)** | **85.0 / 100** | 15.60 s | 51.22 tok/s | 214.50 tok/s | 6 |
| 7 | **`llama-4-scout-17b-16e-instruct-maas`** | Meta Serverless MaaS (`us-east5`) | **60.0% (3/5)** | **85.0 / 100** | 12.21 s | 66.70 tok/s | 332.76 tok/s | 10 |
| 8 | **`gemma-4-31b-it`** | Vertex AI Dedicated (2x A100) | **60.0% (3/5)** | **85.0 / 100** | 17.45 s | 51.23 tok/s | 233.48 tok/s | 8 |
| 9 | **`llama-guard-3-8b`** | Dedicated Model Garden (1x L4) | **80.0% (4/5)** | **84.0 / 100** | 16.32 s | 49.06 tok/s | 235.33 tok/s | 8 |
| 10 | **`llama-3.2-3b-instruct`** | Dedicated Model Garden (1x L4) | **40.0% (2/5)** | **84.0 / 100** | 22.63 s | 44.96 tok/s | 250.51 tok/s | 11 |
| 11 | **`gemma-4-31b-it-speculative`** | Vertex AI Dedicated (2x A100) | **60.0% (3/5)** | **82.4 / 100** | 14.81 s | 54.45 tok/s | 223.31 tok/s | 6 |
| 12 | **`nemotron-3.5-lightning-bf16`** | Dedicated Model Garden (4x L4) | **40.0% (2/5)** | **79.0 / 100** | 17.98 s | 37.02 tok/s | 186.45 tok/s | 6 |
| 13 | **`gemma-3-12b-it-fp8`** | Vertex AI Dedicated (4x L4) | **60.0% (3/5)** | **79.0 / 100** | 14.21 s | 61.76 tok/s | 216.37 tok/s | 4 |
| 14 | **`gemini-2.5-flash`** | Google MaaS | **60.0% (3/5)** | **75.2 / 100** | 11.74 s | 59.64 tok/s | 271.41 tok/s | 6 |
| 15 | **`llama-4-maverick-17b-128e-instruct-maas`** | Meta Serverless MaaS (`us-east5`) | 0.0% (0/5) | 53.0 / 100 | 12.94 s | 58.73 tok/s | 124.25 tok/s | 0 |

---

## 3. Quick Start (`Justfile`)

```bash
# Display categorized help menu
just

# View models in catalog and Model Registry
just model-list

# View infrastructure pricing matrix across all models
just cost-list

# Run master overnight evaluation sweep across newly queued partner models
just sweep-new

# Run master overnight evaluation sweep across all models
just overnight-sweep
```

### Model Deployment Recipes

```bash
# Deploy Gemma 2 9B to Vertex AI (auto-selects g2-standard-12, 1x L4)
just vertex-deploy gemma-2-9b-it

# Deploy Gemma 3 12B Multimodal to Vertex AI (auto-selects g2-standard-48, 4x L4)
just vertex-deploy gemma-3-12b-it

# Deploy Gemma 4 E4B to Vertex AI (auto-selects g2-standard-8, 1x L4)
just vertex-deploy gemma-4-e4b-it

# Deploy Gemma 2 2B to Cloud Run with Scale-to-Zero ($0 idle)
just cloudrun-deploy gemma-2-2b-it

# Deploy Hugging Face / Model Garden OpenModel via Vertex AI SDK
just openmodel-deploy qwen3.8-27b

# Query the active model endpoint
just predict "Explain phishing triage in two paragraphs."

# Undeploy endpoint and guarantee $0 idle cost
just vertex-undeploy
```

---

## 4. Repository Structure

```text
├── configs/
│   ├── models.json               # Central multi-model catalog & hardware specifications
│   └── evals/                    # Declarative SOC Tier 1 evaluation benchmarks
├── scripts/
│   ├── lib/
│   │   └── model_catalog.sh      # Catalog lookup helper library
│   ├── overnight_model_sweep.py  # Targeted sweep orchestrator with $0 idle cost teardown
│   ├── run_overnight_sweep.py    # Master automated benchmark & evaluation sweep runner
│   ├── deploy_open_model.py      # Vertex AI OpenModel deployment wrapper
│   ├── vertex_deploy.sh          # Model-aware Vertex AI deployer
│   ├── vertex_model_register.sh  # Model Registry uploader with metadata
│   ├── vertex_status.sh          # Deployment status & operation inspector
│   ├── vertex_undeploy.sh        # Endpoint undeployer & cost cleanup
│   ├── cloudrun_deploy.sh        # Model-aware Cloud Run deployer
│   ├── cloudrun_quota_check.sh   # Quota checker
│   ├── cloudrun_status.sh        # Cloud Run status inspector
│   ├── model_list.sh             # Interactive catalog list
│   ├── cost_list.sh              # Terminal pricing matrix
│   ├── auth_check.sh             # Preflight credentials checker
│   ├── benchmark.py              # Latency & throughput benchmarking tool (TPS/TTFT/ITL)
│   └── eval_soc_agent.py         # Automated SOC agent evaluator with LLM judge
├── agent/
│   ├── gemma_agent.py            # Multi-backend unified inference interface
│   ├── soc_tier1_agent.py        # Tier 1 SOC Analyst agent class
│   ├── soc_tools.py              # Mockable local SOC inspection tools
│   ├── secops_mcp_tools.py       # Live Google SecOps Remote MCP client
│   └── deploy_soc_tier1.py       # Vertex AI Agent Engine packaging & deployment
├── terraform/
│   ├── locals.tf                 # Reads configs/models.json via jsondecode()
│   ├── variables.tf              # Accepts var.model_flavor
│   ├── vertex.tf                 # Vertex AI endpoint resources
│   └── cloudrun.tf               # Cloud Run service resources
└── docs/
    ├── soc_eval_results/
    │   └── OVERNIGHT_SWEEP_SUMMARY.md # Master dynamic benchmark leaderboard
    ├── llama_model_comparative_evals.md # Detailed Llama & partner comparative scorecards
    ├── llama_soc_agent_evaluation_plan.md # Evaluation blueprint & methodology
    ├── speculative_decoding.md   # Speculative decoding & Prompt Lookup (N-gram) guide
    ├── model_registry_catalog.md # Authoritative Vertex AI Model Registry inventory
    ├── cost_analysis.md          # Hardware sizing, pricing breakdown & lifecycle analysis
    ├── cloudrun_deploy.md        # Cloud Run deployment guide
    └── vertex_deployment_notes.md# Vertex AI deployment guide
```

---

## 5. Documentation Reference

* [Future Work & Strategic Roadmap](docs/future_work.md)
* [Master Dynamic Benchmark Leaderboard](docs/soc_eval_results/OVERNIGHT_SWEEP_SUMMARY.md)
* [Gemma SOC Tier 1 Evaluation Plan & Methodology (10-Case Benchmark Suite)](docs/gemma_soc_agent_evaluation_plan.md)
* [Llama & Partner SOC Evaluation Plan](docs/llama_soc_agent_evaluation_plan.md)
* [Speculative Decoding & Prompt Lookup Guide](docs/speculative_decoding.md)
* [Compute Engine Ephemeral Spot GPU VMs Guide](docs/benchmarking_gce_ephemeral_spot_vms.md)
* [Vertex AI Custom Jobs Ephemeral Runner Guide](docs/benchmarking_vertex_custom_jobs.md)
* [GKE Ray Serve & Kueue Distributed Batch Sweep Guide](docs/benchmarking_gke_ray_serve.md)
* [Vertex AI Model Registry Master Catalog](docs/model_registry_catalog.md)
* [Model Deployment Status & Matrix](docs/deployment_status.md)
* [Cost Analysis & Hardware Sizing Breakdown](docs/cost_analysis.md)
* [Cloud Run GPU Deployment Guide](docs/cloudrun_deploy.md)
* [Terraform Infrastructure Guide](terraform/README.md)
