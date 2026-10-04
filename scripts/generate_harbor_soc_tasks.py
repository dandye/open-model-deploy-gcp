#!/usr/bin/env python3
"""Generates Harbor v1.3 SOC Tier 1 tasks: Gen 5 family-instanced splits by default, the frozen Gen 3 suite behind --gen3."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import sys
import tempfile
from typing import Any, Dict, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.gen5_instancer import canonical_json, sha256_text
from scripts.gen5_reference_policies import plan_oracle

EVALSET_PATH = ROOT_DIR / "configs" / "evals" / "gen3" / "soc_tier1_interactive.json"
CLEAN_SKILL_PATH = ROOT_DIR / "skills" / "secops-triage" / "SKILL.md"
NOISY_SKILL_PATH = ROOT_DIR / "skills" / "secops-triage" / "noisy" / "verbose_lore.md"
DEFAULT_GEPA_RUNBOOKS_DIR = Path("/usr/local/google/home/dandye/Projects/gemma_deploy__worktrees/disciplined_hillclimber_v0001/configs/runbooks/gepa_evolved")
DEFAULT_HARBOR_OUT = ROOT_DIR / "evals" / "harbor_soc"
DEFAULT_EVALS_JSON_OUT = ROOT_DIR / "skills" / "secops-triage" / "evals" / "evals.json"

SKILL_ARMS = ("no_skills", "clean_skills", "noisy_skills", "gepa_evolved_skills")

# --- Gen 5 (spec sections 7.3 and 9.4; plan decision 9) ---

GEN5_ROOT = ROOT_DIR / "configs" / "evals" / "gen5"
GEN5_MANIFEST_PATH = GEN5_ROOT / "manifest.json"
DEFAULT_GEN5_HARBOR_OUT = ROOT_DIR / "evals" / "harbor_soc_gen5"
DEFAULT_GEN5_RUNBOOKS_DIR = ROOT_DIR / "configs" / "runbooks" / "gepa_evolved"
DEFAULT_GEN5_ARMS: Tuple[str, ...] = ("clean_skills", "gepa_evolved_skills")
GEN5_HARBOR_SPLITS: Tuple[str, ...] = ("validation", "final_test")
GEN5_GENERATOR_VERSION = "harbor-soc-gen5-1"
GEN5_CONTAINER_STATE_BUNDLE_REL = "configs/evals/gen5/state_bundle.json"
# What the image may know about a case: the world and the alert, never the answer key.
GEN5_STATE_KEYS: Tuple[str, ...] = (
    "eval_id", "generation", "prompt", "asset_criticality", "cmdb_context",
    "environment_state", "fault_injection",
)
# Mirrors CORE_RUNBOOKS in agent/gepa_runbook_optimizer.py; duplicated so the generator
# does not import the optimizer (and its model clients). A test asserts equality.
GEN5_EVOLVED_RUNBOOKS: Tuple[str, ...] = (
    "basic_ioc_enrichment.md",
    "suspicious_login_triage.md",
    "malware_triage.md",
    "lateral_movement_hunt_psexec_wmi.md",
)
GEN5_DIFFICULTY_NAMES = {1: "easy", 2: "medium", 3: "hard"}
GEN5_TASK_FILES: Tuple[str, ...] = (
    "task.toml", "instruction.md", "solution/solve.sh", "tests/test.sh", "tests/case.json", "tests/manifest.json",
)

GEN5_DOCKERFILE_CONTENT = """FROM python:3.11-slim

WORKDIR /app

COPY soc_environment.py /app/agent/soc_environment.py
COPY j_init.py /app/agent/__init__.py
COPY jev_judge.py /app/agent/jev_judge.py
COPY jev_evaluator.py /app/agent/jev_evaluator.py
COPY j_init.py /app/scripts/__init__.py
COPY eval_trajectory_verifier.py /app/scripts/eval_trajectory_verifier.py
COPY eval_cost_engine.py /app/scripts/eval_cost_engine.py
COPY soc_sandbox_cli.py /app/scripts/soc_sandbox_cli.py
COPY verify_harbor_soc.py /app/scripts/verify_harbor_soc.py
COPY state_bundle.json /app/configs/evals/gen5/state_bundle.json

RUN mkdir -p /var/lib/soc /logs/artifacts /logs/verifier && \\
    ln -sf /app/scripts/soc_sandbox_cli.py /usr/local/bin/soc-cli && \\
    chmod +x /app/scripts/soc_sandbox_cli.py /app/scripts/verify_harbor_soc.py /usr/local/bin/soc-cli
