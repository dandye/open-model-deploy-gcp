# GEPA Runbook Evolution Subsystem Design Specification

## 1. Problem Statement & Motivation

Empirical evaluations of hierarchical and single-agent SOC Tier 1 architectures on `gemini-2.5-flash-lite` revealed critical operational tradeoffs:
- **Baseline (No Runbooks)**: 20% Pass Rate, 58.0/100 Rubric, 10% Operator Compliance, 24 tool calls.
- **Hierarchical Control (No Runbooks)**: 20% Pass Rate, 57.0/100 Rubric, 80% Operator Compliance, 46 tool calls, 66.7% False Alarm Rate, d' = 1.03.
- **Hierarchical + Static Playbooks**: 30% Pass Rate, 59.8/100 Rubric, 90% Operator Compliance, 52 tool calls, 33.3% False Alarm Rate, d' = 1.50 (+45% discrimination lift).

While procedural runbooks cut the false alarm rate in half and boosted operator compliance from 10% to 90%, human-authored playbooks from `third_party/ai-runbooks` exhibit structural flaws:
1. **Lack of Explicit Boundary Rules**: Playbooks lack explicit instructions for benign non-routable documentation subnets (RFC-5737: `192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`) and authorized internal scanners (Qualys: `10.0.99.50`). As a result, agents over-isolate benign assets (e.g. `CASE-02` documentation test and `CASE-10` scheduled vulnerability scanner).
2. **Superfluous Non-Actionable Content**: Playbooks include raw Mermaid diagrams, CLI instructions (`ask_followup_question`), and verbose formatting that consume agent context without improving triage precision.
3. **Sub-optimal Containment Gating**: Playbooks do not clearly decouple initial enrichment and verification from destructive containment actions (`isolate_host`, `block_ip`), leading to premature actions or false positives.

To resolve these defects systematically, we build a GEPA (Genetic Engine for Prompt Ad-hoc Optimization) evolution pipeline that mutates runbooks against live benchmark evaluations using multi-objective Pareto optimization.

---

## 2. Architecture & Data Flow

```
                      +---------------------------------------+
                      |   configs/evals/gen3/                 |
                      |   soc_tier1_interactive.json (10 Cases)|
                      +-------------------+-------------------+
                                          |
                      +-------------------v-------------------+
                      |         GEPA Optimization Loop        |
                      |    (agent/gepa_runbook_optimizer.py)  |
                      +-------------------+-------------------+
                                          |
        +---------------------------------+---------------------------------+
        |                                                                   |
        v                                                                   v
+-----------------------------+                             +-----------------------------+
|   RunbookGEPAAdapter        |                             |   Reflection Engine         |
|   (Hierarchical Agent Eval) |                             |   (GoogleGenAILM)           |
+--------------+--------------+                             +--------------+--------------+
               |                                                           ^
               | Rollout Trajectories & Scores                             | Propose Mutation
               +-----------------------------------------------------------+
                                          |
                                          v
                      +---------------------------------------+
                      | Pareto-Optimal Runbook Output         |
                      | (configs/runbooks/gepa_evolved/)      |
                      +---------------------------------------+
```

### Component Details
1. **Seed Runbook Pool**:
   Read from `third_party/ai-runbooks/.clinerules/run_books/`:
   - `basic_ioc_enrichment.md` (Enrichment and verification of IP, domain, and file hashes)
   - `suspicious_login_triage.md` (Identity, brute force, and multi-factor triage)
   - `malware_triage.md` (Endpoint malware, reverse shell, and persistence triage)
   - `lateral_movement_hunt_psexec_wmi.md` (Lateral movement and administrative tool abuse)
2. **Execution Engine (`RunbookGEPAAdapter`)**:
   - Subclasses `gepa.GEPAAdapter`.
   - `evaluate(batch, candidate, capture_traces)`:
     - Instantiates `HierarchicalSOCTier1Agent` loaded with the candidate runbooks.
     - Runs the agent on test cases in `batch`.
     - Executes real tools or mock tool harness as configured.
     - Computes multi-objective fitness scores and captures detailed execution traces.
   - `make_reflective_dataset(candidate, eval_batch, components_to_update)`:
     - Formats diagnostic failure records for the components requested.
     - Surfaces input case prompts, executed trajectories, failed assertions, grounding scores, and containment errors.
3. **Reflection Engine (`GoogleGenAILM`)**:
   - Wraps Google GenAI API (`gemini-2.5-pro` or `gemini-2.5-flash` / Vertex AI).
   - Receives current runbook markdown and diagnostic failure cases.
   - Generates evolved markdown incorporating boundary conditions and removing noise.
4. **Target Output**:
   - Clean evolved runbooks written to `configs/runbooks/gepa_evolved/`.
   - Directly usable by `HierarchicalSOCTier1Agent` via `--runbooks-dir configs/runbooks/gepa_evolved`.

---

## 3. Candidate Representation & Multi-Objective Fitness Metric

### Candidate Representation
A candidate is a dictionary mapping each runbook filename to its full markdown content:
```python
Candidate = dict[str, str]
# Example:
# {
#     "basic_ioc_enrichment.md": "# Basic IOC Enrichment\n...",
#     "suspicious_login_triage.md": "# Suspicious Login Triage\n...",
#     "malware_triage.md": "# Malware Triage\n...",
#     "lateral_movement_hunt_psexec_wmi.md": "# Lateral Movement Hunt\n..."
# }
```

