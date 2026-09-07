# GCE experiment run identity

Each orchestrated GCE launch attempt now has a unique run ID, a hash of its requested configuration, and a dedicated artifact location. This connects launch, evaluator, collection, and cleanup observations. It does not establish model quality or resolve the deployed source/model revision.

## Launch records

Preview one target without creating cloud resources:

```sh
.venv/bin/python scripts/run_gce_spot_sweep.py --models gemma-2-2b-it --dry-run
```

For an approved live experiment, use the same entry point with explicit project, zone, output bucket, selected model, and the required [source bundle pins](SOURCE_BUNDLES.md). Removing `--dry-run` provisions resources and incurs charges. First complete the [experiment protocol](../experiment_protocol.md), including the reviewer, budget, frozen cases, and acceptance thresholds.

Before each create command, the launcher atomically writes:

```text
logs/experiment_runs/<run_id>/launch.json
gs://<bucket>/<prefix>/runs/<run_id>/<flavor>/
```

Use `--evidence-dir PATH` to change the local directory. Local operational evidence is ignored by Git; preserve or export the whole run directory for review. `--no-wait` still saves the manifest. Zone stockouts produce separate attempt records; uncertain create outcomes remain recoverable and do not trigger a retry elsewhere. Dry runs write no launch records.

The manifest hashes the target configuration, project, selected zone, image family/project, and startup script bytes. Credentials are excluded. The evaluator inherits `EXPERIMENT_RUN_ID` and `EXPERIMENT_CONFIGURATION_HASH`; its `provenance.launch_configuration_hash` binds it to the launch, while `provenance.configuration_hash` continues to describe actual evaluator arguments.

## Recover and inspect

After interruption or an asynchronous launch:

```sh
.venv/bin/python scripts/run_gce_spot_sweep.py --recover logs/experiment_runs/<run_id>/launch.json
```

Recovery collects artifacts and observes the resource using the saved project, zone, and instance name. It never launches a VM. To request removal of that experiment's VM, append `--cleanup`. Deletion requires matching run ID and configuration hash in the existing VM's metadata; command success alone does not establish absence. A remaining or unverifiable resource stays visible in the evidence.

## Read the evidence

Each collection preserves a separate `collection-*` snapshot, including its final cleanup observation, and updates `evidence.json`. Later recovery does not overwrite earlier observations. The bundle retains evaluator case outcomes, errors, timing/token fields when supplied, artifact hashes/locations, startup lifecycle, and resource observations. Each download attempt uses a fresh temporary file. Empty or malformed artifacts and stale or conflicting identities are rejected without exposing their scores as current results. Legacy collection without a launch manifest remains explicitly unverified.

Read these fields separately:

- `evaluation_status`: whether the evaluator completed, independently of case pass rate.
- `artifact_collection`: independent evaluator/lifecycle identity checks and per-file transport results.
- `artifact_evidence_status`: whether required files and successful startup upload/benchmark signals were collected.
- `cleanup.status`: observed absence, presence, identity mismatch, or unavailable state.

CLI success requires completed evaluation, complete artifact evidence, and observed absence (or a requested asynchronous launch/dry run). Recovery of failed or partial runs still writes evidence and exits nonzero.

## Remaining limits

Identity verification means **launch binding only**. Pinned launches now verify source archives before execution and require matching source evidence from both producers. Legacy low-level callers may still retrieve mutable GCS code. Image families, model names, and installed dependencies remain unpinned; source verification does not establish their identities. Benchmark/log files are associated through the dedicated path and downloaded byte hashes; they have no embedded run attestation. Costs, missing token fields, source attestation, and held-out dataset history are not inferred. A controlled comparison still needs approved inputs, fixed serving revisions, actual measurements, and reviewer judgment.
