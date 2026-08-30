---
title: "GKE with Ray Serve & Kueue: Distributed Multi-Model Inference & Benchmarking"
description: "Architecture design, RayCluster manifests, Kueue batch queuing, Justfile recipes, and testing procedures for distributed LLM inference and benchmark sweeps on Google Kubernetes Engine."
type: "architecture"
tags:
  - gemma
  - gke
  - kubernetes
  - ray-serve
  - vllm
  - kueue
  - benchmarking
created: 2026-08-30
updated: 2026-08-30
---

# GKE with Ray Serve & Kueue: Distributed Multi-Model Inference & Benchmarking

This document specifies the architecture, Kubernetes manifests, RayCluster custom resources, Kueue batch job queuing, CLI tooling, and testing procedures for executing multi-model LLM benchmarking sweeps on **Google Kubernetes Engine (GKE)**.

---

## 1. Architectural Concept & Component Layout

For enterprise-grade inference and multi-model benchmarking across heterogeneous GPU clusters, GKE provides fine-grained orchestration using KubeRay (Ray on Kubernetes), Kueue (batch resource scheduling), and vLLM:

```
[Benchmark Sweep Queue (37 Target Models)]
                   |
                   v
[Kueue Batch Queue (LocalQueue / ClusterQueue)]
                   |
                   v
[KubeRay Operator: Provisions RayCluster Pods on GKE GPU Node Pool]
                   |
                   +--> Worker Pod 1: 4x L4 (g2-standard-48) -> vLLM Tensor Parallelism (TP=4)
                   +--> Worker Pod 2: 2x A100 (a2-highgpu-2g) -> Two-Model Draft Proposers
                   |
                   v
[Benchmark Runner Job executes against Ray Serve vLLM Endpoint]
                   |
                   v
[Upload Scorecards & Traces to Google Cloud Storage (gs://...)]
                   |
                   v
[Kueue Releases GPU Node Pool -> GKE Cluster Autoscaler scales to 0 nodes ($0.00 Idle)]
```

---

## 2. Key Advantages & Capabilities

1. **Multi-Model Concurrent Serving**: Host multiple models (e.g. Gemma 3 4B, Gemma 3 27B FP8, Gemma 4 31B) across independent Ray Serve deployments within a single cluster.
2. **Distributed Multi-Node Tensor Parallelism**: Scale beyond single-VM limits for ultra-large models (e.g. 70B parameter models distributed across multiple nodes via Ray actor pipelines).
3. **Automated Resource Queuing via Kueue**: Queue all 37 benchmark targets simultaneously; Kueue manages GPU quota consumption, scheduling jobs sequentially or in parallel as GPU nodes become available.
4. **Dynamic Scale-to-Zero Node Pools**: GKE Node Auto-Provisioning (NAP) and Cluster Autoscaler provision GPU nodes dynamically and deprovision them to **0 active nodes ($0.00 idle cost)** when the batch queue is empty.

---

## 3. Justfile Automation Recipes

The repository provides high-level `Justfile` commands for managing the GKE Ray and Kueue lifecycle:

| Recipe | Description | Usage |
| :--- | :--- | :--- |
| `just gke-ray-init [cluster] [region]` | Initialize GKE cluster credentials and apply Kueue queues (`k8s/kueue_queues.yaml`) | `just gke-ray-init gemma-eval-cluster us-central1` |
| `just gke-ray-run [flavor] [dry_run]` | Run a single model benchmark against a GKE RayCluster | `just gke-ray-run gemma-3-4b-it` |
| `just gke-ray-sweep [models] [dry_run]` | Execute a full or filtered benchmark sweep across GKE Ray workloads | `just gke-ray-sweep "gemma-3-4b-it,gemma-3-12b-it"` |
| `just gke-ray-status [namespace]` | Query active RayClusters, Kueue LocalQueues, and batch Jobs | `just gke-ray-status gemma-benchmarks` |
| `just gke-ray-cleanup [namespace]` | Delete all RayClusters and batch Jobs to release GPU node pools | `just gke-ray-cleanup gemma-benchmarks` |

