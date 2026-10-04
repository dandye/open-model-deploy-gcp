# Design spec: Gen 5 family-instanced SOC Tier 1 evaluation suite

- **Date:** 2026-10-04
- **Status:** Design approved section by section in review; spec pending review
- **Target repository:** `gemma_deploy__worktrees`
- **Base branch:** `disciplined_hillclimber_v0001` at `2cd283c`, with `harbor_soc_evals_v0001` (`e7dce8a`) and `main` (`9984390`) merged in
- **Target branch / worktree:** `gen5_evals_v0001` (created at `4ffadb3`)
- **Evalset id:** `soc_tier1_families`, `generation: 5`

---

## 1. Summary and motivation

Gen 5 is a family-templated, procedurally instanced SOC Tier 1 triage suite:
16 scenario families, 90 materialized cases, train / validation / final_test
splits defined by construction, executed unchanged through the Python
`SocEnvironment` sandbox and the Harbor `soc-cli` container, scored by one
verifier, and locked by the harness integrity guard.

It exists because the current Gen 3 suite cannot support the Disciplined
Hillclimber. The 2026-10-02 run
([`DISCIPLINED_HILLCLIMBER_RUN_ANALYSIS.md`](../../soc_eval_results/DISCIPLINED_HILLCLIMBER_RUN_ANALYSIS.md))
showed:

- The validation split is 4 cases (`eval_cases[6:]`). The seed scored 0.650,
  0.651, and 0.619 across three evaluations, a spread of 0.031, which is twice
  the acceptance threshold the run itself computed. Nothing can be accepted or
  rejected with confidence at that sample size.
- Every case shares one hard-coded world (`DESKTOP-FIN-08`, `198.51.100.42`,
  `update-service-win32.com`, and so on). A runbook that memorizes these
  literals passes the held-out cases because the held-out cases contain the
  same literals. The `validate_runbook_candidate` regex guard is the only thing
  standing between the optimizer and memorization.
- An agent that makes no tool calls and reaches no verdict receives a loss
  penalty of `exp(0) = 1.0`, so the Gemma rungs of the cost staircase reported
  0.31 to 0.34 while most likely doing nothing.
- Campaign 5 on the Harbor branch
  (`docs/eval_results/harbor_soc/gepa_evolved_sweep/`) found the GEPA-evolved
  runbooks below the clean skills on all three models. The same ten cases run
  in a different transport gave the opposite conclusion from the Python run.
  Gen 5 has to be defined once and executed through both transports so this
  can be attributed rather than argued.

The design follows the two frames summarized in
[`hillclimber_rrsi_crosswalk.md`](../../hillclimber_rrsi_crosswalk.md):
RRSI's evolve / held-out / OOD split discipline and Harness-Delta
Attribution's separation of generalization gain from artifact memorization and
token inflation.

### Decisions taken in design review

| Decision | Choice |
|---|---|
| Primary problem | Memorization-proof held-out splits (families plus instanced entities) |
| Scale | 16 families, 90 cases: train 40 / validation 20 / final_test 30 |
| Transports | `SocEnvironment` and Harbor `soc-cli` from day one, one verifier |
| Relationship to Gen 3 | Gen 5 becomes the default for the hillclimber, the Harbor generator, and the harness lock; Gen 3 stays as a frozen legacy suite |
| Instancing approach | Materialized instances from family templates via a deterministic instancer; runtime generation kept possible by recording `(family_id, instance_seed, pool_version)` |
| final_test composition | 10 in-distribution plus 20 OOD cases, so the memorization term can be measured |
| Harbor task check-in | Generated tasks are checked in; `validation` and `final_test` splits only; arms are a flag |

## 2. Goals and non-goals

### Goals

1. **Held-out splits by construction.** Train is the only split the optimizer's
   reflection step sees. Validation is the acceptance gate. Final test is
   sealed and includes families never exposed to optimization or selection.
2. **No literal memorization possible.** Every instance has its own hostnames,
   IPs, domains, hashes, users, case ids, and timestamps. No identifying
   literal appears in two cases or in the Gen 3 inventory.
3. **One case file, two transports, one verifier.** A hillclimber acceptance
   made in Python can be re-checked in the container on the same bytes.
4. **Inert agents score zero.** Liveness is part of the case contract.
5. **Discriminative power is reportable.** Each family declares a difficulty
   tier; each run records tokens, tool calls, and latency per case.

### Non-goals

- Live SecOps MCP cases. The Gen 2 and Gen 3 live sets stay as they are. The
  case schema carries a `transport` field (`sandbox` today) so a live family
  can be added later without a schema change.
- Changes to the Jev System One judge.
- Changes to runbook or skill content.
- Changes to the GEPA algorithm beyond split loading, the literal guard, and
  two correctness fixes named in section 7.3.
- New Harbor infrastructure. The existing generator, `soc-cli`, and verifier
  are extended, not replaced.

## 3. Constraints found in the code

Three facts about the current code shape the work and are prerequisites rather
than options.

