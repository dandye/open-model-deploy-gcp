"""Unit tests for Gemini 4 per-model implicit prompt caching, prefix hygiene, and TCO telemetry."""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

from agent.gemini4_caching import (
    GEMINI_4_NEON_MAX_CONCURRENCY,
    assert_explicit_caching_allowed,
    compute_cache_telemetry,
    detect_token0_prefix_hazards,
    estimate_cached_cost_usd,
    extract_usage_metrics,
    is_gemini_4_model,
    is_gemini_4_neon,
    neon_concurrency_guard,
    resolve_gemini_location,
    sanitize_generate_content_config_kwargs,
    supports_explicit_caching,
)
from agent.gemma_agent import GemmaAgent
from agent.gepa_runbook_optimizer import (
    GoogleGenAILM,
    build_compose_prompt,
    build_domain_reflection_prompt_template,
    build_invariant_reflection_prompt_template,
    build_reflection_prompt_template,
)
from agent.hierarchical_soc_agent import (
    HierarchicalSOCTier1Agent,
    SOCRunbookWorkerAgent,
    WorkerInvestigationReport,
)
from agent.hillclimb_harness import estimate_model_cost_usd
from agent.soc_environment import SocEnvironment
from agent.soc_tier1_agent import SocTier1Agent


def test_gemini4_model_detection_and_explicit_cache_gating():
    """Gemini 4 models must gate off explicit caching and route to location='global'."""
    for model in (
        "gemini-4-hydrogen",
        "gemini-4-neon",
        "gemini-4-carbon",
        "publishers/google/models/gemini-4-neon",
    ):
        assert is_gemini_4_model(model) is True
        assert supports_explicit_caching(model) is False
        assert resolve_gemini_location(model, "us-central1") == "global"
        assert resolve_gemini_location(model, "us-east4") == "global"
        with pytest.raises(ValueError, match="Implicit Context Caching"):
            assert_explicit_caching_allowed(model)

    assert is_gemini_4_neon("gemini-4-neon") is True
    assert is_gemini_4_neon("gemini-4-hydrogen") is False
    assert is_gemini_4_model("gemini-2.5-flash") is False
    assert supports_explicit_caching("gemini-2.5-flash") is True
    assert_explicit_caching_allowed("gemini-2.5-flash")


def test_gemini4_parameter_hygiene_strips_sampling_and_flex_and_cached_content():
    """Gemini 4 config sanitization must omit temperature, top_p, top_k, cached_content, and Flex tier."""
    raw = {
        "temperature": 0.2,
        "top_p": 0.9,
        "top_k": 40,
        "cached_content": "projects/p/locations/global/cachedContents/123",
        "service_tier": "FLEX",
        "system_instruction": "Static SOC policy.",
        "max_output_tokens": 2048,
    }
    cleaned_g4 = sanitize_generate_content_config_kwargs("gemini-4-hydrogen", raw)
    assert "temperature" not in cleaned_g4
    assert "top_p" not in cleaned_g4
    assert "top_k" not in cleaned_g4
    assert "cached_content" not in cleaned_g4
    assert "service_tier" not in cleaned_g4
    assert cleaned_g4["system_instruction"] == "Static SOC policy."
    assert cleaned_g4["max_output_tokens"] == 2048

    # Non-Gemini-4 models preserve sampling and explicit cache fields
    cleaned_g25 = sanitize_generate_content_config_kwargs("gemini-2.5-pro", raw)
    assert cleaned_g25["temperature"] == 0.2
    assert cleaned_g25["cached_content"] == raw["cached_content"]


