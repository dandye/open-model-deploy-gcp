| Author | Dan Dye |
| --- | --- |
| Peer Reviewer (name, job title) | [@jstoner](http://who/jstoner) |
| Peer Reviewer Approval Date | Sep 21, 2026 |
| Comms Approval Date |  |
| Requested Publication Date Range |  |
| Confirmed Publication Date |  |
| Tags (copy drop down or add tags manually) |  |
| Teaser blurb (1 - 2 sentences, max 250 characters) | Do agent skills help open-weight models? Sourcing Karl Weinmeister's benchmark, we evaluate 27 open models across Gemma, Llama, and Qwen on Cloud Run GPU and Vertex AI to uncover the foundation plateau and measured capability lifts. |
| LinkedIn post | We can't hill-climb without a slope. In my previous post, we showed that AI runbooks and graph workflows elevated Google SecOps investigation quality from a C average up to an A- average while cutting runtime and token burn. As I noted then, having a repeatable A/B evaluation harness unblocks more experimenting.<br><br>Today, in Part 2 of our Serving Open Models series, we tackle the next big question: Do domain skills actually help self-hosted, open-weight models?<br><br>Motivated by Karl Weinmeister's landmark 72-trial benchmark on Claude Code, we adapted the declarative evals.json pattern and evaluated 27 open-weight models (from 1B edge checkpoints up to 405B frontier weights across Gemma, Llama, Qwen, and Nemotron) on Cloud Run GPU and Vertex AI.<br><br>The empirical findings:<br>1. The Foundation Plateau: Without domain skills, every model—from 1B to 405B—plateaus between 25% and 58% pass rate. Models cannot guess proprietary cloud parameters from pretraining alone.<br>2. Disproportionate Lift: While closed frontier APIs gained +16.7% from skills, open models gained up to +41.7% net capability lift.<br>3. Frontier Parity: At 27B+ scale, models like Gemma 4 31B, Qwen 2.5 Coder 32B, and Llama 3.3 70B achieved a 91.7% pass rate (47/48 assertions matched), successfully resolving complex security containment blast-radius trade-offs.<br>4. Scale-to-Zero Efficiency: Edge MoE models like Gemma 4 E4B on Cloud Run GPU (\$0 idle cost) reached 58.3% accuracy while activating only 4B parameters.<br><br>Full evaluation breakdown, 27-model scorecard, and authoring lessons: [Insert Blog Link] |

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

In [Part 1 of this series](part1_zero_idle_gpu_infrastructure.md), we began that experimentation by establishing the infrastructure layer: building a repeatable, inspectable serving platform in [`open-model-deploy-gcp`](https://github.com/dandye/open-model-deploy-gcp) for self-hosted open models across serverless Cloud Run GPUs (\$0 idle compute cost) and dedicated Vertex AI prediction endpoints.

Around the same time, my colleague Karl Weinmeister published a pivotal study that examined the exact same core question from another angle: [Do agent skills help? I ran 72 trials to find out](https://www.linkedin.com/pulse/do-agent-skills-help-i-ran-72-trials-find-out-karl-weinmeister-nnqec/).

### Moving Beyond the "Vibe Check"

When developers load specialized skills, runbooks, or tool definitions into an AI agent, an uncomfortable question remains: **are skills genuinely improving autonomous execution, or are they simply burning context tokens on prompt bloat?**

In most developer workflows, that question is answered with an informal "vibe check": run a prompt in a terminal, inspect the output, and decide whether it feels improved.

Karl challenged this informal paradigm by creating a rigorous, clean-room benchmark. Using [NVIDIA SkillEvaluator](https://github.com/NVIDIA/SkillEvaluator) and the [Harbor sandbox runner](https://github.com/laude-institute/harbor), Karl executed 72 controlled trials on Claude Code (running on Google Cloud Vertex AI) across 12 real-world cloud infrastructure scenarios defined in a declarative [evals.json specification](https://github.com/kweinmeister/scripts/blob/main/evals/google-cloud-developer/evals.json).

His study produced two essential findings:

1. **The Efficiency Dimension (0.0000 vs. 0.8616):** Without domain skills, even frontier coding assistants fell into severe "shell thrashing"—repeatedly guessing CLI flags, encountering syntax errors, and piping raw JSON dumps through fragile local awk and grep chains. With skills, the agent executed focused leaf-level syntax checks (`gcloud help <command>`), achieving an action economy score of 0.8616 versus 0.0000 for the baseline.
2. **First-Try Operational Reliability:** Armed with curated recipes for identity, storage volumes, and server-side filtering, the agent achieved 1.0000 goal effectiveness with a 100% Pass@3 reliability rate.

### The Open Model Question

Karl’s results were compelling, but they evaluated a single closed frontier model through a proprietary agent interface. In enterprise security environments, sovereign clouds, and cost-disciplined teams, routing every payload to commercial frontier APIs is often not feasible or permissible. Teams want to self-host open-weight models—like Google Gemma, Meta Llama, and Alibaba Qwen—on private infrastructure.

This raised a critical empirical question: **How does Karl’s declarative evaluation pattern translate to self-hosted open models across parameter scales (1B to 405B) and release generations?**

* **Do smaller edge models (1B–4B) actually follow domain skills**, or does additional prompt context cause cognitive distraction?
* **Does scaling model size render skills redundant**, or do larger models hit the same ceiling on cloud platforms without them?
* **Do skills produce higher relative capability lift on open models** compared to closed frontier APIs?

To answer these questions, we implemented the **Gen 4 Declarative Agent Evaluation Suite** following the `evals.json` pattern, authored 10 targeted cloud deployment skills, and executed full A/B ablation sweeps across **27 open-weight models** and 3 managed Gemini baselines.

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

We evaluated **27 open-weight models** across six research labs: **Google Gemma (2, 3, 4)**, **Meta Llama (3.1, 3.2, 3.3, 4)**, **Alibaba Qwen (2.5, 3.8)**, **NVIDIA Nemotron**, and specialized reasoning models (**Muse Spark, Thinking Machines Inkling, Mistral, Microsoft Phi-4, Zhipu GLM**).

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

## 4. Key Findings: What the Numbers Tell Us

### 1. The "Foundation Plateau" Exists Across All Labs and Scales

In the baseline arm (without skills), performance hit an unmistakable ceiling:

* Across all 27 models—from 1B edge checkpoints up to Meta’s 405B flagship—**the unassisted baseline pass rate plateaued between 25.0% and 58.3%**.
* Even massive frontier models like `llama-3.1-405b-instruct` (58.3%) and `gemini-2.5-pro` (41.7%) failed on exact platform conventions without skills.

Why did frontier models plateau without skills? Because **foundation models cannot deduce proprietary, platform-specific parameters from pretraining alone.**

When asked to configure Cloud Run GPU quota increases in Scenario 8 (`gdo-008`), every single baseline model failed because none could recall the exact internal GCP quota identifier:

```text
NvidiaL4GpuAllocNoZonalRedundancyPerProjectRegion
```

Without domain skills, larger models simply produced more grammatically fluent hallucinations of standard GCE quota flags (`GPUS_ALL_REGIONS`), failing the operational assertion. Parameter scale improves eloquence, not hidden platform state.

### 2. Open Models Benefit Disproportionately from Skills

While closed managed models like `gemini-2.5-flash` gained **+16.7%** with skills, open-weight models experienced up to **+41.7% net lift**.

Closed commercial models undergo extensive instruction-tuning on general cloud APIs, giving them reasonable superficial familiarity. However, open models deployed on self-hosted infrastructure benefit disproportionately from authoritative operational guardrails:

* **Speculative Decoding (`gdo-002`):** In the baseline arm, models hallucinated that N-gram prompt lookup required loading secondary weights into VRAM. With the `vertex-prediction` skill, open models correctly configured `--speculative-model=[ngram]`, set prompt lookup window parameters, and explicitly confirmed that N-gram speculation adds \$0\text{ MB} additional VRAM overhead.
* **Dynamic Endpoint Discovery (`gdo-009`):** Shifted open agents from guessing internal container hostnames to querying `/v1/models` on the model server to dynamically resolve exact vLLM served model identifiers.
* **Tier 1 Alert Escalation (`gdo-010`):** Eliminated reflexive, destructive host isolation on mission-critical assets (\$50k+ ERP downtime blast radius), guiding agents to gather secondary telemetry (WHOIS, VirusTotal) and escalate with a structured dossier.

### 3. Frontier Parity at 27B+ Scale

In the frontier tier, **`gemma-4-31b-it`**, **`gemma-3-27b-it`**, **`qwen2.5-coder-32b`**, **`llama-3.3-70b`**, and **`nemotron-3.5-lightning`** achieved **91.7% clean pass rates** (47/48 assertions matched).

Armed with skills, these open-weight models matched or exceeded the accuracy of closed commercial endpoints while operating entirely within a self-hosted VPC perimeter.

### 4. MoE Architectures Deliver Frontier Sizing on Edge Budgets

In the edge tier ($\le 4\text{B}$), **`gemma-4-e4b-it`** (Gemma 4 Mixture-of-Experts) demonstrated how architectural evolution impacts deployment economics.

On serverless Cloud Run GPU (`1x NVIDIA L4`), `gemma-4-e4b-it` activates only 4B parameters during generation, fitting into serverless scale-to-zero memory limits (\$0 idle compute cost) while achieving **58.3% operational accuracy** with skills. It matched dense 4B models in accuracy while generating tokens at significantly reduced thermal and memory overhead.

---

## 5. Practical Lessons for Skill Authors

Karl Weinmeister’s original study outlined essential recommendations for authoring cloud agent skills. Our experiments across open-weight models validate those rules and introduce four critical constraints for open deployments:

### 1. Enforce Leaf-Level Help Checks Before Execution

Open models are susceptible to "flag drift"—borrowing syntax from related CLI tools (e.g. using Kubernetes `--volume-mount` flags inside `gcloud run deploy`). Instructing agents to check leaf-level help eliminates syntax hallucination:

```bash
# Rule: Before drafting complex gcloud invocations, inspect leaf help
gcloud help run deploy
```

### 2. Guard Against Context Window Pollution

Open models with 4k–8k context windows degrade quickly when flooded with raw JSON. Skills must mandate server-side filtering and projection:

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

## 6. Connecting the Dots: Runbooks, Graphs, and Skills

Looking at these results alongside my previous testing on [Agent Graphs](https://docs.google.com/document/d/1Na6BsFAEyUci6bELF4OgLBKBBw4Ey-FsIq9WYHgOUHA/edit), a unified architectural hierarchy emerges:

| Mechanism | Where it Operates | What it Provides | Effect on Open Models |
| :--- | :--- | :--- | :--- |
| **Model Scale Alone** | Pre-training weights | General reasoning & fluent grammar | Plateaus at 25%–58% on cloud platforms |
| **Domain Skills (`SKILL.md`)** | Prompt context / tooling | Parameter syntax & operational rules | **+33% to +42% Net Lift** (bypasses shell thrashing) |
| **ADK Graph Workflows** | Execution runtime | Deterministic state machine & gating | Eliminates trajectory drift & locks in A- quality |

Skills and graph workflows solve the same fundamental problem: **they replace stochastic trial-and-error with structured operational guidance.**

As open models continue to close the raw reasoning gap with proprietary frontier APIs, the differentiator in production is no longer just parameter count. It is the quality of the operational guardrails, skills, and execution graphs that guide them.

---

## 7. Conclusion & What’s Next

Karl Weinmeister proved that agent skills transform coding assistants from exploratory trial-and-error guessing into first-try operational accuracy.

Our experiments extend that conclusion to the open-weight ecosystem:

1. **Without skills, even frontier models plateau around 50% on cloud platforms.** Fluency cannot compensate for missing platform facts.
2. **With skills, open models achieve up to +41.7% net capability lift**, with 27B+ variants reaching **91.7% operational accuracy**.
3. **Edge MoE models deployed on Cloud Run GPU with scale-to-zero become genuinely capable operational agents** when guided by focused domain skills.

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
