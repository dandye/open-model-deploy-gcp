---
title: "Benchmarking Gemma & Open Models on GCE Ephemeral Spot GPU VMs"
description: "Architecture, automation recipes, and operational guide for running cost-optimized LLM benchmark sweeps on Compute Engine Ephemeral Spot GPU VMs with Local NVMe SSD caching and zero idle cost leaks."
type: "guide"
tags:
  - gemma
  - compute-engine
  - spot-vms
  - vllm
  - benchmarks
  - cost-optimization
  - nvidia-l4
  - nvidia-a100
created: 2026-08-30
updated: 2026-08-30
---

# Benchmarking Gemma & Open Models on GCE Ephemeral Spot GPU VMs

This guide documents the architecture, automation tooling, and operational workflows for executing large-scale, cost-optimized LLM evaluation and benchmark sweeps using Google Compute Engine (GCE) Ephemeral Spot GPU Virtual Machines.

---

## 1. Executive Summary & Cost Economics

Dedicated cloud endpoints (such as Vertex AI Online Prediction) provide persistent availability for interactive serving but incur continuous hourly GPU billing even during idle periods. When conducting large batch benchmark sweeps across dozens of model architectures and quantization variants, dedicated endpoints represent significant unnecessary cost overhead.

By utilizing **Compute Engine Ephemeral Spot GPU VMs** combined with attached **Local NVMe SSD scratch drives** and **programmatic self-deletion**, this architecture delivers:

* **60% to 80% Cost Reduction**: Spot GPU instances leverage excess Compute Engine capacity at steep discounts (e.g. ~\$0.21/hr for 1x L4 Spot vs. ~\$0.70/hr on-demand; ~\$1.00/hr for 4x L4 Spot vs. ~\$3.36/hr on-demand).
* **Extreme Disk I/O**: Local NVMe SSDs provide ultra-high read/write throughput (GB/s), minimizing model weight caching and container startup latency.
* **Guaranteed Zero Idle Billing ($0.00 Leakage)**: Each virtual machine runs a self-terminating startup script configured with bash exit/signal traps that immediately issues a self-deletion call (`gcloud compute instances delete`) upon evaluation completion or failure.

---

## 2. Architecture & Lifecycle Overview

The ephemeral benchmarking lifecycle follows a strict six-stage pipeline:

```
+-------------------------------------------------------------------------+
|                      Ephemeral Spot VM Lifecycle                        |
+-------------------------------------------------------------------------+
|                                                                         |
|  [1. Orchestration]                                                     |
|      GCESpotOrchestrator generates gcloud instance creation command     |
|      with Spot provisioning, Local NVMe SSD, and custom metadata.       |
|                             |                                           |
|                             v                                           |
|  [2. VM Provisioning & Storage Mount]                                   |
|      GCE provisions VM; startup script formats & mounts Local NVMe SSD  |
|      to /mnt/disks/nvme and initializes HF_HOME cache directory.        |
|                             |                                           |
|                             v                                           |
|  [3. Model Weight Sync & vLLM Container Launch]                         |
|      Model weights downloaded from GCS / HuggingFace; Docker launches   |
|      vLLM OpenAI server (vllm/vllm-openai:latest) on port 8080.         |
|                             |                                           |
|                             v                                           |
|  [4. Evaluation & Benchmarking Execution]                                |
|      Startup script polls health endpoint, executes SOC Tier 1 eval     |
|      suite (eval_soc_agent.py) and latency/throughput benchmark suite.  |
|                             |                                           |
|                             v                                           |
|  [5. Artifact Synchronization to GCS]                                   |
|      Evaluation scorecards, latency percentiles, and JSON logs synced   |
|      to gs://<output-bucket>/<model_flavor>/.                           |
|                             |                                           |
|                             v                                           |
|  [6. Guaranteed Self-Deletion ($0.00 Idle Cost)]                        |
|      Bash trap triggers gcloud compute instances delete $(hostname).    |
|      VM is permanently deleted, ending all compute and disk billing.    |
|                                                                         |
+-------------------------------------------------------------------------+
```

---

## 3. Justfile Recipes & Commands

All operations are integrated into the repository's `Justfile` under the `COMPUTE ENGINE SPOT GPU VMS` category.

### 3.1 Run Single Model Benchmark (`gce-spot-run`)

Launch an ephemeral Spot GPU VM for a single model flavor:

```bash
# Run Gemma 3 4B on 1x L4 Spot VM
just gce-spot-run "gemma-3-4b-it"

# Run Gemma 3 27B on 4x L4 Spot VM
just gce-spot-run "gemma-3-27b-it"

# Dry-run validation (prints gcloud command without provisioning resources)
just gce-spot-run "gemma-2-9b-it" "true"
```

### 3.2 Run Batch Evaluation Sweep (`gce-spot-sweep`)

Execute an automated sweep across multiple model flavors or the full model catalog:

