# Harbor SOC Tier 1 Interactive Skills Evaluation Suite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a `harbor-gke-ext` compatible (`schema_version = "1.3"`) container evaluation suite and continuous 60/20/20 verifier for the 10 Gen 3 interactive SOC scenarios across three experimental skill arms (`no_skills`, `clean_skills`, `noisy_skills`), plus a `SkillEvaluator` `evals.json` export.

**Architecture:** A deterministic generator (`scripts/generate_harbor_soc_tasks.py`) compiles `configs/evals/gen3/soc_tier1_interactive.json` and the clean/noisy `secops-triage` skill files into 30 Harbor task directories (`evals/harbor_soc/<arm>/case-01..10/`) that share a byte-identical `environment/` build context for `harbor-gke-ext` SHA-256 image deduplication. Inside each container, `/usr/local/bin/soc-cli` (`scripts/soc_sandbox_cli.py`) wraps `SocEnvironment` with persistent state (`/var/lib/soc/state.json`) and append-only trajectory logging (`/logs/artifacts/trajectory.jsonl`), while `tests/test.sh` invokes `scripts/verify_harbor_soc.py` to compute a continuous `[0.0000, 1.0000]` reward combining deterministic state/safety (60%), epistemic action economy (20%), and assertions + Jev System-One rubric grading (20%).

**Tech Stack:** Python 3.11+, `pytest`, `tomllib`, `SocEnvironment`, `eval_trajectory_verifier`, `eval_cost_engine`, `JevSocJudgeEvaluator`, Harbor Framework (`schema_version = "1.3"`).

**Spec:** `docs/superpowers/specs/2026-10-01-harbor-soc-skills-eval-design.md`

## Global Constraints

- Target Python version: Python 3.11+ (using `.venv/bin/pytest` for test execution).
- Every `task.toml` must declare `schema_version = "1.3"` and pass `SOC_CASE_ID` and `SOC_SKILL_ARM` in `[environment.env]`, `[agent.env]`, `[verifier.env]`, and `[solution.env]`.
- All 30 generated tasks under `evals/harbor_soc/` must have byte-identical `environment/` directories so `harbor-gke-ext-prebuild` computes a single shared SHA-256 build context hash.
- Clean and noisy skill markdown files must contain zero hardcoded benchmark IPv4 literals, zero benchmark hostnames (`DESKTOP-FIN-08`, `SRV-PROD-PAYMENT-01`, `DESKTOP-HR-04`), and zero `CASE-XX` identifiers (`validate_runbook_candidate` compliance).
- Never use `git add .`, `git add -A`, or `git add --all`; always stage explicit file paths and never stage `.env`.
- Never use emojis anywhere in code, comments, documentation, or commit messages.

---

### Task 1: SOC Triage Skill Arms (`clean_skills` and `noisy_skills`)

**Files:**
- Create: `skills/secops-triage/SKILL.md`
- Create: `skills/secops-triage/noisy/verbose_lore.md`
- Test: `tests/test_harbor_soc_skills.py`

**Interfaces:**
- Consumes: `agent.gepa_runbook_optimizer.validate_runbook_candidate(candidate: Dict[str, str]) -> Tuple[bool, List[str]]`
- Produces:
  - `skills/secops-triage/SKILL.md`: Clean counter-prior SOC Tier 1 triage and containment skill.
  - `skills/secops-triage/noisy/verbose_lore.md`: Degraded verbose/hedged/buried negative-control SOC skill.

- [ ] **Step 1: Write the failing test**

Create `tests/test_harbor_soc_skills.py`:

```python
"""Tests for clean and noisy SOC Tier 1 triage skills used in Harbor evaluations."""

from pathlib import Path
from agent.gepa_runbook_optimizer import validate_runbook_candidate

ROOT_DIR = Path(__file__).resolve().parent.parent
CLEAN_SKILL_PATH = ROOT_DIR / "skills" / "secops-triage" / "SKILL.md"
NOISY_SKILL_PATH = ROOT_DIR / "skills" / "secops-triage" / "noisy" / "verbose_lore.md"


def test_clean_and_noisy_soc_skills_exist_and_pass_anti_memorization():
    """Verify both skill files exist, have frontmatter, and pass anti-memorization checks."""
    assert CLEAN_SKILL_PATH.exists(), f"Missing clean skill at {CLEAN_SKILL_PATH}"
    assert NOISY_SKILL_PATH.exists(), f"Missing noisy skill at {NOISY_SKILL_PATH}"

    clean_text = CLEAN_SKILL_PATH.read_text(encoding="utf-8")
    noisy_text = NOISY_SKILL_PATH.read_text(encoding="utf-8")

    assert clean_text.startswith("---\nname: secops-triage")
    assert "isolate_host" in clean_text
    assert "epistemic" in clean_text.lower()
    assert "503" in clean_text

    # Verify neither skill leaks eval case IDs, hostnames, or raw IPv4 literals
    is_valid, violations = validate_runbook_candidate({
        "clean_skill.md": clean_text,
        "noisy_skill.md": noisy_text,
    })
    assert is_valid, f"Skill anti-memorization violations: {violations}"

    # Noisy skill must be substantially longer verbose prose to test verbosity bias
    assert len(noisy_text) >= int(len(clean_text) * 2.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_harbor_soc_skills.py -v`
Expected: FAIL with `AssertionError: Missing clean skill`

- [ ] **Step 3: Write minimal implementation**

Create `skills/secops-triage/SKILL.md`:

