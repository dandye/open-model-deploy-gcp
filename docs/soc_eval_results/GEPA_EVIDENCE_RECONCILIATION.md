# Evaluation Evidence Reconciliation

Generated: 2026-09-07T02:03:40.783Z

This report is generated directly from the source JSON artifacts. Dollar amounts are outputs of the simulated operational-loss model; they do not establish actual savings, avoided downtime, or realized business impact.

## Artifacts

| Role | Artifact | SHA-256 | Lifecycle | Provenance |
| --- | --- | --- | --- | --- |
| Baseline / raw-playbook comparison | gemini-2.5-flash-lite_approach3_report.json | `1eac0734a1f1ac5835d02093b77633b760aed6f1d8fb7db8c9236aa4c72576fa` | unverified | missing fields |
| Evolved / GEPA runbooks | gemini-2.5-flash-lite_gepa_evolved_report.json | `69781dc12c2e5f6dc66a4a4a4c0f1a23c8a660ab9ef8fad0af1c1b7fd5d7ec8c` | unverified | missing fields |

## Side-by-side metrics

`Unavailable` means the source did not provide a valid finite value. It is not a zero.

| Metric | Baseline | Evolved | Evolved − baseline |
| --- | ---: | ---: | ---: |
| Total cases | 10 | 10 | +0 |
| Passed cases | 3 | 2 | −1 |
| Pass rate | 30.00% | 20.00% | −10.00 pp |
| Average rubric score | 59.8 | 47.5 | −12.3 |
| Average latency (s/case) | 40.5 | 31.93 | −8.57 |
| Total tokens | 529,125 | 388,464 | −140,661 |
| Tool invocations | 52 | 45 | −7 |
| Hit rate | 85.71% | 92.86% | +7.14 pp |
| False alarm rate | 33.33% | 66.67% | +33.33 pp |
| Total operational loss | $250,051.11 (simulated loss) | $100.82 (simulated loss) | −$249,950.29 simulated loss |
| False-positive loss | $50.00 (simulated loss) | $100.00 (simulated loss) | +$50.00 simulated loss |
| False-negative loss | $250,000.00 (simulated loss) | $0.00 (simulated loss) | −$250,000.00 simulated loss |
| Investigation cost | $1.11 (simulated loss) | $0.82 (simulated loss) | −$0.29 simulated loss |

## Evidence status

- Baseline case results: 10; non-success case statuses: 0
- Evolved case results: 10; non-success case statuses: 0
- Historical result verification: unverified; lifecycle and/or provenance evidence is incomplete

## Audit findings

- **WARNING** `missing-provenance`: Missing provenance fields: source_commit, model, configuration_hash, dataset, runbook, evaluator, started_at, completed_at, logs, lifecycle. Historical conclusions remain unverified.
- **WARNING** `unverified-lifecycle`: Run lifecycle evidence is missing or unresolved; this result cannot be treated as a verified successful run.
- **WARNING** `missing-provenance`: Missing provenance fields: source_commit, model, configuration_hash, dataset, runbook, evaluator, started_at, completed_at, logs, lifecycle. Historical conclusions remain unverified.
- **WARNING** `unverified-lifecycle`: Run lifecycle evidence is missing or unresolved; this result cannot be treated as a verified successful run.
- **ERROR** `narrative-json-mismatch`: Narrative claims $55050.56 → $100.82 total loss, but selected JSON reports 250,051.11 USD → 100.82 USD.
- **ERROR** `narrative-reduction-mismatch`: Narrative claims a 99.8% reduction, while selected JSON implies 99.96%.
- **ERROR** `narrative-table-mismatch`: Narrative table false positive loss claims 50050 → 100, while selected JSON reports 50 → 100.
- **ERROR** `narrative-table-mismatch`: Narrative table false negative loss claims 5000 → 0, while selected JSON reports 250000 → 0.
- **ERROR** `narrative-table-mismatch`: Narrative table total operational loss claims 55050.56 → 100.82, while selected JSON reports 250051.11 → 100.82.
- **ERROR** `narrative-table-mismatch`: Narrative table average latency claims 22.81 → 31.93, while selected JSON reports 40.5 → 31.93.
- **WARNING** `simulated-savings-claim`: Narrative contains savings/avoidance claims. Treat them as simulated loss-model results, never as actual savings or avoided downtime.

## Interpretation limits

The source reports are historical artifacts. This reconciliation does not rerun an evaluator, validate an untouched final test set, prove that a cloud run completed successfully, or turn modeled loss into financial savings. A future run record should satisfy the provenance contract in `docs/evidence/EXPERIMENT_PROVENANCE_SCHEMA.json`.