def test_gemma_agent_gemini4_omits_temperature_and_gates_explicit_cache():
    """GemmaAgent.query on Gemini 4 must use global location, generate_content, omit temperature & cached_content, and capture cached tokens."""
    agent = GemmaAgent(
        project_id="test-proj",
        region="us-central1",
        managed_model="gemini-4-hydrogen",
    )
    mock_client = MagicMock()
    mock_res = MagicMock()
    mock_res.text = "Final Answer: Verified."
    mock_res.candidates = []
    mock_res.usage_metadata = MagicMock(
        prompt_token_count=10000,
        cached_content_token_count=8500,
        candidates_token_count=400,
        thoughts_token_count=100,
        total_token_count=10500,
    )
    mock_client.models.generate_content.return_value = mock_res

    with patch("google.genai.Client", return_value=mock_client) as mock_client_cls:
        out = agent.query(
            prompt="Investigate alert",
            temperature=0.7,
            system_instruction="Static prefix",
            cached_content="projects/p/cachedContents/should-be-stripped",
        )

    assert mock_client_cls.call_args.kwargs["location"] == "global"
    assert mock_client_cls.call_args.kwargs["http_options"].api_version == "v1"
    mock_client.models.generate_content.assert_called_once()
    mock_client.chats.create.assert_not_called()
    cfg = mock_client.models.generate_content.call_args.kwargs["config"]
    assert cfg.temperature is None
    assert cfg.top_p is None
    assert cfg.top_k is None
    assert cfg.cached_content is None
    assert cfg.system_instruction == "Static prefix"
    assert out["region"] == "global"
    assert out["usage"]["prompt_tokens"] == 10000
    assert out["usage"]["cached_tokens"] == 8500
    assert out["usage"]["thoughts_tokens"] == 100
    assert out["usage"]["cache_hit_rate"] == pytest.approx(0.85, rel=1e-4)


def test_google_genai_lm_gemini4_parameter_hygiene_and_usage():
    """GoogleGenAILM must route Gemini 4 to global, omit temperature, and record cached_tokens."""
    mock_client = MagicMock()
    mock_res = MagicMock()
    mock_res.text = "```markdown\n# Revised Runbook\n```"
    mock_res.usage_metadata = MagicMock(
        prompt_token_count=6000,
        cached_content_token_count=4800,
        candidates_token_count=300,
        thoughts_token_count=200,
        total_token_count=6500,
    )
    mock_client.models.generate_content.return_value = mock_res

    lm = GoogleGenAILM(model="gemini-4-neon", project_id="test-proj", location="us-central1", client=mock_client)
    assert lm.location == "global"
    text = lm("Refine runbook")
    assert "Revised Runbook" in text
    cfg = mock_client.models.generate_content.call_args.kwargs["config"]
    assert "temperature" not in cfg
    assert lm.last_usage["cached_tokens"] == 4800
    assert lm.last_usage["cache_hit_rate"] == pytest.approx(0.80, rel=1e-4)


def test_neon_concurrency_guard_caps_at_two():
    """gemini-4-neon concurrency must never exceed 2 active calls simultaneously."""
    active = 0
    peak = 0
    lock = threading.Lock()

    def worker():
        nonlocal active, peak
        with neon_concurrency_guard("gemini-4-neon"):
            with lock:
                active += 1
                peak = max(peak, active)
            time.sleep(0.05)
            with lock:
                active -= 1

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert peak <= GEMINI_4_NEON_MAX_CONCURRENCY
    assert peak == 2


def test_token0_prefix_hazard_detector():
    """detect_token0_prefix_hazards must flag dynamic timestamps, turn counters, IDs, and CMDB blocks."""
    dirty = (
        "[Turn=1 | RequestTimestamp=2026-11-24T04:00:00Z | RequestId=req-123]\n"
        "Original Alert:\nInvestigate CASE-999 [CMDB Asset Context: SRV-01]"
    )
    hazards = set(detect_token0_prefix_hazards(dirty))
    assert "dynamic_timestamp" in hazards
    assert "dynamic_turn_counter" in hazards
    assert "dynamic_request_or_session_id" in hazards
    assert "per_case_id" in hazards
    assert "per_case_cmdb_block" in hazards
    assert "per_case_alert_payload" in hazards

    clean = "You are a Tier 1 SOC Analyst. Follow Stages A through D deterministically."
    assert detect_token0_prefix_hazards(clean) == []


