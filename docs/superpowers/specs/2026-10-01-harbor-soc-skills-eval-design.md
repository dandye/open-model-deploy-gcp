# Harbor SOC Tier 1 Interactive Skills Evaluation Suite Design Spec

- **Date:** 2026-10-01
- **Status:** Approved
- **Author:** dandye
- **Target Repository:** `gemma_deploy` (`gemma_deploy__worktrees/harbor_soc_evals_v0001`)
- **Base Branch:** `disciplined_hillclimber_v0001`
- **Target Branch:** `harbor_soc_evals_v0001`
- **Related References:** `vladkol__harbor-gke-ext` (`task.toml` `schema_version = "1.3"`), SkillsBench (`arXiv:2602.12670`), Vlad Kolesnikov (*"Your Agent Is Only as Good as the Sandbox You Measured It In"*, Medium, Sep 2026), and `docs/superpowers/specs/2026-10-01-disciplined-hillclimber-design.md`.

---

## 1. Executive summary and problem statement

Our primary research hypothesis states: *"Smaller models with good skills matched larger models without them."* We also test a follow-on degradation hypothesis: degrading procedural skills with noise should cause smaller models to perform worse, and any benchmark where noisy skills score higher exposes evaluator miscalibration.

In earlier experiments (`karl_harbor_evals_v0001` and `karl_skills_obfuscation_v0001`), Harbor container evaluations covered only the 12 Google Cloud Developer (`gdo` and `gcd`) scenarios, while the 10 Gen 3 interactive Security Operations Center (SOC) scenarios (`CASE-GEN3-01` through `CASE-GEN3-10` in `configs/evals/gen3/soc_tier1_interactive.json`) ran exclusively inside the in-process Python harness (`scripts/eval_soc_agent.py`). Those experiments revealed two critical architectural findings:

1. **Skill discovery versus skill execution decoupling on smaller models:** When Harbor mounts skills only at `/harbor/skills/<skill-name>/SKILL.md`, frontier CLI harnesses such as Claude Code emit proprietary `Skill` or `Read` tool calls to load them, whereas smaller open-weight models (`gemma-3-4b-it`, `gemma-4-e4b-it`) do not emit those harness-specific file-read calls and never load the skill into context.
2. **LLM-as-a-judge verbosity bias under noisy skills:** In text-only evaluations without container state verification, adding historical filler (`verbose_lore.md`) caused smaller models (`gemini-2.5-flash-lite`, `gemma-4-26b-a4b-it-maas`) to generate longer, more elaborate responses that scored higher under generative LLM-as-a-judge rubrics. In contrast, executing the degraded skill inside a real Harbor container sandbox dropped overall scores from `0.7742` to `0.6900` and exposed severe procedural failures.

This specification defines a native Harbor Framework (`harbor-gke-ext` compatible, `schema_version = "1.3"`) container evaluation suite for the 10 Gen 3 interactive SOC scenarios across three experimental arms (`no_skills`, `clean_skills`, and `noisy_skills`, totaling 30 Harbor task directories), paired with an exported `skills/secops-triage/evals/evals.json` manifest for NVIDIA `SkillEvaluator` compatibility.

---

## 2. System architecture and execution flow

