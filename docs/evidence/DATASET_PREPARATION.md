# Freeze experiment inputs and review exposure history

Experiment schema **2** adds a hash-pinned exposure inventory. A final-test case is rejected if its ID or exact content appears in any listed historical dataset, including history marked `unknown`. Train and validation cases may overlap history. This supplements the existing split-overlap and reviewer-attestation checks.

## Prepare a review packet

Copy `configs/experiments/evidence_comparison.template.json` to an ignored local path. Fill only information you actually have. Dataset paths are relative to the input manifest. Leave a dataset path or approval field null when it is unavailable.

Add historical datasets under `exposure_history.datasets`:

```json
{
  "path": "../configs/evals/gen1/soc_tier1_triage.json",
  "sha256": null,
  "source": "Repository benchmark; record the source revision and known use here",
  "usage": "unknown"
}
```

`usage` is `optimization`, `validation`, `evaluation`, or `unknown`. Name the exposure reviewer and reference their evidence separately in `exposure_history.reviewer` and `.evidence`. The inventory must be nonempty for preflight to pass. Include all known historical sources; an incomplete inventory cannot prove an untouched holdout.

```sh
bun run experiment:prepare logs/draft-experiment.json logs/review-packet
bun run experiment:validate logs/review-packet/manifest.json
```

Preparation copies only the explicitly supplied dataset files into a **new** private directory. It hashes the bytes it copies, records case IDs and content fingerprints, and writes portable relative paths. Null hashes are filled from those bytes; a supplied mismatching hash is an error, never silently replaced. Manifests and datasets must contain strict UTF-8 JSON without a byte-order mark. Invalid manifest encoding fails preparation; invalid dataset encoding keeps the packet DRAFT. Inputs must be regular files, not symlinks, at most 16 MiB each and 64 MiB total, with at most 100 history datasets.

The output contains `manifest.json`, `preparation.json`, `datasets/`, and `history/` as applicable. Existing output directories are never overwritten. Missing supplied files and mismatched hashes fail preparation; missing paths and approvals produce a `DRAFT` packet. An interrupted packet can retain `INCOMPLETE` status and must not be treated as ready.

Exit codes: **0** means `READY_FOR_REVIEW`, **1** means a saved `DRAFT` with outstanding preflight errors, and **2** means preparation failed. Neither status approves or launches an experiment. Approval names, timestamps, thresholds, and holdout attestations are preserved exactly; the tool never fills them in. In particular, calculating a final-test hash does not create a matching reviewer attestation.

## Review limits and migration

Case fingerprints ignore `eval_id`, `id`, and `case_id` and normalize object-key order. Conflicting ID aliases are rejected. Matching IDs are conservatively treated as overlap even if other content changed. Fingerprints detect exact content reuse; renamed titles, rewritten prompts, near-duplicates, and unlisted exposure require human review. A `source` description and named reviewer are declarations, not authenticated proof.

Version 1 manifests must be explicitly upgraded to schema 2 and supplied with exposure history. The template remains incomplete by design. Preparing datasets does not settle source/image readiness, workflow ownership, acceptance thresholds, budget, or permission to use cloud resources.

## Current repository inventory

At merged source `bacaa7672644db9b27b47c7af55662527cfb23a6`, the eight files under `configs/evals/` contain **70 case appearances, 30 distinct IDs, and 40 distinct exact-content fingerprints**. Repeated IDs and changed content across generations are not independent holdout evidence. A local draft packet snapshots these eight files with usage `unknown`; no train, validation, or final-test assignments have been invented.

The outstanding inputs remain a named reviewer, approved acceptance and budget values, pinned comparison configurations, explicit split inventories, and independently supported final-test exposure history. See [the experiment protocol](../experiment_protocol.md).
