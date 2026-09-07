"""Unit tests for Approach 3: Hierarchical Multi-Agent Supervisor / Worker Architecture.

Tests:
1. Alert classification across operational domains.
2. Runbook mapping and translation from repository submodule.
3. SOCRunbookWorkerAgent epistemic investigation and report generation.
4. SOCSupervisorAgent synthesis, containment execution, and environment state updates.
5. Unified trajectory recording and compliance with Trajectory Verifier.
6. SOCTier1Response interface compatibility.
7. eval_soc_agent.py CLI --agent-mode argument and runner routing.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from agent.hierarchical_soc_agent import (
    CLASSIFICATION_RUNBOOK_MAP,
    DEFAULT_RUNBOOKS_DIR,
    HierarchicalSOCTier1Agent,
    SOCRunbookWorkerAgent,
    SOCSupervisorAgent,
    SOCTier1Agent,
    SOCTier1Response,
    WorkerInvestigationReport,
    extract_worker_report,
    load_runbook,
    translate_runbook_to_system_instruction,
)
from agent.soc_environment import SocEnvironment
from agent.soc_tier1_agent import SocDecision, extract_soc_decision
from scripts.eval_trajectory_verifier import verify_agent_trajectory


ROOT_DIR = Path(__file__).resolve().parent.parent


def test_classification_and_runbook_mapping():
    """Verify alert classification correctly categorizes alerts and maps to runbooks."""
    supervisor = SOCSupervisorAgent()

    test_cases = [
        # Malware / Hash alerts
        ("Triage alert for suspicious file hash e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 detected on endpoint", "MALWARE_HASH"),
        ("Ransomware payload detected: mimikatz binary identified in temporary folder", "MALWARE_HASH"),
        ("Supply chain binary anomaly with revoked certificate on payroll_update.exe", "MALWARE_HASH"),
        # Lateral movement alerts
        ("Investigate PsExec remote service execution originating from workstation to file server", "LATERAL_MOVEMENT"),
        ("WMI process creation detected: wmic process call create cmd.exe on remote host", "LATERAL_MOVEMENT"),
        ("Suspicious SMB session and lateral movement detected across internal subnet", "LATERAL_MOVEMENT"),
        # Suspicious login alerts
        ("Triage authentication log alert: multiple failed logins followed by successful login from untrusted location", "SUSPICIOUS_LOGIN"),
        ("Impossible travel detected for user jdoe between New York and London within 10 minutes", "SUSPICIOUS_LOGIN"),
        ("Authorized Qualys vulnerability scanner noise triage on SRV-PROD-PAYMENT-01", "SUSPICIOUS_LOGIN"),
        # Phishing domain alerts
        ("Credential harvesting phishing domain login-microsoft-auth.com reported in email", "PHISHING_DOMAIN"),
        ("Typosquat domain secure-bank-portal.xyz identified in employee phishing report", "PHISHING_DOMAIN"),
        # C2 Beacon alerts
        ("Host DESKTOP-FIN-08 connecting repeatedly to C2 server IP 198.51.100.42", "C2_BEACON"),
        ("DNS tunneling beaconing activity observed from finance workstation", "C2_BEACON"),
    ]

    for prompt, expected_class in test_cases:
        classification = supervisor.classify_alert(prompt)
        assert classification == expected_class, f"Failed for prompt: {prompt}"
        runbook = supervisor.get_runbook_for_classification(classification)
        assert runbook == CLASSIFICATION_RUNBOOK_MAP[expected_class]


def test_runbook_loading_from_submodule():
    """Verify load_runbook reads actual markdown files from the ai-runbooks submodule."""
    assert DEFAULT_RUNBOOKS_DIR.exists(), f"Submodule runbook directory missing at {DEFAULT_RUNBOOKS_DIR}"

    for classification, runbook_name in CLASSIFICATION_RUNBOOK_MAP.items():
        content = load_runbook(runbook_name, DEFAULT_RUNBOOKS_DIR)
        assert content, f"Empty content for runbook: {runbook_name}"
        assert "# " in content or "## " in content, f"Runbook {runbook_name} is not valid markdown"


def test_runbook_translation_to_worker_system_instruction():
    """Verify translation produces instructions with epistemic constraints and tool mappings."""
    sample_runbook = """# Malware Triage Runbook
