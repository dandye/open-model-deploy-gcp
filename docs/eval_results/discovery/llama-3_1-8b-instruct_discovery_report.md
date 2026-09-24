# Empirical Evaluation: Two-Stage Skill Discovery & Prior Correction

- **Model Under Test:** `llama-3.1-8b-instruct`
- **Benchmark Suite:** `evals.json` (12 scenarios)
- **Judge Model:** `vertex_ai/gemini-2.5-flash`
- **Date:** 2026-09-24 19:31:44 UTC

## 1. Executive Summary Scorecard

| Evaluation Stage | Metric | Score | Finding |
| :--- | :--- | :---: | :--- |
| **Stage 1: Autonomous Discovery** | Tool Trigger Rate | **100.0%** | Recognized need to query catalog |
| | Exact Skill Routing | **16.7%** | Identified canonical target skill |
| | Acceptable Skill Routing | **16.7%** | Loaded valid/acceptable domain skill |
| **Stage 2: Cognitive Prior Correction** | Baseline Pass Rate | **25.0%** | Without skills |
| | With-Skill Pass Rate | **83.3%** | Conditioned on retrieved skill |
| | **Net Pass Rate Lift (Δ)** | **+58.3%** | Measurable capability improvement |
| | Assertion Match Lift | **18 -> 42** (+50.0%) | Specific syntax & rule adherence |

## 2. Scenario-by-Scenario Discovery & Execution Breakdown

| ID | Expected Skill | Agent Selected Skill | Discovery Status | Baseline Match | With-Skill Match | Net Lift (Δ) |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| `gdo-001-cloudrun-gpu-l4-scale-to-zero` | `cloudrun-deploy` | `cloudrun-deploy` | `EXACT` | 1/4 | **4/4** | **+3** |
| `gdo-002-vertex-speculative-decoding-ngram` | `vertex-prediction` | `NONE` | `MISSED` | 0/4 | **4/4** | **+4** |
| `gdo-003-server-side-disk-audit` | `gcloud` | `NONE` | `MISSED` | 3/4 | **3/4** | **+0** |
| `gdo-004-cross-project-secret-iam` | `gcp-auth` | `gcp-auth` | `EXACT` | 1/4 | **4/4** | **+3** |
| `gdo-005-destructive-teardown-safety-gate` | `cloud-safety` | `NONE` | `MISSED` | 2/4 | **4/4** | **+2** |
| `gdo-006-gce-spot-vm-auto-deletion` | `gce-spot` | `NONE` | `MISSED` | 2/4 | **4/4** | **+2** |
| `gdo-007-vertex-container-swap-space` | `vertex-prediction` | `NONE` | `MISSED` | 3/4 | **3/4** | **+0** |
| `gdo-008-cloudrun-gpu-quota-lifecycle` | `cloudrun-quota` | `NONE` | `MISSED` | 0/4 | **4/4** | **+4** |
| `gdo-009-adk-agent-endpoint-discovery` | `agent-engine` | `NONE` | `MISSED` | 2/4 | **2/4** | **+0** |
| `gdo-010-soc-containment-vs-escalation` | `secops-triage` | `NONE` | `MISSED` | 3/4 | **4/4** | **+1** |
| `gdo-011-adc-vs-service-account-keys` | `gcp-auth` | `NONE` | `MISSED` | 1/4 | **4/4** | **+3** |
| `gdo-012-model-catalog-sizing-parity` | `model-catalog` | `NONE` | `MISSED` | 0/4 | **2/4** | **+2** |
