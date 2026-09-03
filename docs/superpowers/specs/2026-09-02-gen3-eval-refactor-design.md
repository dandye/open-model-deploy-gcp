# Gen 3 Evaluation Framework In-Place Refactor: Design Specification

## 1. Objective

Refactor the Gen 3 Agentic Evaluation Framework in-place to address core evaluation misalignments:
1. **Bridge the "Advisor vs Operator" Role Disconnect**: Recognize both direct programmatic SOAR tool execution (`trajectory`) AND explicit structured recommendations (`soc_decision`) so models that properly investigate and recommend appropriate actions are rewarded rather than failed.
2. **Eliminate Brittle Substring Fallback Bugs**: Replace naive substring matching in `classify_decision_outcome()` (which misclassified *"No containment or blocking actions are required"* as a `FALSE_POSITIVE`) with structured verdict extraction and context-aware verdict parsing.
3. **Purge Brittle Assertions**: Remove overly prescriptive substring assertions (`"escalat"`, `"Qualys"`, `"BENIGN"`) that penalize natural linguistic expression, synonymy, or natural negation, relying on factual anchors and LLM judge rubric grading for semantic quality.
4. **Calibrate Pass/Fail Composition**: Align the composite pass criteria (`assert_passed`, `rubric_score >= 70`, `grounding_score >= 0.70`, `actions_matched`, `prohibited_actions_avoided`, and `decision_outcome`) so that procedurally sound, well-grounded investigations pass reliably.

---

## 2. Architecture & Components

### 2.1 Structured Output & Decision Schema (`agent/soc_tier1_agent.py`)
Add an optional structured decision block to the Tier 1 agent prompt and a parser helper `extract_soc_decision(response_text: str) -> Optional[SocDecision]`:
```python
@dataclass
class SocDecision:
    verdict: str  # "BENIGN", "MALICIOUS", "SUSPICIOUS", "INCONCLUSIVE"
    recommended_actions: List[str]
    prohibited_actions_avoided: List[str]
    target_entity: Optional[str] = None
    rationale: Optional[str] = None
```
The agent prompt instructs the model to include a structured JSON block at the end of its triage report:
```json
```soc_decision
{
  "verdict": "BENIGN",
  "recommended_actions": ["close_case"],
  "target_entity": "192.0.2.100",
  "rationale": "RFC-5737 documentation IP; zero malicious activity."
}
```
```

### 2.2 Dual-Action Trajectory Verifier (`scripts/eval_trajectory_verifier.py`)
Enhance `verify_agent_trajectory()`:
- Parameters: `trajectory: List[Dict[str, Any]]`, `response_text: str`, `expected_actions: List[str]`, `prohibited_actions: List[str]`, `expected_entities: List[str]`, `fault_injected: bool`.
- Extracted Actions:
  - `executed_actions`: Tool calls in `trajectory` matching pragmatic actions (`isolate_host`, `block_indicator`, `update_case_comment`, `close_case`).
  - `recommended_actions`: Parsed from `soc_decision` JSON block OR extracted from `[Action & Escalation]` / `[SOAR Documentation]` text sections.
  - `all_actions = set(executed_actions) | set(recommended_actions)`.
- Action Matching:
  - `actions_matched = all(act in all_actions for act in expected_actions)`.
  - Distinguishes whether actions were executed in-band or recommended for SOAR dispatch.
- Prohibited Action Avoidance:
  - `prohibited_actions_avoided = not any(act in all_actions for act in prohibited_actions)`.

### 2.3 Semantic Decision Outcome Classifier (`scripts/eval_cost_engine.py`)
Refactor `classify_decision_outcome()`:
```python
def classify_decision_outcome(
    ground_truth_threat: bool,
    agent_flagged_threat: Optional[bool] = None,
    verdict_str: Optional[str] = None,
    executed_actions: Optional[List[str]] = None,
    recommended_actions: Optional[List[str]] = None,
    response_text: Optional[str] = None,
) -> DecisionOutcome:
```
Priority hierarchy:
1. Explicit `verdict_str` from `soc_decision` or parsed `[Analysis & Verdict]` line (e.g. `BENIGN` -> False, `MALICIOUS`/`SUSPICIOUS` -> True).
2. Action intent from `executed_actions` and `recommended_actions`:
   - If contains `close_case` without containment -> False.
   - If contains `isolate_host` or `block_indicator` -> True.
3. Context-aware text analysis:
   - Check for explicit negative/benign patterns: `no containment`, `not malicious`, `benign`, `false positive`, `safe`.
   - Only flag threat if affirmative threat language is detected without negations.

### 2.4 Assertion Sanitization (`configs/evals/gen3/soc_tier1_interactive.json`)
Sanitize `assertions` across the 10 Gen 3 evaluation cases:
- Retain objective entity and indicator anchors (e.g. `192.0.2.100`, `update-service-win32.com`, `DESKTOP-FIN-08`, `10.0.5.23`).
- Remove subjective substring requirements: remove `"escalat"`, remove `"Qualys"`.
- Remove brittle negative substring checks: remove `"BENIGN"` when natural negation is expected.

### 2.5 Calibrated Evaluation Runner (`scripts/eval_soc_agent.py`)
Update composite pass logic:
```python
case_passed = (
    assert_passed
    and judge_res.rubric_score >= 70.0
    and judge_res.grounding_score >= 0.70
    and traj_verif.actions_matched
    and traj_verif.prohibited_actions_avoided
    and (
        (is_threat and decision_outcome in [DecisionOutcome.TRUE_POSITIVE])
        or (not is_threat and decision_outcome in [DecisionOutcome.TRUE_NEGATIVE])
    )
)
```

---

## 3. Backward Compatibility & Test Guardrails

- All existing unit tests in `tests/test_gen3_soc_environment.py`, `tests/test_gen3_cost_engine.py`, `tests/test_gen3_trajectory_verifier.py`, `tests/test_eval_config_schema.py`, and `tests/test_eval_soc_agent.py` must pass.
- Zero emojis anywhere in code, docstrings, configs, or documentation.
- Existing `--gen 1` and `--gen 2` compatibility must remain 100% functional.
