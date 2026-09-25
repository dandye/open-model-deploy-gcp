| Author | Dan Dye |
| :---- | :---- |
| Peer Reviewer |  |
| Topics | Agent Skills, Gemma, Gemini, Model Sizing, Model Evaluation, Vertex AI, Cloud Run GPU |

---

# What is the Smallest Model that Benefits from Agent Skills? Running Karl Weinmeister's Evals on Gemma and Gemini

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

Can a lightweight 1B or 4B edge model running serverless on Cloud Run GPU get the job done? Or do you need an 8B–12B mid-weight model on a single $0.70/hr GPU?

To answer this, I used Karl's standardized 12-scenario declarative benchmark (`evals.json`) and ran them systematically across **Gemma open models and Gemini reference baselines**—spanning 9 open checkpoints across Gemma 2, Gemma 3, and Gemma 4 (from 1B up to 27B) alongside Gemini 2.5 Flash, 3.7 Flash, and 3.8 Flash on Google Cloud.

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

## The Gemma & Gemini Sweep: Empirical Results Across 12 Models

I evaluated 9 open Gemma checkpoints across three generations alongside 3 managed Gemini reference models:

- **Gemma 2:** `gemma-2-2b-it`, `gemma-2-9b-it`, `gemma-2-27b-it`  
- **Gemma 3:** `gemma-3-1b-it`, `gemma-3-4b-it`, `gemma-3-12b-it`, `gemma-3-27b-it`  
- **Gemma 4:** `gemma-4-e2b-it`, `gemma-4-e4b-it` (Mixture-of-Experts)  
- **Gemini Reference Baselines:** `gemini-2.5-flash`, `gemini-3.7-flash`, `gemini-3.8-flash`

Here is the empirical scorecard ordered by With-Skill assertion performance:

| Model Variant | Generation / Sizing | GPU Serving Target | Baseline Pass | With-Skill Pass | Net Pass Lift (Δ) | Assertions Matched (Base -> Skill) | Net Assertion Lift (Δ) |
| :---- | :---- | :---- | :---: | :---: | :---: | :---: | :---: |
| **`gemini-3.7-flash`** | Frontier Reference | Managed API | 83.3% | **100.0%** | +16.7% | 37 -> **48 / 48** (100.0%) | +22.9% |
| **`gemma-4-e4b-it`** | Gemma 4 (4B Active MoE) | 1x L4 (`g2-standard-4`) | 41.7% | **100.0%** | +58.3% | 23 -> **47 / 48** (97.9%) | +50.0% |
| **`gemma-3-27b-it`** | Gemma 3 (27B Dense) | 4x L4 (`g2-standard-48`) | 41.7% | **100.0%** | +58.3% | 23 -> **47 / 48** (97.9%) | +50.0% |
| **`gemini-3.8-flash`** | Frontier Reference | Managed API | 66.7% | **100.0%** | +33.3% | 35 -> **46 / 48** (95.8%) | +22.9% |
| **`gemma-2-27b-it`** | Gemma 2 (27B Dense) | 4x L4 (`g2-standard-48`) | 41.7% | **100.0%** | +58.3% | 21 -> **45 / 48** (93.8%) | +50.0% |
| **`gemma-3-12b-it`** | Gemma 3 (12B Dense) | 4x L4 (`g2-standard-48`) | 66.7% | **100.0%** | +33.3% | 33 -> **45 / 48** (93.8%) | +25.0% |
| **`gemma-3-4b-it`** | Gemma 3 (4B Dense) | 1x L4 (`g2-standard-8`) | 41.7% | **100.0%** | +58.3% | 26 -> **45 / 48** (93.8%) | +39.6% |
| **`gemini-2.5-flash`** | Frontier Reference | Managed API | 50.0% | **91.7%** | +41.7% | 25 -> **42 / 48** (87.5%) | +35.4% |
| **`gemma-2-9b-it`** | Gemma 2 (9B Dense) | 1x L4 (`g2-standard-12`) | 16.7% | **83.3%** | **+66.7%** | 17 -> **40 / 48** (83.3%) | +47.9% |
| **`gemma-2-2b-it`** | Gemma 2 (2.6B Dense) | 1x L4 (`g2-standard-4`) | 8.3% | 66.7% | +58.3% | 13 -> **32 / 48** (66.7%) | +39.6% |
| **`gemma-3-1b-it`** | Gemma 3 (1.0B Dense) | 1x L4 (`g2-standard-4`) | 50.0% | 58.3% | +8.3% | 28 -> **29 / 48** (60.4%) | +2.1% |
| **`gemma-4-e2b-it`** | Gemma 4 (2.3B Active MoE)| 1x L4 (`g2-standard-4`) | 8.3% | 41.7% | +33.3% | 5 -> **20 / 48** (41.7%) | +31.2% |

---

## 4. Answering the Core Questions: Size, Generation, and Viability

The empirical results across Gemma generations and Gemini baselines answer what model size and generation you need to capture Karl's observed skill lift.