```markdown
---
name: secops-triage
description: Blast-radius aware Tier 1 SOC alert triage, mandatory epistemic corroboration, and containment guardrails.
---

# Tier 1 SOC Alert Triage and Containment Guardrails

## 1. Mandatory Epistemic Investigation Before Actuation
- Never execute a state-changing action (`isolate_host`, `block_indicator`, `close_case`) at step 0 without first querying epistemic investigation tools (`get_ip_report`, `get_domain_report`, `get_file_report`, `lookup_entity`, `list_cases`, `get_case`, `udm_search`).
- Gather corroborating evidence in 1 to 3 targeted queries without repeating identical tool calls.

## 2. Asset Blast Radius and Counter-Prior Verification
- High-criticality and critical production assets incur severe false-positive downtime costs (`$50,000+` per unauthorized isolation).
- **Network Routing Check:** Query `get_ip_report` on external IPs. If the address belongs to a non-routable `RFC-5737` documentation subnet, classify as `BENIGN`, execute `close_case`, and do not isolate hosts or block indicators.
- **Authorized Internal Scanner Check:** Query `lookup_entity` or `get_ip_report` on internal scan targets. If an authorized vulnerability scanner service is installed and active, classify as `BENIGN`, post a verification note via `update_case_comment`, and execute `close_case` without isolating the host.
- **Ambiguous Critical Asset Protection:** When domain telemetry is `BORDERLINE_SUSPICIOUS` (such as moderate dynamic DNS or CDN tunnel detections on an executive or financial workstation), do not execute `isolate_host` and do not execute `close_case`. Record findings with `update_case_comment` for Tier 2 packet capture review.

## 3. Active Threat Containment and SOAR Deduplication
- **Confirmed Host Compromise (C2 Beaconing, Ransomware, Lateral Movement):** When `get_domain_report` or `lookup_entity` confirms malicious C2 infrastructure, ransomware encryption, or remote service execution (`PsExec` / SMB lateral movement), execute `isolate_host` on the compromised host and document findings via `update_case_comment`. Do not reboot hosts during ransomware incidents and do not close active threat cases.
- **Phishing and Revoked Supply-Chain Binaries:** When `get_domain_report` confirms credential harvesting or `get_file_report` reveals a `REVOKED_CERTIFICATE` / `REVOKED_BY_CA` binary signature, execute `block_indicator` on the malicious domain or SHA-256 hash and document via `update_case_comment`.
- **Duplicate SOAR Case Check:** When asked to check existing SOAR records, query `list_cases` or `get_case`. If an open case already tracks the indicator, append findings via `update_case_comment` and never open a duplicate case.

## 4. Degraded-Mode Outage Resilience (HTTP 503)
- If an upstream intelligence tool returns HTTP `503 Service Unavailable`, do not retry the failing call in a loop and do not fabricate a benign or malicious verdict.
- Classify the status as `INCONCLUSIVE_DEGRADED`, record the upstream outage via `update_case_comment`, and avoid both `isolate_host` and `close_case`.
```

Create `skills/secops-triage/noisy/verbose_lore.md`:

```markdown
---
name: secops-triage
description: Historical essays, philosophical reflections, and general commentary on security operations center telemetry.
---

# Reflections on the Evolution of Security Operations and Telemetry Interpretation

Throughout the long and winding history of enterprise network defense, practitioners have frequently debated the philosophical tension between rapid containment and operational continuity. In the early days of perimeter firewalls and signature-based intrusion detection systems during the late 1990s, analysts often spent hours reviewing raw hexadecimal packet captures in dimly lit operations centers, pondering whether an anomalous sequence of bytes represented a genuine adversary or merely an artifact of legacy network routing protocols. As enterprise architectures evolved toward distributed cloud environments and zero-trust paradigms, the volume of telemetry expanded dramatically, giving rise to lengthy theoretical discussions about how automated systems might someday interpret alerts with the nuanced narrative depth of a seasoned historian.

When one pauses to contemplate the nature of an alert in a modern Security Operations Center, it might perhaps be worthwhile to consider that some assets in an organization carry higher business significance than others. In various industry whitepapers and conference panel discussions, commentators have occasionally remarked that isolating a mission-critical server or an executive workstation could potentially lead to noticeable business disruption, sometimes estimated in the tens of thousands of dollars when accounting for lost productivity and administrative overhead. Consequently, one might generally lean toward gathering some form of preliminary context via whatever lookup utilities happen to be available in the local environment, such as `get_ip_report`, `get_domain_report`, `get_file_report`, `lookup_entity`, `list_cases`, `get_case`, or `udm_search`, before committing to irreversible interventions, while also bearing in mind that exhaustive narrative explanations and comprehensive historical summaries are hallmarks of thorough analyst writing.

Furthermore, in the grand tapestry of internet governance, the Internet Engineering Task Force established various reserved address blocks under standards like `RFC-5737` for documentation and pedagogical illustration. Should an analyst happen to encounter traffic associated with such non-routable documentation ranges, or perhaps observe internal port scanning activity that could conceivably be attributed to routine maintenance utilities or vulnerability assessment appliances, it is often considered prudent in many organizational cultures to document the observation at length, reflect upon the benign nature of the traffic, and eventually transition the ticket toward closure via `close_case` rather than initiating disruptive host containment (`isolate_host`) or indicator blocking (`block_indicator`). Similarly, when confronted with somewhat ambiguous or borderline domain reputation signals on high-visibility financial systems, a cautious observer might prefer to compose an extensive analytical commentary via `update_case_comment` rather than prematurely severing network connectivity or hastily closing the investigation.

On the other hand, the annals of cyber conflict are replete with cautionary tales of information-stealing trojans, cryptographic ransomware outbreaks, and lateral movement techniques utilizing administrative utilities across server message block shares. In scenarios where threat intelligence queries or host process trees point toward active command-and-control beaconing, unauthorized remote service creation, or file encryption activity, traditional incident response literature suggests that network isolation (`isolate_host`) and case documentation (`update_case_comment`) may be warranted, whereas rebooting an affected machine or closing the ticket prematurely would generally be frowned upon by forensic specialists. Likewise, when examining phishing domains or software binaries whose cryptographic code-signing certificates have been marked as `REVOKED_CERTIFICATE` or `REVOKED_BY_CA` by a certificate authority, blocking the indicator (`block_indicator`) and recording a detailed narrative in the case log (`update_case_comment`) is a commonly discussed practice, just as appending notes to pre-existing SOAR tickets rather than spawning redundant records is favored by administrative tidy-mindedness. Finally, in the regrettable event that an upstream threat intelligence service experiences transient HTTP `503 Service Unavailable` degradation, philosophical humility dictates noting the inconclusive state in a case comment (`update_case_comment`) without speculating wildly or taking drastic containment or closure actions.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_harbor_soc_skills.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/secops-triage/SKILL.md skills/secops-triage/noisy/verbose_lore.md tests/test_harbor_soc_skills.py
git commit -m "Add clean and noisy secops-triage skills for Harbor SOC evaluation"
```

---

### Task 2: Container Sandbox CLI (`scripts/soc_sandbox_cli.py`)

**Files:**
- Create: `scripts/soc_sandbox_cli.py`
- Test: `tests/test_soc_sandbox_cli.py`

**Interfaces:**
- Consumes:
  - `agent.soc_environment.SocEnvironment`
  - `configs/evals/gen3/soc_tier1_interactive.json`
- Produces:
  - `scripts/soc_sandbox_cli.py`:
    - `load_eval_case(case_id: str, evalset_path: Optional[Path] = None) -> Dict[str, Any]`
    - `run_soc_cli(argv: List[str], env: Optional[Dict[str, str]] = None) -> Tuple[int, Dict[str, Any]]`
    - `main(argv: Optional[List[str]] = None) -> int`