"""

GEPA_CASE_RUNBOOK_MAP: Dict[str, str] = {
    "CASE-GEN3-01-LOKIBOT-C2": "basic_ioc_enrichment.md",
    "CASE-GEN3-02-RFC5737-BENIGN-IP": "suspicious_login_triage.md",
    "CASE-GEN3-03-PHISHING-CRED-HARVEST": "basic_ioc_enrichment.md",
    "CASE-GEN3-04-DUPLICATE-SOAR-CASE": "basic_ioc_enrichment.md",
    "CASE-GEN3-05-RANSOMWARE-ESCALATION": "malware_triage.md",
    "CASE-GEN3-06-AMBIGUOUS-DNS-TUNNEL": "basic_ioc_enrichment.md",
    "CASE-GEN3-07-LATERAL-MOVEMENT-PSEXEC": "lateral_movement_hunt_psexec_wmi.md",
    "CASE-GEN3-08-SUPPLY-CHAIN-REVOKED-CERT": "malware_triage.md",
    "CASE-GEN3-09-TOOL-503-OUTAGE-RESILIENCE": "basic_ioc_enrichment.md",
    "CASE-GEN3-10-AUTHORIZED-SCANNER-NOISE": "basic_ioc_enrichment.md",
}

# Canonical oracle recipes for each of the 10 Gen 3 cases
ORACLE_RECIPES: Dict[str, Dict[str, Any]] = {
    "CASE-GEN3-01-LOKIBOT-C2": {
        "commands": [
            'get_domain_report --domain "update-service-win32.com"',
            'lookup_entity --entity_id "DESKTOP-FIN-08"',
            'isolate_host --hostname "DESKTOP-FIN-08"',
            'update_case_comment --case_id "CASE-33279" --comment "Confirmed Lokibot C2 beaconing from DESKTOP-FIN-08 (10.0.4.15) to update-service-win32.com. Host isolated."',
        ],
        "verdict": "MALICIOUS",
        "executed_actions": ["isolate_host", "update_case_comment"],
        "report": (
            "# SOC Tier 1 Triage Report: CASE-GEN3-01-LOKIBOT-C2\n\n"
            "- **Target Host:** DESKTOP-FIN-08 (10.0.4.15)\n"
            "- **Indicator:** update-service-win32.com\n"
            "- **Threat Verdict:** MALICIOUS (Lokibot InfoStealer C2)\n"
            "- **Containment Executed:** Executed `isolate_host` on DESKTOP-FIN-08 and recorded IOCs via `update_case_comment`.\n"
        ),
    },
    "CASE-GEN3-02-RFC5737-BENIGN-IP": {
        "commands": [
            'get_ip_report --ip "192.0.2.100"',
            'close_case --case_id "CASE-33279" --verdict "BENIGN"',
        ],
        "verdict": "BENIGN",
        "executed_actions": ["close_case"],
        "report": (
            "# SOC Tier 1 Triage Report: CASE-GEN3-02-RFC5737-BENIGN-IP\n\n"
            "- **Source IP:** 192.0.2.100\n"
            "- **Target Gateway:** GW-CORE-VPN-01\n"
            "- **Routing Classification:** Reserved RFC-5737 TEST-NET-1 non-routable documentation subnet.\n"
            "- **Verdict:** BENIGN. Closed case via `close_case` without host isolation or indicator blocking.\n"
        ),
    },
    "CASE-GEN3-03-PHISHING-CRED-HARVEST": {
        "commands": [
            'get_domain_report --domain "evil.com"',
            'lookup_entity --entity_id "john.doe" --entity_type "user"',
            'block_indicator --indicator "evil.com"',
            'update_case_comment --case_id "CASE-33279" --comment "Blocked credential harvesting domain evil.com targeted at john.doe."',
        ],
        "verdict": "MALICIOUS",
        "executed_actions": ["block_indicator", "update_case_comment"],
        "report": (
            "# SOC Tier 1 Triage Report: CASE-GEN3-03-PHISHING-CRED-HARVEST\n\n"
            "- **Targeted User:** john.doe on DESKTOP-MKT-14\n"
            "- **Malicious Domain:** evil.com\n"
            "- **Verdict:** MALICIOUS phishing credential harvesting campaign.\n"
            "- **Actions Executed:** Blocked `evil.com` via `block_indicator` and updated case documentation via `update_case_comment`.\n"
        ),
    },
    "CASE-GEN3-04-DUPLICATE-SOAR-CASE": {
        "commands": [
            'get_case --case_id "CASE-33279"',
            'get_ip_report --ip "198.51.100.42"',
            'update_case_comment --case_id "CASE-33279" --comment "Correlated IP 198.51.100.42 with existing open SOAR case CASE-33279 on DESKTOP-ENG-22."',
        ],
        "verdict": "SUSPICIOUS",
        "executed_actions": ["update_case_comment"],
        "report": (
            "# SOC Tier 1 Triage Report: CASE-GEN3-04-DUPLICATE-SOAR-CASE\n\n"
            "- **Existing SOAR Ticket:** CASE-33279\n"
            "- **Correlated Indicator:** 198.51.100.42\n"
            "- **Verdict:** SUSPICIOUS duplicate correlation.\n"
            "- **Actions Executed:** Appended correlation notes to open ticket 33279 via `update_case_comment` without creating a duplicate case.\n"
        ),
    },
    "CASE-GEN3-05-RANSOMWARE-ESCALATION": {
        "commands": [
            'lookup_entity --entity_id "DESKTOP-FIN-08"',
            'get_ip_report --ip "10.0.5.23"',
            'isolate_host --hostname "DESKTOP-FIN-08"',
            'update_case_comment --case_id "CASE-33279" --comment "Critical ransomware outbreak on DESKTOP-FIN-08 (10.0.5.23). Isolated host immediately; do not reboot."',
        ],
        "verdict": "MALICIOUS",
        "executed_actions": ["isolate_host", "update_case_comment"],
        "report": (
            "# SOC Tier 1 Triage Report: CASE-GEN3-05-RANSOMWARE-ESCALATION\n\n"
            "- **Compromised Asset:** DESKTOP-FIN-08 (10.0.5.23)\n"
            "- **Verdict:** MALICIOUS active ransomware infection.\n"
            "- **Containment Executed:** Immediately isolated DESKTOP-FIN-08 (10.0.5.23) via `isolate_host`, instructed against rebooting, and escalated via `update_case_comment`.\n"
        ),
    },
    "CASE-GEN3-06-AMBIGUOUS-DNS-TUNNEL": {
        "commands": [
            'get_domain_report --domain "tunnel-data.cdn-edge-update.net"',
            'lookup_entity --entity_id "DESKTOP-FIN-08"',
            'update_case_comment --case_id "CASE-33279" --comment "Borderline suspicious TXT lookups to tunnel-data.cdn-edge-update.net on CFO workstation DESKTOP-FIN-08. Avoided host isolation to prevent $50k downtime; escalated for packet capture."',
        ],
        "verdict": "INCONCLUSIVE",
        "executed_actions": ["update_case_comment"],
        "report": (
            "# SOC Tier 1 Triage Report: CASE-GEN3-06-AMBIGUOUS-DNS-TUNNEL\n\n"
            "- **Asset:** DESKTOP-FIN-08 (CFO Workstation)\n"
            "- **Domain:** tunnel-data.cdn-edge-update.net\n"
            "- **Verdict:** INCONCLUSIVE / BORDERLINE_SUSPICIOUS.\n"
            "- **Actions Executed:** Avoided disruptive isolation on DESKTOP-FIN-08 to prevent $50k false-positive downtime and logged escalation notes via `update_case_comment`.\n"
        ),
    },
    "CASE-GEN3-07-LATERAL-MOVEMENT-PSEXEC": {
        "commands": [
            'lookup_entity --entity_id "DESKTOP-HR-04"',
            'get_ip_report --ip "10.0.8.99"',
            'isolate_host --hostname "DESKTOP-HR-04"',
            'update_case_comment --case_id "CASE-33279" --comment "Confirmed PsExec lateral movement by mwilson on DESKTOP-HR-04 (10.0.8.99). Isolated host."',
        ],
        "verdict": "MALICIOUS",
        "executed_actions": ["isolate_host", "update_case_comment"],
        "report": (
            "# SOC Tier 1 Triage Report: CASE-GEN3-07-LATERAL-MOVEMENT-PSEXEC\n\n"
            "- **Compromised Host:** DESKTOP-HR-04 (10.0.8.99)\n"
            "- **Account:** mwilson\n"
            "- **Verdict:** MALICIOUS PsExec SMB lateral movement (MITRE T1021.002).\n"
            "- **Containment Executed:** Isolated DESKTOP-HR-04 (10.0.8.99) via `isolate_host` and documented via `update_case_comment`.\n"
        ),
    },
    "CASE-GEN3-08-SUPPLY-CHAIN-REVOKED-CERT": {
        "commands": [
            'get_file_report --file_hash "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90"',
            'block_indicator --indicator "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90"',
            'update_case_comment --case_id "CASE-33279" --comment "Blocked supply-chain binary invoice_update.exe (a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90) signed with revoked Acme Corp certificate."',
        ],
        "verdict": "MALICIOUS",
        "executed_actions": ["block_indicator", "update_case_comment"],
        "report": (
            "# SOC Tier 1 Triage Report: CASE-GEN3-08-SUPPLY-CHAIN-REVOKED-CERT\n\n"
            "- **Binary:** invoice_update.exe\n"
            "- **SHA-256:** a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90\n"
            "- **Signer Status:** Revoked Acme Corp code-signing certificate (`REVOKED_BY_CA`).\n"
            "- **Verdict:** MALICIOUS supply-chain anomaly. Blocked hash via `block_indicator` and documented via `update_case_comment`.\n"
        ),
    },
    "CASE-GEN3-09-TOOL-503-OUTAGE-RESILIENCE": {
        "commands": [
            'get_domain_report --domain "error-503.service-unavailable.org"',
            'update_case_comment --case_id "CASE-33279" --comment "Upstream threat intelligence returned HTTP 503 Service Unavailable for error-503.service-unavailable.org. Recorded degraded inconclusive status without premature isolation or closure."',
        ],
        "verdict": "INCONCLUSIVE",
        "executed_actions": ["update_case_comment"],
        "report": (
            "# SOC Tier 1 Triage Report: CASE-GEN3-09-TOOL-503-OUTAGE-RESILIENCE\n\n"
            "- **Domain:** error-503.service-unavailable.org\n"
            "- **Tool Status:** HTTP 503 Service Unavailable outage encountered on `get_domain_report`.\n"
            "- **Verdict:** INCONCLUSIVE_DEGRADED. Documented 503 outage in `update_case_comment` and avoided unverified containment or case closure.\n"
        ),
    },
    "CASE-GEN3-10-AUTHORIZED-SCANNER-NOISE": {
        "commands": [
            'lookup_entity --entity_id "SRV-PROD-PAYMENT-01"',
            'get_ip_report --ip "10.0.99.50"',
            'update_case_comment --case_id "CASE-17305" --comment "Verified internal scan on SRV-PROD-PAYMENT-01 (10.0.99.50) is authorized Qualys Scanner maintenance."',
            'close_case --case_id "CASE-17305" --verdict "BENIGN"',
        ],
        "verdict": "BENIGN",
        "executed_actions": ["update_case_comment", "close_case"],
        "report": (
            "# SOC Tier 1 Triage Report: CASE-GEN3-10-AUTHORIZED-SCANNER-NOISE\n\n"
            "- **Host:** SRV-PROD-PAYMENT-01 (10.0.99.50)\n"
            "- **Finding:** Authorized internal Qualys Scanner vulnerability maintenance.\n"
            "- **Verdict:** BENIGN. Updated case comments via `update_case_comment` and resolved alert via `close_case` without isolating the payment server.\n"
        ),
    },
}

DOCKERFILE_CONTENT = """FROM python:3.11-slim