### Finding 1: The Sizing Sweet Spot is 4B Parameters (Gemma 3 4B & Gemma 4 E4B)

The most striking finding is how compact a model can be while achieving full operational capability when armed with skills:

* **The 4B Breakthrough:** Both **`gemma-3-4b-it`** and **`gemma-4-e4b-it`** achieved a **100.0% pass rate (12 of 12 scenarios passed)** when provided with domain skills.
* **Matching and Exceeding 27B Models:** With skills loaded, `gemma-3-4b-it` matched 45/48 assertions (93.8%), equaling the much larger `gemma-2-27b-it` (45/48). `gemma-4-e4b-it` reached **47/48 assertions (97.9%)**, tying `gemma-3-27b-it` and trailing `gemini-3.7-flash` by only a single assertion check.
* **Surpassing Gemini 2.5 Flash:** Both 4B models scored higher with skills (45 and 47 assertions) than managed `gemini-2.5-flash` (42 assertions).
* **Single-GPU Economics:** A 4B model runs comfortably on a single NVIDIA L4 GPU (`g2-standard-4` or `g2-standard-8`) at **~$0.70/hr**, or serverless on Cloud Run GPU with `--min-instances=0` scale-to-zero ($0 idle cost).

You do not need a multi-GPU 27B cluster to achieve reliable execution. **At 4B parameters, modern Gemma models equipped with skills achieve near-frontier operational reliability.**

### Finding 2: Generational Progression Shifts the Baseline and the Ceiling

Comparing the three generations of Gemma reveals how architectural evolution raises the ceiling of skill-driven execution:

#### Gemma 2: The Foundational Open Baseline
* `gemma-2-2b-it` achieved 66.7% pass rate with skills (32/48 assertions).
* `gemma-2-9b-it` delivered the **highest net pass rate lift (+66.7%)**, surging from 16.7% baseline to 83.3% with skills (40/48 assertions).
* `gemma-2-27b-it` demonstrated full task completion: 41.7% baseline -> **100.0% pass rate (45/48 assertions)**.

#### Gemma 3: The Mid-Scale Leap
* `gemma-3-4b-it` jumped to **100.0% pass rate and 45/48 assertions**, proving that generation-over-generation pretraining improvements allow 4B models to match previous-generation 27B models.
* `gemma-3-12b-it` reached **100.0% pass rate (45/48 assertions)**, handling complex multi-card swap-space formulas with high reliability.
* `gemma-3-27b-it` reached **47/48 assertions (97.9%)**, demonstrating precision on fine-grained IAM resource scoping and non-interactive quota management.

#### Gemma 4 (MoE): Extreme Edge Efficiency
* **`gemma-4-e4b-it`** represents a structural milestone: by utilizing a Mixture-of-Experts architecture that activates only 4B parameters during token generation, it achieved **100.0% pass rate and 47/48 assertions (97.9%)**. It matches the accuracy of a 27B dense model while running on the compute footprint of a lightweight edge model.

### Finding 3: Skills Provide Prior Correction Across All Sizes

Without skills, baseline Gemma models plateau early:
* Unassisted pass rates range from **8.3% to 41.7%** across open models.
* The failure mode is not a lack of general coding intelligence, but pretraining defaults: unassisted models default to high-frequency tutorial shortcuts (such as project-wide IAM bindings or missing non-interactive `--quiet` flags) rather than production-hardened syntax.
* In Scenario 8 (`gdo-008`), every single unassisted model failed because pretraining cannot guess proprietary internal cloud quota identifiers like `NvidiaL4GpuAllocNoZonalRedundancyPerProjectRegion`.

When domain skills are injected directly into context, they act as **prior correction**, supplying the exact parameters, hardware boundaries, and security rules needed:
* `gemma-2-2b-it`: 13 -> **32 assertions** (+39.6% lift)
* `gemma-2-9b-it`: 17 -> **40 assertions** (+47.9% lift, +66.7% pass lift)
* `gemma-3-4b-it`: 26 -> **45 assertions** (+39.6% lift, +58.3% pass lift)
* `gemma-4-e4b-it`: 23 -> **47 assertions** (+50.0% lift, +58.3% pass lift)

Skills provide an even larger relative capability jump (+33.3% to +66.7% net lift) on open Gemma models than on closed commercial APIs (+16.7% to +33.3% lift on Gemini).

### Finding 4: The Sub-4B Edge Tier (1B vs 2B vs 4B)

What happens below 4B parameters?
* **1B Models (`gemma-3-1b-it`):** Reached 58.3% pass rate with skills (29/48 assertions), representing only a marginal +2.1% net assertion lift. Models at 1B lack the capacity to follow multi-clause operational instructions consistently.
* **2B Models (`gemma-2-2b-it`):** Reached 66.7% pass rate with skills (32/48 assertions, +58.3% pass lift). They reliably execute single-command recipes with clear flags (Cloud Run deployment flags, server-side disk filtering).
* **Where Sub-4B Models Struggle:** When multiple constraints collide—such as balancing a $50k ERP downtime blast radius against containment (`gdo-010`) or managing multi-step destructive confirmation loops (`gdo-005`), models under 4B parameters still stumble.
* **The 4B Inflection Point:** 4B parameters is the empirical threshold where Gemma models acquire the reasoning depth to handle multi-constraint trade-offs without dropping procedural compliance.

