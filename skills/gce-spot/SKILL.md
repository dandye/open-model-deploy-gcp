---
name: gce-spot
description: Ephemeral Compute Engine Spot GPU VM deployment, Local NVMe SSD mounting, and guaranteed zero-idle self-deletion.
---

# GCE Spot VM Ephemeral Batch Benchmarking

## Core Operational Rules
1. **Spot/Preemptible Provisioning:**
   - Configure `--provisioning-model=SPOT` or `--preemptible` for cost-optimized batch workloads.
2. **Local NVMe SSD Scratch Storage:**
   - Format and mount local NVMe SSD storage under `/mnt/disks/nvme` with filesystem verification.
3. **Guaranteed Self-Deletion on Completion:**
   - Startup scripts must trap EXIT and ERR to guarantee termination and deletion via:
     `gcloud compute instances delete "$(hostname)" --zone="$ZONE" --quiet` or `shutdown -h now`.
   - Prevent idle compute billing leaks even if benchmarking errors occur.
4. **Artifact Synchronization:**
   - Stream or upload benchmark scorecards, metrics, and logs to a Cloud Storage bucket before instance deletion.
