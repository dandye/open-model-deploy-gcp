"""Unit tests for GEPA runbook optimizer core data structures and fitness metrics."""

import json
import math
from pathlib import Path
import pytest

from agent.gepa_runbook_optimizer import (
    CORE_RUNBOOKS,
    load_seed_runbooks,
    save_runbooks,
    calculate_loss_penalty,
    calculate_case_fitness,
)


def test_core_runbooks_list():
    assert isinstance(CORE_RUNBOOKS, list)
    assert len(CORE_RUNBOOKS) == 4
    expected = [
        "basic_ioc_enrichment.md",
        "suspicious_login_triage.md",
        "malware_triage.md",
        "lateral_movement_hunt_psexec_wmi.md",
    ]
    assert CORE_RUNBOOKS == expected


def test_load_seed_runbooks_default():
    candidate = load_seed_runbooks()
    assert isinstance(candidate, dict)
    assert set(candidate.keys()) == set(CORE_RUNBOOKS)
    for name, text in candidate.items():
        assert isinstance(text, str)
        assert len(text) > 100
        # Ensure no emojis in seed runbooks
        assert not any(ord(char) > 0x1F000 for char in text)


def test_load_seed_runbooks_custom_dir(tmp_path: Path):
    custom_dir = tmp_path / "custom_runbooks"
    custom_dir.mkdir()
    for name in CORE_RUNBOOKS:
        (custom_dir / name).write_text(f"# Custom content for {name}\n", encoding="utf-8")

    loaded = load_seed_runbooks(runbooks_dir=custom_dir)
    assert set(loaded.keys()) == set(CORE_RUNBOOKS)
    for name in CORE_RUNBOOKS:
        assert loaded[name] == f"# Custom content for {name}\n"


def test_load_seed_runbooks_missing_file_raises(tmp_path: Path):
    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir()
    with pytest.raises(FileNotFoundError):
        load_seed_runbooks(runbooks_dir=empty_dir)


def test_save_runbooks_with_metadata(tmp_path: Path):
    output_dir = tmp_path / "out_runbooks"
    candidate = {
        "basic_ioc_enrichment.md": "# Enrichment\nRule 1",
        "suspicious_login_triage.md": "# Login\nRule 2",
    }
    metadata = {
        "generation": 3,
        "fitness": 0.88,
        "pareto_size": 2,
    }

    save_runbooks(candidate=candidate, output_dir=output_dir, metadata=metadata)

    assert (output_dir / "basic_ioc_enrichment.md").read_text(encoding="utf-8") == "# Enrichment\nRule 1"
    assert (output_dir / "suspicious_login_triage.md").read_text(encoding="utf-8") == "# Login\nRule 2"

    metadata_path = output_dir / "evolution_metadata.json"
    assert metadata_path.exists()
    loaded_meta = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert loaded_meta == metadata


def test_save_runbooks_without_metadata(tmp_path: Path):
    output_dir = tmp_path / "out_runbooks_no_meta"
    candidate = {"malware_triage.md": "# Malware Triage\nSteps"}

    save_runbooks(candidate=candidate, output_dir=output_dir)

    assert (output_dir / "malware_triage.md").read_text(encoding="utf-8") == "# Malware Triage\nSteps"
    assert not (output_dir / "evolution_metadata.json").exists()


def test_calculate_loss_penalty_clean():
    penalty = calculate_loss_penalty(
        expected_label="BENIGN",
        actual_verdict="BENIGN",
        executed_actions=["close_case"],
        prohibited_actions=["isolate_host", "block_ip"],
    )
    assert penalty == pytest.approx(1.0)

    penalty_mal = calculate_loss_penalty(
        expected_label="MALICIOUS",
        actual_verdict="MALICIOUS",
        executed_actions=["isolate_host", "block_ip"],
        prohibited_actions=[],
    )
    assert penalty_mal == pytest.approx(1.0)


def test_calculate_loss_penalty_prohibited_action():
    penalty = calculate_loss_penalty(
        expected_label="BENIGN",
        actual_verdict="BENIGN",
        executed_actions=["isolate_host", "close_case"],
        prohibited_actions=["isolate_host"],
    )
    # loss = 10000.0, exp(-1.0) ~= 0.367879
    expected = math.exp(-1.0)
    assert penalty == pytest.approx(expected, rel=1e-4)


def test_calculate_loss_penalty_false_positive_verdict():
    penalty = calculate_loss_penalty(
        expected_label="BENIGN",
        actual_verdict="MALICIOUS",
        executed_actions=["close_case"],
        prohibited_actions=["isolate_host"],
    )
    # loss = 5000.0, exp(-0.5) ~= 0.60653
    expected = math.exp(-0.5)
    assert penalty == pytest.approx(expected, rel=1e-4)