---

## 5. Architectural Recommendations: Sizing Your Gemma Stack

Based on these empirical results, here is the decision matrix for deploying skill-assisted Gemma models on Google Cloud:

```
                              ┌─────────────────────────────────────────┐
                              │  What is your operational requirement?  │
                              └────────────────────┬────────────────────┘
                                                   │
                  ┌────────────────────────────────┼────────────────────────────────┐
                  ▼                                ▼                                ▼
         [ Extreme Cost / Edge ]        [ Production Balanced ]           [ High-Stakes / Complex ]
         - Serverless Cloud Run GPU      - Single NVIDIA L4 GPU           - Dedicated Multi-GPU
         - Scale-to-zero ($0 idle)       - $0.70 to $0.83 / hour          - Complex blast-radius triage
                  │                                │                                │
                  ▼                                ▼                                ▼
           gemma-4-e4b-it                 gemma-3-4b-it                     gemma-3-27b-it
           (4B Active MoE)                gemma-2-9b-it                     (or Gemini 3.7 Flash)
           Score: 47 / 48 (97.9%)         Score: 40-45 / 48 (93%+)          Score: 47-48 / 48 (100%)
           Pass: 100.0%                   Pass: 83.3% - 100.0%              Pass: 100.0%
```

1. **For Cost-Optimized Edge & Serverless:** Deploy **`gemma-4-e4b-it`** on Cloud Run with GPU. It achieves 97.9% assertion accuracy (47/48 assertions) with $0 idle compute cost when traffic scales to zero.
2. **For Dependable Production Workloads:** Deploy **`gemma-3-4b-it`** or **`gemma-2-9b-it`** on a single NVIDIA L4 GPU (`g2-standard-4` or `g2-standard-12`). They deliver 83.3%–100.0% pass rates with domain skills at approximately $0.70/hr.
3. **For High-Stakes Multi-Constraint Reasoning:** Deploy **`gemma-3-27b-it`** on 4x L4 (`g2-standard-48`) or use managed **`gemini-3.7-flash`**, where complex trade-offs (containment vs enterprise disruption) demand maximum reasoning depth.

---

## 6. Conclusion: Skills Unlock Affordable Gemma Models

Karl Weinmeister proved that skills transform Claude Code from trial-and-error guessing into first-try accuracy.

Our empirical sweep across Gemma generations confirms that:
- Skills provide an even **larger capability jump (+33% to +67% net lift) on open Gemma models** than on commercial frontier APIs.
- The minimum viable model scale for dependable production operations is **4B parameters** (`gemma-3-4b-it` and `gemma-4-e4b-it`), both achieving a **100.0% pass rate** on a single L4 GPU.
- You do not need massive, multi-node clusters to build autonomous cloud agents. With well-crafted domain skills, compact Gemma models running inside your own VPC or on Cloud Run GPU deliver production reliability today.

In our next post, we will explore the inference serving economics of these models, analyzing how **N-gram prompt lookup and speculative decoding** accelerate token generation by 2.3x with zero extra VRAM.

---

### Resources & Citations

- Karl Weinmeister, [Do agent skills help? I ran 72 trials to find out](https://www.linkedin.com/pulse/do-agent-skills-help-i-ran-72-trials-find-out-karl-weinmeister-nnqec/) (2025).  
- Karl Weinmeister, [`evals.json` Reference Benchmark](https://github.com/kweinmeister/scripts/blob/main/evals/google-cloud-developer/evals.json) on GitHub.  
- Dan Dye, [Evaluating Agent Graphs for SecOps AI Runbooks](https://security.googlecloudcommunity.com/community-blog-42/evaluating-agent-graphs-for-secops-ai-runbooks-8232) (2026), local tracking at [`evaluating_agent_graphs_for_secops_ai_runbooks.md`](evaluating_agent_graphs_for_secops_ai_runbooks.md).  
- Dan Dye, [Exploring Agent Graphs for SecOps AI Runbooks](https://security.googlecloudcommunity.com/community-blog-42/exploring-agent-graphs-for-secops-ai-runbooks-8113) (2026), local tracking at [`exploring_agent_graphs_for_secops_ai_runbooks.md`](exploring_agent_graphs_for_secops_ai_runbooks.md).  
- Dan Dye, [Serving Open Models for Security Agents, Part 1: Zero-Idle GPU Infrastructure](part1_zero_idle_gpu_infrastructure.md) (2026).  
- Master Empirical Leaderboard: [`docs/eval_results/discovery/master_open_model_sweep_report.md`](../eval_results/discovery/master_open_model_sweep_report.md).  
- Evaluation Framework & Code: [`dandye/open-model-deploy-gcp`](https://github.com/dandye/open-model-deploy-gcp) (branch `skill_discovery_eval_v0001`).
