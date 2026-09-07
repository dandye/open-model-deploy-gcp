# Bounded SOC comparison experiment protocol

Status: protocol ready for review; user acceptance thresholds and the final
case inventory are still pending approval.

This protocol defines the evidence needed for one deployment decision. It is a
measurement procedure, not evidence that a live comparison has already run.
Historical reports remain historical until their source, configuration, and
execution records can be reconstructed.

## Question and bounded workflow

The comparison asks whether an open model can perform one bounded SOC Tier 1
investigation with acceptable task quality, unsafe-action behavior, latency,
and cost relative to a managed baseline. Select one workflow and name the
intended reviewer before the run. A suitable default is: triage one alert,
retrieve the minimum supporting evidence through the available SOC tools,
classify the alert, and produce a structured disposition with recommended
containment actions. The tool set, maximum iterations, output schema, and
stop/error policy are fixed for both configurations.

The open model and managed baseline receive the same prompt envelope, case
payload, tool responses, temperature, output budget, and retry policy. Pin the
open model container by digest, model revision, hardware, region, serving
runtime, and all generation parameters. Pin the managed model revision and
region as far as the provider permits. Keep concurrency, warm-up policy, and
measurement window identical. Compare cold and warm behavior only when both
configurations have the same documented warm-up treatment.

## Dataset split and holdout protection

Create three case inventories before optimization: `train` for runbook or
prompt development, `validation` for selecting a configuration, and
`final_test` for the single held-out comparison. Freeze each file's byte-level
SHA-256 and record its source, creation date, and case exposure history. A
case exposed during prompt, runbook, model, evaluator, or configuration
optimization cannot be moved into `final_test`; renaming an exposed case does
not create a holdout. Do not invent a holdout from the existing exposed
benchmark cases. If an untouched inventory does not exist, the final-test
result is unavailable and the experiment must stop at protocol preparation.

Use [`scripts/validate_experiment.ts`](../scripts/validate_experiment.ts) for
offline preflight. It checks the manifest schema, full source commit, pinned
configuration fields, numeric acceptance fields, repeated runs, dataset
paths/hashes, duplicate IDs, duplicate case content, and a reviewer attestation
whose hash matches `datasets.final_test.sha256`. This check cannot establish
that an identified reviewer is truthful, prove semantic equivalence of cases,
or prove unseen-case history; attach an independent exposure attestation and
retain the dataset provenance record.

Start from
[`configs/experiments/evidence_comparison.template.json`](../configs/experiments/evidence_comparison.template.json).
The decision record in [`docs/evaluation_decision_record.md`](evaluation_decision_record.md)
defines the evidence fields and keeps simulated benchmark loss separate from
observed financial outcomes.

## Runs and measurements

Run at least two repetitions per configuration, with the repetition count
specified in the manifest. Use a fixed case order or a documented randomized
seed, and retain the seed. Record per-case outcome, tool trajectory, evaluator
version, latency, errors, output, and token-count provenance. Report quality
per case and by failure slice; report the median and p95/p99 where the sample
size supports it. A zero-success run has undefined cost per successful task,
not a zero cost.

For serving measurements, retain these separate quantities:

- request latency: elapsed time for each successful request;
- wall-clock batch duration: elapsed time from dispatch of a concurrent batch
  until all futures complete;
- aggregate throughput: total generated tokens divided by wall-clock duration;
- request-normalized throughput: total generated tokens divided by the sum of
  request latencies, retained for compatibility with historical reports;
- actual provider-reported generated tokens versus character-based estimates;
- time to first network chunk versus time to the first verified generated
  token; the former is not evidence of the latter;
- successful requests, failed requests, empty responses, retries, and dropped
  cases.

The benchmark summary's `tps`/`tpm` fields use aggregate wall-clock rates when
the wall-clock interval is supplied. The explicit
`request_normalized_tps`/`request_normalized_tpm` fields preserve the legacy
service-time denominator. Do not combine rates from different configurations
or omit failed requests from the run record.

## Acceptance and cost gates

Before inspecting `final_test` outputs, the decision owner must approve
numeric thresholds for task completion, unsafe-action rate, p95 latency,
cost per successful task, and total experiment budget. The manifest requires
the approver, approval timestamp, and all five values. The template leaves
these fields empty intentionally; no threshold should be inferred from a
historical score or chosen after seeing the result.

Record cloud project, region, resource IDs, start/end timestamps, image and
model digests, request counts, retries, measured runtime, rate-card inputs,
and billed cost when available. Label rate-card calculations as estimates and
attach billing evidence separately. Capture provisioning, serving, evaluator,
artifact upload, and cleanup outcomes independently. Verify that endpoints,
VMs, jobs, disks, IPs, and buckets created for the experiment are deleted or
explicitly retained with an owner and expiry; cleanup success alone is not
proof that every resource disappeared.

## Review and decision

The named reviewer checks the manifest preflight, exposure attestation, fixed
configuration, per-case artifacts, failure slices, token/timing labels, cost
and cleanup evidence, and threshold approval. The decision record then states
accept, iterate, or stop, including limitations and what evidence would change
the decision. Publication, user validation, deployment recommendation, and
customer adoption are separate outcomes and must not be claimed from this
protocol or from simulated loss.
