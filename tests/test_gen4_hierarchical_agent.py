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


@pytest.mark.parametrize("domain,expected", [("google.com", "BENIGN"), ("evil.com", "MALICIOUS")])
def test_exhausted_worker_and_empty_synthesis_use_actual_domain_verdict(domain, expected):
    env = SocEnvironment()
    supervisor = HierarchicalSOCTier1Agent(
        project_id="offline", managed_model="offline", environment=env, use_runbooks=False,
    )
    with patch.object(supervisor, "_call_llm_step", side_effect=[
        (f'Action: get_domain_report(domain="{domain}")', {}), ("", {}),
    ]):
        result = supervisor.query(f"Investigate {domain} on DESKTOP-FIN-08", max_iterations=1)
    assert result.worker_report["risk_level"] == expected
    assert result.verdict == expected
    actions = verify_agent_trajectory(result.trajectory).executed_actions
    if expected == "BENIGN":
        assert env.action_history == []
        assert actions == []
    else:
        assert "isolate_host" in actions
        assert "block_indicator" in actions


@pytest.mark.parametrize("observations,expected", [
    ([{"verdict": "BENIGN", "malicious_votes": 0, "notes": "PSEXEC TROJAN MALICIOUS"}], "BENIGN"),
    ([{"reputation": "SUSPICIOUS", "notes": "BENIGN"}], "SUSPICIOUS"),
    ([{"verdict": "NOT MALICIOUS", "malicious_votes": 0}], "UNKNOWN"),
    ([{"malicious_votes": 0, "harmless_votes": 100}], "UNKNOWN"),
    ([{"verdict": "BENIGN"}, {"status": "ERROR", "verdict": "MALICIOUS"}], "BENIGN"),
    ([{"verdict": "BENIGN"}, {"status_code": 503, "error": "MALICIOUS lookup failed"}], "BENIGN"),
    ([{"result": {"reputation": " benign "}}], "BENIGN"),
    ([{"verdict": "BENIGN"}, {"verdict": "MALICIOUS"}], "MALICIOUS"),
    ([{"verdict": "BENIGN"}, {"verdict": "SUSPICIOUS"}], "SUSPICIOUS"),
    ([{"verdict": "POTENTIALLY_MALICIOUS"}], "SUSPICIOUS"),
    ([{"reputation": "BENIGN_AUTHORIZED"}], "BENIGN"),
    ([{"verdict": "SAFE"}], "BENIGN"),
    ([{"reputation": "BENIGN / NON-ROUTABLE"}], "BENIGN"),
    ([{"verdict": "NEUTRAL", "reputation": "UNKNOWN"}], "UNKNOWN"),
    ([{"events": [{"verdict": "MALICIOUS"}], "process": "PSEXEC"}], "UNKNOWN"),
    ([{"result": [{"verdict": "BENIGN"}, {"isError": True, "verdict": "MALICIOUS"}]}], "BENIGN"),
    ([{"error": "failed", "data": {"verdict": "MALICIOUS"}}], "UNKNOWN"),
    ([{"content": [{"text": '{"reputation":"BENIGN"}'}]}], "BENIGN"),
])
def test_fallback_risk_uses_explicit_values_from_successful_observations(observations, expected):
    trajectory = [{"tool": "get_domain_report", "args": {"domain": "google.com"},
                   "observation": json.dumps(value)} for value in observations]
    report = extract_worker_report("Investigation iterations completed.", "C2_BEACON", "none", trajectory)
    assert report.risk_level == expected


def test_denied_attempt_cannot_supply_fallback_risk():
    trajectory = [{"tool": None, "attempted_tool": "get_domain_report", "execution_status": "DENIED",
                   "observation": '{"verdict":"MALICIOUS"}'}]
    report = extract_worker_report("Iterations completed.", "C2_BEACON", "none", trajectory)
    assert report.risk_level == "UNKNOWN"


