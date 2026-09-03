# Gen 3 Agentic Evaluation Framework Design Spec

**Date:** 2026-09-01  
**Project:** `gemma_deploy`  
**Status:** Approved for Implementation

---

## 1. Executive Summary & Problem Statement

Conventional LLM benchmarks evaluate models through static question-answering, lexical string assertions (`must_contain: ["escalat"]`), and open-ended text judges. In cybersecurity and agentic decision-making, this paradigm creates severe distortions:
1. **The Essay Trap**: Rewarding verbose markdown formatting rather than decisive operational actions.
2. **The Static Snapshot Trap**: Providing all context in a single prompt rather than requiring active search across partial observations.
3. **The Symmetric Loss Trap**: Penalizing a false positive (disrupting a CFO during quarterly earnings) equally with a false negative (missing active ransomware).

The **Gen 3 Agentic Evaluation Framework** transitions the evaluation of self-hosted Gemma models (and comparison models) into an **interactive, decision-theoretic evaluation engine** grounded in Signal Detection Theory ($d'$, $c$), cost-weighted blast radius matrices, epistemic trajectory verification, and edge vs. frontier routing boundaries.

---

## 2. System Architecture

```
                                  ┌──────────────────────────────────────────────┐
                                  │      Gen 3 Interactive Evaluation Runner     │
                                  │           (scripts/eval_soc_agent.py)        │
                                  └──────────────────────┬───────────────────────┘
                                                         │
               ┌─────────────────────────────────────────┼─────────────────────────────────────────┐
               │                                         │                                         │
┌──────────────▼──────────────┐           ┌──────────────▼──────────────┐           ┌──────────────▼──────────────┐
│  1. Interactive SOC Sandbox │           │  2. Trajectory Action       │           │  3. Cost-Weighted Decision  │
│  & Environment State Machine│           │     & EVOI Verifier         │           │     Loss & SDT Engine       │
│  (agent/soc_environment.py) │           │  (scripts/eval_verifier.py) │           │  (scripts/eval_cost_engine) │
└──────────────┬──────────────┘           └──────────────┬──────────────┘           └──────────────┬──────────────┘
               │                                         │                                         │
               │ - State: Hosts, IPs, Hashes             │ - Action execution checks               │ - Signal Detection (d', c)  │
               │ - Tools: Query & Action execution       │ - Hypothesis entropy & EVOI             │ - Blast-radius loss ($)     │
               │ - Fault injection: 503s, noise          │ - Stopping criteria economy             │ - Edge vs Frontier Boundary │
               │ - Counterfactual branches               │ - Degraded mode resilience              │ - Token & Latency Economics │
               └─────────────────────────────────────────┴─────────────────────────────────────────┘
```

---

## 3. Core Subsystems & Interfaces

### 3.1 Interactive SOC Sandbox (`agent/soc_environment.py`)
Maintains a dynamic environment state machine with:
* **Entities**: Hosts (`hostname`, `ip`, `criticality_tier`, `isolated`, `os`, `active_user`), Hashes (`sha256`, `cert_status`, `threat_name`), Domains (`domain`, `reputation`, `malicious_votes`, `harmless_votes`), and Accounts.
* **Epistemic Tools** (Information gathering): `get_ip_report`, `get_domain_report`, `get_file_report`, `lookup_entity`, `list_cases`, `udm_search`.
* **Pragmatic Tools** (State-changing interventions): `isolate_host(hostname)`, `unblock_host(hostname)`, `block_indicator(indicator)`, `update_case_comment(case_id, comment)`, `close_case(case_id, verdict)`.
* **Dynamic Perturbations**:
  * Outage injection: Returns HTTP 503 / timeout for specific tools.
  * Counterfactual state flips: Valid vendor signature vs revoked key.
  * Asset criticality modulation: Dev VM vs CFO workstation vs Domain Controller.

### 3.2 Epistemic Trajectory & Action Verifier (`scripts/eval_trajectory_verifier.py`)
Validates the actual sequence of actions taken:
* **Action Verification**: Confirms whether the agent invoked the concrete programmatic action (e.g. calling `isolate_host` vs merely printing text).
* **Entropy & EVOI (Information Gain)**: Measures whether investigative tool queries meaningfully reduced uncertainty over the threat hypothesis.
* **Degraded Mode Resilience**: Confirms whether the model explicitly communicated evidentiary gaps when receiving tool errors without fabricating facts.

### 3.3 Cost-Weighted Decision Loss & SDT Engine (`scripts/eval_cost_engine.py`)
Evaluates the agent using formal Signal Detection Theory and operational financial impact:
* **Sensitivity Index ($d'$)**: $d' = Z(H) - Z(F)$, measuring discrimination between true threats and benign activity.
* **Criterion Bias ($c$)**: $c = -\frac{1}{2} (Z(H) + Z(F))$, measuring containment conservatism vs aggressiveness.
* **Blast-Radius Operational Financial Loss**:
  $$\text{Expected Loss} = \sum (\text{FP Loss} + \text{FN Loss} + \text{Inference Cost})$$
  * $L(\text{FP, Critical}) = \$50,000$ (e.g. isolating CFO / Payment API during production close).
  * $L(\text{FP, Standard}) = \$50$ (brief ticket review for normal workstation).
  * $L(\text{FN, High}) = \$250,000$ (uncontained ransomware / credential dump).
  * $L(\text{FN, Low}) = \$200$ (adware).

### 3.4 Gen 3 Dataset Suites (`configs/evals/gen3/`)
* `configs/evals/gen3/soc_tier1_interactive.json`: 10 interactive scenarios with state definitions, criticality tiers, counterfactual perturbations, and asymmetric loss weights.
* `configs/evals/gen3/soc_live_mcp_interactive.json`: 10 interactive scenarios executing against Google SecOps Remote MCP.

---

## 4. Evaluation Outputs & Scorecards
The Gen 3 runner outputs:
1. **Standard Scorecard**: Pass rate, average rubric score, latency, generation TPS.
2. **SDT & Loss Matrix**: $d'$ index, decision bias $c$, and dollar-weighted operational loss.
3. **Model Boundary Map**: Auto-Resolution rate (safe for edge Gemma) vs Escalation rate (routed to frontier model).
