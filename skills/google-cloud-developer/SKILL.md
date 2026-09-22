---
name: google-cloud-developer
description: Developer guidelines and best practices for Google Cloud development, deployment, authentication, and resource management.
---

# Google Cloud Developer Guidelines

## Core Principles

1. **Authentication & Identity**:
   - Always use User-Managed Service Accounts (UMSA) for Cloud Run services and jobs.
   - Use Application Default Credentials (ADC) or service account impersonation (`roles/iam.serviceAccountTokenCreator`) for local development.
   - Never download or commit service account JSON keys.
   - Avoid using the default Compute Engine service account.

2. **Least Privilege Resource-Level IAM**:
   - Bind IAM roles at the specific resource level (e.g. `gcloud secrets add-iam-policy-binding` or `gcloud run services add-iam-policy-binding`) rather than project-wide bindings (`gcloud projects add-iam-policy-binding`).

3. **Server-Side Filtering & Projection**:
   - Use `--filter` and `--format="table(...)"` flags on `gcloud` commands to filter server-side.
   - Avoid piping raw JSON output to local shell utilities like `grep`, `awk`, or `jq`.

4. **Non-Interactive Execution**:
   - In CI/CD or automated environments, use `--format=json`, `--quiet`, and named configurations (`gcloud config configurations activate`) or `CLOUDSDK_ACTIVE_CONFIG_NAME`.

5. **Cloud Run Storage & Secrets**:
   - Mount Cloud Storage buckets using `--add-volume=name=...,type=cloud-storage,bucket=...,readonly=true` and `--add-volume-mount=volume=...,mount-path=...`.
   - Inject secrets from Secret Manager using `--set-secrets` or `--update-secrets`.

6. **Safety Gates for Destructive Actions**:
   - Before deleting resources in batch (such as `gcloud compute instances delete`), always perform a non-destructive preview listing (`gcloud compute instances list --filter=...`).
   - Require explicit human confirmation before executing deletions.
