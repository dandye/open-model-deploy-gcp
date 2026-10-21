# Gemma & Multi-Model Deployment on Google Cloud

**Documentation Site**: [https://dandye.github.io/open-model-deploy-gcp/](https://dandye.github.io/open-model-deploy-gcp/)

Automated deployment scripts, Terraform modules, Justfile recipes, and **Disciplined Agentic SOC Evaluation & Recursive Runbook Evolution ($\text{Harness}^2$, GEPA, and DSPy Context Hygiene)** for the Google Gemma family (Gemma 2 2B/9B/27B, Gemma 3 1B/4B/12B/27B, Gemma 4 E2B/E4B/31B, FP8, and Speculative Decoding variants), Meta Llama models (Llama 4, Llama 3.x, Llama Guard), frontier open-weight partner models (Thinking Machines Inkling, NVIDIA Nemotron, Qwen 3.8 / 2.5, Zhipu GLM, DeepSeek V4, Moonshot Kimi), and managed Gemini models across Vertex AI Online Prediction and Cloud Run with GPU.

---

## 0. Agentic SOC Runbook Evolution: $\text{Harness}^2$, DSPy Context Hygiene & Disciplined Hillclimbing

Beyond serving infrastructure, this repository implements an end-to-end **Regularized Recursive Self-Improvement (RRSI)** and **$\text{Harness}^2$ Propose-Probe-Compose** (`arXiv:2610.14224`, [google-research/harness2](https://github.com/google-research/harness2)) pipeline for evolving Security Operations Center (SOC) Tier 1 triage and Track 2 proactive threat-hunting runbooks without weight updates or test-set memorization:

- **Cryptographic Evaluation Harness Lock (`.eval_harness_lock.json`)**: `HarnessIntegrityGuard` verifies SHA-256 checksums across all 33 protected dataset, sandbox, verifier, and cost-engine files before every optimization step (`just harness-verify`), keeping the 30-case `final_test` split sealed via `scripts/gen5_exposure.py`.
- **DSPy Context Hygiene & Structural Linting (`just lint-runbooks`)**: Strips non-executable Mermaid `sequenceDiagram` blocks, interactive IDE pseudo-tools (`ask_followup_question`, `attempt_completion`, `write_to_file`), and shell `${VAR_NAME}` placeholders (`-> <angle_bracket>` slots) while enforcing a `<350`-word per-runbook cap ([`docs/RUNBOOK_AUTHORING_BEST_PRACTICES.md`](docs/RUNBOOK_AUTHORING_BEST_PRACTICES.md)).
- **$\text{Harness}^2$ Contrastive `INV`/`DOM` Propose-Probe-Compose (`agent/gepa_runbook_optimizer.py`)**:
  - **Task-Level Recursion**: Separates **`INVARIANT` (`INV`)** workflow/tool-ordering edits from **`DOMAIN` (`DOM`)** SecOps decision-boundary contracts, probes both candidates on component-matched training cases with categorical safety/taxonomy gates (`_probe_score()`), and composes verified improvements (`COMPOSED` / `INV` / `DOM` / `KEEP_BASE`).
  - **Component-Stratified Outer Minibatches**: `ComponentStratifiedBatchSampler` + `NonFrozenRoundRobinSelector` guarantee that outer GEPA acceptance minibatches include 3 family-interleaved cases targeting the mutated runbook plus 1 cross-runbook benign/duplicate guard case, eliminating the 51.2%–72.9% minority-runbook starvation rate of uniform sampling.
  - **Harnessing-Level Recursion (`ExperienceLibrary`)**: Computes 4-state component attribution (`helped | hurt | no_observed_effect | confounded`) after every validation pass and persists redacted, contrast-supported rules to [`configs/runbooks/harness2_evolved/EXPERIENCE.md`](configs/runbooks/harness2_evolved/EXPERIENCE.md).

### Gen 5 Tier 1 Cross-Model Transfer Summary (`180` Trajectories across 3 Models $\times$ 3 Arms)

Full report: [`docs/soc_eval_results/harness2_8h_campaign/HARNESS2_CAMPAIGN_REPORT.md`](docs/soc_eval_results/harness2_8h_campaign/HARNESS2_CAMPAIGN_REPORT.md) | Scorecard: [`GEN5_TRANSFER_SCORECARD.md`](docs/soc_eval_results/harness2_8h_campaign/gen5_transfer/GEN5_TRANSFER_SCORECARD.md)

| Runbook Arm | Total Words | Word Reduction vs Seed | Mean Harbor 60/20/20 | Mean GEPA Fitness | Mean $d'$ | Mean Operational Loss ($L$, USD) | Mean Tool Calls | Total Safety Violations |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `seed_runbooks` (`.clinerules`) | `3,648` | `0.0%` | `0.9744` | `0.9584` | `2.91` | `$16,834.40` | `5.53` | `0` |
| `gepa_single_proposer` | `1,988` | `-45.5%` | `0.9787` | `0.9627` | `2.91` | `$33,417.74` | `5.57` | `0` |
| **`harness2_k2_evolved`** ([`configs/runbooks/harness2_evolved/`](configs/runbooks/harness2_evolved/)) | **`1,743`** | **`-52.2%`** | **`0.9804`** | **`0.9804`** | `2.89` | **`$1,834.24`** (**`-89.1%`** vs seed, **`-94.5%`** vs single-proposer) | **`5.30`** | **`0`** |

### Track 2 Proactive Threat Hunting (`ThreatHuntEnvironment`) Transfer Summary (`48` Trajectories across 3 Models $\times$ 4 Arms)

Scorecard: [`THREAT_HUNT_MULTI_MODEL_SCORECARD.md`](docs/soc_eval_results/harness2_8h_campaign/threat_hunt_multi_model/THREAT_HUNT_MULTI_MODEL_SCORECARD.md)

| Runbook Arm | Mean Hunt Composite | Mean Harbor (60/20/20) | Verdict Accuracy | `168h` Widening Rate | LOLBin Safe Rate |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `no_runbook` | `0.8554` | `0.8673` | `92%` | `56%` | `100%` |
| `raw_clinerules_hunt` | `0.8295` | `0.8575` | `92%` | `56%` | `100%` |
| `compressed_track_b_hunt` | `0.9510` | `0.9337` | `100%` | `100%` | `100%` |
| **`harness2_evolved_hunt`** ([`gti_collection_threat_hunt.md`](configs/runbooks/harness2_evolved/gti_collection_threat_hunt.md)) | **`0.9813`** | **`0.9587`** | **`100%`** | **`100%`** | **`100%`** |

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
| **`nemotron-3.5-super-vl-nvfp4`** | NVIDIA | 120B-A12B Multimodal MoE (NVFP4) | `g4-standard-48` | 1x RTX PRO 6000 ($3.85/hr) |
| **`nemotron-3.5-super-vl-bf16`** | NVIDIA | 120B-A12B Multimodal MoE (BF16) | `g4-standard-192` | 4x RTX PRO 6000 ($15.40/hr) |
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
| 10 | **`nemotron-3.5-super-vl-nvfp4`** | Dedicated Model Garden (1x RTX PRO 6000) | **50.0% (5/10)** | **83.0 / 100** | 45.84 s | 186.87 tok/s | 439.65 tok/s | 20 |
| 11 | **`llama-3.2-3b-instruct`** | Dedicated Model Garden (1x L4) | **40.0% (2/5)** | **84.0 / 100** | 22.63 s | 44.96 tok/s | 250.51 tok/s | 11 |
| 12 | **`gemma-4-31b-it-speculative`** | Vertex AI Dedicated (2x A100) | **60.0% (3/5)** | **82.4 / 100** | 14.81 s | 54.45 tok/s | 223.31 tok/s | 6 |
| 13 | **`nemotron-3.5-lightning-bf16`** | Dedicated Model Garden (4x L4) | **40.0% (2/5)** | **79.0 / 100** | 17.98 s | 37.02 tok/s | 186.45 tok/s | 6 |
| 14 | **`gemma-3-12b-it-fp8`** | Vertex AI Dedicated (4x L4) | **60.0% (3/5)** | **79.0 / 100** | 14.21 s | 61.76 tok/s | 216.37 tok/s | 4 |
| 15 | **`gemini-2.5-flash`** | Google MaaS | **60.0% (3/5)** | **75.2 / 100** | 11.74 s | 59.64 tok/s | 271.41 tok/s | 6 |
| 16 | **`llama-4-maverick-17b-128e-instruct-maas`** | Meta Serverless MaaS (`us-east5`) | 0.0% (0/5) | 53.0 / 100 | 12.94 s | 58.73 tok/s | 124.25 tok/s | 0 |

---

## 3. Quick Start (`Justfile`)

```bash
# Display categorized help menu
just

# Verify cryptographic SHA-256 lock on all 33 evaluation harness files
just harness-verify

# Lint SOC runbooks (<350 words, no ${VAR_NAME}, no Mermaid, no IDE pseudo-tools)
just lint-runbooks

# Run Harness^2 Propose-Probe-Compose recursive evolution on Gen 5 (train -> validation)
just gepa-evolve-harness2 gemini-2.5-flash-lite 15 gemini-2.5-pro

# Run Gen 5 SOC evaluation on validation split through the exposure ledger
just eval-gen5 gemini-2.5-flash-lite validation

# Run Two-Stage AQuA trajectory failure clustering and diagnosis
just aqua-diagnose

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

# Deploy NVIDIA Nemotron 3.5 Super VL (120B-A12B NVFP4 on 1x RTX PRO 6000, $3.85/hr)
python3 scripts/deploy_open_model.py \
  --flavor nemotron-3.5-super-vl-nvfp4 \
  --open-model-id publishers/nvidia/models/nemotron-3.5@nemotron-3.5-super-vl-nvfp4 \
  --machine-type g4-standard-48 \
  --accelerator-type NVIDIA_RTX_PRO_6000 \
  --accelerator-count 1

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
│   ├── evals/                    # Gen 1-3, Gen 5 family-instanced & Track 2 threat-hunt benchmarks
│   └── runbooks/
│       ├── harness2_evolved/     # Harness^2 (k=2) evolved <350w runbooks + EXPERIENCE.md
│       └── gepa_evolved/         # Single-proposer GEPA runbook artifacts & ledger
├── scripts/
│   ├── lib/
│   │   └── model_catalog.sh      # Catalog lookup helper library
│   ├── gen5_instancer.py         # Deterministic 90-case Gen 5 family instancer
│   ├── gen5_exposure.py          # Exposure ledger & final_test split seal guard
│   ├── verify_harbor_soc.py      # Unified 60/20/20 Harbor & Python trajectory scorer
│   ├── evolve_threat_hunt_harness2.py # Track 2 ThreatHuntEnvironment Harness^2 evolution runner
│   ├── eval_gen5_transfer_harness2.py # 3-model x 3-arm Gen 5 transfer & cost staircase runner
│   ├── eval_threat_hunt_multi_model.py # Multi-model x 4-arm Track 2 threat-hunt benchmark runner
│   ├── run_aqua_soc_diagnosis.py # Outer-to-inner AQuA trajectory failure cluster analyzer
│   ├── overnight_model_sweep.py  # Targeted sweep orchestrator with $0 idle cost teardown
│   ├── run_overnight_sweep.py    # Master automated benchmark & evaluation sweep runner
│   ├── deploy_open_model.py      # Vertex AI OpenModel deployment wrapper
│   ├── benchmark.py              # Latency & throughput benchmarking tool (TPS/TTFT/ITL)
│   └── eval_soc_agent.py         # Automated SOC agent evaluator with Jev / LLM judge
├── agent/
│   ├── gepa_runbook_optimizer.py # Harness^2 Propose-Probe-Compose, Stratified Sampler & GEPA adapter
│   ├── hillclimb_harness.py      # HarnessIntegrityGuard, Categorical Gates, Attribution & ExperienceLibrary
│   ├── aqua_diagnostics.py       # Two-stage AQuA trajectory diagnosis & stage localization
│   ├── hierarchical_soc_agent.py # Supervisor-Worker SOC agent with DSPy context hygiene
│   ├── threat_hunt_environment.py# Track 2 GTI collection & SIEM horizon-widening sandbox
│   ├── soc_environment.py        # Interactive Gen 3 / Gen 5 SOC state machine sandbox
│   ├── jev_evaluator.py          # Jev System-One logprob & GLiNER2.5-Decide inner-loop judge
│   ├── gemma_agent.py            # Multi-backend unified inference interface
│   ├── soc_tier1_agent.py        # Tier 1 SOC Analyst ReAct agent class
│   ├── soc_tools.py              # Mockable local SOC inspection tools
│   └── secops_mcp_tools.py       # Live Google SecOps Remote MCP client
├── terraform/
│   ├── locals.tf                 # Reads configs/models.json via jsondecode()
│   ├── variables.tf              # Accepts var.model_flavor
│   ├── vertex.tf                 # Vertex AI endpoint resources
│   └── cloudrun.tf               # Cloud Run service resources
└── docs/
    ├── blog/
    │   ├── gepa_runbook_evolution_and_disciplined_hillclimbing.md # Full GEPA, RRSI, DSPy & Harness^2 narrative
    │   ├── gepa_mcp_tool_description_optimization.md             # SecOps MCP tool description optimization
    │   └── part1_zero_idle_gpu_infrastructure.md                 # Zero-idle GPU serving infrastructure
    ├── soc_eval_results/
    │   ├── harness2_8h_campaign/
    │   │   ├── HARNESS2_CAMPAIGN_REPORT.md                       # Complete Harness^2 technical & transfer report
    │   │   ├── gen5_transfer/GEN5_TRANSFER_SCORECARD.md          # 180-trajectory Gen 5 3-model x 3-arm scorecard
    │   │   └── threat_hunt_multi_model/THREAT_HUNT_MULTI_MODEL_SCORECARD.md # 48-trajectory Track 2 scorecard
    │   ├── dspy_overnight/MORNING_REPORT.md                      # 29-experiment DSPy context-hygiene report
    │   └── OVERNIGHT_SWEEP_SUMMARY.md                            # Master dynamic benchmark leaderboard
    ├── RUNBOOK_AUTHORING_BEST_PRACTICES.md # 10 rules for agentic SOC runbooks & 4-way disposition matrix
    ├── hillclimber_rrsi_crosswalk.md       # Disciplined Hillclimber vs RRSI & Harness^2 mechanism crosswalk
    ├── references_agent_harness_literature.md # Annotated bibliography (Harness^2, RRSI, HDA, GEPA)
    └── evals_gen5.md                       # Gen 5 family-instanced SOC suite & measurement gates guide
```

---

## 5. Documentation Reference

* **Published Static Site (GitHub Pages)**: [https://dandye.github.io/open-model-deploy-gcp/](https://dandye.github.io/open-model-deploy-gcp/)

### Agentic SOC Evaluation & Recursive Harness Evolution ($\text{Harness}^2$, RRSI, GEPA)
* [$\text{Harness}^2$ Recursive Runbook Evolution Campaign Report (`arXiv:2610.14224`)](docs/soc_eval_results/harness2_8h_campaign/HARNESS2_CAMPAIGN_REPORT.md)
* [Gen 5 Cross-Model Transfer & Cost Staircase Scorecard (`180` Trajectories)](docs/soc_eval_results/harness2_8h_campaign/gen5_transfer/GEN5_TRANSFER_SCORECARD.md)
* [Track 2 Proactive Threat Hunting Multi-Model Scorecard (`48` Trajectories)](docs/soc_eval_results/harness2_8h_campaign/threat_hunt_multi_model/THREAT_HUNT_MULTI_MODEL_SCORECARD.md)
* [Blog: Evolving SecOps Runbooks Without Cheating (GEPA, Verbosity Bias, RRSI, DSPy & $\text{Harness}^2$)](docs/blog/gepa_runbook_evolution_and_disciplined_hillclimbing.md)
* [Blog: Evolving SecOps MCP Tool Descriptions with GEPA](docs/blog/gepa_mcp_tool_description_optimization.md)
* [10 Rules for Agentic SOC Runbook Authoring (`RUNBOOK_AUTHORING_BEST_PRACTICES.md`)](docs/RUNBOOK_AUTHORING_BEST_PRACTICES.md)
* [Disciplined Hillclimber vs. RRSI & $\text{Harness}^2$: Mechanism Crosswalk](docs/hillclimber_rrsi_crosswalk.md)
* [Annotated Bibliography: Agent Harness, Skill Evolution & Evaluation Literature](docs/references_agent_harness_literature.md)
* [Gen 5 Family-Instanced SOC Evaluation Suite & Measurement Gates](docs/evals_gen5.md)
* [DSPy Context Engineering 9-Hour Overnight Report (`MORNING_REPORT.md`)](docs/soc_eval_results/dspy_overnight/MORNING_REPORT.md)

### Multi-Model GPU Serving & Benchmarking Infrastructure
* [Project Overview (`docs/index.md`)](docs/index.md)
* [Full Documentation Catalog (`docs/catalog.md`)](docs/catalog.md)
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
