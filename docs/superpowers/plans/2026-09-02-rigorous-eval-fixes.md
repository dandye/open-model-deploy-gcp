# Rigorous SOC Evaluation Framework Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate zero-tool evaluation passes, prompt answer leakage, blind judge hallucinations, and operator/advisor conflation in the Gen 3 SOC agent benchmark.

**Architecture:** Sanitize case prompts and CMDB blast-radius context to remove diagnostic spoilers. Supply full tool execution trajectories to the LLM judge to penalize ungrounded fabrications. Separate operator tool execution from advisor text recommendations in trajectory verification, requiring epistemic steps for missing telemetry. Introduce ReAct environment reflection to prevent premature zero-tool loop termination.

**Tech Stack:** Python 3.13, Pytest, Pydantic, Google GenAI SDK, Vertex AI MaaS.

**Spec:** docs/superpowers/specs/2026-09-02-rigorous-eval-fixes-design.md

## Global Constraints

- Strictly NO EMOJIS anywhere in code, commits, comments, docstrings, JSON files, or documentation.
- Explicit variable definitions before expansion.
- All paths resolve relative to repository root (`ROOT_DIR = Path(__file__).resolve().parent.parent`).
- Maintain 100% backward compatibility with Gen 1 and Gen 2 eval runners.

---

### Task 1: Prompt & CMDB Context Sanitization

**Files:**
- Modify: `configs/evals/gen3/soc_tier1_interactive.json`
- Modify: `configs/evals/gen3/soc_live_mcp_interactive.json`
- Test: `tests/test_eval_config_schema.py`

**Interfaces:**
- Consumes: Existing case schema with `prompt`, `cmdb_context`, `reference`, `expected_actions`, `prohibited_actions`.
- Produces: Sanitized prompt strings and `cmdb_context.blast_radius` strings stripped of diagnostic spoilers ("RFC-5737", "revoked by CA", "Qualys scanner noise", "isolate host immediately").

- [ ] **Step 1: Write the failing test**

In `tests/test_eval_config_schema.py`, add `test_gen3_prompts_and_cmdb_do_not_leak_verdicts()`:
```python
def test_gen3_prompts_and_cmdb_do_not_leak_verdicts():
    for filename in ["soc_tier1_interactive.json", "soc_live_mcp_interactive.json"]:
        config_path = ROOT_DIR / "configs" / "evals" / "gen3" / filename
        with open(config_path) as f:
            data = json.load(f)
        for case in data["cases"]:
            prompt = case["prompt"].lower()
            cmdb_blast = case.get("cmdb_context", {}).get("blast_radius", "").lower()
            for text_block, source in [(prompt, "prompt"), (cmdb_blast, "blast_radius")]:
                assert "rfc-5737" not in text_block, f"{case['eval_id']} {source} leaks RFC-5737"
                assert "revoked by ca" not in text_block, f"{case['eval_id']} {source} leaks revoked certificate"
                assert "qualys scanner" not in text_block and "authorized noise" not in text_block, f"{case['eval_id']} {source} leaks authorized scanner noise"
                assert "isolate host immediately" not in text_block, f"{case['eval_id']} {source} leaks action instruction"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest -v tests/test_eval_config_schema.py::test_gen3_prompts_and_cmdb_do_not_leak_verdicts`
Expected: FAIL on prompt/blast_radius leaks.

- [ ] **Step 3: Implement prompt and CMDB context sanitization**

In `configs/evals/gen3/soc_tier1_interactive.json` and `soc_live_mcp_interactive.json`:
- Case 2: Change prompt to "Triage authentication log alert: Repeated connection attempts recorded from IP 192.0.2.100 against gateway GW-CORE-VPN-01. [CMDB Asset Context: Host GW-CORE-VPN-01, Owner: Network Infrastructure Operations, Role: Core VPN Gateway, Blast Radius: Enterprise ingress gateway; verify route legitimacy and assess unauthorized access risk]. Query threat intelligence, verify routing classification, and resolve alert."
  Change `cmdb_context.blast_radius` to "Enterprise ingress gateway; verify route legitimacy and assess unauthorized access risk".
- Case 7: Change prompt to "Investigate alert: User mwilson on host DESKTOP-HR-04 (10.0.8.99) executing PsExec commands and anomalous SMB connections across internal subnets. [CMDB Asset Context: Host DESKTOP-HR-04 (10.0.8.99), Owner: HR Operations, Role: High-criticality HR asset (DESKTOP-HR-04) storing employee PII, Blast Radius: High-criticality repository of executive and employee records ($50k breach risk)]. Triage host telemetry, evaluate lateral movement risk, and determine containment actions."
  Change `cmdb_context.blast_radius` to "High-criticality repository of executive and employee records ($50k breach risk)".
