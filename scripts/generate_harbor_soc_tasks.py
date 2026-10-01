#!/usr/bin/env python3
"""Generates Harbor v1.3 SOC Tier 1 Interactive Tasks across 3 experimental skill arms."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import stat
import sys
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

EVALSET_PATH = ROOT_DIR / "configs" / "evals" / "gen3" / "soc_tier1_interactive.json"
CLEAN_SKILL_PATH = ROOT_DIR / "skills" / "secops-triage" / "SKILL.md"
NOISY_SKILL_PATH = ROOT_DIR / "skills" / "secops-triage" / "noisy" / "verbose_lore.md"
DEFAULT_HARBOR_OUT = ROOT_DIR / "evals" / "harbor_soc"
DEFAULT_EVALS_JSON_OUT = ROOT_DIR / "skills" / "secops-triage" / "evals" / "evals.json"

SKILL_ARMS = ("no_skills", "clean_skills", "noisy_skills")

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
    """Converts CASE-GEN3-01-LOKIBOT-C2 to case-01-lokibot-c2."""
    return eval_id.lower().replace("case-gen3-", "case-")


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
    name = f"soc-{arm}-{slug}"
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


def _build_instruction_md(case: Dict[str, Any], arm: str, clean_skill: str, noisy_skill: str) -> str:
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
) -> Dict[str, Any]:
    """Generates all 30 Harbor task directories and the SkillEvaluator evals.json manifest."""
    evalset_data = json.loads(EVALSET_PATH.read_text(encoding="utf-8"))
    cases = evalset_data.get("eval_cases", [])
    clean_skill = CLEAN_SKILL_PATH.read_text(encoding="utf-8")
    noisy_skill = NOISY_SKILL_PATH.read_text(encoding="utf-8")

    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    env_hashes = set()
    created_tasks: List[str] = []

    for arm in SKILL_ARMS:
        for case in cases:
            eval_id = case["eval_id"]
            slug = _case_slug(eval_id)
            task_dir = output_root / arm / slug
            task_dir.mkdir(parents=True, exist_ok=True)

            (task_dir / "task.toml").write_text(
                _build_task_toml(case, arm, slug),
                encoding="utf-8",
            )
            (task_dir / "instruction.md").write_text(
                _build_instruction_md(case, arm, clean_skill, noisy_skill),
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
        "arms": list(SKILL_ARMS),
        "cases_per_arm": len(cases),
        "unique_environment_hashes": sorted(env_hashes),
        "output_root": str(output_root),
        "evals_json_out": str(evals_json_out),
    }


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point to generate the 30 Harbor SOC tasks."""
    parser = argparse.ArgumentParser(description="Generate Harbor v1.3 SOC Tier 1 evaluation tasks")
    parser.add_argument("--output-root", default=str(DEFAULT_HARBOR_OUT))
    parser.add_argument("--evals-json-out", default=str(DEFAULT_EVALS_JSON_OUT))
    args = parser.parse_args(argv)

    summary = generate_harbor_soc_suite(
        output_root=Path(args.output_root),
        evals_json_out=Path(args.evals_json_out),
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