def test_calculate_loss_penalty_false_negative_verdict():
    penalty = calculate_loss_penalty(
        expected_label="MALICIOUS",
        actual_verdict="BENIGN",
        executed_actions=["close_case"],
        prohibited_actions=[],
    )
    # loss = 10000.0, exp(-1.0) ~= 0.367879
    expected = math.exp(-1.0)
    assert penalty == pytest.approx(expected, rel=1e-4)


def test_calculate_loss_penalty_compound():
    penalty = calculate_loss_penalty(
        expected_label="BENIGN",
        actual_verdict="MALICIOUS",
        executed_actions=["isolate_host"],
        prohibited_actions=["isolate_host"],
    )
    # loss = 10000.0 (prohibited action) + 5000.0 (false positive verdict) = 15000.0
    # exp(-1.5) ~= 0.22313
    expected = math.exp(-1.5)
    assert penalty == pytest.approx(expected, rel=1e-4)


def test_calculate_case_fitness_weights():
    # 0.40 * 1.0 + 0.20 * 1.0 + 0.20 * 1.0 + 0.20 * 1.0 = 1.0
    fitness = calculate_case_fitness(
        rubric_score=1.0,
        assertions_passed=True,
        operator_compliance=1.0,
        loss_penalty=1.0,
    )
    assert fitness == pytest.approx(1.0)

    # 0.40 * 0.0 + 0.20 * 0.0 + 0.20 * 0.0 + 0.20 * 0.0 = 0.0
    fitness_zero = calculate_case_fitness(
        rubric_score=0.0,
        assertions_passed=False,
        operator_compliance=0.0,
        loss_penalty=0.0,
    )
    assert fitness_zero == pytest.approx(0.0)

    # 0.40 * 0.5 + 0.20 * 0.0 + 0.20 * 0.5 + 0.20 * 0.368 = 0.2 + 0 + 0.1 + 0.0736 = 0.3736
    fitness_low = calculate_case_fitness(
        rubric_score=0.5,
        assertions_passed=False,
        operator_compliance=0.5,
        loss_penalty=0.368,
    )
    assert fitness_low == pytest.approx(0.3736, abs=1e-3)


def test_google_genai_lm_call():
    from agent.gepa_runbook_optimizer import GoogleGenAILM
    from unittest.mock import MagicMock

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Optimized runbook content"
    mock_client.models.generate_content.return_value = mock_response

    lm = GoogleGenAILM(model="gemini-2.5-pro", client=mock_client)
    result = lm("Generate runbook")

    assert result == "Optimized runbook content"
    mock_client.models.generate_content.assert_called_once()
    call_kwargs = mock_client.models.generate_content.call_args.kwargs
    assert call_kwargs["model"] == "gemini-2.5-pro"
    assert "Generate runbook" in call_kwargs["contents"]


def test_google_genai_lm_call_list_prompt():
    from agent.gepa_runbook_optimizer import GoogleGenAILM
    from unittest.mock import MagicMock

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Chat response"
    mock_client.models.generate_content.return_value = mock_response

    lm = GoogleGenAILM(model="gemini-2.5-pro", client=mock_client)
    prompt_msgs = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"},
    ]
    result = lm(prompt_msgs)
    assert result == "Chat response"
    mock_client.models.generate_content.assert_called_once()


def test_runbook_gepa_adapter_evaluate():
    from agent.gepa_runbook_optimizer import RunbookGEPAAdapter
    from unittest.mock import MagicMock
    import gepa

    candidate = {
        "basic_ioc_enrichment.md": "# Basic IOC Enrichment\nRules",
        "suspicious_login_triage.md": "# Suspicious Login\nRules",
        "malware_triage.md": "# Malware Triage\nRules",
        "lateral_movement_hunt_psexec_wmi.md": "# Lateral Movement\nRules",
    }

    batch = [
        {
            "eval_id": "CASE-GEN3-01-LOKIBOT-C2",
            "prompt": "Triage alert for host DESKTOP-FIN-08 (10.0.4.15) connecting repeatedly to update-service-win32.com.",
            "ground_truth_label": "MALICIOUS",
            "expected_actions": ["isolate_host", "update_case_comment"],
            "prohibited_actions": ["close_case"],
            "assertions": {
                "must_contain": ["update-service-win32.com", "DESKTOP-FIN-08"],
                "must_not_contain": ["False Positive", "confirmed benign"],
            },
        }
    ]

    mock_agent = MagicMock()
    mock_response = MagicMock()
    mock_response.response = "Identified Lokibot C2 connecting to update-service-win32.com on DESKTOP-FIN-08. Isolate host."
    mock_response.trajectory = [
        {"tool": "get_domain_report", "args": {"domain": "update-service-win32.com"}, "observation": "Malicious C2"},
        {"tool": "isolate_host", "args": {"hostname": "DESKTOP-FIN-08"}, "observation": "Host isolated"},
    ]
    mock_response.get = MagicMock(side_effect=lambda k, default="": "MALICIOUS" if k == "verdict" else default)
    mock_agent.query.return_value = mock_response

    mock_agent_factory = MagicMock(return_value=mock_agent)

    adapter = RunbookGEPAAdapter(agent_factory=mock_agent_factory)
    eval_batch = adapter.evaluate(batch, candidate, capture_traces=True)

    assert isinstance(eval_batch, gepa.EvaluationBatch)
    assert len(eval_batch.scores) == 1
    assert len(eval_batch.outputs) == 1
    assert eval_batch.trajectories is not None
    assert len(eval_batch.trajectories) == 1
    assert eval_batch.scores[0] > 0.8
    mock_agent_factory.assert_called_once()
    assert mock_agent_factory.call_args.kwargs["runbooks_dict"] == candidate


