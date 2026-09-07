# Evaluation experiment provenance contract

Future evaluation artifacts must carry enough identity and lifecycle evidence for a reviewer to reproduce and qualify a result. The machine-readable contract is [EXPERIMENT_PROVENANCE_SCHEMA.json](EXPERIMENT_PROVENANCE_SCHEMA.json).

Each run record must identify:

- the exact source commit and a stable configuration hash;
- the model and serving identity, separating the requested/observed model from the resolved endpoint or model revision when both are available;
- configuration values observed at invocation and values resolved by the serving platform; if resolution was not captured, record an explicit `unknown` status with a reason;
- the dataset revision and split, including whether cases were exposed during optimization;
- the runbook identity and revision/hash, including whether runbooks were enabled;
- the evaluator implementation and scoring configuration;
- start and completion timestamps;
- references to evaluator, artifact-collection, runtime, and cleanup logs;
- lifecycle status and references to each outcome, including non-success runs.

The contract is intentionally separate from the historical JSON files. Existing reports omit these fields, so their benchmark conclusions are marked unverified by the audit tool. Adding a provenance block after the fact must not be used to imply that an old run had evidence it never recorded.

The evaluation runner now captures an initial `provenance` block automatically: run ID, Git commit/dirty state, input configuration hash, dataset and local source/runbook hashes, timestamps, and evaluator completion. This partial record is deliberately not a schema-conforming verified result. Resolved serving revision, external lifecycle outcomes, and log references remain unavailable until independently collected. The runner marks this `partial_observed_inputs`; do not fill those gaps by inference. The audit tool checks presence and reported lifecycle signals; it does not validate the full JSON Schema, fetch log references, or independently verify their contents.

The lifecycle record is part of the result, rather than an inferred property of the summary. A failed evaluator, missing artifact, or failed cleanup must remain visible even when partial metrics exist. A consumer should reject a result as a verified successful benchmark unless the lifecycle status is `success` and the referenced evaluator and artifact logs support that outcome.

Dollar values in the current evaluation reports come from a simulated operational-loss model. They may support a modeled comparison under the stated assumptions; they are not actual savings, avoided downtime, revenue, or customer impact. Reports and articles must use that qualification whenever they mention loss reductions or counterfactual avoidance.

Example shape for a future run:

```json
{
  "source_commit": "<git revision>",
  "model": {
    "name": "<requested model>",
    "version_or_revision": "<observed model revision>",
    "observed": { "name": "<requested model>", "version_or_revision": "<observed revision>" },
    "resolved": { "name": "<resolved endpoint/model>", "version_or_revision": "<resolved revision>" }
  },
  "configuration_hash": "<sha256>",
  "configuration": {
    "observed": { "<input setting>": "<value>" },
    "resolved": { "<platform setting>": "<value>" }
  },
  "dataset": { "name": "<dataset>", "version_or_revision": "<dataset revision>", "split": "final-test" },
  "runbook": { "name": "<runbook set>", "version_or_revision": "<runbook revision>", "enabled": true },
  "evaluator": { "name": "<evaluator>", "version_or_revision": "<evaluator revision>" },
  "started_at": "<RFC 3339 timestamp>",
  "completed_at": "<RFC 3339 timestamp>",
  "logs": [
    { "uri": "<evaluator log reference>", "kind": "evaluator" },
    { "uri": "<artifact log reference>", "kind": "artifact" },
    { "uri": "<cleanup log reference>", "kind": "cleanup" }
  ],
  "lifecycle": {
    "status": "success",
    "outcome_refs": [
      { "uri": "<evaluator outcome reference>", "kind": "evaluator" },
      { "uri": "<artifact outcome reference>", "kind": "artifact" },
      { "uri": "<cleanup outcome reference>", "kind": "cleanup" }
    ]
  }
}
```
