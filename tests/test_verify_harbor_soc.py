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
