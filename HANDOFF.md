# Agent Handoff: Disciplined Hillclimber (`eval-hillclimb` + Jev Judge + Harness Checksum)

## 1. Context & Workspace

- **Repository:** `gemma_deploy`
- **Worktree Path:** `/usr/local/google/home/dandye/Projects/gemma_deploy__worktrees/disciplined_hillclimber_v0001`
- **Active Branch:** `disciplined_hillclimber_v0001` (stacked on `jev_evals_v0001`)
- **Companion Worktree (for `manage_eval.py` in `agentic_soc_gemini_enterprise`):**
  `/usr/local/google/home/dandye/Projects/agentic_soc_agentspace__worktrees/disciplined_hillclimber_v0001`

## 2. Design Specifications & Implementation Plans on Disk

1. **Disciplined Hillclimber Design Spec:**
   [docs/superpowers/specs/2026-10-01-disciplined-hillclimber-design.md](file:///usr/local/google/home/dandye/Projects/gemma_deploy__worktrees/disciplined_hillclimber_v0001/docs/superpowers/specs/2026-10-01-disciplined-hillclimber-design.md)
2. **Disciplined Hillclimber Implementation Plan (Primary Execution Target):**
   [docs/superpowers/plans/2026-10-01-disciplined-hillclimber.md](file:///usr/local/google/home/dandye/Projects/gemma_deploy__worktrees/disciplined_hillclimber_v0001/docs/superpowers/plans/2026-10-01-disciplined-hillclimber.md)
3. **Prerequisite / Companion Jev System-One Judge Plan (Tasks 1–4 provide `agent/jev_judge.py` and `agent/jev_evaluator.py`):**
   [docs/superpowers/plans/2026-09-24-jev-eval-judge-migration.md](file:///usr/local/google/home/dandye/Projects/gemma_deploy__worktrees/disciplined_hillclimber_v0001/docs/superpowers/plans/2026-09-24-jev-eval-judge-migration.md)

## 3. Execution Instructions for Receiving Agent

1. Verify you are operating inside the isolated worktree:
   ```bash
   WORKTREE_DIR="/usr/local/google/home/dandye/Projects/gemma_deploy__worktrees/disciplined_hillclimber_v0001"
   cd "$WORKTREE_DIR"
   git status
   ```
2. Read [docs/superpowers/plans/2026-10-01-disciplined-hillclimber.md](file:///usr/local/google/home/dandye/Projects/gemma_deploy__worktrees/disciplined_hillclimber_v0001/docs/superpowers/plans/2026-10-01-disciplined-hillclimber.md) and execute the tasks sequentially using Test-Driven Development (`superpowers:subagent-driven-development` or `superpowers:executing-plans`).
3. Follow all global constraints:
   - Strictly NO emojis anywhere in code, comments, documentation, reports, or commit messages.
   - NEVER run `git add .`, `git add -A`, or `git add --all`. Stage explicit file paths only (`git add <file1> <file2>`) and never stage `.env*` files.
   - Ensure any dedicated GPU endpoints used during live verification are torn down immediately (`$0.00` idle compute leak).
