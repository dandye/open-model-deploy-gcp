# Prepare and check an evaluator image

The GCE pinned runtime needs a compatible Linux AMD64 evaluator image. This workflow builds its dependency environment and checks the actual evaluator entrypoint without a GPU, model requests, or cloud credentials. Docker must be installed and connected to a daemon you control. The check does not pull images automatically.

## Dependency lock and build

`docker/requirements-evaluator.in` selects runtime dependencies from `agent/requirements.txt` plus HTTPX. `docker/requirements-evaluator.lock` fixes all transitive versions and distribution hashes for Python 3.12 / Linux AMD64. Optional GEPA optimization is outside this image's supported smoke profile.

Regenerate and review dependency updates explicitly:

```sh
uv pip compile docker/requirements-evaluator.in --python-version 3.12 \
  --python-platform x86_64-unknown-linux-gnu --generate-hashes \
  --no-emit-index-url -o docker/requirements-evaluator.lock
```

Choose a trusted Python 3.12 Linux AMD64 base, such as an official slim image, and obtain its immutable registry digest. No base digest is invented or automatically approved by this repository. Build with that reference:

```sh
.venv/bin/python scripts/evaluator_image.py build \
  --python-image docker.io/library/python@sha256:<approved-base-digest> \
  --tag evaluator-preflight:local --output logs/evaluator-build.json
```

The builder sends only snapshots of `Dockerfile.evaluator` and the lock file to Docker. Untracked files and repository credentials cannot enter its build context. Docker installs wheels using `--require-hashes --only-binary=:all:` and runs `pip check`; the base must supply Python 3.12. The build can download the base image and locked packages. The resulting record contains the build input hashes and local image ID. A local image ID is not a registry manifest digest.

## Check before publishing

Commit the source revision you intend to run, then build its [source bundle](SOURCE_BUNDLES.md). It must include `scripts/evaluator_smoke.py`. Use the local image ID from the build record:

```sh
.venv/bin/python scripts/evaluator_image.py check \
  --image sha256:<local-image-id> \
  --archive logs/source-bundles/code.tar.gz \
  --sha256 <archive-sha256> --source-commit <source-commit> \
  --output logs/evaluator-preflight.json
```

The checker verifies the source archive before mounting it read-only. It requires an existing Linux AMD64 image, inspects the actual created container, disables pulls and networking, makes the container root read-only, and allows writes only to temporary storage and its output mount. It executes the evaluator in isolated Python mode against one synthetic case, with model and judge calls replaced by deterministic fixtures. Experiment identity and cloud credential environment variables are cleared. The checker requires a successful container exit and a fresh, complete synthetic report, then removes the owned container and its anonymous volumes. Uncertain create outcomes use an attempt label to identify owned resources before cleanup.

For a quick host-only dependency check, run:

```sh
.venv/bin/python -I -B scripts/evaluator_smoke.py --output logs/evaluator-host-smoke.json
```

A host-only pass is not a container pass. A container pass verifies this limited evaluator/import/output profile, not model quality, all optional integrations, or cloud authentication. Reports explicitly mark synthetic evidence. Failed attempts replace stale success with a failure record and return a nonzero exit code.

## Use a checked image

After a separately approved registry publication, retain the image's registry digest. Pull that exact digest onto the checker host explicitly and rerun the check with `--image registry/repository@sha256:<digest>`. Set that digest reference as `evaluator_image` in the [serving configuration](SERVING_CONFIGURATION.md). Neither this builder nor checker pushes an image or changes a serving configuration. Preflight reports are supporting evidence, not a launch authorization gate.

A locked dependency installation and pinned base reduce build variability; they do not promise byte-identical OCI images across build engines or timestamps. Retain the registry image itself. Workflow/reviewer, untouched cases, acceptance thresholds, budget, a compatible vLLM image, and an approved live smoke run remain prerequisites for the controlled comparison.

Reference behavior: [pip hash checking](https://pip.pypa.io/en/stable/topics/secure-installs/), [Docker create options](https://docs.docker.com/reference/cli/docker/container/create/), and [Docker's none network](https://docs.docker.com/engine/network/drivers/none/).