```
+-----------------------------------------------------------------------------------+
|                   GENERATOR: scripts/generate_harbor_soc_tasks.py                 |
|  Inputs:                                                                          |
|  - configs/evals/gen3/soc_tier1_interactive.json (10 Gen 3 interactive cases)     |
|  - skills/secops-triage/SKILL.md (clean operational triage & containment rules)   |
|  - skills/secops-triage/noisy/verbose_lore.md (degraded verbose/hedged control)   |
|  Outputs:                                                                         |
|  - evals/harbor_soc/{no_skills,clean_skills,noisy_skills}/case-01..10/ (30 tasks) |
|  - skills/secops-triage/evals/evals.json (SkillEvaluator declarative manifest)    |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|            SHARED CONTAINER ENVIRONMENT (Byte-Identical Across 30 Tasks)          |
|  - environment/Dockerfile (Python 3.11 slim + /usr/local/bin/soc-cli + verifier)  |
|  - environment/soc_environment.py & soc_tier1_interactive.json                    |
|  - SHA-256 context deduplication: harbor-gke-ext-prebuild builds 1 shared image   |
|  - Case selection injected via task.toml env: SOC_CASE_ID & SOC_SKILL_ARM         |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                     AGENT OR ORACLE EXECUTION INSIDE CONTAINER                    |
|  - Reads task prompt & embedded skill arm from instruction.md                     |
|  - Invokes /usr/local/bin/soc-cli <tool_or_action> [--arg val ...]                |
|  - Mutates persistent state at /var/lib/soc/state.json                            |
|  - Appends every tool call & observation to /logs/artifacts/trajectory.jsonl      |
|  - Writes final report to /logs/artifacts/triage_report.md & soc_decision.json    |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                   VERIFIER: tests/test.sh -> verify_harbor_soc.py                 |
|  - Evaluates /var/lib/soc/state.json, trajectory.jsonl, and triage_report.md      |
|  - Computes 60% State/Safety + 20% Action Economy + 20% Assertions/Jev Rubric     |
|  - Writes scalar [0.0000..1.0000] to /logs/verifier/reward.txt & reward.json      |
+-----------------------------------------------------------------------------------+
```

---

## 3. Experimental arms and skill provisioning

The task generator (`scripts/generate_harbor_soc_tasks.py`) produces 30 Harbor task directories organized under `evals/harbor_soc/<arm>/<case_slug>/`, where `<arm>` is one of:

1. **`no_skills` (Unassisted Baseline Arm):**
   - `instruction.md` contains the incident alert prompt, CMDB asset context, `/usr/local/bin/soc-cli` command syntax reference, and the required artifact output paths (`/logs/artifacts/triage_report.md` and `/logs/artifacts/soc_decision.json`).
   - No procedural triage or containment skill directives are included.
2. **`clean_skills` (Counter-Prior Operational Skill Arm):**
   - `instruction.md` embeds the full text of `skills/secops-triage/SKILL.md` directly inside a `# Security Operations Triage Skill (secops-triage)` section prior to the incident prompt.
   - The clean skill codifies four non-spoiling operational rules:
     1. **Asset blast-radius and downtime cost awareness:** High-criticality and critical assets incur severe false-positive downtime loss (`$50,000` on critical infrastructure).
     2. **Mandatory epistemic corroboration:** Never execute state-changing containment (`isolate_host`, `block_indicator`) or case closure (`close_case`) at step 0 without first querying epistemic tools (`get_ip_report`, `get_domain_report`, `get_file_report`, `lookup_entity`, `list_cases`, `get_case`, `udm_search`).
     3. **Network routing, certificate, and service verification:** Check whether an IP belongs to non-routable documentation subnets (`RFC-5737`), whether a binary signature certificate is revoked (`REVOKED_CERTIFICATE` / `REVOKED_BY_CA`), whether an open SOAR case already tracks the indicator, and whether internal scanning originates from an authorized service before isolating hosts.
     4. **Degraded-mode outage resilience:** When an upstream threat intelligence tool returns HTTP `503 Service Unavailable`, do not retry in an infinite loop and do not guess a benign or malicious verdict; record the degraded status via `update_case_comment` and keep the case open without isolating the host.
3. **`noisy_skills` (Degraded Verbosity-Bias Negative Control Arm):**
   - `instruction.md` embeds `skills/secops-triage/noisy/verbose_lore.md`, which wraps the SOC operational concepts in sprawling historical anecdotes, passive hedging, and unformatted prose paragraphs.
   - Serves as a negative control: if an evaluator scores `noisy_skills` higher than `clean_skills`, the evaluator is over-rewarding prose length rather than operational containment accuracy and epistemic efficiency.

To ensure zero container build duplication across arms, the skill markdown is injected into each task's `instruction.md` (which Harbor mounts at runtime without rebuilding the container image) rather than baked into `environment/`.

---

## 4. `harbor-gke-ext` task structure and image deduplication

Each of the 30 task directories under `evals/harbor_soc/<arm>/<case_slug>/` contains:

```
evals/harbor_soc/<arm>/<case_slug>/
├── task.toml
├── instruction.md
├── environment/
│   ├── Dockerfile
│   ├── soc_environment.py
│   ├── soc_sandbox_cli.py
│   ├── verify_harbor_soc.py
│   ├── eval_trajectory_verifier.py
│   ├── eval_cost_engine.py
│   ├── jev_judge.py
│   ├── jev_evaluator.py
│   └── soc_tier1_interactive.json
├── solution/
│   └── solve.sh
└── tests/
    └── test.sh
```

### 4.1 `task.toml` schema v1.3 contract

Every `task.toml` conforms to `vladkol__harbor-gke-ext` `schema_version = "1.3"`:

```toml
version = "1.0"
schema_version = "1.3"

[task]
name = "soc-clean_skills-case-01-lokibot-c2"
description = "Lokibot C2 InfoStealer Host Containment (clean_skills arm)"
categories = ["security", "soc-tier1", "gen3-interactive", "clean_skills"]

[metadata]
author_name = "Dan Dye"
author_email = "dandye@google.com"
difficulty = "medium"
category = "security-operations"
tags = ["secops", "soc-tier1", "harbor", "clean_skills", "CASE-GEN3-01-LOKIBOT-C2"]
eval_id = "CASE-GEN3-01-LOKIBOT-C2"
skill_arm = "clean_skills"
asset_criticality = "STANDARD"
ground_truth_label = "MALICIOUS"

[verifier]
timeout_sec = 120.0

[agent]
timeout_sec = 300.0

[environment]
build_timeout_sec = 300.0
cpus = 2
memory_mb = 2048
storage_mb = 4096
allow_internet = false

[environment.env]
SOC_CASE_ID = "CASE-GEN3-01-LOKIBOT-C2"
SOC_SKILL_ARM = "clean_skills"
SOC_STATE_FILE = "/var/lib/soc/state.json"
SOC_TRAJECTORY_FILE = "/logs/artifacts/trajectory.jsonl"

[agent.env]
SOC_CASE_ID = "CASE-GEN3-01-LOKIBOT-C2"
SOC_SKILL_ARM = "clean_skills"
SOC_STATE_FILE = "/var/lib/soc/state.json"
SOC_TRAJECTORY_FILE = "/logs/artifacts/trajectory.jsonl"

[verifier.env]
SOC_CASE_ID = "CASE-GEN3-01-LOKIBOT-C2"
SOC_SKILL_ARM = "clean_skills"
SOC_STATE_FILE = "/var/lib/soc/state.json"
SOC_TRAJECTORY_FILE = "/logs/artifacts/trajectory.jsonl"
SOC_JEV_BACKEND = "mock"

[solution.env]
SOC_CASE_ID = "CASE-GEN3-01-LOKIBOT-C2"
SOC_SKILL_ARM = "clean_skills"
SOC_STATE_FILE = "/var/lib/soc/state.json"
SOC_TRAJECTORY_FILE = "/logs/artifacts/trajectory.jsonl"
```

### 4.2 Content-addressable `environment/` deduplication invariant

In `vladkol__harbor-gke-ext`, `CloudBuildPlugin` and `harbor-gke-ext-prebuild` hash the files inside each task's `environment/` directory (`compute_context_hash`) to deduplicate container image builds. Therefore, all 30 generated tasks must have byte-identical `environment/` directories. All per-case and per-arm specialization is passed via `task.toml` environment variables (`SOC_CASE_ID`, `SOC_SKILL_ARM`), `instruction.md`, and `solution/solve.sh`.

---

## 5. Container sandbox CLI (`soc-cli`) and state persistence

Inside the container, `/usr/local/bin/soc-cli` (implemented by `scripts/soc_sandbox_cli.py` and copied into `/app/soc_sandbox_cli.py`) wraps `SocEnvironment` (`agent/soc_environment.py`) with file-backed state persistence at `SOC_STATE_FILE` (default `/var/lib/soc/state.json`) and trajectory logging at `SOC_TRAJECTORY_FILE` (default `/logs/artifacts/trajectory.jsonl`).

### 5.1 Supported subcommands

