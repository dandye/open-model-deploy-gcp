# Campaign 5: Closed-Loop Harbor Sandbox Validation of GEPA-Evolved Runbooks

- **Date:** 2026-10-02
- **Evaluator:** Jetski Campaign 5 Harbor Runner (`scripts/run_harbor_soc_sweep.py`)
- **Repository:** `gemma_deploy__worktrees/harbor_soc_evals_v0001`
- **GCP Tenant Isolation:** Argolis Project `dandye-0324-chronicle` (`1002894625780`, Region: `us-central1`)
- **Cluster Target:** `harbor-eval-cluster` (GKE / Container Sandbox Fallback)
- **Total Trials Evaluated:** 90 trials (3 models x 3 arms x 10 cases)

---

## 1. Executive Summary & Objective

Campaign 5 completes the empirical loop between offline genetic Pareto optimization (GEPA) and closed-loop interactive container sandbox execution. We address the core research question:

> **Did genetic Pareto evolution produce runbooks that outperform human-authored clean skills in the interactive execution sandbox?**

### The Empirical Answer: NO (Human-Authored Skills Remain Decisively Superior)

Across all three evaluated model tiers (`gemini-3.5-flash-lite`, `gemini-2.5-flash`, and `gemini-2.5-flash-lite`), human-authored clean skills (`secops-triage`) consistently and significantly outperformed the GEPA-evolved runbooks:
- On `gemini-3.5-flash-lite`: `clean_skills` scored **0.8413** (90.0% pass rate, $5.00 loss) vs. `gepa_evolved_skills` at **0.7459** (60.0% pass rate, $6,505.00 loss) — a **-11.34% (-0.0954)** performance drop for GEPA.
- On `gemini-2.5-flash`: `clean_skills` scored **0.8555** (90.0% pass rate, $505.00 loss) vs. `gepa_evolved_skills` at **0.7033** (60.0% pass rate, $1,000.00 loss) — a **-17.79% (-0.1522)** performance drop for GEPA.
- On `gemini-2.5-flash-lite`: `clean_skills` scored **0.6551** (50.0% pass rate, $5,500.00 loss) vs. `gepa_evolved_skills` at **0.4361** (10.0% pass rate, $11,005.00 loss) — a catastrophic **-33.43% (-0.2190)** performance collapse for GEPA.

While genetic Pareto evolution succeeded in optimizing structured multi-agent mock prompt interactions in offline hillclimbing, the resulting runbooks introduced abstract template scaffolding (`${IOC_VALUE}`, `${CASE_ID}`, `REL_LIST`, pseudo-code `IF/ELSE` branches, and Mermaid diagrams) that caused cognitive friction, hesitation, and state/safety degradation inside an interactive CLI sandbox (`soc-cli`).

---

## 2. Master Comparative Scorecard

Empirical results across all 90 trials evaluated by the continuous 60/20/20 verifier (`scripts/verify_harbor_soc.py`):

| Model | Experimental Arm | Mean Continuous Reward | State & Safety Compliance (60%) | Epistemic Action Economy (20%) | Assertions + Jev Rubric (20%) | Mean Expected Loss ($USD) | Pass Rate (Reward >= 0.70) | Mean Latency (s) | Total Tools Called |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `gemini-3.5-flash-lite` | `no_skills` | **0.7704** | 0.4920 | 0.1384 | 0.1400 | $505.00 | 70.0% | 7.69s | 35 |
| `gemini-3.5-flash-lite` | `clean_skills` | **0.8413** | 0.5199 | 0.1504 | 0.1710 | $5.00 | 90.0% | 7.36s | 35 |
| `gemini-3.5-flash-lite` | `gepa_evolved_skills` | **0.7459** | 0.4164 | 0.1900 | 0.1395 | $6,505.00 | 60.0% | 12.29s | 37 |
| `gemini-2.5-flash` | `no_skills` | **0.8109** | 0.5400 | 0.0984 | 0.1725 | $5,000.00 | 80.0% | 29.52s | 49 |
| `gemini-2.5-flash` | `clean_skills` | **0.8555** | 0.5720 | 0.1140 | 0.1695 | $505.00 | 90.0% | 28.82s | 50 |
| `gemini-2.5-flash` | `gepa_evolved_skills` | **0.7033** | 0.4243 | 0.1560 | 0.1230 | $1,000.00 | 60.0% | 27.89s | 31 |
| `gemini-2.5-flash-lite` | `no_skills` | **0.6731** | 0.4724 | 0.0412 | 0.1595 | $10,500.00 | 60.0% | 13.50s | 50 |
| `gemini-2.5-flash-lite` | `clean_skills` | **0.6551** | 0.4323 | 0.0668 | 0.1560 | $5,500.00 | 50.0% | 11.22s | 45 |
| `gemini-2.5-flash-lite` | `gepa_evolved_skills` | **0.4361** | 0.2844 | 0.0532 | 0.0985 | $11,005.00 | 10.0% | 11.63s | 30 |