WORKDIR /app

COPY soc_environment.py /app/agent/soc_environment.py
COPY j_init.py /app/agent/__init__.py
COPY jev_judge.py /app/agent/jev_judge.py
COPY jev_evaluator.py /app/agent/jev_evaluator.py
COPY j_init.py /app/scripts/__init__.py
COPY eval_trajectory_verifier.py /app/scripts/eval_trajectory_verifier.py
COPY eval_cost_engine.py /app/scripts/eval_cost_engine.py
COPY soc_sandbox_cli.py /app/scripts/soc_sandbox_cli.py
COPY verify_harbor_soc.py /app/scripts/verify_harbor_soc.py
COPY soc_tier1_interactive.json /app/soc_tier1_interactive.json
COPY soc_tier1_interactive.json /app/configs/evals/gen3/soc_tier1_interactive.json

RUN mkdir -p /var/lib/soc /logs/artifacts /logs/verifier && \\
    ln -sf /app/scripts/soc_sandbox_cli.py /usr/local/bin/soc-cli && \\
    chmod +x /app/scripts/soc_sandbox_cli.py /app/scripts/verify_harbor_soc.py /usr/local/bin/soc-cli
"""


def _case_slug(eval_id: str) -> str:
    """CASE-GEN3-01-LOKIBOT-C2 -> case-01-lokibot-c2; CASE-GEN5-C2-INFOSTEALER-01 -> case-c2-infostealer-01."""
    return re.sub(r"^case-gen\d+-", "case-", eval_id.lower())


def compute_environment_hash(env_dir: Path) -> str:
    """Computes a deterministic SHA-256 hash over all files in environment/."""
    hasher = hashlib.sha256()
    for path in sorted(env_dir.rglob("*")):
        if path.is_file():
            rel = path.relative_to(env_dir).as_posix()
            hasher.update(rel.encode("utf-8"))
            hasher.update(b"\0")
            hasher.update(path.read_bytes())
            hasher.update(b"\0")
    return hasher.hexdigest()


def _populate_identical_environment(env_dir: Path) -> None:
    """Copies the shared sandbox runtime into task_dir/environment/."""
    env_dir.mkdir(parents=True, exist_ok=True)
    (env_dir / "Dockerfile").write_text(DOCKERFILE_CONTENT, encoding="utf-8")
    (env_dir / "j_init.py").write_text('"""Package init."""\n', encoding="utf-8")

    file_map = {
        "soc_environment.py": ROOT_DIR / "agent" / "soc_environment.py",
        "jev_judge.py": ROOT_DIR / "agent" / "jev_judge.py",
        "jev_evaluator.py": ROOT_DIR / "agent" / "jev_evaluator.py",
        "eval_trajectory_verifier.py": ROOT_DIR / "scripts" / "eval_trajectory_verifier.py",
        "eval_cost_engine.py": ROOT_DIR / "scripts" / "eval_cost_engine.py",
        "soc_sandbox_cli.py": ROOT_DIR / "scripts" / "soc_sandbox_cli.py",
        "verify_harbor_soc.py": ROOT_DIR / "scripts" / "verify_harbor_soc.py",
        "soc_tier1_interactive.json": EVALSET_PATH,
    }
    for dest_name, src_path in file_map.items():
        shutil.copyfile(src_path, env_dir / dest_name)


def _build_task_toml(case: Dict[str, Any], arm: str, slug: str) -> str:
    """Renders Harbor schema_version = 1.3 task.toml."""
    eval_id = case["eval_id"]
    name = f"secops/soc-{arm}-{slug}"
    desc = f"{case['name']} ({arm} arm)"
    crit = case.get("asset_criticality", "STANDARD")
    label = case.get("ground_truth_label", "UNKNOWN")

    return f"""version = "1.0"
schema_version = "1.3"

[task]
name = "{name}"
description = "{desc}"
categories = ["security", "soc-tier1", "gen3-interactive", "{arm}"]

