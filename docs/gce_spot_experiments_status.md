# Compute Engine (GCE) Ephemeral Spot GPU VM Experiment Status

This document records the operational benchmarks, throughput metrics, hardware sizing, and cost efficiency findings for the 34-model evaluation sweep executed on **Architecture 2: Compute Engine Ephemeral Spot GPU VMs** in `secops-demo-env` (`europe-west4`).

---

## 1. Executive Summary & Key Takeaways

1. **Sub-Minute Boot & Scaling**: Ephemeral Spot GPU VMs acquired compute and mounted Local NVMe SSD scratch drives in under 15 seconds across all single-GPU (`g2-standard-4`, `g2-standard-8`, `g2-standard-16`), 4-GPU (`g2-standard-48`), and dual-A100 (`a2-highgpu-2g`) instances.
2. **Multi-Zone Resilience**: When `europe-west4-a` experienced `ZONE_RESOURCE_POOL_EXHAUSTED` stockout errors for `g2-standard-48` instances during partner model runs, the orchestrator automatically routed requests to `europe-west4-b` without disrupting the sweep.
3. **Guaranteed $0.00 Idle Compute Teardown**: Every VM cleanly executed its self-deletion routine upon evaluation completion or failure via bash exit traps (`gcloud compute instances delete $(hostname) --quiet`), resulting in 0 active instances running after the sweep.
4. **Served Model ID Dynamic Lookup**: In containerized vLLM OpenAI-compatible endpoints, query calls to `/v1/chat/completions` dynamically resolve the exact model identifier from `/v1/models` rather than relying on static generic model names.

---

## 2. Hardware Architecture & Spot Cost Matrix

| Machine Type | GPU Configuration | Spot Price (approx) | On-Demand Price | Target Models |
| :--- | :--- | :--- | :--- | :--- |
| `g2-standard-4` | 1x NVIDIA L4 (24GB) + 1x NVMe SSD | \$0.21 / hr | \$0.70 / hr | Gemma 2 2B, Gemma 3 1B, Gemma 4 E2B |
| `g2-standard-8` | 1x NVIDIA L4 (24GB) + 1x NVMe SSD | \$0.26 / hr | \$0.87 / hr | Gemma 3 4B, Gemma 4 E4B |
| `g2-standard-16` | 1x NVIDIA L4 (24GB) + 1x NVMe SSD | \$0.36 / hr | \$1.21 / hr | Gemma 2 9B |
| `g2-standard-48` | 4x NVIDIA L4 (96GB) + 4x NVMe SSD | \$1.04 / hr | \$3.47 / hr | Gemma 2 27B, Gemma 3 12B, Gemma 3 27B, Qwen 2.5 Coder 32B |
| `a2-highgpu-2g` | 2x NVIDIA A100 (160GB) + 2x NVMe SSD | \$2.45 / hr | \$8.16 / hr | Gemma 4 31B |

---

## 3. Overnight Model Evaluation Results

### 3.1 Gemma 2 Family

| Model Flavor | Machine Type | Speculative / Quant | Generation TPS | Total TPS | Pass Rate | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `gemma-2-2b-it` | `g2-standard-4` | None | 23.68 | 78.40 | 60.0% | Completed & Self-Deleted |
| `gemma-2-2b-it-speculative` | `g2-standard-4` | N-gram Draft | 38.46 | 112.10 | 60.0% | Completed & Self-Deleted |
| `gemma-2-9b-it` | `g2-standard-16` | None | 18.20 | 64.10 | 60.0% | Completed & Self-Deleted |
| `gemma-2-9b-it-fp8` | `g2-standard-16` | FP8 | 27.50 | 88.30 | 60.0% | Completed & Self-Deleted |
| `gemma-2-9b-it-speculative` | `g2-standard-16` | FP8 + N-gram | 36.10 | 104.50 | 60.0% | Completed & Self-Deleted |
| `gemma-2-27b-it` | `g2-standard-48` | TP=4 | 14.80 | 52.00 | 60.0% | Completed & Self-Deleted |
| `gemma-2-27b-it-fp8` | `g2-standard-48` | FP8 (TP=4) | 22.40 | 76.80 | 60.0% | Completed & Self-Deleted |
| `gemma-2-27b-it-speculative` | `g2-standard-48` | FP8 + N-gram (TP=4) | 29.80 | 92.40 | 60.0% | Completed & Self-Deleted |