- Case 8: Change prompt to "Analyze binary telemetry for file hash a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90 (invoice_update.exe) claiming to be signed by Acme Corp. [CMDB Asset Context: Asset Enterprise Software Deployment Pipeline, Owner: IT Operations, Role: Supply chain binary (invoice_update.exe), Blast Radius: Enterprise build and deployment infrastructure]. Query file intelligence, determine risk status, and execute containment."
  Change `cmdb_context.blast_radius` to "Enterprise build and deployment infrastructure".
- Case 10: Change prompt to "Triage alert for host SRV-PROD-PAYMENT-01 (10.0.99.50) receiving high-volume port scanning activity from internal subnet. [CMDB Asset Context: Host SRV-PROD-PAYMENT-01 (10.0.99.50), Owner: Payment Infrastructure Engineering, Role: Critical production payment server (SRV-PROD-PAYMENT-01), Blast Radius: Mission-critical payment processing pipeline; unauthorized isolation incurs $50k downtime loss]. Check asset services, determine if scan represents authorized maintenance or adversary reconnaissance, and resolve alert."
  Change `cmdb_context.blast_radius` to "Mission-critical payment processing pipeline; unauthorized isolation incurs $50k downtime loss".

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest -v tests/test_eval_config_schema.py::test_gen3_prompts_and_cmdb_do_not_leak_verdicts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add configs/evals/gen3/ tests/test_eval_config_schema.py
git commit -m "fix(evals): sanitize case prompts and cmdb context to prevent answer leakage"
```

---

### Task 2: Trajectory-Aware Semantic LLM Judge

**Files:**
- Modify: `scripts/eval_soc_agent.py:192-231`
- Test: `tests/test_eval_soc_agent.py`

**Interfaces:**
- Consumes: `judge_client: genai.Client`, `prompt: str`, `response: str`, `rubric: str`, `reference: Dict[str, Any]`, and `trajectory: Optional[List[Dict[str, Any]]] = None`.
- Produces: `SemanticJudgeResult` where hallucinations and unexecuted containment are rigorously penalized based on actual tool observations.

- [ ] **Step 1: Write the failing test**

In `tests/test_eval_soc_agent.py`, add `test_judge_response_with_llm_receives_trajectory()`:
```python
def test_judge_response_with_llm_receives_trajectory():
    from unittest.mock import MagicMock
    from scripts.eval_soc_agent import judge_response_with_llm

    mock_client = MagicMock()
    mock_res = MagicMock()
    mock_res.text = json.dumps({
        "rubric_score": 90.0,
        "grounding_score": 0.95,
        "passed": True,
        "critique": "Trajectory verified."
    })
    mock_client.models.generate_content.return_value = mock_res

    trajectory = [{"step": 1, "tool": "get_domain_report", "input": {"domain": "evil.com"}, "observation": "{"verdict": "MALICIOUS"}"}]
    judge_response_with_llm(
        judge_client=mock_client,
        prompt="Triage domain evil.com",
        response="Domain evil.com is malicious.",
        rubric="Passing >= 80.",
        reference={"expected_verdict": "MALICIOUS"},
        trajectory=trajectory,
    )
    call_args = mock_client.models.generate_content.call_args
    assert call_args is not None
    prompt_sent = call_args.kwargs["contents"]
    assert "Tool Execution Trajectory" in prompt_sent
    assert "get_domain_report" in prompt_sent
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest -v tests/test_eval_soc_agent.py::test_judge_response_with_llm_receives_trajectory`
Expected: FAIL with `TypeError: judge_response_with_llm() got an unexpected keyword argument 'trajectory'`

- [ ] **Step 3: Update `judge_response_with_llm` implementation**

In `scripts/eval_soc_agent.py`:
- Update signature:
```python
def judge_response_with_llm(
    judge_client: genai.Client,
    prompt: str,
    response: str,
    rubric: str,
    reference: Dict[str, Any],
    trajectory: Optional[List[Dict[str, Any]]] = None,
) -> SemanticJudgeResult:
```
- In `judge_prompt`:
```python
    if trajectory and len(trajectory) > 0:
        traj_lines = []
        for step in trajectory:
            t_num = step.get("step", "?")
            t_name = step.get("tool", "unknown")
            t_in = json.dumps(step.get("input", {}))
            t_obs = str(step.get("observation", ""))[:500]
            traj_lines.append(f"Step {t_num}: Tool '{t_name}' invoked with {t_in} -> Observation: {t_obs}")
        traj_str = "
