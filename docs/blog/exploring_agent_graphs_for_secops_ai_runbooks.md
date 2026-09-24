# Exploring Agent Graphs for SecOps AI Runbooks

- **Author**: Dan Dye (Adoption Engineer, Security, Google Cloud)
- **Published**: August 2026 / Community Blog
- **Source**: https://security.googlecloudcommunity.com/community-blog-42/exploring-agent-graphs-for-secops-ai-runbooks-8113
- **Follow-up Evaluation Post**: [Evaluating Agent Graphs for SecOps AI Runbooks](https://security.googlecloudcommunity.com/community-blog-42/evaluating-agent-graphs-for-secops-ai-runbooks-8232) ([local tracking](evaluating_agent_graphs_for_secops_ai_runbooks.md))
- **Repository**: [github.com/dandye/adk_runbooks](https://github.com/dandye/adk_runbooks)
- **Documentation**: [dandye.github.io/adk_runbooks](https://dandye.github.io/adk_runbooks)

---

*Author: Dan Dye, Adoption Engineer, Security, Google Cloud*

The Agent Development Kit (ADK) project recently introduced [graph-based agent workflows](https://adk.dev/graphs/) and I highly recommend Romin Irani's [Google ADK 2 Graph Workflows: A Complete Guide with Code Examples](https://medium.com/google-cloud/google-adk-2-graph-workflows-a-complete-guide-with-code-examples-7e27046b85d5).

Can we use that to add determinism to agentic SecOps workflows? My goals are: **rigorous execution, deterministic control flows, known-working tool integration, and verifiable explainability**.

To that end, I've created an Agent Graph version of the [ADK Runbooks](https://github.com/dandye/adk_runbooks), an open-source, multi-agent cybersecurity operations framework built on top of [Google's Agent Development Kit (ADK)](https://github.com/google/adk) and the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/).

---

## The Vision: Executable Agent Graphs

In the security operation center (SOC), a runbook is a set of instructions for a human analyst: extract the IP, query the SIEM, enrich via threat intelligence, check recent user authentication logs, and document findings in the ticketing system. Incident Response Plans (IRPs) are a runbook subtype.

In the **ADK Runbooks** project, those runbooks are written for large language models (LLMs) (instead of humans) in persona-driven, multi-agent systems. This new work explores refactoring ADK Runbooks into agent graphs.

![Agent Graph Architecture Overview](https://uploads-us-west-2.insided.com/securitygooglecloud-en/attachment/b35e5400-f5fa-4fcf-8067-5f992983ee39.jpg)

---

## Domain-Specific Personas & Delegation

Agents assume personas within the security organization. A few examples:

- **Manager Agent**: Coordinates high-level objectives and routes tasks based on structured YAML capability profiles.
- **SOC Analysts (Tiers 1, 2, 3)**: Handle alert triage, deep-dive investigations, and complex root-cause forensic analysis.
- **Threat Hunter**: Proactively hunt across telemetry (using, for example, MITRE ATT&CK patterns).
- **CTI Researcher**: Synthesize Google Threat Intelligence (GTI) reports.
- **Detection Engineer**: Tune detection rules (ideally with Detection-as-Code).
- **Incident Responder**: Orchestrate incident response lifecycles (e.g. SANS PICERL).

---

## The Rules Bank: Grounding Agents in Enterprise Reality

We can tailor those agents by providing operational context. I don't have that kind of context for a full fictitious organization (yet!), so my grounding context in the "Rules Bank" is instead domain expertise that codifies:

- **Operational Runbooks & IRPs**: Step-by-step tactical workflows and end-to-end incident response plans (e.g., Malware, Phishing, Ransomware, Compromised Accounts).
- **Environmental Context**: Log source mappings, asset criticality guidelines, network maps, and known benign baselines to minimize false positives.
- **Explainability Standards**: Clear templates ensuring every automated recommendation includes primary evidence, confidence scores, and referenced protocols (i.e. "rubrics").

---

## Deterministic ADK Graph Workflows

The AI runbooks were already a step towards formalization of security work performed with the aid of reasoning language models. When I first configured a coding assistant with the MCP tools for Google SecOps and Google Threat Intelligence, there were lots of false starts and failures as the agent learned how and when to use the tools for each investigation. You don't want to lose that hard-won knowledge when you clear the session. Instead, you can prompt for a "handoff" or skill creation (or runbook!) to capture what was effective. That works surprisingly well. The next agent is more efficient as it avoids the pitfalls. But could we take that formalization a step further with graph workflows?

In [this feature branch](https://github.com/dandye/adk_runbooks/pull/65), I've converted 29+ runbooks and 4 Incident Response Plans into those **deterministic ADK Graph Workflows** (Directed Acyclic Graphs). Each step, from entity extraction and SecOps queries to VirusTotal/GTI enrichment and conditional risk routing, runs as a structured node with typed Pydantic schemas:

![Deterministic Graph Execution Pipeline](https://uploads-us-west-2.insided.com/securitygooglecloud-en/attachment/1f482068-13a8-41c0-bea8-bbfc610e1efa.jpg)

This guarantees predictable execution order while preserving LLM intelligence for reasoning when it is needed.

---

## MCP Security Tool Ecosystem

Agents interact with your security stack through standardized **Model Context Protocol (MCP)** servers:

- **Google SecOps (Chronicle SIEM & SOAR)**: Ingest alerts, search UDM events, inspect entity graphs, and post case commentary.
- **Google Threat Intelligence (GTI / VirusTotal)**: Score hashes, domains, and IP reputations with live actor campaign correlation.
- **Identity & Endpoint Telemetry**: Pivot seamlessly between user directories and host telemetry.

---

## Built-in Evaluation: LLM-as-a-Judge & PICERL Metrics

To evolve improvements, we need a hill to climb. Every runbook includes a rubric evaluated by an `llm_judge` agent. Every execution captures:

- **Tool Trajectory** via Mermaid sequence diagrams documenting the exact runtime call sequence.
- **Execution Metadata & Token Metrics** for minimizing cost and latency.
- **Structured Findings** formatted directly for SOAR case comments and executive summaries.

---

## Getting Started

The project is structured for easy local experimentation:

```bash
# Clone repository with submodules
git clone --recurse-submodules https://github.com/dandye/adk_runbooks.git
git checkout graph_v00001
cd adk_runbooks/multi-agent

# Set up environment & install dependencies
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Launch the ADK Web UI or CLI
adk web
```

---

## What's Next?

My goal is to push the boundaries of **Autonomous Security Operations.** We've seen that interactive chat sessions can be formalized into runbooks, which can in turn be formalized into agent graphs. I think the next step is to formalize even more and to offload with SOAR playbooks. That may feel like a step backwards, but my thesis is that this workflow enables exploration (similar to exploratory data analysis) for new scenarios with the assistance of a reasoning agent. Once that is done, it is overkill to reason about it all over again. We can instead harness the existing, proven automation tools we have on hand.

Take it for a spin, test out the workflows against your test cases, and let me know your thoughts and feedback!

- **Documentation & Runbook Index**: [dandye.github.io/adk_runbooks](https://dandye.github.io/adk_runbooks)
- **Source Code & Contributing**: [github.com/dandye/adk_runbooks](https://github.com/dandye/adk_runbooks)