@pytest.mark.parametrize("output", [
    "Unable to investigate", "Final Answer: MALICIOUS", "",
    'Action: isolate_host(hostname="DESKTOP-FIN-08")',
    'Action: get_domain_report(domain="evil.com")',
])
@pytest.mark.parametrize("budget", [0, 1, 3])
def test_query_without_investigation_evidence_cannot_contain(output, budget):
    env = SocEnvironment()
    env.inject_fault("get_domain_report", status_code=503, error="outage")
    supervisor = HierarchicalSOCTier1Agent(project_id="offline", managed_model="offline", environment=env, use_runbooks=False)
    decision = SocDecision(verdict="MALICIOUS", recommended_actions=["isolate_host"], target_entity="DESKTOP-FIN-08")
    with patch.object(supervisor, "classify_alert", return_value="C2_BEACON"), \
         patch.object(supervisor, "_call_llm_step", return_value=(output, {})), \
         patch.object(supervisor, "_synthesize_verdict_and_containment", return_value=("MALICIOUS", decision, {})) as synthesize:
        result = supervisor.query("Investigate DESKTOP-FIN-08", max_iterations=budget)
    synthesize.assert_not_called()
    assert env.action_history == []
    assert verify_agent_trajectory(result.trajectory).executed_actions == []
    assert result.verdict == "INCONCLUSIVE"
    assert result.worker_report["evidence"] == []
    assert "incomplete" in result.response.lower()


def test_worker_retries_plain_text_until_real_investigation():
    supervisor = HierarchicalSOCTier1Agent(project_id="offline", managed_model="offline", environment=SocEnvironment(), use_runbooks=False)
    outputs = [("Unable to investigate", {}), ("Final Answer: MALICIOUS", {}),
               ('Action: get_domain_report(domain="evil.com")', {}),
               ('Final Answer: investigated evil.com', {}),
               ('```soc_decision\n{"verdict":"MALICIOUS","recommended_actions":["isolate_host"],"target_entity":"DESKTOP-FIN-08"}\n```', {})]
    with patch.object(supervisor, "classify_alert", return_value="C2_BEACON"), \
         patch.object(supervisor, "_call_llm_step", side_effect=outputs):
        result = supervisor.query("Investigate DESKTOP-FIN-08", max_iterations=4)
    assert verify_agent_trajectory(result.trajectory).executed_actions == ["isolate_host"]
    assert result.trajectory[0]["tool"] == "get_domain_report"


@pytest.mark.parametrize("observation,verified", [
    ({"verdict": "MALICIOUS"}, True),
    ({"cases": [], "total": 0}, True),
    ({"entity": "host", "status": "OPEN"}, True),
    ({"status": "SUCCESS"}, False),
    ({"error": {}}, False),
    ({"status_code": 503, "detail": "outage"}, False),
    ({"isError": True, "content": [{"text": "failed"}]}, False),
    ({"status": "NOT_FOUND", "entity": "host"}, False),
    ({"result": {"status": "ERROR", "message": "failed"}}, False),
    ({"content": []}, False), ({"result": {}}, False), ({"data": None}, False),
    ({"events": [{"status": "FAILED", "event_type": "USER_LOGIN"}]}, True),
    ({}, False), (None, False), ("unverified prose", False),
])
def test_supervisor_requires_usable_tool_observation(observation, verified):
    env = SocEnvironment()
    supervisor = HierarchicalSOCTier1Agent(project_id="offline", managed_model="offline", environment=env, use_runbooks=False)
    decision = SocDecision(verdict="MALICIOUS", recommended_actions=["isolate_host"], target_entity="DESKTOP-FIN-08")
    with patch.object(supervisor, "classify_alert", return_value="C2_BEACON"), \
         patch.object(supervisor, "_call_llm_step", return_value=('Action: get_domain_report(domain="evil.com")', {})), \
         patch.object(env, "query_tool", return_value=observation), \
         patch.object(supervisor, "_synthesize_verdict_and_containment", return_value=("MALICIOUS", decision, {})) as synthesize:
        result = supervisor.query("Investigate DESKTOP-FIN-08", max_iterations=1)
    assert bool(synthesize.call_count) is verified
    assert bool(env.action_history) is verified
    assert result.verdict == ("MALICIOUS" if verified else "INCONCLUSIVE")


