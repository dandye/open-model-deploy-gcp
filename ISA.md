---
task: Resolve evaluation PR correctness and evidence review findings
project: open-model-deploy-gcp
effort: E3
phase: verify
progress: 15/15
mode: interactive
started: 2026-09-07
updated: 2026-09-07
---

## Problem

The first two review rounds resolved eleven defects. A third review reproduced containment without worker evidence and first-token timing delayed by a buffered HTTP read.

## Vision

Evaluation artifacts accurately describe what ran and which actions executed. Project claims distinguish implemented capabilities from unverified historical outcomes.

## Out of Scope

- New cloud deployments or paid model evaluations.
- Changing historical source JSON to reconcile contradictory claims.
- Merging the PR or changing the user's separate article worktree.

## Constraints

- Preserve the unprefixed `evaluation-evidence` branch.
- Use offline tests with mocked external services; Python is authorized.
- Keep both standalone GCE startup scripts usable before a repository checkout exists.

## Goal

Resolve the review findings with regression coverage across the affected execution paths and source-linked documentation. Commit and push the verified changes to the existing PR.

## Criteria

- [x] ISC-1: The optimizer exports the highest-scoring eligible candidate.
- [x] ISC-2: Explicit training/validation splitting rejects insufficient datasets.
- [x] ISC-3: Worker containment attempts cannot reach environment dispatch.
- [x] ISC-4: Startup failure handling retains existing evaluator diagnostics.
- [x] ISC-5: Unverified cleanup cannot replace an evaluation failure status.
- [x] ISC-6: Current project narratives qualify historical modeled-loss claims.
- [x] ISC-7: Anti: historical source JSON remains byte-for-byte unchanged.
- [x] ISC-8: Anti: the working branch has no prefix.

- [x] ISC-9: Supervisor actions without a confirmed successful backend receive no execution credit.
- [x] ISC-10: Supervisor actions require an unambiguous target identified by the investigation.
- [x] ISC-11: Streaming provider failures are excluded from successful benchmark requests.
- [x] ISC-12: Optimizer and evaluator apply the same per-case fault configuration.
- [x] ISC-13: A completed evaluation artifact survives collection with its completion status.
- [x] ISC-14: Missing or failed worker evidence cannot reach supervisor synthesis or containment.
- [x] ISC-15: First-token measurement does not wait for a later HTTP chunk to fill a read buffer.

## Test Strategy

| Criteria | Probe | Required result |
|---|---|---|
| ISC-1, ISC-2 | Optimizer CLI regression tests with mocked GEPA | Best valid score selected; insufficient split fails before optimization |
| ISC-3 | Worker dispatch and investigation-loop tests | No state mutation; denied attempts receive no execution credit |
| ISC-4 | Bun lifecycle tests on shared and embedded helpers | Original failure diagnostics preserved; fallback remains failed |
| ISC-5 | Mocked sweep terminal-state tests | Original failure status remains authoritative |
| ISC-6 | Read summary and article against evidence reconciliation | Claims are qualified and sources linked |
| ISC-7 | Git diff of historical JSON | No changed source artifacts |
| ISC-8 | `git branch --show-current` | Branch remains `evaluation-evidence` |
| ISC-9, ISC-10 | Supervisor execution and target-resolution regressions | No fabricated success, arbitrary inventory action, or failed-action credit |
| ISC-11 | Mock HTTP streaming and runner integration tests | Explicit errors and malformed streams fail; normal SSE/NDJSON remain supported |
| ISC-12 | Shared fixture through optimizer and evaluator | Identical fault responses; no fault leaks between cases |
| ISC-13 | Actual evaluator output through mocked artifact transport | Completion preserved; conflicting failure wins; launch identity remains unverified |
| ISC-14 | Full supervisor queries with plain text, denied calls, outages, and exhausted budgets | Inconclusive result and no action; real observations preserve normal execution |
| ISC-15 | Real HTTPResponse with deterministic chunk arrivals plus localhost probe | First event observed before later token arrival |

## Features

| Work | Criteria | Dependencies | Parallelizable |
|---|---|---|---|
| Optimizer eligibility and split corrections | ISC-1, ISC-2 | None | Yes |
| Worker dispatch authorization | ISC-3 | None | Yes |
| Lifecycle evidence preservation | ISC-4, ISC-5 | None | Yes |
| Documentation reconciliation | ISC-6, ISC-7 | Current source artifacts | Yes |
| Verification and PR update | ISC-8 | All fixes | No |
| Supervisor action verification | ISC-9, ISC-10 | None | Yes |
| Streaming error propagation | ISC-11 | None | Yes |
| Evaluation pipeline contracts | ISC-12, ISC-13 | None | Yes |
| Investigation evidence boundary and unbuffered observations | ISC-14, ISC-15 | None | Yes |