[metadata]
author_name = "Dan Dye"
author_email = "dandye@google.com"
difficulty = "medium"
category = "security-operations"
tags = ["secops", "soc-tier1", "harbor", "{arm}", "{eval_id}"]
eval_id = "{eval_id}"
skill_arm = "{arm}"
asset_criticality = "{crit}"
ground_truth_label = "{label}"

[verifier]
timeout_sec = 120.0

[agent]
timeout_sec = 300.0

[environment]
network_mode = "public"
build_timeout_sec = 300.0
cpus = 2
memory_mb = 2048
storage_mb = 4096
allow_internet = false

[environment.env]
SOC_CASE_ID = "{eval_id}"
SOC_SKILL_ARM = "{arm}"
SOC_STATE_FILE = "/var/lib/soc/state.json"
SOC_TRAJECTORY_FILE = "/logs/artifacts/trajectory.jsonl"

[agent.env]
SOC_CASE_ID = "{eval_id}"
SOC_SKILL_ARM = "{arm}"
SOC_STATE_FILE = "/var/lib/soc/state.json"
SOC_TRAJECTORY_FILE = "/logs/artifacts/trajectory.jsonl"

[verifier.env]
SOC_CASE_ID = "{eval_id}"
SOC_SKILL_ARM = "{arm}"
SOC_STATE_FILE = "/var/lib/soc/state.json"
SOC_TRAJECTORY_FILE = "/logs/artifacts/trajectory.jsonl"
SOC_JEV_BACKEND = "mock"

[solution.env]
SOC_CASE_ID = "{eval_id}"
SOC_SKILL_ARM = "{arm}"
SOC_STATE_FILE = "/var/lib/soc/state.json"
SOC_TRAJECTORY_FILE = "/logs/artifacts/trajectory.jsonl"
"""


def _build_instruction_md(
    case: Dict[str, Any],
    arm: str,
    clean_skill: str,
    noisy_skill: str,
    evolved_runbook: Optional[str] = None,
) -> str:
    """Renders instruction.md with embedded skill arm and soc-cli usage instructions."""
    skill_block = ""
    if arm == "clean_skills":
        skill_block = (
            "## Active Operational Skill (`secops-triage`)\n\n"
            f"{clean_skill.strip()}\n\n---\n\n"
        )
    elif arm == "noisy_skills":
        skill_block = (
            "## Active Operational Skill (`secops-triage`)\n\n"
            f"{noisy_skill.strip()}\n\n---\n\n"
        )
    elif arm == "gepa_evolved_skills":
        skill_block = (
            "# Security Operations GEPA Evolved Runbook\n\n"
            f"{(evolved_runbook or '').strip()}\n\n---\n\n"
        )

    return f"""# Security Operations Center (SOC) Tier 1 Interactive Triage Task

{skill_block}## Incident Alert & Asset Context

- **Case ID:** `{case['eval_id']}`
- **Scenario:** {case['name']}
- **Asset Criticality:** `{case.get('asset_criticality', 'STANDARD')}`

{case['prompt']}

## Sandbox Environment CLI (`soc-cli`)

Use `/usr/local/bin/soc-cli` to query telemetry and execute state-changing containment or case actions. Every command updates `/var/lib/soc/state.json` and logs to `/logs/artifacts/trajectory.jsonl`:

### Epistemic Investigation Tools (Read-Only)
- `soc-cli get_ip_report --ip <IP_ADDRESS>`
- `soc-cli get_domain_report --domain <DOMAIN>`
- `soc-cli get_file_report --file_hash <SHA256>`
- `soc-cli lookup_entity --entity_id <HOSTNAME_OR_IP>`
- `soc-cli list_cases [--query <FILTER>]`
- `soc-cli get_case --case_id <CASE_ID>`
- `soc-cli udm_search --query <QUERY>`

### Pragmatic State-Changing Actions (Interventions)
- `soc-cli isolate_host --hostname <HOSTNAME_OR_IP>`
- `soc-cli unblock_host --hostname <HOSTNAME_OR_IP>`
- `soc-cli block_indicator --indicator <DOMAIN_IP_OR_HASH>`
- `soc-cli update_case_comment --case_id <CASE_ID> --comment "<NOTES>"`
- `soc-cli close_case --case_id <CASE_ID> --verdict "<VERDICT>"`

## Required Deliverables

1. Execute at least one epistemic investigation tool via `soc-cli` before taking any containment or closure action.
2. Execute the appropriate pragmatic action(s) via `soc-cli` while avoiding prohibited or destructive false-positive actions.
3. Write your final grounded investigation report to `/logs/artifacts/triage_report.md`.
4. (Optional) Write structured JSON decision metadata to `/logs/artifacts/soc_decision.json` with keys `verdict` and `executed_actions`.
"""


def _build_solve_sh(eval_id: str) -> str:
    """Renders solution/solve.sh for oracle verification."""
    recipe = ORACLE_RECIPES[eval_id]
    cli_lines = "\n".join(f'$SOC_CLI {cmd.replace("$", "\\$")}' for cmd in recipe["commands"])
    decision_json = json.dumps(
        {
            "case_id": eval_id,
            "verdict": recipe["verdict"],
            "executed_actions": recipe["executed_actions"],
            "recommended_actions": recipe["executed_actions"],
        },
        indent=2,
    )
    return f"""#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${{SOC_CLI_BIN:-soc-cli}}"
ARTIFACTS_DIR="${{SOC_ARTIFACTS_DIR:-/logs/artifacts}}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
{cli_lines}

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
{recipe["report"].strip()}
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{decision_json}
EOF_DECISION
"""


def _build_test_sh() -> str:
    """Renders tests/test.sh verifier script."""
    return """#!/usr/bin/env bash
set -euo pipefail

VERIFY_BIN="${SOC_VERIFY_BIN:-python3 /app/scripts/verify_harbor_soc.py}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
VERIFIER_DIR="${SOC_VERIFIER_DIR:-/logs/verifier}"
mkdir -p "$VERIFIER_DIR"

$VERIFY_BIN \\
  --case-id "${SOC_CASE_ID}" \\
  --state-file "${SOC_STATE_FILE:-/var/lib/soc/state.json}" \\
  --trajectory-file "${SOC_TRAJECTORY_FILE:-$ARTIFACTS_DIR/trajectory.jsonl}" \\
  --report-file "$ARTIFACTS_DIR/triage_report.md" \\
  --decision-file "$ARTIFACTS_DIR/soc_decision.json" \\
  --reward-dir "$VERIFIER_DIR"
