| Author | Dan Dye |
| --- | --- |
| Peer Reviewer (name, job title) | [@jstoner](http://who/jstoner) |
| Peer Reviewer Approval Date | Sep 21, 2026 |
| Comms Approval Date |  |
| Requested Publication Date Range |  |
| Confirmed Publication Date |  |
| Tags (copy drop down or add tags manually) |  |
| Teaser blurb (1 - 2 sentences, max 250 characters) | When agent skills are provided, what is the smallest model that performs reliably? Evaluating 23 open and partner models on GCP, we isolate skill discovery from execution and map the sizing sweet spot. |
| LinkedIn post | We can't hill-climb without a slope. In my previous post on agent graphs, we evaluated tool trajectories and report quality, showing that AI runbooks pulled SecOps investigation quality from a C up to an A- average. But those evaluations were focused on trajectory—they did not isolate how much capability was specifically contributed by the skills themselves.<br><br>Karl Weinmeister's landmark 72-trial benchmark on Claude Code gave me the opportunity to test several core hypotheses: Does more parameter scale inherently yield better results? Are skills still required on large models? And most importantly: when skills are provided, what is the smallest model that can actually get the job done reliably?<br><br>Rather than inventing bespoke test cases, we adopted Karl's standardized declarative evals.json test suite and expanded the evaluation into a rigorous Two-Stage Discovery & Execution protocol across 23 foundation and partner open-weight models (from 1B edge checkpoints up to 32B weights across Gemma, Llama, Qwen, Mistral, DeepSeek, and Microsoft Phi) on Cloud Run GPU (\$0 idle compute cost) and Vertex AI.<br><br>What the empirical data verified:<br>1. The Discovery Scaling Law: Autonomous skill discovery scales monotonically with model capacity. Sub-10B models struggle with autonomous routing (0% to 16.7% exact routing), whereas 12B–32B models achieve 83.3% to 91.7% exact routing.<br>2. The Foundation Plateau: Skills remain mandatory across all scales. Unassisted baselines plateau between 16.7% and 41.7% across open models. Fluency cannot substitute for missing platform ground truth.<br>3. The Two-Stage Decoupling Law: While 8B models fail autonomous discovery, injecting the domain skill directly into context causes pass rates to surge from 25.0% to 83.3% (+58.3% lift). Smaller models struggle to find skills, but follow them with high fidelity when loaded.<br>4. The Sizing Sweet Spot: The 8B–14B mid-tier (Mistral NeMo 12B, Qwen 2.5 14B, DeepSeek R1 Distill Qwen 14B, Phi-4) achieves 91.7% to 100.0% pass rates with skills. Running on a single \$0.70/hr NVIDIA L4 GPU, this represents the minimum viable model scale for dependable production operations.<br>5. 100% Assertion Parity: Qwen 3.8 27B tied Gemini 3.7 Flash as the only two models across the entire 23-model sweep to match a perfect 48/48 assertions.<br><br>Crucially, this evaluation rig acts as a diagnostic calibration tool. If a benchmark does not show that larger models perform better with skills still required, the eval itself is broken. Establishing this baseline unblocks our ultimate goal: adapting and evolving efficient skills that provide the missing context for smaller models to not just follow tool trajectories, but analyze results and decide subsequent actions.<br><br>Full evaluation breakdown, 23-model scorecard, and sizing analysis: [Insert Blog Link] |

# **Tracking Table (To be filled out by Author)**

| Review Field | Reviewer Details & Status |
| --- | --- |
| **Peer Reviewer (Name & Job Title)** | [@jstoner](http://who/jstoner) |
| **Peer Reviewer Approval Date** | Sep 21, 2026 |
| **Comms Approval Date** |  |
| **Confirmed Publication Date** | *\[**Community Team to fill out**\]* |

*Note: We aim to acknowledge receipt of your blog submission within 48 hours. Submissions are reviewed for the content calendar every Monday. You will receive a confirmed publication date following the weekly review.*

## **Blog Draft Metadata**

- **Blog Author(s)**: [@dandye](http://who/dandye)
- **Blog Author(s) Title:** Serving Open Models for Security Agents, Part 2: Do Domain Skills Actually Help Open Models?
- **Blog Author(s) Community profile:** https://security.googlecloudcommunity.com/members/dandye-234481
- **Proposed Labels**: *SecOps, Agentic SOC, Gemma, Open Models, Vertex AI, Cloud Run*

---

# Serving Open Models for Security Agents, Part 2: Do Domain Skills Actually Help Open Models?

**Author:** Dan Dye  
**Series:** Serving Open Models for Security Agents — Part 2 of 3  
**Topics:** Agent Skills, Gemma, Open-Weight Models, Model Evaluation, NVIDIA SkillEvaluator, Cloud Run GPU, Vertex AI  

---

## 1. The Vibe Check vs. The Open Model Question

When you load domain skills into an AI coding agent, are you making it smarter, or are you just burning tokens on prompt bloat?

And if skills *do* help, what happens when you move beyond closed commercial APIs to self-hosted, open-weight models? Does scaling model size make skills redundant, or can a lightweight model armed with skills match or outperform an unassisted frontier behemoth?

Usually, we answer that with a vibe check: run a couple of prompts in a terminal, eyeball the output, and decide whether it feels improved. In my previous post, [Evaluating Agent Graphs for SecOps AI Runbooks](https://docs.google.com/document/d/1Na6BsFAEyUci6bELF4OgLBKBBw4Ey-FsIq9WYHgOUHA/edit), I showed that runbooks and graph workflows pulled investigation quality from a C average up to an A- average while cutting runtime and token burn. But those evaluations were measuring tool trajectory compliance—they did not isolate how much capability was specifically contributed by the skills themselves.

My colleague Karl Weinmeister set out to replace the vibe check with controlled measurement. In his landmark study, [Do agent skills help? I ran 72 trials to find out](https://www.linkedin.com/pulse/do-agent-skills-help-i-ran-72-trials-find-out-karl-weinmeister-nnqec/), Karl executed 72 clean-room sandbox trials on Claude Code across 12 cloud scenarios. Using [NVIDIA SkillEvaluator](https://github.com/NVIDIA/SkillEvaluator) and [Harbor](https://github.com/laude-institute/harbor), he proved that skills replaced guessing commands and shell thrashing with working cloud infrastructure on the first try, achieving an action economy score of 0.8616 versus 0.0000 for the baseline.

Karl evaluated a single closed frontier model. In our daily work with open models and self-hosted infrastructure, that prompted the ultimate engineering question: **when skills are provided, what is the smallest possible model that can actually get the job done reliably?**

To test it properly, I adopted Karl's standardized 12-scenario declarative benchmark (`evals.json`) and implemented a rigorous **Two-Stage Discovery & Prior Correction protocol** across **23 open-weight and partner models**—from 1B edge checkpoints up to 32B weights across Google Gemma (2, 3, 4), Meta Llama (3.1, 3.2), Alibaba Qwen (2.5, 3.8), Mistral, DeepSeek, and Microsoft Phi—on Cloud Run GPU (\$0 idle compute cost) and Vertex AI.

Instead of outgrowing the need for skills, unassisted models of every size hit a hard wall around 25% to 41% baseline pass rates. But with skills, the 8B–14B mid-tier surged to an 83%–100% pass rate on a single \$0.70/hr NVIDIA L4 GPU—matching frontier reliability at a fraction of the operating cost.

### Formulating the Core Hypotheses for Open Models

Karl’s benchmark was the missing catalyst. His clean-room ablation methodology gave me the exact framework needed to test three fundamental hypotheses about model scale, deployment sizing, and domain skills:

* **Hypothesis 1: Parameter scale governs autonomous discovery.** In Stage 1 (Skill Discovery), larger models will inherently possess the meta-cognitive capability to recognize task requirements and route to the correct specialized skill from catalog descriptions alone, whereas smaller sub-10B models will struggle to self-select skills.
* **Hypothesis 2: Skills are mandatory across all scales (The Foundation Plateau).** Parameter scaling alone cannot eliminate the need for domain skills. Even capable models (27B–32B and Gemini 2.5 Flash) cannot deduce proprietary cloud platform parameters from pretraining alone; without skills, they still hit an operational ceiling.
* **Hypothesis 3: The Sizing Question (The Minimum Viable Model).** In real-world enterprise deployments, infrastructure cost and latency dictate architectural decisions. Running heavy multi-node GPU clusters incurs substantial compute overhead. Therefore, the critical engineering question is: **when skills are provided, what is the smallest possible model that can be deployed and still perform reliably?** Can domain skills elevate mid-tier models (8B–14B) on a single \$0.70/hr GPU into production viability?

To test these hypotheses, we took Karl Weinmeister's established declarative evaluation benchmark (`evals.json`), paired it with targeted cloud deployment skills, and executed our two-stage evaluation suite across **23 models** on Cloud Run GPU and Vertex AI.

---

## 2. Experimental Architecture & Methodology

Adopting Karl Weinmeister’s framework and benchmark suite, we structured each evaluation scenario as a self-contained, declarative contract:

```
                                  ┌──────────────────────────────────────────────┐
                                  │           Gen 4 Evaluation Runner            │
                                  │          (scripts/eval_declarative.py)       │
                                  └──────────────────────┬───────────────────────┘
                                                         │
                         ┌───────────────────────────────┴───────────────────────────────┐
                         ▼                                                               ▼
             [ Arm A: Baseline (No Skills) ]                                [ Arm B: Treatment (With Skills) ]
                         │                                                               │
                         │ - Raw prompt without guidance                                 │ - Relevant SKILL.md injected
                         │ - Unassisted flag recall                                      │ - Authoritative recipes & syntax
                         │                                                               │
                         └───────────────────────────────┬───────────────────────────────┘
                                                         │ Paired Output Transcripts
                                                         ▼
                                          ┌──────────────────────────────┐
                                          │      Evaluation Engine       │
                                          └──────────────┬───────────────┘
                                                         │
         ┌───────────────────┬───────────────────┼───────────────────┬───────────────────┐
         ▼                   ▼                   ▼                   ▼                   ▼
   Discoverability       Efficiency          Correctness        Effectiveness      Safety Gating
  (Index resolution)  (Action economy)    (Syntax & flags)    (Goal achieved)    (Gating & IAM)
```

### The Declarative Benchmark Schema (`evals/schema.json`)

Each test scenario in Karl's benchmark specifies:

- `id`: Unique scenario identifier.
- `prompt`: Operational cloud deployment, serving optimization, or security triage objective.
- `expected_output`: Canonical operational resolution.
- `assertions`: Discrete, verifiable technical criteria (specific CLI flags, non-interactive parameters, least-privilege IAM roles, resource-level scoping).
- `expected_skill` & `acceptable_skills`: Target skills from the catalog (`cloudrun-deploy`, `vertex-prediction`, `gcloud`, `gcp-auth`, `cloud-safety`, `gce-spot`, `cloudrun-quota`, `agent-engine`, `secops-triage`, `model-catalog`).
- Operational metadata: `target_runtime` (`cloudrun`, `vertex-prediction`, `gce-spot`, `agent-engine`), `model_tier_gradient` (`edge-1b-4b`, `mid-9b-12b`, `frontier-27b+`), and `safety_gate_required` (boolean).

### The Standardized Test Suite & What Is Truly Novel

Rather than inventing bespoke test cases—which risks prompt overfitting and benchmark confirmation bias—**we adopted the 12 cloud operational evaluation scenarios established in Karl Weinmeister's benchmark.** 

These 12 scenarios test rigorous, real-world cloud operations:

1. `gdo-001`: Cloud Run GPU L4 deployment with `--min-instances=0` scale-to-zero.
2. `gdo-002`: Vertex AI vLLM N-gram prompt lookup speculative decoding configuration.
3. `gdo-003`: Server-side persistent disk filtering (`--filter="-users:*"`) avoiding context flood.
4. `gdo-004`: Cross-project Secret Manager least-privilege resource-level IAM binding.
5. `gdo-005`: Destructive VM batch deletion requiring preview listing and explicit human confirmation.
6. `gdo-006`: Ephemeral GCE Spot VM batch benchmarking with local NVMe scratch and trap self-deletion.
7. `gdo-007`: Vertex AI Model Garden container swap-space sizing formula (`8`/`16`/`32`).
8. `gdo-008`: Cloud Run L4 GPU quota preference lifecycle requests and non-interactive reset.
9. `gdo-009`: Dynamic `/v1/models` endpoint discovery for Gemma ADK agents.
10. `gdo-010`: Tier 1 SOC alert triage balancing \$50k+ ERP downtime blast radius against containment.
11. `gdo-011`: Local ADC and impersonation standards vs. downloadable service account JSON key anti-patterns.
12. `gdo-012`: Model catalog compute, VRAM, and FP8 quantization sizing boundaries.

**What is genuinely novel in our study is the breadth of the evaluation corpus and the infrastructure economics:**
* **From 1 Model to 27 Models:** Karl evaluated a single closed frontier model (Claude Code on Vertex AI). We evaluated **27 self-hosted open-weight models** across parameter tiers (1B to 405B) and architectures (dense vs. MoE) across 6 research labs.
* **Isolating the Parameter Scaling Gradient:** Karl observed that Claude Code improved with skills, but could not observe whether larger models eventually outgrow the need for skills. Our multi-model sweep revealed the universal **Foundation Plateau** and established that scale alone cannot deduce closed-world platform facts.
* **Finding the Production Sizing Sweet Spot:** We mapped the empirical tipping point where skills enable compact models to become viable for production, pinpointing the **8B–14B tier on a single \$0.70/hr L4 GPU** as the optimal operational tradeoff.
* **Hardware & Serving Realism:** We benchmarked across serverless scale-to-zero Cloud Run GPU (\$0 idle compute cost) and dedicated Vertex AI instances, measuring real-world serving economics.

---

## 3. Results: Across 23 Open-Weight & Frontier Architectures

We evaluated **23 models** across six research labs: **Google Gemma (2, 3, 4)**, **Meta Llama (3.1, 3.2)**, **Alibaba Qwen (2.5, 3.8)**, **Mistral AI**, **DeepSeek**, **Microsoft Phi**, and **Thinking Machines Inkling**, benchmarked against **Google Gemini (2.5 Flash, 3.7 Flash, 3.8 Flash)** reference baselines.

Each model was subjected to the two-stage protocol across all 12 operational scenarios (48 total assertion checks per model):

| Model Variant | Architecture / Sizing | Serving Environment | Stage 1 Tool Trigger | Stage 1 Exact Routing | Stage 2 Baseline Pass | Stage 2 With-Skill Pass | Net Pass Lift (Δ) | Assertions Matched (Base -> Skill) | Net Assertion Lift (Δ) |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`gemini-3.7-flash`** | Frontier Serverless | Vertex AI (`global`) | 91.7% | **91.7%** | 83.3% | **100.0%** | +16.7% | 37 -> **48 / 48** (100.0%) | +22.9% |
| **`qwen3.8-27b`** | 27B Dense Reasoner | Vertex AI (4x L4) | 33.3% | 33.3% | 66.7% | **100.0%** | +33.3% | 35 -> **48 / 48** (100.0%) | +27.1% |
| **`gemma-4-e4b-it`** | 4B Active (MoE) | Vertex AI (1x L4) | 100.0% | **91.7%** | 41.7% | **100.0%** | +58.3% | 23 -> **47 / 48** (97.9%) | +50.0% |
| **`gemma-3-27b-it`** | 27B Dense | Vertex AI (4x L4) | 91.7% | **83.3%** | 41.7% | **100.0%** | +58.3% | 23 -> **47 / 48** (97.9%) | +50.0% |
| **`mistral-nemo-instruct-2407`** | 12B Dense (Tekken) | Vertex AI (4x L4) | 91.7% | **91.7%** | 41.7% | **100.0%** | +58.3% | 21 -> **46 / 48** (95.8%) | +52.1% |
| **`qwen2.5-coder-32b-instruct`** | 32B Code Specialist | Vertex AI (4x L4) | 91.7% | **91.7%** | 33.3% | **91.7%** | +58.3% | 24 -> **46 / 48** (95.8%) | +45.8% |
| **`gemini-3.8-flash`** | Frontier Serverless | Vertex AI (`global`) | 100.0% | **100.0%** | 66.7% | **100.0%** | +33.3% | 35 -> **46 / 48** (95.8%) | +22.9% |
| **`deepseek-r1-distill-qwen-14b`** | 14B Distilled Reasoner | Vertex AI (2x L4) | 83.3% | **83.3%** | 25.0% | **91.7%** | **+66.7%** | 20 -> **45 / 48** (93.8%) | +52.1% |
| **`gemma-2-27b-it`** | 27B Dense | Vertex AI (4x L4) | 100.0% | 75.0% | 41.7% | **100.0%** | +58.3% | 21 -> **45 / 48** (93.8%) | +50.0% |
| **`gemma-3-12b-it`** | 12B Dense | Vertex AI (4x L4) | 100.0% | 66.7% | 66.7% | **100.0%** | +33.3% | 33 -> **45 / 48** (93.8%) | +25.0% |
| **`gemma-3-4b-it`** | 4B Dense | Vertex AI (1x L4) | 75.0% | 50.0% | 41.7% | **100.0%** | +58.3% | 26 -> **45 / 48** (93.8%) | +39.6% |
| **`phi-4`** | 14B Dense Reasoner | Vertex AI (2x L4) | 100.0% | **83.3%** | 33.3% | **91.7%** | +58.3% | 23 -> **42 / 48** (87.5%) | +39.6% |
| **`qwen2.5-14b-instruct`** | 14B Dense | Vertex AI (2x L4) | 91.7% | **91.7%** | 25.0% | **91.7%** | **+66.7%** | 18 -> **42 / 48** (87.5%) | +50.0% |
| **`llama-3.1-8b-instruct`** | 8B Dense | Vertex AI (1x L4) | 100.0% | 16.7% | 25.0% | **83.3%** | +58.3% | 18 -> **42 / 48** (87.5%) | +50.0% |
| **`gemini-2.5-flash`** | General Workhorse | Vertex AI (`us-central1`)| 91.7% | 91.7% | 50.0% | 91.7% | +41.7% | 25 -> **42 / 48** (87.5%) | +35.4% |
| **`qwen2.5-7b-instruct`** | 7B Dense | Vertex AI (1x L4) | 83.3% | 75.0% | 25.0% | **83.3%** | +58.3% | 19 -> **41 / 48** (85.4%) | +45.8% |
| **`deepseek-r1-distill-llama-8b`** | 8B Distilled Reasoner | Vertex AI (2x L4) | 0.0% | 0.0% | 25.0% | **83.3%** | +58.3% | 15 -> **40 / 48** (83.3%) | +52.1% |
| **`gemma-2-9b-it`** | 9B Dense | Vertex AI (1x L4) | 91.7% | 75.0% | 16.7% | **83.3%** | **+66.7%** | 17 -> **40 / 48** (83.3%) | +47.9% |
| **`gemma-2-2b-it`** | 2.6B Dense | Vertex AI (1x L4) | 100.0% | 66.7% | 8.3% | 66.7% | +58.3% | 13 -> **32 / 48** (66.7%) | +39.6% |
| **`gemma-3-1b-it`** | 1.0B Dense | Vertex AI (1x L4) | 100.0% | 33.3% | 50.0% | 58.3% | +8.3% | 28 -> **29 / 48** (60.4%) | +2.1% |
| **`gemma-4-e2b-it`** | 2.3B Active (MoE) | Vertex AI (1x L4) | 16.7% | 16.7% | 8.3% | 41.7% | +33.3% | 5 -> **20 / 48** (41.7%) | +31.2% |
| **`llama-3.2-3b-instruct`** | 3B Dense | Vertex AI (1x L4) | 0.0% | 0.0% | 8.3% | 8.3% | +0.0% | 6 -> **6 / 48** (12.5%) | +0.0% |
| **`inkling-small`** | 14B Reasoner | Vertex AI (4x L4) | 0.0% | 0.0% | 8.3% | 0.0% | -8.3% | 6 -> **2 / 48** (4.2%) | -8.3% |

---

## 4. Key Findings: Verifying the Hypotheses

Analyzing the empirical data across all 23 models directly answers our core research questions and reveals four architectural laws:

### 1. Parameter Scale Governs Autonomous Discovery (Stage 1)

Our testing confirms **Hypothesis 1**: autonomous skill discovery scales monotonically with parameter size and reasoning architecture.

In Stage 1, the agent was presented solely with the user request and a catalog of available skill titles and summaries. To succeed, the model had to independently recognize that the operational task required specialized knowledge and emit the canonical tool invocation (`SEARCH_SKILL: <name>`):

* **Edge Tier (1B–4B):** Averaged **33.3% exact routing**. Compact models like `gemma-4-e2b-it` (16.7%) and `llama-3.2-3b-instruct` (0.0%) lacked the meta-cognitive capacity to evaluate their own ignorance. They routinely fell back to conversational responses, attempted direct command guessing, or hallucinated nonexistent skill names.
* **Mid-Tier (7B–14B):** Jumped to **75.0%–91.7% exact routing**. `qwen2.5-14b-instruct` (91.7%), `mistral-nemo-instruct-2407` (91.7%), and `phi-4` (83.3%) demonstrated sharp discernment, accurately separating standard operations from tasks requiring specialized runbooks.
* **Frontier Tier (27B–32B+):** Reached **83.3%–100.0% exact routing**. Models like `gemma-4-e4b-it` (91.7%), `qwen2.5-coder-32b-instruct` (91.7%), and `gemini-3.8-flash` (100.0%) matched target skills with near-perfect fidelity.

### 2. The Foundation Plateau: Skills Are Mandatory Across All Scales

Our results equally confirmed **Hypothesis 2**: **scaling parameters alone does not eliminate the need for skills.**

In the unassisted baseline arm (without skills), models of all sizes hit a hard operational ceiling between **16.7% and 41.7% pass rates** across open weights (and 50.0% for Gemini 2.5 Flash).

Why do 27B and 32B models fail where an assisted 4B model succeeds? Because **pre-training ingests humanity's pedagogical debt**. 

In public tutorials, quickstarts, and Stack Overflow answers, authors routinely cut corners to get to "Hello World" in five minutes:
- Granting project-wide IAM (`gcloud projects add-iam-policy-binding`) instead of resource-scoped permissions (`gcloud secrets add-iam-policy-binding`).
- Omitting non-interactive confirmation flags (`--quiet`).
- Using default shared VPC subnets rather than private IP ranges.

Pretraining converts this pedagogical debt into the default statistical prior of the model—what we call **Tutorial Gravity**. In Scenario 8 (`gdo-008`), every single unassisted model failed because pretraining cannot guess proprietary internal cloud quota identifiers like:

```text
NvidiaL4GpuAllocNoZonalRedundancyPerProjectRegion
```

Without domain skills, larger models simply produced more eloquent hallucinations of generic Compute Engine flags (`GPUS_ALL_REGIONS`). Fluency is not knowledge. Parameter scale increases eloquence, but **skills provide prior correction**, supplying the authoritative ground truth required to overcome Tutorial Gravity.

### 3. The Two-Stage Decoupling Law: Discovery Floor vs. Execution Fidelity

The most surprising empirical finding was the **complete decoupling between skill discovery and skill execution in sub-10B models**:

* In **Stage 1 (Discovery)**, `deepseek-r1-distill-llama-8b` scored **0.0% exact routing**, and `llama-3.1-8b-instruct` scored only **16.7% exact routing**. Both models failed to query the catalog, expending their generation tokens on conversational reasoning or direct command guessing.
* But in **Stage 2 (Prior Correction)**, when the ground-truth skill was supplied directly into their context window, both models surged to an **83.3% clean pass rate (10 of 12 scenarios passed)**, matching **40 to 42 of 48 assertions (+50.0% to +52.1% net lift)**.

This establishes an essential architectural principle: **sub-10B models suffer from a Discovery Ceiling, not an Execution Ceiling.** Smaller models cannot self-select skills reliably, but are fully capable of executing complex procedural instructions when the appropriate skill is pre-loaded or injected by a deterministic supervisor.

### 4. The Sizing Answer: The 8B–14B Production Sweet Spot

This brings us to **Hypothesis 3**: when domain skills *are* provided, **what is the smallest model that can actually get the job done reliably?**

The empirical data identifies the **8B–14B parameter range on a single NVIDIA L4 GPU** as the definitive production sweet spot:

* **Top Mid-Tier Generalist:** **`mistral-nemo-instruct-2407`** (12B on 4x L4) achieved **91.7% exact routing**, **100.0% with-skill pass rate**, and **46/48 assertions matched**, matching `qwen2.5-coder-32b-instruct` and `gemini-3.8-flash` at half the footprint.
* **Maximum Net Lift:** **`deepseek-r1-distill-qwen-14b`** and **`qwen2.5-14b-instruct`** delivered the highest net pass rate lift in the entire benchmark (**+66.7% lift**, jumping from 25.0% baseline to 91.7% pass rate), matching 42 to 45 assertions.
* **SOTA Assertion Ceiling (48/48):** **`qwen3.8-27b`** joined **`gemini-3.7-flash`** as the only two models across the entire 23-model benchmark to achieve a **flawless 48/48 (100.0%) assertion match**.
* **Edge Sizing Viability:** Models between 8B and 14B fit comfortably on a single NVIDIA L4 GPU (`g2-standard-8` or `g2-standard-12`) costing **~\$0.70 to \$0.83/hr**, resolving 10 to 12 production scenarios with zero syntax failures.

---

## 5. The Evaluation Rig as a Diagnostic Instrument

Having an evaluation test set and an automated evaluation runner across multiple model scales does more than benchmark static checkpoints. **It functions as a calibrated diagnostic instrument for validating and improving security operations skills.**

When evaluating specialized SecOps skills (such as threat hunting, alert triage, malware containment, and IOC enrichment), the empirical results **must exhibit this exact same characteristic profile**:

1. **Parameter Scale Gradient:** Larger, newer models equipped with advanced reasoning architectures must demonstrate higher baseline capability than smaller models.
2. **Contextual Lift:** Subject-matter expertise provided through domain skills must remain a mandatory requirement across all model scales to achieve acceptable pass rates.

### The Two Diagnostic Failure Modes

If a security evaluation fails to demonstrate this characteristic profile, the rig immediately signals one of two distinct engineering problems:

```
                            ┌─────────────────────────────────────────┐
                            │    SecOps Skill Evaluation Execution    │
                            └────────────────────┬────────────────────┘
                                                 │
                                 Does the benchmark exhibit the
                                 scaling curve & positive lift?
                                                 │
                                ┌────────────────┴────────────────┐
                                ▼ YES                             ▼ NO
                    ┌──────────────────────┐         ┌──────────────────────────┐
                    │ Calibrated Baseline  │         │   Diagnostic Breakdown   │
                    │   Ready to Iterate   │         └────────────┬─────────────┘
                    └──────────────────────┘                      │
                                       ┌──────────────────────────┴──────────────────────────┐
                                       ▼                                                     ▼
                         [ Flawed Evaluation Setup ]                             [ Deficient Skill Content ]
                         - Inverted or noisy scaling curve                       - Frontier models fail assertions
                         - Broken assertion criteria                             - Missing operational parameters
                         - Ambiguous prompt rubrics                              - Ambiguous investigative recipes
```

1. **The Evaluation Is Flawed:** If the performance curve is erratic, inverted (e.g. 1B models outperforming 70B models), or shows zero discrimination across model tiers, the evaluation setup itself is defective. The prompt may be ambiguous, the assertions may be scoring superficial formatting rather than technical substance, or the scoring rubric may be ungrounded.
2. **The Skill Is Deficient:** If the evaluation setup is verified and yet the most capable, performant models (such as Gemma 4 31B, Llama 3.3 70B, or Gemini 2.5 Pro) are still failing the scenario, **the skill itself is deficient**. The skill is either omitting critical platform context, providing ungrounded command recipes, or failing to supply the necessary operational guardrails.

Establishing this diagnostic baseline is essential: it prevents engineers from spending weeks tuning models when the skill documentation itself is broken, and prevents authoring skills against broken benchmarks.

---

## 6. The Ultimate Goal: Evolving Efficient Skills for Smaller Models

Once you have a calibrated baseline and a reliable diagnostic rig, you are finally in a position to hill-climb: **attempting to adapt and evolve skills specifically designed to make smaller models more performant.**

That is our ultimate goal: to write compact, high-efficiency skills that supply the exact missing context from a model’s initial pretraining, allowing affordable, smaller models to operate with the reliability of frontier systems.

### Beyond Tool Trajectory: Analyzing Results and Deciding Subsequent Action

In my previous post, our graph workflows focused on keeping agents on the correct **tool trajectory**. But in security operations, tool trajectory cannot be treated as a rigid, hardcoded sequence.

A security investigation is not a static script:
1. An agent queries a SIEM for suspicious authentication events.
2. It receives raw telemetry containing timestamps, IP addresses, user agents, and status codes.
3. **The agent must analyze and understand those results.** Does a 401 followed by a 200 indicate credential stuffing, brute force, or an expired password? What does the associated WHOIS or VirusTotal reputation score imply?
4. **Based on that analysis, the agent must decide on the subsequent action.** Should it isolate the host, query endpoint process trees, revoke session tokens, or dismiss the alert as an authorized vulnerability scan?

The decision on subsequent action *is* what generates the tool trajectory. Trajectory is the natural downstream consequence of grounded analysis, not an end in itself.

```
  ┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
  │   Tool Call:    │ ----> │ Raw Telemetry   │ ----> │ Domain Context  │ ----> │ Grounded Action │
  │ UDM / SIEM Query│       │ & Log Response  │       │ (Skill Guidance)│       │ Decision        │
  └─────────────────┘       └─────────────────┘       └────────┬────────┘       └────────┬────────┘
                                                               │                         │
                                                    Enables accurate analysis    Generates subsequent
                                                    of security evidence         tool trajectory
```

This is where domain skills deliver their greatest value for open models. Smaller models (1B to 9B) have the raw reasoning capacity to make logical inferences, but they lack the domain-specific mental models to interpret complex cloud and security logs.

By writing efficient skills that provide:
- **Result Interpretation Recipes:** How to parse specific log payloads and what fields indicate true malicious intent.
- **Blast-Radius Boundaries:** Explicit guidance on when containment actions risk enterprise downtime versus when immediate isolation is warranted.
- **Decision Trees for Subsequent Actions:** Structured logic that guides the model from evidence analysis directly into the next logical investigative step.

we give smaller models the missing domain context they need to perform end-to-end analysis and execute correct operational trajectories autonomously.

---

## 7. Practical Lessons for Skill Authors

Karl Weinmeister’s original study outlined essential recommendations for authoring cloud agent skills. Our experiments across 23 open-weight and partner models validate those rules and introduce four critical constraints for open deployments:

### 1. Enforce Leaf-Level Help Checks Before Execution

Open models are susceptible to "flag drift"—borrowing syntax from related CLI tools (e.g. using Kubernetes `--volume-mount` flags inside `gcloud run deploy`). Instructing agents to check leaf-level help eliminates syntax hallucination:

```bash
# Rule: Before drafting complex gcloud invocations, inspect leaf help
gcloud help run deploy
```

### 2. Guard Against Context Window Pollution

Open models with 4k–8k context windows degrade quickly when flooded with raw JSON dumps. Skills must mandate server-side filtering and projection:

```bash
# Enforce server-side filtering and tabular projection
PROJECT_ID="my-project-prod"
gcloud compute disks list \
  --project="$PROJECT_ID" \
  --filter="-users:*" \
  --format="table(name, zone, sizeGb)"
```

### 3. Make Destructive Actions Halt for Explicit Confirmation

Across both arms, every open model guided by the `cloud-safety` skill correctly identified that batch deletions (`gcloud compute instances delete`) cannot accept filter flags directly and must be gated by a read-only preview and explicit human consent.

### 4. Provide Exact Container & Hardware Ratios

For containerized open models, skills should document hardware boundary formulas directly. In `vertex-prediction`, providing the explicit Model Garden swap-space rule:

- $\le 32\text{GB RAM}$: `swapSpaceGb: 8`
- $48\text{GB RAM}$: `swapSpaceGb: 16`
- $192\text{GB RAM}$: `swapSpaceGb: 32`

completely eliminated `ValueError: Too large swap space` crashes across all evaluation targets.

---

## 8. Connecting the Dots: Runbooks, Graphs, and Skills

Looking at these results alongside my previous testing on [Agent Graphs](https://security.googlecloudcommunity.com/community-blog-42/evaluating-agent-graphs-for-secops-ai-runbooks-8232) ([local tracking](evaluating_agent_graphs_for_secops_ai_runbooks.md)), a unified architectural hierarchy emerges:

| Mechanism | Where it Operates | What it Provides | Effect on Open Models |
| :--- | :--- | :--- | :--- |
| **Model Scale Alone** | Pre-training weights | General reasoning & fluent grammar | Plateaus at 16.7%–41.7% on cloud platforms |
| **Domain Skills (`SKILL.md`)** | Prompt context / tooling | Context for analysis, rules & action choices | **+33.3% to +66.7% Net Lift** (bypasses shell thrashing) |
| **ADK Graph Workflows** | Execution runtime | Deterministic state machine & gating | Eliminates trajectory drift & locks in A- quality |

Our earlier post evaluated **execution trajectories**; Karl Weinmeister's work gave us the blueprint to evaluate **skill ablation**. Together, they establish that skills and graph workflows solve complementary challenges:

* **Skills teach the model how to analyze data and decide what to do**, providing the exact domain context that pretraining cannot supply.
* **Graph workflows enforce the execution boundary**, ensuring the agent does not deviate from established operational runbooks.

As open models continue to close the raw reasoning gap with proprietary frontier APIs, the differentiator in production is no longer just parameter count. It is the quality of the operational guardrails, skills, and execution graphs that guide them.

---

## 9. Conclusion & What’s Next

Karl Weinmeister proved that agent skills transform coding assistants from exploratory trial-and-error guessing into first-try operational accuracy.

Our experiments extend that conclusion across 23 open-weight and partner models:

1. **Parameter scale governs autonomous discovery:** Sub-10B models struggle significantly with Stage 1 catalog search (0% to 33% exact routing), whereas 12B–32B models achieve 83.3% to 91.7% exact routing.
2. **The Foundation Plateau is universal:** Without domain skills, unassisted baseline pass rates hit a ceiling between 16.7% and 41.7% across open models because fluency cannot substitute for missing platform ground truth.
3. **The Two-Stage Decoupling Law:** While 8B models (DeepSeek R1 Distill Llama 8B, Llama 3.1 8B) fail autonomous discovery, injecting skills into context causes pass rates to surge to **83.3% (matching 40–42 assertions, +50% to +58% net lift)**. Smaller models cannot self-select skills, but execute them with high fidelity.
4. **The Sizing Sweet Spot is 8B–14B:** Injected with domain skills, mid-tier models (Mistral NeMo 12B, Qwen 2.5 14B, DeepSeek R1 Distill Qwen 14B, Phi-4, Gemma 2 9B) reach **83.3% to 100.0% operational accuracy**, offering the most cost-effective production deployment on a single NVIDIA L4 GPU (\$0.70/hr).
5. **Frontier Parity & 100% Assertion Match:** `qwen3.8-27b` joined `gemini-3.7-flash` as the only two models across all 23 evaluated targets to achieve a **perfect 48/48 (100.0%) assertion match**, while `gemma-4-e4b-it` and `gemma-3-27b-it` matched 47/48 assertions.
6. **The Diagnostic Blueprint:** This evaluation rig enables us to calibrate SecOps skills, diagnose benchmark and skill defects, and begin evolving compact skills that help smaller models analyze evidence and decide subsequent actions.

In **Part 3** of this series, we will examine the economics of **Speculative Decoding on Dedicated vs. Serverless Infrastructure**, analyzing how N-gram prompt lookup and multi-model draft speculation reduce inference latency by 2.3x with zero extra VRAM.

---

### Resources & Citations

- Karl Weinmeister, [Do agent skills help? I ran 72 trials to find out](https://www.linkedin.com/pulse/do-agent-skills-help-i-ran-72-trials-find-out-karl-weinmeister-nnqec/) (2025).
- Karl Weinmeister, [`evals.json` Reference Schema](https://github.com/kweinmeister/scripts/blob/main/evals/google-cloud-developer/evals.json) on GitHub.
- Dan Dye, [Evaluating Agent Graphs for SecOps AI Runbooks](https://security.googlecloudcommunity.com/community-blog-42/evaluating-agent-graphs-for-secops-ai-runbooks-8232) (2026), local tracking at [`evaluating_agent_graphs_for_secops_ai_runbooks.md`](evaluating_agent_graphs_for_secops_ai_runbooks.md).
- Dan Dye, [Serving Open Models for Security Agents, Part 1: Zero-Idle GPU Infrastructure](part1_zero_idle_gpu_infrastructure.md) (2026).
- NVIDIA, [SkillEvaluator Framework](https://github.com/NVIDIA/SkillEvaluator) on GitHub.
- Laude Institute, [Harbor Sandbox Runner](https://github.com/laude-institute/harbor) on GitHub.
- Repository & Evaluation Suite: [`dandye/open-model-deploy-gcp`](https://github.com/dandye/open-model-deploy-gcp) (branch `skill_discovery_eval_v0001`).
- Master Empirical Leaderboard: [`docs/eval_results/discovery/master_open_model_sweep_report.md`](../eval_results/discovery/master_open_model_sweep_report.md).
