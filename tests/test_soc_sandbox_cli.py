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
