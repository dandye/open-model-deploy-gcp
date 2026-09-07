import hashlib
from pathlib import Path
import subprocess
import uuid

from scripts.evaluation_provenance import capture_provenance


def test_observed_inputs_change_identity_without_claiming_resolved_model(tmp_path: Path):
    dataset = tmp_path / "dataset.json"
    dataset.write_text('{"eval_cases": []}')
    first = capture_provenance(tmp_path, dataset, {"flavor": "fixture"})
    assert first["dataset"]["sha256"] == hashlib.sha256(dataset.read_bytes()).hexdigest()
    assert first["source_commit"] is None
    assert first["source_identity"]["status"] == "unknown"
    assert first["source_identity"]["reason"]
    assert first["model"]["resolved_revision"] is None
    assert first["logs"] == []
    assert first["lifecycle"]["cleanup"] == "unverified"
    assert first["runbook"]["status"] == "not_applicable"
    second = capture_provenance(tmp_path, dataset, {"flavor": "different"})
    assert first["configuration_hash"] != second["configuration_hash"]
    assert first["run_id"] != second["run_id"]


def test_missing_inputs_are_explicit(tmp_path: Path):
    provenance = capture_provenance(tmp_path, tmp_path / "missing.json", {}, tmp_path / "missing-runbooks")
    assert provenance["dataset"]["sha256"] is None
    assert provenance["runbook"]["status"] == "unavailable"
    assert all(file["status"] == "unavailable" for file in provenance["evaluator"]["files"])


def test_runbooks_fingerprinted_without_storing_content(tmp_path: Path):
    runbooks = tmp_path / "runbooks"
    runbooks.mkdir()
    book = runbooks / "triage.md"
    book.write_text("# Synthetic runbook")
    first = capture_provenance(tmp_path, tmp_path / "missing.json", {}, runbooks)
    assert first["runbook"]["files"][0]["sha256"] == hashlib.sha256(book.read_bytes()).hexdigest()
    assert "Synthetic runbook" not in str(first)
    book.write_text("# Changed runbook")
    second = capture_provenance(tmp_path, tmp_path / "missing.json", {}, runbooks)
    assert first["runbook"]["files"] != second["runbook"]["files"]


def test_git_dirty_state_preserved(tmp_path: Path):
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    dataset = tmp_path / "data.json"
    dataset.write_text("{}")
    provenance = capture_provenance(tmp_path, dataset, {})
    assert provenance["source_dirty"] is True


def test_launch_identity_is_reused_and_keeps_launch_hash_separate(tmp_path: Path, monkeypatch):
    run_id = str(uuid.uuid4())
    launch_hash = "a" * 64
    monkeypatch.setenv("EXPERIMENT_RUN_ID", run_id)
    monkeypatch.setenv("EXPERIMENT_CONFIGURATION_HASH", launch_hash)

    provenance = capture_provenance(tmp_path, tmp_path / "dataset.json", {"flavor": "fixture"})

    assert provenance["run_id"] == run_id
    assert provenance["launch_configuration_hash"] == launch_hash
    assert provenance["configuration_hash"] != launch_hash


def test_launch_identity_requires_both_valid_values(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("EXPERIMENT_RUN_ID", str(uuid.uuid4()))
    monkeypatch.delenv("EXPERIMENT_CONFIGURATION_HASH", raising=False)
    try:
        capture_provenance(tmp_path, tmp_path / "dataset.json", {})
    except ValueError as exc:
        assert "supplied together" in str(exc)
    else:
        raise AssertionError("incomplete launch identity must be rejected")

    monkeypatch.setenv("EXPERIMENT_CONFIGURATION_HASH", "A" * 64)
    try:
        capture_provenance(tmp_path, tmp_path / "dataset.json", {})
    except ValueError as exc:
        assert "lowercase hexadecimal" in str(exc)
    else:
        raise AssertionError("unsafe launch configuration hash must be rejected")


def test_standalone_captures_get_independent_ids_without_launch_claim(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("EXPERIMENT_RUN_ID", raising=False)
    monkeypatch.delenv("EXPERIMENT_CONFIGURATION_HASH", raising=False)
    first = capture_provenance(tmp_path, tmp_path / "dataset.json", {})
    second = capture_provenance(tmp_path, tmp_path / "dataset.json", {})

    assert first["run_id"] != second["run_id"]
    assert first["launch_configuration_hash"] is None
    assert second["launch_configuration_hash"] is None
