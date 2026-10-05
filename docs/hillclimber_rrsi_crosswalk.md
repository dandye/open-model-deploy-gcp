---
title: "Disciplined Hillclimber vs RRSI: mechanism crosswalk and gap list"
description: "Mechanism-by-mechanism comparison of the Disciplined Hillclimber's five guards against the proposer and selector regularizers in RRSI (Xia et al., 2026), read through Harness-Delta Attribution, with evidence from the 2026-10-02 run and Campaign 5, and a prioritized gap list."
type: "analysis"
tags:
  - gepa
  - rrsi
  - hillclimbing
  - harness-evolution
  - evaluation
  - soc
created: 2026-10-04
updated: 2026-10-04
---

# Disciplined Hillclimber vs RRSI: mechanism crosswalk and gap list

The Disciplined Hillclimber (`agent/hillclimb_harness.py`, `agent/gepa_runbook_optimizer.py`) was designed in late September 2026 from Anthropic's hillclimbing guides, Lance Martin's invariants, and our own failures with naive GEPA. RRSI (Xia et al., arXiv:2609.24972) was published around the same time and names the same problem more precisely: a harness evolution loop is a statistical estimation procedure, and without regularization on both the proposer and the selector it overfits the evolve set, inflates cost, and loses out of distribution. This document lines up what we built against what RRSI prescribes, says where the evidence from our own runs supports each piece, and lists the gaps in the order I think they should be closed.

Companion documents:

- [DISCIPLINED_HILLCLIMBER_RUN_ANALYSIS.md](soc_eval_results/DISCIPLINED_HILLCLIMBER_RUN_ANALYSIS.md) for the 2026-10-02 run artifacts.
- [references_agent_harness_literature.md](references_agent_harness_literature.md) for the annotated bibliography.
- [blog/gepa_runbook_evolution_and_disciplined_hillclimbing.md](blog/gepa_runbook_evolution_and_disciplined_hillclimbing.md) for the narrative.

## Two frames

RRSI splits regularization into a proposal side and a selection side. On the proposal side: an annealed edit budget (they call it L0-style update sparsity), evidence-aware credit assignment (the proposer conditions on a ledger of what each component change did to score and cost), and structured exploration (detect stalls inside the noise band and spend budget on components that have not been touched). On the selection side: leakage screening (a critic reads the diff before any evaluation and rejects task names, entity names, task-specific values, answers, and inert machinery), stability-aware acceptance (repeatedly evaluate the unchanged base harness to estimate a noise band and require improvement above it), complexity-aware acceptance (allowed cost growth is a linear function of score gain, Ridge-style), and structural pruning (components with no positive gain over a window become deletion targets, Lasso-style). Appendix C adds domain-specific non-compensatory guards: things a candidate can never trade away for score.

Harness-Delta Attribution (Ding et al., 2026) is the diagnostic frame. Any measured improvement from harness evolution decomposes into a genuine, generalizable delta, a test-time compute delta (more tokens, more retries, more steps), and an artifact delta (overfitting to the evolve set or evaluator). Their claim is that much of what gets reported as harness improvement is the second and third kind. The only way to separate them is to hold out a split the loop never touched and to measure cost alongside score.

Both frames assume what RRSI calls a frozen, harness-independent evaluation. Our `HarnessIntegrityGuard` is the mechanism that makes that assumption checkable.

## Summary crosswalk

