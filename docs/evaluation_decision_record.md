# Evaluation and Deployment Decision Record

Status: template, pending an actual experiment and user review. Do not replace missing evidence with assumptions.

## Workflow and responsibility

- Intended user and concrete investigation task: pending.
- Current workflow and observed problem: pending.
- Decision owner, implementation contributions, and collaborators: pending.
- Alternatives considered and reasons for the bounded comparison: pending.

## Agreed experiment

Use `configs/experiments/evidence_comparison.template.json` as a starting point. Record the source commit, immutable container digest, model revision, hardware/region, runtime settings, and generation parameters. Dataset paths resolve relative to the manifest. Each dataset is a JSON object with a nonempty `eval_cases` array whose cases have `eval_id`, `id`, or `case_id` fields.

Freeze dataset byte hashes and record training/validation/final-test exposure history. Obtain an identified reviewer's attestation for the final test, tied to its exact hash. The preflight checks duplicate IDs and identical content with renamed IDs; it cannot detect semantic duplicates or prove that a reviewer never exposed a case. Independently review those risks.

Record approval of task-completion, unsafe-action, p95 latency, cost-per-success, and total experiment-budget thresholds before inspecting final-test outcomes. No agreed thresholds currently exist in this template.

## Evidence attached after execution

| Evidence | Required record | Current state |
|---|---|---|
| Reproducibility | Manifest hash, code/config/evaluator/runbook revisions, exact command, run IDs and logs | Pending |
| Task quality | Per-case outcomes, unsafe actions, failure slices, repeated-run variation | Pending |
| Serving performance | Cold/warm latency, wall-clock throughput, token source, errors | Pending |
| Cost | Provisioning/runtime/retry/cleanup durations, rate-based estimates separately from bills | Pending |
| Lifecycle | Evaluator exit, artifact collection, deletion request, independently verified absence | Pending |
| User value | Review feedback, observed analyst effort, operational limitations | Pending |

Simulated loss is an assigned benchmark penalty, not observed financial savings. A low loss score does not establish improved task completion. If there are zero successful tasks, cost per successful task is undefined; do not report zero.

## Decision after review

- Recommendation and evidence supporting it: pending.
- Unfavorable results and limitations: pending.
- Accept, iterate, or stop; accountable owner and decision date: pending.
- Adoption outcome and follow-up observations: pending.
- What evidence would change the decision: pending.

Use verified findings to support subsequent technical articles. Publication, deployment, customer adoption, and measured improvements remain distinct outcomes.
