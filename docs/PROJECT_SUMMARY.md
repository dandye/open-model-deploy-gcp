# Project Summary: open-model-deploy-gcp (gemma_deploy)

**Domain:** Generative AI Systems Engineering, Edge Model Optimization, Autonomous Cyber Defense  
**Scope:** Lead Systems & AI/ML Engineer  
**Core Technologies:** Google Cloud Platform (Vertex AI, Cloud Run GPU, GCE Spot VMs, GKE Ray & Kueue), vLLM, Gemma 2/3/4, Gemini 2.5/3.7, Google SecOps (Chronicle Remote MCP), Terraform, Python, Docker  
**Repository:** [https://github.com/dandye/open-model-deploy-gcp](https://github.com/dandye/open-model-deploy-gcp)  

---

## 1. Executive Summary & Problem Statement

Deploying Large Language Models for autonomous enterprise operations involves a critical operational conflict: availability versus economics.

When serving frontier foundation models like Gemini 2.5 Pro via managed APIs, organizations benefit from elastic, zero-maintenance capacity. However, they forfeit data residency control, accept opaque per-token rate structures, and face compounding costs when autonomous agents generate millions of reasoning tokens during multi-step tool investigations. Conversely, deploying open-weight models—such as Google's Gemma family—provides complete control over weights, execution environments, and internal security boundaries.

The pitfall lies in conventional deployment patterns: provisioning persistent, dedicated GPU virtual machines (e.g., `g2-standard-8` with an NVIDIA L4 GPU or `a2-highgpu-2g` with 2x NVIDIA A100s) that sit idle 80% to 90% of the day. At standard cloud list prices, an idle single-L4 instance costs roughly $600 to $800 per month, while a 4x L4 or 2x A100 node costs between $2,400 and $4,500 per month—accumulating billing waste whether processing inferences or doing nothing.

The **`open-model-deploy-gcp`** project (originally `gemma_deploy`) is an end-to-end cloud infrastructure, inference acceleration, and agentic evaluation framework. It bridges this gap by combining **ephemeral zero-idle cloud serving**, **prompt-lookup speculative decoding**, and a **hierarchical multi-agent labor architecture with Pareto-evolved runbooks**. The platform was proven against an enterprise Security Operations Center (SOC) Tier 1 benchmark, cutting operational decision loss by **99.8%** and eliminating catastrophic production downtime false alarms on mission-critical infrastructure.

---

## 2. Key Technical Pillars & Architectural Innovations

### A. Multi-Substrate Ephemeral Inference Engine ($0.00 Idle Waste)
* Designed a centralized model catalog (`configs/models.json`) mapping 3 generations of Gemma (2, 3, 4: 1B through 31B) and partner open weights (Llama 3/4, Qwen 3.8, Nemotron) to exact GCP GPU accelerator topologies (1x/4x NVIDIA L4, 2x A100).
* Engineered automated orchestration across four distinct GCP compute substrates: **Cloud Run with GPU** (serverless scale-to-zero), **GCE Ephemeral Spot GPU VMs** (startup-script NVMe RAID formatting, automated self-deletion), **Vertex AI Custom Jobs**, and **GKE Ray Clusters with Kueue**.
* Orchestrated multi-model sweeps across 32+ architectures with guaranteed **$0.00 idle compute leak**, systematically logging over 8 hours of autonomous GPU benchmarks.

### B. Inference Acceleration: Speculative Decoding & Native FP8
* Implemented **N-gram Prompt Lookup Speculative Decoding** on containerized vLLM endpoints with zero additional VRAM overhead, delivering **1.5x to 2.3x steady-state generation speedups** across edge architectures (e.g., Gemma 2 9B accelerated from 7.0 to 16.0 tok/s; Gemma 3 1B to 76.86 gen TPS).
* Deployed native **FP8 quantization** on Ada Lovelace (NVIDIA L4) and two-model draft speculative architectures (Gemma 4 31B drafted by E2B/E4B on 2x A100 at 55 gen TPS), slashing dedicated hosting costs to **$6.27 per 1M tokens**.

### C. Gen 3 Interactive Evaluation Harness: Signal Detection & Financial Loss
* Built a stateful simulation sandbox (`agent/soc_environment.py`) simulating enterprise networks, endpoint process trees, CMDB registries, and transient infrastructure faults (HTTP 503 error injection).
* Replaced standard token-matching metrics with **Signal Detection Theory ($d'$, criterion bias $c$)** and an **asymmetric operational loss engine**:
  $$\text{Loss} = L_{FP} \cdot (\text{Host Downtime Blast Radius}) + L_{FN} \cdot (\text{Adversary Breach})$$
  Penalizing unauthorized mission-critical server isolations at $50,000 and uncontained enterprise breaches at $250,000.
* Integrated a trajectory-aware semantic judge and strict epistemic verification gates (`epistemic_step_count >= 1`), penalizing models that make ungrounded claims or hallucinate tool results.

### D. Hierarchical Multi-Agent Orchestration & Anti-Memorization GEPA Evolution
* Solved the edge-model cognitive breakdown by decoupling labor: a **Specialized Runbook Worker** handles epistemic evidence gathering, while a **Supervisor Agent** enforces containment actions and SOAR documentation, lifting operator tool compliance from 10% to 80-90%.
* Implemented **GEPA (Genetic Engine for Prompt Ad-hoc Optimization)** to evolve natural-language playbooks via Gemini 2.5 Pro reflection.
* Engineered an **anti-memorization candidate validator** (`validate_runbook_candidate`) and train/validation split (holding out test scenarios) to reject hardcoded network literals, IP subnets, and shortcut skips, yielding a generalized 4-stage epistemic verification playbook.

---

## 3. Quantified Impact (Google GRAD & CV Highlights)

* **Operational Financial Risk Reduction**: Slashed expected operational loss by **99.8%** (from **$55,050.56** down to **$100.82**) on enterprise benchmark evaluations using `gemini-2.5-flash-lite`.
* **Zero Catastrophic Downtime**: Prevented unauthorized host isolations on mission-critical payment processing servers (`SRV-PROD-PAYMENT-01`) and core VPN gateways (`GW-CORE-VPN-01`), saving **$100,000 in simulated business downtime**.
* **Zero Breach Escape**: Maintained a **92.9% empirical hit rate** across active malware, ransomware, and credential harvesting attacks with **$0.00 False Negative breach loss**.
* **Inference Efficiency**: Achieved **+127% (2.3x) generation speedups** via Prompt Lookup Speculative Decoding with 0 extra VRAM footprint.
* **Cost Governance**: Maintained **100% resource reclamation ($0.00 compute leak)** across dozens of GPU VM sweeps via autonomous ephemeral self-deletion.
* **Engineering Rigor**: Authored **311 comprehensive unit and integration tests** passing cleanly with 100% green build status in 47s.

---

## 4. Direct CV Bullet Points

* **Architected Autonomous AI Infrastructure:** Designed and deployed an ephemeral multi-model serving platform across GCP (Vertex AI, Cloud Run GPU, GCE Spot, GKE Ray), automating sizing, deployment, and testing across 30+ open-weight (Gemma 2/3/4, Llama, Qwen) and frontier architectures with $0.00 idle compute leak.
* **Inference Optimization & Speculative Decoding:** Productionized N-gram prompt lookup speculative decoding and FP8 quantization in vLLM, accelerating edge-model generation throughput by 1.5x–2.3x (up to 76 gen tok/s) with zero VRAM penalty, reducing serving cost to $6.27 / 1M tokens.
* **Gen 3 Stateful Evaluation Engine:** Built an interactive cyber simulation environment pairing Signal Detection Theory ($d'$) with an asymmetric financial loss matrix ($50k false positive downtime vs. $250k breach escape), replacing synthetic string evals with trajectory-grounded semantic verification.
* **Multi-Agent Systems & Genetic Prompt Evolution (GEPA):** Engineered a hierarchical supervisor-worker agent architecture and Pareto evolutionary optimization loop with anti-memorization guardrails, cutting autonomous Tier 1 SOC operational decision loss by 99.8% ($55k -> $100) and preventing catastrophic production outages.