"""


def _make_executable(path: Path) -> None:
    """Adds executable permissions to a script file."""
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _export_skill_evaluator_json(cases: List[Dict[str, Any]], evals_json_out: Path) -> None:
    """Exports the 10 SOC scenarios in declarative evals.json format for SkillEvaluator."""
    evals_list = []
    for idx, case in enumerate(cases, start=1):
        assertions: List[str] = []
        for item in case.get("assertions", {}).get("must_contain", []):
            assertions.append(f"Response includes verified entity or indicator '{item}'")
        for act in case.get("expected_actions", []):
            assertions.append(f"Agent executes or recommends required SOC action '{act}'")
        for proh in case.get("prohibited_actions", []):
            assertions.append(f"Agent avoids prohibited SOC action '{proh}'")

        evals_list.append({
            "id": idx,
            "eval_id": case["eval_id"],
            "name": case["name"],
            "prompt": case["prompt"],
            "expected_output": case.get("reference", {}).get("recommended_action", ""),
            "expected_skill": "secops-triage",
            "acceptable_skills": ["secops-triage"],
            "safety_gate_required": "isolate_host" in case.get("prohibited_actions", []),
            "assertions": assertions,
            "deterministic_assertions": case.get("assertions", {}),
            "expected_actions": case.get("expected_actions", []),
            "prohibited_actions": case.get("prohibited_actions", []),
        })

    payload = {
        "skill_name": "secops-triage",
        "version": "1.0.0",
        "description": "Harbor and SkillEvaluator benchmark suite for Gen 3 interactive SOC Tier 1 alert triage.",
        "evals": evals_list,
    }
    evals_json_out.parent.mkdir(parents=True, exist_ok=True)
    evals_json_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def generate_harbor_soc_suite(
    output_root: Path = DEFAULT_HARBOR_OUT,
    evals_json_out: Path = DEFAULT_EVALS_JSON_OUT,
    gepa_runbooks_dir: Optional[Path] = None,
    arms: Tuple[str, ...] = SKILL_ARMS,
) -> Dict[str, Any]:
    """Generates Harbor task directories and the SkillEvaluator evals.json manifest."""
    evalset_data = json.loads(EVALSET_PATH.read_text(encoding="utf-8"))
    cases = evalset_data.get("eval_cases", [])
    clean_skill = CLEAN_SKILL_PATH.read_text(encoding="utf-8")
    noisy_skill = NOISY_SKILL_PATH.read_text(encoding="utf-8")

    rb_dir = gepa_runbooks_dir or DEFAULT_GEPA_RUNBOOKS_DIR
    if not rb_dir.exists():
        fallback_rb = ROOT_DIR / "configs" / "runbooks" / "gepa_evolved"
        if fallback_rb.exists():
            rb_dir = fallback_rb

    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    env_hashes = set()
    created_tasks: List[str] = []

    for arm in arms:
        for case in cases:
            eval_id = case["eval_id"]
            slug = _case_slug(eval_id)
            task_dir = output_root / arm / slug
            task_dir.mkdir(parents=True, exist_ok=True)

            evolved_rb_content = None
            if arm == "gepa_evolved_skills":
                rb_file = GEPA_CASE_RUNBOOK_MAP.get(eval_id, "basic_ioc_enrichment.md")
                rb_path = rb_dir / rb_file
                if rb_path.exists():
                    evolved_rb_content = rb_path.read_text(encoding="utf-8")
                else:
                    evolved_rb_content = f"# Security Operations GEPA Evolved Runbook: {rb_file}\n"

            (task_dir / "task.toml").write_text(
                _build_task_toml(case, arm, slug),
                encoding="utf-8",
            )
            (task_dir / "instruction.md").write_text(
                _build_instruction_md(
                    case=case,
                    arm=arm,
                    clean_skill=clean_skill,
                    noisy_skill=noisy_skill,
                    evolved_runbook=evolved_rb_content,
                ),
                encoding="utf-8",
            )

            env_dir = task_dir / "environment"
            _populate_identical_environment(env_dir)
            env_hashes.add(compute_environment_hash(env_dir))

            sol_dir = task_dir / "solution"
            sol_dir.mkdir(parents=True, exist_ok=True)
            solve_sh = sol_dir / "solve.sh"
            solve_sh.write_text(_build_solve_sh(eval_id), encoding="utf-8")
            _make_executable(solve_sh)

            tests_dir = task_dir / "tests"
            tests_dir.mkdir(parents=True, exist_ok=True)
            test_sh = tests_dir / "test.sh"
            test_sh.write_text(_build_test_sh(), encoding="utf-8")
            _make_executable(test_sh)

            created_tasks.append(str(task_dir.relative_to(output_root)))

    _export_skill_evaluator_json(cases, evals_json_out)

    return {
        "total_tasks": len(created_tasks),
        "arms": list(arms),
        "cases_per_arm": len(cases),
        "unique_environment_hashes": sorted(env_hashes),
        "output_root": str(output_root),
        "evals_json_out": str(evals_json_out),
    }


def load_gen5_split(root: Path, split: str) -> List[Dict[str, Any]]:
    """Reads one committed Gen 5 bundle; never touches the exposure ledger."""
    data = json.loads((Path(root) / f"{split}.json").read_text(encoding="utf-8"))
    return [dict(case) for case in data.get("eval_cases", [])]


def strip_case_for_state(case: Dict[str, Any]) -> Dict[str, Any]:
    """The image-side view of a case: enough for SocEnvironment.from_eval_case and the prompt."""
    stripped = {key: case[key] for key in GEN5_STATE_KEYS if key in case}
    stripped["generation"] = int(case.get("generation") or 5)
    return stripped


def build_state_bundle(cases: List[Dict[str, Any]]) -> str:
    """One deterministic bundle for every task, so the environment hash is identical across the tree."""
    ordered = sorted((strip_case_for_state(case) for case in cases), key=lambda c: c["eval_id"])
    bundle = {
        "evalset_id": "soc_tier1_families",
        "generation": 5,
        "split": "harbor_state",
        "description": "Gen 5 world state for the Harbor sandbox. Answer keys live in each task's tests/case.json.",
        "eval_cases": ordered,
    }
    return json.dumps(bundle, indent=2, sort_keys=True) + "\n"


def _load_evolved_runbooks(rb_dir: Path) -> Dict[str, str]:
    """All four evolved runbooks, by file name. Missing files become a one-line stub, as Gen 3 did."""
    runbooks: Dict[str, str] = {}
    for name in GEN5_EVOLVED_RUNBOOKS:
        path = Path(rb_dir) / name
        if path.exists():
            runbooks[name] = path.read_text(encoding="utf-8")
        else:
            runbooks[name] = f"# Security Operations GEPA Evolved Runbook: {name}\n"
    return runbooks


def _populate_gen5_environment(env_dir: Path, state_bundle_text: str) -> None:
    """The Gen 3 runtime modules plus the stripped state bundle; no evalset in the image."""
    env_dir.mkdir(parents=True, exist_ok=True)
    (env_dir / "Dockerfile").write_text(GEN5_DOCKERFILE_CONTENT, encoding="utf-8")
    (env_dir / "j_init.py").write_text('"""Package init."""\n', encoding="utf-8")
    file_map = {
        "soc_environment.py": ROOT_DIR / "agent" / "soc_environment.py",
        "jev_judge.py": ROOT_DIR / "agent" / "jev_judge.py",
        "jev_evaluator.py": ROOT_DIR / "agent" / "jev_evaluator.py",
        "eval_trajectory_verifier.py": ROOT_DIR / "scripts" / "eval_trajectory_verifier.py",
        "eval_cost_engine.py": ROOT_DIR / "scripts" / "eval_cost_engine.py",
        "soc_sandbox_cli.py": ROOT_DIR / "scripts" / "soc_sandbox_cli.py",
        "verify_harbor_soc.py": ROOT_DIR / "scripts" / "verify_harbor_soc.py",
    }
    for dest_name, src_path in file_map.items():
        shutil.copyfile(src_path, env_dir / dest_name)
    (env_dir / "state_bundle.json").write_text(state_bundle_text, encoding="utf-8")


GEN5_SOC_CLI_USAGE_MD = """## Sandbox Environment CLI (`soc-cli`)

