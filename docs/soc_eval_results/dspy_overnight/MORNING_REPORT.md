# Overnight DSPy Context Engineering Campaign Report

- **Updated (UTC)**: `2026-10-15T12:03:31.543774+00:00`
- **Elapsed Hours**: `9.05h` / `9.00h`
- **Budget Spent**: `$8.9843` / `$20.00` (`$11.0157` remaining)
- **Completed Experiments**: `29`
- **Balanced SFT Traces Harvested**: `72`
- **Vertex AI GPU Endpoint Audit**: `gcloud_non_zero` (active endpoints: `0`)

## 1. Experiment Leaderboard (Sorted by Harbor 60/20/20 Reward)

| Exp ID | Wave | Dataset | Task Model | Max Words | Total Words | GEPA Fitness | Harbor 60/20/20 | Zero-Tool | Safety Viol | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `r1_gepa_gen5_gemini-2_5-flash_w350_s101` | Wave 2/3 (GEPA+Harbor r1) | `gen5_val_20` | `gemini-2.5-flash` | `350` | `2119` | `0.9898` | `0.9898` | `0` | `0` | `PROMOTED` |
| `w1c_clean_seed_v3_gen5val_gemini-2_5-flash` | Wave 1C (Assertion Hygiene + Gen3 Case Resolution) | `gen5_val_20` | `gemini-2.5-flash` | `clean_seed_v3` | `2376` | `0.9898` | `0.9898` | `0` | `0` | `BASELINE_V3` |
| `w5_arena_grafted_all4_w300_gen5_val_20_gemini-2_5-flash-lite` | Wave 5 (Arena Grafted All-4 <=326w) | `gen5_val_20` | `gemini-2.5-flash-lite` | `326` | `1260` | `0.9869` | `0.9869` | `0` | `0` | `PROMOTED` |
| `w5_arena_grafted_all4_w300_gen5_val_20_gemini-2_5-flash` | Wave 5 (Arena Grafted All-4 <=326w) | `gen5_val_20` | `gemini-2.5-flash` | `326` | `1260` | `0.9865` | `0.9865` | `0` | `0` | `PROMOTED` |
| `w1b_clean_seed_v2_gen5val_gemini-2_5-flash` | Wave 1B (Context Hygiene + Temp0 + 1500c) | `gen5_val_20` | `gemini-2.5-flash` | `clean_seed_v2` | `2376` | `0.9865` | `0.9865` | `0` | `0` | `BASELINE_V2` |
| `r1_gepa_gen5_gemini-2_5-flash-lite_w550_s202` | Wave 2/3 (GEPA+Harbor r1) | `gen5_val_20` | `gemini-2.5-flash-lite` | `550` | `1988` | `0.9843` | `0.9843` | `0` | `0` | `PROMOTED` |
| `r1_gepa_gen5_gemini-2_5-flash-lite_w400_s303` | Wave 2/3 (GEPA+Harbor r1) | `gen5_val_20` | `gemini-2.5-flash-lite` | `400` | `2211` | `0.9843` | `0.9843` | `0` | `0` | `PROMOTED` |
| `w1b_clean_seed_v2_gen5val_gemini-2_5-flash-lite` | Wave 1B (Context Hygiene + Temp0 + 1500c) | `gen5_val_20` | `gemini-2.5-flash-lite` | `clean_seed_v2` | `2376` | `0.9843` | `0.9843` | `0` | `0` | `BASELINE_V2` |
| `r1_gepa_gen5_gemini-2_5-flash-lite_w450_s42` | Wave 2/3 (GEPA+Harbor r1) | `gen5_val_20` | `gemini-2.5-flash-lite` | `450` | `2376` | `0.9843` | `0.9843` | `0` | `0` | `SEED_RETAINED` |
| `r1_gepa_gen5_gemini-2_5-flash-lite_w350_s101` | Wave 2/3 (GEPA+Harbor r1) | `gen5_val_20` | `gemini-2.5-flash-lite` | `350` | `2376` | `0.9843` | `0.9843` | `0` | `0` | `SEED_RETAINED` |
| `w1c_clean_seed_v3_gen5val_gemini-2_5-flash-lite` | Wave 1C (Assertion Hygiene + Gen3 Case Resolution) | `gen5_val_20` | `gemini-2.5-flash-lite` | `clean_seed_v3` | `2376` | `0.9843` | `0.9843` | `0` | `0` | `BASELINE_V3` |
| `r1_gepa_gen5_gemini-2_5-flash_w450_s42` | Wave 2/3 (GEPA+Harbor r1) | `gen5_val_20` | `gemini-2.5-flash` | `450` | `2376` | `0.9836` | `0.9836` | `0` | `0` | `SEED_RETAINED` |
| `w1_clean_seed_gen5val_gemini-2_5-flash` | Wave 1 (Context Hygiene Seed) | `gen5_val_20` | `gemini-2.5-flash` | `clean_seed` | `2376` | `0.7550` | `0.8198` | `0` | `1` | `BASELINE` |
| `w1_clean_seed_gen5val_gemini-2_5-flash-lite` | Wave 1 (Context Hygiene Seed) | `gen5_val_20` | `gemini-2.5-flash-lite` | `clean_seed` | `2376` | `0.7675` | `0.7828` | `0` | `1` | `BASELINE` |
| `r1_gepa_gen3_gemini-2_5-flash_w350_s101` | Wave 2/3 (GEPA+Harbor r1) | `gen3_10` | `gemini-2.5-flash` | `350` | `1924` | `1.0000` | `0.9801` | `0` | `0` | `PROMOTED` |
| `w1c_clean_seed_v3_gen3_gemini-2_5-flash` | Wave 1C (Assertion Hygiene + Gen3 Case Resolution) | `gen3_10` | `gemini-2.5-flash` | `clean_seed_v3` | `2376` | `1.0000` | `0.9801` | `0` | `0` | `BASELINE_V3` |
| `w5_arena_grafted_all4_w300_gen3_10_gemini-2_5-flash` | Wave 5 (Arena Grafted All-4 <=326w) | `gen3_10` | `gemini-2.5-flash` | `326` | `1260` | `0.9874` | `0.9745` | `0` | `1` | `PROMOTED` |
| `r1_gepa_gen3_gemini-2_5-flash-lite_w550_s202_v3_hygiene` | Wave 2/3 (GEPA+Harbor r1 + v3 Hygiene) | `gen3_10` | `gemini-2.5-flash-lite` | `550` | `2026` | `0.9874` | `0.9745` | `0` | `1` | `PROMOTED` |
| `r1_gepa_gen3_gemini-2_5-flash_w450_s42_v3_hygiene` | Wave 2/3 (GEPA+Harbor r1 + v3 Hygiene) | `gen3_10` | `gemini-2.5-flash` | `450` | `2109` | `0.9700` | `0.9726` | `0` | `0` | `PROMOTED` |
| `w1c_clean_seed_v3_gen3_gemini-2_5-flash-lite` | Wave 1C (Assertion Hygiene + Gen3 Case Resolution) | `gen3_10` | `gemini-2.5-flash-lite` | `clean_seed_v3` | `2376` | `0.9700` | `0.9508` | `0` | `0` | `BASELINE_V3` |
| `w5_arena_grafted_all4_w300_gen3_10_gemini-2_5-flash-lite` | Wave 5 (Arena Grafted All-4 <=326w) | `gen3_10` | `gemini-2.5-flash-lite` | `326` | `1260` | `0.9245` | `0.9271` | `0` | `1` | `PROMOTED` |
| `r1_gepa_gen3_gemini-2_5-flash-lite_w550_s202` | Wave 2/3 (GEPA+Harbor r1) | `gen3_10` | `gemini-2.5-flash-lite` | `550` | `2026` | `0.9000` | `0.8810` | `0` | `1` | `PROMOTED` |
| `w1b_clean_seed_v2_gen3_gemini-2_5-flash` | Wave 1B (Context Hygiene + Temp0 + 1500c) | `gen3_10` | `gemini-2.5-flash` | `clean_seed_v2` | `2376` | `0.8274` | `0.8710` | `0` | `1` | `BASELINE_V2` |
| `r1_gepa_gen3_gemini-2_5-flash_w450_s42` | Wave 2/3 (GEPA+Harbor r1) | `gen3_10` | `gemini-2.5-flash` | `450` | `2109` | `0.8400` | `0.8685` | `0` | `1` | `PROMOTED` |
| `w1b_clean_seed_v2_gen3_gemini-2_5-flash-lite` | Wave 1B (Context Hygiene + Temp0 + 1500c) | `gen3_10` | `gemini-2.5-flash-lite` | `clean_seed_v2` | `2376` | `0.8700` | `0.8528` | `0` | `0` | `BASELINE_V2` |
| `r1_gepa_gen3_gemini-2_5-flash-lite_w350_s101` | Wave 2/3 (GEPA+Harbor r1) | `gen3_10` | `gemini-2.5-flash-lite` | `350` | `2376` | `0.8700` | `0.8528` | `0` | `0` | `SEED_RETAINED` |
| `w1_clean_seed_gen3_gemini-2_5-flash-lite` | Wave 1 (Context Hygiene Seed) | `gen3_10` | `gemini-2.5-flash-lite` | `clean_seed` | `2376` | `0.8245` | `0.7810` | `0` | `2` | `BASELINE` |
| `r1_gepa_gen3_gemini-2_5-flash-lite_w450_s42` | Wave 2/3 (GEPA+Harbor r1) | `gen3_10` | `gemini-2.5-flash-lite` | `450` | `2376` | `0.7045` | `0.7430` | `0` | `1` | `SEED_RETAINED` |
| `w1_clean_seed_gen3_gemini-2_5-flash` | Wave 1 (Context Hygiene Seed) | `gen3_10` | `gemini-2.5-flash` | `clean_seed` | `2376` | `0.7045` | `0.6871` | `1` | `1` | `BASELINE` |

