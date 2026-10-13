"""Unit tests for GEPA runbook optimizer core data structures and fitness metrics."""

import json
import math
from pathlib import Path
from typing import Optional
import pytest

from agent.gepa_runbook_optimizer import (
    CORE_RUNBOOKS,
    load_seed_runbooks,
    save_runbooks,
    calculate_loss_penalty,
    calculate_case_fitness,
    is_gen5_evalset,
)

ROOT_DIR = Path(__file__).resolve().parent.parent


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
    assert "False positive operational disruption" in rec["Feedback"]
    assert "prohibited host isolation" in rec["Feedback"].lower()
    assert "epistemic" in rec["Feedback"].lower()


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
    assert "False positive operational disruption" in rec["Feedback"]
    assert "prohibited host isolation" in rec["Feedback"].lower()
    assert "epistemic" in rec["Feedback"].lower()


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
    # De-spoiled: zero literal IP subnets or specific scanner IPs
    assert "192.0.2.0/24" not in template
    assert "198.51.100.0/24" not in template
    assert "203.0.113.0/24" not in template
    assert "10.0.99.50" not in template
    # Procedural and anti-memorization guidelines present
    assert "CMDB" in template or "lookup_entity" in template
    assert "epistemic" in template.lower() or "verification" in template.lower()
    assert "memoriz" in template.lower() or "variable" in template.lower()
    # Strictly NO EMOJIS
    assert not any(ord(char) > 0x1F000 for char in template)


def test_validate_runbook_candidate_clean():
    from agent.gepa_runbook_optimizer import validate_runbook_candidate

    candidate = {
        "basic_ioc_enrichment.md": (
            "# Basic IOC Enrichment\n\n"
            "## Steps\n"
            "1. Extract ${IOC_VALUE} and ${IOC_TYPE}.\n"
            "2. Query lookup_entity for asset context and check ${ASSET_ROLE}.\n"
            "3. Query get_ip_address_report to verify routing classification.\n"
            "4. If GTI reputation indicates active malicious malware, recommend isolate_host.\n"
        )
    }
    valid, violations = validate_runbook_candidate(candidate)
    assert valid is True
    assert violations == []


def test_validate_runbook_candidate_hardcoded_ip():
    from agent.gepa_runbook_optimizer import validate_runbook_candidate

    candidate = {
        "basic_ioc_enrichment.md": (
            "# Basic IOC Enrichment\n\n"
            "Rule 1: If IP is 192.0.2.0/24, close case immediately.\n"
            "Rule 2: Scanner is 10.0.99.50.\n"
        )
    }
    valid, violations = validate_runbook_candidate(candidate)
    assert valid is False
    assert len(violations) >= 2
    assert any("192.0.2.0/24" in v or "IPv4 literal" in v for v in violations)


def test_validate_runbook_candidate_hardcoded_hostname():
    from agent.gepa_runbook_optimizer import validate_runbook_candidate

    candidate = {
        "basic_ioc_enrichment.md": (
            "# Basic IOC Enrichment\n\n"
            "If host is GW-CORE-VPN-01 or SRV-PROD-PAYMENT-01, do not isolate.\n"
        )
    }
    valid, violations = validate_runbook_candidate(candidate)
    assert valid is False
    assert any("GW-CORE-VPN-01" in v for v in violations)
    assert any("SRV-PROD-PAYMENT-01" in v for v in violations)


def test_validate_runbook_candidate_short_circuit():
    from agent.gepa_runbook_optimizer import validate_runbook_candidate

    candidate = {
        "basic_ioc_enrichment.md": (
            "# Basic IOC Enrichment\n\n"
            "If asset is authorized scanner, skip all enrichment and proceed to Step 9.\n"
        )
    }
    valid, violations = validate_runbook_candidate(candidate)
    assert valid is False
    assert any("short-circuit" in v.lower() or "skip all enrichment" in v.lower() for v in violations)


def test_adapter_evaluate_rejects_memorized_candidate():
    from agent.gepa_runbook_optimizer import RunbookGEPAAdapter

    memorized_candidate = {
        "basic_ioc_enrichment.md": "If IP is 192.0.2.100 or host is GW-CORE-VPN-01, skip all enrichment."
    }
    batch = [
        {
            "eval_id": "CASE-01",
            "prompt": "Investigate alert",
            "ground_truth_label": "BENIGN",
            "expected_actions": ["close_case"],
            "prohibited_actions": [],
        }
    ]

    adapter = RunbookGEPAAdapter()
    eval_batch = adapter.evaluate(batch=batch, candidate=memorized_candidate)

    assert eval_batch.scores == [0.0]
    assert len(eval_batch.trajectories) == 1
    assert "rejected" in eval_batch.outputs[0].lower() or "memoriz" in eval_batch.outputs[0].lower()