---

## 4. Python CLI Orchestrator (`scripts/run_gke_ray_sweep.py`)

The orchestrator manages rendering of Kubernetes manifests, job submission to Kueue, lifecycle monitoring, and GCS metric collection.

### Command-Line Arguments

```bash
uv run python3 scripts/run_gke_ray_sweep.py [OPTIONS]
```

* `--models [STR ...]`: Filter specific model flavor(s) (e.g. `gemma-3-4b-it`, `gemma-3-27b-it-speculative`, `qwen3.8-flash-next`). Supports commas and wildcards.
* `--namespace [STR]`: Kubernetes namespace (default: `gemma-benchmarks`).
* `--queue-name [STR]`: Kueue local queue name (default: `llm-sweep-queue`).
* `--output-gcs-bucket [STR]`: GCS bucket for evaluation artifacts and scorecards (default: `dandye-0324-chronicle-soc-benchmarks`).
* `--dry-run`: Render manifests and simulate execution without applying changes via `kubectl`.
* `--no-wait`: Submit workloads asynchronously without waiting for job completion.
* `--timeout-seconds [INT]`: Per-job completion timeout in seconds (default: `3600`).

### Dry-Run Example

```bash
uv run python3 scripts/run_gke_ray_sweep.py --models gemma-3-4b-it --dry-run
```

---

## 5. Kubernetes Manifest Templates

### 5.1 Kueue ClusterQueue & LocalQueue (`k8s/kueue_queues.yaml`)

Defines cluster-wide GPU quotas and the local queue for namespace workloads:

```yaml
apiVersion: kueue.x-k8s.io/v1beta1
kind: ClusterQueue
metadata:
  name: "gpu-benchmark-cluster-queue"
spec:
  namespaceSelector: {}
  resourceGroups:
    - coveredResources: ["cpu", "memory", "nvidia.com/gpu"]
      flavors:
        - name: "l4-gpu-flavor"
          resources:
            - name: "nvidia.com/gpu"
              nominalQuota: 8
            - name: "cpu"
              nominalQuota: 96
            - name: "memory"
              nominalQuota: 384Gi
---
apiVersion: kueue.x-k8s.io/v1beta1
kind: LocalQueue
metadata:
  namespace: "gemma-benchmarks"
  name: "llm-sweep-queue"
spec:
  clusterQueue: "gpu-benchmark-cluster-queue"
```

### 5.2 RayCluster Template (`k8s/templates/ray_vllm_cluster_template.yaml`)

Defines the KubeRay `RayCluster` custom resource with configurable head and GPU worker nodes, shared memory mounts (`/dev/shm`), and vLLM CLI arguments.

### 5.3 Batch Evaluation Job Template (`k8s/templates/eval_job_template.yaml`)

Defines the Kubernetes batch `Job` that executes the SOC evaluation suite against the Ray Serve endpoint and persists JSON results to Google Cloud Storage.

---

## 6. End-to-End Execution Workflow

### Step 1: Initialize GKE Cluster & Kueue Queues
```bash
PROJECT_ID="dandye-0324-chronicle"
REGION="us-central1"
CLUSTER_NAME="gemma-eval-cluster"

gcloud container clusters get-credentials "$CLUSTER_NAME" --region="$REGION" --project="$PROJECT_ID"
just gke-ray-init
```

### Step 2: Launch Benchmark Sweep
```bash
# Run a dry run to verify rendered manifests
just gke-ray-sweep "gemma-3-4b-it,gemma-3-12b-it" true

# Execute live sweep on GKE
just gke-ray-sweep "gemma-3-4b-it,gemma-3-12b-it"
```

### Step 3: Monitor Cluster and Queue Status
```bash
just gke-ray-status
```

### Step 4: Tear Down Workloads & Release Nodes
```bash
just gke-ray-cleanup
```
Once all RayClusters and Jobs are deleted, GKE Cluster Autoscaler automatically scales GPU node pools down to 0 nodes within 10-15 minutes, guaranteeing $0.00 idle compute cost.
