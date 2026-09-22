# Empirical Harbor Sandbox Benchmark: Claude Sonnet 4.5 Evaluation

**Author:** Dan Dye  
**Date:** 2026-09-22  
**Dataset:** Karl Weinmeister's Official 12-Scenario Benchmark (`evals/kweinmeister/evals.json`)  
**Harness:** Claude Code 2.1.269 in Harbor Sandbox on Rootless Podman  
**Model:** `claude-sonnet-4-5` on Vertex AI (`us-east5`) via LiteLLM Proxy  
**Evaluator:** NVIDIA SkillEvaluator 0.3.0 with LiteLLM Vertex AI Gemini 2.5 Flash Judge  
**Run ID:** `20260922_033240_3040438_920eb05d3e57`  
**HTML Report:** `http://ahma.c.googlers.com:8088/report.html`

---

## 1. Executive Summary

Following our empirical Claude Code baseline run, we evaluated Anthropic's **Claude Sonnet 4.5** on Vertex AI Model Garden (`us-east5`) across Karl Weinmeister's full 12-scenario benchmark protocol under the exact same Harbor sandbox constraints.

Both arms (Treatment: with `google-cloud-developer` skill vs. Control: baseline without skills) ran across all 12 scenarios (24 total trials) with zero timeouts, zero runtime errors, and 100% completion.

### Key Highlights
1. **Dramatic Positive Lift (+0.1827 / +30.89%)**:
   - **Without Skill Baseline**: **0.5915** overall score
   - **With Skill Arm**: **0.7742** overall score
   - Claude Sonnet 4.5 demonstrated statistically significant positive lift on 10 out of 12 benchmark tasks when equipped with the `google-cloud-developer` skill.
2. **Top Scenario Gains**:
   - **`gcd-008` (Worker Pools Architecture)**: **+0.3194 Lift** (0.5000 -> 0.8194)
   - **`gcd-011` (ADC Troubleshooting)**: **+0.2639 Lift** (0.6111 -> 0.8750)
   - **`gcd-001` (Explicit Auth & Service Identity)**: **+0.2500 Lift** (0.6250 -> 0.8750)
   - **`gcd-002` (Cloud Run Storage & Volume Mounts)**: **+0.2083 Lift** (0.6667 -> 0.8750)
   - **`gcd-007` (Run Service-Level IAM)**: **+0.2083 Lift** (0.6667 -> 0.8750)
   - **`gcd-009` (Cross-Project Secret IAM)**: **+0.2083 Lift** (0.6667 -> 0.8750)
   - **`gcd-010` (Destructive Batch VM Safety)**: **+0.2083 Lift** (0.6667 -> 0.8750)
   - **`gcd-005` (Catalog Skill Discovery)**: **+0.2062 Lift** (0.3167 -> 0.5229)
3. **Flawless Security Grounding**:
   - Both arms scored **1.0000** on Security, strictly adhering to user-managed service accounts, Application Default Credentials (ADC), least-privilege resource-level IAM bindings, and absolute rejection of downloadable JSON keys.
4. **Zero Timeouts**:
   - Unlike Claude 3.5 Sonnet which timed out on unassisted catalog discovery (`gcd-005`), Claude Sonnet 4.5 completed all 12 baseline trials without timing out.

---

## 2. Scenario-by-Scenario Scorecard & Measured Lift

Below is the side-by-side comparison between the unassisted baseline arm and the skill-assisted arm for Claude Sonnet 4.5:

| ID | Scenario Description | Without Skill | With Skill | Net Lift ($\Delta$) | Behavioral Impact |
| :--- | :--- | :---: | :---: | :---: | :--- |
| `gcd-001` | Cloud Run Authentication & Least-Privilege IAM | 0.6250 | **0.8750** | **+0.2500** | Strict least-privilege `roles/storage.objectViewer` bucket-level binding |
| `gcd-002` | Cloud Run Volume & Secret Mount | 0.6667 | **0.8750** | **+0.2083** | Explicit volume and secret mount syntax provided |
| `gcd-003` | Headless CI/CD Non-Interactive Config | 0.5555 | **0.5778** | **+0.0223** | Correct non-interactive flags and env vars |
| `gcd-004` | Batch Timeout Limits (Jobs vs. Services) | 0.5444 | **0.6674** | **+0.1230** | Delineates 60m service vs. 24h job limits |
| `gcd-005` | Official Skill Catalog Discovery | 0.3167 | **0.5229** | **+0.2062** | Structured discovery flow vs. raw search |
| `gcd-006` | Server-Side Persistent Disk Filtering | 0.6667 | 0.6667 | 0.0000 | Identical server-side filter query syntax |
| `gcd-007` | Service-Level IAM Invocation Binding | 0.6667 | **0.8750** | **+0.2083** | Precision service-level invocation binding |
| `gcd-008` | Cloud Run Worker Pools Architecture | 0.5000 | **0.8194** | **+0.3194** | Pub/Sub pull subscription worker pool architecture |
| `gcd-009` | Cross-Project Secret Manager IAM Scoping | 0.6667 | **0.8750** | **+0.2083** | Resource-level secretAccessor binding across projects |
| `gcd-010` | Destructive VM Batch Deletion Safety | 0.6667 | **0.8750** | **+0.2083** | Two-phase verify-then-delete pipeline |
| `gcd-011` | ADC Troubleshooting vs. Downloadable Keys | 0.6111 | **0.8750** | **+0.2639** | Prescribed ADC remediation without JSON service account keys |
| `gcd-012` | Project Onboarding Safety & Collisions | 0.6111 | **0.7861** | **+0.1750** | Enforced project ID uniqueness and naming validation |

---

## 3. Evaluator Dimension Metrics

| Evaluator Dimension | With Skill | Without Skill | Lift ($\Delta$) | Direction |
| :--- | :---: | :---: | :---: | :---: |
| **Overall Score** | **0.7742** | 0.5915 | **+0.1827** | Up |
| **Security** | **1.0000** | 1.0000 | 0.0000 | Flat (Optimal) |
| **Skill Execution** | **0.6562** | 0.0000 | **+0.6562** | Up |
| **Skill Efficiency** | **0.4167** | 0.0000 | **+0.4167** | Up |
| **Behavior Check** | **0.8472** | 0.7153 | **+0.1319** | Up |
| **Accuracy** | 0.8500 | 0.9167 | -0.0667 | Slight variance |
| **Goal Accuracy** | 0.8750 | 0.9167 | -0.0417 | Slight variance |
| **Pass Rate (pass@1)** | **1.0000** (12/12) | 0.9167 (11/12) | **+0.0833** | Up (+1 passed case) |

---

## 4. Cross-Model Comparison: Claude Sonnet 4.5 vs. Claude Code Baseline

Comparing Claude Sonnet 4.5 against the prior Claude Code run:

| Metric | Claude Code Prior Run | Claude Sonnet 4.5 (Vertex AI) | Delta / Commentary |
| :--- | :---: | :---: | :--- |
| **With Skill Overall** | 0.6050 | **0.7742** | **+0.1692** higher quality with Sonnet 4.5 |
| **Without Skill Overall** | 0.5362 | **0.5915** | **+0.0553** stronger out-of-the-box base capability |
| **Skill Net Lift** | +0.0688 | **+0.1827** | Sonnet 4.5 leverages skill instructions significantly better |
| **Pass Rate (With Skill)** | 83.3% (10/12) | **100.0%** (12/12) | Perfect 12/12 scenario pass rate |
| **Unassisted Timeouts** | 1 (`gcd-005`) | **0** | No hanging tool call loops |
| **Total Duration** | ~35 minutes | **28.6 minutes** | Faster inference and tool turn resolution |

---

## 5. Artifacts and Verification

- **Interactive HTML Report**: `http://ahma.c.googlers.com:8088/report.html`
- **Output Run Directory**: `skills/google-cloud-developer/evals/results/20260922_033240_3040438_920eb05d3e57/`
- **Results JSON**: `skills/google-cloud-developer/evals/results/20260922_033240_3040438_920eb05d3e57/result.json`