def test_build_arg_parser_defaults():
    from agent.gepa_runbook_optimizer import build_arg_parser

    parser = build_arg_parser()
    args = parser.parse_args([])

    assert args.max_metric_calls == 15
    assert args.task_lm == "gemini-2.5-flash-lite"
    assert args.reflection_lm == "gemini-2.5-pro"
    assert args.evalset is None
    assert args.train_split == "train" and args.val_split == "validation" and args.noise_only is False and args.manifest.endswith("configs/evals/gen5/manifest.json")
    assert args.output_dir == "configs/runbooks/gepa_evolved"
    assert args.seed == 42
    assert args.dry_run is False


def test_build_arg_parser_exposes_jev_backend_choices():
    from agent.gepa_runbook_optimizer import build_arg_parser
    from agent.jev_backends import JEV_BACKEND_CHOICES

    parser = build_arg_parser()
    assert parser.parse_args([]).jev_backend == "gemini_system1"
    assert parser.parse_args(["--judge-backend", "jev", "--jev-backend", "gliner_decide"]).jev_backend == "gliner_decide"
    for name in JEV_BACKEND_CHOICES:
        assert parser.parse_args(["--jev-backend", name]).jev_backend == name
    with pytest.raises(SystemExit):
        parser.parse_args(["--jev-backend", "not-a-backend"])


def test_build_inner_judge_follows_the_judge_and_jev_backend_flags():
    from agent.gepa_runbook_optimizer import build_arg_parser, build_inner_judge
    from agent.jev_backend_gliner import GlinerDecideBackend
    from agent.jev_judge import MockJevBackend

    parser = build_arg_parser()
    assert build_inner_judge(parser.parse_args(["--judge-backend", "deterministic"])) is None
    assert isinstance(build_inner_judge(parser.parse_args(["--judge-backend", "mock"])).backend, MockJevBackend)
    assert isinstance(build_inner_judge(parser.parse_args(["--judge-backend", "jev", "--jev-backend", "mock"])).backend, MockJevBackend)
    gliner_judge = build_inner_judge(parser.parse_args(["--judge-backend", "jev", "--jev-backend", "gliner_decide"]))
    assert isinstance(gliner_judge.backend, GlinerDecideBackend)
    assert gliner_judge.backend._engine is None


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


@pytest.fixture
def optimizer_cli(tmp_path, monkeypatch):
    """Run the real CLI against an in-memory GEPA result, without model calls."""
    from unittest.mock import MagicMock
    from gepa.core.result import GEPAResult
    import agent.gepa_runbook_optimizer as optimizer

    seed = {name: "# Seed\nInvestigate available evidence." for name in CORE_RUNBOOKS}
    monkeypatch.setattr(optimizer, "load_seed_runbooks", lambda: seed)
    adapter = MagicMock()
    reflection = MagicMock()
    optimize = MagicMock()
    monkeypatch.setattr(optimizer, "RunbookGEPAAdapter", adapter)
    monkeypatch.setattr(optimizer, "GoogleGenAILM", reflection)
    monkeypatch.setattr(optimizer.gepa, "optimize", optimize)
    output_dir = tmp_path / "evolved"

    def run(candidates, scores, *, case_count=8, split=False, gen5=False, legacy_evalset: Optional[Path] = None, extra=()):
        optimize.return_value = GEPAResult(
            candidates=candidates,
            parents=[[] for _ in candidates],
            val_aggregate_scores=scores,
            val_subscores=[{} for _ in candidates],
            per_val_instance_best_candidates={},
            discovery_eval_counts=[0 for _ in candidates],
        )
        if legacy_evalset is not None:
            monkeypatch.setenv("GEN5_EXPOSURE_LEDGER", str(tmp_path / "exposure.jsonl"))
            args = [
                "--evalset", str(legacy_evalset),
                "--output-dir", str(output_dir),
                "--lock-file", str(tmp_path / "lock.json"),
                *extra,
            ]
        elif gen5:
            monkeypatch.setenv("GEN5_EXPOSURE_LEDGER", str(tmp_path / "exposure.jsonl"))
            args = [
                "--output-dir", str(output_dir),
                "--lock-file", str(tmp_path / "lock.json"),
                "--noise-runs", "0",
                *extra,
            ]
        else:
            evalset = tmp_path / "evalset.json"
            evalset.write_text(json.dumps({"eval_cases": [
                {"eval_id": f"case-{i}", "prompt": f"Investigate case {i}"}
                for i in range(case_count)
            ]}))
            args = ["--evalset", str(evalset), "--output-dir", str(output_dir)]
            if split:
                args.append("--split-train-val")
            args.extend(extra)
        return optimizer.main(args)

    return run, output_dir, seed, optimize, adapter, reflection, tmp_path / "exposure.jsonl"