def test_retry_does_not_reuse_report_written_before_tool_evidence():
    worker = SOCRunbookWorkerAgent(
        classification="C2_BEACON", runbook_name="none", runbook_content="",
        project_id="offline", managed_model="offline", environment=SocEnvironment(),
    )
    premature = 'Final Answer: ```worker_report\n{"classification":"C2_BEACON","risk_level":"MALICIOUS","evidence":["fabricated evidence"]}\n```'
    with patch.object(worker, "_call_llm_step", side_effect=[
        (premature, {}), ('Action: get_domain_report(domain="google.com")', {}),
    ]):
        report, trajectory, _ = worker.investigate("Investigate google.com", max_iterations=2)
    assert len(trajectory) == 1
    assert "fabricated evidence" not in report.evidence
    assert premature not in report.raw_response
    assert report.findings


def _containment_report(entities=()):
    return WorkerInvestigationReport(
        classification="C2_BEACON", runbook_name="basic_ioc_enrichment.md",
        target_entities=list(entities),
    )


def _assert_no_containment_credit(steps, action):
    from scripts.eval_cost_engine import DecisionOutcome, classify_decision_outcome
    verification = verify_agent_trajectory(steps, expected_actions=[action])
    assert verification.executed_actions == []
    assert not verification.operator_actions_matched
    assert classify_decision_outcome(
        ground_truth_threat=True, executed_actions=verification.executed_actions,
    ) == DecisionOutcome.FALSE_NEGATIVE


@pytest.mark.parametrize("use_live_mcp", [False, True])
@pytest.mark.parametrize("action", [
    "isolate_host", "unblock_host", "block_indicator", "close_case", "update_case_comment",
])
def test_supervisor_without_backend_never_claims_execution(use_live_mcp, action):
    supervisor = HierarchicalSOCTier1Agent(managed_model="offline", use_live_mcp=use_live_mcp)
    decision = SocDecision(verdict="MALICIOUS", recommended_actions=[action])
    report = _containment_report(["DESKTOP-FIN-08", "198.51.100.42", "CASE-33279"])
    steps = supervisor._execute_containment_decisions(decision, report, "Investigate alert")
    assert len(steps) == 1
    assert steps[0]["tool"] is None
    assert steps[0]["attempted_tool"] == action
    assert steps[0]["execution_status"] == "NOT_EXECUTED"
    assert "backend" in steps[0]["reason"].lower()
    assert json.loads(steps[0]["observation"])["status"] == "NOT_EXECUTED"
    _assert_no_containment_credit(steps, action)


@pytest.mark.parametrize("action", ["isolate_host", "unblock_host", "close_case", "update_case_comment", "block_indicator"])
def test_supervisor_missing_targets_never_mutates_inventory(action):
    env = SocEnvironment()
    before = env.get_state_snapshot()
    supervisor = HierarchicalSOCTier1Agent(managed_model="offline", environment=env)
    steps = supervisor._execute_containment_decisions(
        SocDecision(verdict="MALICIOUS", recommended_actions=[action]),
        _containment_report(), "Investigate an alert without identified entities",
    )
    assert env.get_state_snapshot() == before
    assert env.action_history == []
    assert len(steps) == 1
    assert steps[0]["execution_status"] == "NOT_EXECUTED"
    assert "target" in steps[0]["reason"].lower()
    _assert_no_containment_credit(steps, action)