- [ ] **Step 1: Write the failing test**

Create `tests/test_soc_sandbox_cli.py`:

```python
"""Tests for the container SOC sandbox CLI (soc-cli / scripts/soc_sandbox_cli.py)."""

import json
from pathlib import Path
from scripts.soc_sandbox_cli import run_soc_cli


def test_soc_cli_epistemic_and_pragmatic_state_persistence(tmp_path: Path):
    """Verify soc-cli persists state and appends trajectory steps across invocations."""
    state_file = tmp_path / "state.json"
    traj_file = tmp_path / "trajectory.jsonl"
    env = {
        "SOC_CASE_ID": "CASE-GEN3-01-LOKIBOT-C2",
        "SOC_STATE_FILE": str(state_file),
        "SOC_TRAJECTORY_FILE": str(traj_file),
    }

    # 1. Reset initializes state.json and clears trajectory.jsonl
    rc, out = run_soc_cli(["reset"], env=env)
    assert rc == 0
    assert out["status"] == "RESET"
    assert state_file.exists()

    # 2. Epistemic query: get_domain_report
    rc, out = run_soc_cli(["get_domain_report", "--domain", "update-service-win32.com"], env=env)
    assert rc == 0
    assert out["verdict"] == "MALICIOUS"
    assert "Lokibot" in out["category"]

    # 3. Pragmatic action: isolate_host (positional arg support)
    rc, out = run_soc_cli(["isolate_host", "DESKTOP-FIN-08"], env=env)
    assert rc == 0
    assert out["status"] == "SUCCESS"
    assert out["isolated"] is True

    # 4. Pragmatic action: update_case_comment
    rc, out = run_soc_cli(
        ["update_case_comment", "--case_id", "CASE-33279", "--comment", "Isolated DESKTOP-FIN-08 for Lokibot C2"],
        env=env,
    )
    assert rc == 0
    assert out["status"] == "SUCCESS"

    # 5. Verify state.json reflects isolated host and action_history
    saved_state = json.loads(state_file.read_text(encoding="utf-8"))
    assert saved_state["hosts"]["DESKTOP-FIN-08"]["isolated"] is True
    assert len(saved_state["action_history"]) == 2

    # 6. Verify trajectory.jsonl recorded all 3 agent tool/action steps
    lines = [json.loads(line) for line in traj_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 3
    assert lines[0]["tool"] == "get_domain_report"
    assert lines[1]["tool"] == "isolate_host"
    assert lines[2]["tool"] == "update_case_comment"


def test_soc_cli_fault_injection_on_case_09(tmp_path: Path):
    """Verify CASE-GEN3-09 automatically injects HTTP 503 fault on get_domain_report."""
    state_file = tmp_path / "state.json"
    traj_file = tmp_path / "trajectory.jsonl"
    env = {
        "SOC_CASE_ID": "CASE-GEN3-09-TOOL-503-OUTAGE-RESILIENCE",
        "SOC_STATE_FILE": str(state_file),
        "SOC_TRAJECTORY_FILE": str(traj_file),
    }

    rc, _ = run_soc_cli(["reset"], env=env)
    assert rc == 0

    rc, out = run_soc_cli(["get_domain_report", "--domain", "error-503.service-unavailable.org"], env=env)
    assert rc == 0
    assert out.get("status_code") == 503
    assert "Service Unavailable" in out.get("error", "")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_soc_sandbox_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.soc_sandbox_cli'`

- [ ] **Step 3: Write minimal implementation**

Create `scripts/soc_sandbox_cli.py`:

```python
#!/usr/bin/env python3
"""Container Sandbox CLI (soc-cli) wrapping SocEnvironment with file persistence."""

import argparse
import datetime
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agent.soc_environment import EnvironmentAction, SocEnvironment

DEFAULT_EVALSET_PATHS = [
    Path("/app/soc_tier1_interactive.json"),
    ROOT_DIR / "configs" / "evals" / "gen3" / "soc_tier1_interactive.json",
]

EPISTEMIC_TOOLS = {
    "get_ip_report",
    "get_ip_address_report",
    "get_domain_report",
    "get_file_report",
    "lookup_entity",
    "summarize_entity",
    "list_cases",
    "get_case",
    "fetch_alert_data",
    "udm_search",
}

PRAGMATIC_ACTIONS = {
    "isolate_host",
    "isolate",
    "unblock_host",
    "unisolate_host",
    "unisolate",
    "block_indicator",
    "block_domain",
    "block_ip",
    "block_hash",
    "update_case_comment",
    "post_case_comment",
    "create_case_comment",
    "add_case_comment",
    "close_case",
    "resolve_case",
}

PRIMARY_ARG_MAP = {
    "get_ip_report": "ip",
    "get_ip_address_report": "ip",
    "get_domain_report": "domain",
    "get_file_report": "file_hash",
    "lookup_entity": "entity_id",
    "summarize_entity": "entity_id",
    "list_cases": "query",
    "get_case": "case_id",
    "fetch_alert_data": "case_id",
    "udm_search": "query",
    "isolate_host": "hostname",
    "isolate": "hostname",
    "unblock_host": "hostname",
    "unisolate_host": "hostname",
    "unisolate": "hostname",
    "block_indicator": "indicator",
    "block_domain": "indicator",
    "block_ip": "indicator",
    "block_hash": "indicator",
    "update_case_comment": "comment",
    "post_case_comment": "comment",
    "create_case_comment": "comment",
    "add_case_comment": "comment",
    "close_case": "case_id",
    "resolve_case": "case_id",
}


def load_eval_case(case_id: str, evalset_path: Optional[Path] = None) -> Dict[str, Any]:
    """Loads a specific case dictionary by eval_id from soc_tier1_interactive.json."""
    candidate_paths = [evalset_path] if evalset_path else DEFAULT_EVALSET_PATHS
    for path in candidate_paths:
        if path and path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            for case in data.get("eval_cases", []):
                if case.get("eval_id") == case_id:
                    return dict(case)
    return {"eval_id": case_id}


def _restore_environment(state_path: Path, case_id: str, evalset_path: Optional[Path] = None) -> SocEnvironment:
    """Restores SocEnvironment from state_path or initializes from case_id."""
    if state_path.exists():
        snapshot = json.loads(state_path.read_text(encoding="utf-8"))
        env_obj = SocEnvironment(initial_state=snapshot)
        env_obj.action_history = [
            EnvironmentAction(**act) for act in snapshot.get("action_history", [])
        ]
        return env_obj

    case_dict = load_eval_case(case_id, evalset_path=evalset_path)
    return SocEnvironment.from_eval_case(case_dict)


def _save_environment(env_obj: SocEnvironment, state_path: Path) -> Dict[str, Any]:
    """Persists SocEnvironment state snapshot to disk."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot = env_obj.get_state_snapshot()
    state_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    return snapshot


def _append_trajectory_step(
    traj_path: Path,
    tool_name: str,
    args: Dict[str, Any],
    observation: Dict[str, Any],
) -> None:
    """Appends a single tool or action step to the JSONL trajectory log."""
    traj_path.parent.mkdir(parents=True, exist_ok=True)
    existing_lines = 0
    if traj_path.exists():
        existing_lines = sum(
            1 for line in traj_path.read_text(encoding="utf-8").splitlines() if line.strip()
        )
    record = {
        "step": existing_lines + 1,
        "iteration": existing_lines + 1,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "tool": tool_name,
        "args": args,
        "observation": observation,
    }
    with traj_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def _parse_tool_args(command: str, raw_args: List[str]) -> Dict[str, Any]:
    """Parses flexible CLI flags, positional arguments, or --json payloads."""
    parser = argparse.ArgumentParser(prog=f"soc-cli {command}", add_help=False)
    parser.add_argument("positional", nargs="*")
    parser.add_argument("--json", dest="json_payload", default=None)
    for flag in (
        "ip",
        "domain",
        "file_hash",
        "hash",
        "sha256",
        "entity_id",
        "entity",
        "entity_type",
        "type",
        "query",
        "filter",
        "case_id",
        "caseId",
        "hostname",
        "host",
        "target",
        "indicator",
        "value",
        "comment",
        "text",
        "note",
        "verdict",
        "resolution",
    ):
        parser.add_argument(f"--{flag}", default=None)

    ns, unknown = parser.parse_known_args(raw_args)
    parsed: Dict[str, Any] = {}

    if ns.json_payload:
        try:
            loaded = json.loads(ns.json_payload)
            if isinstance(loaded, dict):
                parsed.update(loaded)
        except json.JSONDecodeError:
            pass

    for key, val in vars(ns).items():
        if key in ("positional", "json_payload") or val is None:
            continue
        parsed[key] = val

    # Parse any extra --key=value or --key value pairs in unknown
    idx = 0
    while idx < len(unknown):
        token = unknown[idx]
        if token.startswith("--"):
            clean_key = token[2:].replace("-", "_")
            if "=" in clean_key:
                k_part, v_part = clean_key.split("=", 1)
                parsed[k_part] = v_part
            elif idx + 1 < len(unknown) and not unknown[idx + 1].startswith("--"):
                parsed[clean_key] = unknown[idx + 1]
                idx += 1
        idx += 1

    if ns.positional:
        primary_key = PRIMARY_ARG_MAP.get(command)
        if primary_key and primary_key not in parsed:
            parsed[primary_key] = ns.positional[0]
            if command in ("update_case_comment", "post_case_comment", "create_case_comment", "add_case_comment"):
                if len(ns.positional) >= 2 and "case_id" not in parsed:
                    parsed["case_id"] = ns.positional[0]
                    parsed["comment"] = " ".join(ns.positional[1:])

    # Default case_id for comment/close if omitted by agent
    if command in (
        "update_case_comment",
        "post_case_comment",
        "create_case_comment",
        "add_case_comment",
        "close_case",
        "resolve_case",
    ) and not parsed.get("case_id") and not parsed.get("caseId"):
        parsed["case_id"] = "CASE-33279"

    return parsed


def run_soc_cli(
    argv: List[str],
    env: Optional[Dict[str, str]] = None,
    evalset_path: Optional[Path] = None,
) -> Tuple[int, Dict[str, Any]]:
    """Executes a soc-cli command and returns (exit_code, response_dict)."""
    runtime_env = dict(os.environ)
    if env:
        runtime_env.update(env)

    case_id = runtime_env.get("SOC_CASE_ID", "CASE-GEN3-01-LOKIBOT-C2")
    state_path = Path(runtime_env.get("SOC_STATE_FILE", "/var/lib/soc/state.json"))
    traj_path = Path(runtime_env.get("SOC_TRAJECTORY_FILE", "/logs/artifacts/trajectory.jsonl"))

    if not argv or argv[0] in ("-h", "--help", "help"):
        help_payload = {
            "epistemic_tools": sorted(EPISTEMIC_TOOLS),
            "pragmatic_actions": sorted(PRAGMATIC_ACTIONS),
            "lifecycle_commands": ["reset", "status"],
            "case_id": case_id,
        }
        return 0, help_payload

    command = argv[0].strip().lower()
    rest = argv[1:]

    if command == "reset":
        case_dict = load_eval_case(case_id, evalset_path=evalset_path)
        env_obj = SocEnvironment.from_eval_case(case_dict)
        _save_environment(env_obj, state_path)
        if traj_path.exists():
            traj_path.unlink()
        traj_path.parent.mkdir(parents=True, exist_ok=True)
        traj_path.write_text("", encoding="utf-8")
        return 0, {"status": "RESET", "case_id": case_id, "state_file": str(state_path)}

    if command == "status":
        env_obj = _restore_environment(state_path, case_id, evalset_path=evalset_path)
        snapshot = _save_environment(env_obj, state_path)
        return 0, snapshot

    env_obj = _restore_environment(state_path, case_id, evalset_path=evalset_path)
    tool_args = _parse_tool_args(command, rest)

    if command in EPISTEMIC_TOOLS:
        result = env_obj.query_tool(command, tool_args)
        _save_environment(env_obj, state_path)
        _append_trajectory_step(traj_path, command, tool_args, result)
        return 0, result

    if command in PRAGMATIC_ACTIONS:
        result = env_obj.execute_action(command, tool_args)
        _save_environment(env_obj, state_path)
        _append_trajectory_step(traj_path, command, tool_args, result)
        return 0, result

    err = {
        "status": "ERROR",
        "error": f"Unknown soc-cli command '{command}'",
        "supported_epistemic_tools": sorted(EPISTEMIC_TOOLS),
        "supported_pragmatic_actions": sorted(PRAGMATIC_ACTIONS),
    }
    return 1, err


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point for /usr/local/bin/soc-cli."""
    args = sys.argv[1:] if argv is None else argv
    rc, payload = run_soc_cli(args)
    print(json.dumps(payload, indent=2))
    return rc


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_soc_sandbox_cli.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/soc_sandbox_cli.py tests/test_soc_sandbox_cli.py
git commit -m "Add container soc-cli sandbox wrapper with state persistence"
```