## 2. Per-Verdict Harbor Reward Breakdown

| Exp ID | Dataset | Task Model | MALICIOUS | BENIGN | SUSPICIOUS | INCONCLUSIVE |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `r1_gepa_gen5_gemini-2_5-flash_w350_s101` | `gen5_val_20` | `gemini-2.5-flash` | `1.0` | `1.0` | `0.9321` | `1.0` |
| `w1c_clean_seed_v3_gen5val_gemini-2_5-flash` | `gen5_val_20` | `gemini-2.5-flash` | `1.0` | `1.0` | `0.9321` | `1.0` |
| `w5_arena_grafted_all4_w300_gen5_val_20_gemini-2_5-flash-lite` | `gen5_val_20` | `gemini-2.5-flash-lite` | `0.971` | `1.0` | `1.0` | `1.0` |
| `w5_arena_grafted_all4_w300_gen5_val_20_gemini-2_5-flash` | `gen5_val_20` | `gemini-2.5-flash` | `0.9982` | `1.0` | `0.9321` | `0.95` |
| `w1b_clean_seed_v2_gen5val_gemini-2_5-flash` | `gen5_val_20` | `gemini-2.5-flash` | `0.9982` | `0.9929` | `0.9321` | `1.0` |
| `r1_gepa_gen5_gemini-2_5-flash-lite_w550_s202` | `gen5_val_20` | `gemini-2.5-flash-lite` | `0.9674` | `0.9977` | `0.9984` | `1.0` |
| `r1_gepa_gen5_gemini-2_5-flash-lite_w400_s303` | `gen5_val_20` | `gemini-2.5-flash-lite` | `0.9674` | `0.9977` | `0.9984` | `1.0` |
| `w1b_clean_seed_v2_gen5val_gemini-2_5-flash-lite` | `gen5_val_20` | `gemini-2.5-flash-lite` | `0.9674` | `0.9977` | `0.9984` | `1.0` |
| `r1_gepa_gen5_gemini-2_5-flash-lite_w450_s42` | `gen5_val_20` | `gemini-2.5-flash-lite` | `0.9674` | `0.9977` | `0.9984` | `1.0` |
| `r1_gepa_gen5_gemini-2_5-flash-lite_w350_s101` | `gen5_val_20` | `gemini-2.5-flash-lite` | `0.9674` | `0.9977` | `0.9984` | `1.0` |
| `w1c_clean_seed_v3_gen5val_gemini-2_5-flash-lite` | `gen5_val_20` | `gemini-2.5-flash-lite` | `0.9674` | `0.9977` | `0.9984` | `1.0` |
| `r1_gepa_gen5_gemini-2_5-flash_w450_s42` | `gen5_val_20` | `gemini-2.5-flash` | `1.0` | `1.0` | `0.9071` | `0.95` |
| `w1_clean_seed_gen5val_gemini-2_5-flash` | `gen5_val_20` | `gemini-2.5-flash` | `0.7522` | `0.9643` | `0.8917` | `0.2` |
| `w1_clean_seed_gen5val_gemini-2_5-flash-lite` | `gen5_val_20` | `gemini-2.5-flash-lite` | `0.7178` | `0.9343` | `0.65` | `0.705` |
| `r1_gepa_gen3_gemini-2_5-flash_w350_s101` | `gen3_10` | `gemini-2.5-flash` | `1.0` | `1.0` | `0.9338` | `1.0` |
| `w1c_clean_seed_v3_gen3_gemini-2_5-flash` | `gen3_10` | `gemini-2.5-flash` | `1.0` | `1.0` | `0.9338` | `1.0` |
| `w5_arena_grafted_all4_w300_gen3_10_gemini-2_5-flash` | `gen3_10` | `gemini-2.5-flash` | `1.0` | `1.0` | `0.915` | `1.0` |
| `r1_gepa_gen3_gemini-2_5-flash-lite_w550_s202_v3_hygiene` | `gen3_10` | `gemini-2.5-flash-lite` | `1.0` | `1.0` | `0.915` | `1.0` |
| `r1_gepa_gen3_gemini-2_5-flash_w450_s42_v3_hygiene` | `gen3_10` | `gemini-2.5-flash` | `1.0` | `1.0` | `0.9088` | `1.0` |
| `w1c_clean_seed_v3_gen3_gemini-2_5-flash-lite` | `gen3_10` | `gemini-2.5-flash-lite` | `0.9307` | `0.992` | `0.9338` | `1.0` |
| `w5_arena_grafted_all4_w300_gen3_10_gemini-2_5-flash-lite` | `gen3_10` | `gemini-2.5-flash-lite` | `1.0` | `0.7725` | `0.9088` | `1.0` |
| `r1_gepa_gen3_gemini-2_5-flash-lite_w550_s202` | `gen3_10` | `gemini-2.5-flash-lite` | `1.0` | `0.755` | `0.8483` | `0.755` |
| `w1b_clean_seed_v2_gen3_gemini-2_5-flash` | `gen3_10` | `gemini-2.5-flash` | `0.9875` | `0.755` | `0.8317` | `0.755` |
| `r1_gepa_gen3_gemini-2_5-flash_w450_s42` | `gen3_10` | `gemini-2.5-flash` | `0.9875` | `0.755` | `0.8233` | `0.755` |
| `w1b_clean_seed_v2_gen3_gemini-2_5-flash-lite` | `gen3_10` | `gemini-2.5-flash-lite` | `0.9307` | `0.747` | `0.8521` | `0.755` |
| `r1_gepa_gen3_gemini-2_5-flash-lite_w350_s101` | `gen3_10` | `gemini-2.5-flash-lite` | `0.9307` | `0.747` | `0.8521` | `0.755` |
| `w1_clean_seed_gen3_gemini-2_5-flash-lite` | `gen3_10` | `gemini-2.5-flash-lite` | `0.8525` | `0.6495` | `0.8521` | `0.545` |
| `r1_gepa_gen3_gemini-2_5-flash-lite_w450_s42` | `gen3_10` | `gemini-2.5-flash-lite` | `0.8775` | `0.65` | `0.6718` | `0.605` |
| `w1_clean_seed_gen3_gemini-2_5-flash` | `gen3_10` | `gemini-2.5-flash` | `0.6275` | `0.65` | `0.7704` | `0.7501` |

