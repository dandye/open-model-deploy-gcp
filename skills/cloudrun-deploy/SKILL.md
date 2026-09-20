---
name: cloudrun-deploy
description: Guidelines and recipes for deploying models and workloads to Cloud Run with GPU support and scale-to-zero.
---

# Cloud Run GPU Deployment Guide

## Core Operational Rules
1. **GPU Acceleration Configuration:**
   - Always specify `--gpu 1` and `--gpu-type nvidia-l4` (or target accelerator type).
   - Enforce `--execution-environment gen2`.
2. **Scale-to-Zero and Billing:**
   - Always set `--min-instances 0` to enable scale-to-zero when idle ($0 idle compute cost).
   - Understand that Cloud Run GPU quota (`run.googleapis.com`) is separate from Compute Engine and Vertex AI GPU quota.
3. **Compute and Memory Limits:**
   - Ensure adequate host memory: 4 vCPU supports max 16Gi RAM (`--memory 16Gi --cpu 4`).
   - Higher memory allocations (24Gi, 32Gi) require 8 vCPU (`--cpu 8`).
4. **Volume Mounts and Secrets:**
   - GCS Volumes: `--add-volume="name=vol-name,type=cloud-storage,bucket=bucket-name,readonly=true"` and `--add-volume-mount="volume=vol-name,mount-path=/mnt/path"`.
   - Secret Manager: `--update-secrets` or `--set-secrets="KEY=secret-name:latest"`.