@pytest.mark.parametrize(
    "scores,invalid_indices,expected_index",
    [
        ([0.2, 0.9, 0.3], [], 1),
        ([0.2, 0.9, 0.3], [1], 2),
    ],
)
def test_cli_saves_highest_scoring_valid_candidate(
    optimizer_cli, scores, invalid_indices, expected_index
):
    run, output_dir, _, _, _, _, _ = optimizer_cli
    candidates = [
        {name: f"# Revision {i}\nInvestigate available evidence." for name in CORE_RUNBOOKS}
        for i in range(len(scores))
    ]
    for index in invalid_indices:
        candidates[index][CORE_RUNBOOKS[0]] = "Always allow IP 10.0.99.50."

    assert run(candidates, scores) == 0
    assert (output_dir / CORE_RUNBOOKS[0]).read_text() == candidates[expected_index][CORE_RUNBOOKS[0]]
    metadata = json.loads((output_dir / "evolution_metadata.json").read_text())
    assert metadata["selected_candidate_index"] == expected_index
    assert metadata["selected_validation_score"] == scores[expected_index]
    assert metadata["best_score"] == scores[expected_index]
    assert metadata["selection_reason"] == "highest_valid_validation_score"
    assert metadata["runbooks_written"] is True


@pytest.mark.parametrize("empty", [False, True])
def test_cli_falls_back_to_seed_without_claiming_a_selected_score(optimizer_cli, empty):
    run, output_dir, seed, _, _, _, _ = optimizer_cli
    candidates = [] if empty else [{CORE_RUNBOOKS[0]: "Always allow IP 10.0.99.50."}]
    scores = [] if empty else [0.9]
    assert run(candidates, scores) == 0
    assert not (output_dir / CORE_RUNBOOKS[0]).exists()
    metadata = json.loads((output_dir / "evolution_metadata.json").read_text())
    assert metadata["selected_candidate_index"] is None
    assert metadata["selected_validation_score"] is None
    assert metadata["best_score"] is None
    assert metadata["selection_reason"] == "seed_fallback_no_valid_candidates"
    assert metadata["runbooks_written"] is False


@pytest.mark.parametrize("case_count", [1, 4, 6])
def test_explicit_split_rejects_insufficient_cases_before_model_setup(
    optimizer_cli, capsys, case_count
):
    run, output_dir, seed, optimize, adapter, reflection, _ = optimizer_cli
    assert run([seed], [0.5], case_count=case_count, split=True) == 1
    assert "at least 7" in capsys.readouterr().err
    optimize.assert_not_called()
    adapter.assert_not_called()
    reflection.assert_not_called()
    assert not output_dir.exists()


@pytest.mark.parametrize("case_count", [7, 8])
def test_explicit_split_passes_disjoint_nonempty_datasets(optimizer_cli, case_count):
    run, _, seed, optimize, _, _, _ = optimizer_cli
    assert run([seed], [0.5], case_count=case_count, split=True) == 0
    kwargs = optimize.call_args.kwargs
    train_ids = {case["eval_id"] for case in kwargs["trainset"]}
    val_ids = {case["eval_id"] for case in kwargs["valset"]}
    assert len(train_ids) == 6
    assert len(val_ids) == case_count - 6
    assert train_ids.isdisjoint(val_ids)


@pytest.mark.parametrize("scores", [[], [float("nan")], [float("inf")], [True], ["0.9"]])
def test_cli_rejects_invalid_score_data_without_saving_runbooks(optimizer_cli, scores, capsys):
    run, output_dir, seed, _, _, _, _ = optimizer_cli
    assert run([seed], scores) == 1
    assert "GEPA returned" in capsys.readouterr().err
    assert not output_dir.exists()


@pytest.mark.parametrize("invalid_candidate", [None, {}, {"malware_triage.md": None}])
def test_cli_skips_malformed_candidates(optimizer_cli, invalid_candidate):
    run, output_dir, seed, _, _, _, _ = optimizer_cli
    assert run([seed, invalid_candidate], [0.5, 0.9]) == 0
    assert not (output_dir / CORE_RUNBOOKS[0]).exists()
    metadata = json.loads((output_dir / "evolution_metadata.json").read_text())
    assert metadata["selected_candidate_index"] == 0
    assert metadata["selected_validation_score"] == 0.5
    assert metadata["selection_reason"] == "seed_retained_all_candidates_reverted"
    assert metadata["runbooks_written"] is False


def test_validate_runbook_candidate_rejects_case_id_and_bloat():
    from agent.gepa_runbook_optimizer import validate_runbook_candidate

    seed = {"basic_ioc_enrichment.md": "# Title\n" + ("Standard instruction line.\n" * 10)}

    # 1. Case-ID literal leakage
    cand_case_id = {
        "basic_ioc_enrichment.md": "# Title\nIn CASE-02 and CASE-10, do not isolate the host.\n"
    }
    ok_id, violations_id = validate_runbook_candidate(cand_case_id, seed_candidate=seed)
    assert ok_id is False
    assert any("CASE-02" in v for v in violations_id)

    # 2. Bloat exceeding 1.35x seed length
    cand_bloated = {
        "basic_ioc_enrichment.md": seed["basic_ioc_enrichment.md"] * 2
    }
    ok_bloat, violations_bloat = validate_runbook_candidate(
        cand_bloated, seed_candidate=seed, max_growth_ratio=1.35
    )
    assert ok_bloat is False
    assert any("growth ratio" in v.lower() for v in violations_bloat)