---

## 3. Procedural Lift and Evolution Delta Analysis

| Model | Baseline (`no_skills`) | Clean Skill (`clean_skills`) | GEPA Evolved (`gepa_evolved_skills`) | Clean Skill Procedural Lift | GEPA vs. Clean Delta | GEPA Outperformed Clean? |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `gemini-3.5-flash-lite` | 0.7704 | 0.8413 | 0.7459 | **+0.0709 (+9.20%)** | **-0.0954 (-11.34%)** | **NO (Human-authored superior)** |
| `gemini-2.5-flash` | 0.8109 | 0.8555 | 0.7033 | **+0.0446 (+5.50%)** | **-0.1522 (-17.79%)** | **NO (Human-authored superior)** |
| `gemini-2.5-flash-lite` | 0.6731 | 0.6551 | 0.4361 | -0.0180 (-2.67%) | **-0.2190 (-33.43%)** | **NO (Human-authored superior)** |

---

## 4. Deep Qualitative & Architectural Analysis

### A. Why Did Human-Authored Clean Skills Excel?
The human-authored `secops-triage` skill was designed around operational action boundaries:
1. **Clear Epistemic-First Gate:** "Never execute a state-changing action at step 0 without first querying epistemic tools."
2. **Explicit Counter-Prior Rules:** Non-routable RFC-5737 addresses are explicitly labeled benign; authorized internal scanners require checking CMDB schedules rather than isolating; ambiguous CDN/DNS tunnels on CFO workstations require logging notes rather than triggering $50k downtime isolations.
3. **Low Cognitive Overhead:** It fits within 30 concise, declarative bullet points. Models readily internalize the rules into their system directive without distraction.

### B. Why Did GEPA-Evolved Runbooks Degrade in the Sandbox?
1. **Offline-to-Online Domain Transfer Failure:**
   - GEPA evolved runbooks using a static reflection LM (`gemini-2.5-pro`) optimizing a text prompt for an offline supervisor-worker agent. The reflection LM favored formal software engineering artifacts: input variable declarations (`${IOC_VALUE}`), output contracts (`${GTI_FINDINGS}`), Mermaid sequence diagrams, and multi-clause pseudo-code rules.
   - When deployed in an interactive Harbor container, the agent must interact with a real Linux CLI (`/usr/local/bin/soc-cli`). The model struggled to reconcile abstract variables with the concrete CLI syntax.
2. **Hesitation and Zero-Tool Premature Termination on Smaller Models:**
   - On `gemini-2.5-flash-lite`, the complex runbook structure overwhelmed the model's instruction-following capacity. The model exhibited complete tool paralysis on multiple scenarios (Case 03 Phishing, Case 05 Ransomware, Case 09 503 Outage), attempting to output conclusions without executing any CLI commands (0 tools called, earning only the 0.20 baseline prior score). This dropped the pass rate from 50.0% to 10.0%.
