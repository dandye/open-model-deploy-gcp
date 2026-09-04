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