def test_static_first_prefix_hygiene_across_agents_and_gepa_templates():
    """All agent system_instructions and GEPA templates must be static-first with sorted tools."""
    # 1. SocTier1Agent
    t1 = SocTier1Agent()
    t1_sys = t1._build_react_system_instruction()
    assert detect_token0_prefix_hazards(t1_sys) == []
    tool_lines = [line for line in t1._build_tools_description().splitlines() if line.startswith("- ")]
    tool_names = [line.split("(", 1)[0].lstrip("- ").strip() for line in tool_lines]
    assert tool_names == sorted(tool_names)

    # 2. SOCRunbookWorkerAgent
    worker = SOCRunbookWorkerAgent(
        classification="C2_BEACON",
        runbook_name="basic_ioc_enrichment.md",
        runbook_content="# Basic IOC Enrichment\n1. Query indicators.\n",
    )
    w_sys = worker._build_worker_system_instruction()
    assert detect_token0_prefix_hazards(w_sys) == []
    w_tool_lines = [line for line in worker._build_tools_description().splitlines() if line.startswith("- ")]
    w_tool_names = [line.split("(", 1)[0].lstrip("- ").strip() for line in w_tool_lines]
    assert w_tool_names == sorted(w_tool_names)

    # 3. SOCSupervisorAgent
    sup = HierarchicalSOCTier1Agent()
    s_sys = sup.build_supervisor_system_instruction()
    assert detect_token0_prefix_hazards(s_sys) == []

    # Verify supervisor synthesis passes static system_instruction and trailing dynamic user prompt
    captured: Dict[str, Any] = {}

    def fake_step(prompt: str, max_tokens=None, temperature=0.0, *, system_instruction=None):
        captured["prompt"] = prompt
        captured["system_instruction"] = system_instruction
        return (
            '[Context & Enrichment]\nOK\n\n[Analysis & Verdict]\nBENIGN\n\n'
            '[Action & Escalation]\nclose_case\n\n[SOAR Documentation]\nDone\n\n'
            '```soc_decision\n{"verdict": "BENIGN", "recommended_actions": ["close_case"], "target_entity": "CASE-101", "rationale": "Authorized"}\n```',
            {"prompt_tokens": 5000, "cached_tokens": 4200, "completion_tokens": 120, "thoughts_tokens": 30, "total_tokens": 5150},
        )

    sup._call_llm_step = fake_step
    report = WorkerInvestigationReport(
        classification="C2_BEACON",
        runbook_name="basic_ioc_enrichment.md",
        target_entities=["CASE-101", "198.51.100.10"],
        risk_level="BENIGN",
        evidence=["get_ip_address_report: benign"],
    )
    sup._synthesize_verdict_and_containment(
        prompt="Alert CASE-101 [CMDB Asset Context: host=SRV-01]",
        classification="C2_BEACON",
        runbook_name="basic_ioc_enrichment.md",
        worker_report=report,
    )
    assert detect_token0_prefix_hazards(captured["system_instruction"]) == []
    assert "CASE-101" not in captured["system_instruction"]
    assert "[CMDB Asset Context:" not in captured["system_instruction"]
    assert "CASE-101" in captured["prompt"]
    assert "[CMDB Asset Context:" in captured["prompt"]

    # 4. GEPA reflection & compose templates must place static rules before dynamic placeholders
    for tmpl in (
        build_reflection_prompt_template(),
        build_invariant_reflection_prompt_template(),
        build_domain_reflection_prompt_template(),
    ):
        rules_pos = tmpl.find("Rules")
        if rules_pos == -1:
            rules_pos = tmpl.find("Refinement Guidelines")
        assert rules_pos != -1
        assert rules_pos < tmpl.index("<curr_param>")
        assert tmpl.index("<curr_param>") < tmpl.index("<side_info>")

    compose = build_compose_prompt(
        component_name="malware_triage.md",
        base_text="# Base",
        inv_text="# INV",
        dom_text="# DOM",
        base_score=0.5,
        inv_score=0.7,
        dom_score=0.8,
    )
    assert compose.index("COMPOSE Rules:") < compose.index("Matched Probe Scores")
    assert compose.index("COMPOSE Rules:") < compose.index("### Base Runbook")


