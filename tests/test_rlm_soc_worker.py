"""Unit tests for DSPy RLM SOC Runbook Worker Agent and GuardedSOCInterpreter."""

from __future__ import annotations

import json
from typing import Any, Dict, List
import dspy
from dspy.primitives.code_interpreter import CodeExecutionError, FinalOutput
import pytest

from agent.hierarchical_soc_agent import SOCSupervisorAgent
from agent.rlm_soc_worker import (
    GuardedSOCInterpreter,
    RLMSOCRunbookWorkerAgent,
    normalize_rlm_entities,
    normalize_rlm_risk_level,
)
from agent.soc_environment import SocEnvironment


class SequencedMockDSPyLM(dspy.BaseLM):
    """Deterministic mock DSPy BaseLM returning pre-programmed RLM responses."""

    def __init__(self, responses: List[Dict[str, str]], model: str = "vertex_ai/gemini-2.5-flash-lite") -> None:
        super().__init__(model=model)
        self._responses = list(responses)
        self._call_idx = 0

    def __call__(self, prompt: Any = None, messages: Any = None, **kwargs: Any) -> List[str]:
        idx = min(self._call_idx, len(self._responses) - 1)
        self._call_idx += 1
        step = self._responses[idx]
        text = f"[[ ## reasoning ## ]]\n{step['reasoning']}\n\n[[ ## code ## ]]\n```python\n{step['code']}\n```"
        self.history.append({
            "prompt": prompt,
            "messages": messages,
            "outputs": [text],
            "usage": {"prompt_tokens": 250, "completion_tokens": 75, "total_tokens": 325},
        })
        return [text]


def test_normalize_rlm_entities_handles_dicts_and_strings() -> None:
    raw = [
        {"entity_id": "DESKTOP-FIN-08", "entity_type": "hostname"},
        {"ip": "185.220.101.45"},
        "update-service-win32.com",
    ]
    cleaned = normalize_rlm_entities(raw, [])
    assert cleaned == ["DESKTOP-FIN-08", "185.220.101.45", "update-service-win32.com"]


def test_normalize_rlm_risk_level_maps_severity_aliases_and_tool_evidence() -> None:
    trajectory = [
        {
            "iteration": 1,
            "tool": "get_domain_report",
            "args": {"domain": "update-service-win32.com"},
            "observation": json.dumps({"domain": "update-service-win32.com", "reputation": "MALICIOUS"}),
            "execution_status": "SUCCESS",
        }
    ]
    assert normalize_rlm_risk_level("HIGH", trajectory) == "MALICIOUS"
    assert normalize_rlm_risk_level("CLEAN", []) == "BENIGN"
    assert normalize_rlm_risk_level("MEDIUM", []) == "SUSPICIOUS"


def test_guarded_soc_interpreter_enforces_epistemic_guards() -> None:
    recorded_trajectory: List[Dict[str, Any]] = []

    def lookup_entity(entity_id: str, entity_type: str = "host") -> Dict[str, Any]:
        obs = {"entity": entity_id, "reputation": "SUSPICIOUS", "ip": "10.10.4.22"}
        recorded_trajectory.append({
            "iteration": len(recorded_trajectory) + 1,
            "tool": "lookup_entity",
            "args": {"entity_id": entity_id, "entity_type": entity_type},
            "observation": json.dumps(obs),
            "execution_status": "SUCCESS",
        })
        return obs

    interp = GuardedSOCInterpreter(
        recorded_trajectory=recorded_trajectory,
        classification="C2_BEACON",
        require_observe_before_submit=True,
        tools={"lookup_entity": lookup_entity},
        output_fields=[
            {"name": "target_entities"},
            {"name": "risk_level"},
            {"name": "findings_summary"},
            {"name": "evidence_items"},
        ],
    )
    try:
        # 1. Zero-tool SUBMIT must raise CodeExecutionError
        with pytest.raises(CodeExecutionError, match="no epistemic investigation tool was called"):
            interp.execute(
                'SUBMIT(target_entities=["DESKTOP-FIN-08"], risk_level="MALICIOUS", '
                'findings_summary="Guessed", evidence_items=["none"])'
            )

        # 2. Calling a tool and SUBMIT in the same step must raise CodeExecutionError (Rule 6)
        with pytest.raises(CodeExecutionError, match="Rule 6"):
            interp.execute(
                'host = lookup_entity(entity_id="DESKTOP-FIN-08")\n'
                'SUBMIT(target_entities=["DESKTOP-FIN-08"], risk_level="SUSPICIOUS", '
                'findings_summary="Same turn", evidence_items=["host"])'
            )
        assert len(recorded_trajectory) == 1

        # 3. Calling SUBMIT on the subsequent step after inspecting output succeeds
        res2 = interp.execute(
            'SUBMIT(target_entities=["DESKTOP-FIN-08"], risk_level="SUSPICIOUS", '
            'findings_summary="Verified after inspection", evidence_items=["10.10.4.22"])'
        )
        assert isinstance(res2, FinalOutput)
        assert res2.output["risk_level"] == "SUSPICIOUS"
    finally:
        interp.shutdown()


