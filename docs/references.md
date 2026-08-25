---
title: "External References & Architectural Guides"
description: "Curated external guides, Google Cloud official documentation, and articles on Gemma 4 and Agent Platform integration."
type: "reference"
tags:
  - references
  - gemma4
  - agent-platform
  - vertex-ai
  - adk
created: 2026-08-25
updated: 2026-08-25
---

# External References & Architectural Guides

This document collects authoritative external references, Google Cloud community guides, and official documentation supporting our Gemma deployment and Agent Development Kit (ADK) implementations.

---

## 1. Gemma 4 & Agent Platform Integration

* **Article**: [How to deploy and personalize Gemma 4 on Agent Platform](https://medium.com/google-cloud/how-to-deploy-and-personalize-gemma-4-on-agent-platform-32364b7496e3)
* **Author / Publisher**: Google Cloud Community
* **Core Topics Covered**:
  * **Model Garden Deployment**: Serving Gemma 4 open-weight multimodal models on dedicated Vertex AI prediction nodes and Cloud Run GPU serverless infrastructure.
  * **Agent Development Kit (ADK) Integration**: Connecting Gemma 4 backends into the Agent Engine framework (`agent/` in this repository) for tool calling, structured reasoning, and autonomous multi-agent pipelines.
  * **Personalization Techniques**:
    1. **Retrieval-Augmented Generation (RAG)**: Supplying dynamic enterprise context to avoid retraining while ensuring factually grounded responses.
    2. **Parameter-Efficient Fine-Tuning (PEFT / LoRA)**: Customizing foundational behavior using Vertex AI Training clusters.
  * **Cloud Run Scale-to-Zero**: Utilizing serverless NVIDIA L4 GPU containers to achieve $0 idle serving costs.

---

## 2. Related Repository Implementations

* [`agent/`](../agent/): Production Agent Development Kit (ADK) agent configured for Vertex AI Agent Engine with dynamic backend auto-discovery.
* [`docs/managed_vs_deploy.md`](managed_vs_deploy.md): Comparison of Managed Model-as-a-Service (MaaS) vs self-deployed GPU endpoints.
* [`docs/cloudrun_deploy.md`](cloudrun_deploy.md): Serverless GPU deployment guide with scale-to-zero mechanics.
* [`docs/gemma4_performance_optimization_plan.md`](gemma4_performance_optimization_plan.md): Systematic optimization roadmap for Gemma 4 serving throughput.
* [Cloud Run GPU Configuration Guide](https://docs.cloud.google.com/run/docs/configuring/services/gpu#gcloud): Google Cloud official documentation for configuring NVIDIA L4 GPU acceleration and `--no-gpu-zonal-redundancy` on Cloud Run.
* [Google Security Operations Remote MCP](https://docs.cloud.google.com/chronicle/docs/secops/use-google-secops-mcp): Official documentation for configuring Google SecOps Remote MCP servers with AI agents and application frameworks.