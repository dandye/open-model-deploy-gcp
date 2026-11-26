# DeepSeek-V4.1-Flash Serverless Vertex OpenMaaS Evaluation Report

- **Generated (UTC):** `2026-11-26T03:02:36Z`
- **Campaign Status:** `COMPLETED`
- **Environment:** Serverless Vertex AI OpenMaaS (`global`, test GCP project & test Google SecOps tenant offline grounding suites)
- **Sampling & Judge Configuration:** `temperature=0.0`, `--jev-backend gliner_decide` (`fastino/GLiNER2.5-Decide` local CPU, \$0.00 judge spend)
- **Evaluation Harness Lock:** Verified across all 33 protected files (`composite_sha256=038639ae9c6839146f0ecad07b0ecfc6c48ea47b8a49d507c7dab237619218df`, `configs/evals/gen5/final_test.json` untouched and sealed)
- **Cumulative Campaign Spend:** \$0.8573 / \$10.00 (`0` dedicated GPU hours, \$0.00/hr infrastructure cost)

## 1. Executive Summary

- **Serverless OpenMaaS Throughput & Multimodal Vision (`global`, \$0.00/hr idle):** `deepseek-ai/deepseek-v4.1-flash-1017-maas` achieved `103.0 tok/s` single-stream and `264.6 tok/s` 4-stream aggregate throughput (`TTFT=262.1 ms`, `ITL=17.40 ms`, `token_count_source=actual`), with `792.9 ms` multimodal PNG `image_url` + text vision latency (`HTTP 200`).
- **Experiment A - Gen 3 10-Case Checkpoint Delta (`0924` vs `1017`):** `deepseek-v4.1-flash-1017-maas` scored `0.0%` pass rate (`0/10`), `64.6/100` Jev rubric, `0.7382` Harbor 60/20/20 reward, SDT sensitivity $d' = 1.03$ ($c = -0.95$), and \$300.41 simulated operational loss, compared against the initial Sept 2026 checkpoint `deepseek-v4.1-flash-maas` at `0.0%` pass rate (`0/10`), `63.2/100` rubric, `0.7359` Harbor 60/20/20, $d' = 1.03$, and \$300.38 operational loss.
- **Experiment B - Gen 5 Validation 20-Case Hierarchical Triage (`clean_skills` vs `harness2_evolved`):** On `deepseek-ai/deepseek-v4.1-flash-1017-maas`, `clean_skills` (`skills/secops-triage/SKILL.md`, `376` words) achieved `0.9651` mean Harbor 60/20/20 reward (`95.0%` pass rate, `0` safety violations), while `harness2_evolved` (`configs/runbooks/harness2_evolved`, `1,256` words) achieved `0.9744` mean Harbor 60/20/20 reward (`100.0%` pass rate, `0` safety violations), benchmarked directly against `gemini-2.5-flash` (`0.9612` `clean_skills` / `0.9723` `harness2_evolved` / `0.9898` GEPA best) and `gemini-2.5-flash-lite` (`0.9840` `harness2_evolved` / `0.9869` `arena_grafted_all4_w300`).
- **Experiment C - Track 2 Proactive Threat Hunting (4 Ursnif GTI Scenarios):** `deepseek-ai/deepseek-v4.1-flash-1017-maas` achieved `0.9812` Hunt Composite (`0.9400` Harbor 60/20/20, `100%` `72h -> 168h` widening, `100%` LOLBin safety) on `compressed_track_b_hunt`, and `1.0000` Hunt Composite (`0.9440` Harbor 60/20/20, `100%` `168h` widening, `100%` Patient Zero `malwaretest-win` discovery, `100%` `rundll32.exe` LOLBin non-blocking safety) on `harness2_evolved_hunt`.
- **Zero-GPU Infrastructure Verification:** Python REST audit at `2026-11-26T03:02:15Z` confirmed `0` deployed Vertex AI endpoints across `us-central1, us-east1, us-west1, europe-west4` and `0` running/staging GCE Spot or GPU VMs.

