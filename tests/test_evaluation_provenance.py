import hashlib
from pathlib import Path
import subprocess

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
