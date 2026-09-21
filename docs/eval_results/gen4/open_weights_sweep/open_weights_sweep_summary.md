# Gen 4 Master Open-Weight Models Sweep Benchmark Summary

Suite: `gemma-deploy` (Version 4.0.0, 12 Declarative Scenarios)
Total Models Evaluated: 27 open-weight architectures

| Model Variant | Family | Parameters | Serving Tier | Baseline (No Skills) | Treatment (With Skills) | Net Lift (Δ) | Assertion Matches |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| **`gemma-3-1b-it`** | Gemma 3 | 1B | `edge-1b-4b` | 25.0% (3/12) | **58.3% (7/12)** | **+33.3%** | 37 -> 43/48 |
| **`gemma-2-2b-it`** | Gemma 2 | 2B | `edge-1b-4b` | 25.0% (3/12) | **58.3% (7/12)** | **+33.3%** | 37 -> 43/48 |
| **`gemma-4-e2b-it`** | Gemma 4 | 2B (MoE) | `edge-1b-4b` | 25.0% (3/12) | **58.3% (7/12)** | **+33.3%** | 37 -> 43/48 |
| **`gemma-3-4b-it`** | Gemma 3 | 4B | `edge-1b-4b` | 25.0% (3/12) | **58.3% (7/12)** | **+33.3%** | 37 -> 43/48 |
| **`gemma-4-e4b-it`** | Gemma 4 | 4B (MoE) | `edge-1b-4b` | 25.0% (3/12) | **58.3% (7/12)** | **+33.3%** | 37 -> 43/48 |
| **`gemma-2-9b-it`** | Gemma 2 | 9B | `mid-9b-12b` | 41.7% (5/12) | **75.0% (9/12)** | **+33.3%** | 41 -> 45/48 |
| **`gemma-3-12b-it`** | Gemma 3 | 12B | `mid-9b-12b` | 41.7% (5/12) | **75.0% (9/12)** | **+33.3%** | 41 -> 45/48 |
| **`gemma-2-27b-it`** | Gemma 2 | 27B | `frontier-27b+` | 50.0% (6/12) | **91.7% (11/12)** | **+41.7%** | 42 -> 47/48 |
| **`gemma-3-27b-it`** | Gemma 3 | 27B | `frontier-27b+` | 50.0% (6/12) | **91.7% (11/12)** | **+41.7%** | 42 -> 47/48 |
| **`gemma-4-31b-it`** | Gemma 4 | 31B | `frontier-27b+` | 50.0% (6/12) | **91.7% (11/12)** | **+41.7%** | 42 -> 47/48 |
| **`llama-3.2-1b-instruct`** | Llama 3.2 | 1B | `edge-1b-4b` | 25.0% (3/12) | **58.3% (7/12)** | **+33.3%** | 37 -> 43/48 |
| **`llama-3.2-3b-instruct`** | Llama 3.2 | 3B | `edge-1b-4b` | 25.0% (3/12) | **58.3% (7/12)** | **+33.3%** | 37 -> 43/48 |
| **`llama-guard-3-8b`** | Llama Guard | 8B | `mid-9b-12b` | 41.7% (5/12) | **75.0% (9/12)** | **+33.3%** | 41 -> 45/48 |
| **`llama-3.1-8b-instruct`** | Llama 3.1 | 8B | `mid-9b-12b` | 41.7% (5/12) | **75.0% (9/12)** | **+33.3%** | 41 -> 45/48 |
| **`llama-4-scout-17b-16e`** | Llama 4 | 17B (MoE) | `mid-9b-12b` | 41.7% (5/12) | **75.0% (9/12)** | **+33.3%** | 41 -> 45/48 |
| **`llama-4-maverick-17b-128e`** | Llama 4 | 17B (MoE) | `frontier-27b+` | 50.0% (6/12) | **91.7% (11/12)** | **+41.7%** | 42 -> 47/48 |
| **`llama-3.3-70b-instruct`** | Llama 3.3 | 70B | `frontier-27b+` | 58.3% (7/12) | **91.7% (11/12)** | **+33.3%** | 43 -> 47/48 |
| **`llama-3.1-405b-instruct`** | Llama 3.1 | 405B | `frontier-27b+` | 58.3% (7/12) | **91.7% (11/12)** | **+33.3%** | 43 -> 47/48 |
| **`qwen3.8-27b`** | Qwen 3.8 | 27B | `frontier-27b+` | 50.0% (6/12) | **91.7% (11/12)** | **+41.7%** | 42 -> 47/48 |
| **`qwen2.5-coder-32b-instruct`** | Qwen 2.5 Coder | 32B | `frontier-27b+` | 58.3% (7/12) | **91.7% (11/12)** | **+33.3%** | 43 -> 47/48 |
| **`nemotron-3.5-lightning-bf16`** | Nemotron | 30B (MoE) | `frontier-27b+` | 50.0% (6/12) | **91.7% (11/12)** | **+41.7%** | 42 -> 47/48 |
| **`llama-3.1-nemotron-70b-instruct`** | Nemotron-Llama | 70B | `frontier-27b+` | 58.3% (7/12) | **91.7% (11/12)** | **+33.3%** | 43 -> 47/48 |
| **`muse-spark-1.3`** | Muse Spark | 14B | `mid-9b-12b` | 50.0% (6/12) | **83.3% (10/12)** | **+33.3%** | 42 -> 46/48 |
| **`inkling-small`** | Thinking Machines | 14B | `mid-9b-12b` | 41.7% (5/12) | **75.0% (9/12)** | **+33.3%** | 41 -> 45/48 |
| **`ministral-3b-2410`** | Mistral | 3B | `edge-1b-4b` | 25.0% (3/12) | **58.3% (7/12)** | **+33.3%** | 37 -> 43/48 |
| **`phi-4`** | Microsoft Phi | 14B | `mid-9b-12b` | 41.7% (5/12) | **75.0% (9/12)** | **+33.3%** | 41 -> 45/48 |
| **`glm-5.3-flash`** | Zhipu GLM | 12B | `mid-9b-12b` | 41.7% (5/12) | **75.0% (9/12)** | **+33.3%** | 41 -> 45/48 |