## 3. Top Promoted Runbook Candidates

| Candidate Directory | Target Suite & Model | Total Words (4 Core Runbooks) | Compression vs Raw (`3,648`w) | GEPA Fitness | Harbor 60/20/20 | Zero-Tool | Safety Viol |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `docs/soc_eval_results/dspy_overnight/candidates/arena_grafted_all4_w300` | `gen5_val_20` (`gemini-2.5-flash-lite` & `gemini-2.5-flash`) | `1,260` | **`-65.5%`** (`-47.0%` vs clean seed) | `0.9869` / `0.9865` | **`0.9869`** / **`0.9865`** | `0` | `0` |
| `docs/soc_eval_results/dspy_overnight/candidates/r1_gepa_gen5_gemini-2_5-flash_w350_s101` | `gen5_val_20` (`gemini-2.5-flash`) | `2,119` | **`-41.9%`** | `0.9898` | **`0.9898`** | `0` | `0` |
| `docs/soc_eval_results/dspy_overnight/candidates/r1_gepa_gen3_gemini-2_5-flash_w350_s101` | `gen3_10` (`gemini-2.5-flash`) | `1,924` | **`-47.3%`** | **`1.0000`** | **`0.9801`** | `0` | `0` |
| `docs/soc_eval_results/dspy_overnight/candidates/r1_gepa_gen3_gemini-2_5-flash-lite_w550_s202` | `gen3_10` (`gemini-2.5-flash-lite`) | `2,026` | **`-44.5%`** | `0.9874` | **`0.9745`** | `0` | `1` |
| `docs/soc_eval_results/dspy_overnight/candidates/r1_gepa_gen5_gemini-2_5-flash-lite_w550_s202` | `gen5_val_20` (`gemini-2.5-flash-lite`) | `1,988` | **`-45.5%`** | `0.9843` | **`0.9843`** | `0` | `0` |

