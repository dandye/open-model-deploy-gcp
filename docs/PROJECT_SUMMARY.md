# Project Summary: open-model-deploy-gcp

`open-model-deploy-gcp` is an experimental platform for deploying open models on Google Cloud and evaluating SOC investigation agents. It connects serving configuration, request performance, tool use, and simulated decision consequences. It does not yet establish production readiness, customer adoption, or measured financial savings.

## Implemented capabilities

- **Model deployment:** a [model catalog](../configs/models.json), Terraform, and orchestration scripts cover Vertex AI, Cloud Run GPU, GCE Spot VMs, Vertex Custom Jobs, and experimental GKE/Ray deployments. Some sweep scripts maintain separate target definitions; catalog integration is incomplete.
- **Serving measurement:** the [benchmark runner](../scripts/benchmark.py) distinguishes wall-clock aggregate throughput from request-normalized throughput, reported token usage from estimates, and network-chunk timing from generated-content timing. Quantization and speculative decoding options provide configurations for controlled comparisons; their presence does not establish a verified speedup.
- **SOC simulation:** the [environment](../agent/soc_environment.py) models investigation tools, containment actions, and injected failures. Evaluation combines task assertions, trajectory checks, signal-detection metrics, and assigned operational-loss penalties.
- **Runbook optimization:** a [supervisor/worker architecture](../agent/hierarchical_soc_agent.py) separates investigation from containment. [GEPA](../agent/gepa_runbook_optimizer.py) optimizes runbook text, filters candidates for memorization patterns, and selects eligible candidates by validation score. This optimizes prompts, not model weights; optimization validation is not an untouched final test.
- **Evidence handling:** failed or missing evaluators produce failure artifacts. Input provenance, artifact collection, and cleanup outcomes are recorded separately. Manifest-bound GCE runs use dedicated artifact paths and reject mismatched run/configuration identities. Legacy artifacts remain unverified. Recovery observes cleanup separately; a deletion request does not prove absence. See [run identity and recovery](evidence/EXPERIMENT_RUNS.md).

## Historical evidence and limitations

The [evidence reconciliation](soc_eval_results/GEPA_EVIDENCE_RECONCILIATION.md) compares the raw-playbook and evolved-runbook JSON artifacts:

| Reported metric | Baseline | Evolved |
|---|---:|---:|
| Passed cases | 3/10 | 2/10 |
| Average rubric score | 59.8 | 47.5 |
| Average latency | 40.5 s | 31.93 s |
| Simulated operational loss | $250,051.11 | $100.82 |

These are historical artifact values, not verified comparative outcomes. The older narrative uses conflicting baseline loss and latency figures, and the artifacts lack sufficient lifecycle and provenance evidence. Lower modeled loss coexists with worse task completion and rubric scores. No headline percentage reduction, actual avoided outage, realized saving, guaranteed zero idle cost, or verified serving speedup follows from these records. Historical source artifacts remain unchanged for auditability.

## Validation and next milestone

The [offline validation guide](evidence/VALIDATION.md) documents the Python and Bun suites, evidence audit, and experiment preflight. Passing those tests verifies the covered local behavior; it does not establish live serving performance or cloud cleanup. The strict historical evidence audit deliberately fails on the unresolved discrepancies.

The next milestone is one bounded workflow comparison using the [experiment protocol](experiment_protocol.md): frozen and disjoint datasets, an untouched final test, immutable serving configuration, repeated runs, attributable results, independently verified cleanup, and user-approved acceptance thresholds. Record the resulting recommendation and its limitations in the [decision record](evaluation_decision_record.md).