def test_adapter_evaluate_verifies_harness_guard(tmp_path: Path):
    from agent.gepa_runbook_optimizer import RunbookGEPAAdapter
    from agent.hillclimb_harness import HarnessIntegrityGuard, HarnessTamperError

    eval_file = tmp_path / "evalset.json"
    eval_file.write_text('{"eval_cases": []}', encoding="utf-8")
    lock_file = tmp_path / ".eval_harness_lock.json"

    guard = HarnessIntegrityGuard(
        root_dir=tmp_path,
        lock_file=lock_file,
        protected_paths=[Path("evalset.json")],
    )
    guard.approve_and_save()

    # Tamper with evalset
    eval_file.write_text('{"eval_cases": [{"eval_id": "TAMPERED"}]}', encoding="utf-8")

    adapter = RunbookGEPAAdapter(harness_guard=guard)
    with pytest.raises(HarnessTamperError, match="evalset.json"):
        adapter.evaluate(
            batch=[{"eval_id": "CASE-01", "prompt": "test"}],
            candidate={"basic_ioc_enrichment.md": "# Clean runbook"},
        )


def test_adapter_evaluate_blends_jev_evaluator_and_reflective_feedback():
    from unittest.mock import MagicMock
    from agent.gepa_runbook_optimizer import RunbookGEPAAdapter
    from agent.jev_evaluator import JevSocJudgeEvaluator
    from agent.jev_judge import MockJevBackend

    candidate = {
        "basic_ioc_enrichment.md": "# Basic IOC Enrichment\nRules",
    }
    batch = [
        {
            "eval_id": "CASE-GEN3-01-LOKIBOT-C2",
            "prompt": "Triage alert for host DESKTOP-FIN-08 connecting to update-service-win32.com.",
            "ground_truth_label": "MALICIOUS",
            "expected_actions": ["isolate_host"],
            "prohibited_actions": ["close_case"],
            "assertions": {
                "must_contain": ["update-service-win32.com"],
                "must_not_contain": [],
            },
        }
    ]

    mock_agent = MagicMock()
    mock_response = MagicMock()
    mock_response.response = "Host DESKTOP-FIN-08 connected to update-service-win32.com."
    mock_response.trajectory = []
    mock_response.runbook = "basic_ioc_enrichment.md"
    mock_response.get = MagicMock(return_value="MALICIOUS")
    mock_agent.query.return_value = mock_response
    mock_factory = MagicMock(return_value=mock_agent)

    jev_backend = MockJevBackend(
        score_level=5,
        noul_pass_prob=0.60,
        noul_grounding_prob=0.60,
        choice_label="PREMATURE_TERMINATION_ZERO_TOOLS",
    )
    jev_eval = JevSocJudgeEvaluator(backend=jev_backend)

    adapter = RunbookGEPAAdapter(
        agent_factory=mock_factory,
        jev_evaluator=jev_eval,
        seed_candidate=candidate,
        max_growth_ratio=1.35,
    )
    eval_batch = adapter.evaluate(batch, candidate, capture_traces=True)
    assert eval_batch.trajectories is not None
    trace = eval_batch.trajectories[0]
    assert trace["jev_choice"] == "PREMATURE_TERMINATION_ZERO_TOOLS"

    reflective = adapter.make_reflective_dataset(
        candidate=candidate,
        eval_batch=eval_batch,
        components_to_update=["basic_ioc_enrichment.md"],
    )
    records = reflective["basic_ioc_enrichment.md"]
    assert len(records) == 1
    assert "PREMATURE_TERMINATION_ZERO_TOOLS" in records[0]["Feedback"]