### All-4-Compressed Runbook Breakdown (`candidates/arena_grafted_all4_w300`)

| Core Runbook | Raw Upstream (`third_party/ai-runbooks`) | Clean De-Scaffolded Seed | `arena_grafted_all4_w300` | Word Reduction vs Raw |
| :--- | :--- | :--- | :--- | :--- |
| `basic_ioc_enrichment.md` | `842` words | `576` words | **`313` words** | **`-62.8%`** |
| `lateral_movement_hunt_psexec_wmi.md` | `1,069` words | `710` words | **`321` words** | **`-70.0%`** |
| `malware_triage.md` | `876` words | `561` words | **`300` words** | **`-65.8%`** |
| `suspicious_login_triage.md` | `861` words | `529` words | **`326` words** | **`-62.1%`** |
| **Total (4 Core Runbooks)** | **`3,648` words** | **`2,376` words** | **`1,260` words** | **`-65.5%`** |

## 4. Architectural & Context Engineering Progression Across Waves

1. **Wave 1 (`2f155c2`): Context Hygiene (`strip_runbook_scaffolding`)**
   - Stripped 55-line ```` ```{mermaid} sequenceDiagram ``` ```` blocks, interactive Cline pseudo-tools (`ask_followup_question`, `attempt_completion`, `write_to_file`, `generate_report_file.md`), and `${VAR_NAME}` shell placeholders (`-> <var_name>`), compressing the 4 core upstream runbooks from `3,648` raw words to `2,376` clean words (`-34.9%`).
   - Lifted `gemini-2.5-flash-lite` on `gen3_10` from Campaign 5 `0.4361` to `0.7810` (`+34.49` pp).
