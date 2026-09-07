# Serving Open Models for Security Agents, Part 1: Building a Repeatable Experiment

**Author:** Dan Dye

**Series:** Serving Open Models for Security Agents — Part 1 of 3

**Topics:** Google Cloud, vLLM, GPU infrastructure, model evaluation, security agents

A security investigation can spend several turns gathering evidence before it reaches a decision. That makes the economics of model serving a workflow question: how much does it cost to complete a useful investigation, and how long does the analyst wait?

I built `open-model-deploy-gcp` to explore that question across managed model APIs and self-hosted open models. The project brings together deployment automation, inference benchmarks, and an interactive SOC evaluation environment. My work spans model configuration, GPU deployment lifecycles, benchmark instrumentation, and the connection between serving performance and agent behavior.

This first article covers the infrastructure and the decisions behind it. The project is still an experimental platform. Its most useful outcome so far is a concrete way to investigate the tradeoff among task quality, responsiveness, and operating cost—and a clearer view of what the measurements must establish before a deployment recommendation is credible.

## Start with the decision the experiment should support

An open model gives me control over its weights, serving configuration, and execution environment. That control also makes me responsible for capacity, startup behavior, runtime compatibility, and cleanup. A managed API removes much of that infrastructure work. Neither choice establishes the better security workflow by itself.

I framed the comparison around four requirements:

| Requirement | Engineering consequence | Evidence needed to choose a deployment |
|---|---|---|
| Complete a useful investigation | Connect the model endpoint to a common SOC task and tool interface | Correct decisions, grounded tool use, and failure cases |
| Keep waiting acceptable | Measure startup and request latency separately | Cold-start behavior, warm latency, and performance under concurrency |
| Control experiment cost | Give temporary GPU resources an explicit lifecycle | Provisioning duration, retries, teardown outcome, and residual resources |
| Make comparisons repeatable | Record model, runtime, workload, and evaluation configuration | Comparable runs with preserved outputs and configuration provenance |

These are design requirements for the experiment. Their acceptance thresholds still need to come from the intended workflow and its users. A batch evaluation can tolerate a startup delay that would be unacceptable during an interactive investigation.

This also changes the optimization target. Output tokens per second is useful for diagnosing a serving engine. For a deployment decision, I also want **cost per successfully completed task**, with explicit penalties for unsafe or unsupported actions. A cheap response that sends an analyst down the wrong path can be an expensive result.

## Make the model configuration inspectable

The [model catalog](../../configs/models.json) records model identity, hardware choices, runtime settings, and supported deployment targets. Terraform reads that catalog through [its locals](../../terraform/locals.tf); the shell deployment path uses [shared catalog helpers](../../scripts/lib/model_catalog.sh).

For example, the Gemma 2 9B entry currently contains these fields, shown as an excerpt:

```json
{
  "gemma-2-9b-it": {
    "hfRepo": "google/gemma-2-9b-it",
    "compute": {
      "machineType": "g2-standard-12",
      "acceleratorType": "nvidia-l4",
      "acceleratorCount": 1
    },
    "runtime": {
      "tensorParallelSize": 1,
      "swapSpaceGb": 16,
      "gpuMemoryUtilization": 0.95,
      "maxModelLen": 4096
    }
  }
}
```

That is a configuration in this repository, not a universal sizing recommendation. The useful engineering boundary is that hardware and runtime choices can be inspected together. A model fitting into accelerator memory does not establish that it can serve the required context length and concurrency. Host memory, KV-cache demand, and runtime overhead also matter.

One concrete failure recorded in the [deployment notes](../vertex_deployment_notes.md) was a container rejecting its host-memory swap allocation during initialization. That is why I treat a model's configuration as more than a parameter count and GPU name. The runtime version and startup arguments belong in the experiment record too.

The catalog integration is incomplete: the GCE, Custom Job, and GKE sweep scripts also maintain target definitions of their own. Those definitions make the experiments explicit, but introduce another place for hardware choices to diverge. Consolidating them is a useful next step toward reproducibility.

## Give each execution path a reason to exist

The repository contains several execution paths because interactive serving and finite evaluation runs have different lifecycle requirements.

| Path | Question it helps investigate | Main tradeoff |
|---|---|---|
| Vertex AI online prediction | What does a managed endpoint for a self-hosted model require? | Endpoint availability and scaling behavior versus provisioned capacity |
| Cloud Run GPU | Can a request-driven service meet the workflow's needs with scale-to-zero enabled? | Reduced idle instance time versus startup and request-handling behavior |
| GCE Spot GPU VMs | Can a finite benchmark use temporary GPU capacity effectively? | Control over the machine and runtime versus interruptions and cleanup responsibility |
| Vertex AI Custom Jobs | Can deployment and evaluation run inside a managed job lifecycle? | Managed job execution versus startup and packaging overhead |
| GKE with RayCluster and Kueue manifests | How might multiple evaluations share constrained GPU capacity? | Scheduling flexibility versus cluster and integration complexity |

The implementations are in the [Vertex and Cloud Run Terraform](../../terraform/), [GCE sweep](../../scripts/run_gce_spot_sweep.py), [Custom Job sweep](../../scripts/run_vertex_custom_job_sweep.py), and [GKE sweep](../../scripts/run_gke_ray_sweep.py). Having these paths in the repository does not establish equal operational maturity across them.

