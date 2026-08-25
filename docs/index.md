---
title: "Gemma Deployment Knowledge Catalog"
description: "Index and catalog of all technical guides, cost analyses, and operational documentation for deploying Gemma on Google Cloud."
type: "index"
tags:
  - gemma
  - index
  - catalog
  - vertex-ai
  - cloud-run
created: 2026-08-24
updated: 2026-08-24
---

# Gemma Deployment Knowledge Catalog

This directory forms an Open Knowledge Format (OKF) compliant knowledge bundle for deploying Google Gemma models on Google Cloud Platform.

---

## Catalog Index

| Document | Type | Description |
| :--- | :--- | :--- |
| [`gemma_soc_agent_evaluation_plan.md`](gemma_soc_agent_evaluation_plan.md) | `plan` | Gemma SOC Tier 1 agent implementation, deployment & rubric evaluation plan |
| [`gemma4_performance_optimization_plan.md`](gemma4_performance_optimization_plan.md) | `plan` | Gemma 4 performance analysis, optimization roadmap & empirical findings |
| [`deployment_status.md`](deployment_status.md) | `guide` | Live deployment tracking, multi-model compatibility matrix & test records |
| [`experiments_status.md`](experiments_status.md) | `status` | Gemma 4 Vertex AI performance optimization experiment logs & benchmarks |
| [`cloudrun_experiments_status.md`](cloudrun_experiments_status.md) | `status` | Cloud Run GPU deployment experiments, benchmarks & scale-to-zero tracking |
| [`cloudrun_deploy.md`](cloudrun_deploy.md) | `guide` | Deploying Gemma to Cloud Run with NVIDIA L4 GPU & Scale-to-Zero |
| [`cost_analysis.md`](cost_analysis.md) | `analysis` | Hardware sizing, VRAM requirements, and pricing projections |
| [`quota_requests.md`](quota_requests.md) | `status` | Google Cloud GPU quota requests & experiment unblocking log |
| [`research.md`](research.md) | `research` | Best practices for deploying Gemma across Agent Platform, Cloud Run, GKE, and TPUs |
| [`managed_vs_deploy.md`](managed_vs_deploy.md) | `guide` | Comparison of Model as a Service (MaaS) vs self-deployed GPU endpoints |
| [`vertex_deployment_notes.md`](vertex_deployment_notes.md) | `guide` | Vertex AI Online Prediction deployment & troubleshooting solutions |
| [`vertex_cleanup_strategies.md`](vertex_cleanup_strategies.md) | `architecture` | Automated scheduled and metric-based cleanup architectures |
| [`speculative_decoding.md`](speculative_decoding.md) | `architecture` | Speculative decoding guide, N-gram prompt lookup mechanics & Vertex AI benchmarks |
| [`model_registry_catalog.md`](model_registry_catalog.md) | `guide` | Authoritative catalog of all registered Vertex AI models, container specs & creation commands |
| [`references.md`](references.md) | `reference` | Curated external guides, Google Cloud community articles & ADK references |