def test_runbook_gepa_adapter_make_reflective_dataset_rfc5737():
    from agent.gepa_runbook_optimizer import RunbookGEPAAdapter
    import gepa

    candidate = {
        "basic_ioc_enrichment.md": "# Basic IOC Enrichment\nRules",
    }

    trace_case = {
        "case_id": "CASE-GEN3-02-RFC5737-BENIGN-IP",
        "alert_type": "C2_BEACON",
        "prompt": "Triage authentication log alert: Repeated connection attempts recorded from IP 192.0.2.100 against gateway GW-CORE-VPN-01.",
        "cmdb_context": {"asset_id": "GW-CORE-VPN-01"},
        "expected_verdict": "BENIGN",
        "expected_actions": ["close_case"],
        "prohibited_actions": ["isolate_host", "block_indicator"],
        "actual_verdict": "MALICIOUS",
        "executed_actions": ["isolate_host"],
        "summary": "Falsely isolated host for RFC-5737 test IP 192.0.2.100.",
        "score": 0.45,
        "loss_penalty": 0.3678,
        "assert_passed": False,
        "component_name": "basic_ioc_enrichment.md",
    }

    eval_batch = gepa.EvaluationBatch(
        outputs=["Response text"],
        scores=[0.45],
        trajectories=[trace_case],
    )

    adapter = RunbookGEPAAdapter()
    reflective_dataset = adapter.make_reflective_dataset(
        candidate=candidate,
        eval_batch=eval_batch,
        components_to_update=["basic_ioc_enrichment.md"],
    )

    assert "basic_ioc_enrichment.md" in reflective_dataset
    records = reflective_dataset["basic_ioc_enrichment.md"]
    assert len(records) == 1
    rec = records[0]
    assert "Inputs" in rec
    assert "Generated Outputs" in rec
    assert "Feedback" in rec
    assert "RFC-5737" in rec["Feedback"]
    assert "isolate" in rec["Feedback"].lower() or "benign" in rec["Feedback"].lower()


def test_runbook_gepa_adapter_make_reflective_dataset_scanner():
    from agent.gepa_runbook_optimizer import RunbookGEPAAdapter
    import gepa

    candidate = {
        "suspicious_login_triage.md": "# Suspicious Login Triage\nRules",
    }

    trace_case = {
        "case_id": "CASE-GEN3-10-AUTHORIZED-SCANNER-NOISE",
        "alert_type": "SUSPICIOUS_LOGIN",
        "prompt": "Triage alert for host SRV-PROD-PAYMENT-01 (10.0.99.50) receiving high-volume port scanning activity from internal subnet.",
        "cmdb_context": {"asset_id": "SRV-PROD-PAYMENT-01"},
        "expected_verdict": "BENIGN",
        "expected_actions": ["close_case", "update_case_comment"],
        "prohibited_actions": ["isolate_host"],
        "actual_verdict": "MALICIOUS",
        "executed_actions": ["isolate_host"],
        "summary": "Falsely isolated production payment server for Qualys vulnerability scanner.",
        "score": 0.40,
        "loss_penalty": 0.3678,
        "assert_passed": False,
        "component_name": "suspicious_login_triage.md",
    }

    eval_batch = gepa.EvaluationBatch(
        outputs=["Response text"],
        scores=[0.40],
        trajectories=[trace_case],
    )

    adapter = RunbookGEPAAdapter()
    reflective_dataset = adapter.make_reflective_dataset(
        candidate=candidate,
        eval_batch=eval_batch,
        components_to_update=["suspicious_login_triage.md"],
    )

    assert "suspicious_login_triage.md" in reflective_dataset
    records = reflective_dataset["suspicious_login_triage.md"]
    assert len(records) == 1
    rec = records[0]
    assert "Inputs" in rec
    assert "Generated Outputs" in rec
    assert "Feedback" in rec
    assert "Qualys" in rec["Feedback"] or "scanner" in rec["Feedback"].lower()