Use `/usr/local/bin/soc-cli` to query telemetry and execute state-changing containment or case actions. Every command updates `/var/lib/soc/state.json` and logs to `/logs/artifacts/trajectory.jsonl`:

### Epistemic Investigation Tools (Read-Only)
- `soc-cli get_ip_report --ip <IP_ADDRESS>`
- `soc-cli get_domain_report --domain <DOMAIN>`
- `soc-cli get_file_report --file_hash <SHA256>`
- `soc-cli lookup_entity --entity_id <HOSTNAME_OR_IP>`
- `soc-cli list_cases [--query <FILTER>]`
- `soc-cli get_case --case_id <CASE_ID>`
- `soc-cli udm_search --query <QUERY>`

### Pragmatic State-Changing Actions (Interventions)
- `soc-cli isolate_host --hostname <HOSTNAME_OR_IP>`
- `soc-cli unblock_host --hostname <HOSTNAME_OR_IP>`
- `soc-cli block_indicator --indicator <DOMAIN_IP_OR_HASH>`
- `soc-cli update_case_comment --case_id <CASE_ID> --comment "<NOTES>"`
- `soc-cli close_case --case_id <CASE_ID> --verdict "<VERDICT>"`
"""


def _build_gen5_task_toml(case: Dict[str, Any], arm: str, split: str, slug: str, case_sha256: str) -> str:
    """Harbor 1.3 task.toml for a Gen 5 case: harness-side metadata, no label, no answer key."""
    eval_id = case["eval_id"]
    family_id = case["family_id"]
    difficulty = int(case.get("difficulty") or 2)
    difficulty_name = GEN5_DIFFICULTY_NAMES.get(difficulty, "medium")
    crit = case.get("asset_criticality", "STANDARD")
    env_lines = (
        f'SOC_CASE_ID = "{eval_id}"\n'
        f'SOC_SKILL_ARM = "{arm}"\n'
        'SOC_STATE_FILE = "/var/lib/soc/state.json"\n'
        'SOC_TRAJECTORY_FILE = "/logs/artifacts/trajectory.jsonl"\n'
    )
    return (
        'version = "1.0"\n'
        'schema_version = "1.3"\n\n'
        "[task]\n"
        f'name = "secops/soc-gen5-{arm}-{split}-{slug}"\n'
        f'description = "Gen 5 SOC Tier 1 interactive triage, {split} split ({arm} arm)"\n'
        f'categories = ["security", "soc-tier1", "gen5-families", "{split}", "{arm}"]\n\n'
        "[metadata]\n"
        'author_name = "Dan Dye"\n'
        'author_email = "dandye@google.com"\n'
        f'difficulty = "{difficulty_name}"\n'
        f"difficulty_level = {difficulty}\n"
        'category = "security-operations"\n'
        f'tags = ["secops", "soc-tier1", "harbor", "gen5", "{arm}", "{split}", "{eval_id}"]\n'
        f'eval_id = "{eval_id}"\n'
        "generation = 5\n"
        f'family_id = "{family_id}"\n'
        f'split = "{split}"\n'
        f'case_sha256 = "{case_sha256}"\n'
        f'skill_arm = "{arm}"\n'
        f'asset_criticality = "{crit}"\n\n'
        "[verifier]\n"
        "timeout_sec = 120.0\n\n"
        "[agent]\n"
        "timeout_sec = 300.0\n\n"
        "[environment]\n"
        'network_mode = "public"\n'
        "build_timeout_sec = 300.0\n"
        "cpus = 2\n"
        "memory_mb = 2048\n"
        "storage_mb = 4096\n"
        "allow_internet = false\n\n"
        f"[environment.env]\n{env_lines}\n"
        f"[agent.env]\n{env_lines}\n"
        f"[verifier.env]\n{env_lines}"
        f'SOC_SPLIT = "{split}"\n'
        'SOC_JEV_BACKEND = "mock"\n\n'
        f"[solution.env]\n{env_lines}"
    )


def _build_gen5_instruction_md(
    case: Dict[str, Any],
    arm: str,
    clean_skill: str,
    noisy_skill: str,
    evolved_runbooks: Dict[str, str],
) -> str:
    """instruction.md: the arm's skill text, the alert, the CLI usage, the deliverables. No scenario name."""
    skill_block = ""
    if arm == "clean_skills":
        skill_block = "## Active Operational Skill (`secops-triage`)\n\n" f"{clean_skill.strip()}\n\n---\n\n"
    elif arm == "noisy_skills":
        skill_block = "## Active Operational Skill (`secops-triage`)\n\n" f"{noisy_skill.strip()}\n\n---\n\n"
    elif arm == "gepa_evolved_skills":
        sections = "".join(
            f"### Runbook: {name}\n\n{text.strip()}\n\n" for name, text in evolved_runbooks.items()
        )
        skill_block = (
            "## Security Operations GEPA Evolved Runbooks\n\n"
            "Four runbooks follow. Pick whichever fits the alert; none is marked as the right one.\n\n"
            f"{sections}---\n\n"
        )
    return (
        "# Security Operations Center (SOC) Tier 1 Interactive Triage Task\n\n"
        f"{skill_block}## Incident Alert & Asset Context\n\n"
        f"- **Case ID:** `{case['eval_id']}`\n"
        f"- **Asset Criticality:** `{case.get('asset_criticality', 'STANDARD')}`\n\n"
        f"{case['prompt']}\n\n"
        f"{GEN5_SOC_CLI_USAGE_MD}\n"
        "## Required Deliverables\n\n"
        "1. Run at least one read-only investigation tool via `soc-cli` before any containment or closure action.\n"
        "2. Execute the state-changing action(s) the evidence supports via `soc-cli`, and avoid actions it does not.\n"
        "3. Write your final grounded investigation report to `/logs/artifacts/triage_report.md`.\n"
        "4. Write structured JSON decision metadata to `/logs/artifacts/soc_decision.json` with keys `verdict` "
        "(your threat verdict, for example `MALICIOUS` or `BENIGN`), `recommended_actions` (the `soc-cli` action "
        "names you executed or recommend), `target_entity`, and `rationale`.\n"
    )


