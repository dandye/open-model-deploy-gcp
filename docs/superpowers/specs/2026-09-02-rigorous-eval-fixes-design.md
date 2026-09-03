# Technical Design Specification: Rigorous SOC Evaluation Framework Fixes

## 1. Problem Statement & Motivation

A critical review of the Gen 3 SOC Agent evaluation framework revealed that models were achieving 70% pass rates while executing 0 tool calls in 80-90% of test cases. This was caused by four interconnected structural vulnerabilities:
1. **Prompt Information Leakage**: Case prompts and `cmdb_context.blast_radius` leaked ground-truth diagnoses and explicit action directives (e.g. telling the model an IP is RFC-5737 documentation, or telling it a certificate is revoked and to block the indicator).
2. **Blind LLM Judge**: `judge_response_with_llm()` only saw the prompt, rubric, reference, and model final text. It had zero visibility into the actual tool execution trajectory, leading it to award full points and high grounding scores for fabricated telemetry that was never queried.
3. **Operator vs. Advisor Conflation**: `verify_agent_trajectory()` combined in-band executed tool calls with out-of-band text recommendations (`set(canonical_executed) | set(canonical_recommended)`), allowing pure text models to pass action verification without ever invoking tools.
4. **Zero-Tool ReAct Premature Termination**: Flash-tier models emitted the complete final report template in Step 0 without emitting `Action: ...`. The agent loop immediately halted, bypassing multi-step interactive investigation entirely.

## 2. Architecture & Design

### Component A: Prompt & CMDB Context Sanitization
- **File**: `configs/evals/gen3/soc_tier1_interactive.json`
- **Design**:
  - Purge ground-truth verdicts, diagnostic findings, and action commands from prompts and `cmdb_context`.
  - `cmdb_context` must strictly describe asset metadata, business role, owner, baseline criticality, and monetary downtime blast-radius penalty (e.g., "$50k/hr downtime disruption risk on payment processing").
  - Prompts must provide raw incident alerts with an objective instruction to investigate, triage, and take appropriate action.

### Component B: Trajectory-Aware LLM Judge
- **File**: `scripts/eval_soc_agent.py`
- **Design**:
  - Pass `trajectory: List[Dict[str, Any]]` into `judge_response_with_llm()`.
  - In `judge_prompt`, render an explicit `### Tool Execution Trajectory (Actual Tool Calls & Observations):` section detailing every tool called, arguments passed, and observations returned (or state `No tools were invoked during this investigation.`).
  - Instruct the judge:
    1. Grounding: All telemetry, IOC classifications, IP routes, process lists, and certificate statuses asserted in the agent response must be verifiable in the trajectory observations. If ungrounded, score grounding strictly below 0.70.
    2. Containment Execution: If the rubric requires containment, distinguish between executed tool calls in the trajectory vs. text recommendations. Text-only recommendations without tool execution must receive deductions on execution criteria.

### Component C: Operator vs. Advisor Action Verification
- **File**: `scripts/eval_trajectory_verifier.py`
- **Design**:
  - Update `TrajectoryVerificationResult` to track:
    - `operator_actions_matched: bool`: Checks if expected primary actions were actually executed via tools (`canonical_executed`).
    - `advisor_actions_matched: bool`: Checks if expected actions were either executed or recommended in text (`all_actions`).
    - `epistemic_step_count`: Verifiable count of investigative tool calls.
  - In `scripts/eval_soc_agent.py`, require:
    - `traj_verif.epistemic_step_count >= 1` for all cases requiring enrichment/investigation.
    - If a case expects containment, verify `traj_verif.operator_actions_matched` (or require clear distinction in the scorecard).

### Component D: ReAct Reflection on Premature Zero-Tool Termination
- **File**: `agent/soc_tier1_agent.py`
- **Design**:
  - In `SocTier1Agent.query()`:
    - If in Step 0 the agent emits `Final Answer:` or a structured decision block without having executed ANY tool, AND the alert prompt requires telemetry enrichment, do not immediately exit.
    - Inject an environmental reflection:
      `Observation: Investigation incomplete. You have not called any investigation tools (e.g., get_ip_report, get_domain_report, get_file_report, lookup_entity). You must invoke an investigation tool to gather verified telemetry before providing a final triage verdict.`
    - Allow the loop to continue to Step 1, giving the agent a chance to execute investigative actions.
