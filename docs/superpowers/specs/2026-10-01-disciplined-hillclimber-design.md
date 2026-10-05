# Disciplined Hillclimber (eval-hillclimb + Jev Judge + Harness Checksum) Design Spec

- **Date:** 2026-10-01
- **Status:** Proposed / Ready for Execution
- **Author:** dandye
- **Target Repository:** `gemma_deploy` (`gemma_deploy__worktrees/disciplined_hillclimber_v0001`)
- **Base Branch:** `jev_evals_v0001`
- **Target Branch:** `disciplined_hillclimber_v0001`
- **Theoretical Grounding:** `anthropic-2026` (*Hill-Climbing on an Eval*, `eval-hillclimb.md`), `anthropic_buildeval-2026` (*Building an Eval for a Claude-Powered Application*, `build-eval.md`), `martin-2026` (*Automating eval design and hillclimbing with Claude*), `bennett-2026` (*Claude's hillclimb loop, with your traces underneath*), and Jev System-One (`2026-09-24-jev-eval-judge-design.md`).

---

## 1. Executive Summary & Problem Statement

In `agent/gepa_runbook_optimizer.py`, the current GEPA (Genetic Engine for Prompt Ad-hoc Optimization) loop evolves SOC Tier 1 runbooks (`basic_ioc_enrichment.md`, `suspicious_login_triage.md`, `malware_triage.md`, `lateral_movement_hunt_psexec_wmi.md`) against the 10-case Gen 3 interactive benchmark (`configs/evals/gen3/soc_tier1_interactive.json`). While anti-memorization regexes (`IPV4_LITERAL_REGEX`, `FORBIDDEN_EVAL_HOSTNAMES`, `SHORT_CIRCUIT_PATTERNS`) and `--split-train-val` were added in PR #7, five structural weaknesses identified in Anthropic's `eval-hillclimb.md` and `build-eval.md` remain:

1. **No Harness Checksum Lock (Invariant #1 Violation Risk):** Nothing verifies that the evaluation dataset (`configs/evals/gen3/soc_tier1_interactive.json`), environment sandbox (`agent/soc_environment.py`), trajectory verifier (`scripts/eval_trajectory_verifier.py`), or cost engine (`scripts/eval_cost_engine.py`) remain unmodified across optimization iterations.
2. **Heuristic/Generative Inner-Loop Rubric Grading:** `RunbookGEPAAdapter.evaluate()` currently approximates `rubric_normalized` via a static 4-part heuristic (`epistemic_pts + action_pts + assertion_pts + 25.0`), bypassing calibrated semantic grading of whether the agent's reasoning is grounded in its tool trajectory. Conversely, calling generative `gemini-2.5-pro` on every rollout adds 15-35s per case and introduces generative judge sampling variance.
3. **No Step 0 Noise-Floor Calibration:** Single-pass stochastic LLM rollouts fluctuate across runs. Accepting any candidate where `score > selected_score` (even by `0.001`) hillclimbs run-to-run sampling noise.
4. **No Prompt-Bloat Ceiling or Case-ID Leakage Check:** While IPv4 literals and 6 static hostnames are blocked, the reflection LM can still inject case IDs (`CASE-01`..`CASE-10`) or bloat a 120-line runbook into a 600-line patch of special cases.
5. **No Append-Only Hillclimb Ledger or `cost-hillclimb` Staircase Walk:** Iteration history is not persisted in a git-auditable JSONL ledger, and there is no automated `cost-hillclimb` walk down the model staircase (`gemini-2.5-flash` -> `gemma-4-31b-it` -> `gemma-4-e4b-it` -> `gemma-3-4b-it` -> `gemma-3-1b-it`) to find the cheapest model tier that satisfies quality and zero-catastrophic-loss gates.

---

## 2. Architecture & Five Core Upgrades

```
+-----------------------------------------------------------------------------------+
|                        STEP 0: PRE-FLIGHT & NOISE FLOOR                           |
|  1. HarnessIntegrityGuard: Verify SHA-256 manifest of evalset + graders           |
|  2. NoiseFloorEstimator: Run K=2 baseline passes on seed runbooks                 |
|     -> Compute sigma_noise = |S_1 - S_2| and tau_accept = max(min_delta, 1.5*sigma)|
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                     INNER LOOP: TWO-SPEED JEV + SANDBOX GRADING                   |
|  - Anti-Memorization & Anti-Bloat Gate (validate_runbook_candidate v2):           |
|    Rejects IPv4 literals, eval hostnames, CASE-XX IDs, short-circuits, >1.35x bloat|
|  - Sandbox Rollout: SocEnvironment + verify_agent_trajectory                      |
|  - Jev System-One Fast Scorer (JevSocJudgeEvaluator):                             |
|    Single-pass logprob E[S] (Score), p_grounded & p_pass (Noul), Failure (Choice) |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                   OUTER LOOP: TRACE-GROUNDED REFLECTION & GATING                  |
|  - Generative Teacher (GoogleGenAILM / gemini-2.5-pro) invoked ONLY on failed     |
|    traces (fitness < 0.85 or loss_penalty < 1.0) enriched with Jev Choice tag     |
|  - Noise-Floor Acceptance Gate: Keep candidate iff                                |
|    (val_score - best_val_score >= tau_accept) AND (zero new case regressions)     |
|  - Append-Only HillclimbLedger (hillclimb_ledger.jsonl)                           |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                  OPTIONAL PHASE 2: COST-HILLCLIMB STAIRCASE WALK                  |
|  Walk evolved runbooks down model staircase:                                      |
|  gemini-2.5-flash -> gemma-4-31b-it -> gemma-4-e4b-it -> gemma-3-4b-it -> 1b-it   |
|  Accept lowest tier with val_score >= ceiling - tolerance AND loss_penalty == 1.0 |
+-----------------------------------------------------------------------------------+
```

### 2.1 Component 1: `HarnessIntegrityGuard` (`agent/hillclimb_harness.py`)
- Computes a deterministic SHA-256 manifest over protected evaluation harness files:
  - Target `evalset` JSON file (e.g., `configs/evals/gen3/soc_tier1_interactive.json`)
  - `agent/soc_environment.py`
  - `scripts/eval_trajectory_verifier.py`
  - `scripts/eval_cost_engine.py`
  - `scripts/eval_soc_agent.py`
- Persists lockfile at `.eval_harness_lock.json` (or custom path).
- Before Step 0 and before every candidate evaluation in `RunbookGEPAAdapter.evaluate()`, verifies the current SHA-256 digest matches the locked manifest.
- Raises `HarnessTamperError` if any protected file changed without `--approve-harness`.

### 2.2 Component 2: `NoiseFloorEstimator` & Acceptance Gate (`agent/hillclimb_harness.py`)
- Executes $K=2$ baseline evaluation passes on the seed runbooks over the validation set (or accepts two pre-recorded score vectors).
- Computes:
  - Aggregate noise floor: $\sigma_{\text{agg}} = |\bar{S}^{(1)} - \bar{S}^{(2)}|$
  - Mean per-case absolute deviation: $\sigma_{\text{case}} = \frac{1}{N}\sum_{i=1}^N |S_i^{(1)} - S_i^{(2)}|$
  - Acceptance threshold: $\tau_{\text{accept}} = \max(\delta_{\min}, 1.5 \cdot \sigma_{\text{agg}})$, where $\delta_{\min} = 0.015$ by default.
- Provides `evaluate_candidate_acceptance(baseline_scores, candidate_scores, tau_accept)` returning a structured `AcceptanceDecision(accepted: bool, reason: str, mean_delta: float, tau_accept: float, regressed_case_ids: list[str])`. A candidate is rejected if any case that previously passed (`score >= 0.80`) drops below `0.80` (`REVERTED_REGRESSION`) or if `mean_delta < tau_accept` (`REVERTED_NOISE`).

### 2.3 Component 3: Anti-Bloat & Case-ID Leakage Guard (`validate_runbook_candidate` v2)
- Extends `validate_runbook_candidate()` in `agent/gepa_runbook_optimizer.py` with:
  - `CASE_ID_REGEX = re.compile(r"\bCASE-\d{2,}\b", re.IGNORECASE)`: Prohibits referencing specific benchmark case IDs (`CASE-01` through `CASE-10`).
  - `seed_candidate: Optional[Dict[str, str]] = None` and `max_growth_ratio: float = 1.35`: If `seed_candidate` is provided, rejects any mutated runbook whose character length exceeds `len(seed_content) * max_growth_ratio`, forcing the reflection engine to consolidate and generalize rules rather than appending endless special-case clauses.

### 2.4 Component 4: Two-Speed Jev System-One Grader Integration (`RunbookGEPAAdapter`)
- Adds optional `jev_evaluator: Optional[JevSocJudgeEvaluator] = None` to `RunbookGEPAAdapter`.
- When `jev_evaluator` is configured:
  - Inner-loop `rubric_normalized` blends the deterministic sandbox trajectory verification (50%) with Jev's calibrated `Score` expected value $E[S]/100$ (30%) and `Noul` grounding probability $p_{\text{grounded}}$ (20%).
  - Records `jev_choice` (from `SOC_FAILURE_TAXONOMY`, e.g., `OVER_CONTAINMENT_FALSE_ALARM`, `UNGROUNDED_HALLUCINATED_CLAIM`, `PREMATURE_TERMINATION_ZERO_TOOLS`) and `jev_grounding_prob` into each trace dictionary.
  - In `make_reflective_dataset()`, injects the structured `jev_choice` diagnostic label and grounding probability directly into the `Feedback` field so the generative teacher (`gemini-2.5-pro`) knows the exact failure category before editing the markdown.

### 2.5 Component 5: `HillclimbLedger` & `run_cost_staircase_walk`
- `HillclimbLedger` appends one JSON record per evaluation batch / candidate to `configs/runbooks/gepa_evolved/hillclimb_ledger.jsonl` containing timestamp, git commit, `harness_sha256`, `candidate_index`, `mean_score`, `per_case_scores`, `decision`, `rationale`, and `char_lengths`.
- `run_cost_staircase_walk(candidate, eval_cases, model_tiers, adapter_factory, tolerance=0.05)` evaluates the winning runbooks across ordered model tiers (default: `["gemini-2.5-flash", "gemma-4-31b-it", "gemma-4-e4b-it", "gemma-3-4b-it", "gemma-3-1b-it"]`), returning a `CostStaircaseReport` that identifies the lowest-cost tier achieving `score >= ceiling_score - tolerance` with zero prohibited actions (`all(loss_penalty == 1.0)`).

---

## 3. CLI Additions to `agent/gepa_runbook_optimizer.py`

- `--lock-file`: Path to harness checksum lockfile (default: `.eval_harness_lock.json`).
- `--approve-harness`: Recompute and overwrite the harness checksum lockfile when intentional harness updates are made.
- `--noise-runs`: Number of Step 0 baseline runs to estimate noise floor (default: `2`; `0` disables).
- `--min-delta`: Minimum validation score improvement required above noise floor (default: `0.015`).
- `--max-growth-ratio`: Maximum character length ratio vs seed runbook (default: `1.35`).
- `--judge-backend`: `["heuristic", "jev_mock", "jev_gemini_system1"]` (default: `"jev_gemini_system1"` when Jev module is present, with `"heuristic"` fallback).
- `--cost-staircase`: Run post-optimization cost-staircase walk across model tiers.
- `--cost-tolerance`: Allowed score drop from ceiling during cost-staircase walk (default: `0.05`).
