---
name: gcloud
description: Best practices for non-interactive execution, leaf-level help checks, and server-side filtering with gcloud CLI.
---

# gcloud CLI Best Practices

## Core Operational Rules
1. **Leaf-Level Help Checks Before Composing Commands:**
   - When uncertain of parameters or subcommands, always inspect `gcloud help <group> <subcommand>` first.
   - Never invent or guess CLI flag names.
2. **Server-Side Filtering and Projection:**
   - Always push filtering and projection to the server using `--filter` and `--format`.
   - Example: `gcloud compute disks list --project="$PROJECT_ID" --filter="-users:*" --format="table(name, zone, sizeGb)"`.
   - Never pipe large raw JSON dumps through local grep, jq, or awk for core filtering.
3. **Non-Interactive Execution:**
   - In automated pipelines, use `--format=json` or `--format=value(...)`.
   - Use named configurations (`gcloud config configurations activate <name>`) or `CLOUDSDK_ACTIVE_CONFIG_NAME` rather than interactive prompts.
