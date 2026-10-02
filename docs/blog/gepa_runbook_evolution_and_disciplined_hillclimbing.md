# Evolving SecOps runbooks without cheating: GEPA, verbosity bias, and disciplined hillclimbing

**Author:** Dan Dye  
**Date:** October 2026  
**Series:** Serving Open Models for Security & Cloud Agents  
**Repository:** [github.com/dandye/open-model-deploy-gcp](https://github.com/dandye/open-model-deploy-gcp)  
**Topics:** Google SecOps, GEPA, Prompt Optimization, Gemma, Gemini, Agent Evaluation, Vertex AI  

---

In the previous post in this series, I tested whether smaller open models could execute cloud infrastructure tasks when given structured domain skills (`SKILL.md` files). Using Karl Weinmeister's 12-scenario benchmark, I found that 4B and 9B models (`gemma-3-4b-it`, `gemma-4-e4b-it`, and `gemini-2.5-flash-lite`) jumped to a 100% pass rate on a single \$0.70/hr NVIDIA L4 GPU once the relevant skill was placed in context. That result matched Vlad Kolesnikov's summary of SkillsBench (`arXiv:2602.12670`): *"Smaller models with good skills matched larger models without them."*

Then I brought those same compact models back to our Tier 1 Security Operations Center (SOC) benchmark (`configs/evals/gen3/soc_tier1_interactive.json`), and the story got messier.

Dividing labor between a supervisor agent and an epistemic worker (`agent/hierarchical_soc_agent.py`) solved tool execution. Operator action compliance on `gemini-2.5-flash-lite` rose from 10.0% in a single-agent loop to 80.0% and 90.0% in the hierarchical workflow. The worker stopped hallucinating zero-tool verdicts and started calling SIEM, CMDB, and Google Threat Intelligence (GTI) tools.

The new failure mode came from the human-written runbooks themselves.

When we loaded the raw community playbooks from `third_party/ai-runbooks` (`basic_ioc_enrichment.md`, `suspicious_login_triage.md`, `malware_triage.md`, and `lateral_movement_hunt_psexec_wmi.md`), the small models followed them literally. Those playbooks told the analyst to query threat intelligence and SIEM logs, but they omitted boundary conditions for benign test traffic and authorized internal scanners.

When `CASE-02` fired on RFC-5737 documentation subnet traffic (`192.0.2.0/24`) hitting the core VPN gateway `GW-CORE-VPN-01`, the agent isolated the gateway. When `CASE-10` fired on an authorized high-volume Qualys vulnerability scan (`10.0.99.50`) targeting the production payment server `SRV-PROD-PAYMENT-01`, the agent called `isolate_host` and took down payment processing. In our simulated operational loss model (`scripts/eval_cost_engine.py`), each wrongful isolation of a critical production asset carries a \$50,000 downtime penalty.

I did not want to hand-edit the markdown runbooks after every failed test case. If a frontier model can read failed execution traces, it should be able to tighten the runbooks automatically so a 4B or Flash-Lite model can run them safely.

That led me to wire up GEPA (Genetic Engine for Prompt Ad-hoc Optimization) in `agent/gepa_runbook_optimizer.py`. Over the next two weeks, the optimizer taught me three hard lessons about how automated hillclimbing cheats, how LLM judges reward bloat, and why you need cryptographic harness locks and calibrated logprob graders before trusting an optimization loop.

---

## Failure mode 1: how naive GEPA cheated by memorizing the test set

To evolve the four core SOC runbooks, I built `RunbookGEPAAdapter` in `agent/gepa_runbook_optimizer.py`. On each evaluation batch, `gemini-2.5-flash-lite` runs the candidate markdown runbooks inside `SocEnvironment`, a stateful sandbox that tracks entity lookups, SIEM queries, SOAR case comments, and containment actions (`isolate_host`, `block_indicator`, `close_case`).

Each case rollout is scored by a multi-objective fitness function that combines rubric quality, deterministic string assertions, operator tool compliance, and an exponential penalty for operational loss:

```python
def calculate_loss_penalty(
    expected_label: str,
    actual_verdict: str,
    executed_actions: List[str],
    prohibited_actions: List[str],
) -> float:
    loss = 0.0
    prohibited_set = set(prohibited_actions or [])
    if any(action in prohibited_set for action in (executed_actions or [])):
        loss += 10000.0

    norm_expected = (expected_label or "").strip().upper()
    norm_actual = (actual_verdict or "").strip().upper()

    if norm_actual == "MALICIOUS" and norm_expected == "BENIGN":
        loss += 5000.0
    elif norm_actual == "BENIGN" and norm_expected == "MALICIOUS":
        loss += 10000.0

    return math.exp(-loss / 10000.0)
```

When a candidate runbook underperforms on a case, `make_reflective_dataset()` packages the prompt, the CMDB context, the executed tool trajectory, and diagnostic feedback into a trace record. GEPA passes those failed traces to a teacher model (`gemini-2.5-pro` via `GoogleGenAILM`) to propose a mutated markdown runbook.

On my first unconstrained GEPA run, the validation loss dropped to zero almost immediately.

When I opened the evolved `basic_ioc_enrichment.md` to see what clever investigative logic `gemini-2.5-pro` had discovered, I found a lookup table of the benchmark answers. Seeing that `CASE-02` penalized isolating `GW-CORE-VPN-01` on `192.0.2.0/24` and `CASE-10` penalized isolating `SRV-PROD-PAYMENT-01` on `10.0.99.50`, the reflection teacher wrote rules at the top of the runbook:

- If the source IP falls in `192.0.2.0/24`, `198.51.100.0/24`, or `203.0.113.0/24`, or matches `10.0.99.50`, classify the alert as benign immediately.
- Instruct the analyst to *"skip all enrichment"* and proceed directly to case closure without calling GTI or SIEM tools.

We saw the exact same failure mode in a parallel repo (`agentic_soc_agentspace`, Experiment 008), where an unconstrained `PromptOptimizer` reflected on validation errors and injected literal test entities (`john.doe` and `192.0.2.100`) straight into `tier1_analyst_instructions.md`.

From the optimizer's point of view, hardcoding the test set is the shortest path to a higher score. It saves tool calls, eliminates false-positive containment penalties on the benchmark cases, and hits 100% on string assertions. In production, a runbook that tells an agent to skip enrichment whenever it sees a specific IP is worse than useless.

---

## Failure mode 2: judge verbosity bias and the `verbose_lore.md` negative control

Blocking literal IP addresses and hostnames is straightforward. The second failure mode was subtler because it lived inside the evaluation judge.

While testing skill evolution across model scales, I wanted to test a follow-on hypothesis: if clean, concise skills allow smaller models to match larger unassisted models, then intentionally degrading those skills with narrative fluff (`verbose_lore.md`), pronoun indirection (`pronoun_indirection.md`), buried formatting (`buried_structure.md`), or all three combined (`composite_degraded.md`) should dilute attention and cause smaller models to fail.

To test this, I took our clean ~466-token reference skill (`SKILL.md`) and generated degraded variants, including `verbose_lore.md`, a ~2,116-token version padded with fictional War of 1812 analogies, culinary tangents, and sprawling historical digressions while keeping the underlying technical flags intact.

Then I ran the 7-arm degradation sweep (`karl_skills_obfuscation_v0001`) on `gemini-2.5-flash-lite` and `gemma-4-26b-a4b-it-maas` using our standard text-only assertion evaluator.

The results ran backwards from my hypothesis:

| Evaluation Environment | Model | Clean Skill (`SKILL.md`, ~466 tokens) | Degraded Skill (`verbose_lore.md` / `composite_degraded.md`) | Observed Delta |
| :--- | :--- | :---: | :---: | :---: |
| Text-only LLM judge (`karl_skills_obfuscation_v0001`) | `gemini-2.5-flash-lite` | 66.7% pass (31/36 checks) | 83.3% pass on `verbose_lore.md` (34/36 checks) | +16.6 pp (false improvement) |
| Text-only LLM judge (`karl_skills_obfuscation_v0001`) | `gemma-4-26b-a4b-it-maas` | 83.3% pass (34/36 checks) | 91.7% pass on `verbose_lore.md` (35/36 checks) | +8.4 pp (false improvement) |
| Container execution sandbox (Harbor + NVIDIA SkillEvaluator) | `claude-sonnet-4-5` (`20260929_033816`) | 0.7742 overall (`gcd-003`: 0.8750, `gcd-012`: 0.7195) | 0.6900 on `composite_degraded.md` (`gcd-003`: 0.5555, `gcd-012`: 0.5111) | -0.0842 overall (-31.95 pp on `gcd-003`) |

Why did `gemini-2.5-flash-lite` jump from 66.7% on the clean skill to 83.3% on `verbose_lore.md` in text-only grading?

When I inspected the transcripts, two things stood out:

1. **Style and length mimicry.** Compact models copy the register of their prompt context. When given the terse 466-token `clean` skill, `gemini-2.5-flash-lite` wrote short, direct answers that occasionally omitted a secondary CLI flag. When given the 2,116-token `verbose_lore.md` skill, the model wrote multi-paragraph essays.
2. **Judge verbosity bias and shotgun recall.** Generative LLM-as-a-judge graders and positive-only assertion checklists reward long responses. By dumping every tangentially related command flag and caveat into a sprawling essay, the model hit more positive substring checks without paying any penalty for bloat.

To verify that `verbose_lore.md` was not secretly helping the agent, I ran the degraded skill (`composite_degraded.md`) inside a real container execution sandbox using Harbor and NVIDIA SkillEvaluator 0.3.0 (Run ID `20260929_033816_3903695_38615fb475e8`). In Harbor, the agent does not get points for writing an essay. It has to execute shell commands inside a Podman container, configure live files, and pass state checks while being scored on action economy.

Inside the execution sandbox, the degraded skill failed immediately. Overall score fell from `0.7742` to `0.6900`. Skill efficiency failed below the `0.40` threshold (`0.2292`), headless CLI execution (`gcd-003-gcloud-noninteractive`) plunged 31.95 percentage points (`0.8750 -> 0.5555`), and project onboarding safety gating (`gcd-012-onboarding-safety-gate`) dropped 20.84 percentage points (`0.7195 -> 0.5111`).

This finding changed how I think about prompt optimization. If your inner-loop evaluator suffers from verbosity bias, an automated hillclimber will exploit Goodhart's Law by turning every 120-line runbook into a 600-line wall of text. Degraded skills like `verbose_lore.md` are a mandatory negative control for the evaluation rig itself. If a noisy skill outscores a clean skill, your judge is broken, and you have no business hillclimbing on it.

---

## De-spoiling reflection and enforcing anti-memorization guardrails

To keep GEPA honest, I had to strip benchmark spoilers out of the reflection loop and put hard programmatic gates in front of candidate evaluation.

First, I partitioned the 10-case Gen 3 benchmark using `--split-train-val` (`trainset = eval_cases[:6]`, `valset = eval_cases[6:]`). That kept `CASE-10` (the Qualys vulnerability scanner on `SRV-PROD-PAYMENT-01`) in the held-out validation set so the reflection prompt never saw scanner telemetry when proposing edits.

Second, I rewrote `make_reflective_dataset()` and `build_reflection_prompt_template()` in `agent/gepa_runbook_optimizer.py` so the teacher model receives feedback framed around epistemic verification rather than case-specific answers.

Third, I implemented `validate_runbook_candidate()`, which runs inside `RunbookGEPAAdapter.evaluate()` before any LLM rollout starts. If a mutated runbook trips any guardrail, the adapter skips the rollout and assigns a `0.0` fitness score immediately:

```python
FORBIDDEN_EVAL_HOSTNAMES: List[str] = [
    "GW-CORE-VPN-01",
    "SRV-PROD-PAYMENT-01",
    "DESKTOP-FIN-08",
    "SRV-DATA-01",
    "SRV-DC-01",
    "LAPTOP-CFO-01",
]

SHORT_CIRCUIT_PATTERNS: List[str] = [
    r"skip\s+(?:all\s+)?enrichment",
    r"skip\s+(?:all\s+)?investigation",
    r"skip\s+steps?\s+\d+",
    r"proceed\s+directly\s+to\s+step\s+\d+",
]

IPV4_LITERAL_REGEX: re.Pattern = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}"
    r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(?:/(?:[1-2]?\d|3[0-2]))?\b"
)

CASE_ID_REGEX: re.Pattern = re.compile(
    r"\bCASE-(?:GEN\d+-)?\d+\b", re.IGNORECASE
)
```

In addition to blocking IPv4 literals (outside parenthetical `(e.g., ...)` examples), benchmark hostnames, `CASE-XX` identifiers, and short-circuit directives, `validate_runbook_candidate()` enforces `max_growth_ratio = 1.35` against `seed_candidate`:

```python
if seed_candidate and filename in seed_candidate:
    seed_len = max(1, len(seed_candidate[filename]))
    ratio = len(content) / seed_len
    if ratio > max_growth_ratio:
        violations.append(
            f"{filename}: Candidate growth ratio ({ratio:.2f}x) "
            f"exceeds max_growth_ratio ({max_growth_ratio:.2f}x)."
        )
```

Capping character growth at 1.35x forces `gemini-2.5-pro` to consolidate and generalize its instructions instead of tacking on endless `IF/ELSE` patches.

Once blocked from memorizing IPs or bloating the prompt, `gemini-2.5-pro` evolved `configs/runbooks/gepa_evolved/basic_ioc_enrichment.md` into a four-stage epistemic verification sequence:

1. **Stage A: Asset Identity and CMDB Context.** Execute `secops-mcp.lookup_entity` with `entity_name=${ASSET_IDENTIFIER}` and store the business role, owner, and criticality in `${ASSET_CONTEXT}` and `${ASSET_CRITICALITY}`.
2. **Stage B: Network Routing and Scope Verification.** Execute `gti-mcp.get_ip_address_report` or `get_domain_report` to classify whether the indicator resolves to public, private (RFC-1918), or reserved documentation space, storing the classification in `${IOC_ROUTING_TYPE}`.
3. **Stage C: Threat Intelligence Reputation.** Extract reputation scores and malware associations into `${GTI_FINDINGS}`.
4. **Stage D: Corroboration of Malicious Activity.** Execute `secops-mcp.search_security_events` for the indicator and `${ASSET_IDENTIFIER}` to check whether active malware execution or C2 beaconing is present, setting `${CORROBORATING_ACTIVITY_FOUND}` to `"Yes"` or `"No"`.

The evolved runbook then expresses containment gates purely in terms of those runtime variables:

```markdown
* Rule 1 (High Confidence - Containment Required):
  IF (${GTI_FINDINGS} indicates "Malicious" OR "High-Risk")
  AND (${CORROBORATING_ACTIVITY_FOUND} is "Yes")
  AND (${IOC_ROUTING_TYPE} is "Public")
  THEN set ${ASSESSMENT} to "High" and ${RECOMMENDATION} to "Trigger Containment".

* Rule 2 (Medium Confidence - Escalation Required):
  IF (the conditions for Rule 1 are not met)
  AND ((${GTI_FINDINGS} indicates "Suspicious" OR "Malicious")
  OR (${CORROBORATING_ACTIVITY_FOUND} is "Yes")
  OR (${FOUND_CASES} is not empty))
  THEN set ${ASSESSMENT} to "Medium" and ${RECOMMENDATION} to "Escalate to Tier 2".

* Rule 3 (Low Confidence - Benign/Informational):
  ELSE (all other conditions)
  THEN set ${ASSESSMENT} to "Low" and ${RECOMMENDATION} to "Close as False Positive/Informational".
```

Look at what Rule 1 accomplishes on `gemini-2.5-flash-lite`. In `CASE-02` (RFC-5737 test traffic on `GW-CORE-VPN-01`), Stage B sets `${IOC_ROUTING_TYPE}` to `"Reserved"`, which blocks Rule 1 and prevents `isolate_host`. In `CASE-10` (held-out Qualys scanner on `SRV-PROD-PAYMENT-01`), Stage A calls `lookup_entity("SRV-PROD-PAYMENT-01")`, discovers `"installed_services": ["PaymentGateway", "Qualys Scanner", "SSH"]`, and Stage D finds zero corroborating malware execution, preventing host isolation on an unseen validation scenario. Meanwhile, on `CASE-01` (Lokibot infostealer C2 on `DESKTOP-FIN-08`) and `CASE-05` (ransomware shadow copy deletion), all three Rule 1 conditions hold and the worker triggers immediate host isolation.

---

## Honest results and why we built the Evidence Reconciliation audit

When we first summarized the GEPA run in `docs/soc_eval_results/GEPA_RUNBOOK_EVALUATION_ANALYSIS.md`, the headline numbers looked like an unqualified victory: zero false-negative breaches, both catastrophic host isolations prevented on `CASE-02` and `CASE-10`, and simulated operational loss dropping to \$100.82.

Then I wrote an automated reconciliation auditor to cross-check our markdown narrative against the raw JSON evaluation artifacts (`gemini-2.5-flash-lite_approach3_report.json` and `gemini-2.5-flash-lite_gepa_evolved_report.json`). The resulting report, committed at `docs/soc_eval_results/GEPA_EVIDENCE_RECONCILIATION.md`, caught several discrepancies that forced us to tighten our engineering hygiene.

Here is the reconciled side-by-side table generated directly from the pinned JSON artifacts:

| Metric | Raw Playbooks (`approach3_report.json`) | GEPA Evolved (`gepa_evolved_report.json`) | Reconciled Delta |
| :--- | ---: | ---: | ---: |
| Total cases | 10 | 10 | +0 |
| Strict binary pass rate | 30.00% (3/10) | 20.00% (2/10) | -10.00 pp |
| Average rubric score (/100) | 59.8 | 47.5 | -12.3 |
| Average latency (s/case) | 40.50 s | 31.93 s | -8.57 s |
| Total tokens consumed | 529,125 | 388,464 | -140,661 |
| Total tool invocations | 52 | 45 | -7 |
| Threat hit rate | 85.71% (6/7) | 92.86% (7/7) | +7.15 pp |
| False alarm rate | 33.33% | 66.67% | +33.34 pp |
| Simulated false-positive loss | \$50.00 | \$100.00 | +\$50.00 |
| Simulated false-negative loss | \$250,000.00 | \$0.00 | -\$250,000.00 |
| Simulated investigation cost | \$1.11 | \$0.82 | -\$0.29 |
| Total simulated operational loss | \$250,051.11 | \$100.82 | -\$249,950.29 |

Looking at the reconciled artifact data alongside our earlier write-up reveals three things every engineer running agent benchmarks should watch for:

1. **Operational safety improved, but strict binary pass rate and rubric scores dropped.** The evolved runbooks succeeded at their primary operational goal: they caught 7 out of 7 real threats (\$0.00 simulated false-negative loss), avoided calling `isolate_host` on `SRV-PROD-PAYMENT-01` and `GW-CORE-VPN-01`, cut total token consumption by 140,661 tokens (`529,125 -> 388,464`), and reduced average case latency by 8.57 seconds (`40.50s -> 31.93s`). However, on benign cases (`CASE-02` and `CASE-10`), Rule 2 and Rule 3 instructed the agent to document findings via `post_case_comment` rather than invoking `close_case` directly. That left a \$50 triage overhead penalty on each benign case, raised the false-alarm classification rate from 33.33% to 66.67%, and dropped the strict all-or-nothing pass rate from 3/10 to 2/10 and average rubric score from 59.8 to 47.5.
2. **Unpinned baseline comparisons create narrative drift.** Our initial markdown table in `GEPA_RUNBOOK_EVALUATION_ANALYSIS.md` compared the evolved run against an earlier baseline table that had \$55,050.56 in total loss (\$50,050.00 FP loss, \$5,000.00 FN loss) and 22.81s latency, whereas the committed JSON baseline artifact (`gemini-2.5-flash-lite_approach3_report.json`, SHA-256 `1eac0734...`) recorded \$250,051.11 in simulated loss (from a missed critical breach) and 40.50s average latency. Neither JSON file embedded the git commit SHA, the dataset hash, or the evaluator configuration hash.
3. **Simulated loss penalties are model outputs, not realized dollar savings.** Our cost engine assigns \$50,000 to isolating a critical host and \$250,000 to missing a critical breach so that the optimizer weights blast radius asymmetrically. Those numbers are useful objective-function weights, not prevented production outages or money in the bank.

That reconciliation audit convinced me that regex filters on candidate text are not enough. If you want to hillclimb prompts or skills reliably, the evaluation harness itself needs cryptographic provenance, noise-floor calibration, and a deterministic inner-loop judge.

---

## The Disciplined Hillclimber architecture: five production guards

To fix these structural weaknesses, I designed and built the Disciplined Hillclimber upgrade in `agent/hillclimb_harness.py` and `agent/gepa_runbook_optimizer.py` (729 unit tests passing on branch `disciplined_hillclimber_v0001`). The design draws directly on Anthropic's engineering guides (*Hill-Climbing on an Eval* and *Building an Eval for a Claude-Powered Application*), Lance Martin's hillclimbing invariants, Jim Bennett's trace-grounded hillclimb loop, and our Jev System-One non-generative judge.

```text
+-----------------------------------------------------------------------------------+
|                        STEP 0: PRE-FLIGHT & NOISE FLOOR                           |
|  1. HarnessIntegrityGuard: Verify SHA-256 manifest (.eval_harness_lock.json)      |
|  2. NoiseFloorEstimator: Run K=2 baseline passes on seed runbooks                 |
|     -> Compute sigma_agg = |S_1 - S_2| and tau_accept = max(min_delta, 1.5*sigma) |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                     INNER LOOP: TWO-SPEED JEV + SANDBOX GRADING                   |
|  - Anti-Memorization & Anti-Bloat Gate (validate_runbook_candidate v2):           |
|    Rejects IPv4 literals, eval hostnames, CASE-XX IDs, short-circuits, >1.35x     |
|  - Sandbox Rollout: SocEnvironment + verify_agent_trajectory                      |
|  - Jev System-One Fast Scorer (JevSocJudgeEvaluator):                             |
|    Single-pass logprob E[S] (Score), p_grounded & p_pass (Noul), Failure (Choice) |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                   OUTER LOOP: TRACE-GROUNDED REFLECTION & GATING                  |
|  - Generative Teacher (GoogleGenAILM / gemini-2.5-pro) invoked ONLY on failed     |
|    traces enriched with Jev SOC_FAILURE_TAXONOMY Choice tag                       |
|  - Noise-Floor Acceptance Gate: Keep candidate iff                                |
|    (mean_delta >= tau_accept) AND (zero previously passing cases regressed)       |
|  - Append-Only HillclimbLedger (hillclimb_ledger.jsonl)                           |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                  OPTIONAL PHASE 2: COST-HILLCLIMB STAIRCASE WALK                  |
|  Walk evolved runbooks down model staircase:                                      |
|  gemini-2.5-flash -> gemma-4-31b-it -> gemma-4-e4b-it -> gemma-3-4b-it -> 1b-it   |
|  Select lowest tier with mean_score >= ceiling - 0.05 AND min_loss_penalty >= 1.0 |
+-----------------------------------------------------------------------------------+
```

Here are the five concrete mechanisms that enforce discipline across every optimization run.

### 1. Cryptographic harness lock (`HarnessIntegrityGuard`)

The first rule of hillclimbing is that the optimizer must never modify the test suite or the grading logic to make its score go up. `HarnessIntegrityGuard` in `agent/hillclimb_harness.py` computes a SHA-256 manifest over all protected harness files and stores it in `.eval_harness_lock.json`:

```python
DEFAULT_PROTECTED_HARNESS_PATHS: Tuple[str, ...] = (
    "configs/evals/gen3/soc_tier1_interactive.json",
    "agent/soc_environment.py",
    "scripts/eval_trajectory_verifier.py",
    "scripts/eval_cost_engine.py",
    "scripts/eval_soc_agent.py",
)
```

Before Step 0 and at the start of every `RunbookGEPAAdapter.evaluate()` call, `self.harness_guard.verify(auto_initialize=False)` recomputes the SHA-256 digest of each file. If any byte in the dataset, sandbox environment, trajectory verifier, or cost engine changes during a run without an explicit `--approve-harness` flag, the guard raises `HarnessTamperError` and halts execution immediately. Every record written to the hillclimb ledger stamps the composite SHA-256 of this manifest so we always know which exact harness version produced a score.

### 2. Step 0 noise-floor calibration and zero-regression gating (`NoiseFloorEstimator`)

Multi-turn agent rollouts have run-to-run sampling variance even at low temperatures. If your hillclimber accepts any candidate where `val_score > best_score` by `0.001`, you will spend your compute budget hillclimbing random noise.

Before running a single mutation, `gepa_runbook_optimizer.py` runs $K=2$ baseline evaluation passes (`--noise-runs 2`) on the unmodified seed runbooks across the validation set. `estimate_noise_floor()` measures the aggregate run-to-run drift $\sigma_{\text{agg}} = |\bar{S}^{(1)} - \bar{S}^{(2)}|$ and sets the minimum acceptance bar:

$$\tau_{\text{accept}} = \max(\delta_{\min}, 1.5 \cdot \sigma_{\text{agg}})$$

where $\delta_{\min} = 0.015$ by default. When a candidate finishes validation, `evaluate_candidate_acceptance()` enforces two rules:

1. **Zero per-case regressions (`REVERTED_REGRESSION`).** If any validation case that previously passed (`baseline_score >= 0.80`) drops below `0.80`, the candidate is rejected regardless of its mean score.
2. **Signal above noise (`REVERTED_NOISE`).** If the mean validation improvement `mean_delta` does not clear $\tau_{\text{accept}}$, the candidate is rejected as indistinguishable from run-to-run variance.

### 3. Two-speed Jev System-One judge (`JevSocJudgeEvaluator`)

Calling a generative `gemini-2.5-pro` judge to write a multi-paragraph critique on every inner-loop rollout adds 15 to 35 seconds per case and introduces generative judge variance (including the verbosity bias we caught with `verbose_lore.md`). Conversely, relying purely on a static heuristic misses whether the agent's final explanation is actually grounded in the tool outputs it observed.

To solve this, we integrated `JevSocJudgeEvaluator` (`agent/jev_evaluator.py` and `agent/jev_judge.py`) with `GeminiSystem1Backend`. Instead of decoding free-form prose critiques, Jev evaluates the serialized episode state (`build_soc_evaluation_state()`) in a single forward pass using constrained token log-probabilities across three structured evaluations:

- **`Score` ($E[S]$).** Computes the probability-weighted expected value over a 10-level rubric distribution ($\sum_{k=1}^{10} k \cdot p_k \times 10$), turning discrete rubric tiers into a smooth, continuous `0.0` to `100.0` signal that registers partial progress.
- **`Noul` ($p_{\text{grounded}}$ and $p_{\text{pass}}$).** Renormalizes constrained `{YES, NO}` logprobs (`normalize_noul_probs()`) on whether every forensic claim in the agent's response is corroborated by the executed tool trajectory (`grounding_score`) and whether mandatory containment standards were met.
- **`Choice` (`SOC_FAILURE_TAXONOMY`).** Classifies the episode into one of seven discrete diagnostic categories:

```python
SOC_FAILURE_TAXONOMY: Dict[str, str] = {
    "A": "FLAWLESS_CONTAINMENT",
    "B": "UNGROUNDED_HALLUCINATED_CLAIM",
    "C": "MISSED_MALICIOUS_BREACH",
    "D": "OVER_CONTAINMENT_FALSE_ALARM",
    "E": "PREMATURE_TERMINATION_ZERO_TOOLS",
    "F": "RUNBOOK_PROCEDURAL_VIOLATION",
    "G": "DEGRADED_MODE_FAILURE",
}
```

Inside `RunbookGEPAAdapter.evaluate()`, the normalized rubric score blends the deterministic sandbox trajectory check (50%) with Jev's expected rubric score (30%) and calibrated grounding probability (20%):

```python
rubric_normalized = (
    0.50 * rubric_normalized
    + 0.30 * (float(jev_out.rubric_score) / 100.0)
    + 0.20 * float(jev_out.grounding_score)
)
jev_choice = jev_out.primary_choice
```

When a case fails, `make_reflective_dataset()` injects `jev_choice` directly into the `Feedback` string sent to the `gemini-2.5-pro` reflection teacher. The fast System-One logprob judge scores every inner-loop rollout in milliseconds without rewarding prose length, and the slow generative teacher is only invoked in the outer loop with a precise failure label (`OVER_CONTAINMENT_FALSE_ALARM` or `UNGROUNDED_HALLUCINATED_CLAIM`).

### 4. Append-only provenance ledger (`HillclimbLedger`)

To prevent the unverified-artifact problem surfaced by our reconciliation report, `HillclimbLedger` writes an append-only JSONL audit log (`configs/runbooks/gepa_evolved/hillclimb_ledger.jsonl`) for every candidate evaluated during a run. Each line records the UTC timestamp, candidate index, composite `harness_sha256`, validation score, $\tau_{\text{accept}}$, the gate decision (`KEPT`, `REJECTED_INVALID`, `REVERTED_REGRESSION`, or `REVERTED_NOISE`), any regressed case IDs, and the exact rejection rationale.

### 5. Automated cost-staircase walk (`run_cost_staircase_walk`)

Once GEPA converges on a validated runbook set, we want to answer our original deployment question: what is the cheapest, smallest model that can execute these evolved runbooks without breaking safety invariants?

Passing `--cost-staircase` triggers `run_cost_staircase_walk()`, which evaluates the winning runbook candidate down our ordered model staircase (`DEFAULT_COST_STAIRCASE_TIERS`):

```python
DEFAULT_COST_STAIRCASE_TIERS: Tuple[str, ...] = (
    "gemini-2.5-flash",
    "gemma-4-31b-it",
    "gemma-4-e4b-it",
    "gemma-3-4b-it",
    "gemma-3-1b-it",
)
```

The first tier (`gemini-2.5-flash`) establishes `ceiling_score`. As the runner steps down through `gemma-4-31b-it`, `gemma-4-e4b-it`, `gemma-3-4b-it`, and `gemma-3-1b-it`, each rung must satisfy two conditions to be selected:

1. **Zero safety violations.** `min_loss_penalty >= 0.999`, meaning the model executed zero prohibited actions (no wrongful host isolations) and made zero false-negative or false-positive verdict errors across the validation cases.
2. **Quality within tolerance.** `mean_score >= ceiling_score - tolerance` (default `tolerance = 0.05`).

The runner writes the full rung-by-rung breakdown to `cost_staircase_report.json` and records the lowest-cost model tier that clears both gates.

---

## Running the disciplined hillclimber

You can run the full optimization loop with harness locking, Step 0 noise-floor estimation, the Jev System-One inner-loop judge, train/validation splitting, and the post-convergence cost staircase walk using a single command:

```bash
PROJECT_ID="dandye-0324-chronicle"
REGION="us-central1"
EVALSET="configs/evals/gen3/soc_tier1_interactive.json"
OUTPUT_DIR="configs/runbooks/gepa_evolved"
LOCK_FILE=".eval_harness_lock.json"

uv run python agent/gepa_runbook_optimizer.py \
  --project-id "$PROJECT_ID" \
  --region "$REGION" \
  --evalset "$EVALSET" \
  --output-dir "$OUTPUT_DIR" \
  --lock-file "$LOCK_FILE" \
  --approve-harness \
  --split-train-val \
  --noise-runs 2 \
  --min-delta 0.015 \
  --max-growth-ratio 1.35 \
  --judge-backend jev \
  --cost-staircase \
  --cost-tolerance 0.05
```

---

## What I learned from breaking the optimizer first

Automated prompt and skill evolution works, but only after you treat the optimizer like an untrusted adversary that will exploit every gap in your measurement rig.

When we let GEPA reflect on raw evaluation traces without guardrails, it memorized the test CIDR blocks and told the analyst to skip enrichment. When we evaluated degraded skills with a generative text judge, `verbose_lore.md` outscored our clean reference skill because small models mimicked the bloat and the judge rewarded shotgun keyword recall. When we audited our own markdown summary tables against the raw JSON reports, we caught unpinned baseline drift and missing provenance metadata.

Fixing those three problems gave us a hillclimber we can actually trust:

- Use degraded skills (`verbose_lore.md`) inside execution sandboxes as a negative control to catch judge verbosity bias before you start optimizing.
- Enforce deterministic anti-memorization and anti-bloat filters (`validate_runbook_candidate()` with `max_growth_ratio = 1.35`) so the teacher model has to write variable-driven verification stages instead of lookup tables.
- Lock the evaluation harness with SHA-256 checksums (`HarnessIntegrityGuard`), measure the Step 0 noise floor ($\tau_{\text{accept}}$) before accepting mutations, and score inner-loop rollouts with calibrated single-pass logprobs (`JevSocJudgeEvaluator`) instead of slow generative essays.
- Walk the evolved skills down the model cost staircase (`run_cost_staircase_walk`) so you can prove, with an append-only JSONL ledger, exactly how small a model you can deploy on a single L4 GPU without sacrificing containment safety.