@pytest.mark.parametrize("action,target,entities,prompt", [
    ("isolate_host", "DESKTOP-FIN-08", ["GW-CORE-VPN-01"], "Investigate alert"),
    ("isolate_host", None, [], "Compare DESKTOP-FIN-08 and GW-CORE-VPN-01"),
    ("close_case", "CASE-33279", ["CASE-17305"], "Investigate alert"),
    ("update_case_comment", None, [], "Compare CASE-33279 with CASE-17305"),
    ("isolate_host", "CASE-33279", ["update-service-win32.com"], "Investigate alert"),
    ("isolate_host", "SRV-WEB.example.com", [], "Investigate SRV-WEB.example.com"),
    ("block_indicator", "CASE-33279", [], "Investigate case"),
    ("block_indicator", "198.51.100.42", ["192.0.2.100"], "Investigate alert"),
    ("block_indicator", "999.1.1.1", [], "Investigate alert"),
])
def test_supervisor_rejects_ambiguous_or_wrong_type_targets(action, target, entities, prompt):
    env = SocEnvironment()
    supervisor = HierarchicalSOCTier1Agent(managed_model="offline", environment=env)
    steps = supervisor._execute_containment_decisions(
        SocDecision(verdict="MALICIOUS", recommended_actions=[action], target_entity=target),
        _containment_report(entities), prompt,
    )
    assert env.action_history == []
    assert len(steps) == 1
    assert steps[0]["execution_status"] == "NOT_EXECUTED"
    _assert_no_containment_credit(steps, action)


@pytest.mark.parametrize("action,target,arg_key", [
    ("isolate_host", "DESKTOP-FIN-08", "hostname"),
    ("unblock_host", "DESKTOP-FIN-08", "hostname"),
    ("close_case", "CASE-33279", "case_id"),
    ("update_case_comment", "CASE-33279", "case_id"),
    ("block_indicator", "198.51.100.42", "indicator"),
])
@pytest.mark.parametrize("source", ["decision", "report", "prompt"])
def test_supervisor_executes_only_explicit_successful_targets(action, target, arg_key, source):
    env = SocEnvironment()
    supervisor = HierarchicalSOCTier1Agent(managed_model="offline", environment=env)
    steps = supervisor._execute_containment_decisions(
        SocDecision(verdict="MALICIOUS", recommended_actions=[action],
                    target_entity=target if source == "decision" else None),
        _containment_report([target] if source == "report" else []),
        f"Investigate {target}" if source == "prompt" else "Investigate alert",
    )
    assert steps[0]["tool"] == action
    assert steps[0]["args"][arg_key] == target
    assert json.loads(steps[0]["observation"])["status"] == "SUCCESS"
    assert verify_agent_trajectory(steps).executed_actions == [action]
    assert len(env.action_history) == 1


@pytest.mark.parametrize("result", [
    {"status": "ERROR", "error": "host unavailable"},
    {"status": "FAILED", "reason": "operation failed"},
    {"status": "DENIED", "error": "permission denied"},
    {"status": "SUCCESS", "error": "conflicting backend response"},
    {"message": "request submitted"},
    "backend returned invalid output",
])
def test_supervisor_failed_or_unverified_backend_results_get_no_execution_credit(result):
    env = SocEnvironment()
    supervisor = HierarchicalSOCTier1Agent(managed_model="offline", environment=env)
    with patch.object(env, "execute_action", return_value=result) as execute:
        steps = supervisor._execute_containment_decisions(
            SocDecision(verdict="MALICIOUS", recommended_actions=["isolate_host"], target_entity="DESKTOP-FIN-08"),
            _containment_report(), "Investigate alert",
        )
    execute.assert_called_once_with("isolate_host", {"hostname": "DESKTOP-FIN-08"})
    assert steps[0]["tool"] is None
    assert steps[0]["attempted_tool"] == "isolate_host"
    assert steps[0]["reason"]
    assert steps[0]["observation"] == (json.dumps(result) if isinstance(result, dict) else result)
    _assert_no_containment_credit(steps, "isolate_host")


