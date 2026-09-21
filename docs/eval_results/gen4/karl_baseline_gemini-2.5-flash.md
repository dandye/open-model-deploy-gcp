# Gen 4 A/B Ablation Evaluation Report: google-cloud-developer

- **Model Under Test:** gemini-2.5-flash
- **Version:** None
- **Baseline Pass Rate (Without Skills):** 75.0%
- **Treatment Pass Rate (With Skills):** 66.7%
- **Net Capability Lift (Δ):** -8.3%
- **Assertion Matches:** 33 -> 31 / 36 (+-2)

| Scenario ID | Baseline | With Skills | Net Lift (Δ) | Baseline Assertions | With Skills Assertions | Runtime | Tier |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- | :--- |
| `gcd-001-explicit-auth` | PASS | **PASS** | **BOTH_PASSED (=)** (+0.0%) | 4/4 | 4/4 | `general` | `edge-1b-4b` |
| `gcd-002-cloudrun-storage` | PASS | **PASS** | **BOTH_PASSED (=)** (+0.0%) | 3/3 | 3/3 | `general` | `edge-1b-4b` |
| `gcd-003-gcloud-noninteractive` | FAIL | **FAIL** | **BOTH_FAILED (=)** (-33.3%) | 2/3 | 1/3 | `general` | `edge-1b-4b` |
| `gcd-004-batch-timeout-limits` | PASS | **PASS** | **BOTH_PASSED (=)** (+0.0%) | 3/3 | 3/3 | `general` | `edge-1b-4b` |
| `gcd-005-catalog-skill-discovery` | FAIL | **FAIL** | **BOTH_FAILED (=)** (+0.0%) | 1/2 | 1/2 | `general` | `edge-1b-4b` |
| `gcd-006-storage-unattached-disks` | PASS | **FAIL** | **REGRESSION (-)** (-33.3%) | 3/3 | 2/3 | `general` | `edge-1b-4b` |
| `gcd-007-run-service-level-iam` | PASS | **PASS** | **BOTH_PASSED (=)** (+0.0%) | 3/3 | 3/3 | `general` | `edge-1b-4b` |
| `gcd-008-worker-pools-architecture` | PASS | **PASS** | **BOTH_PASSED (=)** (+0.0%) | 3/3 | 3/3 | `general` | `edge-1b-4b` |
| `gcd-009-cross-project-secret-iam` | PASS | **PASS** | **BOTH_PASSED (=)** (+0.0%) | 3/3 | 3/3 | `general` | `edge-1b-4b` |
| `gcd-010-destructive-batch-safety` | PASS | **PASS** | **BOTH_PASSED (=)** (+0.0%) | 3/3 | 3/3 | `general` | `edge-1b-4b` |
| `gcd-011-adc-troubleshooting` | PASS | **PASS** | **BOTH_PASSED (=)** (+0.0%) | 3/3 | 3/3 | `general` | `edge-1b-4b` |
| `gcd-012-onboarding-safety-gate` | FAIL | **FAIL** | **BOTH_FAILED (=)** (+0.0%) | 2/3 | 2/3 | `general` | `edge-1b-4b` |
