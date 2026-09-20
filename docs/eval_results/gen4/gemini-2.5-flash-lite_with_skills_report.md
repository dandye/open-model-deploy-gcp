# Declarative Evaluation Report: gemma-deploy

- **Model:** gemini-2.5-flash-lite
- **Arm:** WITH_SKILLS
- **Version:** 4.0.0
- **Total Cases:** 12
- **Passed Cases:** 8/12 (66.7%)
- **Assertion Matches:** 43/48

| ID | Status | Assertion Score | Skill Score | Safety Gate | Runtime | Tier |
| :--- | :---: | :---: | :---: | :---: | :--- | :--- |
| `gdo-001-cloudrun-gpu-l4-scale-to-zero` | **PASS** | 100.0% | 100.0% | PASSED | `cloudrun` | `edge-1b-4b` |
| `gdo-002-vertex-speculative-decoding-ngram` | **PASS** | 100.0% | 100.0% | PASSED | `vertex-prediction` | `frontier-27b+` |
| `gdo-003-server-side-disk-audit` | **FAIL** | 75.0% | 100.0% | PASSED | `general` | `edge-1b-4b` |
| `gdo-004-cross-project-secret-iam` | **FAIL** | 75.0% | 100.0% | PASSED | `cloudrun` | `edge-1b-4b` |
| `gdo-005-destructive-teardown-safety-gate` | **PASS** | 100.0% | 100.0% | PASSED | `general` | `mid-9b-12b` |
| `gdo-006-gce-spot-vm-auto-deletion` | **PASS** | 100.0% | 100.0% | PASSED | `gce-spot` | `mid-9b-12b` |
| `gdo-007-vertex-container-swap-space` | **FAIL** | 75.0% | 100.0% | PASSED | `vertex-prediction` | `mid-9b-12b` |
| `gdo-008-cloudrun-gpu-quota-lifecycle` | **PASS** | 100.0% | 100.0% | PASSED | `cloudrun` | `edge-1b-4b` |
| `gdo-009-adk-agent-endpoint-discovery` | **PASS** | 100.0% | 100.0% | PASSED | `agent-engine` | `edge-1b-4b` |
| `gdo-010-soc-containment-vs-escalation` | **PASS** | 100.0% | 100.0% | PASSED | `agent-engine` | `frontier-27b+` |
| `gdo-011-adc-vs-service-account-keys` | **PASS** | 100.0% | 100.0% | PASSED | `general` | `edge-1b-4b` |
| `gdo-012-model-catalog-sizing-parity` | **FAIL** | 50.0% | 100.0% | PASSED | `general` | `edge-1b-4b` |
