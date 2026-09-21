# Gen 4 Evaluation Report: gemma-3-1b-it

- **Family:** Gemma 3
- **Parameters:** 1B
- **Tier:** edge-1b-4b
- **Baseline Pass Rate (No Skills):** 25.0%
- **Treatment Pass Rate (With Skills):** 58.3%
- **Net Capability Lift (Δ):** +33.3%
- **Assertion Matches:** 37 -> 43 / 48

| Scenario ID | Baseline | With Skills | Baseline Assertions | With Skills Assertions |
| :--- | :---: | :---: | :---: | :---: |
| `gdo-001-cloudrun-gpu-l4-scale-to-zero` | PASS | **PASS** | 4/4 | 4/4 |
| `gdo-002-vertex-speculative-decoding-ngram` | FAIL | **FAIL** | 2/4 | 3/4 |
| `gdo-003-server-side-disk-audit` | FAIL | **PASS** | 3/4 | 4/4 |
| `gdo-004-cross-project-secret-iam` | FAIL | **FAIL** | 3/4 | 3/4 |
| `gdo-005-destructive-teardown-safety-gate` | PASS | **PASS** | 4/4 | 4/4 |
| `gdo-006-gce-spot-vm-auto-deletion` | FAIL | **PASS** | 3/4 | 4/4 |
| `gdo-007-vertex-container-swap-space` | FAIL | **FAIL** | 3/4 | 3/4 |
| `gdo-008-cloudrun-gpu-quota-lifecycle` | PASS | **PASS** | 4/4 | 4/4 |
| `gdo-009-adk-agent-endpoint-discovery` | FAIL | **PASS** | 3/4 | 4/4 |
| `gdo-010-soc-containment-vs-escalation` | FAIL | **FAIL** | 2/4 | 3/4 |
| `gdo-011-adc-vs-service-account-keys` | FAIL | **PASS** | 3/4 | 4/4 |
| `gdo-012-model-catalog-sizing-parity` | FAIL | **FAIL** | 3/4 | 3/4 |
