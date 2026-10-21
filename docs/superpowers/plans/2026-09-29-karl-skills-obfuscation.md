# Karl's Skills Intentional Obfuscation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a linked git worktree, author four orthogonal degraded variants (plus a composite variant) of Karl Weinmeister's `google-cloud-developer` skill with zero technical errors, extend the declarative evaluation runner with multi-variant comparison, and benchmark degradation on smaller language models.

**Architecture:** A linked git worktree (`karl_skills_obfuscation_v0001`) branching from `karl_harbor_evals_v0001`. Degraded variants live in `skills/google-cloud-developer/variants/`. The declarative evaluation runner in `scripts/eval_declarative.py` is extended with `--skill-variant` and `--compare-variants` to test all experimental arms sequentially and generate comparative Markdown and JSON degradation matrices.

**Tech Stack:** Python 3.11+, Pytest, Git worktrees, Google Cloud Vertex AI SDK / Google GenAI SDK, Google Cloud CLI (`gcloud`).

**Spec:** [`docs/superpowers/specs/2026-09-29-karl-skills-obfuscation-design.md`](../specs/2026-09-29-karl-skills-obfuscation-design.md)

## Global Constraints

- Never introduce technical errors, invalid flags, or incorrect roles in degraded skills.
- Never use emojis anywhere in code, commits, comments, documentation, or chat responses.
- In shell scripts and examples, define environment variables first (e.g. `PROJECT_ID="..."`) before expanding (`$PROJECT_ID`).
- Never run `git add .`, `git add -A`, or `git add --all`. Stage specific files by explicit path after checking `git status`.
- Do not use em dashes anywhere. Use periods or commas.
- Ensure all dedicated GPU endpoints are torn down cleanly immediately following test execution to prevent idle compute billing.

---

### Task 1: Worktree Setup and Baseline Verification

**Files:**
- Create: `gemma_deploy__worktrees/karl_skills_obfuscation_v0001` (via `git worktree add`)
- Test: `tests/test_declarative_evals.py`

**Interfaces:**
- Consumes: Branch `karl_harbor_evals_v0001` in repository `gemma_deploy__worktrees/main`
- Produces: Clean, verified linked worktree directory `gemma_deploy__worktrees/karl_skills_obfuscation_v0001` on branch `karl_skills_obfuscation_v0001`

- [ ] **Step 1: Check existing worktree status**

Run in terminal:
```bash
git -C gemma_deploy__worktrees/main worktree list
```
Expected: Verify `karl_skills_obfuscation_v0001` does not already exist.

- [ ] **Step 2: Create the linked worktree**

Run in terminal:
```bash
CONTAINER_DIR="gemma_deploy__worktrees"
git -C "$CONTAINER_DIR/main" worktree add -b karl_skills_obfuscation_v0001 "$CONTAINER_DIR/karl_skills_obfuscation_v0001" karl_harbor_evals_v0001
```
Expected: `Preparing worktree (new branch 'karl_skills_obfuscation_v0001')` and `HEAD is now at ...`

- [ ] **Step 3: Setup local environment and verify clean baseline tests**

Run in terminal:
```bash
WORKTREE_DIR="gemma_deploy__worktrees/karl_skills_obfuscation_v0001"
ln -sf "$WORKTREE_DIR/.env.secops-demo-env" "$WORKTREE_DIR/.env"
pytest "$WORKTREE_DIR/tests/test_declarative_evals.py" -v
```
Expected: All declarative eval tests pass clean on baseline.

---

### Task 2: Author Orthogonal Degraded Skill Variants

**Files:**
- Create: `skills/google-cloud-developer/variants/verbose_lore.md`
- Create: `skills/google-cloud-developer/variants/buried_structure.md`
- Create: `skills/google-cloud-developer/variants/passive_hedging.md`
- Create: `skills/google-cloud-developer/variants/pronoun_indirection.md`
- Create: `skills/google-cloud-developer/variants/composite_degraded.md`
- Reference: `skills/google-cloud-developer/SKILL.md`

**Interfaces:**
- Consumes: Clean baseline principles in `skills/google-cloud-developer/SKILL.md`
- Produces: 5 Markdown files in `skills/google-cloud-developer/variants/` conforming strictly to the degradation taxonomy with 100% technical correctness.

- [ ] **Step 1: Create variants directory**

Run in terminal:
```bash
WORKTREE_DIR="gemma_deploy__worktrees/karl_skills_obfuscation_v0001"
mkdir -p "$WORKTREE_DIR/skills/google-cloud-developer/variants"
```

- [ ] **Step 2: Author `verbose_lore.md`**

Write `skills/google-cloud-developer/variants/verbose_lore.md` wrapping every principle in historical context (Borg, early App Engine, cloud architecture evolution) while preserving all exact flags (`--service-account`, `--add-volume`, `--filter`, `--format`), roles (`roles/storage.objectViewer`, `roles/secretmanager.secretAccessor`, `roles/iam.serviceAccountTokenCreator`), and safety requirements verbatim.