1. **Epistemic investigation tools (read-only):**
   - `soc-cli get_ip_report --ip <IP>` (alias: `get_ip_address_report`)
   - `soc-cli get_domain_report --domain <DOMAIN>`
   - `soc-cli get_file_report --file_hash <SHA256>`
   - `soc-cli lookup_entity --entity_id <HOST_OR_IP> [--entity_type host]` (alias: `summarize_entity`)
   - `soc-cli list_cases [--query <FILTER>]`
   - `soc-cli get_case --case_id <CASE_ID>` (alias: `fetch_alert_data`)
   - `soc-cli udm_search --query <UDM_QUERY>`
2. **Pragmatic state-changing actions (interventions):**
   - `soc-cli isolate_host --hostname <HOST_OR_IP>`
   - `soc-cli unblock_host --hostname <HOST_OR_IP>`
   - `soc-cli block_indicator --indicator <DOMAIN_IP_OR_HASH>`
   - `soc-cli update_case_comment --case_id <CASE_ID> --comment <TEXT>`
   - `soc-cli close_case --case_id <CASE_ID> [--verdict <VERDICT>]`
3. **Lifecycle and diagnostic subcommands (not counted as agent trajectory steps):**
   - `soc-cli reset [--case-id <CASE_ID>]`: Initializes `/var/lib/soc/state.json` from `SocEnvironment.from_eval_case(case)` (automatically injecting configured faults such as HTTP 503 on `get_domain_report` for `CASE-GEN3-09-TOOL-503-OUTAGE-RESILIENCE`) and truncates `/logs/artifacts/trajectory.jsonl`.
   - `soc-cli status`: Prints the current serialized state snapshot from `/var/lib/soc/state.json`.

### 5.2 Flexible argument parsing for smaller models

To prevent brittle CLI flag syntax errors on 4B-parameter models while maintaining strict state evaluation, `soc-cli` accepts:
- Standard flags (`--ip`, `--domain`, `--file_hash`, `--hash`, `--entity_id`, `--hostname`, `--host`, `--indicator`, `--case_id`, `--comment`, `--verdict`, `--query`).
- Single positional arguments mapped to the subcommand's primary key (for example, `soc-cli get_domain_report update-service-win32.com` or `soc-cli isolate_host DESKTOP-FIN-08`).
- Inline JSON object arguments via `--json '{"domain": "update-service-win32.com"}'`.

---

## 6. Continuous verifier reward formula (`tests/test.sh` and `verify_harbor_soc.py`)

When an agent or `solution/solve.sh` finishes, Harbor executes `tests/test.sh`, which runs `/app/verify_harbor_soc.py` and writes a scalar float in `[0.0000, 1.0000]` to `/logs/verifier/reward.txt` and a detailed JSON scorecard to `/logs/verifier/reward.json`.

For each case, the total reward $R \in [0.0000, 1.0000]$ is the sum of three components:

$$R = R_{\text{state}} + R_{\text{economy}} + R_{\text{quality}}$$

### 6.1 Component 1: Deterministic state and safety ($R_{\text{state}} \in [0.00, 0.60]$)

1. **Epistemic investigation gate (`0.20`):**
   - Awards `0.20` if `epistemic_step_count >= 1` in `/logs/artifacts/trajectory.jsonl` (verified via `verify_agent_trajectory()`), else `0.00`.
2. **Operator action execution (`0.20`):**
   - Awards `0.20` if `operator_actions_matched` is `True` (all required primary actions in `expected_actions` were executed via `soc-cli`, or secondary actions when the case defines only secondary actions such as `update_case_comment` in `CASE-GEN3-04`, `CASE-GEN3-06`, and `CASE-GEN3-09`), else `0.00`.
3. **Prohibited action avoidance and zero catastrophic financial loss (`0.20`):**
   - Computes the decision outcome (`TRUE_POSITIVE`, `FALSE_POSITIVE`, `TRUE_NEGATIVE`, `FALSE_NEGATIVE`) and dollar operational loss $L_{\text{op}}$ via `classify_decision_outcome()` and `calculate_operational_loss()` in `scripts/eval_cost_engine.py`, with loss penalty $P_{\text{loss}} = \exp(-L_{\text{op}} / 10000.0)$.
   - Awards `0.20 * P_loss` if `prohibited_actions_avoided` is `True`, else `0.00`.

### 6.2 Component 2: Epistemic action economy ($R_{\text{economy}} \in [0.00, 0.20]$)