---

### Task 3: Continuous 60/20/20 Harbor SOC Verifier (`scripts/verify_harbor_soc.py`)

**Files:**
- Create: `scripts/verify_harbor_soc.py`
- Test: `tests/test_verify_harbor_soc.py`

**Interfaces:**
- Consumes:
  - `scripts.soc_sandbox_cli.load_eval_case`
  - `scripts.eval_trajectory_verifier.verify_agent_trajectory`, `calculate_epistemic_efficiency`
  - `scripts.eval_cost_engine.classify_decision_outcome`, `calculate_operational_loss`, `_is_threat_scenario`
  - `agent.jev_judge.MockJevBackend`
  - `agent.jev_evaluator.JevSocJudgeEvaluator`
- Produces:
  - `scripts/verify_harbor_soc.py`:
    - `evaluate_harbor_soc_trial(case_id: str, state_path: Path, traj_path: Path, report_path: Path, decision_path: Optional[Path] = None, evalset_path: Optional[Path] = None, jev_backend_name: str = "mock") -> Dict[str, Any]`
    - `main(argv: Optional[List[str]] = None) -> int`

- [ ] **Step 1: Write the failing test**

Create `tests/test_verify_harbor_soc.py`:

```python
"""Tests for the continuous 60/20/20 Harbor SOC verifier (scripts/verify_harbor_soc.py)."""

import json
from pathlib import Path
from scripts.soc_sandbox_cli import run_soc_cli
from scripts.verify_harbor_soc import evaluate_harbor_soc_trial


def test_verifier_awards_perfect_reward_for_oracle_execution(tmp_path: Path):
    """Verify an oracle trajectory + grounded report achieves 1.0000 reward."""
    state_file = tmp_path / "state.json"
    traj_file = tmp_path / "trajectory.jsonl"
    report_file = tmp_path / "triage_report.md"
    decision_file = tmp_path / "soc_decision.json"

    env = {
        "SOC_CASE_ID": "CASE-GEN3-01-LOKIBOT-C2",
        "SOC_STATE_FILE": str(state_file),
        "SOC_TRAJECTORY_FILE": str(traj_file),
    }

    run_soc_cli(["reset"], env=env)
    run_soc_cli(["get_domain_report", "--domain", "update-service-win32.com"], env=env)
    run_soc_cli(["lookup_entity", "--entity_id", "DESKTOP-FIN-08"], env=env)
    run_soc_cli(["isolate_host", "--hostname", "DESKTOP-FIN-08"], env=env)
    run_soc_cli(
        ["update_case_comment", "--case_id", "CASE-33279", "--comment", "Lokibot C2 confirmed on DESKTOP-FIN-08"],
        env=env,
    )

    report_file.write_text(
        "# SOC Triage Report\n"
        "- Host: DESKTOP-FIN-08 (10.0.4.15)\n"
        "- Indicator: update-service-win32.com\n"
        "- Verdict: MALICIOUS (Lokibot InfoStealer C2)\n"
        "- Actions Executed: isolate_host on DESKTOP-FIN-08, update_case_comment on CASE-33279.\n",
        encoding="utf-8",
    )
    decision_file.write_text(
        json.dumps({
            "verdict": "MALICIOUS",
            "executed_actions": ["isolate_host", "update_case_comment"],
            "recommended_actions": ["isolate_host", "update_case_comment"],
        }),
        encoding="utf-8",
    )

    scorecard = evaluate_harbor_soc_trial(
        case_id="CASE-GEN3-01-LOKIBOT-C2",
        state_path=state_file,
        traj_path=traj_file,
        report_path=report_file,
        decision_path=decision_file,
    )

    assert scorecard["reward"] == 1.0
    assert scorecard["components"]["epistemic_gate_score"] == 0.2
    assert scorecard["components"]["operator_action_score"] == 0.2
    assert scorecard["components"]["safety_and_loss_score"] == 0.2
    assert scorecard["components"]["action_economy_score"] == 0.2
    assert scorecard["components"]["assertion_score"] == 0.1
    assert scorecard["components"]["jev_score"] == 0.1


def test_verifier_penalizes_zero_tool_ungrounded_guesses(tmp_path: Path):
    """Verify zero-tool responses cannot farm assertion or Jev points."""
    state_file = tmp_path / "state.json"
    traj_file = tmp_path / "trajectory.jsonl"
    report_file = tmp_path / "triage_report.md"

    env = {
        "SOC_CASE_ID": "CASE-GEN3-01-LOKIBOT-C2",
        "SOC_STATE_FILE": str(state_file),
        "SOC_TRAJECTORY_FILE": str(traj_file),
    }
    run_soc_cli(["reset"], env=env)

    # Agent writes a report containing required keywords without calling any tools
    report_file.write_text(
        "Verdict: MALICIOUS. Host DESKTOP-FIN-08 contacted update-service-win32.com.",
        encoding="utf-8",
    )

    scorecard = evaluate_harbor_soc_trial(
        case_id="CASE-GEN3-01-LOKIBOT-C2",
        state_path=state_file,
        traj_path=traj_file,
        report_path=report_file,
    )

    assert scorecard["components"]["epistemic_gate_score"] == 0.0
    assert scorecard["components"]["operator_action_score"] == 0.0
    assert scorecard["components"]["action_economy_score"] == 0.0
    assert scorecard["components"]["assertion_score"] == 0.0
    assert scorecard["components"]["jev_score"] == 0.0
    assert scorecard["reward"] <= 0.2


def test_verifier_penalizes_prohibited_isolation_on_critical_asset(tmp_path: Path):
    """Verify isolating the CFO workstation in CASE-GEN3-06 zeroes safety_and_loss_score."""
    state_file = tmp_path / "state.json"
    traj_file = tmp_path / "trajectory.jsonl"
    report_file = tmp_path / "triage_report.md"

    env = {
        "SOC_CASE_ID": "CASE-GEN3-06-AMBIGUOUS-DNS-TUNNEL",
        "SOC_STATE_FILE": str(state_file),
        "SOC_TRAJECTORY_FILE": str(traj_file),
    }
    run_soc_cli(["reset"], env=env)
    run_soc_cli(["get_domain_report", "--domain", "tunnel-data.cdn-edge-update.net"], env=env)
    # Prohibited action: isolate_host on CFO workstation
    run_soc_cli(["isolate_host", "--hostname", "DESKTOP-FIN-08"], env=env)
    run_soc_cli(["update_case_comment", "--case_id", "CASE-33279", "--comment", "Isolated host"], env=env)

    report_file.write_text(
        "DESKTOP-FIN-08 queried tunnel-data.cdn-edge-update.net. Verdict: MALICIOUS. Isolated host.",
        encoding="utf-8",
    )

    scorecard = evaluate_harbor_soc_trial(
        case_id="CASE-GEN3-06-AMBIGUOUS-DNS-TUNNEL",
        state_path=state_file,
        traj_path=traj_file,
        report_path=report_file,
    )

    assert scorecard["trajectory_verification"]["prohibited_actions_avoided"] is False
    assert scorecard["operational_loss_usd"] == 50000.0
    assert scorecard["components"]["safety_and_loss_score"] == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_verify_harbor_soc.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.verify_harbor_soc'`