def test_cli_disciplined_hillclimber_flags_and_ledger(tmp_path: Path, monkeypatch):
    from unittest.mock import MagicMock
    import gepa
    from gepa.core.result import GEPAResult
    import agent.gepa_runbook_optimizer as optimizer

    seed = {name: "# Seed\nInvestigate available evidence." for name in CORE_RUNBOOKS}
    monkeypatch.setattr(optimizer, "load_seed_runbooks", lambda: seed)

    evalset = tmp_path / "evalset.json"
    evalset.write_text(
        json.dumps(
            {
                "eval_cases": [
                    {"eval_id": "case-0", "prompt": "Investigate case 0"},
                    {"eval_id": "case-1", "prompt": "Investigate case 1"},
                ]
            }
        ),
        encoding="utf-8",
    )

    mock_adapter_instance = MagicMock()
    mock_adapter_instance.evaluate.side_effect = [
        gepa.EvaluationBatch(outputs=["o1", "o2"], scores=[0.70, 0.70], trajectories=None),
        gepa.EvaluationBatch(outputs=["o1", "o2"], scores=[0.71, 0.71], trajectories=None),
        gepa.EvaluationBatch(
            outputs=["o1", "o2"],
            scores=[0.90, 0.90],
            trajectories=[{"loss_penalty": 1.0}, {"loss_penalty": 1.0}],
        ),
        gepa.EvaluationBatch(
            outputs=["o1", "o2"],
            scores=[0.88, 0.88],
            trajectories=[{"loss_penalty": 1.0}, {"loss_penalty": 1.0}],
        ),
        gepa.EvaluationBatch(
            outputs=["o1", "o2"],
            scores=[0.87, 0.87],
            trajectories=[{"loss_penalty": 1.0}, {"loss_penalty": 1.0}],
        ),
        gepa.EvaluationBatch(
            outputs=["o1", "o2"],
            scores=[0.86, 0.86],
            trajectories=[{"loss_penalty": 0.368}, {"loss_penalty": 1.0}],
        ),
        gepa.EvaluationBatch(
            outputs=["o1", "o2"],
            scores=[0.50, 0.50],
            trajectories=[{"loss_penalty": 1.0}, {"loss_penalty": 1.0}],
        ),
    ]
    mock_adapter_cls = MagicMock(return_value=mock_adapter_instance)
    monkeypatch.setattr(optimizer, "RunbookGEPAAdapter", mock_adapter_cls)
    monkeypatch.setattr(optimizer, "GoogleGenAILM", MagicMock())

    improved = {name: "# Improved\nInvestigate available evidence." for name in CORE_RUNBOOKS}
    mock_optimize = MagicMock(
        return_value=GEPAResult(
            candidates=[seed, improved],
            parents=[[], [0]],
            val_aggregate_scores=[0.70, 0.88],
            val_subscores=[
                {"case-0": 0.70, "case-1": 0.70},
                {"case-0": 0.88, "case-1": 0.88},
            ],
            per_val_instance_best_candidates={},
            discovery_eval_counts=[0, 1],
        )
    )
    monkeypatch.setattr(optimizer.gepa, "optimize", mock_optimize)

    output_dir = tmp_path / "evolved_out"
    lock_file = tmp_path / ".eval_harness_lock.json"

    rc = optimizer.main([
        "--evalset", str(evalset),
        "--output-dir", str(output_dir),
        "--lock-file", str(lock_file),
        "--approve-harness",
        "--noise-runs", "2",
        "--min-delta", "0.015",
        "--max-growth-ratio", "1.35",
        "--judge-backend", "mock",
        "--cost-staircase",
        "--cost-tolerance", "0.05",
    ])
    assert rc == 0
    assert lock_file.exists()
    ledger_path = output_dir / "hillclimb_ledger.jsonl"
    assert ledger_path.exists()
    entries = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(entries) >= 2
    assert any(e["decision"] == "KEPT" for e in entries)
    staircase_path = output_dir / "cost_staircase_report.json"
    assert staircase_path.exists()
    staircase_data = json.loads(staircase_path.read_text(encoding="utf-8"))
    assert staircase_data["selected_model"] == "gemma-4-e4b-it"


def test_cli_keeps_the_seed_when_no_candidate_beats_it(optimizer_cli):
    run, output_dir, seed, _, _, _, _ = optimizer_cli
    output_dir.mkdir(parents=True)
    evolved = output_dir / CORE_RUNBOOKS[0]
    evolved.write_text("# Previously evolved\nKeep me.", encoding="utf-8")
    candidates = [seed, {name: f"# Worse\n{seed[name]}" for name in CORE_RUNBOOKS}]
    assert run(candidates, [0.9, 0.5]) == 0
    assert evolved.read_text(encoding="utf-8") == "# Previously evolved\nKeep me."
    metadata = json.loads((output_dir / "evolution_metadata.json").read_text())
    assert metadata["selected_candidate_index"] == 0
    assert metadata["selection_reason"] == "seed_retained_all_candidates_reverted"
    assert metadata["runbooks_written"] is False


def test_cli_writes_runbooks_only_when_a_non_seed_candidate_wins(optimizer_cli):
    run, output_dir, seed, _, _, _, _ = optimizer_cli
    better = {name: f"# Better\n{seed[name]}" for name in CORE_RUNBOOKS}
    assert run([seed, better], [0.5, 0.9]) == 0
    assert (output_dir / CORE_RUNBOOKS[0]).read_text() == better[CORE_RUNBOOKS[0]]
    metadata = json.loads((output_dir / "evolution_metadata.json").read_text())
    assert metadata["selection_reason"] == "highest_valid_validation_score"
    assert metadata["runbooks_written"] is True


def test_gen5_default_loads_train_and_validation_and_records_exposure(optimizer_cli):
    run, output_dir, seed, optimize, _, _, ledger = optimizer_cli
    better = {name: f"# Better\n{seed[name]}" for name in CORE_RUNBOOKS}
    assert run([seed, better], [0.5, 0.9], gen5=True) == 0
    kwargs = optimize.call_args.kwargs
    train_ids = {case["eval_id"] for case in kwargs["trainset"]}
    val_ids = {case["eval_id"] for case in kwargs["valset"]}
    assert len(train_ids) == 40 and len(val_ids) == 20 and train_ids.isdisjoint(val_ids)
    assert all(case["generation"] == 5 for case in kwargs["trainset"])
    entries = [json.loads(line) for line in ledger.read_text().splitlines()]
    assert [e["split"] for e in entries] == ["train", "validation"]
    assert len({e["run_id"] for e in entries}) == 1
    assert entries[0]["purpose"].endswith("(train)") and entries[1]["purpose"].endswith("(validation)")
    metadata = json.loads((output_dir / "evolution_metadata.json").read_text())
    assert metadata["train_split"] == "train" and metadata["val_split"] == "validation"
    assert metadata["run_id"] == entries[0]["run_id"] and metadata["exposure"] == entries
    assert metadata["forbidden_literals_count"] > 100


