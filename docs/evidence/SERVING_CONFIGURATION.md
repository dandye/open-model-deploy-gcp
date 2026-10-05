# Pinned GCE serving configuration

New live GCE sweep CLI launches require a serving configuration as well as the [source bundle pins](SOURCE_BUNDLES.md). No approved model revision, image, experiment budget, or live result is supplied by this feature.

## Prepare one configuration

Copy `configs/experiments/serving_config.template.json` to an ignored local path, for example `logs/serving-config.json`. Its null fields deliberately fail validation. Fill in:

- `target_flavor` and `model_repository`: the exact catalog target and its Hugging Face repository.
- `model_revision`: a full lowercase 40-character commit, used for model, tokenizer, and remote code revisions.
- `serving_image`: a compatible vLLM image identified as `registry/repository@sha256:<64 lowercase hex>`.
- `evaluator_image`: a Linux AMD64 image with Python 3.10+ and the evaluator's installed runtime dependencies, identified by the same digest format. It must support `python3 -I /workspace/scripts/eval_soc_agent.py`; install the dependencies from `agent/requirements.txt` and the evaluator's imports when preparing that image. Startup installs no packages into the pinned evaluator environment.
- `boot_image`: a specific `projects/<project>/global/images/<image-name>`, not an image family path.
- `parameters`: explicit tensor parallelism matching the target, positive maximum context length, and GPU memory utilization strictly between zero and one.

Use the [evaluator image build and offline check](EVALUATOR_IMAGE.md) to prepare this dependency environment. Use a trusted registry and retain the referenced images. The evaluator receives a read-only source mount at `/workspace`, writable output at `/output`, host networking, and explicit launch/source identity variables. Its Python entrypoint overrides the image entrypoint. It uses VM credentials through the metadata service; local credential files are not mounted. The image must permit reading the source and writing outputs as root.

A configuration covers one exact target. Extra catalog vLLM flags and mutable GCS model caches are rejected in pinned mode. Secondary/speculative models and arbitrary engine flags need a future structured configuration extension with their own pins.

## Preview and launch

Build the source bundle from a commit that includes `scripts/serving_runtime.py` and `scripts/serving_config.py`. Then preview with real approved references:

```sh
.venv/bin/python scripts/run_gce_spot_sweep.py \
  --models gemma-2-2b-it --dry-run \
  --source-bundle-uri gs://<bucket>/source/<archive>.tar.gz \
  --source-bundle-sha256 <archive-sha256> --source-commit <source-commit> \
  --serving-config logs/serving-config.json
```

Dry runs validate the inputs and print the command without writing launch records or calling cloud APIs. Existing Just recipes also accept `GCE_SERVING_CONFIG` alongside the three source-pin environment variables. Explicit CLI options take precedence. Recovery uses the saved launch configuration, ignores environment defaults, and rejects explicit overrides.

Each launch saves the complete configuration and a canonical `serving-config.json` sidecar, with its SHA-256 bound into metadata and the launch hash. Startup checks the downloaded sidecar before using it. Container pulls and launches use digest references; the runtime compares each created container's image ID with the image inspected for that reference. The evaluator starts only after both container checks pass. Failed downloads, inspections, or configuration checks cannot select the legacy path.

Removing `--dry-run` incurs cloud charges and still requires the approvals and untouched cases in the [experiment protocol](../experiment_protocol.md).

## Read the evidence accurately

Both lifecycle and evaluator provenance contain `serving_runtime`. Collection requires matching configuration, configuration hash, and image IDs from both producers. Missing or conflicting evidence leaves the result partial.

`PINNED_IMAGES_VERIFIED` covers Docker image ID observations and the requested model revision. Docker image IDs differ from registry manifest digests; both are retained. Model revision flags are not independent proof of downloaded weight bytes. Named OS images are requested identities and could be recreated under the same name. Host driver/tool installation remains mutable, and the managed judge revision remains requested-only. Pinning the evaluator image fixes its installed dependency environment for execution; it does not make an unpinned image build recipe reproducible. Overall evaluator provenance therefore remains partial.

Legacy low-level callers without a serving configuration retain explicitly unverified behavior. No registry pulls, container execution, uploads, or cloud experiments were performed by the offline implementation tests.

## Reference behavior

The runtime uses vLLM's [revision arguments](https://docs.vllm.ai/en/v0.10.1/configuration/engine_args.html), Docker's [digest references](https://docs.docker.com/reference/cli/docker/image/pull/), and GCE's [specific image option](https://docs.cloud.google.com/sdk/gcloud/reference/compute/instances/create). Compatibility of the selected images must be checked before an approved live experiment.