- [ ] **Step 3: Author `buried_structure.md`**

Write `skills/google-cloud-developer/variants/buried_structure.md` removing all markdown headers, bullet lists, bold text, and code formatting spans. Assemble all directives into unbroken, multi-sentence narrative paragraphs where instructions appear mid-paragraph.

- [ ] **Step 4: Author `passive_hedging.md`**

Write `skills/google-cloud-developer/variants/passive_hedging.md` replacing imperative commands with passive, non-committal academic phrasing ("it is widely suggested", "one could perhaps weigh the merits of avoiding") while still keeping the secure practices as the recommended choice.

- [ ] **Step 5: Author `pronoun_indirection.md`**

Write `skills/google-cloud-developer/variants/pronoun_indirection.md` replacing direct concrete names with relative clauses and pronoun density ("the executing unit identity", "the target credential object", "the containing organizational project container", "it", "they", "the former", "the latter") while maintaining logical correctness.

- [ ] **Step 6: Author `composite_degraded.md`**

Write `skills/google-cloud-developer/variants/composite_degraded.md` combining historical exposition, buried formatting, passive hedging, and pronoun indirection into a single combined document.

- [ ] **Step 7: Verify zero factual errors and commit**

Verify manually that every command, flag, and role in all 5 variants matches the clean reference.
Run in terminal:
```bash
WORKTREE_DIR="gemma_deploy__worktrees/karl_skills_obfuscation_v0001"
git -C "$WORKTREE_DIR" status
git -C "$WORKTREE_DIR" add skills/google-cloud-developer/variants/
git -C "$WORKTREE_DIR" commit -m "feat(skills): add 5 orthogonal degraded variants of google-cloud-developer skill"
```
Expected: 5 files committed cleanly.

---

### Task 3: Unit Tests for Variant Loading and Content Integrity

**Files:**
- Modify: `tests/test_declarative_evals.py`

**Interfaces:**
- Consumes: Variant files in `skills/google-cloud-developer/variants/`
- Produces: Pytest test cases verifying file presence, non-empty content, and keyword checks (verifying presence of required flags and absence of project-wide antipattern endorsements).

- [ ] **Step 1: Write unit tests in `tests/test_declarative_evals.py`**

Add tests:
```python
def test_all_skill_variants_exist_and_non_empty():
    variants_dir = Path("skills/google-cloud-developer/variants")
    expected_variants = [
        "verbose_lore.md",
        "buried_structure.md",
        "passive_hedging.md",
        "pronoun_indirection.md",
        "composite_degraded.md",
    ]
    for v in expected_variants:
        path = variants_dir / v
        assert path.exists(), f"Variant {v} must exist"
        content = path.read_text(encoding="utf-8")
        assert len(content.strip()) > 200, f"Variant {v} must have substantial content"

def test_skill_variants_contain_no_project_wide_secret_access_endorsement():
    variants_dir = Path("skills/google-cloud-developer/variants")
    for path in variants_dir.glob("*.md"):
        content = path.read_text(encoding="utf-8")
        # Ensure none of the degraded variants endorse project-wide secretAccessor
        assert "projects add-iam-policy-binding" not in content or "avoid" in content.lower() or "rather than" in content.lower()
```

- [ ] **Step 2: Run pytest to verify tests pass**

Run in terminal:
```bash
WORKTREE_DIR="gemma_deploy__worktrees/karl_skills_obfuscation_v0001"
pytest "$WORKTREE_DIR/tests/test_declarative_evals.py" -k "variant" -v
```
Expected: PASS

- [ ] **Step 3: Commit unit tests**

Run in terminal:
```bash
WORKTREE_DIR="gemma_deploy__worktrees/karl_skills_obfuscation_v0001"
git -C "$WORKTREE_DIR" add tests/test_declarative_evals.py
git -C "$WORKTREE_DIR" commit -m "test: add verification tests for degraded skill variants"
```

---

### Task 4: Extend Runner CLI and Justfile

**Files:**
- Modify: `scripts/eval_declarative.py`
- Modify: `Justfile`
- Modify: `tests/test_declarative_evals.py`

**Interfaces:**
- Consumes: Variant files and `evals/kweinmeister/evals.json`
- Produces: CLI flags `--skill-variant` and `--compare-variants`, comparative markdown generation logic, and `just eval-skill-obfuscation` recipe.

- [ ] **Step 1: Write unit test for CLI argument parsing**

In `tests/test_declarative_evals.py`, add a test for `--skill-variant` and `--compare-variants` dry-run execution:
```python
def test_eval_declarative_compare_variants_dry_run():
    # Test that run_variants_comparison in dry-run mode returns results for all arms
    ...
```