def test_rlm_worker_deduplicates_identical_tool_calls_and_bridges_trajectory() -> None:
    env = SocEnvironment()
    mock_lm = SequencedMockDSPyLM([
        {
            "reasoning": "Query host and domain report, plus a duplicate host call to verify deduplication.",
            "code": (
                'h1 = lookup_entity(entity_id="DESKTOP-FIN-08", entity_type="host")\n'
                'h2 = lookup_entity(entity_id="DESKTOP-FIN-08", entity_type="host")\n'
                'dom = get_domain_report(domain="update-service-win32.com")\n'
                'print(h1["ip"], dom["reputation"])'
            ),
        },
        {
            "reasoning": "Submit verified malicious findings.",
            "code": (
                'SUBMIT(\n'
                '    target_entities=["DESKTOP-FIN-08", "update-service-win32.com"],\n'
                '    risk_level="MALICIOUS",\n'
                '    findings_summary="Confirmed Cobalt Strike C2 on update-service-win32.com from DESKTOP-FIN-08.",\n'
                '    evidence_items=["lookup_entity: DESKTOP-FIN-08", "get_domain_report: MALICIOUS"]\n'
                ')'
            ),
        },
    ])

    worker = RLMSOCRunbookWorkerAgent(
        classification="C2_BEACON",
        runbook_name="basic_ioc_enrichment.md",
        runbook_content="Enrich host and domain indicators before concluding.",
        environment=env,
        dspy_lm=mock_lm,
    )
    report, trajectory, usage = worker.investigate(
        "Alert: Outbound C2 beacon from DESKTOP-FIN-08 to update-service-win32.com"
    )

    assert len(trajectory) == 2
    assert [step["tool"] for step in trajectory] == ["lookup_entity", "get_domain_report"]
    assert all(step.get("rlm_repl") is True for step in trajectory)
    assert report.risk_level == "MALICIOUS"
    assert "DESKTOP-FIN-08" in report.target_entities
    assert "update-service-win32.com" in report.target_entities
    assert usage["total_tokens"] == 650


def test_supervisor_with_rlm_worker_executes_end_to_end() -> None:
    env = SocEnvironment()
    mock_lm = SequencedMockDSPyLM([
        {
            "reasoning": "Enrich host, domain, and open cases.",
            "code": (
                'h = lookup_entity(entity_id="DESKTOP-FIN-08", entity_type="host")\n'
                'd = get_domain_report(domain="update-service-win32.com")\n'
                'c = list_cases(query="DESKTOP-FIN-08")\n'
                'print(h, d, c)'
            ),
        },
        {
            "reasoning": "Submit verified findings to supervisor.",
            "code": (
                'SUBMIT(\n'
                '    target_entities=["DESKTOP-FIN-08", "update-service-win32.com", "CASE-33279"],\n'
                '    risk_level="MALICIOUS",\n'
                '    findings_summary="Confirmed active Cobalt Strike C2 beacon on DESKTOP-FIN-08 to update-service-win32.com.",\n'
                '    evidence_items=["update-service-win32.com reputation MALICIOUS", "DESKTOP-FIN-08 IP 10.0.5.23"]\n'
                ')'
            ),
        },
    ])

    supervisor = SOCSupervisorAgent(
        environment=env,
        worker_mode="rlm",
        dspy_lm=mock_lm,
    )

    def _mock_supervisor_llm(prompt: str, max_tokens: Any = None, temperature: float = 0.0) -> Any:
        synth = (
            "[Context & Enrichment]\n"
            "Host DESKTOP-FIN-08 (10.0.5.23) communicated with known C2 update-service-win32.com (CASE-33279).\n\n"
            "[Analysis & Verdict]\n"
            "Confirmed MALICIOUS C2 beacon.\n\n"
            "[Action & Escalation]\n"
            "Isolate DESKTOP-FIN-08, block update-service-win32.com, and update CASE-33279.\n\n"
            "[SOAR Documentation]\n"
            "Executed containment on DESKTOP-FIN-08 and update-service-win32.com.\n\n"
            "```soc_decision\n"
            + json.dumps({
                "verdict": "MALICIOUS",
                "recommended_actions": ["isolate_host", "block_indicator", "update_case_comment"],
                "target_entity": "DESKTOP-FIN-08",
                "rationale": "Confirmed C2 traffic.",
            })
            + "\n```"
        )
        return synth, {"prompt_tokens": 300, "completion_tokens": 100, "total_tokens": 400}

    supervisor._call_llm_step = _mock_supervisor_llm  # type: ignore[method-assign]
    res = supervisor.query(
        "Investigate outbound C2 beacon from host DESKTOP-FIN-08 to domain update-service-win32.com (Case 33279)."
    )

    assert res["verdict"] == "MALICIOUS"
    assert res["worker_mode"] == "rlm"
    assert res["rlm_repl_steps"] == 2
    tools_called = [step["tool"] for step in res["trajectory"]]
    assert tools_called == [
        "lookup_entity",
        "get_domain_report",
        "list_cases",
        "isolate_host",
        "block_indicator",
        "update_case_comment",
    ]


def test_supervisor_auto_worker_mode_routes_threat_hunt_to_rlm_and_triage_to_react() -> None:
    env = SocEnvironment()
    supervisor = SOCSupervisorAgent(environment=env, worker_mode="auto")

    assert supervisor._resolve_effective_worker_mode("THREAT_HUNT") == "rlm"
    assert supervisor._resolve_effective_worker_mode("C2_BEACON") == "react"
    assert supervisor._resolve_effective_worker_mode("PHISHING_DOMAIN") == "react"
    assert supervisor._resolve_effective_worker_mode("MALWARE_HASH") == "react"
    assert supervisor._resolve_effective_worker_mode("SUSPICIOUS_LOGIN") == "react"
    assert supervisor._resolve_effective_worker_mode("LATERAL_MOVEMENT") == "react"

