---
name: gcp-auth
description: Cloud IAM identity standards, least-privilege scoping, and Application Default Credentials.
---

# GCP Identity & Authentication Standards

## Core Operational Rules
1. **Prohibit Downloadable Service Account Keys:**
   - Never create or download static service account JSON keys due to credential leakage, lack of rotation, and security risk.
2. **Application Default Credentials (ADC):**
   - For local developer identities, use `gcloud auth application-default login` or `gcloud auth login <ACCOUNT> --update-adc`.
   - Runtimes on Compute Engine, Cloud Run, and Vertex AI automatically receive credentials via the metadata server.
3. **Service Account Impersonation:**
   - Assume service identities securely using impersonation with `roles/iam.serviceAccountTokenCreator`.
4. **Resource-Level IAM Scoping:**
   - When granting access to resources (e.g. Secret Manager secrets across projects), scope the IAM binding directly to the individual resource:
     `gcloud secrets add-iam-policy-binding <secret> --project=<sec-project> --member="serviceAccount:<sa>@<app-project>.iam.gserviceaccount.com" --role="roles/secretmanager.secretAccessor"`.
   - Avoid project-wide broad IAM roles.
