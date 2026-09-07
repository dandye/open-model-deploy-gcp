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