| RRSI mechanism | Side | Disciplined Hillclimber equivalent | Status | Evidence from our runs |
| --- | --- | --- | --- | --- |
| Leakage screening | Selection | `validate_runbook_candidate()`: IPv4 literals, eval hostnames, `CASE-XX` IDs, short-circuit phrases | Partial (literal, not semantic) | Caught the 2026-09-04 lookup-table candidate; would not catch a paraphrase |
| Stability-aware acceptance | Selection | `estimate_noise_floor()` + `evaluate_candidate_acceptance()`, `REVERTED_NOISE` | Implemented, under-sampled | 2026-10-02: K=2 agreed to 0.00025 while the seed's third sample sat 0.031 away |
| Complexity-aware acceptance | Selection | `max_growth_ratio = 1.35` on characters | Partial (static cap, not cost-vs-gain) | Campaign 5: evolved runbooks raised latency 7.36 s to 12.29 s on `gemini-3.5-flash-lite` while reward fell |
| Structural pruning | Selection | None | Missing | Campaign 5 attributes the drop to template scaffolding, pseudo-code, and diagrams that nothing ever removed |
| Domain non-compensatory guards | Selection | `REVERTED_REGRESSION` (any passing case dropping below 0.80), prohibited-action loss penalty, `min_loss_penalty >= 0.999` in the staircase | Implemented, one hole | Loss penalty is 1.0 for an agent that does nothing |
| Annealed update sparsity | Proposal | None (GEPA rewrites whole files) | Missing | Both 2026-10-02 candidates were whole-file rewrites |
| Evidence-aware credit assignment | Proposal | `HillclimbLedger` exists but the proposer never reads it; `make_reflective_dataset()` passes failed traces plus the Jev failure tag | Partial | Ledger is write-only, reconstructed after the run |
| Structured exploration | Proposal | None beyond GEPA's Pareto candidate selection | Missing | n/a |
| Frozen evaluation | Assumption | `HarnessIntegrityGuard`, `.eval_harness_lock.json`, composite SHA on every ledger row | Implemented | Lock verified 2026-10-02; composite hash matches across lock, ledger, metadata |
| Held-out split | Assumption | `--split-train-val` within the 10-case Gen 3 suite (6 train, 4 val); Harbor sandbox as a true OOD harness | Partial | Campaign 5 is the only OOD test, and it was negative |

## Proposal side

### Annealed update sparsity

RRSI constrains how much of the harness a single proposal may touch, with a budget that shrinks over rounds. We constrain how long the result may be. Those are different things. A 1.35x length cap stops the lookup-table failure mode (the 2026-09-04 candidate tried to grow a 120-line runbook into a 600-line one) but says nothing about how many sections changed. GEPA's reflective mutation returns a complete replacement file, so every accepted candidate is an unbounded edit in RRSI's terms, and nothing in the ledger can attribute a score change to a particular paragraph.

The cheapest approximation inside GEPA is to diff the candidate against the seed at the section level and reject candidates that modify more than `b_t` sections, with `b_t` decreasing per round. That also gives credit assignment something to work with.

### Evidence-aware credit assignment

RRSI's proposer sees a ledger: component, hypothesis, diff, score, cost, accepted or not. Ours has a ledger with most of those columns (`iteration`, `val_score`, `tau_accept`, `decision`, `rationale`, `regressed_cases`) but it is written after `gepa.optimize()` returns and the reflection model never sees it. What the reflection model does see is per-trace: the failed rollout, the CMDB context, the tool trajectory, and the Jev `SOC_FAILURE_TAXONOMY` choice (`OVER_CONTAINMENT_FALSE_ALARM`, `UNGROUNDED_HALLUCINATED_CLAIM`, and so on). That is good trace-level feedback, and it is the part of our design that Bennett's "traces underneath" argument is about. It is not history. The proposer cannot know that the last three attempts to tighten Stage B all got reverted as noise.

Fix: stream ledger entries during the run (see fix 7 in the run analysis) and prepend the last N entries to `build_reflection_prompt_template()`.

### Structured exploration

RRSI detects a stall when progress stays inside the noise band for `w` rounds and then reserves budget for components the loop has not exercised. We have nothing comparable. GEPA's Pareto selection across validation instances provides some diversity among candidates, but there is no stall detector and no notion of untouched components. At 20 metric calls this did not matter. At 200 it will: the loop will keep re-proposing variations on `basic_ioc_enrichment.md` because that is where the failed traces are, and never touch `lateral_movement_hunt_psexec_wmi.md`.

## Selection side

### Leakage screening

