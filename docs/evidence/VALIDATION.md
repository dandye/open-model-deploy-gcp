# Offline validation

Run commands from the repository root. The checks below use fixtures and mocked cloud calls; they do not establish live serving performance or customer usefulness.

## Test environment

```sh
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements-test.txt
.venv/bin/python -m pytest -q
bun test
git diff --check
```

The existing hierarchical/GEPA tests require the pinned `third_party/ai-runbooks` submodule. Initialize it with `git submodule update --init third_party/ai-runbooks`; access to `dandye/ai-runbooks` is required. Its GitHub URL replaces the former machine-specific local path, and the pinned commit was verified on GitHub. Initial validation in this worktree used the existing sibling repository at that same commit.

## Execution and pipeline contracts

- Supervisor containment requires an explicit, unambiguous target and a successful backend response. Missing backends or targets, denied operations, and backend failures remain visible as attempts without execution credit. Live MCP containment is not implemented; enabling live investigation does not establish containment capability.
- The supervisor also requires usable structured evidence from an executed investigation tool. Exhausted retries, tool errors, denied calls, and unverified plain-text MCP results produce an inconclusive outcome without synthesis or containment. Valid negative observations, such as an empty case search, remain usable.
- When the worker cannot produce a final assessment, fallback risk comes from exact `verdict` and `reputation` values in successful results. Vote field names, process names, arbitrary prose, and failed responses do not establish risk. Unrecognized values remain unknown; explicit malicious and suspicious assessments take precedence over benign assessments across results.
- GEPA optimization and the evaluator construct isolated sandbox environments through `SocEnvironment.from_eval_case`, applying the same declared tool faults. Faults do not carry into subsequent cases and are not installed in live MCP mode.
- `COMPLETED` means the evaluator finished, independently of case pass rate. Collection preserves explicit completion and failure signals, with failures taking precedence. Legacy collection does not establish launch identity or successful cloud cleanup. Manifest-bound GCE collection validates run ID/configuration hash separately from evaluator success and resource absence.
- Streaming benchmark requests containing provider errors or malformed events count as failures even after partial generation. Valid SSE metadata and multiline events remain supported.
- First-token timing reads available HTTP data without waiting for a fixed-size buffer to fill. A regression uses Python's real HTTP response reader with deterministic chunk arrivals; localhost streaming also verifies the short-event case.

`tests/test_evaluation_pipeline.py` exercises real evaluator output through mocked artifact transport and compares optimizer/evaluator fault responses. Supervisor and benchmark regressions cover execution credit and mixed successful/failed requests. These checks make no cloud or model calls.

## Run identity and recovery

`tests/test_experiment_run.py` covers unique same-model launches, zone retries, interrupted creation, stale/mismatched artifacts, partial uploads, saved-manifest recovery, and deletion identity checks with mocked cloud transport. Executable shell tests verify final lifecycle marker publication and upload failures in both startup scripts. Recovery regressions also cover empty logs, bounded monitoring, and preserved cleanup observations across repeated collection. See [GCE experiment runs](EXPERIMENT_RUNS.md) for the file contract and recovery commands.

## Source archive verification

`tests/test_source_bundle.py` verifies committed-source builds, pinned submodule objects, reproducible bytes, and rejection of unsafe or inconsistent archives. `tests/test_source_bootstrap.py` executes both actual startup verification functions with offline metadata/transport fixtures. Integration tests cover source pins in launch metadata, provenance, and collection. These tests do not attest serving images, model revisions, or installed dependencies. See [source bundles](SOURCE_BUNDLES.md).

## Evidence audit

```sh
bun run evidence:audit --output docs/soc_eval_results/GEPA_EVIDENCE_RECONCILIATION.md
bun run evidence:audit --strict
```

Normal mode writes the report even when historical evidence is inconsistent. Strict mode exits nonzero for detected errors; the current historical mismatch intentionally fails this audit. Passing unit tests means the audit detects those discrepancies correctly, not that historical results have been validated. The original JSON is unchanged; the narrative has a review addendum pointing to the reconciliation, with historical figures preserved.

## Experiment preflight

```sh
bun run experiment:validate configs/experiments/evidence_comparison.template.json
```

The template intentionally fails. Supply real workflow/reviewer information, approved thresholds, model configuration, frozen dataset paths/hashes, and final-test exposure evidence in a separate completed manifest. A successful offline preflight checks structure, hashes, and exact overlap; it cannot prove unseen-case history, serving identity, cloud cleanup, or reviewer approval authenticity.

See [the experiment protocol](../experiment_protocol.md) and [decision record](../evaluation_decision_record.md) for the remaining live evidence requirements.

## Serving configuration pins

`tests/test_serving_config.py`, `tests/test_serving_launch.py`, `tests/test_serving_runtime.py`, and `tests/test_serving_bootstrap.py` cover strict configuration, metadata initialization in both startup scripts, mocked Docker commands and image inspection, evaluator failures, and conflicting collected evidence. These checks are offline and do not prove an image is available, compatible, or deployed. See [serving configuration](SERVING_CONFIGURATION.md).

## Evaluator image preparation

`tests/test_evaluator_smoke.py` executes the evaluator with synthetic fixtures and network guards, including its isolated Python entrypoint. `tests/test_evaluator_image.py` checks allowlisted build inputs, image identity/platform, fresh report validation, and cleanup through mocked Docker and Podman calls. The host smoke also passes in an environment containing only the hash-locked dependencies. An actual Podman 5.8.2 build and container check passed on September 7, 2026, using Linux AMD64 emulation on an ARM64 machine. The image installed all 45 locked dependencies, passed `pip check`, and completed the synthetic evaluator case with networking disabled and read-only source. Docker itself and the GCE runtime remain untested here. The [recorded Podman evidence](podman_preflight.json) identifies the pinned base, image ID, source commit, archive hash, and smoke checks. A negative container check rejected the bare Python base without runtime dependencies and replaced a seeded stale PASS with FAIL. A real SIGTERM cancellation during an attached Podman container returned failure and confirmed removal; a second real check covered cancellation during normal removal. Subprocess regressions cover interrupted creation, attach, and removal, including repeated signals during cleanup. Full regression validation passed 753 Python tests and 33 Bun tests. See [image preparation](EVALUATOR_IMAGE.md).

## Dataset preparation and exposure history

`tests/prepare_experiment.test.ts` checks private portable snapshots, approval preservation, missing and changed inputs, output collisions, and draft exit status. `tests/validate_experiment.test.ts` additionally checks schema 2, historical exposure overlap, canonical fingerprints, conflicting aliases, invalid history, and incomplete reviewer metadata. The real repository inventory produces a DRAFT packet, with reviewer/acceptance/configuration/split/holdout requirements still pending; no historical case is certified untouched. See [dataset preparation](DATASET_PREPARATION.md).

PR #6 review verification: **55 Bun tests passed**. Strict UTF-8 regressions prevent malformed dataset bytes from qualifying as ready and prevent manifest text from being silently replaced; history inputs and both CLI entrypoints use the same decoder. Independent probes also covered output-directory races, FIFO/oversized inputs, and interrupted preparation retaining INCOMPLETE status. The existing eight-file draft remains hash-valid with experiment inputs pending.
