---
name: cloud-safety
description: Safety gating, read-only preview requirements, and human confirmation enforcement for destructive cloud actions.
---

# Cloud Safety & Teardown Guardrails

## Core Operational Rules
1. **Non-Destructive Preview Before Mutation:**
   - Destructive operations (batch deletions, instance termination, infrastructure teardown) must always be preceded by a non-destructive read-only preview.
   - Example: Run `gcloud compute instances list --filter="name:..." --format="table(name, status)"` before any deletion.
2. **Mandatory Human Confirmation Gate:**
   - Never silently execute destructive operations in batch mode with `--quiet` without preceding preview and explicit human consent.
   - Present candidate resources and halt for explicit confirmation.
3. **Refuse Filter-Based Deletion Syntax Hallucinations:**
   - Note that `gcloud compute instances delete` accepts explicit positional instance names and does NOT accept a direct `--filter` flag for deletion.