- Computes `efficiency = calculate_epistemic_efficiency(trajectory)` from `scripts/eval_trajectory_verifier.py` (`1.0` for 1-4 non-redundant epistemic queries without loops; penalized for duplicate queries, 2-step cycles, or >4 queries; `0.0` if `epistemic_step_count == 0`).
- Awards $R_{\text{economy}} = 0.20 \times \text{efficiency}$ when `epistemic_step_count >= 1`, else `0.00`.

### 6.3 Component 3: Assertions and Jev System-One rubric ($R_{\text{quality}} \in [0.00, 0.20]$)

1. **Deterministic entity and IOC assertions (`0.10`):**
   - Reads `/logs/artifacts/triage_report.md` (falling back to `/logs/artifacts/soc_decision.json` if only JSON was written).
   - Evaluates all `must_contain` (case-insensitive substring match) and `must_not_contain` checks from `soc_tier1_interactive.json`.
   - Awards `0.10 * (matched_checks / total_checks)` when `epistemic_step_count >= 1` (to prevent ungrounded zero-tool text guesses from farming assertion points), else `0.00`.
2. **Jev System-One calibrated score and grounding (`0.10`):**
   - Evaluates the serialized state (`build_soc_evaluation_state`) through `JevSocJudgeEvaluator` (`agent/jev_evaluator.py`).
   - Uses `MockJevBackend` (`SOC_JEV_BACKEND=mock`, default in air-gapped containers) or `GeminiSystem1Backend` (`SOC_JEV_BACKEND=gemini` when Vertex AI credentials are mounted).
   - Computes `jev_unit = 0.5 * (jev_out.rubric_score / 100.0) + 0.5 * jev_out.grounding_score` and awards `0.10 * jev_unit` when `epistemic_step_count >= 1`, else `0.00`.

---

## 7. Reference oracle solutions (`solution/solve.sh`)

Every task includes an executable `solution/solve.sh` that:
1. Runs `soc-cli reset` to ensure a clean initial state.
2. Executes the minimum sufficient epistemic `soc-cli` queries for `SOC_CASE_ID` (1-2 steps, yielding `epistemic_efficiency == 1.0`).
3. Executes the exact `expected_actions` for `SOC_CASE_ID` via `soc-cli` while avoiding all `prohibited_actions`.
4. Writes a grounded `/logs/artifacts/triage_report.md` and `/logs/artifacts/soc_decision.json` satisfying all `must_contain` and `must_not_contain` assertions.

Running `solution/solve.sh` followed by `tests/test.sh` is guaranteed to produce `1.0000` in `/logs/verifier/reward.txt` across all 30 tasks (`harbor run -a oracle` calibration invariant).

---

## 8. File map and test deliverables

| File Path | Responsibility |
| :--- | :--- |
| `skills/secops-triage/SKILL.md` | Clean counter-prior SOC Tier 1 triage and containment skill. |
| `skills/secops-triage/noisy/verbose_lore.md` | Degraded noisy SOC skill (historical filler, passive hedging, buried structure) for verbosity-bias negative control. |
| `skills/secops-triage/evals/evals.json` | Exported 10-case declarative evaluation manifest for NVIDIA `SkillEvaluator` and `scripts/eval_declarative.py`. |
| `scripts/soc_sandbox_cli.py` | Container-ready CLI (`soc-cli`) wrapping `SocEnvironment` with `/var/lib/soc/state.json` persistence and `/logs/artifacts/trajectory.jsonl` logging. |
| `scripts/verify_harbor_soc.py` | Container verifier computing the 60/20/20 composite reward and writing `/logs/verifier/reward.txt` and `/logs/verifier/reward.json`. |
| `scripts/generate_harbor_soc_tasks.py` | Generator producing the 30 Harbor task directories (`evals/harbor_soc/<arm>/case-01..10/`) with byte-identical `environment/` contexts and `skills/secops-triage/evals/evals.json`. |
| `tests/test_harbor_soc_evals.py` | Pytest suite testing `soc_sandbox_cli.py`, `verify_harbor_soc.py`, task generation, `environment/` SHA-256 deduplication, and 100% oracle calibration (`reward == 1.0000`) across all 10 cases. |
