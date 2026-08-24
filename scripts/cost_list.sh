#!/usr/bin/env bash
set -euo pipefail

echo "=========================================================================================="
echo " Gemma Infrastructure Cost & Sizing Matrix (us-central1)"
echo "=========================================================================================="
echo ""
echo "=== 1. Vertex AI Dedicated GPU Instances (Billed 24/7 while deployed) ==="
cat << 'TABLE'
+----------------+----------------------+---------+----------+-----------+-----------+------------+------------+
| MACHINE TYPE   | ACCELERATORS         | VRAM    | HOST RAM | HOURLY    | WEEKLY    | MONTHLY    | BIZ HOURS  |
|                |                      |         |          | ($/hr)    | (168 hrs) | (730 hrs)  | (160 hrs)  |
+----------------+----------------------+---------+----------+-----------+-----------+------------+------------+
| g2-standard-4  | 1x NVIDIA L4 (24GB)  | 24 GB   | 16 GB    | $0.70     | $117.60   | $511.00    | $112.00    |
| g2-standard-8  | 1x NVIDIA L4 (24GB)  | 24 GB   | 32 GB    | $0.76     | $127.68   | $554.80    | $121.60    |
| g2-standard-12 | 1x NVIDIA L4 (24GB)  | 24 GB   | 48 GB    | $0.83     | $139.44   | $605.90    | $132.80    |
| g2-standard-16 | 1x NVIDIA L4 (24GB)  | 24 GB   | 64 GB    | $0.89     | $149.52   | $649.70    | $142.40    |
| g2-standard-24 | 2x NVIDIA L4 (48GB)  | 48 GB   | 96 GB    | $1.68     | $282.24   | $1,226.40  | $268.80    |
| g2-standard-48 | 4x NVIDIA L4 (96GB)  | 96 GB   | 192 GB   | $3.36     | $564.48   | $2,452.80  | $537.60    |
| a2-highgpu-1g  | 1x A100 (40GB)       | 40 GB   | 85 GB    | $3.67     | $616.56   | $2,679.10  | $587.20    |
| a2-ultragpu-1g | 1x A100 (80GB)       | 80 GB   | 85 GB    | $4.50     | $756.00   | $3,285.00  | $720.00    |
+----------------+----------------------+---------+----------+-----------+-----------+------------+------------+
TABLE

echo ""
echo "=== 2. Cloud Run with GPU (Serverless Scale-to-Zero) ==="
cat << 'TABLE'
+-------------------------+----------------------+--------------------+--------------------+
| IDLE STATE              | ACTIVE INFERENCE     | MIN INSTANCES = 0  | REQUEST COST       |
+-------------------------+----------------------+--------------------+--------------------+
| $0.00 / hour (0 cost)   | ~$0.80 / active hour | Scale-to-Zero ON   | Billed per second  |
+-------------------------+----------------------+--------------------+--------------------+
TABLE

echo ""
echo "Note: For complete sizing analysis and quantization trade-offs, see docs/cost_analysis.md"
echo "=========================================================================================="