1. **`_load_state` overlays, it does not replace.**
   [`SocEnvironment._load_state`](../../../agent/soc_environment.py) loads the
   Gen 3 defaults first and then overlays whatever `initial_state` provides. A
   Gen 5 world must be able to say "replace", or the Gen 3 inventory leaks into
   every instance.
2. **Tool responses are an if-chain on Gen 3 literals.** `query_tool` and
   `execute_action` hard-code scenario logic on roughly twenty literals
   (`10.0.99.50`, `198.51.100.42`, `update-service-win32.com`, `10.0.5.23`,
   `10.0.8.99`, `DESKTOP-FIN-08`, `192.0.2.10`, and others). There is no IP
   indicator inventory at all; external IP reputation is synthesized by
   branches. Gen 5 requires making tool responses fully data-driven. This is
   the largest single piece of work.
3. **Harbor copies the runtime into every task.**
   `generate_harbor_soc_tasks._populate_identical_environment` writes ten
   runtime files plus four task files per task directory. Campaign 5 has four
   arms times ten cases, 560 files. Section 9.4 sets the Gen 5 policy.

Branch feasibility was checked: `harbor_soc_evals_v0001` forked from the
hillclimber branch at `b4fd8d2`, `git merge-tree` reported no conflicts, and
both merges landed cleanly on `gen5_evals_v0001`.

## 4. Data model

Four artifact types, all JSON, under `configs/evals/gen5/`.

### 4.1 Family template (`families/<FAMILY_ID>.json`, 16 files, hand-authored)

A family fixes everything that defines correct handling and leaves identity to
slots.

```json
{
  "family_id": "FAM-C2-INFOSTEALER",
  "name": "Infostealer C2 beacon from a workstation",
  "ground_truth_label": "MALICIOUS",
  "asset_criticality": "STANDARD",
  "difficulty": 2,
  "counterfactual_pair_id": "PAIR-01",
  "transport": "sandbox",
  "slots": {
    "victim_host":     {"type": "hostname", "role": "workstation"},
    "victim_ip":       {"type": "internal_ip", "same_site_as": "victim_host"},
    "active_user":     {"type": "username", "owned_by": "victim_host"},
    "c2_domain":       {"type": "domain", "style": "lookalike_update_service",
                        "resolves_to": "c2_ip"},
    "c2_ip":           {"type": "external_ip"},
    "malware_family":  {"type": "choice", "pool": "infostealer_families"},
    "dropper_hash":    {"type": "sha256"},
    "distractor_host": {"type": "hostname", "role": "workstation"},
    "case_id":         {"type": "case_id"}
  },
  "environment_state": {
    "mode": "replace",
    "hosts":   {"{{victim_host}}": {...}, "{{distractor_host}}": {...}},
    "ips":     {"{{c2_ip}}": {...}},
    "domains": {"{{c2_domain}}": {...}},
    "hashes":  {"{{dropper_hash}}": {...}},
    "cases":   {"{{case_id}}": {...}}
  },
  "prompt": "Alert: {{victim_host}} ({{victim_ip}}) beaconed to {{c2_domain}} ...",
  "expected_actions": ["isolate_host", "update_case_comment"],
  "prohibited_actions": ["close_case"],
  "expected_entities": ["{{victim_host}}", "{{c2_domain}}"],
  "prohibited_entities": ["{{distractor_host}}"],
  "cmdb_context": {...},
  "reference": {"expected_verdict": "MALICIOUS", "expected_threat_family": "{{malware_family}}",
                "recommended_action": "...", "grading_rubric": "..."},
  "assertions": {"must_contain": ["{{c2_domain}}"], "must_not_contain": ["benign", "false positive"]},
  "fault_injection": null,
  "liveness": {"min_epistemic_steps": 1},
  "oracle": {
    "lookups": [{"tool": "get_domain_report", "args": {"domain": "{{c2_domain}}"}},
                {"tool": "lookup_entity", "args": {"entity": "{{victim_host}}"}}],
    "actions": [{"action": "isolate_host", "args": {"hostname": "{{victim_host}}"}},
                {"action": "update_case_comment", "args": {"case_id": "{{case_id}}",
                 "comment": "Confirmed {{malware_family}} C2 to {{c2_domain}}; host isolated."}}]
  }
}
```

Labels, criticality, expected and prohibited actions, rubric, oracle, and the
world's shape (which entities exist, their reputations, which are distractors)
are fixed per family. Only identities vary per instance. That is what makes an
unseen instance a fair in-distribution test rather than a different task.

The `oracle` block is new. It is the family's reference solution in data form.
The instancer renders it into each case; the reference-policy runner executes
it in Python; the Harbor generator renders it into `solution/solve.sh`. One
definition, both transports.

### 4.2 Pools (`pools/pools-v1.json`, versioned, append-only)

Word lists and an address plan: host role prefixes and sites, departments, name
lists for usernames, registrars, hosting labels, malware family names, benign
SaaS vendors, scanner products, lookalike domain stems.

Address plan:

| Slot type | Range | Reason |
|---|---|---|
| `internal_ip` | RFC 1918, one `/24` per site (`10.<site>.0.0/24` style) | matches the CMDB story |
| `external_ip` | `198.18.0.0/15` (RFC 2544 benchmarking space) | non-routable, so no synthetic indicator can point at a real organization, and distinct from documentation space |
| documentation IP (one family only) | RFC 5737 `192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24` | "this is a documentation range" stays a signal unique to `FAM-DOC-IP-FALSE-POSITIVE`; Gen 3 contaminated this signal by placing its C2 at `198.51.100.42` |
| `domain` | invented second-level names from word pools plus digits, common TLDs | never resolved outside the sandbox |
| `sha256` | seeded 64-hex | |
| `case_id` | seeded `CASE-nnnnn` | |
| `hostname` | `<ROLE>-<SITE>-<NN>` (for example `WKS-AUS-17`, `SRV-FRA-PAY-02`) | |
| `username` | `first.last` from name pools | |

`pools/reserved_literals.json` lists the Gen 3 inventory and every literal
currently hard-coded in `soc_environment.py`. The allocator never emits them.

### 4.3 Materialized case

The Gen 3 case shape (`eval_id`, `name`, `prompt`, `asset_criticality`,
`ground_truth_label`, `expected_actions`, `prohibited_actions`,
`expected_entities`, `counterfactual_pair_id`, `cmdb_context`, `reference`,
`assertions`, `fault_injection`) plus:

| Field | Type | Notes |
|---|---|---|
| `generation` | `5` | |
| `family_id` | string | |
| `instance_index` | int, 0-based | `eval_id` uses `instance_index + 1`, two digits |
| `instance_seed` | int | section 6.2 |
| `pool_version` | string | `pools-v1` |
| `template_sha256` | hex | hash of the family template that produced the case |
| `difficulty` | 1, 2, or 3 | |
| `transport` | `sandbox` | |
| `environment_state` | object | fully rendered, `mode: "replace"`, inventories `hosts`, `ips`, `domains`, `hashes`, `cases`, optional `faults` |
| `prohibited_entities` | list | entities the agent must not act on |
| `liveness` | `{min_epistemic_steps: int}` | |
| `oracle` | object | rendered reference solution |

`eval_id` format: `CASE-GEN5-<FAMILY_SHORT>-<NN>`, for example
`CASE-GEN5-C2-INFOSTEALER-03`.

`split` is deliberately not stored in the case. Membership lives only in the
manifest so there is one source of truth.

### 4.4 Bundles and manifest

- `train.json`, `validation.json`, `final_test.json`: the existing evalset
  shape, `{evalset_id, generation, split, eval_cases}`, so every current loader
  works with a path change.
- `manifest.json`:
  - `evalset_id`, `generation`, `pool_version`, `instancer_version`,
    `built_from_git_sha`
  - `families[]`: `{family_id, split_role, template_sha256, instances}`
  - `cases[]`: `{eval_id, family_id, instance_index, instance_seed, split,
    difficulty, label, case_sha256}` where `case_sha256` is over
    `json.dumps(case, sort_keys=True, separators=(",", ":"))`
  - `splits`: `{train: [eval_id...], validation: [...], final_test: [...]}`
  - `forbidden_literals[]` and `forbidden_literals_sha256`
  - `supersedes[]`: prior `case_sha256` values when a rebuild changes bytes
- `schema/family.schema.json`, `schema/case.schema.json`,
  `schema/manifest.schema.json`, following the Gen 4 `evals/schema.json`
  precedent.

## 5. Families and splits

Gen 3 uses four labels (`MALICIOUS`, `BENIGN`, `SUSPICIOUS`, `INCONCLUSIVE`)
and the action vocabulary `isolate_host`, `block_indicator`, `close_case`,
`update_case_comment` (with the aliases the environment already accepts). Gen 5
keeps both. New families use only entity types the sandbox already models
(hosts, domains, hashes, cases) plus the new `ips` inventory, so no new tools
are needed.

### 5.1 Split roles

Roles are assigned per family in `split_plan.json`, never per case.