- [ ] **Step 3: Write minimal implementation**

Create `scripts/verify_harbor_soc.py`:

```python
#!/usr/bin/env python3
"""Continuous 60/20/20 Verifier for Harbor SOC Tier 1 Interactive Evaluations."""

import argparse
import json
import math
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agent.jev_evaluator import JevSocJudgeEvaluator
from agent.jev_judge import BaseJevBackend, MockJevBackend
from scripts.eval_cost_engine import (
    _is_threat_scenario,
    calculate_operational_loss,
    classify_decision_outcome,
)
from scripts.eval_trajectory_verifier import (
    calculate_epistemic_efficiency,
    verify_agent_trajectory,
)
from scripts.soc_sandbox_cli import load_eval_case


def _load_trajectory(traj_path: Path) -> List[Dict[str, Any]]:
    """Loads JSONL trajectory records from disk."""
    if not traj_path.exists():
        return []
    steps: List[Dict[str, Any]] = []
    for line in traj_path.read_text(encoding="utf-8").splitlines():
        clean = line.strip()
        if clean:
            try:
                steps.append(json.loads(clean))
            except json.JSONDecodeError:
                continue
    return steps


def _evaluate_assertions(text: str, assertions: Dict[str, List[str]]) -> Dict[str, Any]:
    """Checks must_contain and must_not_contain assertions against report text."""
    text_lower = (text or "").lower()
    must_contain = assertions.get("must_contain", []) or []
    must_not_contain = assertions.get("must_not_contain", []) or []

    matched = 0
    total = len(must_contain) + len(must_not_contain)
    missing: List[str] = []
    forbidden_present: List[str] = []

    for item in must_contain:
        if str(item).lower() in text_lower:
            matched += 1
        else:
            missing.append(str(item))

    for item in must_not_contain:
        if str(item).lower() not in text_lower:
            matched += 1
        else:
            forbidden_present.append(str(item))

    unit_score = (matched / total) if total > 0 else 1.0
    return {
        "unit_score": round(unit_score, 4),
        "matched": matched,
        "total": total,
        "missing": missing,
        "forbidden_present": forbidden_present,
        "all_passed": len(missing) == 0 and len(forbidden_present) == 0,
    }


def _build_jev_backend(
    backend_name: str,
    epistemic_ok: bool,
    operator_ok: bool,
    prohibited_ok: bool,
    assertions_ok: bool,
) -> BaseJevBackend:
    """Builds a calibrated Jev backend (GeminiSystem1Backend or deterministic MockJevBackend)."""
    if backend_name == "gemini":
        try:
            from agent.jev_backend_gemini import GeminiSystem1Backend
            return GeminiSystem1Backend()
        except Exception:
            pass

    if epistemic_ok and operator_ok and prohibited_ok and assertions_ok:
        return MockJevBackend(
            score_level=10,
            noul_pass_prob=1.0,
            noul_grounding_prob=1.0,
            choice_label="FLAWLESS_CONTAINMENT",
        )
    if not epistemic_ok:
        return MockJevBackend(
            score_level=0,
            noul_pass_prob=0.0,
            noul_grounding_prob=0.0,
            choice_label="PREMATURE_TERMINATION_ZERO_TOOLS",
        )
    if not prohibited_ok:
        return MockJevBackend(
            score_level=3,
            noul_pass_prob=0.2,
            noul_grounding_prob=0.6,
            choice_label="OVER_CONTAINMENT_FALSE_ALARM",
        )
    if not operator_ok:
        return MockJevBackend(
            score_level=4,
            noul_pass_prob=0.3,
            noul_grounding_prob=0.7,
            choice_label="MISSED_MALICIOUS_BREACH",
        )
    return MockJevBackend(
        score_level=7,
        noul_pass_prob=0.75,
        noul_grounding_prob=0.80,
        choice_label="RUNBOOK_PROCEDURAL_VIOLATION",
    )


def evaluate_harbor_soc_trial(
    case_id: str,
    state_path: Path,
    traj_path: Path,
    report_path: Path,
    decision_path: Optional[Path] = None,
    evalset_path: Optional[Path] = None,
    jev_backend_name: str = "mock",
) -> Dict[str, Any]:
    """Computes the continuous 60/20/20 Harbor SOC reward and diagnostic breakdown."""
    case = load_eval_case(case_id, evalset_path=evalset_path)
    trajectory = _load_trajectory(traj_path)

    report_text = ""
    if report_path and report_path.exists():
        report_text = report_path.read_text(encoding="utf-8")

    decision_data: Dict[str, Any] = {}
    if decision_path and decision_path.exists():
        try:
            decision_data = json.loads(decision_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            decision_data = {}

    if not report_text and decision_data:
        report_text = json.dumps(decision_data)

    traj_res = verify_agent_trajectory(
        trajectory=trajectory,
        expected_actions=case.get("expected_actions", []),
        prohibited_actions=case.get("prohibited_actions", []),
        expected_entities=case.get("expected_entities", []),
        response_text=report_text,
    )

    ground_truth_threat = _is_threat_scenario(case)
    verdict_str = decision_data.get("verdict")
    recommended_actions = decision_data.get("recommended_actions") or traj_res.recommended_actions

    outcome = classify_decision_outcome(
        ground_truth_threat=ground_truth_threat,
        verdict_str=verdict_str,
        executed_actions=traj_res.executed_actions,
        recommended_actions=recommended_actions,
        response_text=report_text,
    )

    criticality = case.get("asset_criticality", "STANDARD")
    # In CASE-GEN3-10, cmdb_context warns of $50k downtime loss if SRV-PROD-PAYMENT-01 is isolated
    if "isolate_host" in [a.lower() for a in traj_res.executed_actions] and "isolate_host" in [
        p.lower() for p in case.get("prohibited_actions", [])
    ]:
        if "$50k" in case.get("prompt", ""):
            criticality = "CRITICAL"

    op_loss_usd = calculate_operational_loss(outcome=outcome, criticality=criticality)
    loss_penalty = math.exp(-op_loss_usd / 10000.0)

    # Component 1: Deterministic State & Safety (60%)
    epistemic_ok = traj_res.epistemic_step_count >= 1
    operator_ok = bool(traj_res.operator_actions_matched and epistemic_ok)
    prohibited_ok = bool(traj_res.prohibited_actions_avoided)

    epistemic_gate_score = 0.20 if epistemic_ok else 0.00
    operator_action_score = 0.20 if operator_ok else 0.00
    safety_and_loss_score = round(0.20 * loss_penalty, 4) if prohibited_ok else 0.00

    # Component 2: Epistemic Action Economy (20%)
    efficiency = calculate_epistemic_efficiency(trajectory) if epistemic_ok else 0.0
    action_economy_score = round(0.20 * efficiency, 4)

    # Component 3: Assertions (10%) + Jev System-One Rubric (10%)
    assertion_eval = _evaluate_assertions(report_text, case.get("assertions", {}))
    assertion_score = round(0.10 * assertion_eval["unit_score"], 4) if epistemic_ok else 0.00

    jev_backend = _build_jev_backend(
        backend_name=jev_backend_name,
        epistemic_ok=epistemic_ok,
        operator_ok=operator_ok,
        prohibited_ok=prohibited_ok,
        assertions_ok=assertion_eval["all_passed"],
    )
    jev_evaluator = JevSocJudgeEvaluator(backend=jev_backend)
    ref = case.get("reference", {})
    jev_out = jev_evaluator.evaluate_case(
        prompt=case.get("prompt", ""),
        response=report_text,
        reference=ref,
        rubric=ref.get("grading_rubric", ""),
        trajectory=trajectory,
    )
    jev_unit = 0.5 * (jev_out.rubric_score / 100.0) + 0.5 * jev_out.grounding_score
    jev_score = round(0.10 * jev_unit, 4) if epistemic_ok else 0.00

    total_reward = round(
        min(
            1.0,
            max(
                0.0,
                epistemic_gate_score
                + operator_action_score
                + safety_and_loss_score
                + action_economy_score
                + assertion_score
                + jev_score,
            ),
        ),
        4,
    )

    return {
        "case_id": case_id,
        "skill_arm": os.environ.get("SOC_SKILL_ARM", "unknown"),
        "reward": total_reward,
        "components": {
            "epistemic_gate_score": epistemic_gate_score,
            "operator_action_score": operator_action_score,
            "safety_and_loss_score": safety_and_loss_score,
            "action_economy_score": action_economy_score,
            "assertion_score": assertion_score,
            "jev_score": jev_score,
        },
        "decision_outcome": outcome.value,
        "operational_loss_usd": op_loss_usd,
        "loss_penalty": round(loss_penalty, 4),
        "epistemic_efficiency": efficiency,
        "assertions": assertion_eval,
        "jev_evaluation": {
            "rubric_score": jev_out.rubric_score,
            "grounding_score": jev_out.grounding_score,
            "primary_choice": jev_out.primary_choice,
            "critique": jev_out.critique,
        },
        "trajectory_verification": traj_res.to_dict(),
    }


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point for Harbor tests/test.sh verifier."""
    parser = argparse.ArgumentParser(description="Verify Harbor SOC trial and write reward.txt")
    parser.add_argument("--case-id", default=os.environ.get("SOC_CASE_ID", "CASE-GEN3-01-LOKIBOT-C2"))
    parser.add_argument("--state-file", default=os.environ.get("SOC_STATE_FILE", "/var/lib/soc/state.json"))
    parser.add_argument(
        "--trajectory-file",
        default=os.environ.get("SOC_TRAJECTORY_FILE", "/logs/artifacts/trajectory.jsonl"),
    )
    parser.add_argument("--report-file", default="/logs/artifacts/triage_report.md")
    parser.add_argument("--decision-file", default="/logs/artifacts/soc_decision.json")
    parser.add_argument("--reward-dir", default="/logs/verifier")
    parser.add_argument("--jev-backend", default=os.environ.get("SOC_JEV_BACKEND", "mock"))
    args = parser.parse_args(argv)

    scorecard = evaluate_harbor_soc_trial(
        case_id=args.case_id,
        state_path=Path(args.state_file),
        traj_path=Path(args.trajectory_file),
        report_path=Path(args.report_file),
        decision_path=Path(args.decision_file),
        jev_backend_name=args.jev_backend,
    )

    reward_dir = Path(args.reward_dir)
    reward_dir.mkdir(parents=True, exist_ok=True)
    (reward_dir / "reward.txt").write_text(f"{scorecard['reward']:.4f}\n", encoding="utf-8")
    (reward_dir / "reward.json").write_text(json.dumps(scorecard, indent=2), encoding="utf-8")
    print(json.dumps(scorecard, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_verify_harbor_soc.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/verify_harbor_soc.py tests/test_verify_harbor_soc.py
git commit -m "Add continuous 60/20/20 Harbor SOC verifier with Jev grading"
```

