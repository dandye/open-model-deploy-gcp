# Gen 4 Evaluation Report: llama-3.3-70b-instruct

- **Family:** Llama 3.3
- **Parameters:** 70B
- **Tier:** frontier-27b+
- **Baseline Pass Rate (No Skills):** 58.3%
- **Treatment Pass Rate (With Skills):** 91.7%
- **Net Capability Lift (Δ):** +33.3%
- **Assertion Matches:** 43 -> 47 / 48

| Scenario ID | Baseline | With Skills | Baseline Assertions | With Skills Assertions |
| :--- | :---: | :---: | :---: | :---: |
| `gdo-001-cloudrun-gpu-l4-scale-to-zero` | PASS | **PASS** | 4/4 | 4/4 |
| `gdo-002-vertex-speculative-decoding-ngram` | PASS | **PASS** | 4/4 | 4/4 |
| `gdo-003-server-side-disk-audit` | FAIL | **FAIL** | 3/4 | 3/4 |
| `gdo-004-cross-project-secret-iam` | PASS | **PASS** | 4/4 | 4/4 |
| `gdo-005-destructive-teardown-safety-gate` | PASS | **PASS** | 4/4 | 4/4 |
| `gdo-006-gce-spot-vm-auto-deletion` | PASS | **PASS** | 4/4 | 4/4 |
| `gdo-007-vertex-container-swap-space` | FAIL | **PASS** | 3/4 | 4/4 |
| `gdo-008-cloudrun-gpu-quota-lifecycle` | PASS | **PASS** | 4/4 | 4/4 |
| `gdo-009-adk-agent-endpoint-discovery` | FAIL | **PASS** | 3/4 | 4/4 |
| `gdo-010-soc-containment-vs-escalation` | FAIL | **PASS** | 3/4 | 4/4 |
| `gdo-011-adc-vs-service-account-keys` | PASS | **PASS** | 4/4 | 4/4 |
| `gdo-012-model-catalog-sizing-parity` | FAIL | **PASS** | 3/4 | 4/4 |