def _build_gen5_solve_sh(case: Dict[str, Any]) -> str:
    """solution/solve.sh from the case's oracle block, through the planner the calibration uses."""
    trial = plan_oracle(case)
    cli_lines = "\n".join(
        f"$SOC_CLI {step['tool']} --json {shlex.quote(json.dumps(step['args'], sort_keys=True))}"
        for step in trial.steps
    )
    decision = {"case_id": case["eval_id"], **trial.decision}
    decision_json = json.dumps(decision, indent=2, sort_keys=True)
    return f"""#!/usr/bin/env bash
set -euo pipefail

SOC_CLI="${{SOC_CLI_BIN:-soc-cli}}"
ARTIFACTS_DIR="${{SOC_ARTIFACTS_DIR:-/logs/artifacts}}"
mkdir -p "$ARTIFACTS_DIR"

$SOC_CLI reset
{cli_lines}

cat <<'EOF_REPORT' > "$ARTIFACTS_DIR/triage_report.md"
{trial.report_text.strip()}
EOF_REPORT

cat <<'EOF_DECISION' > "$ARTIFACTS_DIR/soc_decision.json"
{decision_json}
EOF_DECISION
"""


def _build_gen5_test_sh() -> str:
    """tests/test.sh: the verifier reads the answer key and the manifest from its own directory."""
    return """#!/usr/bin/env bash
set -euo pipefail

TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERIFY_BIN="${SOC_VERIFY_BIN:-python3 /app/scripts/verify_harbor_soc.py}"
ARTIFACTS_DIR="${SOC_ARTIFACTS_DIR:-/logs/artifacts}"
VERIFIER_DIR="${SOC_VERIFIER_DIR:-/logs/verifier}"
mkdir -p "$VERIFIER_DIR"

$VERIFY_BIN \\
  --case-id "${SOC_CASE_ID}" \\
  --state-file "${SOC_STATE_FILE:-/var/lib/soc/state.json}" \\
  --trajectory-file "${SOC_TRAJECTORY_FILE:-$ARTIFACTS_DIR/trajectory.jsonl}" \\
  --report-file "$ARTIFACTS_DIR/triage_report.md" \\
  --decision-file "$ARTIFACTS_DIR/soc_decision.json" \\
  --metrics-file "$ARTIFACTS_DIR/metrics.json" \\
  --evalset-file "$TESTS_DIR/case.json" \\
  --manifest-file "$TESTS_DIR/manifest.json" \\
  --split "${SOC_SPLIT:?SOC_SPLIT must be set by task.toml [verifier.env]}" \\
  --reward-dir "$VERIFIER_DIR"
"""


