# Empirical Evaluation: Two-Stage Skill Discovery & Prior Correction

- **Model Under Test:** `vertex_ai/gemini-2.5-flash`
- **Benchmark Suite:** `evals.json` (12 scenarios)
- **Judge Model:** `vertex_ai/gemini-2.5-flash`
- **Date:** 2026-09-22 17:31:42 UTC

## 1. Executive Summary Scorecard

| Evaluation Stage | Metric | Score | Finding |
| :--- | :--- | :---: | :--- |
| **Stage 1: Autonomous Discovery** | Tool Trigger Rate | **91.7%** | Recognized need to query catalog |
| | Exact Skill Routing | **25.0%** | Identified canonical target skill |
| | Acceptable Skill Routing | **41.7%** | Loaded valid/acceptable domain skill |
| **Stage 2: Cognitive Prior Correction** | Baseline Pass Rate | **33.3%** | Without skills |
| | With-Skill Pass Rate | **66.7%** | Conditioned on retrieved skill |
| | **Net Pass Rate Lift (Δ)** | **+33.3%** | Measurable capability improvement |
| | Assertion Match Lift | **24 -> 28** (+11.1%) | Specific syntax & rule adherence |

## 2. Scenario-by-Scenario Discovery & Execution Breakdown

| ID | Expected Skill | Agent Selected Skill | Discovery Status | Baseline Match | With-Skill Match | Net Lift (Δ) |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| `gcd-001-explicit-auth` | `google-cloud-recipe-auth` | `gcloud` | `ACCEPTABLE` | 2/4 | **1/4** | **-1** |
| `gcd-002-cloudrun-storage` | `gcloud` | `cloudrun-deploy` | `MISSED` | 1/3 | **2/3** | **+1** |
| `gcd-003-gcloud-noninteractive` | `gcloud` | `gcloud` | `EXACT` | 1/3 | **3/3** | **+2** |
| `gcd-004-batch-timeout-limits` | `retrieving-developer-knowledge` | `google-cloud-developer` | `MISSED` | 2/3 | **3/3** | **+1** |
| `gcd-005-catalog-skill-discovery` | `finding-google-skills` | `NONE` | `MISSED` | 1/2 | **1/2** | **+0** |
| `gcd-006-storage-unattached-disks` | `gcloud` | `gcloud` | `EXACT` | 3/3 | **3/3** | **+0** |
| `gcd-007-run-service-level-iam` | `google-cloud-recipe-auth` | `gcloud` | `ACCEPTABLE` | 3/3 | **3/3** | **+0** |
| `gcd-008-worker-pools-architecture` | `retrieving-developer-knowledge` | `cloudrun-deploy` | `MISSED` | 1/3 | **3/3** | **+2** |
| `gcd-009-cross-project-secret-iam` | `google-cloud-recipe-auth` | `gcp-auth` | `MISSED` | 3/3 | **3/3** | **+0** |
| `gcd-010-destructive-batch-safety` | `gcloud` | `gcloud` | `EXACT` | 2/3 | **3/3** | **+1** |
| `gcd-011-adc-troubleshooting` | `google-cloud-recipe-auth` | `gcp-auth` | `MISSED` | 2/3 | **3/3** | **+1** |
| `gcd-012-onboarding-safety-gate` | `google-cloud-recipe-onboarding` | `google-cloud-developer` | `MISSED` | 3/3 | **0/3** | **-3** |
