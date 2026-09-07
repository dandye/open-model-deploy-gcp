---
task: Resolve evaluation PR correctness and evidence review findings
project: open-model-deploy-gcp
effort: E3
phase: complete
progress: 8/8
mode: interactive
started: 2026-09-07
updated: 2026-09-07
---

## Problem

PR #1 contains six confirmed review findings despite passing its original tests. Candidate selection, split handling, worker permissions, lifecycle reporting, and documentation need correction.

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

Resolve the six review findings with regression coverage for the five code defects and source-linked corrections for the documentation. Commit and push the verified changes to the existing PR.

## Criteria

- [x] ISC-1: The optimizer exports the highest-scoring eligible candidate.
- [x] ISC-2: Explicit training/validation splitting rejects insufficient datasets.
- [x] ISC-3: Worker containment attempts cannot reach environment dispatch.
- [x] ISC-4: Startup failure handling retains existing evaluator diagnostics.
- [x] ISC-5: Unverified cleanup cannot replace an evaluation failure status.
- [x] ISC-6: Current project narratives qualify historical modeled-loss claims.
- [x] ISC-7: Anti: historical source JSON remains byte-for-byte unchanged.
- [x] ISC-8: Anti: the working branch has no prefix.

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

## Features

| Work | Criteria | Dependencies | Parallelizable |
|---|---|---|---|
| Optimizer eligibility and split corrections | ISC-1, ISC-2 | None | Yes |
| Worker dispatch authorization | ISC-3 | None | Yes |
| Lifecycle evidence preservation | ISC-4, ISC-5 | None | Yes |
| Documentation reconciliation | ISC-6, ISC-7 | Current source artifacts | Yes |
| Verification and PR update | ISC-8 | All fixes | No |

## Decisions

- 2026-09-07: Keep eight concrete review criteria instead of expanding the soft criterion floor; the scoped defects each have a direct regression probe.
- 2026-09-07: Fix authorization at worker dispatch, candidate selection at optimizer output ingestion, and failure preservation before fallback writing. Denied tool attempts remain visible without being represented as executed actions.
- 2026-09-07: Reuse the revised article from the sibling worktree and update its implementation descriptions. Leave that sibling file unchanged.

## Changelog

- Conjectured: guarding worker dispatch and the investigation trace covered worker action accounting.
- Refuted by: an offline call through inherited `query()` still recorded denied containment as executed.
- Learned: both entry points need the same trajectory recorder at the execution boundary.
- Criterion now: ISC-3 also probes inherited query and dispatch aliases, including downstream loss classification.

## Verification

- ISC-1, ISC-2: 44 optimizer tests pass, including highest valid score, rejected best candidate, ties, malformed scores, seed fallback, and dataset boundaries. Initial new regressions reproduced eight failures.
- ISC-3: Dispatch, both worker entry points, and downstream loss checks pass. Denied containment leaves sandbox state unchanged and receives no execution credit; allowed investigation and supervisor behavior remain covered.
- ISC-4: 11 lifecycle tests pass, including byte-preserving diagnostics, missing reports, malformed/stale artifacts, and execution of both embedded startup helpers.
- ISC-5: 31 orchestrator tests pass, including all four authoritative failure statuses across both terminal VM outcomes.
- ISC-6: Read summary and article against the reconciliation; local document links resolve and contradictory headline figures are removed. Platform lifecycle references were checked against official Google Cloud documentation.
- ISC-7: Git diff confirms no historical source JSON changed. The sibling article worktree retains its original uncommitted diff.
- ISC-8: `git branch --show-current` returns `evaluation-evidence`.
- Final validation: 371 Python tests and 28 Bun tests pass. Shell syntax and `git diff --check` pass. The strict historical audit and unfilled experiment template still reject unresolved inputs as intended. No live GPU/model workload was run.