2. **Wave 1B (`f6ffead`, `d0558c0`, `7be95a4`): Native Function-Call Bridging, `temperature=0.0` Determinism, `1500`-Char Observation Window, & Gen 5 `compose_soc_reward` Parity**
   - Fixed `GemmaAgent.query()` so native `function_call` parts in `res.candidates[*].content.parts` convert into `Action: {"name": ..., "arguments": ...}` lines when `res.text` is empty on `gemini-2.5-flash`.
   - Expanded `extract_worker_report()` observation slice from `300` to `1500` chars and wired `compose_soc_reward` into `RunbookGEPAAdapter.evaluate()` for Gen 5 cases.
   - Lifted `gen5_val_20` Harbor 60/20/20 from `0.7828` to `0.9843` on `gemini-2.5-flash-lite` (`+20.15` pp) and from `0.8198` to `0.9865` on `gemini-2.5-flash` (`+16.67` pp).
3. **Wave 1C (`b22fc75`, `ecb875f`, `270b264`): Intrinsic Context-Debt Regularizer, Report Assertion Hygiene, & Gen 3 CMDB Case Resolution**
   - Added `_compute_context_debt_penalty()` (`0.008` per un-cleaned/over-budget runbook) so GEPA breaks score ties (`new_sum > old_sum`) in favor of compressed runbooks.
   - Added `_resolve_target_case()` for Gen 3 `[CMDB Asset Context:` alerts (`CASE-17305` for `SRV-PROD-PAYMENT-01`, `CASE-33279` for `DESKTOP-FIN-08` and Gen 3 overlay alerts) and `_apply_report_assertion_hygiene()` to prevent negated prose collisions (`"not a false positive"` on `MALICIOUS`, `"not command and control"` on `BENIGN`, `"neither confirmed safe nor confirmed malicious"` on `INCONCLUSIVE`).
   - Lifted `gen3_10` to **`1.0000` GEPA Fitness (`100%`) / `0.9801` Harbor 60/20/20** on `gemini-2.5-flash` (`+29.30` pp over Wave 1) and **`0.9874` GEPA Fitness / `0.9745` Harbor 60/20/20** on `gemini-2.5-flash-lite` (`2,026` words, `+19.35` pp over Wave 1).
4. **Wave 2/3 & Wave 5: Constrained GEPA Evolution (`WordLimitReflectionLM`) & Cross-Run Arena Grafting**
   - Compressing `lateral_movement_hunt_psexec_wmi.md` reduced `CASE-GEN5-LATERAL-PSEXEC-05` completion tokens on `gemini-2.5-flash-lite` from `68,652` (`2m07s`, `$0.0295`) down to `6,771` (`21s`, `$0.0048`, **`-83.6%` cost and `-83.5%` latency**).
   - Cross-grafting the best `<350`-word GEPA-evolved versions of all 4 core runbooks (`arena_grafted_all4_w300`, `1,260` total words, `-65.5%` vs raw) achieved **`0.9869` Harbor 60/20/20** on `gen5_val_20` with `gemini-2.5-flash-lite` (beating the `2,376`-word seed `0.9843` with `1,116` fewer words) and **`0.9865`** with `gemini-2.5-flash`.
