---
name: cloudrun-quota
description: Lifecycle management, non-interactive requests, and reset procedures for Cloud Run GPU quotas.
---

# Cloud Run GPU Quota Lifecycle

## Core Operational Rules
1. **Target Service and Quota Identifiers:**
   - Service: `run.googleapis.com`
   - Quota ID: `NvidiaL4GpuAllocNoZonalRedundancyPerProjectRegion`
2. **Requesting Quota Increase:**
   - Use `gcloud quotas preferences update` (or `create`) with `--service=run.googleapis.com --quota-id=NvidiaL4GpuAllocNoZonalRedundancyPerProjectRegion --preferred-value=1` in region (e.g. `europe-west4` or `us-central1`).
3. **Resetting Quota Preference to Prevent Sprawl:**
   - When batch testing concludes, reset the preference:
     `gcloud quotas preferences update --service=run.googleapis.com --quota-id=NvidiaL4GpuAllocNoZonalRedundancyPerProjectRegion --preferred-value=0`
   - Ensure non-interactive execution.