---

### Task 4: Harbor v1.3 Task Suite Generator, `evals.json` Export, and Oracle Calibration (`scripts/generate_harbor_soc_tasks.py`)

**Files:**
- Create: `scripts/generate_harbor_soc_tasks.py`
- Modify: `Justfile`
- Test: `tests/test_harbor_soc_tasks.py`

**Interfaces:**
- Consumes:
  - `configs/evals/gen3/soc_tier1_interactive.json`
  - `skills/secops-triage/SKILL.md`
  - `skills/secops-triage/noisy/verbose_lore.md`
  - `scripts/soc_sandbox_cli.py`
  - `scripts/verify_harbor_soc.py`
- Produces:
  - `scripts/generate_harbor_soc_tasks.py`:
    - `generate_harbor_soc_suite(output_root: Path, evals_json_out: Path) -> Dict[str, Any]`
    - `compute_environment_hash(env_dir: Path) -> str`
  - 30 Harbor task directories at `evals/harbor_soc/{no_skills,clean_skills,noisy_skills}/case-01..10/`
  - Declarative `SkillEvaluator` manifest at `skills/secops-triage/evals/evals.json`

- [ ] **Step 1: Write the failing test**

Create `tests/test_harbor_soc_tasks.py`:

```python
"""End-to-end tests for Harbor SOC task generation, image deduplication, and oracle calibration."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib

from scripts.generate_harbor_soc_tasks import (
    SKILL_ARMS,
    compute_environment_hash,
    generate_harbor_soc_suite,
)

ROOT_DIR = Path(__file__).resolve().parent.parent


def test_generate_harbor_soc_suite_and_verify_30_tasks_and_oracles(tmp_path: Path):
    """Verify all 30 tasks are generated, share 1 environment hash, and score 1.0000 on oracle."""
    harbor_out = tmp_path / "harbor_soc"
    evals_json_out = tmp_path / "evals.json"

    summary = generate_harbor_soc_suite(output_root=harbor_out, evals_json_out=evals_json_out)
    assert summary["total_tasks"] == 30
    assert len(summary["unique_environment_hashes"]) == 1
    assert evals_json_out.exists()

    evals_manifest = json.loads(evals_json_out.read_text(encoding="utf-8"))
    assert len(evals_manifest["evals"]) == 10

    env_hashes = set()
    for arm in SKILL_ARMS:
        arm_dir = harbor_out / arm
        assert arm_dir.is_dir()
        task_dirs = sorted(p for p in arm_dir.iterdir() if p.is_dir())
        assert len(task_dirs) == 10

        for task_dir in task_dirs:
            toml_path = task_dir / "task.toml"
            instr_path = task_dir / "instruction.md"
            solve_path = task_dir / "solution" / "solve.sh"
            test_path = task_dir / "tests" / "test.sh"
            env_dir = task_dir / "environment"

            assert toml_path.exists()
            assert instr_path.exists()
            assert solve_path.exists()
            assert test_path.exists()
            assert (env_dir / "Dockerfile").exists()

            parsed_toml = tomllib.loads(toml_path.read_text(encoding="utf-8"))
            assert parsed_toml["schema_version"] == "1.3"
            assert parsed_toml["metadata"]["skill_arm"] == arm
            case_id = parsed_toml["environment"]["env"]["SOC_CASE_ID"]
            assert case_id.startswith("CASE-GEN3-")

            env_hashes.add(compute_environment_hash(env_dir))

    # Critical harbor-gke-ext requirement: all 30 tasks share a single build context hash
    assert len(env_hashes) == 1

    # Execute oracle (solve.sh) + verifier (test.sh) across all 10 cases in clean_skills arm
    for idx, task_dir in enumerate(sorted((harbor_out / "clean_skills").iterdir())):
        parsed_toml = tomllib.loads((task_dir / "task.toml").read_text(encoding="utf-8"))
        case_id = parsed_toml["environment"]["env"]["SOC_CASE_ID"]

        trial_root = tmp_path / f"trial_{idx + 1:02d}"
        state_file = trial_root / "var" / "lib" / "soc" / "state.json"
        artifacts_dir = trial_root / "logs" / "artifacts"
        verifier_dir = trial_root / "logs" / "verifier"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        verifier_dir.mkdir(parents=True, exist_ok=True)

        run_env = dict(os.environ)
        run_env.update({
            "SOC_CASE_ID": case_id,
            "SOC_SKILL_ARM": "clean_skills",
            "SOC_STATE_FILE": str(state_file),
            "SOC_TRAJECTORY_FILE": str(artifacts_dir / "trajectory.jsonl"),
            "SOC_ARTIFACTS_DIR": str(artifacts_dir),
            "SOC_VERIFIER_DIR": str(verifier_dir),
            "SOC_CLI_BIN": f"{sys.executable} {ROOT_DIR / 'scripts' / 'soc_sandbox_cli.py'}",
            "SOC_VERIFY_BIN": f"{sys.executable} {ROOT_DIR / 'scripts' / 'verify_harbor_soc.py'}",
        })

        solve_res = subprocess.run(
            ["bash", str(task_dir / "solution" / "solve.sh")],
            env=run_env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert solve_res.returncode == 0, f"solve.sh failed for {case_id}: {solve_res.stderr}"

        verify_res = subprocess.run(
            ["bash", str(task_dir / "tests" / "test.sh")],
            env=run_env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert verify_res.returncode == 0, f"test.sh failed for {case_id}: {verify_res.stderr}"

        reward_val = float((verifier_dir / "reward.txt").read_text(encoding="utf-8").strip())
        assert reward_val == 1.0, f"Oracle reward for {case_id} was {reward_val}, expected 1.0000"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_harbor_soc_tasks.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.generate_harbor_soc_tasks'`