@pytest.mark.parametrize("action,target", [
    ("isolate_host", "DESKTOP-FIN-08"), ("close_case", "CASE-33279"),
    ("block_indicator", "198.51.100.42"), ("block_indicator", "example.com"),
    ("block_indicator", "a" * 64),
])
def test_supervisor_resolves_sentence_final_targets(action, target):
    supervisor = HierarchicalSOCTier1Agent(managed_model="offline", environment=SocEnvironment())
    steps = supervisor._execute_containment_decisions(
        SocDecision(verdict="MALICIOUS", recommended_actions=[action]),
        _containment_report(), f"Investigate {target}.",
    )
    assert steps[0]["tool"] == action


@pytest.mark.parametrize("action,target", [
    ("isolate_host", "DESKTOP-UNKNOWN"), ("close_case", "CASE-UNKNOWN"),
])
def test_supervisor_preserves_real_sandbox_failures_without_execution_credit(action, target):
    supervisor = HierarchicalSOCTier1Agent(managed_model="offline", environment=SocEnvironment())
    steps = supervisor._execute_containment_decisions(
        SocDecision(verdict="MALICIOUS", recommended_actions=[action], target_entity=target),
        _containment_report(), "Investigate alert",
    )
    assert steps[0]["execution_status"] == "ERROR"
    assert "not found" in json.loads(steps[0]["observation"])["error"]
    _assert_no_containment_credit(steps, action)


def test_supervisor_backend_exception_is_preserved_without_execution_credit():
    env = SocEnvironment()
    supervisor = HierarchicalSOCTier1Agent(managed_model="offline", environment=env)
    with patch.object(env, "execute_action", side_effect=RuntimeError("backend unavailable")):
        steps = supervisor._execute_containment_decisions(
            SocDecision(verdict="MALICIOUS", recommended_actions=["isolate_host"], target_entity="DESKTOP-FIN-08"),
            _containment_report(), "Investigate alert",
        )
    assert steps[0]["execution_status"] == "ERROR"
    assert steps[0]["reason"] == "RuntimeError: backend unavailable"
    _assert_no_containment_credit(steps, "isolate_host")


@pytest.mark.parametrize("use_live_mcp", [False, True])
def test_supervisor_targetless_request_without_backend_is_not_executed(use_live_mcp):
    supervisor = HierarchicalSOCTier1Agent(managed_model="offline", use_live_mcp=use_live_mcp)
    steps = supervisor._execute_containment_decisions(
        SocDecision(verdict="MALICIOUS", recommended_actions=["isolate_host", "close_case"]),
        _containment_report(), "Investigate alert",
    )
    assert len(steps) == 2
    assert all(step["execution_status"] == "NOT_EXECUTED" for step in steps)
    assert verify_agent_trajectory(steps).executed_actions == []


def test_supervisor_shared_host_ip_does_not_select_arbitrary_inventory_entry():
    env = SocEnvironment()
    env.hosts["SRV-PROD-PAYMENT-01"].ip = env.hosts["DESKTOP-FIN-08"].ip
    supervisor = HierarchicalSOCTier1Agent(managed_model="offline", environment=env)
    steps = supervisor._execute_containment_decisions(
        SocDecision(verdict="MALICIOUS", recommended_actions=["isolate_host"],
                    target_entity=env.hosts["DESKTOP-FIN-08"].ip),
        _containment_report(), "Investigate alert",
    )
    assert env.action_history == []
    _assert_no_containment_credit(steps, "isolate_host")


@pytest.mark.parametrize("invalid_ip", ["", "none"])
def test_supervisor_missing_inventory_ip_does_not_create_target(invalid_ip):
    env = SocEnvironment()
    env.hosts["DESKTOP-FIN-08"].ip = invalid_ip
    supervisor = HierarchicalSOCTier1Agent(managed_model="offline", environment=env)
    steps = supervisor._execute_containment_decisions(
        SocDecision(verdict="MALICIOUS", recommended_actions=["isolate_host"]),
        _containment_report(), "Target host: none given.",
    )
    assert env.action_history == []
    _assert_no_containment_credit(steps, "isolate_host")


