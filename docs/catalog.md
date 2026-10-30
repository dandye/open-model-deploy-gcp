---
title: "Full Documentation Catalog"
description: "Index and catalog of all technical guides, evaluation reports, blog posts, cost analyses, and operational documentation for Open Model & Gemma Deployment on Google Cloud."
type: "index"
tags:
  - gemma
  - index
  - catalog
  - vertex-ai
  - cloud-run
  - evaluation
  - gepa
  - harness2
created: 2026-08-24
updated: 2026-10-21
---

# Full Documentation Catalog

This catalog indexes all architecture specifications, multi-model benchmark reports, GEPA and `Harness^2` runbook evolution studies, blog posts, and Google Cloud deployment guides in `open-model-deploy-gcp`.

---

## Catalog Index

| Document | Type | Description |
| :--- | :--- | :--- |
| [`PROJECT_SUMMARY.md`](PROJECT_SUMMARY.md) | `summary` | Executive summary of implemented capabilities, evidence handling, and validation scope |
| [`RUNBOOK_AUTHORING_BEST_PRACTICES.md`](RUNBOOK_AUTHORING_BEST_PRACTICES.md) | `guide` | Empirical 10-rule runbook authoring & context hygiene standard (`RB-01`..`RB-05`) |
| [`soc_eval_results/OVERNIGHT_SWEEP_SUMMARY.md`](soc_eval_results/OVERNIGHT_SWEEP_SUMMARY.md) | `analysis` | Master dynamic benchmark leaderboard across Vertex AI, Cloud Run GPU, and MaaS |
| [`soc_model_comparative_evals.md`](soc_model_comparative_evals.md) | `analysis` | Multi-model capability matrix & comparative analysis (Gemma vs. Gemini tiers) |
| [`llama_model_comparative_evals.md`](llama_model_comparative_evals.md) | `analysis` | Detailed Meta Llama, NVIDIA Nemotron, Qwen, and partner comparative scorecards |
| [`soc_eval_results/dspy_overnight/MORNING_REPORT.md`](soc_eval_results/dspy_overnight/MORNING_REPORT.md) | `analysis` | 9-hour DSPy context engineering hygiene & constrained GEPA runbook compression report |
| [`soc_eval_results/DSPY_RLM_WORKER_EVALUATION_ANALYSIS.md`](soc_eval_results/DSPY_RLM_WORKER_EVALUATION_ANALYSIS.md) | `analysis` | DSPy `dspy.RLM` (Recursive Language Model) vs. ReAct SOC Worker evaluation (`57.5%` / `2.35x` hunt speedup & `0.3300 -> 1.0000` unstripped runbook recovery) |
| [`soc_eval_results/harness2_8h_campaign/HARNESS2_CAMPAIGN_REPORT.md`](soc_eval_results/harness2_8h_campaign/HARNESS2_CAMPAIGN_REPORT.md) | `analysis` | 8-hour $\text{Harness}^2$ (`arXiv:2610.14224`) Propose-Probe-Compose recursive runbook evolution & 228-trajectory multi-model transfer report |
| [`soc_eval_results/harness2_8h_campaign/gen5_transfer/GEN5_TRANSFER_SCORECARD.md`](soc_eval_results/harness2_8h_campaign/gen5_transfer/GEN5_TRANSFER_SCORECARD.md) | `analysis` | 3-model $\times$ 3-arm Gen 5 validation transfer matrix (`180` trajectories, `-89.1%` vs. seed and `-94.5%` vs. single-proposer operational loss) |
| [`soc_eval_results/harness2_8h_campaign/threat_hunt_multi_model/THREAT_HUNT_MULTI_MODEL_SCORECARD.md`](soc_eval_results/harness2_8h_campaign/threat_hunt_multi_model/THREAT_HUNT_MULTI_MODEL_SCORECARD.md) | `analysis` | 3-model $\times$ 4-arm Track 2 proactive threat-hunting (`ThreatHuntEnvironment`) transfer scorecard (`48` trajectories) |
| [`gemma_soc_agent_evaluation_plan.md`](gemma_soc_agent_evaluation_plan.md) | `plan` | Expanded 10-case Gemma SOC Tier 1 agent implementation, deployment & rubric evaluation plan |
| [`llama_soc_agent_evaluation_plan.md`](llama_soc_agent_evaluation_plan.md) | `plan` | Evaluation blueprint & methodology for Meta Llama and partner open-weight models |
| [`thoughts_on_evals.md`](thoughts_on_evals.md) | `architecture` | Core philosophy on benchmark discriminative power & capability gradients |
| [`soc_eval_failure_analysis.md`](soc_eval_failure_analysis.md) | `analysis` | Failure analysis of `CASE-01`, synthetic GTI hallucination & ReAct next steps |
| [`hillclimber_rrsi_crosswalk.md`](hillclimber_rrsi_crosswalk.md) | `analysis` | Disciplined Hillclimber guards vs. RRSI proposer and selector regularizers & Harness-Delta Attribution |
| [`jev_vs_gemini_judge_evaluation.md`](jev_vs_gemini_judge_evaluation.md) | `analysis` | Jev System-One single-token logprob judge vs. generative Gemini 2.5 Pro chain-of-thought judge |
| [`experiment_protocol.md`](experiment_protocol.md) | `plan` | Bounded SOC comparison experiment protocol for one deployment decision |
| [`evals_gen5.md`](evals_gen5.md) | `guide` | Gen 5 family-instanced SOC suite: build, check, calibrate, run, optimize, Harbor, gates, ledger |
| [`superpowers/specs/2026-10-04-gen5-evals-design.md`](superpowers/specs/2026-10-04-gen5-evals-design.md) | `plan` | Design spec for the Gen 5 suite: families, instancer, splits, scoring, exposure ledger, Harbor policy |
| [`soc_eval_results/GEN5_CALIBRATION.md`](soc_eval_results/GEN5_CALIBRATION.md) | `analysis` | Reference-policy calibration (Oracle, Inert, Shotgun, Close-all) in both transports |
| [`evaluation_decision_record.md`](evaluation_decision_record.md) | `plan` | Evaluation and deployment decision record template |
| [`soc_eval_results/DISCIPLINED_HILLCLIMBER_RUN_ANALYSIS.md`](soc_eval_results/DISCIPLINED_HILLCLIMBER_RUN_ANALYSIS.md) | `analysis` | Evidence review of the 2026-10-02 GEPA run: noise floor, acceptance ledger, cost staircase caveats |
| [`soc_eval_results/GEPA_EVIDENCE_RECONCILIATION.md`](soc_eval_results/GEPA_EVIDENCE_RECONCILIATION.md) | `analysis` | Reconciliation of GEPA narrative tables against pinned JSON artifacts (SHA-256, simulated-loss labeling) |
| [`soc_eval_results/GEPA_RUNBOOK_EVALUATION_ANALYSIS.md`](soc_eval_results/GEPA_RUNBOOK_EVALUATION_ANALYSIS.md) | `analysis` | September 2026 GEPA-evolved runbook evaluation on `gemini-2.5-flash-lite` |
| [`soc_eval_results/GEPA_MCP_EVALUATION_ANALYSIS.md`](soc_eval_results/GEPA_MCP_EVALUATION_ANALYSIS.md) | `analysis` | Default MCP vs. Gusto GEPA-optimized MCP tool descriptions in the Gen 3 interactive suite |
| [`blog/gepa_runbook_evolution_and_disciplined_hillclimbing.md`](blog/gepa_runbook_evolution_and_disciplined_hillclimbing.md) | `blog` | Evolving SecOps runbooks without cheating: GEPA memorization, judge verbosity bias, five guards & RRSI crosswalk |
| [`blog/gepa_mcp_tool_description_optimization.md`](blog/gepa_mcp_tool_description_optimization.md) | `blog` | Evolving SecOps MCP tool descriptions with GEPA |
| [`blog/dspy_rlm_recursive_language_models_for_secops.md`](blog/dspy_rlm_recursive_language_models_for_secops.md) | `blog` | Recursive Language Models (`dspy.RLM`) in the SOC: when a Python REPL beats ReAct, when it over-pivots, and hybrid `worker_mode="auto"` routing |
| [`blog/part1_zero_idle_gpu_infrastructure.md`](blog/part1_zero_idle_gpu_infrastructure.md) | `blog` | Serving Open Models for Security Agents, Part 1: building a repeatable experiment |
| [`references_agent_harness_literature.md`](references_agent_harness_literature.md) | `reference` | Annotated bibliography: RRSI, Harness-Delta Attribution, GEPA, hillclimbing guides, sandboxes & benchmarks |
| [`gemma4_performance_optimization_plan.md`](gemma4_performance_optimization_plan.md) | `plan` | Gemma 4 performance analysis, optimization roadmap & empirical findings |
| [`model_registry_catalog.md`](model_registry_catalog.md) | `catalog` | Authoritative Vertex AI Model Registry inventory and serving configurations |
| [`deployment_status.md`](deployment_status.md) | `guide` | Live deployment tracking, multi-model compatibility matrix & test records |
| [`experiments_status.md`](experiments_status.md) | `status` | Gemma 4 Vertex AI performance optimization experiment logs & benchmarks |
| [`cloudrun_experiments_status.md`](cloudrun_experiments_status.md) | `status` | Cloud Run GPU deployment experiments, benchmarks & scale-to-zero tracking |
| [`cloudrun_deploy.md`](cloudrun_deploy.md) | `guide` | Deploying Gemma to Cloud Run with NVIDIA L4 GPU & Scale-to-Zero |
| [`cost_analysis.md`](cost_analysis.md) | `analysis` | Hardware sizing, VRAM requirements, and pricing projections |
| [`quota_requests.md`](quota_requests.md) | `status` | Google Cloud GPU quota requests & experiment unblocking log |
| [`research.md`](research.md) | `research` | Best practices for deploying Gemma across Agent Platform, Cloud Run, GKE, and TPUs |
| [`managed_vs_deploy.md`](managed_vs_deploy.md) | `guide` | Comparison of Model as a Service (MaaS) vs. self-deployed GPU endpoints |
| [`vertex_deployment_notes.md`](vertex_deployment_notes.md) | `guide` | Vertex AI Online Prediction deployment & troubleshooting solutions |
| [`vertex_cleanup_strategies.md`](vertex_cleanup_strategies.md) | `architecture` | Automated scheduled and metric-based cleanup architectures |
| [`speculative_decoding.md`](speculative_decoding.md) | `architecture` | Speculative decoding guide, N-gram prompt lookup mechanics & Vertex AI benchmarks |
| [`future_work.md`](future_work.md) | `plan` | Strategic roadmap, hybrid model gateway, LoRA distillation, and POMDP integration tracks |
| [`benchmarking_gce_ephemeral_spot_vms.md`](benchmarking_gce_ephemeral_spot_vms.md) | `guide` | Compute Engine Ephemeral Spot GPU VMs runner, NVMe caching & multi-zone failover |
| [`benchmarking_vertex_custom_jobs.md`](benchmarking_vertex_custom_jobs.md) | `guide` | Vertex AI Custom Jobs ephemeral container runner & worker pool sizing |
| [`benchmarking_gke_ray_serve.md`](benchmarking_gke_ray_serve.md) | `guide` | GKE Ray Serve and Kueue dynamic batch queuing & distributed sweep runner |
| [`references.md`](references.md) | `reference` | Curated external guides, Google Cloud community articles & ADK references |