def test_heterogeneous_neon_supervisor_and_batched_hydrogen_worker_telemetry():
    """HierarchicalSOCTier1Agent with Neon supervisor + Hydrogen worker tracks per-model cache hits and TCO."""
    env = SocEnvironment.from_eval_case({
        "eval_id": "CASE-G4-01",
        "prompt": "Alert on DESKTOP-FIN-08 contacting 198.51.100.55 (CASE-G4-01)",
        "ground_truth_label": "MALICIOUS",
        "expected_actions": ["isolate_host", "block_indicator", "update_case_comment"],
        "prohibited_actions": ["close_case"],
        "initial_state": {
            "hosts": {"DESKTOP-FIN-08": {"ip": "10.0.0.8", "role": "finance_workstation", "isolated": False}},
            "ips": {"198.51.100.55": {"verdict": "MALICIOUS", "reputation": "MALICIOUS", "threat_category": "C2"}},
            "cases": {"CASE-G4-01": {"status": "OPEN", "comments": []}},
        },
    })

    agent = HierarchicalSOCTier1Agent(
        project_id="test-proj",
        managed_model="gemini-4-neon",
        worker_model="gemini-4-hydrogen",
        environment=env,
        runbooks_dict={"basic_ioc_enrichment.md": "# IOC Enrichment\n1. Query IP and host.\n"},
    )

    seen_models: List[str] = []
    call_idx = 0

    def fake_gemma_query(self_obj, prompt, max_tokens=None, temperature=0.7, *, system_instruction=None, **kwargs):
        nonlocal call_idx
        call_idx += 1
        seen_models.append(self_obj.managed_model)
        if self_obj.managed_model == "gemini-4-hydrogen":
            if call_idx == 1:
                return {
                    "response": 'Thought: Enrich IP.\nAction: get_ip_address_report(ip="198.51.100.55")',
                    "backend": "MaaS (gemini-4-hydrogen)",
                    "usage": {"prompt_tokens": 5000, "cached_tokens": 0, "completion_tokens": 80, "thoughts_tokens": 20, "total_tokens": 5100, "cache_hit_rate": 0.0},
                }
            return {
                "response": (
                    "Final Answer:\n[Context & Enrichment]\n198.51.100.55 malicious\n\n"
                    "[Findings & Evidence]\nConfirmed C2\n\n[Preliminary Risk Assessment]\nMALICIOUS\n\n"
                    '```worker_report\n{"classification": "C2_BEACON", "target_entities": ["DESKTOP-FIN-08", "198.51.100.55", "CASE-G4-01"], "findings": {"198.51.100.55": "MALICIOUS"}, "evidence": ["MALICIOUS"], "risk_level": "MALICIOUS"}\n```'
                ),
                "backend": "MaaS (gemini-4-hydrogen)",
                "usage": {"prompt_tokens": 5200, "cached_tokens": 4500, "completion_tokens": 120, "thoughts_tokens": 30, "total_tokens": 5350, "cache_hit_rate": 0.8654},
            }
        # Supervisor synthesis on gemini-4-neon
        return {
            "response": (
                "[Context & Enrichment]\nDESKTOP-FIN-08 -> 198.51.100.55\n\n"
                "[Analysis & Verdict]\nMALICIOUS\n\n"
                "[Action & Escalation]\nIsolate DESKTOP-FIN-08 and block 198.51.100.55\n\n"
                "[SOAR Documentation]\nUpdated CASE-G4-01\n\n"
                '```soc_decision\n{"verdict": "MALICIOUS", "recommended_actions": ["isolate_host", "block_indicator", "update_case_comment"], "target_entity": "DESKTOP-FIN-08", "rationale": "Confirmed C2"}\n```'
            ),
            "backend": "MaaS (gemini-4-neon)",
            "usage": {"prompt_tokens": 5500, "cached_tokens": 4400, "completion_tokens": 150, "thoughts_tokens": 50, "total_tokens": 5700, "cache_hit_rate": 0.8},
        }

    with patch.object(GemmaAgent, "query", fake_gemma_query):
        res = agent.query("Alert on DESKTOP-FIN-08 contacting 198.51.100.55 (CASE-G4-01)", max_iterations=4)

    # Consecutive Hydrogen worker turns batched BEFORE single Neon supervisor turn
    assert seen_models == ["gemini-4-hydrogen", "gemini-4-hydrogen", "gemini-4-neon"]
    assert res.verdict == "MALICIOUS"
    usage = res.usage
    assert usage["worker_model"] == "gemini-4-hydrogen"
    assert usage["supervisor_model"] == "gemini-4-neon"
    assert usage["prompt_tokens"] == 5000 + 5200 + 5500
    assert usage["cached_tokens"] == 4500 + 4400
    assert usage["thoughts_tokens"] == 20 + 30 + 50
    assert usage["cache_hit_pct"] == pytest.approx((8900 / 15700) * 100.0, rel=1e-2)
    assert usage["estimated_cost_usd"] > 0
    assert usage["estimated_cost_per_1k_runs_usd"] == pytest.approx(usage["estimated_cost_usd"] * 1000.0, rel=1e-3)