### Fitness Metric Formulation
For each evaluated case $i \in \{1, \dots, N\}$:
$$\text{Fitness}_i = 0.40 \cdot \text{Rubric}_i + 0.20 \cdot \text{AssertPass}_i + 0.20 \cdot \text{OperatorCompliance}_i + 0.20 \cdot \text{LossPenalty}_i$$

Where:
- $\text{Rubric}_i \in [0.0, 1.0]$: Normalized aggregate rubric score from the semantic judge (composite of accuracy, reasoning, grounding).
- $\text{AssertPass}_i \in \{0.0, 1.0\}$: Binary indicator (1.0 if all case assertions pass, 0.0 otherwise).
- $\text{OperatorCompliance}_i \in [0.0, 1.0]$: Verified operator tool adherence score (1.0 if mandatory containment/investigative tool actions match expected actions).
- $\text{LossPenalty}_i = \exp(-L_i / 10000.0)$: Operational loss penalty.
  - For false positive containment on benign entities (isolating RFC-5737 documentation IPs or Qualys vulnerability scanners): $L_i = 10000 \implies \text{LossPenalty}_i = \exp(-1) \approx 0.368$.
  - For false negative containment on critical threats (failing to isolate active ransomware/C2): $L_i = 10000 \implies \text{LossPenalty}_i = \exp(-1) \approx 0.368$.
  - For clean, correct triage: $L_i = 0 \implies \text{LossPenalty}_i = 1.0$.

Global score for candidate evaluation:
$$\text{Score}(\text{candidate}) = \frac{1}{|B|} \sum_{i \in B} \text{Fitness}_i$$

The GEPA optimizer uses minibatch sum for acceptance checks and full dataset mean for Pareto-front maintenance.

---

## 4. Reflection & Mutation Engine

### Diagnostic Feedback Structure
When an evaluation case underperforms ($\text{Fitness}_i < 0.85$ or assertion failed or false positive action executed), `RunbookGEPAAdapter.make_reflective_dataset()` formats a structured record:
```json
{
  "Inputs": {
    "case_id": "CASE-02",
    "alert_type": "C2_BEACON",
    "prompt": "Investigate potential C2 beaconing to 192.0.2.14..."
  },
  "Generated Outputs": {
    "verdict": "MALICIOUS",
    "executed_actions": ["isolate_host", "block_ip"],
    "tool_calls_count": 5
  },
  "Feedback": "CRITICAL FALSE POSITIVE: The agent executed 'isolate_host' and 'block_ip' on RFC-5737 test/documentation IP 192.0.2.14. RFC-5737 subnets (192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24) are non-routable documentation ranges. The runbook MUST explicitly instruct the analyst to verify if the IOC belongs to RFC-5737 or internal testing ranges, and if so, classify as BENIGN without executing host isolation."
}
```

### Reflection Prompt Template
A specialized domain prompt template guides the reflection LM (`gemini-2.5-pro`):
- Instructions to add explicit validation guards for benign test ranges and authorized scanners.
- Instructions to preserve strict containment steps for actual malware and C2 activity.
- Enforces removal of unexecutable CLI syntax, raw Mermaid blocks, and non-actionable verbosity.
- Enforces strict markdown formatting with zero emojis.

---

## 5. Storage & Evaluation Integration

### Directory Layout
- `configs/runbooks/gepa_evolved/`:
  - `basic_ioc_enrichment.md`
  - `suspicious_login_triage.md`
  - `malware_triage.md`
  - `lateral_movement_hunt_psexec_wmi.md`
  - `evolution_metadata.json` (Pareto front scores, generation count, timestamp)

### CLI & Justfile Commands
1. Run GEPA evolution:
   ```bash
   just gepa-evolve
   # or
   .venv/bin/python3 agent/gepa_runbook_optimizer.py --max-metric-calls 20 --reflection-lm gemini-2.5-pro --task-lm gemini-2.5-flash-lite
   ```
2. Run Comparative Evaluation:
   ```bash
   just gepa-compare
   # Evaluates gemini-2.5-flash-lite on:
   # 1. Baseline (No runbooks)
   # 2. Raw Human Runbooks (third_party/ai-runbooks)
   # 3. GEPA-Evolved Runbooks (configs/runbooks/gepa_evolved)
   ```
3. Analysis Report:
   Saved to `docs/soc_eval_results/GEPA_RUNBOOK_EVALUATION_ANALYSIS.md`.

---

## 6. Verification Plan & Success Criteria

1. **Unit Test Coverage**:
   - `tests/test_gepa_runbook_optimizer.py`:
     - Test candidate initialization from raw runbooks.
     - Test `RunbookGEPAAdapter.evaluate` scoring and trace capture.
     - Test `RunbookGEPAAdapter.make_reflective_dataset` feedback formatting.
     - Test fitness computation including `LossPenalty` scaling.
2. **Behavioral Milestones**:
   - RFC-5737 False Positive Elimination: `CASE-02` passes without triggering host isolation.
   - Qualys Scanner False Positive Elimination: `CASE-10` passes without triggering host isolation.
   - Threat Containment Preservation: `CASE-01`, `CASE-04`, `CASE-05` maintain 100% containment action compliance.
   - Overall Pass Rate: Increase from 30% to >= 60% on `gemini-2.5-flash-lite`.
   - Discrimination Index $d'$: Maintain or improve beyond $d' = 1.50$.