| Role | Families | Instances per family | Exposure |
|---|---|---|---|
| `seen` | 10 ported from Gen 3 | 6: indices 0 to 3 train, 4 validation, 5 final_test | reflection sees train only |
| `validation_ood` | 2 new | 5, all validation | seen only by the acceptance gate (a selection leak in Dwork's sense), never by reflection |
| `final_test_ood` | 4 new | 5, all final_test | sealed |

Totals: train 40, validation 20 (10 in-distribution plus 10 OOD), final_test 30
(10 in-distribution plus 20 OOD), 90 cases.

The in-distribution slice of final_test is what allows the "unseen instance"
gain to be separated from the "unseen family" gain. That difference is the
memorization term in the HDA decomposition; without it the suite could not say
whether an accepted runbook learned the task or learned the families.

### 5.2 The sixteen families

| Family | Role | Label | Criticality | Diff. | Expected | Prohibited | Pair |
|---|---|---|---|---|---|---|---|
| FAM-C2-INFOSTEALER | seen | MALICIOUS | STANDARD | 2 | isolate_host, comment | close_case | PAIR-01 |
| FAM-DOC-IP-FALSE-POSITIVE | seen | BENIGN | LOW | 1 | close_case | isolate_host, block_indicator | |
| FAM-PHISHING-CREDENTIAL | seen | MALICIOUS | STANDARD | 2 | block_indicator, comment | close_case | |
| FAM-DUPLICATE-CASE | seen | SUSPICIOUS | STANDARD | 2 | comment | create_case | |
| FAM-RANSOMWARE-CRITICAL | seen | MALICIOUS | CRITICAL | 3 | isolate_host, comment | reboot_host, close_case | PAIR-02 |
| FAM-DNS-TUNNEL-AMBIGUOUS | seen | SUSPICIOUS | CRITICAL | 3 | comment | isolate_host, close_case | PAIR-01 |
| FAM-LATERAL-PSEXEC | seen | MALICIOUS | HIGH | 3 | isolate_host, comment | close_case | |
| FAM-SUPPLYCHAIN-REVOKED-CERT | seen | SUSPICIOUS | HIGH | 3 | block_indicator, comment | close_case | |
| FAM-TOOL-OUTAGE-503 | seen | INCONCLUSIVE | STANDARD | 3 | comment | close_case, isolate_host | |
| FAM-AUTHORIZED-SCANNER | seen | BENIGN | LOW | 1 | close_case, comment | isolate_host | PAIR-02 |
| FAM-CRYPTOMINER-DEV | validation_ood | MALICIOUS | STANDARD | 2 | isolate_host, block_indicator, comment | close_case | PAIR-03 |
| FAM-SAAS-BEACON-BENIGN | validation_ood | BENIGN | STANDARD | 2 | close_case, comment citing the change ticket | isolate_host, block_indicator | PAIR-03 |
| FAM-PASSWORD-SPRAY | final_test_ood | MALICIOUS | HIGH | 2 | block_indicator (source IP), comment | isolate_host (targets are victims; one is a DC), close_case | PAIR-04 |
| FAM-CLOUD-KEY-EXFIL | final_test_ood | MALICIOUS | CRITICAL | 3 | block_indicator, comment naming key rotation | isolate_host (the credential is compromised, not the host), close_case | |
| FAM-INSIDER-EXFIL | final_test_ood | SUSPICIOUS | HIGH | 3 | comment escalating to HR and legal, preserve evidence | close_case, isolate_host | |
| FAM-IMPOSSIBLE-TRAVEL-APPROVED | final_test_ood | BENIGN | STANDARD | 2 | close_case, comment | isolate_host, block_indicator | PAIR-04 |

Balance: 7 MALICIOUS, 4 BENIGN, 4 SUSPICIOUS, 1 INCONCLUSIVE.

Difficulty: 1 means one lookup settles it; 2 means two or three lookups plus a
CMDB or case cross-check; 3 means conflicting signals or restraint on a
critical asset.

The `seen` families port the Gen 3 cases one to one (labels, criticality,
expected and prohibited actions, fault injection for the 503 family) so that
Gen 3 results remain interpretable against their Gen 5 descendants.

### 5.3 Rules behind the table

- Counterfactual pairs never straddle split roles. PAIR-01 and PAIR-02 are
  both `seen`; PAIR-03 is both `validation_ood`; PAIR-04 is both
  `final_test_ood`. A pair split across train and final_test would leak the
  counterfactual's structure into the sealed set.
- Each OOD role mixes labels (validation OOD: one malicious, one benign; final
  OOD: two malicious, one suspicious, one benign) so "always escalate" cannot
  score well on held-out data.
- Every family has at least one distractor entity in its world, a benign host
  or domain the agent must not touch, feeding `prohibited_entities`.
- The three new restraint families (password spray, cloud key, insider) each
  make `isolate_host` the wrong move for a different reason. Over-isolation is
  where Campaign 5 and the Gen 3 Gemma rungs showed runbooks go wrong.
- The six new family templates are reviewed by the project owner for
  defensibility of expected and prohibited actions before instancing (section
  8.1). They encode SOC judgment, not code.

## 6. Instancer, determinism, and provenance

### 6.1 CLI

`scripts/gen5_instancer.py` with four subcommands:

| Subcommand | Behavior |
|---|---|
| `build` | families + pools + `split_plan.json` in; three bundles + `manifest.json` out |
| `check` | regenerate to a temp dir and diff byte-for-byte against the checked-in artifacts; a unit test calls this so any drift fails CI (lockfile semantics) |
| `show <eval_id>` | print one rendered case |
| `literals` | print the forbidden literal list |

`split_plan.json` maps each family to its role and instance count. It is about
twenty lines, so split membership is reviewable in a diff and is never computed
at run time.

### 6.2 Determinism

```python
instance_seed = int(hashlib.sha256(f"{pool_version}:{family_id}:{instance_index}".encode()).hexdigest()[:16], 16)
```

Each slot draws from `random.Random(instance_seed + slot_ordinal)` in template
declaration order. No clock, no filesystem ordering, sorted iteration
everywhere. `instancer_version` and `pool_version` are recorded in the
manifest. Bumping either is a Gen 5.x release; the new manifest carries a
`supersedes` list of prior `case_sha256` values so any old result file can be
tied to the bytes that produced it.

### 6.3 Rendering

`{{slot}}` substitution over every string in the template, strict: an
unresolved placeholder, or a placeholder inside a non-string value, is a build
error. Relationships are declarative:

| Attribute | Meaning |
|---|---|
| `same_site_as: <host_slot>` | the internal IP lands in that host's site `/24` |
| `resolves_to: <ip_slot>` | the domain's `resolutions` and `passive_dns` include that IP |
| `owned_by: <host_slot>` | the host's `active_user` is this username |

A build-time check verifies that every literal referenced in `prompt`,
`assertions`, `expected_entities`, `prohibited_entities`, and `oracle` exists
in that case's `environment_state`, so no case can ask about an entity the
sandbox cannot answer for. A second check verifies that the oracle's comment
action contains every `assertions.must_contain` string, so the Oracle policy
in section 8.1 can only pass if the family's own reference solution satisfies
the family's own assertions.

### 6.4 Uniqueness

Identifying slot types (`hostname`, `internal_ip`, `external_ip`, `domain`,
`sha256`, `username`, `case_id`) draw without replacement from a global
allocator across all 90 cases, pre-seeded with `reserved_literals.json`. On a
collision the allocator advances the stream deterministically and redraws.
Non-identifying slots (malware family names, departments, vendor names,
registrars) may repeat; they are flavor, not identity.

Tests: no identifying literal in two cases; none in Gen 3; none in
`reserved_literals.json`.

### 6.5 Forbidden literal guard

`manifest.forbidden_literals` is the full set of identifying literals from all
three splits plus the reserved set. `validate_runbook_candidate` in the GEPA
adapter loads this list instead of its current hard-coded Gen 3 strings and
rejects any candidate containing one. The list is consumed only by code; the
reflector model never sees it, so listing final_test literals is not a leak.
Any instance-specific literal in a runbook is memorization by definition,
train literals included.

### 6.6 Exposure ledger

`configs/evals/gen5/exposure.jsonl`, committed and append-only. Every loader
that reads a Gen 5 split appends:

```json
{"timestamp": "...", "run_id": "...", "git_sha": "...", "split": "validation",
 "eval_ids_sha256": "...", "purpose": "...", "model": "..."}
```

Loading `final_test` also requires `--unseal-final-test` and a
non-empty `--purpose`; the loader refuses otherwise. This is
[`experiment_protocol.md`](../../experiment_protocol.md)'s exposure history
made mechanical.

### 6.7 Harness lock chain

`DEFAULT_PROTECTED_HARNESS_PATHS` in `agent/hillclimb_harness.py` gains
`manifest.json`, the three bundles, `families/`, `pools/`, `schema/`,
`split_plan.json`, and `scripts/gen5_instancer.py`. The Gen 3 entries move to a
`LEGACY_PROTECTED_PATHS` set that is still locked but no longer the default
evalset. The chain is: ledger entry, manifest hash, `case_sha256`, bytes.

## 7. Environment, scoring, and runner changes

### 7.1 `SocEnvironment` becomes data-driven (prerequisite)

- New `IpIndicatorEntity` dataclass and `self.ips` inventory: `ip, reputation,
  verdict, category, asn, cidr, routing_status, threat_family,
  malicious_votes, harmless_votes, vt_positives, vt_total, reverse_dns,
  service, host_association, country`.
- `_load_state`: when `state_config["mode"] == "replace"`, start from empty
  inventories. Overlay behavior is unchanged when `mode` is absent, so nothing
  that builds `SocEnvironment()` today changes.
- `from_eval_case`: if `environment_state` is present, construct with it, then
  apply `fault_injection` as now. A case with `generation >= 5` and no
  `environment_state` raises `ValueError`.
- `query_tool`: the if-chains on literals are replaced by inventory lookups
  plus data-free range fallbacks.

  | Lookup | Resolution order |
  |---|---|
  | IP report | `ips` exact match; else a host whose `ip` matches (internal asset record); else RFC 5737 (documentation-range record); else RFC 1918 (unknown internal); else `NO_DATA` |
  | Domain report | `domains`; else not-found record |
  | File report | `hashes`; else not-found record |
  | `lookup_entity` | route by entity type (hostname or IP to hosts, domain to domains, hash to hashes, case id to cases) |
  | Cases | `cases`; search by id, title substring, or entity mention |

  Faults stay first in dispatch.
- `execute_action`: the Gen 3 literals at the block and isolate paths go.
  Actions resolve targets against inventories. Blocking an indicator that
  exists in no inventory is still recorded but flagged `unknown_indicator:
  true`, so the verifier can see shotgun blocking.
- Gen 3 parity is protected two ways. First, the values the if-chains used to
  synthesize (the scanner at `10.0.99.50`, the C2 at `198.51.100.42`, the
  TEST-NET records, and the rest) move into a `gen3_defaults` `ips` inventory
  that the default (overlay) constructor loads. Second, a golden
  characterization test records `query_tool` and `execute_action` outputs for a
  fixed list of calls before the refactor and asserts byte equality after. The
  frozen suite must score identically, or the refactor is wrong.

### 7.2 Shared scoring

Changes to `scripts/eval_trajectory_verifier.py` and
`scripts/eval_cost_engine.py`, gated on fields only Gen 5 cases carry so Gen 3
numbers do not move:

- **Liveness.** If `epistemic_step_count < liveness.min_epistemic_steps` and
  there is no verdict, the trajectory is `inert`: final score 0.0, and
  `min_loss_penalty` is reported as null with `inert: true` instead of the
  current vacuous 1.0.
- **Prohibited entities.** A mutating action whose target matches an entry in
  `prohibited_entities` is a safety violation with the same weight as a
  prohibited action.
- **Result fields.** Every per-case result records `family_id`, `split`,
  `difficulty`, `case_sha256`, `manifest_sha256`, `tokens_in`, `tokens_out`,
  `tool_calls`, `latency_ms`, and `infra_failure`.

### 7.3 Runners

- `scripts/eval_soc_agent.py`: `--split {train,validation,final_test}`
  resolves to the Gen 5 bundles; `--families` and `--difficulty` filters;
  `--unseal-final-test --purpose "..."` required for final_test; ledger append
  on every load.
- `agent/gepa_runbook_optimizer.py`: `--train-split` and `--val-split` replace
  the `eval_cases[:6]` / `eval_cases[6:]` slicing (defaults: Gen 5 train and
  validation). Reflection minibatches draw from the 40 train cases; Pareto
  selection scores on the 20 validation cases. `validate_runbook_candidate`
  loads `manifest.forbidden_literals`. Two fixes from the run analysis that the
  first Gen 5 campaign cannot do without: `save_runbooks()` writes only when a
  candidate was `KEPT` (no more seed overwrite), and `selection_reason`
  reports `seed_retained_all_candidates_reverted` when that is what happened.
- `agent/hillclimb_harness.py`: `estimate_noise_floor` accepts K runs (K >= 2)
  and writes `noise_floor.json` with per-case standard deviation; protected
  paths per section 6.7; the cost staircase walk records tokens and latency
  per rung and marks inert rungs rather than reporting them as a score.
- Harbor: `scripts/generate_harbor_soc_tasks.py` takes `--evalset`, `--split`,
  `--arms`, `--out`; writes `evals/harbor_soc_gen5/<arm>/<split>/<case-slug>/`;
  tags `task.toml` with `family_id`, `split`, `difficulty`, `case_sha256`; and
  renders `solution/solve.sh` from the case's `oracle` block. A `--check` mode
  mirrors the instancer's. `scripts/soc_sandbox_cli.load_eval_case` searches
  the Gen 5 bundles and restores via `from_eval_case`, so replace mode comes
  for free. `scripts/verify_harbor_soc.py` already imports the shared verifier,
  so liveness and prohibited entities apply inside the container without
  separate code.

### 7.4 Tests

New: `tests/test_gen5_schema.py`; `tests/test_gen5_instancer.py`
(determinism, `check` mode, uniqueness, prompt-literal existence, oracle
renders); `tests/test_gen5_soc_environment.py` (replace mode, `ips`
fallbacks, unknown-indicator flag); `tests/test_gen3_soc_environment_parity.py`
(golden characterization); `tests/test_gen5_reference_policies.py`.

Extended: cost engine and verifier (liveness, prohibited entities, result
fields); GEPA optimizer (split loading, manifest literal guard, no-overwrite,
selection reason); `eval_soc_agent` (split flags, unseal, ledger); Harbor task
generation (task count, identical environment hash across tasks, Gen 5
`solve.sh`, `--check`); hillclimb harness (K-run noise floor, protected paths).

## 8. Validation and done criteria

Two layers: build gates that must pass before any model token is spent, and
measurement gates for the first campaign. Thresholds are fixed here so they are
approved before anything is inspected.

### 8.1 Build gates (no LLM involved)

Three scripted reference policies (`scripts/gen5_reference_policies.py`) run
against all 90 cases, 3 trials each, in both transports:

| Policy | Behavior | Gate |
|---|---|---|
| Oracle | executes the case's `oracle` block: the lookups, then the actions, whose comment action carries the `must_contain` strings | >= 0.95 on every case; cases classified Stable / Flaky / Broken as in Kolesnikov's `-a oracle -k 3`; any Flaky or Broken case is fixed (which regenerates bundles and manifest) before model runs |
| Inert | no tool calls, no verdict | exactly 0.0 on every case |
| Shotgun | isolate every host and block every indicator it can discover, close nothing | mean <= 0.35, and below Oracle on every case |
| Close-all | close every case with no lookups | mean <= 0.35, and below Oracle on every case |

Also required:

- Transport parity: Oracle and Shotgun per-case scores agree within 0.01
  between `SocEnvironment` and `soc-cli`.
- `gen5_instancer.py check` and `generate_harbor_soc_tasks.py --check` clean.
- Full test suite green.
- Zero `final_test` entries in `exposure.jsonl`.
- Human review of the 16 family templates for defensibility of expected and
  prohibited actions.

The Shotgun and Close-all gates are what make the acceptance gate meaningful.
If either degenerate policy can score above 0.35, the suite rewards a strategy
instead of judgment, and the hillclimber would find it.

### 8.2 Measurement gates (first campaign, validation split only)

1. **Seed noise floor.** K = 3 runs of the seed runbooks with
   `gemini-2.5-flash` on the 20 validation cases. Report `tau_accept`, mean
   spread (the largest minus the smallest of the K split means), and per-case
   standard deviation. Gate: mean spread <= 0.02 (the 4-case Gen 3 valset gave
   0.031). If missed, raise K and list the high-variance
   cases rather than proceeding.
2. **Infrastructure segregation.** A case-run that ends in 429, timeout, or
   endpoint error is retried and excluded from quality metrics, never scored 0.
   The result record carries `infra_failure: true`.
3. **Headroom.** Frontier seed mean on validation < 0.95. If the frontier
   saturates, the suite cannot show improvement and difficulty-3 families need
   tightening before the campaign.
4. **Capability gradient (report, not gate).** `gemini-2.5-flash`,
   `gemma-4-31b-it`, `gemma-3-4b-it`, `gemma-3-1b-it` with seed runbooks,
   reported with inert counts per model. Monotonic ordering is expected; a
   violation is reported with its cause.
5. **Final test unsealing** requires a pre-registered comparison file
   (`configs/experiments/gen5_campaign1.json`, from the existing
   `configs/experiments/evidence_comparison.template.json`) listing the exact
   hypotheses, the in-distribution versus OOD comparison, and the >= 2
   repetitions, approved before the `--unseal-final-test` run and recorded in
   the ledger.

### 8.3 Recipes

| Recipe | Does |
|---|---|
| `just gen5-build` | `gen5_instancer.py build` |
| `just gen5-check` | both `--check` modes plus the schema tests |
| `just gen5-calibrate` | the four policies in both transports; writes `docs/soc_eval_results/GEN5_CALIBRATION.md` |
| `just gen5-noise` | measurement gate 1 |

## 9. Rollout and layout

### 9.1 Branch

`gen5_evals_v0001` from `disciplined_hillclimber_v0001` at `2cd283c`, with
`harbor_soc_evals_v0001` and `main` merged (done; HEAD `4ffadb3`). Worktree at
`gemma_deploy__worktrees/gen5_evals_v0001`. One branch, one commit per phase,
PR to `main` after the build gates and the noise-floor gate are recorded in
docs, matching how PRs #1 to #4 landed.

### 9.2 Layout

```
configs/evals/gen5/
  split_plan.json                 family -> role, instance count
  families/FAM-*.json             16 templates (hand-authored)
  pools/pools-v1.json             word lists and address plan
  pools/reserved_literals.json    Gen 3 inventory + soc_environment.py literals
  schema/{family,case,manifest}.schema.json
  train.json  validation.json  final_test.json   generated bundles
  manifest.json                   generated
  exposure.jsonl                  append-only ledger
scripts/gen5_instancer.py         build | check | show | literals
scripts/gen5_reference_policies.py  oracle | inert | shotgun | close_all, both transports
evals/harbor_soc_gen5/<arm>/<split>/<case-slug>/   generated Harbor tasks
docs/evals_gen5.md                how to build, check, calibrate, run
docs/soc_eval_results/GEN5_CALIBRATION.md    generated by just gen5-calibrate
docs/superpowers/specs/2026-10-04-gen5-evals-design.md   this document
docs/superpowers/plans/2026-10-04-gen5-evals.md
configs/experiments/gen5_campaign1.json      pre-registration, written before unsealing
```

Flat modules in `scripts/` and `agent/` follow the existing convention.
Nothing new is needed inside the container beyond the bundles, since the Harbor
`environment/` already copies `soc_environment.py`, the verifier, and the cost
engine.

### 9.3 Phases

0. Branch and merges (done); golden characterization test of the Gen 3
   environment, recorded before any refactor.
1. Data-driven `SocEnvironment`: `ips`, replace mode, fallbacks; parity test
   green.
2. Schemas, pools, split plan, instancer, the 10 ported families; `build` and
   `check`; uniqueness tests.
3. The 6 new families; reference policies; calibration in `SocEnvironment`;
   owner review of family templates.
4. Scoring: liveness, prohibited entities, per-case result fields.
5. Runners: `eval_soc_agent` splits and ledger; GEPA splits, manifest guard,
   no-overwrite, selection reason; harness K-run noise floor and protected
   paths.
6. Harbor generator, `soc-cli`, container calibration, transport parity.
7. Docs, `just` recipes, noise-floor gate, gradient report, memory, PR.

### 9.4 Harbor task check-in policy

Generated tasks are checked in, as Campaign 5 did, so provenance is byte-level
in git and `generate_harbor_soc_tasks.py --check` enforces regenerability. The
environment hash is identical across tasks and recorded once in the manifest.

Scope is limited to keep the tree manageable. Campaign 5 shipped four arms
times ten cases at 14 files per task (560 files). A full Gen 5 matrix would be
90 cases times four arms, 5,040 files. The policy is:

- Only `validation` and `final_test` are generated for Harbor (50 cases). The
  train split never runs in the container; the optimizer is Python-side.
- Arms are a generation flag. Default arms are `clean_skills` and
  `gepa_evolved_skills`: 100 tasks, 1,400 files. All four arms: 200 tasks,
  2,800 files. Git stores identical blobs once, so the repository size cost is
  small; the cost is diff noise when the runtime changes, which `--check`
  keeps honest.

### 9.5 Docs touched besides the new ones

- `docs/experiment_protocol.md`: split names now map to the Gen 5 bundles; the
  ledger path and the unseal flag.
- `docs/index.md`: catalog rows.
- `docs/thoughts_on_evals.md` section 5: pointer to this spec.
- `configs/evals/gen3/soc_tier1_interactive.json`: `frozen: true` note in the
  description; no other change.
- Memory: `projects/gemma-deploy/soc-evals.md` lineage entry for Gen 5.

## 10. Risks and open questions

| Risk | Mitigation |
|---|---|
| The data-driven refactor changes Gen 3 behavior silently | golden characterization test recorded before the refactor (phase 0) |
| Family templates encode debatable SOC judgment (insider exfil, cloud key) | owner review gate before instancing; rubric text states the reason each prohibited action is wrong |
| Oracle gate passes but the family is still too easy or too hard for models | headroom gate (8.2.3) and gradient report (8.2.4) run before the campaign |
| Validation OOD families become "seen" through repeated selection | they are only two of sixteen; final_test holds four more families that nothing selects on; the ledger records every exposure |
| Candidate scoring moves from 4 validation cases to 20 (5x per candidate), and reflection draws from 40 train cases instead of 6 | reflection minibatches of fixed size; Pareto scoring on validation only; the staircase walk stays on validation; `--max-metric-calls` budgets stated per campaign in the pre-registration file |
| Harbor tree growth | section 9.4 policy; `--arms` and `--split` flags |
| `forbidden_literals` in a public manifest | the list is a filter consumed by code; the reflector never reads it |

Open: whether `gemma-3-1b-it` is worth an endpoint for the gradient report, or
whether the 4B rung is the smallest useful one. Decide at phase 7 from the
inert counts on the 4B rung.

## 11. References

Internal:

- [`DISCIPLINED_HILLCLIMBER_RUN_ANALYSIS.md`](../../soc_eval_results/DISCIPLINED_HILLCLIMBER_RUN_ANALYSIS.md): the 2026-10-02 run, noise floor, seed overwrite, staircase caveats.
- [`hillclimber_rrsi_crosswalk.md`](../../hillclimber_rrsi_crosswalk.md): RRSI and HDA frames mapped to the hillclimber.
- [`references_agent_harness_literature.md`](../../references_agent_harness_literature.md): annotated literature list.
- [`experiment_protocol.md`](../../experiment_protocol.md): split rules, exposure history, pre-registration.
- [`thoughts_on_evals.md`](../../thoughts_on_evals.md): discriminative power and capability gradient.
- [`2026-09-01-gen3-eval-framework-design.md`](2026-09-01-gen3-eval-framework-design.md) and [`2026-09-04-gepa-runbook-evolution-design.md`](2026-09-04-gepa-runbook-evolution-design.md): the suite and optimizer Gen 5 extends.
- `docs/eval_results/harbor_soc/gepa_evolved_sweep/scorecard.md`: Campaign 5 numbers.

External:

- Xia et al., 2026, RRSI: Regularized Recursive Self-Improvement of Agent Harnesses, arXiv:2609.24972. Evolve / held-out / OOD split discipline; selection-side pruner with noise floor.
- Ding et al., 2026, Harness-Delta Attribution. Decomposition of score deltas into generalization, test-time scaling, and artifact memorization.
- Dwork et al., 2015, The reusable holdout, arXiv:1506.02629. Why selecting on a validation set leaks.
- Kolesnikov, 2026, `harbor-gke-ext`. Oracle calibration (`-a oracle -k 3`), Stable / Flaky / Broken classification.
- Martin, 2026, automated eval design. Four invariants: production mirroring, monotonic capability scaling, headroom under 95 percent, low run-to-run variance.
- Shah, 2026, Agentic Evals: A Software Engineer's Guide, Part 1. Infrastructure failure segregation, pinned agent under test, aggregation with confidence intervals.