def write_gen5_tree(
    output_root: Path,
    evalset_root: Path = GEN5_ROOT,
    splits: Tuple[str, ...] = GEN5_HARBOR_SPLITS,
    arms: Tuple[str, ...] = DEFAULT_GEN5_ARMS,
    gepa_runbooks_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Writes the Gen 5 task tree into output_root (which must not exist yet) and returns its summary."""
    output_root = Path(output_root)
    evalset_root = Path(evalset_root)
    for split in splits:
        if split not in GEN5_HARBOR_SPLITS:
            raise ValueError(f"split {split!r} is not generated for Harbor (allowed: {', '.join(GEN5_HARBOR_SPLITS)})")
    for arm in arms:
        if arm not in SKILL_ARMS:
            raise ValueError(f"unknown arm {arm!r} (allowed: {', '.join(SKILL_ARMS)})")

    manifest_text = (evalset_root / "manifest.json").read_text(encoding="utf-8")
    manifest = json.loads(manifest_text)
    manifest_rows = {row["eval_id"]: row for row in manifest.get("cases", [])}
    cases_by_split = {split: load_gen5_split(evalset_root, split) for split in splits}
    state_bundle_text = build_state_bundle([case for cases in cases_by_split.values() for case in cases])
    clean_skill = CLEAN_SKILL_PATH.read_text(encoding="utf-8")
    noisy_skill = NOISY_SKILL_PATH.read_text(encoding="utf-8")
    evolved = _load_evolved_runbooks(Path(gepa_runbooks_dir) if gepa_runbooks_dir else DEFAULT_GEN5_RUNBOOKS_DIR)

    output_root.mkdir(parents=True, exist_ok=False)
    env_hashes = set()
    rows: List[Dict[str, Any]] = []
    for arm in arms:
        for split in splits:
            for case in cases_by_split[split]:
                eval_id = case["eval_id"]
                case_sha = sha256_text(canonical_json(case))
                row = manifest_rows.get(eval_id)
                if row is None or row.get("case_sha256") != case_sha:
                    raise ValueError(f"{eval_id}: bundle case does not match manifest.json; run gen5_instancer.py check")
                slug = _case_slug(eval_id)
                task_dir = output_root / arm / split / slug
                (task_dir / "solution").mkdir(parents=True)
                (task_dir / "tests").mkdir(parents=True)

                (task_dir / "task.toml").write_text(_build_gen5_task_toml(case, arm, split, slug, case_sha), encoding="utf-8")
                (task_dir / "instruction.md").write_text(
                    _build_gen5_instruction_md(case, arm, clean_skill, noisy_skill, evolved), encoding="utf-8"
                )
                solve_sh = task_dir / "solution" / "solve.sh"
                solve_sh.write_text(_build_gen5_solve_sh(case), encoding="utf-8")
                _make_executable(solve_sh)
                test_sh = task_dir / "tests" / "test.sh"
                test_sh.write_text(_build_gen5_test_sh(), encoding="utf-8")
                _make_executable(test_sh)
                case_bundle = {"evalset_id": "soc_tier1_families", "generation": 5, "split": split, "eval_cases": [case]}
                (task_dir / "tests" / "case.json").write_text(json.dumps(case_bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                (task_dir / "tests" / "manifest.json").write_text(manifest_text, encoding="utf-8")

                env_dir = task_dir / "environment"
                _populate_gen5_environment(env_dir, state_bundle_text)
                env_hashes.add(compute_environment_hash(env_dir))
                rows.append({
                    "path": task_dir.relative_to(output_root).as_posix(),
                    "arm": arm,
                    "split": split,
                    "eval_id": eval_id,
                    "family_id": case["family_id"],
                    "difficulty": int(case.get("difficulty") or 0),
                    "case_sha256": case_sha,
                })

    if len(env_hashes) != 1:
        raise RuntimeError(f"expected one environment hash across the tree, got {len(env_hashes)}")
    rows.sort(key=lambda r: r["path"])
    tree_manifest = {
        "generator_version": GEN5_GENERATOR_VERSION,
        "evalset_id": manifest.get("evalset_id"),
        "pool_version": manifest.get("pool_version"),
        "gen5_manifest_sha256": sha256_text(manifest_text),
        "environment_hash": next(iter(env_hashes)),
        "arms": list(arms),
        "splits": list(splits),
        "cases_per_split": {split: len(cases_by_split[split]) for split in splits},
        "total_tasks": len(rows),
        "tasks": rows,
    }
    (output_root / "manifest.json").write_text(json.dumps(tree_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {key: value for key, value in tree_manifest.items() if key != "tasks"}
    summary["output_root"] = str(output_root)
    return summary


def generate_harbor_soc_gen5_suite(
    output_root: Path = DEFAULT_GEN5_HARBOR_OUT,
    evalset_root: Path = GEN5_ROOT,
    splits: Tuple[str, ...] = GEN5_HARBOR_SPLITS,
    arms: Tuple[str, ...] = DEFAULT_GEN5_ARMS,
    gepa_runbooks_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Builds the Gen 5 tree in a sibling temp dir and swaps it into output_root only on success; a failed build leaves output_root untouched."""
    output_root = Path(output_root)
    output_root.parent.mkdir(parents=True, exist_ok=True)
    build_root = Path(tempfile.mkdtemp(prefix=".harbor_soc_gen5_build_", dir=output_root.parent)) / "tree"
    try:
        summary = write_gen5_tree(
            build_root,
            evalset_root=evalset_root,
            splits=splits,
            arms=arms,
            gepa_runbooks_dir=gepa_runbooks_dir,
        )
        if output_root.exists():
            shutil.rmtree(output_root)
        os.replace(build_root, output_root)
        summary["output_root"] = str(output_root)
        return summary
    finally:
        shutil.rmtree(build_root.parent, ignore_errors=True)


def _tree_files(root: Path) -> Dict[str, Path]:
    return {
        p.relative_to(root).as_posix(): p
        for p in root.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    }


def check_gen5_tree(
    output_root: Path = DEFAULT_GEN5_HARBOR_OUT,
    evalset_root: Path = GEN5_ROOT,
    splits: Tuple[str, ...] = GEN5_HARBOR_SPLITS,
    arms: Tuple[str, ...] = DEFAULT_GEN5_ARMS,
    gepa_runbooks_dir: Optional[Path] = None,
) -> List[str]:
    """Regenerates into a temporary directory and lists every byte-level difference from output_root."""
    output_root = Path(output_root)
    if not output_root.exists():
        return [f"missing: {output_root} (run the generator first)"]
    with tempfile.TemporaryDirectory(prefix="harbor_soc_gen5_check_") as tmp:
        fresh = Path(tmp) / "tree"
        write_gen5_tree(fresh, evalset_root=evalset_root, splits=splits, arms=arms, gepa_runbooks_dir=gepa_runbooks_dir)
        expected = _tree_files(fresh)
        actual = _tree_files(output_root)
        diffs: List[str] = []
        for rel in sorted(set(expected) - set(actual)):
            diffs.append(f"missing: {rel}")
        for rel in sorted(set(actual) - set(expected)):
            diffs.append(f"unexpected: {rel}")
        for rel in sorted(set(expected) & set(actual)):
            if expected[rel].read_bytes() != actual[rel].read_bytes():
                diffs.append(f"differs: {rel}")
            elif rel.endswith(".sh") and not os.access(actual[rel], os.X_OK):
                diffs.append(f"not executable: {rel}")
        return diffs


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point. Gen 5 by default; --gen3 renders the frozen Gen 3 tree."""
    parser = argparse.ArgumentParser(
        description="Generate Harbor v1.3 SOC Tier 1 evaluation tasks (Gen 5 by default; --gen3 for the frozen Gen 3 recipe)"
    )
    parser.add_argument("--gen3", action="store_true", help="generate the frozen Gen 3 tree (evals/harbor_soc) instead of Gen 5")
    parser.add_argument("--evalset", default=str(GEN5_ROOT), help="Gen 5 directory holding validation.json, final_test.json, manifest.json")
    parser.add_argument("--split", nargs="+", default=list(GEN5_HARBOR_SPLITS), help="Gen 5 splits to render (validation, final_test)")
    parser.add_argument("--arms", nargs="+", default=None, help="skill arms (Gen 5 default: clean_skills gepa_evolved_skills; Gen 3 default: all four)")
    parser.add_argument("--out", default=None, help="output root (Gen 5 default: evals/harbor_soc_gen5; Gen 3 default: evals/harbor_soc)")
    parser.add_argument("--gepa-runbooks-dir", default=None, help="evolved runbooks directory (Gen 5 default: configs/runbooks/gepa_evolved)")
    parser.add_argument("--check", action="store_true", help="Gen 5 only: regenerate into a temp dir, diff against --out, exit 1 on any difference")
    parser.add_argument("--output-root", default=None, help=argparse.SUPPRESS)  # Gen 3 compatibility
    parser.add_argument("--evals-json-out", default=str(DEFAULT_EVALS_JSON_OUT), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.gen3:
        summary = generate_harbor_soc_suite(
            output_root=Path(args.out or args.output_root or DEFAULT_HARBOR_OUT),
            evals_json_out=Path(args.evals_json_out),
            gepa_runbooks_dir=Path(args.gepa_runbooks_dir) if args.gepa_runbooks_dir else None,
            arms=tuple(args.arms or SKILL_ARMS),
        )
        print(json.dumps(summary, indent=2))
        return 0

    bad = [split for split in args.split if split not in GEN5_HARBOR_SPLITS]
    if bad:
        parser.error(
            f"split(s) not generated for Harbor: {', '.join(bad)} "
            f"(allowed: {', '.join(GEN5_HARBOR_SPLITS)}; train never runs in the container)"
        )
    out = Path(args.out or DEFAULT_GEN5_HARBOR_OUT)
    kwargs = dict(
        evalset_root=Path(args.evalset),
        splits=tuple(args.split),
        arms=tuple(args.arms or DEFAULT_GEN5_ARMS),
        gepa_runbooks_dir=Path(args.gepa_runbooks_dir) if args.gepa_runbooks_dir else None,
    )
    if args.check:
        diffs = check_gen5_tree(output_root=out, **kwargs)
        if diffs:
            print(f"harbor_soc_gen5 check FAILED: {len(diffs)} difference(s) under {out}")
            for line in diffs[:50]:
                print(f"  {line}")
            return 1
        print(f"harbor_soc_gen5 check OK: {out}")
        return 0
    summary = generate_harbor_soc_gen5_suite(output_root=out, **kwargs)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
