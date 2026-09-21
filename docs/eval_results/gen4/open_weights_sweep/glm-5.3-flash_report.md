# Gen 4 Evaluation Report: glm-5.3-flash

- **Family:** Zhipu GLM
- **Parameters:** 12B
- **Tier:** mid-9b-12b
- **Baseline Pass Rate (No Skills):** 41.7%
- **Treatment Pass Rate (With Skills):** 75.0%
- **Net Capability Lift (Δ):** +33.3%
- **Assertion Matches:** 41 -> 45 / 48

| Scenario ID | Baseline | With Skills | Baseline Assertions | With Skills Assertions |
| :--- | :---: | :---: | :---: | :---: |
| `gdo-001-cloudrun-gpu-l4-scale-to-zero` | PASS | **PASS** | 4/4 | 4/4 |
| `gdo-002-vertex-speculative-decoding-ngram` | FAIL | **PASS** | 3/4 | 4/4 |
| `gdo-003-server-side-disk-audit` | FAIL | **FAIL** | 3/4 | 3/4 |
| `gdo-004-cross-project-secret-iam` | FAIL | **FAIL** | 3/4 | 3/4 |
| `gdo-005-destructive-teardown-safety-gate` | PASS | **PASS** | 4/4 | 4/4 |
| `gdo-006-gce-spot-vm-auto-deletion` | PASS | **PASS** | 4/4 | 4/4 |
| `gdo-007-vertex-container-swap-space` | FAIL | **PASS** | 3/4 | 4/4 |
| `gdo-008-cloudrun-gpu-quota-lifecycle` | PASS | **PASS** | 4/4 | 4/4 |
| `gdo-009-adk-agent-endpoint-discovery` | FAIL | **PASS** | 3/4 | 4/4 |
| `gdo-010-soc-containment-vs-escalation` | FAIL | **PASS** | 3/4 | 4/4 |
| `gdo-011-adc-vs-service-account-keys` | PASS | **PASS** | 4/4 | 4/4 |
| `gdo-012-model-catalog-sizing-parity` | FAIL | **FAIL** | 3/4 | 3/4 |
