---
name: vertex-prediction
description: Guidelines for deploying models, configuring speculative decoding, and sizing Model Garden containers on Vertex AI prediction endpoints.
---

# Vertex AI Model Prediction & Inference Optimization

## Core Operational Rules
1. **Speculative Decoding (N-gram Prompt Lookup):**
   - For vLLM inference acceleration without secondary models, configure:
     `--speculative-model=[ngram] --num-speculative-tokens=5 --ngram-prompt-lookup-max=5 --ngram-prompt-lookup-min=2`.
   - Explicitly note that N-gram prompt lookup requires zero additional GPU VRAM because it does not load separate draft model weights.
   - Yields 1.5x to 2.3x throughput acceleration.
2. **Container Swap Space & Host Memory Sizing:**
   - When deploying custom Google Model Garden vLLM containers, set `--swap-space` appropriately:
     - `g2-standard-4` / `g2-standard-8` (<=32GB RAM): `swap-space: 8`
     - `g2-standard-12` (48GB RAM): `swap-space: 16`
     - `g2-standard-48` (192GB RAM): `swap-space: 32`
   - Excessive swap space triggers `ValueError: Too large swap space` container crashes.
3. **Accelerator Count Mappings:**
   - `g2-standard-4`, `g2-standard-8`, `g2-standard-12`, `g2-standard-16`: Exactly 1x L4 (`count=1`).
   - `g2-standard-48`: Exactly 4x L4 (`count=4`).
4. **Container Entrypoint Preservation:**
   - Never override Google Model Garden entrypoint commands; allow the container wrapper to download GCS weights locally before launching vLLM.