def test_gen5_rejects_identical_splits(optimizer_cli, capsys):
    run, _, seed, optimize, _, _, ledger = optimizer_cli
    assert run([seed], [0.5], gen5=True, extra=("--train-split", "validation", "--val-split", "validation")) == 1
    assert "must differ" in capsys.readouterr().err
    optimize.assert_not_called()
    assert not ledger.exists()


def test_gen5_never_optimizes_on_final_test(optimizer_cli, capsys):
    run, _, seed, optimize, _, _, ledger = optimizer_cli
    assert run([seed], [0.5], gen5=True, extra=("--val-split", "final_test")) == 1
    assert "sealed" in capsys.readouterr().err
    optimize.assert_not_called()
    entries = [json.loads(line) for line in ledger.read_text().splitlines()] if ledger.exists() else []
    assert [e["split"] for e in entries] in ([], ["train"])  # train may be recorded first; final_test never is


@pytest.mark.parametrize("bundle", ["train.json", "validation.json", "final_test.json"])
def test_legacy_evalset_refuses_gen5_bundles(optimizer_cli, capsys, bundle):
    """--evalset never bypasses the ledger or the seal: every Gen 5 bundle is refused before any model object exists."""
    run, output_dir, seed, optimize, adapter, reflection, ledger = optimizer_cli
    rc = run([seed], [0.0], legacy_evalset=ROOT_DIR / "configs" / "evals" / "gen5" / bundle)
    assert rc == 1
    err = capsys.readouterr().err
    assert "Gen 5 bundle" in err and "--train-split" in err
    optimize.assert_not_called()
    adapter.assert_not_called()
    reflection.assert_not_called()
    assert not ledger.exists()
    assert not output_dir.exists()


def test_is_gen5_evalset_detection():
    """is_gen5_evalset detects top-level generation >= 5 or case-level generation >= 5."""
    assert not is_gen5_evalset({}, [{"eval_id": "case-1"}])
    assert is_gen5_evalset({"generation": 5}, [])
    assert is_gen5_evalset({}, [{"generation": 5}])


def test_cli_noise_only_writes_the_noise_floor_and_skips_optimization(optimizer_cli):
    from types import SimpleNamespace

    run, output_dir, seed, optimize, adapter, reflection, _ = optimizer_cli
    adapter.return_value.evaluate.side_effect = [
        SimpleNamespace(scores=[0.8, 0.7, 0.9, 0.6] * 5),
        SimpleNamespace(scores=[0.82, 0.66, 0.9, 0.62] * 5),
        SimpleNamespace(scores=[0.84, 0.74, 0.94, 0.64] * 5),
    ]
    assert run([seed], [0.5], gen5=True, extra=("--noise-runs", "3", "--noise-only")) == 0
    data = json.loads((output_dir / "noise_floor.json").read_text())
    assert data["runs"] == 3 and data["split"] == "validation" and len(data["per_case"]) == 20
    assert data["gate_mean_spread_max"] == 0.02 and data["gate_passed"] is False
    optimize.assert_not_called()
    reflection.assert_not_called()
    assert not (output_dir / CORE_RUNBOOKS[0]).exists()


def test_case_id_regex_matches_gen3_and_gen5_ids():
    from agent.gepa_runbook_optimizer import CASE_ID_REGEX

    for text in ("CASE-02", "CASE-GEN3-01", "CASE-GEN5-C2-INFOSTEALER-01", "case-33279"):
        assert CASE_ID_REGEX.search(text), text
    assert not CASE_ID_REGEX.search("CASE-STUDY")


def test_validate_runbook_candidate_rejects_manifest_literals():
    from agent.gepa_runbook_optimizer import load_forbidden_literals, validate_runbook_candidate

    manifest = Path("configs/evals/gen5/manifest.json")
    literals = load_forbidden_literals(manifest)
    hostname = next(x for x in literals if "-" in x and x.isupper())
    domain = next(x for x in literals if "." in x and x.islower() and not x[0].isdigit())
    clean = {name: "# Clean\nEnrich the alerted host, then decide." for name in CORE_RUNBOOKS}
    assert validate_runbook_candidate(clean, forbidden_literals=literals) == (True, [])

    leaky = dict(clean)
    leaky[CORE_RUNBOOKS[0]] = f"# Leaky\nIf the host is {hostname}, isolate it. Block {domain}."
    ok, violations = validate_runbook_candidate(leaky, forbidden_literals=literals)
    assert not ok and len(violations) == 2 and all("memorization" in v for v in violations)

    boundary = dict(clean)
    boundary[CORE_RUNBOOKS[0]] = f"# Boundary\nSee x{domain} and {hostname}X for unrelated names. Real mention: {domain}."
    ok, violations = validate_runbook_candidate(boundary, forbidden_literals=literals)
    assert not ok and len(violations) == 1 and domain in violations[0]


