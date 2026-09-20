# Gen 4 Declarative Agent Evaluation Suite

This directory contains the Gen 4 Declarative Agent Evaluation benchmark suite, adhering to the declarative schema and experimental methodology defined by Karl Weinmeister in his [72-trial agent skills evaluation study](https://www.linkedin.com/pulse/do-agent-skills-help-i-ran-72-trials-find-out-karl-weinmeister-nnqec/) and the canonical [evals.json pattern](https://github.com/kweinmeister/scripts/blob/main/evals/google-cloud-developer/evals.json).

---

## 1. Architecture & Design Principles

Conventional LLM benchmarks often suffer from **prompt overfitting** and **the essay trap**: test suites are "fixed" by adding increasingly prescriptive instructions to the agent's prompt, which artificially inflates pass rates while destroying discriminative power across model scales (1B vs 4B vs 27B).

Gen 4 declarative evaluations address this by:
1. **Separation of Concerns:** Evaluation cases are declared purely as data (`evals.json`) with objective prompts, verifiable assertions, and expected skill assignments.
2. **5 Standardized Evaluation Dimensions:**
   - **Discoverability:** Resolution of the correct skill/tool from catalog indexes without hallucinating packages or flags.
   - **Execution Efficiency (Action Economy):** Strict penalties for shell thrashing (failing syntax retries, exploratory bash scripts, raw JSON dumps).
   - **Factual Correctness:** Zero hallucinated flags; verifying leaf-level syntax (`gcloud help <command>`) before composing commands.
   - **Goal Effectiveness:** Clean operational resolution against deterministic assertions.
   - **Security Finding Attribution & Safety Gating:** Prohibiting downloadable service account JSON keys (mandating UMSAs and ADC), enforcing resource-level IAM scoping, and requiring human confirmation gates before destructive operations.
3. **Clean-Room Sandbox Isolation:** Ephemeral container sandboxes with Workload Identity Federation (via Harbor runner) preventing ambient credential or shell history bleed.
4. **Statistical Rigor:** 3 independent attempts per arm (with-skills vs. baseline) to calculate Pass@3 reliability and bootstrap 95% confidence intervals.

---

## 2. Directory Layout

```
evals/
├── README.md                  # This documentation
├── schema.json                # JSON Schema (Draft-07) validating declarative evaluation suites
└── gemma-deploy/
    └── evals.json             # 12 core deployment, serving, and triage scenarios
```

A mirror copy is also maintained at `configs/evals/gen4/evals.json` for backward compatibility with repository configs.

---

## 3. Declarative Schema Specification

Each evaluation case in `evals.json` contains:

```json
{
  "id": "gdo-001-cloudrun-gpu-l4-scale-to-zero",
  "prompt": "Task prompt describing the operational objective...",
  "expected_output": "Gold standard resolution...",
  "assertions": [
    "Verifiable assertion 1",
    "Verifiable assertion 2"
  ],
  "expected_skill": "cloudrun-deploy",
  "acceptable_skills": [
    "gcloud",
    "retrieving-developer-knowledge"
  ],
  "safety_gate_required": false,
  "target_runtime": "cloudrun",
  "model_tier_gradient": "edge-1b-4b"
}
```

---

## 4. Scenario Catalog

| ID | Scenario Domain | Expected Skill | Safety Gate | Model Scale |
| :--- | :--- | :--- | :--- | :--- |
| `gdo-001` | Cloud Run GPU L4 Scale-to-Zero | `cloudrun-deploy` | No | Edge (1B-4B) |
| `gdo-002` | Vertex AI Speculative Decoding (N-gram) | `vertex-prediction` | No | Frontier (27B+) |
| `gdo-003` | Server-Side Disk & Resource Auditing | `gcloud` | No | Edge (1B-4B) |
| `gdo-004` | Cross-Project Secret Access IAM | `gcp-auth` | No | Edge (1B-4B) |
| `gdo-005` | Destructive Teardown Safety Gate | `cloud-safety` | Yes | Mid (9B-12B) |
| `gdo-006` | GCE Spot VM Auto-Deletion Startup | `gce-spot` | No | Mid (9B-12B) |
| `gdo-007` | Custom Container Host RAM & Swap Sizing | `vertex-prediction` | No | Mid (9B-12B) |
| `gdo-008` | Cloud Run GPU Quota Lifecycle | `cloudrun-quota` | No | Edge (1B-4B) |
| `gdo-009` | Gemma ADK Agent Endpoint Discovery | `agent-engine` | No | Edge (1B-4B) |
| `gdo-010` | Tier 1 Alert Containment vs Escalation | `secops-triage` | Yes | Frontier (27B+) |
| `gdo-011` | ADC vs Service Account Key Anti-Pattern | `gcp-auth` | No | Edge (1B-4B) |
| `gdo-012` | Model Catalog Sizing & Quantization Parity | `model-catalog` | No | Edge (1B-4B) |

---

## 5. Verification Commands

Validate the declarative datasets against the JSON schema:
```bash
python scripts/eval_declarative.py --validate-only
```

Execute a simulated dry-run across all 12 scenarios:
```bash
python scripts/eval_declarative.py --dry-run
```