## Tools
* `gti-mcp.get_file_report`
* `secops-mcp.lookup_entity`
* `secops-soar.list_cases`
## Steps
1. Enrich file hash using `gti-mcp.get_file_report`.
2. Check host details using `secops-mcp.lookup_entity`.
"""
    translated = translate_runbook_to_system_instruction(sample_runbook, "MALWARE_HASH")

    assert "SOC Runbook Worker Agent" in translated
    assert "MALWARE_HASH" in translated
    assert "Epistemic Investigation Only" in translated
    assert "Do NOT execute containment actions" in translated
    assert "get_file_report" in translated
    assert "lookup_entity" in translated
    assert "list_cases" in translated
    assert "gti-mcp.get_file_report" not in translated
    assert "secops-mcp.lookup_entity" not in translated
    assert "```worker_report" in translated


def test_worker_agent_epistemic_tool_restriction():
    """Verify worker agent is equipped only with epistemic read-only tools and no pragmatic actions."""
    runbook_text = load_runbook("malware_triage.md", DEFAULT_RUNBOOKS_DIR)
    worker = SOCRunbookWorkerAgent(
        classification="MALWARE_HASH",
        runbook_name="malware_triage.md",
        runbook_content=runbook_text,
    )

    tool_names = list(worker.tools_dict.keys())
    assert "get_file_report" in tool_names
    assert "lookup_entity" in tool_names
    assert "get_ip_address_report" in tool_names
    assert "get_domain_report" in tool_names
    assert "list_cases" in tool_names

    # Pragmatic state-changing actions must NOT be in worker tool dictionary
    assert "isolate_host" not in tool_names
    assert "block_indicator" not in tool_names
    assert "close_case" not in tool_names
    assert "post_case_comment" not in tool_names


@pytest.mark.parametrize("tool_name", [
    "isolate_host", "isolate", "block_ip", "close_case", "post_case_comment",
    "get_case", "unknown_tool",
])
def test_worker_rejects_tools_outside_allowlist_before_environment_dispatch(tool_name):
    env = MagicMock()
    worker = SOCRunbookWorkerAgent(
        classification="C2_BEACON", runbook_name="basic_ioc_enrichment.md",
        runbook_content="# Investigate evidence", managed_model="offline-model",
        environment=env,
    )
    response = json.loads(worker._execute_tool_action(tool_name, {"hostname": "test-host"}))
    assert response["status"] == "DENIED"
    env.query_tool.assert_not_called()
    env.execute_action.assert_not_called()


@pytest.mark.parametrize("entrypoint", ["investigate", "query"])
def test_worker_denied_containment_is_recorded_as_attempt_not_execution(entrypoint):
    env = SocEnvironment()
    before = env.get_state_snapshot()
    worker = SOCRunbookWorkerAgent(
        classification="C2_BEACON", runbook_name="basic_ioc_enrichment.md",
        runbook_content="# Investigate evidence", managed_model="offline-model",
        environment=env,
    )
    outputs = [
        ('Action: isolate_host(hostname="DESKTOP-FIN-08")', {}),
        ('Action: get_ip_address_report(ip="198.51.100.42")', {}),
        ('Final Answer: Escalate the investigation to the supervisor.', {}),
    ]
    with patch.object(worker, "_call_llm_step", side_effect=outputs):
        if entrypoint == "investigate":
            _, trajectory, _ = worker.investigate("Investigate an alert")
        else:
            trajectory = worker.query("Investigate an alert")["trajectory"]
    assert env.get_state_snapshot() == before
    assert trajectory[0]["attempted_tool"] == "isolate_host"
    assert trajectory[0]["execution_status"] == "DENIED"
    assert trajectory[0]["tool"] is None
    assert trajectory[1]["tool"] == "get_ip_address_report"
    verification = verify_agent_trajectory(trajectory, expected_actions=["isolate_host"])
    assert verification.executed_actions == []
    assert verification.epistemic_step_count == 1
    assert not verification.operator_actions_matched

    from scripts.eval_cost_engine import DecisionOutcome, classify_decision_outcome
    from agent.gepa_runbook_optimizer import calculate_loss_penalty

    assert classify_decision_outcome(
        ground_truth_threat=False,
        executed_actions=verification.executed_actions,
    ) == DecisionOutcome.TRUE_NEGATIVE
    assert classify_decision_outcome(
        ground_truth_threat=True,
        executed_actions=verification.executed_actions,
    ) == DecisionOutcome.FALSE_NEGATIVE
    assert calculate_loss_penalty(
        expected_label="BENIGN", actual_verdict="BENIGN",
        executed_actions=verification.executed_actions, prohibited_actions=["isolate_host"],
    ) == 1.0


def test_inherited_worker_execute_tool_alias_enforces_permissions_and_allows_investigation():
    env = MagicMock()
    env.query_tool.return_value = {"status": "SUCCESS", "reputation": "UNKNOWN"}
    worker = SOCRunbookWorkerAgent(
        classification="C2_BEACON", runbook_name="basic_ioc_enrichment.md",
        runbook_content="# Investigate evidence", managed_model="offline-model",
        environment=env,
    )
    denied = json.loads(worker._execute_tool("isolate_host", {"hostname": "test-host"}))
    assert denied["status"] == "DENIED"
    env.execute_action.assert_not_called()
    env.query_tool.assert_not_called()

    args = {"ip": "198.51.100.42"}
    allowed = json.loads(worker._execute_tool("get_ip_address_report", args))
    assert allowed["status"] == "SUCCESS"
    env.query_tool.assert_called_once_with("get_ip_address_report", args)
    env.execute_action.assert_not_called()


def test_worker_investigation_react_loop_and_report():
    """Verify worker executes investigation tools and produces WorkerInvestigationReport."""
    env = SocEnvironment()
    runbook_text = load_runbook("basic_ioc_enrichment.md", DEFAULT_RUNBOOKS_DIR)
    worker = SOCRunbookWorkerAgent(
        classification="C2_BEACON",
        runbook_name="basic_ioc_enrichment.md",
        runbook_content=runbook_text,
        environment=env,
    )

    worker_step_outputs = [
        (
            'Thought: The alert indicates outbound traffic to 198.51.100.42. I must enrich this IP.\n'
            'Action: get_ip_address_report(ip="198.51.100.42")',
            {"prompt_tokens": 100, "completion_tokens": 30, "total_tokens": 130},
        ),
        (
            'Thought: The IP is confirmed active C2 infrastructure. I will compile findings.\n'
            'Final Answer:\n'
            '[Context & Enrichment]\n'
            '- IP: 198.51.100.42 (Known C2 Endpoint under AS64496)\n\n'
            '[Findings & Evidence]\n'
            '- Confirmed C2 beaconing node targeting internal endpoints.\n\n'
            '[Preliminary Risk Assessment]\n'
            'MALICIOUS\n\n'
            '```worker_report\n'
            '{\n'
            '  "classification": "C2_BEACON",\n'
            '  "target_entities": ["198.51.100.42"],\n'
            '  "findings": {"198.51.100.42": "Known C2 Endpoint under AS64496"},\n'
            '  "evidence": ["Reputation: MALICIOUS", "Threat: Known C2 Endpoint"],\n'
            '  "risk_level": "MALICIOUS",\n'
            '  "recommended_escalation": "Tier 2 Responder"\n'
            '}\n'
            '```',
            {"prompt_tokens": 150, "completion_tokens": 80, "total_tokens": 230},
        ),
    ]

    with patch.object(worker, "_call_llm_step", side_effect=worker_step_outputs):
        report, trajectory, usage = worker.investigate(prompt="Investigate IP 198.51.100.42")

    assert len(trajectory) == 1
    assert trajectory[0]["tool"] == "get_ip_address_report"
    assert trajectory[0]["args"]["ip"] == "198.51.100.42"
    assert trajectory[0]["agent"] == "worker"
    assert "MALICIOUS" in trajectory[0]["observation"]

    assert report.classification == "C2_BEACON"
    assert report.risk_level == "MALICIOUS"
    assert "198.51.100.42" in report.target_entities
    assert report.recommended_escalation == "Tier 2 Responder"
    assert usage["total_tokens"] == 360


def test_worker_report_fallback_extraction():
    """Verify extract_worker_report successfully parses unformatted text without JSON blocks."""
    mock_trajectory = [
        {
            "iteration": 1,
            "tool": "get_ip_address_report",
            "args": {"ip": "198.51.100.42"},
            "observation": '{"ip": "198.51.100.42", "reputation": "MALICIOUS", "category": "Known C2 Endpoint"}',
        }
    ]
    raw_text = (
        "[Context & Enrichment]\n"
        "Queried IP 198.51.100.42.\n\n"
        "[Findings & Evidence]\n"
        "Confirmed C2 infrastructure.\n\n"
        "[Preliminary Risk Assessment]\n"
        "MALICIOUS"
    )

    report = extract_worker_report(
        response_text=raw_text,
        classification="C2_BEACON",
        runbook_name="basic_ioc_enrichment.md",
        trajectory=mock_trajectory,
    )

    assert report.classification == "C2_BEACON"
    assert report.risk_level == "MALICIOUS"
    assert "198.51.100.42" in report.target_entities
    assert len(report.evidence) > 0


def test_supervisor_synthesis_and_unified_trajectory():
    """Verify supervisor coordinates worker, executes containment, and builds unified trajectory."""
    env = SocEnvironment()
    supervisor = HierarchicalSOCTier1Agent(environment=env)

    # Sequence of responses:
    # 1. Worker calls get_ip_address_report
    # 2. Worker produces investigation report
    # 3. Supervisor synthesizes and decides containment
    llm_responses = [
        (
            'Thought: Investigate external IP.\nAction: get_ip_address_report(ip="198.51.100.42")',
            {"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70},
        ),
        (
            'Final Answer:\n[Context & Enrichment]\n198.51.100.42 is MALICIOUS C2.\n\n'
            '[Findings & Evidence]\nActive beaconing.\n\n[Preliminary Risk Assessment]\nMALICIOUS\n\n'
            '```worker_report\n'
            '{\n'
            '  "classification": "C2_BEACON",\n'
            '  "target_entities": ["198.51.100.42", "DESKTOP-FIN-08"],\n'
            '  "findings": {"198.51.100.42": "MALICIOUS C2"},\n'
            '  "evidence": ["Reputation: MALICIOUS"],\n'
            '  "risk_level": "MALICIOUS"\n'
            '}\n'
            '```',
            {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        ),
        (
            '[Context & Enrichment]\n'
            '- External C2: 198.51.100.42\n'
            '- Compromised Endpoint: DESKTOP-FIN-08\n\n'
            '[Analysis & Verdict]\n'
            '- Verdict: MALICIOUS\n'
            '- Rationale: Host DESKTOP-FIN-08 communicating with confirmed C2.\n\n'
            '[Action & Escalation]\n'
            '- Containment: Isolate host DESKTOP-FIN-08 and block indicator 198.51.100.42.\n'
            '- Documentation: Update case comment.\n\n'
            '[SOAR Documentation]\n'
            'Host DESKTOP-FIN-08 isolated; perimeter block applied to 198.51.100.42.\n\n'
            '```soc_decision\n'
            '{\n'
            '  "verdict": "MALICIOUS",\n'
            '  "recommended_actions": ["isolate_host", "block_indicator", "update_case_comment"],\n'
            '  "target_entity": "DESKTOP-FIN-08",\n'
            '  "rationale": "Active C2 beaconing to 198.51.100.42"\n'
            '}\n'
            '```',
            {"prompt_tokens": 120, "completion_tokens": 60, "total_tokens": 180},
        ),
    ]

    prompt = (
        "Triage alert: Host DESKTOP-FIN-08 connecting repeatedly to C2 IP 198.51.100.42. "
        "Investigate indicators, verify threat, and execute containment."
    )

    with patch.object(supervisor, "_call_llm_step", side_effect=llm_responses):
        res = supervisor.query(prompt=prompt)

    # 1. Verify SOCTier1Response properties
    assert isinstance(res, SOCTier1Response)
    assert isinstance(res, dict)
    assert res.classification == "C2_BEACON"
    assert res.runbook == "basic_ioc_enrichment.md"
    assert res.worker_report is not None

    # 2. Verify Unified Trajectory
    trajectory = res.trajectory
    assert len(trajectory) == 4  # 1 worker epistemic step + 3 supervisor containment steps

    # Step 1: Worker epistemic tool
    assert trajectory[0]["iteration"] == 1
    assert trajectory[0]["tool"] == "get_ip_address_report"
    assert trajectory[0]["agent"] == "worker"

    # Step 2: Supervisor isolate_host
    assert trajectory[1]["iteration"] == 2
    assert trajectory[1]["tool"] == "isolate_host"
    assert trajectory[1]["agent"] == "supervisor"
    assert trajectory[1]["args"]["hostname"] == "DESKTOP-FIN-08"

    # Step 3: Supervisor block_indicator
    assert trajectory[2]["iteration"] == 3
    assert trajectory[2]["tool"] == "block_indicator"
    assert trajectory[2]["agent"] == "supervisor"
    assert trajectory[2]["args"]["indicator"] == "198.51.100.42"

    # Step 4: Supervisor update_case_comment
    assert trajectory[3]["iteration"] == 4
    assert trajectory[3]["tool"] == "update_case_comment"
    assert trajectory[3]["agent"] == "supervisor"

    # 3. Verify Environment State Interventions
    assert env.hosts["DESKTOP-FIN-08"].isolated is True
    assert "198.51.100.42" in env.blocked_indicators

    # 4. Verify Decision Extraction
    decision = extract_soc_decision(res.response)
    assert decision is not None
    assert decision.verdict == "MALICIOUS"
    assert "isolate_host" in decision.recommended_actions
    assert "block_indicator" in decision.recommended_actions


def test_trajectory_verifier_compliance():
    """Verify unified trajectory conforms to Trajectory Verifier requirements."""
    env = SocEnvironment()
    supervisor = HierarchicalSOCTier1Agent(environment=env)

    llm_responses = [
        (
            'Thought: Enrich domain.\nAction: get_domain_report(domain="update-service-win32.com")',
            {"prompt_tokens": 40, "completion_tokens": 15, "total_tokens": 55},
        ),
        (
            'Final Answer:\n[Context & Enrichment]\nupdate-service-win32.com is MALICIOUS.\n\n'
            '[Findings & Evidence]\nLokibot info-stealer.\n\n[Preliminary Risk Assessment]\nMALICIOUS\n\n'
            '```worker_report\n'
            '{\n'
            '  "classification": "C2_BEACON",\n'
            '  "target_entities": ["update-service-win32.com", "DESKTOP-FIN-08"],\n'
            '  "findings": {"update-service-win32.com": "Lokibot C2"},\n'
            '  "evidence": ["Trojan.Lokibot.Generic"],\n'
            '  "risk_level": "MALICIOUS"\n'
            '}\n'
            '```',
            {"prompt_tokens": 80, "completion_tokens": 40, "total_tokens": 120},
        ),
        (
            '[Context & Enrichment]\nEnriched update-service-win32.com.\n\n'
            '[Analysis & Verdict]\nMALICIOUS Lokibot C2.\n\n'
            '[Action & Escalation]\nIsolate DESKTOP-FIN-08.\n\n'
            '[SOAR Documentation]\nDocumented.\n\n'
            '```soc_decision\n'
            '{\n'
            '  "verdict": "MALICIOUS",\n'
            '  "recommended_actions": ["isolate_host", "update_case_comment"],\n'
            '  "target_entity": "DESKTOP-FIN-08",\n'
            '  "rationale": "Lokibot C2 communication"\n'
            '}\n'
            '```',
            {"prompt_tokens": 90, "completion_tokens": 45, "total_tokens": 135},
        ),
    ]

    prompt = (
        "Triage alert for host DESKTOP-FIN-08 connecting repeatedly to update-service-win32.com. "
        "Query threat intelligence, determine threat verdict, and execute host containment actions."
    )

    with patch.object(supervisor, "_call_llm_step", side_effect=llm_responses):
        res = supervisor.query(prompt=prompt)

    # Verify trajectory with Trajectory Verifier
    verif = verify_agent_trajectory(
        trajectory=res.trajectory,
        expected_actions=["isolate_host", "update_case_comment"],
        prohibited_actions=["close_case"],
        expected_entities=["DESKTOP-FIN-08", "update-service-win32.com"],
        response_text=res.response,
    )

    assert verif.actions_matched is True
    assert verif.prohibited_actions_avoided is True
    assert verif.epistemic_step_count >= 1
    assert verif.pragmatic_action_count >= 1
    assert not verif.loop_detected


def test_benign_safe_resolution_flow():
    """Verify supervisor closes case and avoids prohibited containment on benign alert."""
    env = SocEnvironment()
    supervisor = HierarchicalSOCTier1Agent(environment=env)

    llm_responses = [
        (
            'Thought: Enrich documentation IP.\nAction: get_ip_address_report(ip="192.0.2.100")',
            {"prompt_tokens": 30, "completion_tokens": 10, "total_tokens": 40},
        ),
        (
            'Final Answer:\n[Context & Enrichment]\n192.0.2.100 is RFC-5737 test IP.\n\n'
            '[Findings & Evidence]\nNon-routable documentation network.\n\n[Preliminary Risk Assessment]\nBENIGN\n\n'
            '```worker_report\n'
            '{\n'
            '  "classification": "C2_BEACON",\n'
            '  "target_entities": ["192.0.2.100"],\n'
            '  "findings": {"192.0.2.100": "RFC-5737 documentation subnet"},\n'
            '  "evidence": ["Reputation: SAFE", "Non-routable"],\n'
            '  "risk_level": "BENIGN"\n'
            '}\n'
            '```',
            {"prompt_tokens": 60, "completion_tokens": 30, "total_tokens": 90},
        ),
        (
            '[Context & Enrichment]\n192.0.2.100 is non-routable.\n\n'
            '[Analysis & Verdict]\nBENIGN documentation artifact.\n\n'
            '[Action & Escalation]\nClose case as benign false positive.\n\n'
            '[SOAR Documentation]\nCase closed.\n\n'
            '```soc_decision\n'
            '{\n'
            '  "verdict": "BENIGN",\n'
            '  "recommended_actions": ["close_case", "update_case_comment"],\n'
            '  "target_entity": "192.0.2.100",\n'
            '  "rationale": "RFC-5737 documentation subnet"\n'
            '}\n'
            '```',
            {"prompt_tokens": 70, "completion_tokens": 35, "total_tokens": 105},
        ),
    ]

    prompt = (
        "Triage authentication log alert: connection attempts recorded from IP 192.0.2.100 against gateway GW-CORE-VPN-01. "
        "Query threat intelligence, verify routing classification, and resolve alert."
    )

    with patch.object(supervisor, "_call_llm_step", side_effect=llm_responses):
        res = supervisor.query(prompt=prompt)

    verif = verify_agent_trajectory(
        trajectory=res.trajectory,
        expected_actions=["close_case"],
        prohibited_actions=["isolate_host", "block_indicator"],
        expected_entities=["192.0.2.100"],
        response_text=res.response,
    )

    assert verif.actions_matched is True
    assert verif.prohibited_actions_avoided is True
    # Verify close_case was executed
    assert any(step["tool"] == "close_case" for step in res.trajectory)
    # Verify isolate_host and block_indicator were not executed
    assert not any(step["tool"] in ("isolate_host", "block_indicator") for step in res.trajectory)


def test_eval_soc_agent_cli_agent_mode_parameter():
    """Verify scripts/eval_soc_agent.py parses --agent-mode and instantiates HierarchicalSOCTier1Agent."""
    import argparse
    from scripts.eval_soc_agent import run_evaluation

    # Test parser configuration
    import subprocess
    cmd = [".venv/bin/python3", "scripts/eval_soc_agent.py", "--help"]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True)
    assert "--agent-mode {single,hierarchical}" in out.stdout

    # Test run_evaluation routing
    from scripts.eval_soc_agent import SemanticJudgeResult
    with patch("scripts.eval_soc_agent.HierarchicalSOCTier1Agent") as mock_hierarchical_cls, \
         patch("scripts.eval_soc_agent.SocTier1Agent") as mock_single_cls, \
         patch("scripts.eval_soc_agent.judge_response_with_llm") as mock_judge:

        mock_judge.return_value = SemanticJudgeResult(
            rubric_score=90.0,
            passed=True,
            grounding_score=1.0,
            critique="Compliant test response.",
        )

        mock_h_agent = MagicMock()
        mock_h_agent.query.return_value = {
            "response": "[Analysis & Verdict]\nBENIGN\n```soc_decision\n{\"verdict\": \"BENIGN\"}\n```",
            "trajectory": [{"tool": "get_ip_report"}, {"tool": "close_case"}],
            "usage": {"total_tokens": 100},
        }
        mock_hierarchical_cls.return_value = mock_h_agent

        mock_s_agent = MagicMock()
        mock_s_agent.query.return_value = {
            "response": "[Analysis & Verdict]\nBENIGN\n```soc_decision\n{\"verdict\": \"BENIGN\"}\n```",
            "trajectory": [{"tool": "get_ip_report"}],
            "usage": {"total_tokens": 50},
        }
        mock_single_cls.return_value = mock_s_agent

        evalset_file = ROOT_DIR / "configs" / "evals" / "gen1" / "soc_tier1_triage.json"
        if not evalset_file.exists():
            evalset_file = ROOT_DIR / "configs" / "evals" / "soc_tier1_evalset.json"

        # Mode 1: hierarchical
        res_h = run_evaluation(
            evalset_path=evalset_file,
            flavor="test-model",
            gen=1,
            agent_mode="hierarchical",
        )
        mock_hierarchical_cls.assert_called_once()
        assert res_h["agent_mode"] == "hierarchical"

        # Mode 2: single
        res_s = run_evaluation(
            evalset_path=evalset_file,
            flavor="test-model",
            gen=1,
            agent_mode="single",
        )
        mock_single_cls.assert_called_once()
        assert res_s["agent_mode"] == "single"


def test_hierarchical_agent_with_runbooks_disabled():
    """Verify HierarchicalSOCTier1Agent functions when runbooks are disabled (generic multi-agent control)."""
    agent = HierarchicalSOCTier1Agent(use_runbooks=False)
    assert agent.use_runbooks is False

    mock_llm_responses = [
        # Worker step 1
        'Action: get_ip_address_report(ip="198.51.100.42")',
        # Worker step 2 (concludes with worker_report)
        'Final Answer:\n[Context & Enrichment]\nQueried 198.51.100.42\n\n[Findings & Evidence]\nMalicious C2 node.\n\n[Preliminary Risk Assessment]\nMALICIOUS\n\n```worker_report\n{"classification": "C2_BEACON", "target_entities": ["198.51.100.42"], "risk_level": "MALICIOUS"}\n```',
        # Supervisor step
        '[Context & Enrichment]\nConfirmed C2\n\n[Analysis & Verdict]\nMALICIOUS\n\n[Action & Escalation]\nisolate_host\n\n[SOAR Documentation]\nIsolated host.\n\n```soc_decision\n{"verdict": "MALICIOUS", "recommended_actions": ["isolate_host"], "target_entity": "DESKTOP-FIN-08", "rationale": "Confirmed C2"}\n```',
    ]
    call_idx = 0

    def mock_caller(prompt, max_tokens=None, temperature=0.2):
        nonlocal call_idx
        res = mock_llm_responses[call_idx]
        call_idx += 1
        return res, {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}

    agent._call_llm_step = mock_caller
    res = agent.query("Host DESKTOP-FIN-08 communicating with C2 server 198.51.100.42")
    assert res.runbook == "none"
    assert res.worker_report["runbook_name"] == "none"
    assert len(res.trajectory) >= 2


def test_load_runbook_with_in_memory_dict():
    """Verify load_runbook returns custom content when runbooks_dict is provided."""
    custom_dict = {
        "malware_triage.md": "# Custom In-Memory Malware Triage Runbook\nCustom instructions.",
        "basic_ioc_enrichment.md": "# Custom IOC Enrichment Runbook\nEnrichment steps.",
    }

    # Found in dict
    content = load_runbook("malware_triage.md", runbooks_dict=custom_dict)
    assert content == "# Custom In-Memory Malware Triage Runbook\nCustom instructions."

    # Not found in dict, falls back to default directory
    content_default = load_runbook("suspicious_login_triage.md", runbooks_dict=custom_dict)
    assert "Suspicious Login" in content_default or "Fallback Runbook" in content_default


def test_load_runbook_with_custom_dir(tmp_path: Path):
    """Verify load_runbook returns content from temporary custom directory."""
    custom_dir = tmp_path / "custom_runbooks"
    custom_dir.mkdir(parents=True, exist_ok=True)
    custom_file = custom_dir / "malware_triage.md"
    custom_file.write_text("# Temp Dir Malware Runbook\nStep 1: Check hash.", encoding="utf-8")

    # Found in custom directory
    content = load_runbook("malware_triage.md", runbooks_dir=custom_dir)
    assert content == "# Temp Dir Malware Runbook\nStep 1: Check hash."

    # String path also accepted
    content_str = load_runbook("malware_triage.md", runbooks_dir=str(custom_dir))
    assert content_str == "# Temp Dir Malware Runbook\nStep 1: Check hash."


def test_hierarchical_agent_with_runbooks_dict():
    """Verify HierarchicalSOCTier1Agent initialized with runbooks_dict passes custom runbook to worker."""
    custom_runbook_content = (
        "# Custom EVOLVED Malware Runbook\n"
        "## Steps\n"
        "1. Check file hash with `get_file_report`.\n"
    )
    custom_dict = {
        "malware_triage.md": custom_runbook_content,
    }

    agent = HierarchicalSOCTier1Agent(runbooks_dict=custom_dict)
    assert agent.runbooks_dict == custom_dict

    worker_runbook_seen = None

    def mock_caller(prompt, max_tokens=None, temperature=0.2):
        nonlocal worker_runbook_seen
        # Capture the worker agent system instruction or caller prompt
        return (
            '[Context & Enrichment]\nHash checked\n\n[Findings & Evidence]\nMalicious file\n\n[Preliminary Risk Assessment]\nMALICIOUS\n\n```worker_report\n{"classification": "MALWARE_HASH", "target_entities": ["e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"], "risk_level": "MALICIOUS"}\n```',
            {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
        )

    agent._call_llm_step = mock_caller

    with patch("agent.hierarchical_soc_agent.SOCRunbookWorkerAgent") as mock_worker_cls:
        mock_worker_instance = MagicMock()
        mock_worker_cls.return_value = mock_worker_instance
        mock_worker_instance.investigate.return_value = (
            WorkerInvestigationReport(
                classification="MALWARE_HASH",
                runbook_name="malware_triage.md",
                target_entities=["e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"],
                risk_level="MALICIOUS",
            ),
            [],
            {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
        )

        agent.query("Suspicious file hash e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 detected on workstation")

        mock_worker_cls.assert_called_once()
        _, kwargs = mock_worker_cls.call_args
        assert kwargs["runbook_name"] == "malware_triage.md"
        assert "Custom EVOLVED Malware Runbook" in kwargs["runbook_content"]