## Decisions

- 2026-09-07: Keep eight concrete review criteria instead of expanding the soft criterion floor; the scoped defects each have a direct regression probe.
- 2026-09-07: Fix authorization at worker dispatch, candidate selection at optimizer output ingestion, and failure preservation before fallback writing. Denied tool attempts remain visible without being represented as executed actions.
- 2026-09-07: Reuse the revised article from the sibling worktree and update its implementation descriptions. Leave that sibling file unchanged.

- 2026-09-07: The second review adds ISC-9 through ISC-13 without renumbering completed criteria. Backend absence records an unexecuted recommendation; this change does not add live containment support.
- 2026-09-07: Per-case fault setup belongs in SocEnvironment so optimization and evaluation cannot diverge. Artifact completion is separate from launch identity and cleanup verification.
- 2026-09-07: Verify investigation from actual structured tool results, independently of model-authored findings. Plain-text MCP results remain unverified because the adapter drops execution metadata. HTTP timing uses available reads rather than filling a fixed-size buffer.

## Changelog

- Conjectured: guarding worker dispatch and the investigation trace covered worker action accounting.
- Refuted by: an offline call through inherited `query()` still recorded denied containment as executed.
- Learned: both entry points need the same trajectory recorder at the execution boundary.
- Criterion now: ISC-3 also probes inherited query and dispatch aliases, including downstream loss classification.
- Conjectured: one reflection on a premature report enforced investigation before containment.
- Refuted by: plain worker prose followed by a malicious supervisor decision isolated a host without any tool evidence.
- Learned: the supervisor must enforce an evidence boundary independently of worker formatting and iteration budgets.
- Criterion now: ISC-14 covers full queries, failures, denied actions, and valid negative evidence.

## Verification

- ISC-1, ISC-2: 44 optimizer tests pass, including highest valid score, rejected best candidate, ties, malformed scores, seed fallback, and dataset boundaries. Initial new regressions reproduced eight failures.
- ISC-3: Dispatch, both worker entry points, and downstream loss checks pass. Denied containment leaves sandbox state unchanged and receives no execution credit; allowed investigation and supervisor behavior remain covered.
- ISC-4: 11 lifecycle tests pass, including byte-preserving diagnostics, missing reports, malformed/stale artifacts, and execution of both embedded startup helpers.
- ISC-5: 31 orchestrator tests pass, including all four authoritative failure statuses across both terminal VM outcomes.
- ISC-6: Read summary and article against the reconciliation; local document links resolve and contradictory headline figures are removed. Platform lifecycle references were checked against official Google Cloud documentation.
- ISC-7: Git diff confirms no historical source JSON changed. The sibling article worktree retains its original uncommitted diff.
- ISC-8: `git branch --show-current` returns `evaluation-evidence`.
- First-round validation: 371 Python tests and 28 Bun tests pass. Shell syntax and `git diff --check` pass. The strict historical audit and unfilled experiment template still reject unresolved inputs as intended. No live GPU/model workload was run.
- ISC-9, ISC-10: 130 related tests pass, including 60 new regressions for absent backends, missing/ambiguous targets, shared inventory addresses, backend failures, downstream loss accounting, and successful sandbox operations.
- ISC-11: 19 benchmark tests pass. Real mocked streams exercise provider errors after partial content, immediate errors, malformed output, valid SSE metadata/multiline events, and mixed request outcomes.
- ISC-12, ISC-13: 14 pipeline tests pass. The same tool outage is observed by evaluation and optimization, normal cases remain isolated, and actual evaluator output retains completion through collection without asserting launch identity. Contradictory failure signals remain authoritative.
- Second-round validation: 451 Python tests and 28 Bun tests pass. Combined implementation diff reviewed; `git diff --check` passes. Historical JSON remains unchanged, and no live cloud or model workload was run.
- ISC-14: 33 new regressions cover absent/failed/denied evidence, budgets of zero/one/three iterations, repeated premature output, valid observations, and valid empty case searches. The initial query regressions reproduced 16 failures before the guard was changed.
- ISC-15: Deterministic HTTPResponse regression reproduced 250 ms instead of the scheduled 10 ms arrival and now passes. The localhost probe improved from approximately 266 ms to 7 ms for an immediately sent 47-byte event, with unchanged generated text.
- Third-round validation: 485 Python tests and 28 Bun tests pass; `git diff --check` passes. No external model or cloud workload ran.