The Cloud Run path targets L4-based configurations. Cloud Run supports GPU services that scale to zero, but instances are billed throughout their lifecycle, including startup and time spent idle before removal. Minimum instances are charged even while idle. That makes scale-to-zero a useful cost-control mechanism rather than a promise that an experiment has no idle cost. [Cloud Run GPU documentation](https://docs.cloud.google.com/run/docs/configuring/services/gpu).

Similarly, an explicit undeploy command in my Vertex workflow should not be interpreted as a platform-wide limitation. Vertex's documented scale-to-zero feature has endpoint and deployment constraints; requests arriving while a model wakes can receive a retryable response. Those semantics belong in the application design. [Vertex inference autoscaling documentation](https://cloud.google.com/vertex-ai/docs/predictions/autoscaling).

The GKE path remains an experimental extension. Its [RayCluster template](../../k8s/templates/ray_vllm_cluster_template.yaml) currently specifies one worker replica with a minimum of one. It does not establish automatic worker scale-to-zero or validated multi-node serving. I would require an end-to-end execution trace before recommending that path for a shared evaluation service.

## Treat teardown and result collection as part of the experiment

The GCE path has a concrete lifecycle: provision a machine, prepare its local environment, start the model server, run evaluation, upload artifacts, and attempt deletion. The [startup template](../../scripts/templates/gce_startup_template.sh) installs cleanup traps, while the [Justfile](../../Justfile) exposes status and cleanup operations.

Keeping those operations close to deployment makes the experiment easier to operate. It also exposes an important distinction: issuing a delete request is different from confirming the resource is gone. Artifact collection and teardown each need their own outcome. An evaluation can succeed while cleanup fails, or cleanup can succeed while the run produces no usable evidence.

A review of the startup template exposed a more serious measurement issue: a missing evaluator could produce a completed scorecard with fixed success and throughput values. The current implementation replaces that fallback with an explicit failed run, preserves the evaluator exit status, and retains diagnostic artifacts. This correction does not prove that historical reports used the fallback or retroactively validate their provenance.

The lifecycle contract I want is therefore explicit:

1. A resource was provisioned and the intended model became ready.
2. The intended evaluator actually ran against that model.
3. Results and failure logs were preserved with the run configuration.
4. Cleanup was attempted and its outcome independently recorded.

The current implementation supplies parts of that contract, including observed input hashes, evaluator lifecycle records, and separate cleanup status. Fixed per-model artifact paths still cannot prove which launch produced a downloaded result, and local tests cannot establish resource deletion in Google Cloud. Finishing that verification has more value than adding another model to a sweep whose outcomes are difficult to audit.

## Measure the serving engine and the security task together

The [benchmark runner](../../scripts/benchmark.py) includes repeated requests, concurrency controls, latency summaries, and streaming timing instrumentation. The deployment targets also expose vLLM options for quantization and speculative decoding. This creates a practical basis for controlled comparisons of serving configurations.

Metric definitions need the same scrutiny as model configuration. The benchmark now reports aggregate output throughput over wall-clock duration separately from the token rate normalized by summed request latencies. It distinguishes provider-reported token usage from estimates, and first network-chunk timing from the first nonempty generated-content event. These definitions are covered by offline tests; controlled live runs are still needed to establish performance.

For the next serving comparison, I want a fixed model revision, container version, hardware shape, workload, output limit, and concurrency level. I would change one optimization at a time, preserve errors as well as successes, and report cold and warm behavior separately. Cost estimates should include startup, retries, and the period before resources are released; billed cost should be distinguished from a rate-based estimate.

The SOC layer adds another test. The [interactive environment](../../agent/soc_environment.py) and [loss evaluator](../../scripts/eval_cost_engine.py) let me examine the consequences of agent decisions as well as their speed. These are simulated consequences with assigned penalties, not measured production losses.

The existing runbook experiment illustrates why several measures are needed. Its raw and evolved JSON reports show pass rate moving from 3/10 to 2/10 and average rubric score from 59.8 to 47.5, even though the modeled loss falls. The narrative and baseline JSON disagree on the magnitude of that loss and on baseline latency. Until the run identities and scoring versions are reconciled, the headline percentage is not a defensible deployment result. [Raw-playbook report](../soc_eval_results/gemini-2.5-flash-lite_approach3_report.json), [evolved-playbook report](../soc_eval_results/gemini-2.5-flash-lite_gepa_evolved_report.json), and [evidence reconciliation](../soc_eval_results/GEPA_EVIDENCE_RECONCILIATION.md).

Those findings sharpen the decision rather than settle it. A lower loss score can coexist with worse task completion. The next experiment needs to establish which behavior changed, whether the assigned penalties reflect the intended use, and whether the result persists on independent cases.

## The next milestone

I would now narrow the experiment to one security workflow and a small set of deployment configurations. Before expanding the platform, the milestone is a reproducible comparison with verified evaluator execution, traceable artifacts, consistent performance definitions, and observed cleanup outcomes.

That comparison should support a concrete recommendation: which configuration is suitable for the workflow, what it costs under the expected demand pattern, and what limitation would change the choice. User review and operational validation are still needed before turning that recommendation into a production launch.

Part 2 will examine the serving experiment: quantization, speculative decoding, and the distinction between request latency and aggregate throughput. Part 3 will examine the agent experiment: action grounding, asymmetric loss, and independent evaluation of evolved runbooks. The aim is to make the evidence behind each decision inspectable enough that another engineer can reproduce it and a product partner can understand the tradeoff.
