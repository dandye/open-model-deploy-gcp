# Design Spec: Intentional Obfuscation of Karl's Skills for Small-Model Degradation Benchmarking

- **Date:** 2026-09-29
- **Status:** Proposed
- **Target Repository:** `gemma_deploy__worktrees`
- **Base Branch:** `karl_harbor_evals_v0001`
- **Target Branch / Worktree:** `karl_skills_obfuscation_v0001`

---

## 1. Executive Summary and Motivation

In agent evaluations, skills act as counter-priors, supplying concise constraints that steer models away from high-frequency web tutorial shortcuts (such as project-wide IAM bindings). Frontier models like Claude Sonnet 4.5 and Gemini 2.5 Pro can parse through verbose text, conversational padding, and passive framing to extract the necessary technical constraints. In contrast, smaller models operating near the capability margin (such as Gemma 3 4B, Gemma 4 E2B/E4B, or Gemini 2.5 Flash Lite) are sensitive to attention dilution and context noise.

This project investigates how prompt structure affects model performance by intentionally degrading Karl Weinmeister's canonical `google-cloud-developer` skill along four orthogonal textual axes.

A primary constraint governs all degraded variants: **zero introduced technical errors**. Every degraded skill variant preserves complete factual accuracy, valid CLI flags, least-privilege role names, and operational intent. The degradation is restricted entirely to style, structure, cognitive load, and framing to isolate which textual properties confuse smaller models.

---

## 2. Worktree and Directory Architecture

The project will reside in a dedicated linked git worktree branched from `karl_harbor_evals_v0001`:

```text
/usr/local/google/home/dandye/Projects/gemma_deploy__worktrees/
├── main/
├── karl_harbor_evals_v0001/
└── karl_skills_obfuscation_v0001/
    ├── skills/
    │   └── google-cloud-developer/
    │       ├── SKILL.md                          # Clean baseline reference
    │       └── variants/                         # Degradation variants
    │           ├── verbose_lore.md
    │           ├── buried_structure.md
    │           ├── passive_hedging.md
    │           ├── pronoun_indirection.md
    │           └── composite_degraded.md
    ├── evals/
    │   └── kweinmeister/
    │       └── evals.json                        # Canonical 12-scenario test suite
    ├── scripts/
    │   └── eval_declarative.py                   # Extended runner CLI
    ├── tests/
    │   └── test_declarative_evals.py             # Validation and variant unit tests
    └── docs/
        └── eval_results/gen4/
            └── karl_skills_obfuscation/          # Comparative scorecards and matrices
```

---

## 3. Degradation Axes and Authoring Specifications

Each variant targets one specific failure mode in smaller language models:

### Axis 1: `verbose_lore.md` (Attention Dilution via Token Bloat)
- **Hypothesis**: Expanding token distance between the user prompt and the critical directive causes attention decay in models with smaller KV-cache attention capacity.
- **Implementation**: Wraps every rule in historical engineering lore (Borg design papers, App Engine generation 1 constraints, Google Cloud infrastructure evolution) and philosophical cloud architecture debates.
- **Guardrail**: Every exact CLI flag (`--service-account`, `--add-volume`, `--filter`), IAM role (`roles/storage.objectViewer`), and command sequence is preserved verbatim.

### Axis 2: `buried_structure.md` (Formatting Decay and Scan Resistance)
- **Hypothesis**: Smaller models rely on typographical beacons (numbered lists, bold lead-ins, backticked code spans) to scan and extract directives.
- **Implementation**: Removes all markdown headers, bullet lists, bold text, and code spans. Reassembles the entire skill into dense, continuous multi-sentence paragraphs. Directives are placed in the middle or end of compound clauses.
- **Guardrail**: Full command syntax and parameter names are written out in plain inline text without typographical emphasis.

### Axis 3: `passive_hedging.md` (Directive Softening and Counter-Prior Collapse)
- **Hypothesis**: Softening imperative commands into passive, highly hedged advice causes smaller models to default to high-frequency pre-trained web tutorial antipatterns.
- **Implementation**: Replaces imperative commands ("Always use", "Never download") with passive academic phrasing ("In certain production environments, practitioners often lean toward avoiding downloadable credentials, favoring instead user-managed identities").
- **Guardrail**: The secure production practice remains the recommended path, with no endorsement of insecure shortcuts.

### Axis 4: `pronoun_indirection.md` (Referential and Syntactic Ambiguity)
- **Hypothesis**: Pronouns and abstract referents strain coreference resolution and parameter binding in smaller models.
- **Implementation**: Replaces explicit resource names with relative descriptions ("the runtime execution identity", "the target secret entity", "the containing project namespace") and pronouns ("it", "they", "the former", "the latter").
- **Guardrail**: The logical mapping of actors to resources remains unambiguous to an attentive human reader.

### Stress Test: `composite_degraded.md`
- Combines all four patterns into a single document to measure the cumulative floor.

---

## 4. Evaluation Harness Extensions (`scripts/eval_declarative.py`)

### 4.1 CLI Arguments
- `--skill-variant=[clean|verbose|buried|hedging|indirection|composite|all]`: Specifies which skill variant to load.
- `--compare-variants`: Sequentially evaluates all 7 arms on the target model and produces a unified comparative report:
  1. `no_skills`
  2. `clean`
  3. `verbose_lore`
  4. `buried_structure`
  5. `passive_hedging`
  6. `pronoun_indirection`
  7. `composite_degraded`

### 4.2 Comparative Scorecard Output
The runner will produce both JSON and GitHub-flavored Markdown artifacts at `docs/eval_results/gen4/karl_skills_obfuscation/<model>_degradation_matrix.{json,md}`:

| Arm | Tokens | Passed Cases | Pass Rate | Assertions Matched | Delta vs Clean | Dominant Failure Mode |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| `no_skills` | 0 | 5/12 | 41.7% | 22/36 | -41.6% | Tutorial IAM shortcuts |
| `clean` | ~450 | 10/12 | 83.3% | 33/36 | Reference | Edge cases (`gcd-005`) |
| `verbose_lore` | ~2400 | (measured) | (measured) | (measured) | (measured) | Attention decay |
| `buried_structure` | ~450 | (measured) | (measured) | (measured) | (measured) | Unparsed syntax |
| `passive_hedging` | ~550 | (measured) | (measured) | (measured) | (measured) | Counter-prior collapse |
| `pronoun_indirection` | ~500 | (measured) | (measured) | (measured) | (measured) | Argument misbinding |
| `composite_degraded` | ~3000 | (measured) | (measured) | (measured) | (measured) | Cumulative breakdown |

---

## 5. Verification and Testing Strategy

1. **Unit Testing (`tests/test_declarative_evals.py`)**:
   - Validate existence and syntax of all variant markdown files.
   - Verify `--skill-variant` loads each file cleanly.
   - Verify `--compare-variants` runs in `--dry-run` mode with 100% assertions passing.
2. **Empirical Benchmarking**:
   - Run live evaluation on `gemini-2.5-flash-lite` to establish baseline degradation deltas.
   - Run live evaluation on `gemma-3-4b-it` (dedicated L4 GPU endpoint).
3. **Billing Safety**:
   - Verify dedicated GPU endpoints are torn down cleanly immediately following test runs via `just vertex-undeploy`.