### 3.2 Gemma 3 Family

| Model Flavor | Machine Type | Speculative / Quant | Generation TPS | Total TPS | Pass Rate | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `gemma-3-1b-it` | `g2-standard-4` | None | 48.54 | 142.60 | 40.0% | Completed & Self-Deleted |
| `gemma-3-1b-it-speculative` | `g2-standard-4` | N-gram Draft | 76.86 | 198.40 | 40.0% | Completed & Self-Deleted |
| `gemma-3-4b-it` | `g2-standard-8` | None | 24.10 | 82.40 | 80.0% | Completed & Self-Deleted |
| `gemma-3-4b-it-speculative` | `g2-standard-8` | N-gram Draft | 39.50 | 118.90 | 80.0% | Completed & Self-Deleted |
| `gemma-3-12b-it` | `g2-standard-48` | TP=4 | 19.30 | 68.20 | 60.0% | Completed & Self-Deleted |
| `gemma-3-12b-it-fp8` | `g2-standard-48` | FP8 (TP=4) | 61.76 | 184.20 | 60.0% | Completed & Self-Deleted |
| `gemma-3-12b-it-speculative` | `g2-standard-48` | FP8 + N-gram (TP=4) | 74.20 | 215.00 | 60.0% | Completed & Self-Deleted |
| `gemma-3-27b-it` | `g2-standard-48` | TP=4 | 16.20 | 58.40 | 60.0% | Completed & Self-Deleted |
| `gemma-3-27b-it-fp8` | `g2-standard-48` | FP8 (TP=4) | 28.00 | 96.20 | 60.0% | Completed & Self-Deleted |
| `gemma-3-27b-it-speculative` | `g2-standard-48` | FP8 + N-gram (TP=4) | 36.40 | 120.50 | 60.0% | Completed & Self-Deleted |
| `gemma-3-27b-it-caching` | `g2-standard-48` | FP8 + Prefix Caching | 31.20 | 108.00 | 60.0% | Completed & Self-Deleted |

### 3.3 Gemma 4 Family

| Model Flavor | Machine Type | Speculative / Quant | Generation TPS | Total TPS | Pass Rate | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `gemma-4-e2b-it` | `g2-standard-4` | None | 25.04 | 86.10 | 40.0% | Completed & Self-Deleted |
| `gemma-4-e2b-it-speculative` | `g2-standard-4` | N-gram Draft | 49.12 | 148.30 | 60.0% | Completed & Self-Deleted |
| `gemma-4-e4b-it` | `g2-standard-8` | None | 21.80 | 74.50 | 60.0% | Completed & Self-Deleted |
| `gemma-4-e4b-it-speculative` | `g2-standard-8` | N-gram Draft | 42.10 | 132.00 | 60.0% | Completed & Self-Deleted |
| `gemma-4-31b-it` | `a2-highgpu-2g` | TP=2 (2x A100) | 32.50 | 110.20 | 80.0% | Completed & Self-Deleted |
| `gemma-4-31b-it-speculative` | `a2-highgpu-2g` | N-gram Draft (2x A100) | 51.62 | 165.40 | 80.0% | Completed & Self-Deleted |

### 3.4 Partner & Open Models

| Model Flavor | Machine Type | Accelerator | Generation TPS | Pass Rate | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `inkling-small` | `g2-standard-48` | 4x NVIDIA L4 | 51.22 | 60.0% | Completed & Self-Deleted (europe-west4-b) |
| `qwen2.5-coder-32b-instruct` | `g2-standard-48` | 4x NVIDIA L4 | 28.40 | 80.0% | Completed & Self-Deleted (europe-west4-a) |

---

## 4. Operational Recommendations

1. **Local NVMe SSD Scratch**: Always attach Local NVMe SSD scratch drives (`--local-ssd=interface=NVME`) and mount to `/mnt/disks/nvme` to eliminate persistent disk I/O bottlenecks during container image layer unpacking and HF weight downloads.
2. **Multi-Zone Retries**: In GPU-constrained regions, enable zonal failover across `europe-west4-a`, `europe-west4-b`, and `europe-west4-c` to maintain continuous sweep execution during spot stockouts.
3. **Pre-Compiled GPU Drivers**: Install kernel-matched binary drivers (`linux-modules-nvidia-535-server-$(uname -r)`) to avoid GCC kernel header compilation delays during instance boot.
