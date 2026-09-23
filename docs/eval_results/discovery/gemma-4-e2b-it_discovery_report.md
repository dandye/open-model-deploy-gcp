# Empirical Evaluation: Two-Stage Skill Discovery & Prior Correction

- **Model Under Test:** `gemma-4-e2b-it`
- **Benchmark Suite:** `evals.json` (12 scenarios)
- **Judge Model:** `vertex_ai/gemini-2.5-flash`
- **Date:** 2026-09-23 01:19:26 UTC

## 1. Executive Summary Scorecard

| Evaluation Stage | Metric | Score | Finding |
| :--- | :--- | :---: | :--- |
| **Stage 1: Autonomous Discovery** | Tool Trigger Rate | **16.7%** | Recognized need to query catalog |
| | Exact Skill Routing | **16.7%** | Identified canonical target skill |
| | Acceptable Skill Routing | **16.7%** | Loaded valid/acceptable domain skill |
| **Stage 2: Cognitive Prior Correction** | Baseline Pass Rate | **8.3%** | Without skills |
| | With-Skill Pass Rate | **41.7%** | Conditioned on retrieved skill |
| | **Net Pass Rate Lift (Δ)** | **+33.3%** | Measurable capability improvement |
| | Assertion Match Lift | **5 -> 20** (+31.2%) | Specific syntax & rule adherence |

## 2. Scenario-by-Scenario Discovery & Execution Breakdown

| ID | Expected Skill | Agent Selected Skill | Discovery Status | Baseline Match | With-Skill Match | Net Lift (Δ) |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| `gdo-001-cloudrun-gpu-l4-scale-to-zero` | `cloudrun-deploy` | `NONE` | `MISSED` | 0/4 | **0/4** | **+0** |
| `gdo-002-vertex-speculative-decoding-ngram` | `vertex-prediction` | `NONE` | `MISSED` | 0/4 | **0/4** | **+0** |
| `gdo-003-server-side-disk-audit` | `gcloud` | `NONE` | `MISSED` | 1/4 | **4/4** | **+3** |
| `gdo-004-cross-project-secret-iam` | `gcp-auth` | `NONE` | `MISSED` | 0/4 | **4/4** | **+4** |
| `gdo-005-destructive-teardown-safety-gate` | `cloud-safety` | `NONE` | `MISSED` | 4/4 | **4/4** | **+0** |
| `gdo-006-gce-spot-vm-auto-deletion` | `gce-spot` | `gce-spot` | `EXACT` | 0/4 | **0/4** | **+0** |
| `gdo-007-vertex-container-swap-space` | `vertex-prediction` | `NONE` | `MISSED` | 0/4 | **1/4** | **+1** |
| `gdo-008-cloudrun-gpu-quota-lifecycle` | `cloudrun-quota` | `cloudrun-quota` | `EXACT` | 0/4 | **0/4** | **+0** |
| `gdo-009-adk-agent-endpoint-discovery` | `agent-engine` | `NONE` | `MISSED` | 0/4 | **0/4** | **+0** |
| `gdo-010-soc-containment-vs-escalation` | `secops-triage` | `NONE` | `MISSED` | 0/4 | **4/4** | **+4** |
| `gdo-011-adc-vs-service-account-keys` | `gcp-auth` | `NONE` | `MISSED` | 0/4 | **3/4** | **+3** |
| `gdo-012-model-catalog-sizing-parity` | `model-catalog` | `NONE` | `MISSED` | 0/4 | **0/4** | **+0** |