```bash
# Run filtered sweep across selected Gemma flavors
just gce-spot-sweep "gemma-2-2b-it,gemma-3-4b-it,gemma-3-12b-it"

# Run full catalog sweep across all supported models
just gce-spot-sweep

# Dry-run sweep simulation
just gce-spot-sweep "" "true"
```

### 3.3 Check Active Spot Instances (`gce-spot-status`)

Inspect currently running Spot GPU instances in the active project and zone:

```bash
# List all active Spot VMs across all zones
just gce-spot-status

# List active Spot VMs in a specific zone
just gce-spot-status "us-central1-a"
```

### 3.4 Force Cleanup Lingering Benchmark VMs (`gce-spot-cleanup`)

Safely terminate and delete any remaining ephemeral benchmark instances matching `name:(spot-* OR gemma-spot-*)`:

```bash
# Clean up lingering instances in default configured zone
just gce-spot-cleanup

# Clean up lingering instances in a specific zone
just gce-spot-cleanup "us-central1-a"
```

---

## 4. CLI Orchestrator Reference (`scripts/run_gce_spot_sweep.py`)

For advanced scripting, CI/CD pipelines, or custom parameters, invoke the Python orchestrator directly:

```bash
uv run python3 scripts/run_gce_spot_sweep.py [OPTIONS]
```

### CLI Arguments

| Argument | Environment Variable | Default | Description |
| :--- | :--- | :--- | :--- |
| `--models` | - | `None` (all) | Comma-separated list of model flavors to evaluate |
| `--project-id` | `GCP_PROJECT_ID` | `dandye-0324-chronicle` | Google Cloud Project ID |
| `--zone` | `GCP_ZONE` | `us-central1-a` | Target Compute Engine zone for Spot provisioning |
| `--output-gcs-bucket` | `GCE_SPOT_OUTPUT_BUCKET` | `gs://dandye-0324-chronicle-evals/gce_spot_sweeps` | Cloud Storage bucket for reports and logs |
| `--hf-token` | `HF_TOKEN` | `None` | Hugging Face API token for gated model weights |
| `--dry-run` | - | `False` | Simulate commands without creating cloud resources |
| `--no-wait` | - | `False` | Launch instances asynchronously without waiting |
| `--timeout-seconds` | - | `3600` | Maximum timeout in seconds per Spot VM |

---

## 5. Hardware Sizing & Spot Pricing Matrix

| Model Flavor | Machine Type | GPU Accelerator | Local NVMe SSD | Spot Price/hr (Est.) | On-Demand/hr (Est.) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `gemma-2-2b-it` | `g2-standard-4` | 1x NVIDIA L4 (24GB) | 1x 375GB NVMe | ~$0.21/hr | ~$0.70/hr |
| `gemma-3-1b-it` | `g2-standard-4` | 1x NVIDIA L4 (24GB) | 1x 375GB NVMe | ~$0.21/hr | ~$0.70/hr |
| `gemma-3-4b-it` | `g2-standard-8` | 1x NVIDIA L4 (24GB) | 1x 375GB NVMe | ~$0.26/hr | ~$0.85/hr |
| `gemma-2-9b-it` | `g2-standard-16` | 1x NVIDIA L4 (24GB) | 1x 375GB NVMe | ~$0.36/hr | ~$1.15/hr |
| `gemma-3-12b-it` | `g2-standard-16` | 1x NVIDIA L4 (24GB) | 1x 375GB NVMe | ~$0.36/hr | ~$1.15/hr |
| `gemma-2-27b-it` | `g2-standard-48` | 4x NVIDIA L4 (96GB) | 4x 375GB NVMe | ~$1.05/hr | ~$3.36/hr |
| `gemma-3-27b-it` | `g2-standard-48` | 4x NVIDIA L4 (96GB) | 4x 375GB NVMe | ~$1.05/hr | ~$3.36/hr |
| `gemma-4-31b-it` | `g2-standard-48` | 4x NVIDIA L4 (96GB) | 4x 375GB NVMe | ~$1.05/hr | ~$3.36/hr |
| `llama-3.1-nemotron-70b` | `a2-highgpu-2g` | 2x NVIDIA A100 (80GB) | 2x 375GB NVMe | ~$1.95/hr | ~$7.35/hr |

---

## 6. Failure Recovery & Safety Mechanisms

1. **Bash Exit & Signal Traps**: The startup script attaches cleanup routines to `EXIT`, `ERR`, `INT`, and `TERM` signals. Even if vLLM fails to start or an evaluation script encounters an exception, `gcloud compute instances delete` executes unconditionally.
2. **Instance Termination Action**: Instances are created with `--instance-termination-action=DELETE` and `--maintenance-policy=TERMINATE` so that Spot preemptions cleanly trigger deletion rather than entering a suspended or stopped state.
3. **Serial Console Streaming**: The orchestrator streams serial port logs (`gcloud compute instances get-serial-port-output`) in real time, capturing diagnostics immediately even if the instance is preempted.
4. **Manual Recovery**: If an instance fails to terminate due to network partition or permissions issues, running `just gce-spot-cleanup` terminates all instances matching `name:(spot-* OR gemma-spot-*)`.
