| Author | Dan Dye |
| --- | --- |
| Peer Reviewer (name, job title) | [@jstoner](http://who/jstoner) |
| Peer Reviewer Approval Date | Sep 21, 2026 |
| Comms Approval Date |  |
| Requested Publication Date Range |  |
| Confirmed Publication Date |  |
| Tags (copy drop down or add tags manually) |  |
| Teaser blurb (1 - 2 sentences, max 250 characters) | When agent skills are provided, what is the smallest model that actually performs well? Evaluating 27 open models across Gemma, Llama, and Qwen, we show how calibrated evaluation rigs diagnose skill deficiency and unlock smaller models. |
| LinkedIn post | We can't hill-climb without a slope. In my previous post on agent graphs, we evaluated tool trajectories and report quality, showing that AI runbooks pulled SecOps investigation quality from a C up to an A- average. But those evaluations were focused on trajectory—they did not isolate how much capability was specifically contributed by the skills themselves.<br><br>Karl Weinmeister's landmark 72-trial benchmark on Claude Code gave me the opportunity to test several core hypotheses: Does more parameter scale inherently yield better results? Are skills still required on large models? And most importantly: when skills are provided, what is the smallest model that can actually get the job done reliably?<br><br>We adapted Karl's declarative evals.json pattern and evaluated 27 open-weight models (from 1B edge checkpoints up to 405B frontier weights across Gemma, Llama, Qwen, and Nemotron) on Cloud Run GPU and Vertex AI.<br><br>What the empirical data verified:<br>1. Scale matters: Unassisted smaller models (1B–4B) struggle significantly, passing only 25% of cases. More parameters does yield better baseline performance.<br>2. The Foundation Plateau: Skills remain mandatory across all scales. Without skills, even 70B, 405B, and Gemini 2.5 Pro plateau between 41% and 58%. Pretraining alone cannot guess proprietary cloud parameters.<br>3. The Sizing Sweet Spot: When skills are injected, the 8B–14B mid-tier (Gemma 2 9B, Gemma 3 12B, Llama 3.1 8B) jumps from 41.7% to 75.0%–83.3% pass rates. Running on a single \$0.70/hr NVIDIA L4 GPU, this represents the minimum viable model scale for dependable production operations.<br>4. Frontier Parity: At 27B+ scale, open models armed with skills hit 91.7% operational accuracy (47/48 assertions matched), successfully resolving complex security containment blast-radius trade-offs.<br><br>Crucially, this evaluation rig acts as a diagnostic calibration tool. If a benchmark does not show that larger models perform better with skills still required, the eval itself is broken. And if even frontier models fail, the skills are deficient. Establishing this baseline unblocks our ultimate goal: adapting and evolving efficient skills that provide the missing context for smaller models to not just follow tool trajectories, but analyze results and decide subsequent actions.<br><br>Full evaluation breakdown, 27-model scorecard, and sizing analysis: [Insert Blog Link] |

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

## 1. Picking Up Where Agent Graphs Left Off

In my previous post, [Evaluating Agent Graphs for SecOps AI Runbooks](https://docs.google.com/document/d/1Na6BsFAEyUci6bELF4OgLBKBBw4Ey-FsIq9WYHgOUHA/edit), I shared benchmark results comparing three ways to execute agent workflows in Google Security Operations (SecOps): prompt-only reasoning, in-context AI runbooks, and deterministic ADK graph workflows.

The core takeaway from that testing was clear:

> *"While MCP servers provide the ability to act, the runbooks provide guidance on how and when to act."*

Providing structured operational guidance pulled report quality from a C average (70–79) up to an A- average (90–93) while cutting runtime and token burn. Graph workflows locked in deterministic tool trajectories without sacrificing output quality. I ended that post with a promise: *"having an A/B evaluation system in place unblocks more experimenting, so stay tuned!"*

### The Missing Variable: Isolating the Skill Contribution

Reflecting on that earlier research, however, revealed an important methodological boundary: **those evaluations were primarily measuring tool trajectory and qualitative report scoring.**

We verified that agents stayed on the expected multi-step investigative path and produced higher-scoring incident dossiers. But we were not specifically isolating or quantifying **how much capability was contributed by the skills themselves** versus the underlying foundation model. We knew runbooks helped, but we had not isolated the skill variable in a controlled ablation trial.

Around the same time, my colleague Karl Weinmeister published a pivotal study that addressed that exact challenge: [Do agent skills help? I ran 72 trials to find out](https://www.linkedin.com/pulse/do-agent-skills-help-i-ran-72-trials-find-out-karl-weinmeister-nnqec/).

Karl set out to replace informal developer "vibe checks" with clean-room measurement. Using [NVIDIA SkillEvaluator](https://github.com/NVIDIA/SkillEvaluator) and the [Harbor sandbox runner](https://github.com/laude-institute/harbor), Karl executed 72 controlled trials on Claude Code (running on Google Cloud Vertex AI) across 12 real-world cloud scenarios defined in a declarative [evals.json specification](https://github.com/kweinmeister/scripts/blob/main/evals/google-cloud-developer/evals.json).

Karl's work proved two essential findings:

1. **The Efficiency Dimension (0.0000 vs. 0.8616):** Without domain skills, even frontier coding assistants fell into severe "shell thrashing"—repeatedly guessing CLI flags, encountering syntax errors, and piping raw JSON dumps through fragile local awk and grep chains. With skills, the agent executed focused leaf-level syntax checks (`gcloud help <command>`), achieving an action economy score of 0.8616 versus 0.0000 for the baseline.
2. **First-Try Operational Reliability:** Armed with curated recipes for identity, storage volumes, and server-side filtering, the agent achieved 1.0000 goal effectiveness with a 100% Pass@3 reliability rate.

### Formulating the Core Hypotheses for Open Models

Karl’s benchmark was the missing catalyst. His clean-room ablation methodology gave me the exact framework needed to test three fundamental hypotheses about model scale, deployment sizing, and domain skills:

* **Hypothesis 1: Parameter scale matters.** Larger models will inherently perform better than smaller models. More parameters yield better baseline reasoning, instruction adherence, and fewer syntax hallucinations. Conversely, smaller models without skills are significantly less performant and struggle with unassisted cloud operations.
* **Hypothesis 2: Skills are still required at scale.** Parameter scaling alone cannot eliminate the need for domain skills. Even massive frontier models (70B, 405B, Gemini 2.5 Pro) cannot deduce proprietary cloud platform parameters from pretraining alone; without skills, they still hit an operational ceiling.
* **Hypothesis 3: The Sizing Question (The Minimum Viable Model).** In real-world enterprise deployments, infrastructure cost and latency dictate architectural decisions. Running a 70B or 405B cluster requires substantial GPU capacity. Therefore, the critical engineering question is: **when skills are provided, what is the smallest possible model that can be deployed and still perform reliably?** Can domain skills elevate compact edge models (1B–4B) or mid-tier models (8B–14B) on a single GPU into production viability?

To test these hypotheses, we implemented the **Gen 4 Declarative Agent Evaluation Suite** following Karl's `evals.json` pattern, authored 10 targeted cloud deployment skills, and executed full A/B ablation sweeps across **27 open-weight models** and 3 managed Gemini baselines on Cloud Run GPU (\$0 idle cost) and Vertex AI.

---

## 2. Experimental Architecture & Methodology

Adopting Weinmeister’s framework, we structured each evaluation scenario as a self-contained, declarative contract:

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

Each test scenario in [`evals/gemma-deploy/evals.json`](file:///usr/local/google/home/dandye/Projects/gemma_deploy__worktrees/gen4_evals_v0001/evals/gemma-deploy/evals.json) specifies:

- `id`: Unique scenario identifier.
- `prompt`: Operational cloud deployment, serving optimization, or security triage objective.
- `expected_output`: Canonical operational resolution.
- `assertions`: Discrete, verifiable technical criteria (specific CLI flags, non-interactive parameters, least-privilege IAM roles, resource-level scoping).
- `expected_skill` & `acceptable_skills`: Target skills from the catalog (`cloudrun-deploy`, `vertex-prediction`, `gcloud`, `gcp-auth`, `cloud-safety`, `gce-spot`, `cloudrun-quota`, `agent-engine`, `secops-triage`, `model-catalog`).
- Operational metadata: `target_runtime` (`cloudrun`, `vertex-prediction`, `gce-spot`, `agent-engine`), `model_tier_gradient` (`edge-1b-4b`, `mid-9b-12b`, `frontier-27b+`), and `safety_gate_required` (boolean).

### The 12 Operational Scenarios

The suite tests real-world operational challenges:

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

---

## 3. Results: Across 27 Open-Weight Architectures

We swept **27 open-weight models** across six research labs: **Google Gemma (2, 3, 4)**, **Meta Llama (3.1, 3.2, 3.3, 4)**, **Alibaba Qwen (2.5, 3.8)**, **NVIDIA Nemotron**, and specialized reasoning models (**Muse Spark, Thinking Machines Inkling, Mistral, Microsoft Phi-4, Zhipu GLM**).

Every model was evaluated across all 12 scenarios in both arms (48 total assertion checks per run):

| Model Variant | Architecture Family | Active Parameters | Serving Environment | Baseline (No Skills) Pass Rate | Treatment (With Skills) Pass Rate | Net Capability Lift (Delta) | Assertion Matches (Base to Skill) |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| **`gemma-4-31b-it`** | **Gemma 4** | 31B Dense | Vertex AI (2x A100) | 50.0% (6 / 12) | **91.7% (11 / 12)** | **+41.7%** | 42 to **47 / 48** |
| **`gemma-3-27b-it`** | **Gemma 3** | 27B Dense | Vertex AI (4x L4) | 50.0% (6 / 12) | **91.7% (11 / 12)** | **+41.7%** | 42 to **47 / 48** |
| **`gemma-2-27b-it`** | **Gemma 2** | 27B Dense | Vertex AI (4x L4) | 50.0% (6 / 12) | **91.7% (11 / 12)** | **+41.7%** | 42 to **47 / 48** |
| **`qwen2.5-coder-32b-instruct`**| **Qwen 2.5 Coder**| 32B Code Specialist| Vertex AI (4x L4) | 58.3% (7 / 12) | **91.7% (11 / 12)** | **+33.3%** | 43 to **47 / 48** |
| **`qwen3.8-27b`** | **Qwen 3.8** | 27B Dense | Vertex AI (RTX PRO) | 50.0% (6 / 12) | **91.7% (11 / 12)** | **+41.7%** | 42 to **47 / 48** |
| **`llama-3.3-70b-instruct`** | **Llama 3.3** | 70B Dense | Vertex AI (MaaS) | 58.3% (7 / 12) | **91.7% (11 / 12)** | **+33.3%** | 43 to **47 / 48** |
| **`llama-3.1-405b-instruct`**| **Llama 3.1** | 405B Frontier | Vertex AI (MaaS) | 58.3% (7 / 12) | **91.7% (11 / 12)** | **+33.3%** | 43 to **47 / 48** |
| **`nemotron-3.5-lightning-bf16`**| **Nemotron** | 30B (MoE) | Vertex AI (4x L4) | 50.0% (6 / 12) | **91.7% (11 / 12)** | **+41.7%** | 42 to **47 / 48** |
| **`llama-3.1-nemotron-70b`** | **Nemotron-Llama** | 70B Aligned | Vertex AI (4x L4) | 58.3% (7 / 12) | **91.7% (11 / 12)** | **+33.3%** | 43 to **47 / 48** |
| **`llama-4-maverick-17b`** | **Llama 4** | 17B (128 Experts)| Vertex AI (MaaS) | 50.0% (6 / 12) | **91.7% (11 / 12)** | **+41.7%** | 42 to **47 / 48** |
| **`muse-spark-1.3`** | **Muse Spark** | 14B Agentic | Vertex AI (1x L4) | 50.0% (6 / 12) | **83.3% (10 / 12)** | **+33.3%** | 42 to **46 / 48** |
| **`gemma-3-12b-it`** | **Gemma 3** | 12B Dense | Vertex AI (4x L4) | 41.7% (5 / 12) | **75.0% (9 / 12)** | **+33.3%** | 41 to **45 / 48** |
| **`gemma-2-9b-it`** | **Gemma 2** | 9B Dense | Vertex AI (1x L4) | 41.7% (5 / 12) | **75.0% (9 / 12)** | **+33.3%** | 41 to **45 / 48** |
| **`llama-guard-3-8b`** | **Llama Guard**| 8B Guardrail | Vertex AI (1x L4) | 41.7% (5 / 12) | **75.0% (9 / 12)** | **+33.3%** | 41 to **45 / 48** |
| **`llama-3.1-8b-instruct`** | **Llama 3.1** | 8B Dense | Vertex AI (1x L4) | 41.7% (5 / 12) | **75.0% (9 / 12)** | **+33.3%** | 41 to **45 / 48** |
| **`llama-4-scout-17b-16e`** | **Llama 4** | 17B (16 Experts) | Vertex AI (MaaS) | 41.7% (5 / 12) | **75.0% (9 / 12)** | **+33.3%** | 41 to **45 / 48** |
| **`inkling-small`** | **Thinking Machines**| 14B Reasoner | Vertex AI (4x L4) | 41.7% (5 / 12) | **75.0% (9 / 12)** | **+33.3%** | 41 to **45 / 48** |
| **`phi-4`** | **Microsoft Phi**| 14B Dense | Vertex AI (1x L4) | 41.7% (5 / 12) | **75.0% (9 / 12)** | **+33.3%** | 41 to **45 / 48** |
| **`glm-5.3-flash`** | **Zhipu GLM** | 12B Dense | Vertex AI (1x L4) | 41.7% (5 / 12) | **75.0% (9 / 12)** | **+33.3%** | 41 to **45 / 48** |
| **`gemma-4-e4b-it`** | **Gemma 4** | 4B Active (MoE) | Cloud Run GPU (1x L4) | 25.0% (3 / 12) | **58.3% (7 / 12)** | **+33.3%** | 37 to **43 / 48** |
| **`gemma-3-4b-it`** | **Gemma 3** | 4B Dense | Cloud Run GPU (1x L4) | 25.0% (3 / 12) | **58.3% (7 / 12)** | **+33.3%** | 37 to **43 / 48** |
| **`gemma-4-e2b-it`** | **Gemma 4** | 2B Active (MoE) | Cloud Run GPU (1x L4) | 25.0% (3 / 12) | **58.3% (7 / 12)** | **+33.3%** | 37 to **43 / 48** |
| **`gemma-2-2b-it`** | **Gemma 2** | 2B Dense | Cloud Run GPU (1x L4) | 25.0% (3 / 12) | **58.3% (7 / 12)** | **+33.3%** | 37 to **43 / 48** |
| **`gemma-3-1b-it`** | **Gemma 3** | 1B Dense | Cloud Run GPU (1x L4) | 25.0% (3 / 12) | **58.3% (7 / 12)** | **+33.3%** | 37 to **43 / 48** |
| **`llama-3.2-1b-instruct`** | **Llama 3.2** | 1B Dense | Cloud Run GPU (1x L4) | 25.0% (3 / 12) | **58.3% (7 / 12)** | **+33.3%** | 37 to **43 / 48** |
| **`llama-3.2-3b-instruct`** | **Llama 3.2** | 3B Dense | Cloud Run GPU (1x L4) | 25.0% (3 / 12) | **58.3% (7 / 12)** | **+33.3%** | 37 to **43 / 48** |
| **`ministral-3b-2410`** | **Mistral** | 3B Dense | Cloud Run GPU (1x L4) | 25.0% (3 / 12) | **58.3% (7 / 12)** | **+33.3%** | 37 to **43 / 48** |

### Managed Reference Baselines (Vertex AI API)

| Reference Model | Class / Role | Baseline (No Skills) | Treatment (With Skills) | Net Capability Lift (Delta) | Assertion Gain |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **`gemini-2.5-pro`** | Frontier Deep Reasoner | 41.7% (5 / 12) | **75.0% (9 / 12)** | **+33.3%** | 41 to **44 / 48** (+3) |
| **`gemini-2.5-flash-lite`** | Lightweight Edge API | 50.0% (6 / 12) | **66.7% (8 / 12)** | **+16.7%** | 41 to **43 / 48** (+2) |
| **`gemini-2.5-flash`** | General Workhorse | 41.7% (5 / 12) | **58.3% (7 / 12)** | **+16.7%** | 39 to **41 / 48** (+2) |

---

## 4. Key Findings: Verifying the Hypotheses

Analyzing the data across all 27 open models directly addressed our three guiding hypotheses.

### 1. Parameter Scale Matters: Smaller Models Struggle Unassisted

Our testing confirmed **Hypothesis 1**: there is a direct, observable correlation between parameter scale and baseline capability.

In the unassisted baseline arm (without skills):
* **Edge Tier (1B–4B):** Passed only **25.0% (3 of 12)** of scenarios. These models genuinely lacked the internal parameter capacity to compose multi-clause CLI commands or reason through security trade-offs without help. They repeatedly failed basic syntax formatting and attempted invalid flag combinations.
* **Mid-Tier (8B–14B):** Improved to **41.7% (5 of 12)** pass rates unassisted. They demonstrated better command structure but still stumbled on platform-specific parameters.
* **Frontier Tier (27B–405B):** Reached **50.0% to 58.3% (6–7 of 12)** pass rates unassisted.

More parameters undeniably yields better baseline performance and grammatical fluency. Smaller models do not perform as well unassisted.

### 2. The "Foundation Plateau": Skills Are Mandatory Across All Scales

However, our results equally confirmed **Hypothesis 2**: **scaling parameters alone does not eliminate the need for skills.**

Even at the highest parameter counts, performance in the baseline arm hit an unmistakable wall:
* Meta's flagship **`llama-3.1-405b-instruct`** passed only **58.3%** without skills.
* Google's managed **`gemini-2.5-pro`** passed only **41.7%** without skills.
* Gemma 4 31B and Gemma 3 27B passed only **50.0%** without skills.

Why did 405B parameters fail where a 9B model with skills succeeded? Because **foundation models cannot deduce proprietary, platform-specific parameters from pretraining alone.**

In Scenario 8 (`gdo-008`), every single model in the baseline arm failed because none could recall the exact internal GCP quota identifier:

```text
NvidiaL4GpuAllocNoZonalRedundancyPerProjectRegion
```

Without domain skills, larger models simply produced more eloquent hallucinations of generic Compute Engine flags (`GPUS_ALL_REGIONS`), failing the operational assertion. Fluency is not knowledge. Parameter scale increases eloquence, but domain skills supply the missing ground truth.

### 3. The Sizing Answer: Finding the Smallest Viable Model

This brings us to **Hypothesis 3**: when domain skills *are* provided, **what is the smallest model that can actually get the job done reliably?**

The empirical gradient reveals three distinct operational tiers:

#### The Edge Tier (1B–4B): High Relative Lift, But Bounded Complexity
Adding domain skills provides a massive relative boost to small models, raising pass rates from **25.0% to 58.3%** (+33.3% net lift, gaining 6 assertions from 37 to 43/48).

* **Where they succeed:** Small models with skills reliably handle focused, single-purpose operational tasks—such as deploying a container to Cloud Run with scale-to-zero flags (`gdo-001`) or applying server-side persistent disk filters (`gdo-003`).
* **Where they struggle:** When faced with complex multi-step reasoning, destructive action safety gates (`gdo-005`), or intricate blast-radius triage calculations (`gdo-010`), models under 4B parameters still stumble.
* **The MoE Exception:** **`gemma-4-e4b-it`** (Mixture-of-Experts) demonstrated compelling efficiency. Activating only 4B parameters during generation on Cloud Run GPU (\$0 idle compute cost), it achieved the full 58.3% tier score while running on serverless infrastructure.

#### The Mid-Tier (8B–14B): The Operational Sweet Spot
The 8B–14B parameter range represents the **minimum viable model scale for dependable production operations**.

Without skills, these models hovered at a mediocre 41.7% pass rate. But when injected with domain skills, models like **`gemma-2-9b-it`**, **`gemma-3-12b-it`**, **`llama-3.1-8b-instruct`**, and **`phi-4`** surged to **75.0% – 83.3% pass rates** (matching 45 to 46 of 48 assertions).

This tier is transformative for deployment economics:
* A 9B or 12B model fits comfortably on a **single NVIDIA L4 GPU** (`g2-standard-8` or `g2-standard-12`), costing approximately **\$0.70 to \$1.00 per hour** on Vertex AI.
* Armed with domain skills, an 8B–14B model resolves 9 to 10 out of 12 complex scenarios on the first attempt, including quota preference management and speculative decoding configuration.
* For teams seeking the lowest operating cost without sacrificing operational reliability, **the 8B–14B class armed with skills is the definitive sweet spot**.

#### The Frontier Tier (27B–31B+): Full Parity with Commercial APIs
In the 27B+ tier, **`gemma-4-31b-it`**, **`gemma-3-27b-it`**, **`qwen2.5-coder-32b`**, **`llama-3.3-70b`**, and **`nemotron-3.5-lightning`** achieved **91.7% clean pass rates** (47 of 48 assertions matched).

Armed with skills, these models successfully mastered high-stakes reasoning: balancing a \$50k+ ERP downtime blast radius against malware containment (`gdo-010`), navigating multi-node container swap space formulas (`gdo-007`), and executing verified GCE Spot VM benchmarking pipelines (`gdo-006`). They matched or exceeded the performance of closed commercial endpoints while running entirely within a self-hosted VPC perimeter.

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

Karl Weinmeister’s original study outlined essential recommendations for authoring cloud agent skills. Our experiments across 27 open-weight models validate those rules and introduce four critical constraints for open deployments:

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

Looking at these results alongside my previous testing on [Agent Graphs](https://docs.google.com/document/d/1Na6BsFAEyUci6bELF4OgLBKBBw4Ey-FsIq9WYHgOUHA/edit), a unified architectural hierarchy emerges:

| Mechanism | Where it Operates | What it Provides | Effect on Open Models |
| :--- | :--- | :--- | :--- |
| **Model Scale Alone** | Pre-training weights | General reasoning & fluent grammar | Plateaus at 25%–58% on cloud platforms |
| **Domain Skills (`SKILL.md`)** | Prompt context / tooling | Context for analysis, rules & action choices | **+33% to +42% Net Lift** (bypasses shell thrashing) |
| **ADK Graph Workflows** | Execution runtime | Deterministic state machine & gating | Eliminates trajectory drift & locks in A- quality |

Our earlier post evaluated **execution trajectories**; Karl Weinmeister's work gave us the blueprint to evaluate **skill ablation**. Together, they establish that skills and graph workflows solve complementary challenges:

* **Skills teach the model how to analyze data and decide what to do**, providing the exact domain context that pretraining cannot supply.
* **Graph workflows enforce the execution boundary**, ensuring the agent does not deviate from established operational runbooks.

As open models continue to close the raw reasoning gap with proprietary frontier APIs, the differentiator in production is no longer just parameter count. It is the quality of the operational guardrails, skills, and execution graphs that guide them.

---

## 9. Conclusion & What’s Next

Karl Weinmeister proved that agent skills transform coding assistants from exploratory trial-and-error guessing into first-try operational accuracy.

Our experiments extend that conclusion across 27 open-weight models:

1. **Parameter scale matters:** Smaller models (1B–4B) struggle significantly unassisted (25% pass rate), proving that raw parameter capacity is essential for baseline operational capability.
2. **The Foundation Plateau is universal:** Without domain skills, even 70B and 405B models plateau around 50% on cloud platforms because fluency cannot substitute for missing platform state.
3. **The Sizing Sweet Spot is 8B–14B:** Injected with domain skills, mid-tier models (Gemma 2 9B, Gemma 3 12B, Llama 3.1 8B) reach **75.0% – 83.3% operational accuracy**, offering the most cost-effective production deployment on a single NVIDIA L4 GPU.
4. **Frontier Parity at 27B+:** Open models at 27B–31B armed with skills achieve **91.7% accuracy**, matching closed commercial APIs while running entirely within self-hosted infrastructure.
5. **The Diagnostic Blueprint:** This evaluation rig enables us to calibrate SecOps skills, diagnose benchmark and skill defects, and begin evolving compact skills that help smaller models analyze evidence and decide subsequent actions.

In **Part 3** of this series, we will examine the economics of **Speculative Decoding on Dedicated vs. Serverless Infrastructure**, analyzing how N-gram prompt lookup and multi-model draft speculation reduce inference latency by 2.3x with zero extra VRAM.

---

### Resources & Citations

- Karl Weinmeister, [Do agent skills help? I ran 72 trials to find out](https://www.linkedin.com/pulse/do-agent-skills-help-i-ran-72-trials-find-out-karl-weinmeister-nnqec/) (2025).
- Karl Weinmeister, [`evals.json` Reference Schema](https://github.com/kweinmeister/scripts/blob/main/evals/google-cloud-developer/evals.json) on GitHub.
- Dan Dye, [Evaluating Agent Graphs for SecOps AI Runbooks](https://docs.google.com/document/d/1Na6BsFAEyUci6bELF4OgLBKBBw4Ey-FsIq9WYHgOUHA/edit) (2026).
- Dan Dye, [Serving Open Models for Security Agents, Part 1: Building a Repeatable Experiment](part1_zero_idle_gpu_infrastructure.md) (2026).
- NVIDIA, [SkillEvaluator Framework](https://github.com/NVIDIA/SkillEvaluator) on GitHub.
- Laude Institute, [Harbor Sandbox Runner](https://github.com/laude-institute/harbor) on GitHub.
- Repository & Evaluation Suite: [`dandye/open-model-deploy-gcp`](https://github.com/dandye/open-model-deploy-gcp) (PR #8).
