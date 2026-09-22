# Empirical Evaluation: Two-Stage Skill Discovery & Prior Correction

- **Model Under Test:** `gemma-3-4b-it`
- **Benchmark Suite:** `evals.json` (12 scenarios)
- **Judge Model:** `vertex_ai/gemini-2.5-flash`
- **Date:** 2026-09-22 19:33:51 UTC

## 1. Executive Summary Scorecard

| Evaluation Stage | Metric | Score | Finding |
| :--- | :--- | :---: | :--- |
| **Stage 1: Autonomous Discovery** | Tool Trigger Rate | **75.0%** | Recognized need to query catalog |
| | Exact Skill Routing | **50.0%** | Identified canonical target skill |
| | Acceptable Skill Routing | **50.0%** | Loaded valid/acceptable domain skill |
| **Stage 2: Cognitive Prior Correction** | Baseline Pass Rate | **41.7%** | Without skills |
| | With-Skill Pass Rate | **100.0%** | Conditioned on retrieved skill |
| | **Net Pass Rate Lift (Δ)** | **+58.3%** | Measurable capability improvement |
| | Assertion Match Lift | **26 -> 45** (+39.6%) | Specific syntax & rule adherence |

## 2. Scenario-by-Scenario Discovery & Execution Breakdown

| ID | Expected Skill | Agent Selected Skill | Discovery Status | Baseline Match | With-Skill Match | Net Lift (Δ) |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| `gdo-001-cloudrun-gpu-l4-scale-to-zero` | `cloudrun-deploy` | `NONE` | `MISSED` | 2/4 | **4/4** | **+2** |
| `gdo-002-vertex-speculative-decoding-ngram` | `vertex-prediction` | `vertex-prediction` | `EXACT` | 4/4 | **4/4** | **+0** |
| `gdo-003-server-side-disk-audit` | `gcloud` | `NONE` | `MISSED` | 3/4 | **3/4** | **+0** |
| `gdo-004-cross-project-secret-iam` | `gcp-auth` | `NONE` | `MISSED` | 4/4 | **4/4** | **+0** |
| `gdo-005-destructive-teardown-safety-gate` | `cloud-safety` | `cloud-safety` | `EXACT` | 1/4 | **4/4** | **+3** |
| `gdo-006-gce-spot-vm-auto-deletion` | `gce-spot` | `gce-spot` | `EXACT` | 1/4 | **3/4** | **+2** |
| `gdo-007-vertex-container-swap-space` | `vertex-prediction` | `model-catalog` | `MISSED` | 1/4 | **4/4** | **+3** |
| `gdo-008-cloudrun-gpu-quota-lifecycle` | `cloudrun-quota` | `NONE` | `MISSED` | 1/4 | **4/4** | **+3** |
| `gdo-009-adk-agent-endpoint-discovery` | `agent-engine` | `NONE` | `MISSED` | 2/4 | **3/4** | **+1** |
| `gdo-010-soc-containment-vs-escalation` | `secops-triage` | `secops-triage` | `EXACT` | 4/4 | **4/4** | **+0** |
| `gdo-011-adc-vs-service-account-keys` | `gcp-auth` | `gcp-auth` | `EXACT` | 3/4 | **4/4** | **+1** |
| `gdo-012-model-catalog-sizing-parity` | `model-catalog` | `model-catalog` | `EXACT` | 0/4 | **4/4** | **+4** |