Our screen is deterministic regex over the candidate text. It is a hard floor and I would keep it as one. It caught literal CIDR blocks, the scanner IP, benchmark hostnames, `CASE-XX` identifiers, and "skip all enrichment". What it cannot catch is the semantic version of the same leak. The 2026-09-04 evolved runbook classified `${IOC_ROUTING_TYPE}` as `"Reserved"` for documentation space. That is a legitimate network concept, and it is also exactly the concept that makes `CASE-02` pass. Whether that is generalization or paraphrased memorization is a judgment call, and a regex cannot make it.

RRSI uses an LLM critic for this, reading the diff before evaluation and rejecting task-specific values and inert machinery. Layering a critic over the regex is the obvious next step. The critic prompt should be given the held-out case descriptions it must not see reflected back, which is the same de-spoiling discipline we applied to the reflection prompt.

### Stability-aware acceptance

This is the mechanism we implemented most faithfully and the one the 2026-10-02 run tested most directly. The design matches RRSI's: evaluate the unchanged seed repeatedly, derive a band, accept only above it. The implementation under-samples. Two aggregate means agreed to 0.00025 while the per-case scores moved by 0.142 on average and GEPA's own third evaluation of the seed came in 0.031 lower. `tau_accept` was carried by the `min_delta = 0.015` floor, which happened to be about right. The gate still made the correct call on both candidates (+0.0128 and +0.0036 are inside a 0.031 band under any reasonable estimator).