def test_calculate_loss_penalty_prohibited_entity_violation():
    from agent.gepa_runbook_optimizer import calculate_loss_penalty

    clean = calculate_loss_penalty("MALICIOUS", "MALICIOUS", ["isolate_host"], [])
    assert clean == pytest.approx(1.0)
    violated = calculate_loss_penalty("MALICIOUS", "MALICIOUS", ["isolate_host"], [], prohibited_violation=True)
    assert violated == pytest.approx(math.exp(-1.0))
    assert calculate_loss_penalty("MALICIOUS", "MALICIOUS", ["isolate_host"], [], prohibited_violation=False) == pytest.approx(1.0)


def _gen5_case(index: int = 0) -> dict:
    data = json.loads(Path("configs/evals/gen5/validation.json").read_text(encoding="utf-8"))
    return data["eval_cases"][index]


def _agent_factory_returning(trajectory, text):
    from types import SimpleNamespace

    class FakeAgent:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def query(self, prompt, max_iterations=None):
            return SimpleNamespace(response=text, trajectory=trajectory, usage={"prompt_tokens": 10, "completion_tokens": 5})

    return lambda **kwargs: FakeAgent(**kwargs)


def test_adapter_evaluate_gen5_inert_trajectory_scores_zero():
    from agent.gepa_runbook_optimizer import RunbookGEPAAdapter

    case = _gen5_case()
    adapter = RunbookGEPAAdapter(task_lm="mock", agent_factory=_agent_factory_returning([], ""))
    batch = adapter.evaluate([case], {name: "# Seed" for name in CORE_RUNBOOKS}, capture_traces=True)
    assert batch.scores == [0.0]
    trace = batch.trajectories[0]
    assert trace["inert"] is True and trace["generation"] == 5 and trace["family_id"] == case["family_id"]
    assert trace["usage"]["prompt_tokens"] == 10 and isinstance(trace["latency_ms"], int)


def test_adapter_evaluate_gen5_prohibited_entity_lowers_the_loss_penalty():
    from agent.gepa_runbook_optimizer import RunbookGEPAAdapter

    case = _gen5_case()
    victim = case["prohibited_entities"][0]
    first_lookup = case["oracle"]["lookups"][0]
    trajectory = [
        {"tool": first_lookup["tool"], "args": dict(first_lookup["args"]), "observation": {}},
        {"tool": "isolate_host", "args": {"hostname": victim}, "observation": {"status": "SUCCESS"}},
    ]
    text = "Contained.\n```soc_decision\n" + json.dumps({"verdict": case["ground_truth_label"], "recommended_actions": ["isolate_host"]}) + "\n```"
    adapter = RunbookGEPAAdapter(task_lm="mock", agent_factory=_agent_factory_returning(trajectory, text))
    batch = adapter.evaluate([case], {name: "# Seed" for name in CORE_RUNBOOKS}, capture_traces=True)
    trace = batch.trajectories[0]
    assert trace["prohibited_entity_violations"], "the verifier must flag the prohibited entity"
    assert trace["loss_penalty"] <= math.exp(-1.0) + 1e-9
    assert trace["inert"] is False

def test_zero_tool_hesitation_penalty():
    from agent.gepa_runbook_optimizer import RunbookGEPAAdapter
    
    # Fake verifier that returns zero tools
    def fake_agent_factory(**kwargs):
        from types import SimpleNamespace
        class FakeAgent:
            def query(self, prompt, max_iterations=None):
                return SimpleNamespace(response="Done.", trajectory=[], usage={}, classification="suspicious_login_triage.md")
        return FakeAgent()
        
    adapter = RunbookGEPAAdapter(task_lm="mock", agent_factory=fake_agent_factory)
    case = {"id": "C-1", "expected_actions": [], "prohibited_actions": [], "ground_truth_label": "BENIGN"}
    batch = adapter.evaluate([case], {"suspicious_login_triage.md": "# Seed"}, capture_traces=True)
    assert batch.scores[0] == 0.0
    trace = batch.trajectories[0]
    assert trace.get("zero_tool_hesitation") is True
    assert trace.get("epistemic_step_count") == 0
    assert trace.get("jev_choice") == "PREMATURE_TERMINATION_ZERO_TOOLS"
    assert trace.get("implicated_runbook") == "suspicious_login_triage.md"

