# Agent Instructions for `gemma_deploy`

## 1. Repository & Worktree Conventions

- **Worktree Layout**: All worktrees live under `/usr/local/google/home/dandye/Projects/gemma_deploy__worktrees/<branch>/` with `main` holding `.git/`.
- **Branch Naming**: Never use `/` in branch names and never use `feat` as a prefix. Use `__` as the delimiter (for example, `dspy__context-engineering` or `blog__aqua_secops_flywheel`).
- **Git Staging**: Never run `git add .`, `git add -A`, or `git add --all`. Always inspect `git status` and stage files by explicit path (`git add <file1> <file2>`). Never stage `.env` files or credentials.
- **Zero Emojis**: Never use emojis in code, comments, docstrings, markdown reports, blog posts, commit messages, or pull request descriptions.
- **Shell & Code Examples**: Define environment variables first (`PROJECT_ID="..."`) and reference them as `$PROJECT_ID`.
- **Zero Idle GPU Spend**: Always ensure all Vertex AI dedicated GPU endpoints and ephemeral Spot VMs are undeployed (`just vertex-undeploy`, `just gce-spot-cleanup`) when benchmarking finishes.

## 2. Evaluation Harness Integrity (`HarnessIntegrityGuard`)

Never edit any of the 33 protected evaluation files (`agent/soc_environment.py`, `scripts/eval_trajectory_verifier.py`, `scripts/eval_cost_engine.py`, `scripts/eval_soc_agent.py`, `scripts/verify_harbor_soc.py`, `configs/evals/gen3/soc_tier1_interactive.json`, or `configs/evals/gen5/**`) during prompt, skill, or runbook optimization. Verify the cryptographic lock before and after runs:

```bash
WORKTREE_DIR="/usr/local/google/home/dandye/Projects/gemma_deploy__worktrees/dspy__context-engineering"
cd "$WORKTREE_DIR"
just harness-verify
```

## 3. Agentic SOC Runbook Authoring Rules (`docs/RUNBOOK_AUTHORING_BEST_PRACTICES.md`)

Every SOC runbook created, edited, or evolved with GEPA (`agent/gepa_runbook_optimizer.py`) must obey the 10 rules documented in [`docs/RUNBOOK_AUTHORING_BEST_PRACTICES.md`](docs/RUNBOOK_AUTHORING_BEST_PRACTICES.md):

1. **Word and Line Budget**: Keep each runbook under `350` words and `50` lines (`WordLimitReflectionLM` targets `0.80 * max_words`).
2. **Fixed 6-Section Skeleton**: `# <Title>`, `## Objective`, `## Scope`, `## Inputs`, `## Tools`, and `## Workflow Steps` (`Stage A` through `Stage D`).
3. **4-Stage Epistemic Sequence**:
   - `Stage A`: Asset Identity, CMDB Context, & SOAR Case Correlation (`lookup_entity`, `list_cases`).
   - `Stage B`: Network Routing & Scope Verification (`PUBLIC`, `PRIVATE`, RFC-5737 documentation space).
   - `Stage C`: Threat Intelligence Reputation (`get_ip_address_report`, `get_domain_report`, `get_file_report`).
   - `Stage D`: Behavioral Corroboration (`search_security_events`), Verdict, and Action.
4. **Input Slot Syntax**: Use `<angle_bracket>` input slots (`<source_ip>`, `<hostname>`). Never use `${VAR_NAME}` shell placeholders (`forbid_template_vars=True`).
5. **No Diagrams**: Never include Mermaid `sequenceDiagram` blocks or ASCII flowcharts (`forbid_mermaid_diagrams=True`).
6. **No IDE Pseudo-Tools**: Reference only registered sandbox/MCP tools. Never reference interactive Cline pseudo-tools (`ask_followup_question`, `attempt_completion`, `write_to_file`, `generate_report_file.md`; `forbid_interactive_pseudotools=True`).
7. **No Short-Circuit Directives**: Never instruct the agent to `"skip all enrichment"` or `"proceed directly to step N"`. Every investigation requires `epistemic_step_count >= 1`.
8. **No Hardcoded Benchmark Literals**: Never include literal IPv4/CIDR addresses, benchmark hostnames, `CASE-` IDs, or Gen 5 `manifest.forbidden_literals`.
9. **Mutually Exclusive Stage D Verdict Rules**: Specify exact conditions and actions for `MALICIOUS`, `SUSPICIOUS`, `INCONCLUSIVE`, and `BENIGN`, and avoid negated verdict substrings (`"not a false positive"`, `"not command and control"`).
10. **Pre-Commit Validation Gate**: Run `just lint-runbooks` before committing runbook changes:

```bash
WORKTREE_DIR="/usr/local/google/home/dandye/Projects/gemma_deploy__worktrees/dspy__context-engineering"
cd "$WORKTREE_DIR"
just lint-runbooks
```
