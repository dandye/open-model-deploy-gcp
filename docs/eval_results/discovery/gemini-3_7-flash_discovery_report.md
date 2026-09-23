# Empirical Evaluation: Two-Stage Skill Discovery & Prior Correction

- **Model Under Test:** `gemini-3.7-flash`
- **Benchmark Suite:** `evals.json` (12 scenarios)
- **Judge Model:** `vertex_ai/gemini-2.5-flash`
- **Date:** 2026-09-23 13:27:33 UTC

## 1. Executive Summary Scorecard

| Evaluation Stage | Metric | Score | Finding |
| :--- | :--- | :---: | :--- |
| **Stage 1: Autonomous Discovery** | Tool Trigger Rate | **91.7%** | Recognized need to query catalog |
| | Exact Skill Routing | **91.7%** | Identified canonical target skill |
| | Acceptable Skill Routing | **91.7%** | Loaded valid/acceptable domain skill |
| **Stage 2: Cognitive Prior Correction** | Baseline Pass Rate | **83.3%** | Without skills |
| | With-Skill Pass Rate | **100.0%** | Conditioned on retrieved skill |
| | **Net Pass Rate Lift (Δ)** | **+16.7%** | Measurable capability improvement |
| | Assertion Match Lift | **37 -> 48** (+22.9%) | Specific syntax & rule adherence |

## 2. Scenario-by-Scenario Discovery & Execution Breakdown

| ID | Expected Skill | Agent Selected Skill | Discovery Status | Baseline Match | With-Skill Match | Net Lift (Δ) |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| `gdo-001-cloudrun-gpu-l4-scale-to-zero` | `cloudrun-deploy` | `cloudrun-deploy` | `EXACT` | 3/4 | **4/4** | **+1** |
| `gdo-002-vertex-speculative-decoding-ngram` | `vertex-prediction` | `vertex-prediction` | `EXACT` | 2/4 | **4/4** | **+2** |
| `gdo-003-server-side-disk-audit` | `gcloud` | `gcloud` | `EXACT` | 4/4 | **4/4** | **+0** |
| `gdo-004-cross-project-secret-iam` | `gcp-auth` | `NONE` | `MISSED` | 4/4 | **4/4** | **+0** |
| `gdo-005-destructive-teardown-safety-gate` | `cloud-safety` | `cloud-safety` | `EXACT` | 3/4 | **4/4** | **+1** |
| `gdo-006-gce-spot-vm-auto-deletion` | `gce-spot` | `gce-spot` | `EXACT` | 3/4 | **4/4** | **+1** |
| `gdo-007-vertex-container-swap-space` | `vertex-prediction` | `vertex-prediction` | `EXACT` | 2/4 | **4/4** | **+2** |
| `gdo-008-cloudrun-gpu-quota-lifecycle` | `cloudrun-quota` | `cloudrun-quota` | `EXACT` | 3/4 | **4/4** | **+1** |
| `gdo-009-adk-agent-endpoint-discovery` | `agent-engine` | `agent-engine` | `EXACT` | 3/4 | **4/4** | **+1** |
| `gdo-010-soc-containment-vs-escalation` | `secops-triage` | `secops-triage` | `EXACT` | 3/4 | **4/4** | **+1** |
| `gdo-011-adc-vs-service-account-keys` | `gcp-auth` | `gcp-auth` | `EXACT` | 3/4 | **4/4** | **+1** |
| `gdo-012-model-catalog-sizing-parity` | `model-catalog` | `model-catalog` | `EXACT` | 4/4 | **4/4** | **+0** |
