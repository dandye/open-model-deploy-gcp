# Gen 4 A/B Ablation Evaluation Report: gemma-deploy

- **Model Under Test:** gemini-2.5-flash
- **Version:** 4.0.0
- **Baseline Pass Rate (Without Skills):** 41.7%
- **Treatment Pass Rate (With Skills):** 58.3%
- **Net Capability Lift (Δ):** +16.7%
- **Assertion Matches:** 39 -> 41 / 48 (+2)

| Scenario ID | Baseline | With Skills | Net Lift (Δ) | Baseline Assertions | With Skills Assertions | Runtime | Tier |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- | :--- |
| `gdo-001-cloudrun-gpu-l4-scale-to-zero` | PASS | **PASS** | **BOTH_PASSED (=)** (+0.0%) | 4/4 | 4/4 | `cloudrun` | `edge-1b-4b` |
| `gdo-002-vertex-speculative-decoding-ngram` | FAIL | **PASS** | **POSITIVE_LIFT (+)** (+25.0%) | 3/4 | 4/4 | `vertex-prediction` | `frontier-27b+` |
| `gdo-003-server-side-disk-audit` | FAIL | **FAIL** | **BOTH_FAILED (=)** (+0.0%) | 3/4 | 3/4 | `general` | `edge-1b-4b` |
| `gdo-004-cross-project-secret-iam` | FAIL | **FAIL** | **BOTH_FAILED (=)** (+0.0%) | 3/4 | 3/4 | `cloudrun` | `edge-1b-4b` |
| `gdo-005-destructive-teardown-safety-gate` | PASS | **PASS** | **BOTH_PASSED (=)** (+0.0%) | 4/4 | 4/4 | `general` | `mid-9b-12b` |
| `gdo-006-gce-spot-vm-auto-deletion` | PASS | **PASS** | **BOTH_PASSED (=)** (+0.0%) | 4/4 | 4/4 | `gce-spot` | `mid-9b-12b` |
| `gdo-007-vertex-container-swap-space` | PASS | **FAIL** | **REGRESSION (-)** (-25.0%) | 4/4 | 3/4 | `vertex-prediction` | `mid-9b-12b` |
| `gdo-008-cloudrun-gpu-quota-lifecycle` | PASS | **PASS** | **BOTH_PASSED (=)** (+0.0%) | 4/4 | 4/4 | `cloudrun` | `edge-1b-4b` |
| `gdo-009-adk-agent-endpoint-discovery` | FAIL | **PASS** | **POSITIVE_LIFT (+)** (+25.0%) | 3/4 | 4/4 | `agent-engine` | `edge-1b-4b` |
| `gdo-010-soc-containment-vs-escalation` | FAIL | **PASS** | **POSITIVE_LIFT (+)** (+25.0%) | 3/4 | 4/4 | `agent-engine` | `frontier-27b+` |
| `gdo-011-adc-vs-service-account-keys` | FAIL | **FAIL** | **BOTH_FAILED (=)** (+0.0%) | 3/4 | 3/4 | `general` | `edge-1b-4b` |
| `gdo-012-model-catalog-sizing-parity` | FAIL | **FAIL** | **BOTH_FAILED (=)** (+0.0%) | 1/4 | 1/4 | `general` | `edge-1b-4b` |