---

## 2. Step 1: Serverless OpenMaaS Streaming Throughput, Latency & Multimodal Vision

| Model ID | Checkpoint | Concurrency | Avg Latency (s) | P50 / P95 TTFT (ms) | Mean / P50 ITL (ms) | Aggregate TPS (tok/s) | Request-Norm TPS | Token Source | Multimodal PNG Vision Latency |
| :--- | :--- | :---: | ---: | ---: | ---: | ---: | ---: | :---: | ---: |
| `deepseek-ai/deepseek-v4.1-flash-1017-maas` | Oct 2026 (`1017`) | `1` | 1.46s | 274.1 / 275.0 | 17.40 / 17.42 | **103.0** | 103.0 | `actual` | 792.9 ms (`OK`) |
| `deepseek-ai/deepseek-v4.1-flash-1017-maas` | Oct 2026 (`1017`) | `4` | 2.18s | 289.9 / 312.4 | 29.06 / 28.64 | **264.6** | 68.7 | `actual` | - |
| `deepseek-ai/deepseek-v4.1-flash-maas` | Sept 2026 (`0924`) | `1` | 1.40s | 194.4 / 194.9 | 18.25 / 18.22 | **107.3** | 107.3 | `actual` | 510.9 ms (`OK`) |
| `deepseek-ai/deepseek-v4.1-flash-maas` | Sept 2026 (`0924`) | `4` | 1.82s | 285.8 / 292.3 | 24.13 / 24.36 | **312.4** | 82.5 | `actual` | - |

---

## 3. Experiment A: Gen 3 10-Case Interactive SOC Checkpoint Delta (`0924` vs `1017`)

Evaluated on `configs/evals/gen3/soc_tier1_interactive.json` (`10` interactive SOC scenarios, `agent_mode=single`, `temperature=0.0`, `--judge-backend jev --jev-backend gliner_decide`). Note that un-spoiled Single ReAct emits containment recommendations in `soc_decision` (`Advisor Action Match: 90.0%`, `Operator Action Match: 0.0%`) rather than invoking supervisor actuation tools directly, placing CPU `GLiNER2.5-Decide` ordinal scores in the `59.9-71.5/100` band against the `70.0` binary pass cutoff; Experiment B below isolates hierarchical supervisor-worker execution (`95.0%-100.0%` pass rate).