RRSI also uses the band for stall detection, which we do not have, and anchors the comparison on the best accepted score `S*` plus the band, which we do (baseline subscores are the seed's). The fix is a sample count, not a redesign: at least three seed evaluations, the per-case band as the primary statistic, and a threshold that shrinks with the number of validation cases.

### Complexity-aware acceptance

RRSI's rule is that allowed cost increase is `beta_0 + beta_1 * delta_S`: you may spend more tokens only in proportion to the score you gain. Our growth cap is a constant. It does not know about tokens or latency at all, and it does not tighten when a candidate's gain is small. The cost staircase measures cost on a different axis (which model tier can run the runbooks), which is useful for deployment but is not an acceptance criterion inside the loop.

The Campaign 5 numbers show why the difference matters. On `gemini-3.5-flash-lite`, the GEPA-evolved arm took 12.29 s per case against 7.36 s for the clean human-written skill, made 37 tool calls against 35, and scored 0.7459 against 0.8413. That is HDA's compute delta with a negative genuine delta. A Ridge-style acceptance rule evaluated on tokens or latency per case would have refused it.

### Structural pruning

Nothing in our loop ever deletes anything. RRSI's Lasso-style rule marks components with no strictly positive gain over a pruning window as deletion targets and tries removing them. The `master_sweep_report.md` for Campaign 5 attributes the evolved runbooks' failure in the container sandbox to `${IOC_VALUE}` and `${CASE_ID}` template placeholders, pseudo-code `IF/ELSE` blocks, and Mermaid diagrams: material the reflection model added because it looked like structure, that the text-only `SocEnvironment` adapter tolerated, and that produced tool paralysis and zero-tool runs when `gemini-2.5-flash-lite` had to drive `soc-cli` in a shell. That is inert machinery in RRSI's sense, and pruning is the mechanism that would have found it, because removing a Mermaid diagram does not reduce score on any case.

This is the gap I would close first, because it is the only one with a direct line to our worst result.

### Domain-specific non-compensatory guards

Here we are ahead of the paper, because a SOC has a blast radius and a coding benchmark does not. `REVERTED_REGRESSION` rejects any candidate that drops a passing validation case below 0.80 regardless of the mean. The cost engine's prohibited-action penalty (`isolate_host` on a critical asset) and the staircase's `min_loss_penalty >= 0.999` gate are non-compensatory by construction. The hole, documented in the run analysis, is that `calculate_loss_penalty()` returns 1.0 for an agent that does nothing, so the staircase gate cannot tell safe from inert. A liveness requirement closes it.

## What this harness has that RRSI does not emphasize

Three things, each of which came from a failure RRSI's benchmarks would not have produced.

The cryptographic harness lock. RRSI assumes the evaluation is frozen. We had already caught ourselves comparing against a drifted baseline (`GEPA_EVIDENCE_RECONCILIATION.md`), so `HarnessIntegrityGuard` recomputes SHA-256 over the dataset, sandbox, verifier, cost engine, and runner before Step 0 and at the start of every `evaluate()` call, and every ledger row carries the composite hash.

The non-generative inner-loop judge. The `verbose_lore.md` negative control showed that a generative LLM judge plus positive-only assertions rewards length (`gemini-2.5-flash-lite` went from 66.7% on the clean skill to 83.3% on the padded one). RRSI's benchmarks have deterministic or sandboxed verifiers, so they did not need to solve this. Our inner loop scores with Jev's constrained logprob `Score`, `Noul`, and `Choice` evaluations and reserves the generative model for the outer-loop proposer. The negative control arm itself (degraded skills in an execution sandbox) is something I would recommend to anyone evolving prompts against an LLM judge.

The cost staircase. RRSI reports cross-backbone transfer (evolving on Opus 4.8 and running on Gemini 3.5 Flash raised Terminal-Bench 2.1 from 64.6 to 78.7; Gemini 3.1 Flash Lite went from 11.2 to 14.6). Oved et al. argue for the reverse: optimize on a cheap model, deploy on a strong one. Our staircase asks the deployment question directly: what is the smallest Gemma that can run these runbooks safely on one L4. The 2026-10-02 walk did not answer it, for the reasons in the run analysis, but the question is the right one for this project.

## Reading our own results through HDA

Three results, three different decompositions.

The 2026-09-04 evolved runbooks, in distribution. Simulated loss fell from \$250,051.11 to \$100.82, tokens fell from 529,125 to 388,464, latency fell from 40.50 s to 31.93 s, and the two catastrophic isolations on `CASE-02` and `CASE-10` disappeared. Lower cost rules out a compute delta. Strict pass rate fell from 30% to 20% and rubric from 59.8 to 47.5. At the time I read this as a genuine safety gain with a reporting-style regression. HDA would say: you cannot tell until you move the harness.

Campaign 5, out of distribution. Same runbooks, embedded in Harbor tasks, driven through `soc-cli` in a container, 90 trials across three models (branch `harbor_soc_evals_v0001`, `docs/eval_results/harbor_soc/gepa_evolved_sweep/`, commit `3d0e2a3`):

| Model | `no_skills` | `clean_skills` | `gepa_evolved_skills` | GEPA minus clean |
| --- | ---: | ---: | ---: | ---: |
| `gemini-3.5-flash-lite` | 0.7704 | 0.8413 | 0.7459 | -0.0954 |
| `gemini-2.5-flash` | 0.8109 | 0.8555 | 0.7033 | -0.1522 |
| `gemini-2.5-flash-lite` | 0.6731 | 0.6551 | 0.4361 | -0.2190 |

Mean continuous reward from the 60/20/20 verifier; pass rate on `gemini-2.5-flash-lite` went from 50% with clean skills to 10% with the evolved ones. The in-distribution gain did not transfer, and on the smallest model it inverted. Under HDA that moves most of the 2026-09-04 improvement into the artifact column: the runbooks were fitted to the `SocEnvironment` Python tool interface and the text judge, and the fit did not survive a change of harness. Zhang and Khattab's framing is that harness behavior generalizes, or fails to, at the level of the composition of components. We changed one component (the tool transport, from in-process Python calls to a shell CLI) and the evolved policy text stopped composing with it. The human-written `secops-triage` skill, which never saw either harness during authoring, transferred fine.

The 2026-10-02 run. Nothing was accepted, so all three deltas are zero by construction. That is not a failure of the loop. RRSI's ablation shows what the alternative looks like: with no acceptance constraints their evolve-set score went from 90.5 to 91.5, their out-of-distribution average went from 43.6 to 41.0, and token spend rose about 50%. With no constraints at all, evolve-set 92.8, OOD 40.3, 3.80M tokens per trial against 2.42M. The constrained loop's job at a small budget is to say no, and it did.

There is also a holdout-reuse problem that neither frame lets us ignore. Every acceptance decision in our loop is made against the same four validation cases, and the seed alone was evaluated on them three times before any candidate was. Dwork et al. (2015) is the standard reference for why repeated adaptive queries against one holdout leak information from it; RRSI cites it as the theoretical reason for keeping the evolve set and the held-out set separate. Four cases is a small holdout to begin with. The Harbor sandbox is our real held-out split, and the right process change is to make a Campaign-5-style sandbox run a required step before any evolved runbook is written to `configs/runbooks/gepa_evolved/`.

## Prioritized gap list

Ordered by expected value given the evidence above, not by implementation effort.

1. Structural pruning plus a cost-aware acceptance rule. Add a pruning pass that tries removing each section of an accepted candidate and keeps the removal if no validation case loses score; add a per-case token or latency budget to `evaluate_candidate_acceptance()` scaled by `mean_delta`. This targets the Campaign 5 failure directly.
2. Make the OOD sandbox the acceptance criterion of record. No candidate is written to the evolved directory until it has been evaluated in the Harbor `soc-cli` harness on at least one model and has not regressed against the clean-skill arm. This is RRSI's evolve-set versus held-out discipline applied with our own harnesses.
3. Artifact integrity. Per-run output directories, no runbook writes on seed selection, honest `selection_reason`. Cheap, and it would have saved the 2026-09-04 artifact.
4. Noise estimation from at least three seed samples and the per-case band, including GEPA's candidate-0 evaluation as a sample.
5. A liveness requirement in the staircase safety gate, and per-rung trajectory summaries and resolved endpoints in `cost_staircase_report.json`.
6. Stream the ledger during the run and feed the last N entries to the reflection prompt (evidence-aware proposer).
7. An LLM leakage critic layered over the regex screen, given the held-out case descriptions as the things it must not find reflected in a candidate.
8. A section-level edit budget per proposal, annealed per round, so that credit assignment has units to work with.
9. A stall detector on the noise band with budget reserved for untouched runbooks.

## References

Annotated entries, links, and knowledge-base pages are in [references_agent_harness_literature.md](references_agent_harness_literature.md).

- Xia, P., Han, R., Wang, Z., Chen, Y., Zhuang, Y., Lee, Y., Huang, C., Yu, H., CuiZhu, Z., Ming, Y., Yao, H., Gokturk, B., Pfister, T., Lee, C.-Y. (2026). RRSI: Regularized Recursive Self-Improvement of Agent Harnesses. arXiv:2609.24972.
- Ding, W., Lu, Q., Yu, C., Li, S., Jin, S., Liu, X., Durrett, G. (2026). Harness-Delta Attribution: What Evolves When We Talk About Harness Evolution? UT Austin.
- Zhang, A. L., Khattab, O. (2026). Language Model Harnesses Are Compositional Generalizers.
- Agrawal, L. A., et al. (2025). GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning. arXiv:2507.19457.
- Oved, T., Pony, R., Naparstek, O., Barzelay, U., Agrawal, L. A. (2026). Optimize Cheap, Deploy Strong: A Recipe for Cost-Efficient GEPA.
- Dwork, C., Feldman, V., Hardt, M., Pitassi, T., Reingold, O., Roth, A. (2015). Generalization in Adaptive Data Analysis and Holdout Reuse. NeurIPS 28.
- Anthropic (2026). Hill-Climbing on an Eval: Iteratively Improving Claude Applications.
- Martin, L. (2026). Automating eval design and hillclimbing with Claude.
- Bennett, J. (2026). Claude's hillclimb loop, with your traces underneath.
- Kolesnikov, V. (2026). Your Agent Is Only as Good as the Sandbox You Measured It In.