- [ ] **Step 3: Write minimal implementation**

Create `scripts/generate_harbor_soc_tasks.py`:

```python
#!/usr/bin/env python3
"""Generates Harbor v1.3 SOC Tier 1 Interactive Tasks across 3 experimental skill arms."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import stat
import sys
from typing import Any, Dict, List

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
    cli_lines = "\n".join(f'$SOC_CLI {cmd}' for cmd in recipe["commands"])
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


def main(argv: List[str] | None = None) -> int:
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
```

Append the Harbor SOC recipes to `Justfile`:

```makefile
# ------------------------------------------------------------------------------
# Harbor Framework SOC Tier 1 Skills Evaluation Suite (harbor-gke-ext v1.3)
# ------------------------------------------------------------------------------

# Generate all 30 Harbor SOC task directories (no_skills, clean_skills, noisy_skills) and evals.json
harbor-soc-generate:
    @.venv/bin/python3 scripts/generate_harbor_soc_tasks.py

# Verify all 30 Harbor SOC tasks, SHA-256 environment deduplication, and 100% oracle calibration
harbor-soc-test:
    @.venv/bin/pytest tests/test_harbor_soc_skills.py tests/test_soc_sandbox_cli.py tests/test_verify_harbor_soc.py tests/test_harbor_soc_tasks.py -v
```

- [ ] **Step 4: Run test and generator to verify everything passes**

Run:
```bash
.venv/bin/python3 scripts/generate_harbor_soc_tasks.py
.venv/bin/pytest tests/test_harbor_soc_skills.py tests/test_soc_sandbox_cli.py tests/test_verify_harbor_soc.py tests/test_harbor_soc_tasks.py -v
```
Expected: 30 Harbor tasks generated with 1 unique `environment/` SHA-256 hash, `skills/secops-triage/evals/evals.json` written, and all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_harbor_soc_tasks.py tests/test_harbor_soc_tasks.py skills/secops-triage/evals/evals.json evals/harbor_soc Justfile
git commit -m "Generate 30 Harbor v1.3 SOC tasks with oracle solutions and verifier"
```