| Metric | `deepseek-v4.1-flash-maas` (`0924`) | `deepseek-v4.1-flash-1017-maas` (`1017`) | Checkpoint Delta (`1017 - 0924`) |
| :--- | ---: | ---: | ---: |
| **Pass Rate** | 0.0% (0/10) | **0.0% (0/10)** | `+0.0 pp` |
| **Mean Harbor 60/20/20 Reward** | 0.7359 | **0.7382** | `+0.0023` |
| **Average Jev Rubric Score** | 63.2 / 100 | **64.6 / 100** | `+1.4` |
| **SDT Sensitivity ($d'$)** | 1.03 | **1.03** | `+0.00` |
| **Decision Criterion Bias ($c$)** | -0.95 | **-0.95** | `+0.00` |
| **Total Tool Calls** | 23 | **23** | `+0` |
| **Epistemic Step Efficiency** | 0.98 | **1.00** | `+0.02` |
| **Action Match Rate** | 90.0% | **90.0%** | `+0.0 pp` |
| **Simulated Operational Loss (USD)** | \$300.38 | **\$300.41** | +\$0.03 |
| **Avg Case Latency (s)** | 30.33s | **28.34s** | `-1.99s` |
| **Generation TPS (tok/s)** | 129.38 | **156.11** | `+26.73` |

### Per-Case Gen 3 Comparison

| Case ID | `0924` Status / Harbor | `1017` Status / Harbor | `1017` Outcome | `1017` Tools | `1017` Loss (USD) |
| :--- | :--- | :--- | :--- | ---: | ---: |
| `CASE-GEN3-01-LOKIBOT-C2` | FAIL (`0.7812`) | **FAIL** (`0.7806`) | `TRUE_POSITIVE` | 2 | \$0.00 |
| `CASE-GEN3-02-RFC5737-BENIGN-IP` | FAIL (`0.7782`) | **FAIL** (`0.7802`) | `TRUE_NEGATIVE` | 1 | \$0.00 |
| `CASE-GEN3-03-PHISHING-CRED-HARVEST` | FAIL (`0.7795`) | **FAIL** (`0.7805`) | `TRUE_POSITIVE` | 2 | \$0.00 |
| `CASE-GEN3-04-DUPLICATE-SOAR-CASE` | FAIL (`0.7818`) | **FAIL** (`0.7815`) | `TRUE_POSITIVE` | 3 | \$0.00 |
| `CASE-GEN3-05-RANSOMWARE-ESCALATION` | FAIL (`0.7836`) | **FAIL** (`0.7601`) | `TRUE_POSITIVE` | 2 | \$0.00 |
| `CASE-GEN3-06-AMBIGUOUS-DNS-TUNNEL` | FAIL (`0.5808`) | **FAIL** (`0.5819`) | `TRUE_POSITIVE` | 4 | \$0.00 |
| `CASE-GEN3-07-LATERAL-MOVEMENT-PSEXEC` | FAIL (`0.7832`) | **FAIL** (`0.7828`) | `TRUE_POSITIVE` | 1 | \$0.00 |
| `CASE-GEN3-08-SUPPLY-CHAIN-REVOKED-CERT` | FAIL (`0.7788`) | **FAIL** (`0.7803`) | `TRUE_POSITIVE` | 2 | \$0.00 |
| `CASE-GEN3-09-TOOL-503-OUTAGE-RESILIENCE` | FAIL (`0.7310`) | **FAIL** (`0.7726`) | `FALSE_POSITIVE` | 3 | \$250.00 |
| `CASE-GEN3-10-AUTHORIZED-SCANNER-NOISE` | FAIL (`0.5808`) | **FAIL** (`0.5813`) | `FALSE_POSITIVE` | 3 | \$50.00 |

---

## 4. Experiment B: Gen 5 `validation` 20-Case Hierarchical Triage (`clean_skills` vs `harness2_evolved`)

Loaded strictly via `scripts/gen5_exposure.py:load_split('validation', ...)` (`20` cases across 10 scenario families; `configs/evals/gen5/final_test.json` remained sealed with `0` exposures). For `clean_skills`, `skills/secops-triage/SKILL.md` (`376` words) was mapped across the 4 `HierarchicalSOCTier1Agent` classification runbook keys (`get_ip_report` / `get_case` / `udm_search` normalized to local worker epistemic tool names). For `harness2_evolved`, the 4 recursive-evolved runbooks in `configs/runbooks/harness2_evolved` (`1,256` total words) were loaded directly.

| Model | Runbook / Skill Arm | Words | Mean Harbor 60/20/20 | Pass Rate (>=0.80) | `MALICIOUS` | `BENIGN` | `SUSPICIOUS` | `INCONCLUSIVE` | $d'$ | $c$ | Simulated Loss (USD) | Safety Viol |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **`deepseek-v4.1-flash-1017-maas`** | **`clean_skills` (`SKILL.md`)** | `376` | **0.9651** | 95.0% | 0.9627 | 0.9739 | 0.9793 | 0.882 | 3.29 | 0.00 | \$1.01 | 0 |
| **`deepseek-v4.1-flash-1017-maas`** | **`harness2_evolved`** | `1256` | **0.9744** | 100.0% | 0.9764 | 0.9734 | 0.9725 | 0.9697 | 3.29 | 0.00 | \$1.01 | 0 |
| `gemini-2.5-flash` (Ref) | `clean_skills` (Harbor Ref) | `370` | `0.9612` | - | - | - | - | - | - | - | - | `0` |
| `gemini-2.5-flash` (Ref) | `harness2_k2_evolved` | `1,743` | `0.9723` | `100.0%` | `0.9850` | `0.9850` | `0.9005` | `0.9850` | `2.49` | `-0.40` | \$5,250.87 | `0` |
| `gemini-2.5-flash` (Ref) | `r1_gepa_w350_s101` (Best) | `2,119` | `0.9898` | `100.0%` | `1.0000` | `1.0000` | `0.9321` | `1.0000` | - | - | - | `0` |
| `gemini-2.5-flash-lite` (Ref) | `harness2_k2_evolved` | `1,743` | `0.9840` | `100.0%` | `0.9850` | `0.9827` | `0.9834` | `0.9850` | `2.91` | `-0.23` | \$251.02 | `0` |
| `gemini-2.5-flash-lite` (Ref) | `arena_grafted_all4_w300` | `1,260` | `0.9869` | `100.0%` | `0.9710` | `1.0000` | `1.0000` | `1.0000` | - | - | - | `0` |
| `gemini-3.5-flash-lite` (Ref) | `harness2_k2_evolved` | `1,743` | `0.9848` | `100.0%` | `0.9850` | `0.9850` | `0.9834` | `0.9850` | `3.27` | `-0.10` | \$0.84 | `0` |

---

## 5. Experiment C: Track 2 Proactive Threat Hunting (`ursnif_gti_hunt_suite.json`, 4 Scenarios)

| Model | Runbook Arm | Mean Hunt Composite | Mean Harbor 60/20/20 | Verdict Acc | `72h -> 168h` Widening | Patient Zero (`malwaretest-win`) | LOLBin Safe (`rundll32.exe`) | Mean Epistemic Steps | Mean Latency (s) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | ---: |
| **`deepseek-v4.1-flash-1017-maas`** | `compressed_track_b_hunt` | **0.9812** | `0.9400` | `100%` | `100%` | `100%` | `100%` | 7.8 | 86.3s |
| **`deepseek-v4.1-flash-1017-maas`** | `harness2_evolved_hunt` | **1.0000** | `0.9440` | `100%` | `100%` | `100%` | `100%` | 7.5 | 85.3s |
| `gemini-2.5-flash` (Ref) | `compressed_track_b_hunt` | `0.9719` | `0.9640` | `100%` | `100%` | `100%` | `100%` | `6.0` | - |
| `gemini-2.5-flash` (Ref) | `harness2_evolved_hunt` | `0.9719` | `0.9560` | `100%` | `100%` | `100%` | `100%` | `6.2` | - |
| `gemini-2.5-flash-lite` (Ref) | `harness2_evolved_hunt` | `1.0000` | `0.9560` | `100%` | `100%` | `100%` | `100%` | `6.5` | - |

---

## 6. Budget Ledger & Zero-GPU Infrastructure Audit Receipt

- **Audit Timestamp (UTC):** `2026-11-26T03:02:15Z`
- **Verification Method:** Python `google.auth.default()` REST inspection across Vertex AI `endpoints` and Compute Engine `aggregated/instances`
- **Active Vertex AI GPU Endpoints (`us-central1`, `us-east1`, `us-west1`, `europe-west4`):** `0`
- **Active GCE Spot or GPU-Attached VMs:** `0`
- **Dedicated GPU Hourly Spend:** \$0.00/hr
- **Budget Ledger Path:** `docs/soc_eval_results/deepseek_v41_budget_ledger.json` (\$0.8573 spent of \$10.00 ceiling across `375` ledger records)

### Reproducible CLI Invocation

```bash
.venv/bin/python scripts/run_deepseek_v41_eval_campaign.py \
  --max-usd 10.0 \
  --temperature 0.0 \
  --jev-backend gliner_decide \
  --resume-existing
```