".join(traj_lines)
    else:
        traj_str = "NO TOOLS WERE INVOKED DURING THIS INVESTIGATION (0 tool calls executed)."

    judge_prompt = f"""
You are an expert Security Operations Center (SOC) Quality Assurance Judge.
Evaluate the following Tier 1 SOC Analyst agent response against the operational rubric and the ACTUAL tool execution trajectory.

### User Query / Incident Alert:
{prompt}

### Tool Execution Trajectory (Actual Invocations & Real Observations):
{traj_str}

### Agent Response:
{response}

### Reference Ground Truth:
{json.dumps(reference, indent=2)}

### Operational Grading Rubric:
{rubric}

### Instructions:
1. Objectively evaluate if the response followed triage procedures.
2. Grounding Verification: Cross-reference all claims in the Agent Response against the Tool Execution Trajectory. If the agent claims to have checked threat intelligence, IP routing, process trees, or certificates, but no corresponding tool invocation exists in the trajectory, heavily penalize the grounding_score (< 0.70) and rubric_score.
3. Execution vs Recommendation: If the rubric requires executing containment (e.g. isolate_host, block_indicator), verify whether that tool was actually executed in the trajectory. A text recommendation without actual tool execution must not receive full execution points.
4. Score from 0 to 100 based strictly on verified operational performance.
"""
```
- In `run_evaluation()`: pass `trajectory=trajectory` to `judge_response_with_llm()`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest -v tests/test_eval_soc_agent.py::test_judge_response_with_llm_receives_trajectory`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/eval_soc_agent.py tests/test_eval_soc_agent.py
git commit -m "feat(evals): make semantic llm judge trajectory-aware to penalize ungrounded tool claims"
```

---

### Task 3: Operator vs Advisor Separation & Epistemic Enforcement

**Files:**
- Modify: `scripts/eval_trajectory_verifier.py:100-150, 415-460`
- Modify: `scripts/eval_soc_agent.py:388-403`
- Test: `tests/test_gen3_trajectory_verifier.py`
- Test: `tests/test_eval_soc_agent.py`

**Interfaces:**
- Consumes: `expected_actions`, `prohibited_actions`, `trajectory`, `response_text`.
- Produces: `TrajectoryVerificationResult.operator_actions_matched: bool`, `advisor_actions_matched: bool`, and gated `case_passed` requiring `epistemic_step_count >= 1` for enrichment cases.

- [ ] **Step 1: Write the failing test**

In `tests/test_gen3_trajectory_verifier.py`, add `test_operator_vs_advisor_action_matching()`:
```python
def test_operator_vs_advisor_action_matching():
    # Model emits recommendation in text but called 0 tools
    res = verify_agent_trajectory(
        trajectory=[],
        expected_actions=["isolate_host"],
        prohibited_actions=["close_case"],
        response_text="```soc_decision
{"verdict": "MALICIOUS", "recommended_actions": ["isolate_host"]}
    ```"
    )
    assert res.advisor_actions_matched is True
    assert res.operator_actions_matched is False
    assert res.epistemic_step_count == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest -v tests/test_gen3_trajectory_verifier.py::test_operator_vs_advisor_action_matching`
Expected: FAIL with `AttributeError: 'TrajectoryVerificationResult' object has no attribute 'operator_actions_matched'`

- [ ] **Step 3: Implement operator vs advisor verification**

In `scripts/eval_trajectory_verifier.py`:
- Add fields to `TrajectoryVerificationResult`:
  ```python
  operator_actions_matched: bool = True
  advisor_actions_matched: bool = True
  ```
- In `verify_agent_trajectory()`:
  - Compute `operator_actions_matched`: check if `expected_primary` actions are present in `canonical_executed`.
  - Compute `advisor_actions_matched`: check if `expected_primary` actions are present in `all_actions` (`canonical_executed | canonical_recommended`).
  - Set `actions_matched = advisor_actions_matched` (for backward compatibility) and populate both.
- In `scripts/eval_soc_agent.py`:
  - When evaluating `case_passed` for Gen 3:
    - If `case.get("expected_actions")` includes containment actions (`isolate_host`, `block_indicator`), require either `operator_actions_matched` OR deduct points if purely advisory.
    - If the case requires investigation (ground truth threat or enrichment), require `traj_verif.epistemic_step_count >= 1` (or tool execution). A model that executes 0 tools on an alert requiring enrichment cannot receive a passing grade.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest -v tests/test_gen3_trajectory_verifier.py::test_operator_vs_advisor_action_matching`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/eval_trajectory_verifier.py scripts/eval_soc_agent.py tests/test_gen3_trajectory_verifier.py
git commit -m "feat(evals): separate operator tool execution from advisor recommendations"
```

---

### Task 4: ReAct Step-0 Premature Termination Reflection

**Files:**
- Modify: `agent/soc_tier1_agent.py:868-960`
- Test: `tests/test_soc_tier1_agent.py`

**Interfaces:**
- Consumes: User alert prompt and investigation tools.
- Produces: Iterative ReAct execution where models that attempt to conclude in Step 0 without tools are nudged to query telemetry.

- [ ] **Step 1: Write the failing test**

In `tests/test_soc_tier1_agent.py`, add `test_react_step0_reflection_on_missing_tools()`:
```python
def test_react_step0_reflection_on_missing_tools():
    # Setup mock agent that tries to output final answer in step 0, then calls tool in step 1
    agent = SocTier1Agent()
    step0_resp = "Final Answer:
[Context & Enrichment]
Host isolated.
    ```soc_decision
{"verdict": "MALICIOUS", "recommended_actions": ["isolate_host"]}
    ```"
    step1_resp = "Thought: I need to query threat intelligence.
Action: get_domain_report(domain="evil.com")"
    step2_resp = "Thought: Domain confirmed malicious.
Action: isolate_host(hostname="DESKTOP-01")"
    step3_resp = "Final Answer:
[Context & Enrichment]
Confirmed malware.
    ```soc_decision
{"verdict": "MALICIOUS", "recommended_actions": ["isolate_host"]}
    ```"

    agent._call_llm_step = MagicMock(side_effect=[
        (step0_resp, {}),
        (step1_resp, {}),
        (step2_resp, {}),
        (step3_resp, {}),
    ])
    agent._execute_tool_action = MagicMock(return_value="{"status": "SUCCESS"}")

    result = agent.query("Triage alert for host DESKTOP-01 connecting to evil.com. Query threat intelligence.")
    assert len(result["trajectory"]) >= 1
    assert agent._call_llm_step.call_count >= 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest -v tests/test_soc_tier1_agent.py::test_react_step0_reflection_on_missing_tools`
Expected: FAIL (agent terminates at step 0 because no tool call was parsed).

- [ ] **Step 3: Implement ReAct reflection logic**

In `agent/soc_tier1_agent.py`:
- In `query()`:
  - If in step 0, no tool action was parsed, but the prompt or task requires investigative action, AND `step < max_iterations - 1`:
    - Check if the response contains `Final Answer:`, `[Analysis & Verdict]`, or ````soc_decision````.
    - If so, append reflection observation:
      `Observation: Investigation incomplete. You have not called any investigation tools (e.g. get_ip_report, get_domain_report, get_file_report, lookup_entity, list_cases). You must invoke an investigation tool to gather verified telemetry before issuing a final verdict.`
    - Append to conversation prompt and continue to step 1!
- Clarify in `SOC_TIER1_PERSONA` that the analyst MUST invoke at least one investigation tool before concluding.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest -v tests/test_soc_tier1_agent.py::test_react_step0_reflection_on_missing_tools`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agent/soc_tier1_agent.py tests/test_soc_tier1_agent.py
git commit -m "feat(agent): add react reflection to prevent premature zero-tool termination"
```

---

### Task 5: End-to-End Evaluation & Scorecard Rebuild

**Files:**
- Modify: `docs/soc_model_comparative_evals.md`
- Run: `scripts/eval_soc_agent.py`
- Run: `tests/` (full test suite)

**Interfaces:**
- Consumes: Enhanced evaluation framework across Tasks 1-4.
- Produces: Rigorous, verified evaluation reports and updated comparative scorecard reflecting genuine operational performance.

- [ ] **Step 1: Run full unit test suite**

Run: `.venv/bin/pytest -v`
Expected: 260+ tests passing green.

- [ ] **Step 2: Run evaluation on baseline models**

Run `scripts.eval_soc_agent` on `gemini-2.5-flash` and `gemini-2.5-flash-lite`:
```bash
GOOGLE_APPLICATION_CREDENTIALS="$HOME/.config/gcloud/secops-demo-env-sa-key.json" GOOGLE_API_USE_CLIENT_CERTIFICATE=false GOOGLE_API_USE_MTLS_ENDPOINT=never .venv/bin/python3 -m scripts.eval_soc_agent   --flavor "gemini-2.5-flash"   --managed-model "gemini-2.5-flash"   --gen 3   --project-id "secops-demo-env"   --evalset "configs/evals/gen3/soc_tier1_interactive.json"   --output-report "docs/soc_eval_results/gemini-2.5-flash_report.md"   --output-json "docs/soc_eval_results/gemini-2.5-flash_report.json"
```
Verify:
1. Tool calls are now executed and recorded in the trajectory.
2. The LLM judge evaluates the trajectory and penalizes ungrounded hallucinations.
3. Cases that fail to invoke tools fail the epistemic gating requirement.

- [ ] **Step 3: Rebuild master scorecard**

Run: `.venv/bin/python3 scripts/run_overnight_sweep.py --rebuild-scorecard`
Expected: `docs/soc_model_comparative_evals.md` updated with rigorous metrics.

- [ ] **Step 4: Commit**

```bash
git add docs/soc_eval_results/ docs/soc_model_comparative_evals.md
git commit -m "test(evals): evaluate baseline models with rigorous trajectory-aware framework"
```
