# Gen 4 Master Model Evaluation Matrix: With vs. Without Skills

Generated at: 2026-09-20T17:35:30Z
Environment: `dandye-0324-chronicle` (`us-central1`)
Benchmark: `gemma-deploy` (Version 4.0.0, 12 Scenarios)

---

## 1. Executive Summary Table

| Model | Class / Tier | Baseline (No Skills) | Treatment (With Skills) | Net Capability Lift (Δ) | Baseline Assertions | Treatment Assertions | Assertion Gain |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`gemini-2.5-pro`** | Frontier Deep Reasoner | 41.7% (5/12) | **75.0% (9/12)** | **+33.3%** | 41 / 48 (85.4%) | **44 / 48 (91.7%)** | +3 |
| **`gemini-2.5-flash-lite`** | Lightweight / Edge | 50.0% (6/12) | **66.7% (8/12)** | **+16.7%** | 41 / 48 (85.4%) | **43 / 48 (89.6%)** | +2 |
| **`gemini-2.5-flash`** | General Workhorse | 41.7% (5/12) | **58.3% (7/12)** | **+16.7%** | 39 / 48 (81.2%) | **41 / 48 (85.4%)** | +2 |
| **Canonical Spec** | Gold Reference | 100.0% (12/12) | **100.0% (12/12)** | 0.0% | 48 / 48 (100.0%) | **48 / 48 (100.0%)** | 0 |

---

## 2. Per-Scenario Head-to-Head Comparison

| Scenario ID | Target Domain Skill | `gemini-2.5-flash` (No Skill -> With Skill) | `gemini-2.5-flash-lite` (No Skill -> With Skill) | `gemini-2.5-pro` (No Skill -> With Skill) |
| :--- | :--- | :---: | :---: | :---: |
| `gdo-001` Cloud Run GPU Scale-to-Zero | `cloudrun-deploy` | PASS -> **PASS** (=) | FAIL -> **PASS** (+) | PASS -> **PASS** (=) |
| `gdo-002` Vertex N-gram Speculation | `vertex-prediction` | FAIL -> **PASS** (+) | FAIL -> **PASS** (+) | PASS -> **PASS** (=) |
| `gdo-003` Server-Side Disk Filtering | `gcloud` | FAIL -> FAIL (=) | FAIL -> FAIL (=) | FAIL -> FAIL (=) |
| `gdo-004` Cross-Project Secret IAM | `gcp-auth` | FAIL -> FAIL (=) | PASS -> FAIL (-) | FAIL -> FAIL (=) |
| `gdo-005` Destructive Safety Gate | `cloud-safety` | PASS -> **PASS** (=) | PASS -> **PASS** (=) | PASS -> **PASS** (=) |
| `gdo-006` GCE Spot Auto-Deletion | `gce-spot` | PASS -> **PASS** (=) | FAIL -> **PASS** (+) | PASS -> **PASS** (=) |
| `gdo-007` Container Swap Space Sizing | `vertex-prediction` | PASS -> FAIL (-) | PASS -> FAIL (-) | FAIL -> **PASS** (+) |
| `gdo-008` Cloud Run Quota Lifecycle | `cloudrun-quota` | PASS -> **PASS** (=) | PASS -> **PASS** (=) | PASS -> **PASS** (=) |
| `gdo-009` ADK Endpoint Discovery | `agent-engine` | FAIL -> **PASS** (+) | PASS -> **PASS** (=) | FAIL -> **PASS** (+) |
| `gdo-010` SOC Containment vs Escalation| `secops-triage` | FAIL -> **PASS** (+) | FAIL -> **PASS** (+) | FAIL -> **PASS** (+) |
| `gdo-011` ADC vs Service Account Keys | `gcp-auth` | FAIL -> FAIL (=) | PASS -> **PASS** (=) | FAIL -> **PASS** (+) |
| `gdo-012` Model Catalog Sizing Parity | `model-catalog` | FAIL -> FAIL (=) | FAIL -> FAIL (=) | FAIL -> FAIL (=) |
