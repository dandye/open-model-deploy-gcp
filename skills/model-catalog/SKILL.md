---
name: model-catalog
description: Authoritative compute, hardware sizing, VRAM, and quantization bounds from configs/models.json.
---

# Model Catalog Sizing & Quantization Reference

## Core Operational Rules
1. **Centralized Single Source of Truth:**
   - Consult `configs/models.json` for all compute, accelerator, and serving parameters.
2. **Single-GPU vs Multi-GPU Boundaries:**
   - Single-GPU (1x L4, `g2-standard-4`/`g2-standard-8`): Gemma 2 2B, Gemma 2 9B, Gemma 3 1B, Gemma 3 4B, Gemma 4 E2B, Gemma 4 E4B.
   - Multi-GPU (4x L4, `g2-standard-48`): Gemma 3 12B, Gemma 3 27B.
   - Multi-GPU (2x A100 / 8x L4): Gemma 4 31B.
3. **Quantization Bounds:**
   - FP8 quantization fits Gemma 3 27B and Gemma 4 31B comfortably within limited VRAM bounds (~30GB) while maintaining high inference quality.