def test_gemini4_pricing_and_tco_math():
    """Verify exact Gemini 4 uncached, cached (95% off), and output+thinking pricing math."""
    # Hydrogen: $1.50 uncached, $0.075 cached, $7.50 output+thinking
    h_cost = estimate_cached_cost_usd(
        "gemini-4-hydrogen",
        prompt_tokens=1_000_000,
        cached_tokens=800_000,
        completion_tokens=600_000,
        thoughts_tokens=400_000,
    )
    expected_h = (200_000 * 1.50 + 800_000 * 0.075 + 1_000_000 * 7.50) / 1_000_000.0
    assert h_cost == pytest.approx(expected_h, rel=1e-6)
    assert estimate_model_cost_usd(
        "gemini-4-hydrogen",
        prompt_tokens=1_000_000,
        cached_tokens=800_000,
        completion_tokens=600_000,
        thoughts_tokens=400_000,
    ) == pytest.approx(expected_h, rel=1e-6)

    # Neon: $3.00 uncached, $0.150 cached, $15.00 output+thinking
    n_cost = estimate_cached_cost_usd(
        "gemini-4-neon",
        prompt_tokens=1_000_000,
        cached_tokens=500_000,
        completion_tokens=1_000_000,
    )
    assert n_cost == pytest.approx(1.50 + 0.075 + 15.00, rel=1e-6)

    # Carbon: $4.00 uncached, $0.200 cached, $20.00 output+thinking
    c_cost = estimate_cached_cost_usd(
        "gemini-4-carbon",
        prompt_tokens=1_000_000,
        cached_tokens=1_000_000,
        completion_tokens=0,
    )
    assert c_cost == pytest.approx(0.200, rel=1e-6)

    telem = compute_cache_telemetry(
        {"prompt_tokens": 10000, "cached_tokens": 8000, "completion_tokens": 200, "thoughts_tokens": 100},
        model="gemini-4-hydrogen",
        runs=2,
    )
    assert telem["cache_hit_pct"] == 80.0
    assert telem["output_and_thinking_tokens"] == 300
    assert telem["estimated_cost_per_1k_runs_usd"] == pytest.approx((telem["estimated_cost_usd"] / 2) * 1000.0, rel=1e-3)
