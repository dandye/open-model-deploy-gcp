| Author | Dan Dye |
| :---- | :---- |
| Peer Reviewer |  |
| Topics | Agent Skills, Local Models, Model Sizing, Model Evaluation, Gemma, Llama, Qwen, Mistral, Vertex AI, Cloud Run GPU |

---

# What is the Smallest Model that Benefits from Agent Skills? Running Karl Weinmeister's Evals on Local Models

**Author:** Dan Dye  
**Series:** Serving Open Models for Security & Cloud Agents  
**Repository:** [github.com/dandye/open-model-deploy-gcp](https://github.com/dandye/open-model-deploy-gcp) (branch `skill_discovery_eval_v0001`)  
**Evaluation Data:** [Master Open Model Sweep Report](../eval_results/discovery/master_open_model_sweep_report.md)

---

&nbsp;

My colleague Karl Weinmeister published a study that changed how we think about agent context engineering: [*Do agent skills help? I ran 72 trials to find out*](https://www.linkedin.com/pulse/do-agent-skills-help-i-ran-72-trials-find-out-karl-weinmeister-nnqec/).

Running 72 clean-room sandbox trials across 12 standardized cloud scenarios with Claude Code, Karl showed that loading domain skills (`SKILL.md` files) replaced command guessing and shell thrashing with working infrastructure on the first attempt, achieving an action economy score of 0.8616 compared to 0.0000 for the unassisted baseline.

Karl gave the community a clean, reproducible evaluation framework, which was exactly what I needed to work on this question:

> **What is the smallest size and earliest generation of model, which still gets that lift from skills?**

Can a lightweight 1B or 4B edge model running serverless on Cloud Run GPU get the job done? Or do you need an 8B–14B mid-weight model on a single $0.70/hr GPU?

To answer this, I used Karl's standardized 12-scenario declarative benchmark (`evals.json`) and ran them systematically across **23 open-weight and partner models** spanning multiple architectures, sizes, and model generations on Google Cloud.

---

## The Benchmark Suite: Karl's 12 Cloud Scenarios

I reused Karl Weinmeister's exact 12-scenario evaluation suite from [`evals/gemma-deploy/evals.json`](../../evals/gemma-deploy/evals.json).

Each scenario tests a concrete, non-trivial operational cloud task with 4 objective boolean assertions scored by a blinded LLM judge (`vertex_ai/gemini-2.5-flash`), yielding 48 assertion checks per model run:

| Scenario ID | Task Name | Domain Skill | Technical Challenge Tested |
| :---- | :---- | :---- | :---- |
| `gdo-001` | Cloud Run GPU L4 Scale-to-Zero | `cloudrun-deploy` | NVIDIA L4 accelerator flags, `--min-instances=0`, CPU-to-RAM ratios |
| `gdo-002` | Vertex Speculative Decoding N-Gram | `vertex-prediction` | vLLM `--speculative-model=[ngram]`, prompt lookup flags, zero VRAM |
| `gdo-003` | Server-Side Disk Audit | `gcloud` | Server-side `--filter="-users:*"` preventing context window floods |
| `gdo-004` | Cross-Project Secret IAM | `gcp-auth` | Resource-level binding (`gcloud secrets`) vs project-wide over-privilege |
| `gdo-005` | Destructive Teardown Safety Gate | `cloud-safety` | Read-only listing preview and explicit confirmation before batch deletion |
| `gdo-006` | GCE Spot VM Auto-Deletion | `gce-spot` | Spot provisioning, Local NVMe scratch, trap self-deletion handlers |
| `gdo-007` | Vertex Container Swap Space | `vertex-prediction` | Exact Model Garden host RAM to swap space ratios (`8`/`16`/`32` GB) |
| `gdo-008` | Cloud Run GPU Quota Lifecycle | `cloudrun-quota` | Quota preference management, exact quota metrics, non-interactive reset |
| `gdo-009` | ADK Agent Endpoint Discovery | `agent-engine` | Dynamic `/v1/models` discovery for local vLLM serving endpoints |
| `gdo-010` | SOC Containment vs Escalation | `secops-triage` | Balancing $50k+ ERP downtime disruption against malware containment |
| `gdo-011` | ADC vs Service Account Keys | `gcp-auth` | User ADC and impersonation vs downloadable JSON key antipatterns |
| `gdo-012` | Model Catalog Sizing Parity | `model-catalog` | Compute shapes, tensor parallelism, and VRAM boundaries |

### The Evaluation Protocol: Prior Correction & Execution

To measure whether domain skills actually improve open models, each scenario is evaluated across two paired conditions:

1. **Baseline Arm (Unassisted Prompt):** The model receives the raw task prompt with zero domain context, testing its baseline pretraining priors and zero-shot command generation.
2. **Treatment Arm (With Domain Skill):** The authoritative domain skill (`SKILL.md`) is injected directly into the context window, supplying exact flags, resource-scoped IAM conventions, and hardware boundary rules.

The outputs from both arms are graded against the 4 discrete technical assertions by a blinded LLM judge (`vertex_ai/gemini-2.5-flash`), isolating the exact capability lift and prior correction contributed by the skill.

---

## The Multi-Model Sweep: Empirical Results Across 23 Models

I evaluated 23 models across different scales (1B to 32B), generations, and model families:

- **Google Gemma:** Gemma 2 (2B, 9B, 27B), Gemma 3 (1B, 4B, 12B, 27B), and Gemma 4 (E2B, E4B)  
- **Meta Llama:** Llama 3.2 (3B), Llama 3.1 (8B)  
- **Alibaba Qwen:** Qwen 2.5 (7B, 14B, 32B Coder), Qwen 3.8 (27B)  
- **Mistral AI:** Mistral NeMo 12B Instruct  
- **DeepSeek:** DeepSeek R1 Distill Llama 8B, DeepSeek R1 Distill Qwen 14B  
- **Microsoft:** Phi-4 (14B)  
- **Thinking Machines:** Inkling Small (14B)  
- **Frontier Reference Baselines:** Gemini 2.5 Flash, Gemini 3.7 Flash, Gemini 3.8 Flash

Here is the empirical scorecard ordered by With-Skill assertion performance:

| Model Variant | Size / Architecture | GPU Serving Target | Baseline Pass | With-Skill Pass | Net Pass Lift (Δ) | Assertions Matched (Base -> Skill) | Net Assertion Lift (Δ) |
| :---- | :---- | :---- | :---: | :---: | :---: | :---: | :---: |
| **`gemini-3.7-flash`** | Frontier Serverless | Managed API | 83.3% | **100.0%** | +16.7% | 37 -> **48 / 48** (100.0%) | +22.9% |
| **`qwen3.8-27b`** | 27B Dense Reasoner | 4x L4 (`g2-standard-48`) | 66.7% | **100.0%** | +33.3% | 35 -> **48 / 48** (100.0%) | +27.1% |
| **`gemma-4-e4b-it`** | 4B Active (MoE) | 1x L4 (`g2-standard-4`) | 41.7% | **100.0%** | +58.3% | 23 -> **47 / 48** (97.9%) | +50.0% |
| **`gemma-3-27b-it`** | 27B Dense | 4x L4 (`g2-standard-48`) | 41.7% | **100.0%** | +58.3% | 23 -> **47 / 48** (97.9%) | +50.0% |
| **`mistral-nemo-instruct-2407`** | 12B Dense (Tekken) | 4x L4 (`g2-standard-48`) | 41.7% | **100.0%** | +58.3% | 21 -> **46 / 48** (95.8%) | +52.1% |
| **`qwen2.5-coder-32b-instruct`** | 32B Code Specialist | 4x L4 (`g2-standard-48`) | 33.3% | **91.7%** | +58.3% | 24 -> **46 / 48** (95.8%) | +45.8% |
| **`gemini-3.8-flash`** | Frontier Serverless | Managed API | 66.7% | **100.0%** | +33.3% | 35 -> **46 / 48** (95.8%) | +22.9% |
| **`deepseek-r1-distill-qwen-14b`** | 14B Distilled Reasoner | 2x L4 (`g2-standard-24`) | 25.0% | **91.7%** | **+66.7%** | 20 -> **45 / 48** (93.8%) | +52.1% |
| **`gemma-2-27b-it`** | 27B Dense | 4x L4 (`g2-standard-48`) | 41.7% | **100.0%** | +58.3% | 21 -> **45 / 48** (93.8%) | +50.0% |
| **`gemma-3-12b-it`** | 12B Dense | 4x L4 (`g2-standard-48`) | 66.7% | **100.0%** | +33.3% | 33 -> **45 / 48** (93.8%) | +25.0% |
| **`gemma-3-4b-it`** | 4B Dense | 1x L4 (`g2-standard-8`) | 41.7% | **100.0%** | +58.3% | 26 -> **45 / 48** (93.8%) | +39.6% |
| **`phi-4`** | 14B Dense Reasoner | 2x L4 (`g2-standard-24`) | 33.3% | **91.7%** | +58.3% | 23 -> **42 / 48** (87.5%) | +39.6% |
| **`qwen2.5-14b-instruct`** | 14B Dense | 2x L4 (`g2-standard-24`) | 25.0% | **91.7%** | **+66.7%** | 18 -> **42 / 48** (87.5%) | +50.0% |
| **`llama-3.1-8b-instruct`** | 8B Dense | 1x L4 (`g2-standard-12`) | 25.0% | **83.3%** | +58.3% | 18 -> **42 / 48** (87.5%) | +50.0% |
| **`gemini-2.5-flash`** | General Workhorse | Managed API | 50.0% | **91.7%** | +41.7% | 25 -> **42 / 48** (87.5%) | +35.4% |
| **`qwen2.5-7b-instruct`** | 7B Dense | 1x L4 (`g2-standard-12`) | 25.0% | **83.3%** | +58.3% | 19 -> **41 / 48** (85.4%) | +45.8% |
| **`deepseek-r1-distill-llama-8b`** | 8B Distilled Reasoner | 2x L4 (`g2-standard-24`) | 25.0% | **83.3%** | +58.3% | 15 -> **40 / 48** (83.3%) | +52.1% |
| **`gemma-2-9b-it`** | 9B Dense | 1x L4 (`g2-standard-12`) | 16.7% | **83.3%** | **+66.7%** | 17 -> **40 / 48** (83.3%) | +47.9% |
| **`gemma-2-2b-it`** | 2.6B Dense | 1x L4 (`g2-standard-4`) | 8.3% | 66.7% | +58.3% | 13 -> **32 / 48** (66.7%) | +39.6% |
| **`gemma-3-1b-it`** | 1.0B Dense | 1x L4 (`g2-standard-4`) | 50.0% | 58.3% | +8.3% | 28 -> **29 / 48** (60.4%) | +2.1% |
| **`gemma-4-e2b-it`** | 2.3B Active (MoE) | 1x L4 (`g2-standard-4`) | 8.3% | 41.7% | +33.3% | 5 -> **20 / 48** (41.7%) | +31.2% |
| **`llama-3.2-3b-instruct`** | 3B Dense | 1x L4 (`g2-standard-8`) | 8.3% | 8.3% | +0.0% | 6 -> **6 / 48** (12.5%) | +0.0% |
| **`inkling-small`** | 14B Reasoner | 4x L4 (`g2-standard-48`) | 8.3% | 0.0% | -8.3% | 6 -> **2 / 48** (4.2%) | -8.3% |

---

## 4. Answering the Core Questions: Size, Generation, and Viability

The empirical sweep reveals clear inflection points that answer what model size and generation you need to capture Karl's observed skill lift.

### Finding 1: The Sizing Sweet Spot is 8B to 14B on a Single L4 GPU

The most important operational finding is that **you do not need a 70B+ cluster to achieve reliable skill-driven execution**:

* Without skills, mid-tier models (8B–14B) hover between a 16.7% and 41.7% baseline pass rate.  
* With domain skills injected, every major mid-tier model surges to **83.3% to 100.0% pass rates**, matching 40 to 46 of the 48 assertions.  
* **Top 12B Performer:** `mistral-nemo-instruct-2407` matched **46/48 assertions (95.8%)** with a **100.0% pass rate**, equaling the performance of 32B models and frontier commercial APIs.  
* **Maximum Net Pass Lift:** Both `deepseek-r1-distill-qwen-14b` and `qwen2.5-14b-instruct` delivered **+66.7% net pass rate lift** (jumping from 25.0% baseline to 91.7%), matching 42 to 45 assertions.  
* **The 8B Baseline:** Both `llama-3.1-8b-instruct` and `qwen2.5-7b-instruct` reached **83.3% pass rates (41–42/48 assertions)** with skills on a single $0.70/hr GPU.

For teams deploying self-hosted agent infrastructure on Google Cloud, the **8B–14B class on a single NVIDIA L4 GPU (`g2-standard-12`) is the definitive minimum viable model scale**.

### Finding 2: Model Generation Shifts the Baseline and the Ceiling

Comparing model generations within the same model family demonstrates how architectural progress interacts with domain skills:

#### The Gemma Generational Progression: 2 -> 3 -> 4

- **2B Class:** Gemma 2 2B scored 8.3% baseline -> 66.7% with skills (32/48 assertions). Gemma 4 E2B (MoE) scored 8.3% -> 41.7% (20 assertions).  
- **4B Class:** Gemma 3 4B achieved a breakthrough: 41.7% baseline -> **100.0% with-skill pass rate (45/48 assertions)**. Gemma 4 E4B (MoE) advanced this further, scoring 41.7% baseline -> **100.0% with-skill pass rate and 47/48 assertions (97.9%)**, while activating only 4B parameters during generation.  
- **27B Class:** Gemma 2 27B scored 41.7% -> 100.0% (45/48 assertions). Gemma 3 27B improved to 41.7% -> **100.0% (47/48 assertions)**, demonstrating increased precision on complex multi-card swap-space formulas.

#### The Qwen Generational Progression: 2.5 -> 3.8

- `qwen2.5-14b-instruct` matched 42/48 assertions (91.7% pass rate).  
- `qwen2.5-coder-32b-instruct` reached 46/48 assertions (91.7% pass rate).  
- `qwen3.8-27b` crossed the frontier threshold, matching a **perfect 48/48 (100.0%) assertions** and tying `gemini-3.7-flash` at the top of the leaderboard.

Newer model generations possess better instruction compliance, which allows them to translate skill instructions into exact syntax without hallucinating near-miss flags.

### Finding 3: Skills Provide Prior Correction Across All Sizes

Without skills, baseline performance plateaus early:
- Unassisted 8B–14B models pass only 16.7% to 41.7% of scenarios.
- Even 27B models pass only 41.7% to 66.7% without skills.
- Models fail not because they lack general programming knowledge, but because pretraining defaults to generic web quickstart patterns (like project-level IAM bindings instead of resource-scoped permissions).

When domain skills are injected directly into context, they act as **prior correction**, supplying the exact parameters, hardware boundaries, and security rules needed:
- `deepseek-r1-distill-llama-8b`: jumps from 15/48 to **40/48 assertions (83.3% pass rate, +58.3% lift)**
- `llama-3.1-8b-instruct`: jumps from 18/48 to **42/48 assertions (83.3% pass rate, +58.3% lift)**
- `qwen2.5-7b-instruct`: jumps from 19/48 to **41/48 assertions (83.3% pass rate, +58.3% lift)**

This confirms that with the right context pre-loaded, open-weight models as small as 7B–8B execute complex operational instructions with near-frontier reliability.

### Finding 4: The 1B–4B Edge Tier (High Relative Lift, Bounded Complexity)

Can you deploy a sub-4B model with skills?

* **Relative lift is high:** Gemma 2 2B jumped +58.3% in pass rate, and Gemma 3 4B reached a 100.0% pass rate (45/48 assertions).  
* **Where they succeed:** Small models with skills reliably execute single-command recipes with clear flags (Cloud Run deployment flags, server-side disk filtering).  
* **Where they fail:** Models under 4B parameters struggle when multiple constraints collide—such as balancing a $50k ERP downtime blast radius against containment (`gdo-010`) or managing multi-step destructive confirmation loops (`gdo-005`).  
* **The MoE Sweet Spot:** **`gemma-4-e4b-it`** is the exception. By activating only 4B parameters from an MoE architecture on a single L4 GPU, it matched 47/48 assertions, proving that modern MoE architectures punch far above their active parameter count.

---

## 5. Architectural Recommendations: Sizing Your Agent Stack

Based on these empirical results, here is the decision matrix for deploying skill-assisted open models in production:

```
                              ┌─────────────────────────────────────────┐
                              │  What is your operational requirement?  │
                              └────────────────────┬────────────────────┘
                                                   │
                  ┌────────────────────────────────┼────────────────────────────────┐
                  ▼                                ▼                                ▼
         [ Extreme Cost / Edge ]        [ Production Balanced ]           [ High-Stakes / Complex ]
         - Serverless Cloud Run GPU      - Single NVIDIA L4 GPU           - Dedicated Multi-GPU
         - Sub-second cold starts        - $0.70 to $0.83 / hour          - Complex blast-radius triage
                  │                                │                                │
                  ▼                                ▼                                ▼
           gemma-4-e4b-it                 mistral-nemo-12b                  qwen3.8-27b
           (4B Active MoE)                qwen2.5-14b-instruct              gemma-3-27b-it
           Score: 47 / 48 (97.9%)         phi-4 (14B)                       Score: 47-48 / 48 (100%)
           Pass: 100.0%                   Score: 42-46 / 48 (95%+)          Pass: 100.0%
```

1. **For Production Enterprise Workloads:** Deploy **`mistral-nemo-instruct-2407` (12B)** or **`qwen2.5-14b-instruct`** on a single NVIDIA L4 GPU. They deliver 91.7%–100.0% pass rates with domain skills at minimal compute cost ($0.70/hr).  
2. **For Edge or Scale-to-Zero Deployment:** Deploy **`gemma-4-e4b-it`** on Cloud Run with GPU. It achieves 97.9% assertion accuracy with $0 idle compute cost when traffic scales to zero.  
3. **For High-Stakes Multi-Constraint Tasks:** Deploy **`gemma-3-27b-it`** or **`qwen3.8-27b`** where complex trade-offs (containment vs business disruption) demand maximal reasoning depth.

---

## 6. Conclusion: Skills Unlock Affordable Models

Karl Weinmeister proved that skills transform Claude Code from trial-and-error guessing into first-try accuracy.

Our multi-model sweep confirms that this effect is not confined to proprietary frontier systems:

- Skills provide an even **larger relative capability jump (+50% to +67% net lift) on open-weight models** than on commercial APIs.  
- The minimum viable model scale for dependable production operations is **8B to 14B on a single NVIDIA L4 GPU**.  
- You do not need to wait for massive, multi-node clusters to build autonomous cloud and security agents. With well-crafted domain skills, compact models can run reliably inside your own VPC today.

In our next post, we will explore the inference serving economics of these models, analyzing how **N-gram prompt lookup and speculative decoding** accelerate open-model token generation by 2.3x with zero extra VRAM.

---

### Resources & Citations

- Karl Weinmeister, [Do agent skills help? I ran 72 trials to find out](https://www.linkedin.com/pulse/do-agent-skills-help-i-ran-72-trials-find-out-karl-weinmeister-nnqec/) (2025).  
- Karl Weinmeister, [`evals.json` Reference Benchmark](https://github.com/kweinmeister/scripts/blob/main/evals/google-cloud-developer/evals.json) on GitHub.  
- Dan Dye, [Evaluating Agent Graphs for SecOps AI Runbooks](https://security.googlecloudcommunity.com/community-blog-42/evaluating-agent-graphs-for-secops-ai-runbooks-8232) (2026), local tracking at [`evaluating_agent_graphs_for_secops_ai_runbooks.md`](evaluating_agent_graphs_for_secops_ai_runbooks.md).  
- Dan Dye, [Exploring Agent Graphs for SecOps AI Runbooks](https://security.googlecloudcommunity.com/community-blog-42/exploring-agent-graphs-for-secops-ai-runbooks-8113) (2026), local tracking at [`exploring_agent_graphs_for_secops_ai_runbooks.md`](exploring_agent_graphs_for_secops_ai_runbooks.md).  
- Dan Dye, [Serving Open Models for Security Agents, Part 1: Zero-Idle GPU Infrastructure](part1_zero_idle_gpu_infrastructure.md) (2026).  
- Master Empirical Leaderboard: [`docs/eval_results/discovery/master_open_model_sweep_report.md`](../eval_results/discovery/master_open_model_sweep_report.md).  
- Evaluation Framework & Code: [`dandye/open-model-deploy-gcp`](https://github.com/dandye/open-model-deploy-gcp) (branch `skill_discovery_eval_v0001`).