3. **Action Economy vs. State Compliance Divergence:**
   - Interestingly, on frontier models (`gemini-3.5-flash-lite` and `gemini-2.5-flash`), Action Economy actually improved under GEPA (0.1900 on 3.5-flash-lite vs 0.1504 on clean skills; 0.1560 on 2.5-flash vs 0.1140 on clean skills). The models executed fewer exploratory calls.
   - However, State & Safety compliance collapsed: from 0.5199 to 0.4164 on 3.5-flash-lite, and from 0.5720 to 0.4243 on 2.5-flash. The models skipped critical containment actions (such as `isolate_host` or `block_indicator`) because they became bogged down in the runbook's abstract intermediate steps (e.g. attempting to search for nonexistent related cases).

---

## 5. Scenario-by-Scenario Comparative Breakdown

| Case ID | Scenario Name | Best Arm (`gemini-3.5-flash-lite`) | Best Arm (`gemini-2.5-flash`) | Clean vs. GEPA Key Dynamic |
| :--- | :--- | :---: | :---: | :--- |
| `CASE-01` | Lokibot C2 InfoStealer | `clean_skills` (1.0000) | `clean_skills` (0.9500) | Clean skill immediately isolated host; GEPA hesitated with case search. |
| `CASE-02` | RFC-5737 Non-Routable IP | `clean_skills` (0.8490) | `clean_skills` (0.8090) | Clean skill cleanly identified RFC-5737 and closed case without isolation. |
| `CASE-03` | Phishing Credential Harvest | `clean_skills` (0.7450) | `gepa_evolved_skills` (0.9500) | GEPA blocked indicator cleanly on Flash, but paralyzed Flash-Lite. |
| `CASE-04` | Duplicate SOAR Case | `gepa_evolved_skills` (0.6263) | `clean_skills` (0.7813) | Clean skill updated comments on open ticket; GEPA missed deduplication. |
| `CASE-05` | Ransomware Escalation | `clean_skills` (1.0000) | `gepa_evolved_skills` (1.0000) | Both arms isolated host on high-end models; GEPA failed on Flash-Lite. |
| `CASE-06` | Ambiguous DNS Tunnel | `clean_skills` (0.7550) | `clean_skills` (0.6550) | Clean skill avoided $50k CFO isolation; GEPA triggered false positive on Flash-Lite. |
| `CASE-07` | PsExec Lateral Movement | `gepa_evolved_skills` (0.9250) | `clean_skills` (0.8200) | Lateral movement runbook provided good technique context for PsExec. |
| `CASE-08` | Revoked CA Supply Chain | `clean_skills` (1.0000) | `clean_skills` (0.9600) | Clean skill blocked hash; GEPA failed CA revocation verification on Flash. |
| `CASE-09` | HTTP 503 Outage Resilience | `clean_skills` (0.8500) | `clean_skills` (0.8500) | Clean skill handled 503 gracefully; GEPA timed out or zero-tooled. |
| `CASE-10` | Authorized Scanner Noise | `clean_skills` (0.7550) | `clean_skills` (0.9600) | Clean skill prevented $50k downtime on payment server; GEPA had extra turns. |

---

## 6. Key Conclusions & Next Steps

1. **Closed-Loop Grounding Requirement for Evolutionary Optimizers:** Offline genetic prompt optimization must evaluate candidates directly in interactive execution sandboxes (like Harbor / GKE) rather than relying on mock LLM-as-a-judge feedback. Optimizing against mock judges produces verbose, template-heavy text that degrades live agent actuation.
2. **Simplicity and Directiveness Outperform Structural Complexity:** Concise operational constraints ("do not isolate unless X", "query Y before Z") are far more effective for LLM agents than elaborate procedural flowcharts or pseudo-code templates.
3. **Model Selection:** `gemini-3.5-flash-lite` armed with `clean_skills` remains the cost-efficiency champion across all tiers: 90.0% pass rate, 0.8413 continuous reward, 7.36s latency, and a minimal $5.00 expected operational loss.