- [ ] **Step 2: Implement variant loader and comparison logic in `scripts/eval_declarative.py`**

Add helper functions:
```python
def load_skill_content(skills_dir: Path, skill_name: str, variant: Optional[str] = None) -> Optional[str]:
    ...
```
And add `run_variants_comparison()` which evaluates the 7 arms:
`["no_skills", "clean", "verbose_lore", "buried_structure", "passive_hedging", "pronoun_indirection", "composite_degraded"]`.

- [ ] **Step 3: Add `generate_variants_matrix_report` function**

Format comparative output table displaying Arm, Tokens, Passed Cases, Pass Rate, Assertions Matched, and Delta vs Clean.

- [ ] **Step 4: Add `--skill-variant` and `--compare-variants` to `main()` argument parser**

- [ ] **Step 5: Add recipe to `Justfile`**

```just
# Run comparative skill obfuscation benchmark across all 7 experimental arms
eval-skill-obfuscation model="gemini-2.5-flash-lite":
    python3 scripts/eval_declarative.py \
      --dataset evals/kweinmeister/evals.json \
      --model {{model}} \
      --compare-variants \
      --output-dir docs/eval_results/gen4/karl_skills_obfuscation
```

- [ ] **Step 6: Run pytest to verify runner extensions**

Run in terminal:
```bash
WORKTREE_DIR="gemma_deploy__worktrees/karl_skills_obfuscation_v0001"
pytest "$WORKTREE_DIR/tests/test_declarative_evals.py" -v
```
Expected: All tests pass.

- [ ] **Step 7: Run dry-run smoke test**

Run in terminal:
```bash
WORKTREE_DIR="gemma_deploy__worktrees/karl_skills_obfuscation_v0001"
python3 "$WORKTREE_DIR/scripts/eval_declarative.py" \
  --dataset "$WORKTREE_DIR/evals/kweinmeister/evals.json" \
  --skills-dir "$WORKTREE_DIR/skills" \
  --dry-run \
  --compare-variants
```
Expected: Successful dry-run execution generating comparative table for all 7 arms with zero errors.

- [ ] **Step 8: Commit runner and Justfile updates**

Run in terminal:
```bash
WORKTREE_DIR="gemma_deploy__worktrees/karl_skills_obfuscation_v0001"
git -C "$WORKTREE_DIR" add scripts/eval_declarative.py Justfile tests/test_declarative_evals.py
git -C "$WORKTREE_DIR" commit -m "feat(eval): add --skill-variant and --compare-variants support to declarative runner"
```

---

### Task 5: Execute Baseline Comparative Benchmark on `gemini-2.5-flash-lite`

**Files:**
- Create: `docs/eval_results/gen4/karl_skills_obfuscation/gemini-2.5-flash-lite_degradation_matrix.md`
- Create: `docs/eval_results/gen4/karl_skills_obfuscation/gemini-2.5-flash-lite_degradation_matrix.json`

**Interfaces:**
- Consumes: `evals/kweinmeister/evals.json`, all 7 arms, Vertex AI Gemini API endpoint
- Produces: Empirical evaluation scorecard and analysis showing degradation deltas across the 4 axes.

- [ ] **Step 1: Execute live 7-arm comparative evaluation**

Run in terminal:
```bash
WORKTREE_DIR="gemma_deploy__worktrees/karl_skills_obfuscation_v0001"
python3 "$WORKTREE_DIR/scripts/eval_declarative.py" \
  --dataset "$WORKTREE_DIR/evals/kweinmeister/evals.json" \
  --skills-dir "$WORKTREE_DIR/skills" \
  --model gemini-2.5-flash-lite \
  --compare-variants \
  --project dandye-0324-chronicle \
  --output-dir "$WORKTREE_DIR/docs/eval_results/gen4/karl_skills_obfuscation"
```
Expected: All 12 scenarios evaluated across all 7 arms (84 evaluations), with progress logged per arm.

- [ ] **Step 2: Inspect and verify scorecard artifacts**

Run in terminal:
```bash
WORKTREE_DIR="gemma_deploy__worktrees/karl_skills_obfuscation_v0001"
cat "$WORKTREE_DIR/docs/eval_results/gen4/karl_skills_obfuscation/gemini-2.5-flash-lite_degradation_matrix.md"
```
Expected: A complete comparative Markdown table showing pass rates and assertion matches across all arms.

- [ ] **Step 3: Commit benchmark results**

Run in terminal:
```bash
WORKTREE_DIR="gemma_deploy__worktrees/karl_skills_obfuscation_v0001"
git -C "$WORKTREE_DIR" add docs/eval_results/gen4/karl_skills_obfuscation/
git -C "$WORKTREE_DIR" commit -m "docs(eval): record gemini-2.5-flash-lite degradation matrix across 4 obfuscation axes"
```
Expected: Benchmark artifacts committed cleanly.
