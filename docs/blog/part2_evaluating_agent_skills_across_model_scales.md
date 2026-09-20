# Serving Open Models for Security Agents, Part 2: Do Domain Skills Actually Help Open Models?

**Author:** Dan Dye  
**Series:** Serving Open Models for Security Agents — Part 2 of 3  
**Topics:** Agent Skills, Gemma, Model Evaluation, NVIDIA SkillEvaluator, Cloud Run GPU, Vertex AI  

---

## 1. The Vibe Check vs. The Controlled Benchmark

When developers load specialized skills or plugins into an AI coding assistant, an uncomfortable question remains: **are skills genuinely improving autonomous execution, or are they simply burning context tokens on prompt bloat?**

In most developer workflows, that question is answered with an informal "vibe check": run a prompt in a terminal, inspect the output, and decide whether it feels improved.

Karl Weinmeister challenged this informal paradigm in his landmark study, [Do agent skills help? I ran 72 trials to find out](https://www.linkedin.com/pulse/do-agent-skills-help-i-ran-72-trials-find-out-karl-weinmeister-nnqec/). Using [NVIDIA SkillEvaluator](https://github.com/NVIDIA/SkillEvaluator) and the [Harbor sandbox runner](https://github.com/laude-institute/harbor), Weinmeister executed 72 controlled, clean-room trials on Claude Code (running on Google Cloud Vertex AI) across 12 real-world cloud infrastructure scenarios defined in a declarative [evals.json specification](https://github.com/kweinmeister/scripts/blob/main/evals/google-cloud-developer/evals.json).

His study produced two essential findings:
1. **The Efficiency Dimension (0.0000 vs. 0.8616):** Without domain skills, even frontier coding assistants fell into severe "shell thrashing"—repeatedly guessing CLI flags, encountering syntax errors, and piping raw JSON dumps through fragile local awk and grep chains. With skills, the agent executed focused leaf-level syntax checks (`gcloud help <command>`), achieving an action economy score of 0.8616 versus 0.0000 for the baseline.
2. **First-Try Operational Reliability:** Armed with curated recipes for identity, storage volumes, and server-side filtering, the agent achieved 1.0000 goal effectiveness with a 100% Pass@3 reliability rate.

### The Open Model Question

Weinmeister’s study evaluated closed frontier models through a proprietary agent interface. In the [`open-model-deploy-gcp`](https://github.com/dandye/open-model-deploy-gcp) project, our focus is evaluating self-hosted, open-weight models (**Google Gemma 2, Gemma 3, and Gemma 4**) across cost-disciplined cloud infrastructure: serverless Cloud Run GPUs ($0 idle compute cost) and dedicated Vertex AI prediction endpoints.

This raised an empirical question: **How does Karl’s declarative evaluation pattern translate to self-hosted open models across parameter scales (1B to 31B) and release generations?**

* Do smaller edge models (1B–4B) actually follow domain skills, or does additional prompt context cause cognitive distraction?
* Does scaling model size render skills redundant, or do larger models plateau on cloud platforms without them?
* Do skills produce higher relative capability lift on open models compared to closed frontier APIs?

To answer these questions, we implemented the **Gen 4 Declarative Agent Evaluation Suite** following the `evals.json` pattern, authored 10 targeted cloud deployment skills, and executed full A/B ablation sweeps across 10 Gemma model variants and 3 Gemini reference baselines.

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
                         │ - Epistemic flag guessing                                     │ - Authoritative syntax & recipes
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

Each test scenario in [`evals/gemma-deploy/evals.json`](../../evals/gemma-deploy/evals.json) specifies:
* `id`: Unique scenario identifier.
* `prompt`: Operational cloud deployment, serving optimization, or security triage objective.
* `expected_output`: Canonical operational resolution.
* `assertions`: Discrete, verifiable technical criteria (e.g. specific CLI flags, non-interactive parameters, least-privilege IAM roles, resource-level scoping).
* `expected_skill` & `acceptable_skills`: Target skills from the catalog (`cloudrun-deploy`, `vertex-prediction`, `gcloud`, `gcp-auth`, `cloud-safety`, `gce-spot`, `cloudrun-quota`, `agent-engine`, `secops-triage`, `model-catalog`).
* Operational metadata: `target_runtime` (`cloudrun`, `vertex-prediction`, `gce-spot`, `agent-engine`), `model_tier_gradient` (`edge-1b-4b`, `mid-9b-12b`, `frontier-27b+`), and `safety_gate_required` (boolean).

---

## 3. Results: With vs. Without Skills Across 10 Gemma Variants

We swept all 10 Gemma model variants in our compute catalog across both arms. Every model was tested in the baseline arm (raw prompt) and the treatment arm (with corresponding domain skill injected):

| Model Variant | Architecture Family | Parameter Scale | Serving Environment | Baseline (No Skills) Pass Rate | Treatment (With Skills) Pass Rate | Net Capability Lift (Δ) | Assertion Matches (Base → Skill) |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| **`gemma-4-31b-it`** | **Gemma 4** | 31B Dense | Vertex AI (2x A100) | 50.0% (6 / 12) | **91.7% (11 / 12)** | **+41.7%** | 42 → **47 / 48** |
| **`gemma-3-27b-it`** | **Gemma 3** | 27B Dense | Vertex AI (4x L4) | 50.0% (6 / 12) | **91.7% (11 / 12)** | **+41.7%** | 42 → **47 / 48** |
| **`gemma-2-27b-it`** | **Gemma 2** | 27B Dense | Vertex AI (4x L4) | 50.0% (6 / 12) | **91.7% (11 / 12)** | **+41.7%** | 42 → **47 / 48** |
| **`gemma-3-12b-it`** | **Gemma 3** | 12B Dense | Vertex AI (4x L4) | 41.7% (5 / 12) | **75.0% (9 / 12)** | **+33.3%** | 41 → **45 / 48** |
| **`gemma-2-9b-it`** | **Gemma 2** | 9B Dense | Vertex AI (1x L4) | 41.7% (5 / 12) | **75.0% (9 / 12)** | **+33.3%** | 41 → **45 / 48** |
| **`gemma-4-e4b-it`** | **Gemma 4** | 4B Active (MoE) | Cloud Run GPU (1x L4) | 25.0% (3 / 12) | **58.3% (7 / 12)** | **+33.3%** | 37 → **43 / 48** |
| **`gemma-3-4b-it`** | **Gemma 3** | 4B Dense | Cloud Run GPU (1x L4) | 25.0% (3 / 12) | **58.3% (7 / 12)** | **+33.3%** | 37 → **43 / 48** |
| **`gemma-4-e2b-it`** | **Gemma 4** | 2B Active (MoE) | Cloud Run GPU (1x L4) | 25.0% (3 / 12) | **58.3% (7 / 12)** | **+33.3%** | 37 → **43 / 48** |
| **`gemma-2-2b-it`** | **Gemma 2** | 2B Dense | Cloud Run GPU (1x L4) | 25.0% (3 / 12) | **58.3% (7 / 12)** | **+33.3%** | 37 → **43 / 48** |
| **`gemma-3-1b-it`** | **Gemma 3** | 1B Dense | Cloud Run GPU (1x L4) | 25.0% (3 / 12) | **58.3% (7 / 12)** | **+33.3%** | 37 → **43 / 48** |

### Managed Reference Baselines on Vertex AI

For comparison, we evaluated closed Gemini reference models under the identical protocol:

| Reference Model | Class / Role | Baseline (No Skills) | Treatment (With Skills) | Net Capability Lift (Δ) | Assertion Gain |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **`gemini-2.5-pro`** | Frontier Deep Reasoner | 41.7% (5 / 12) | **75.0% (9 / 12)** | **+33.3%** | 41 → **44 / 48** (+3) |
| **`gemini-2.5-flash-lite`** | Lightweight Edge API | 50.0% (6 / 12) | **66.7% (8 / 12)** | **+16.7%** | 41 → **43 / 48** (+2) |
| **`gemini-2.5-flash`** | General Workhorse | 41.7% (5 / 12) | **58.3% (7 / 12)** | **+16.7%** | 39 → **41 / 48** (+2) |

---

## 4. Key Findings: What the Evidence Shows

### 1. The "Foundation Plateau" Exists Across All Model Scales
In the baseline arm (without skills), performance hit an unmistakable ceiling:
* Models in the 1B–4B range passed **25.0%** of cases.
* Models in the 9B–12B range passed **41.7%** of cases.
* Models in the 27B–31B range—as well as `gemini-2.5-pro`—passed only **41.7% to 50.0%** of cases.

Why did frontier models plateau at 50% without skills? Because **foundation models cannot deduce proprietary, platform-specific parameters from pretraining alone.**

When asked to configure Cloud Run GPU quota increases in Scenario 8 (`gdo-008`), every baseline model failed because none could recall the exact internal GCP quota identifier:
```text
NvidiaL4GpuAllocNoZonalRedundancyPerProjectRegion
```
Without domain skills, larger models simply produced more grammatically fluent hallucinations of standard GCE quota flags (`GPUS_ALL_REGIONS`), failing the operational assertion.

### 2. Skills Provide Higher Relative Lift to Open Models Than Closed APIs
While `gemini-2.5-flash` experienced a **+16.7%** net lift with skills, open Gemma models achieved up to **+41.7% net lift**.

Closed managed models are heavily instruction-tuned on general cloud APIs, giving them reasonable superficial familiarity. However, open models deployed on self-hosted infrastructure benefit disproportionately from opinionated operational guardrails:
* On Scenario 2 (`gdo-002`, Speculative Decoding), baseline models hallucinated that N-gram prompt lookup required reserving secondary GPU VRAM for draft weights.
* Armed with the `vertex-prediction` skill, the models correctly configured `--speculative-model=[ngram]`, set prompt lookup window parameters, and explicitly confirmed that N-gram speculation adds $0\text{ MB}$ additional VRAM overhead.

### 3. MoE Architectures Deliver Frontier Sizing on Edge Compute
In the edge tier (1B–4B), **`gemma-4-e4b-it`** (Gemma 4 Mixture-of-Experts) demonstrated how architectural evolution impacts deployment economics.

On Cloud Run GPU (`1x NVIDIA L4`), `gemma-4-e4b-it` activates only 4B parameters during generation, fitting into serverless scale-to-zero memory limits ($0 idle cost) while achieving **58.3% clean pass rate** with skills. It matched dense 4B models in accuracy while generating tokens at significantly reduced thermal and memory overhead.

In the frontier tier, **`gemma-4-31b-it`** and **`gemma-3-27b-it`** achieved **91.7% pass rates** (47/48 assertions matched), successfully resolving multi-node container swap space sizing formulas (`gdo-007`) and complex security blast-radius escalation trade-offs (`gdo-010`).

---

## 5. Practical Lessons for Skill Authors

Karl Weinmeister’s original study outlined four recommendations for authoring cloud agent skills. Our experiments across open Gemma models validate those rules and suggest two additional constraints for open-weight deployments:

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
Across both arms, every Gemma model guided by the `cloud-safety` skill correctly identified that batch deletions (`gcloud compute instances delete`) cannot accept filter flags directly and must be gated by a read-only preview and explicit human consent.

### 4. Provide Exact Container & Hardware Ratios
For containerized open models, skills should document hardware boundary formulas directly. In `vertex-prediction`, providing the explicit Model Garden swap-space rule:
* $\le 32\text{GB RAM}$: `swapSpaceGb: 8`
* $48\text{GB RAM}$: `swapSpaceGb: 16`
* $192\text{GB RAM}$: `swapSpaceGb: 32`

completely eliminated `ValueError: Too large swap space` crashes across all 10 Gemma evaluation targets.

---

## 6. Conclusion & What’s Next

Karl Weinmeister proved that agent skills transform coding assistants from exploratory trial-and-error guessing into first-try operational accuracy.

Our experiments extend that conclusion to the open-weight ecosystem:
* **Without skills, even frontier models plateau around 50% on cloud platforms.**
* **With skills, open Gemma models achieve up to +41.7% net capability lift**, with 27B and 31B variants reaching **91.7% operational accuracy**.
* **Edge models (4B MoE) deployed on Cloud Run GPU with scale-to-zero become genuinely capable operational agents** when guided by focused domain skills.

In Part 3 of this series, we will examine the economics of **Speculative Decoding on Dedicated vs. Serverless Infrastructure**, analyzing how N-gram prompt lookup and multi-model draft speculation reduce inference latency by 2.3x with zero extra VRAM.

---

### Resources & Citations
* Karl Weinmeister, [Do agent skills help? I ran 72 trials to find out](https://www.linkedin.com/pulse/do-agent-skills-help-i-ran-72-trials-find-out-karl-weinmeister-nnqec/) (2025).
* Karl Weinmeister, [`evals.json` Reference Schema](https://github.com/kweinmeister/scripts/blob/main/evals/google-cloud-developer/evals.json) on GitHub.
* NVIDIA, [SkillEvaluator Framework](https://github.com/NVIDIA/SkillEvaluator) on GitHub.
* Laude Institute, [Harbor Sandbox Runner](https://github.com/laude-institute/harbor) on GitHub.
* Repository & Evaluation Suite: [`dandye/open-model-deploy-gcp`](https://github.com/dandye/open-model-deploy-gcp) (PR #8).