def test_make_reflective_dataset_strict_attribution():
    from agent.gepa_runbook_optimizer import RunbookGEPAAdapter
    from agent.aqua_diagnostics import AquaDiagnosticReport, AquaInsightCluster
    import gepa
    adapter = RunbookGEPAAdapter(task_lm="mock")
    
    trajectories = [
        {
            "case_id": "c1", "alert_type": "suspicious_login_triage.md", "implicated_runbook": "suspicious_login_triage.md",
            "score": 0.0, "loss_penalty": 0.0, "assert_passed": False, "zero_tool_hesitation": True, "prompt": "p1"
        },
        {
            "case_id": "c2", "alert_type": "malware_triage.md", "implicated_runbook": "malware_triage.md",
            "score": 1.0, "loss_penalty": 1.0, "assert_passed": True, "zero_tool_hesitation": False, "inert": False
        }
    ]
    eval_batch = gepa.EvaluationBatch(outputs=["", ""], scores=[0.0, 1.0], trajectories=trajectories)
    candidate = {"suspicious_login_triage.md": "# A", "malware_triage.md": "# B"}
    
    dataset = adapter.make_reflective_dataset(candidate, eval_batch, list(candidate.keys()))
    
    assert "suspicious_login_triage.md" not in adapter.frozen_runbooks
    assert "malware_triage.md" in adapter.frozen_runbooks
    
    assert len(dataset["suspicious_login_triage.md"]) == 1
    assert "PREMATURE_TERMINATION_ZERO_TOOLS" in dataset["suspicious_login_triage.md"][0]["Feedback"]
    assert len(dataset["malware_triage.md"]) == 0

def test_enforce_frozen_runbooks():
    from agent.gepa_runbook_optimizer import enforce_frozen_runbooks
    
    candidate = {"A.md": "new A", "B.md": "new B"}
    seed = {"A.md": "seed A", "B.md": "seed B"}
    
    res = enforce_frozen_runbooks(candidate, seed, {"A.md"})
    assert res["A.md"] == "seed A"
    assert res["B.md"] == "new B"


def test_cli_always_on_validation_rejects_zero_tool_hesitation(optimizer_cli):
    run, output_dir, seed, optimize, adapter_class, _, _ = optimizer_cli
    
    import gepa
    
    # We want candidates = [seed, cand1]
    # GEPA aggregate scores: [0.5, 0.9] -> Cand1 has higher aggregate score.
    # We mock adapter_instance.evaluate to return per-case scores and trajectories.
    # For cand1, one of the trajectories will have zero_tool_hesitation = True.
    # evaluate_candidate_acceptance should reject cand1 due to REVERTED_CATEGORICAL_ZERO_TOOLS.
    
    def mock_evaluate(batch, candidate, capture_traces=False):
        if candidate == seed:
            # Seed baseline: perfect pass, no zero-tool hesitation
            trajectories = [
                {
                    "case_id": f"case-{i}",
                    "alert_type": "basic_ioc_enrichment.md",
                    "score": 0.5,
                    "zero_tool_hesitation": False,
                    "implicated_runbook": "basic_ioc_enrichment.md",
                    "inert": False,
                    "assert_passed": True,
                    "loss_penalty": 1.0,
                }
                for i in range(len(batch))
            ]
            return gepa.EvaluationBatch(
                outputs=["" for _ in batch],
                scores=[0.5 for _ in batch],
                trajectories=trajectories
            )
        else:
            # cand1: high score but has zero_tool_hesitation on case-0
            trajectories = [
                {
                    "case_id": f"case-{i}",
                    "alert_type": "basic_ioc_enrichment.md",
                    "score": 0.9,
                    "zero_tool_hesitation": (i == 0),
                    "implicated_runbook": "basic_ioc_enrichment.md",
                    "inert": False,
                    "assert_passed": True,
                    "loss_penalty": 1.0,
                }
                for i in range(len(batch))
            ]
            return gepa.EvaluationBatch(
                outputs=["" for _ in batch],
                scores=[0.9 for _ in batch],
                trajectories=trajectories
            )
            
    adapter_instance = adapter_class.return_value
    adapter_instance.evaluate.side_effect = mock_evaluate
    
    cand1 = {name: f"# Cand1\n{seed[name]}" for name in CORE_RUNBOOKS}
    candidates = [seed, cand1]
    scores = [0.5, 0.9]
    
    exit_code = run(candidates, scores, gen5=True)
    assert exit_code == 0
    
    # Cand1 should be rejected despite higher score, meaning seed is retained
    metadata_path = output_dir / "evolution_metadata.json"
    import json
    metadata = json.loads(metadata_path.read_text())
    assert metadata["selected_candidate_index"] == 0
    
    # Read hillclimb ledger
    ledger_text = (output_dir / "hillclimb_ledger.jsonl").read_text()
    entries = [json.loads(line) for line in ledger_text.splitlines() if line.strip()]
    assert len(entries) >= 2
    assert entries[1]["iteration"] == 1
    assert "ZERO_TOOLS" in entries[1]["decision"]
    
    # Check that aqua_diagnostic_report.json was written
    report_path = output_dir / "aqua_diagnostic_report.json"
    assert report_path.exists()
    assert "aqua_diagnostics_summary" in metadata