def test_supervisor_normalizes_repeated_grounded_host_and_action_aliases():
    env = SocEnvironment()
    supervisor = HierarchicalSOCTier1Agent(managed_model="offline", environment=env)
    steps = supervisor._execute_containment_decisions(
        SocDecision(verdict="MALICIOUS", recommended_actions=["isolate_host", "isolate"],
                    target_entity="desktop-fin-08"),
        _containment_report([env.hosts["DESKTOP-FIN-08"].ip]), "Investigate DESKTOP-FIN-08.",
    )
    assert len(steps) == 1
    assert steps[0]["tool"] == "isolate_host"
    assert len(env.action_history) == 1


def test_supervisor_records_unsupported_action_without_dispatching():
    env = SocEnvironment()
    supervisor = HierarchicalSOCTier1Agent(managed_model="offline", environment=env)
    steps = supervisor._execute_containment_decisions(
        SocDecision(verdict="MALICIOUS", recommended_actions=["delete_host"], target_entity="DESKTOP-FIN-08"),
        _containment_report(), "Investigate alert",
    )
    assert env.action_history == []
    assert steps[0]["execution_status"] == "NOT_EXECUTED"
    assert steps[0]["attempted_tool"] == "delete_host"
    assert "Unsupported" in steps[0]["reason"]


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
        "Triage CASE-33279 alert: Host DESKTOP-FIN-08 connecting repeatedly to C2 IP 198.51.100.42. "
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
        "Triage CASE-33279 alert for host DESKTOP-FIN-08 connecting repeatedly to update-service-win32.com. "
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
        "Triage CASE-17305 authentication log alert: connection attempts recorded from IP 192.0.2.100 against gateway GW-CORE-VPN-01. "
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


def test_strip_runbook_scaffolding_and_system_instruction_hygiene():
    """Verify strip_runbook_scaffolding removes Mermaid diagrams, Cline pseudo-tools, and ${VAR} syntax."""
    from agent.hierarchical_soc_agent import (
        strip_runbook_scaffolding,
        translate_runbook_to_system_instruction,
    )

    raw_runbook = (
        "# Basic IOC Enrichment\n\n"
        "```{mermaid}\n"
        "sequenceDiagram\n"
        "    participant User\n"
        "    participant Agent\n"
        "    User->>Agent: Provide ${IOC_VALUE}\n"
        "```\n\n"
        "1. Receive `${IOC_VALUE}` and `${ASSET_ROLE}` from the alert.\n"
        "2. If missing, use `ask_followup_question` to clarify with the user.\n"
        "3. Query `gti-mcp.get_ip_address_report` and `secops-mcp.lookup_entity`.\n"
        "4. Follow [generate_report_file.md](./common_steps/generate_report_file.md) and call `attempt_completion`.\n"
    )
    cleaned = strip_runbook_scaffolding(raw_runbook)
    assert "sequenceDiagram" not in cleaned
    assert "```{mermaid}" not in cleaned
    assert "ask_followup_question" not in cleaned
    assert "attempt_completion" not in cleaned
    assert "generate_report_file.md" not in cleaned
    assert "${IOC_VALUE}" not in cleaned
    assert "<ioc_value>" in cleaned
    assert "<asset_role>" in cleaned

    sys_inst = translate_runbook_to_system_instruction(raw_runbook, "C2_BEACON")
    assert "sequenceDiagram" not in sys_inst
    assert "${IOC_VALUE}" not in sys_inst
    assert "get_ip_address_report" in sys_inst
    assert "lookup_entity" in sys_inst
    assert "gti-mcp." not in sys_inst
    assert "secops-mcp." not in sys_inst