def test_runbook_gepa_adapter_make_reflective_dataset_missed_containment():
    from agent.gepa_runbook_optimizer import RunbookGEPAAdapter
    import gepa

    candidate = {
        "malware_triage.md": "# Malware Triage\nRules",
    }

    trace_case = {
        "case_id": "CASE-GEN3-05-RANSOMWARE-ESCALATION",
        "alert_type": "MALWARE_HASH",
        "prompt": "Urgent: Multiple .locked files appearing on file share server 10.0.5.23.",
        "cmdb_context": {"asset_id": "DESKTOP-FIN-08"},
        "expected_verdict": "MALICIOUS",
        "expected_actions": ["isolate_host", "update_case_comment"],
        "prohibited_actions": ["close_case"],
        "actual_verdict": "MALICIOUS",
        "executed_actions": ["update_case_comment"],
        "summary": "Failed to isolate host under active ransomware threat.",
        "score": 0.50,
        "loss_penalty": 1.0,
        "assert_passed": True,
        "component_name": "malware_triage.md",
    }

    eval_batch = gepa.EvaluationBatch(
        outputs=["Response text"],
        scores=[0.50],
        trajectories=[trace_case],
    )

    adapter = RunbookGEPAAdapter()
    reflective_dataset = adapter.make_reflective_dataset(
        candidate=candidate,
        eval_batch=eval_batch,
        components_to_update=["malware_triage.md"],
    )

    assert "malware_triage.md" in reflective_dataset
    records = reflective_dataset["malware_triage.md"]
    assert len(records) == 1
    rec = records[0]
    assert "Missed containment" in rec["Feedback"]
    assert "isolate_host" in rec["Feedback"] or "host isolation" in rec["Feedback"]


def test_build_reflection_prompt_template():
    from agent.gepa_runbook_optimizer import build_reflection_prompt_template

    template = build_reflection_prompt_template()
    assert isinstance(template, str)
    assert "<curr_param>" in template
    assert "<side_info>" in template
    assert "192.0.2.0/24" in template
    assert "198.51.100.0/24" in template
    assert "203.0.113.0/24" in template
    assert "10.0.99.50" in template
    # Strictly NO EMOJIS
    assert not any(ord(char) > 0x1F000 for char in template)


def test_build_arg_parser_defaults():
    from agent.gepa_runbook_optimizer import build_arg_parser

    parser = build_arg_parser()
    args = parser.parse_args([])

    assert args.max_metric_calls == 15
    assert args.task_lm == "gemini-2.5-flash-lite"
    assert args.reflection_lm == "gemini-2.5-pro"
    assert args.evalset == "configs/evals/gen3/soc_tier1_interactive.json"
    assert args.output_dir == "configs/runbooks/gepa_evolved"
    assert args.seed == 42
    assert args.dry_run is False


def test_cli_main_dry_run(tmp_path: Path):
    from unittest.mock import MagicMock, patch
    from agent.gepa_runbook_optimizer import main

    # Mock agent and factory
    mock_agent = MagicMock()
    mock_response = MagicMock()
    mock_response.response = "Case resolved cleanly."
    mock_response.trajectory = [
        {"tool": "close_case", "args": {}, "observation": "Case closed"}
    ]
    mock_response.get = MagicMock(return_value="BENIGN")
    mock_agent.query.return_value = mock_response

    mock_factory = MagicMock(return_value=mock_agent)

    test_evalset = tmp_path / "test_evalset.json"
    test_cases = {
        "eval_cases": [
            {
                "eval_id": "CASE-01",
                "prompt": "Test prompt 1",
                "ground_truth_label": "BENIGN",
                "expected_actions": ["close_case"],
                "prohibited_actions": [],
            },
            {
                "eval_id": "CASE-02",
                "prompt": "Test prompt 2",
                "ground_truth_label": "BENIGN",
                "expected_actions": ["close_case"],
                "prohibited_actions": [],
            },
        ]
    }
    test_evalset.write_text(json.dumps(test_cases), encoding="utf-8")

    cli_args = [
        "--dry-run",
        "--evalset", str(test_evalset),
        "--output-dir", str(tmp_path / "evolved_out"),
    ]

    with patch("agent.gepa_runbook_optimizer.HierarchicalSOCTier1Agent", mock_factory):
        exit_code = main(cli_args)

    assert exit_code == 0
    assert mock_factory.call_count >= 2


