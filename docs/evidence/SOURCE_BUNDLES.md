# Verified experiment source bundles

New live GCE sweep CLI launches require an exact source archive URI, SHA-256 digest, source commit, and a [pinned serving configuration](SERVING_CONFIGURATION.md). Startup verifies those bytes before running the evaluator. This establishes source identity independently of model/image identity and cleanup.

## Build locally

From a checkout containing the source revision you want to deploy:

```sh
git submodule update --init third_party/ai-runbooks
.venv/bin/python scripts/source_bundle.py build --revision HEAD --output logs/source-bundles/code.tar.gz
```

The builder reads committed Git objects, including the runbook submodule commit pinned by that revision. Dirty edits, ignored files, and untracked files are not bundled. The submodule must have the pinned objects locally; its current checkout may differ. Commit desired changes before building a deployable archive.

Output includes the archive and `code.tar.gz.json`, which records its SHA-256, source commit, and local path. Archive ordering, timestamps, owners, and gzip headers are deterministic. The manifest inventories file hashes and records intentional omissions: the unused `external/adk_runbooks` submodule and the two legacy deployment/README symlinks. Other unsupported entries and recognized credential/state filenames are rejected. This filename check is not a secret scanner.

## Verify locally

Use the digest and commit from the descriptor, and a destination that does not exist:

```sh
.venv/bin/python scripts/source_bundle.py verify \
  --archive logs/source-bundles/code.tar.gz \
  --sha256 <descriptor-sha256> --source-commit <descriptor-source-commit> \
  --destination logs/source-bundles/verified-source
```

Verification checks the archive digest before parsing, then validates commit, inventory, paths, entry types, and every file hash. It rejects links, special files, duplicate paths, traversal, oversized entries, and filesystem collisions. Files are staged privately and checked again before the directory is promoted. Failures do not publish a partial destination.

## Supply a source pin

After the experiment and its storage upload are approved, upload the archive to a dedicated object and retain the descriptor. Uploading is a separate operation; neither builder nor verifier uploads or provisions anything.

Preview the launch using an existing approved object:

```sh
.venv/bin/python scripts/run_gce_spot_sweep.py --models gemma-2-2b-it --dry-run \
  --source-bundle-uri gs://<bucket>/source/<archive-sha256>.tar.gz \
  --source-bundle-sha256 <descriptor-sha256> \
  --source-commit <descriptor-source-commit>
```

For existing `just gce-spot-run` and `just gce-spot-sweep` recipes, supply the same pins through `GCE_SOURCE_BUNDLE_URI`, `GCE_SOURCE_BUNDLE_SHA256`, and `GCE_SOURCE_COMMIT` environment variables. Explicit CLI flags take precedence. Recovery ignores these environment defaults and uses its saved manifest.

The launcher binds source pins and the trusted verifier script digest into the launch configuration. It supplies the verifier through VM metadata. Startup checks the verifier digest before executing it, downloads the exact archive, and verifies/extracts into a fresh directory. Metadata outages, incomplete pins, failed downloads, or mismatched bytes fail the run; they cannot select the legacy mutable source path. The evaluator runs from the verified directory.

The evaluator and startup lifecycle both record `source_bundle`. Collection requires matching verified digest/commit values from both when the launch requested a source pin. Missing or conflicting source evidence leaves the bundle partial. Recovery uses the saved pins and rejects CLI overrides.

## Verification boundary

`source_verification.status: VERIFIED` means the trusted startup wrapper verified the archive bytes and manifest before execution. Source-to-commit attribution comes from the local builder; this is not an independent Git signature verification or runtime attestation. Local source file hashes remain available in evaluator provenance. The [serving configuration](SERVING_CONFIGURATION.md) separately pins requested model revisions and server/evaluator container digests. Weight-byte attestation, resolved OS identity, host dependencies, and live comparison evidence remain separate.

Legacy low-level launch callers and startup scripts without source metadata remain available and explicitly unverified. New live sweep CLI launches require source pins. Dry runs need no pins and make no cloud calls. See [experiment run recovery](EXPERIMENT_RUNS.md) and the [experiment protocol](../experiment_protocol.md) for the remaining approvals and evidence requirements.
