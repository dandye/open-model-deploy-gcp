"""Source pinning across launch metadata, startup provenance, and result collection."""

from pathlib import Path
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from scripts.evaluation_provenance import capture_provenance
from scripts.run_gce_spot_sweep import ALL_GCE_SPOT_TARGETS, GCESpotOrchestrator, ROOT_DIR, main

SOURCE = {"source_bundle_uri": "gs://fixture/source/code.tar.gz",
          "source_bundle_sha256": "a" * 64, "source_commit": "b" * 40}
TARGET = ALL_GCE_SPOT_TARGETS[0]


@pytest.mark.parametrize("override", [
    {"source_commit": None}, {"source_bundle_sha256": "bad"}, {"source_commit": "main"},
    {"source_bundle_uri": "gs://bucket/prefix/*"}, {"source_bundle_uri": "https://example.com/code"},
    {"source_bundle_uri": "gs://bucket/a|~|injected=value"},
])
def test_invalid_source_request_fails_before_launch(override):
    with patch("subprocess.run") as cloud, pytest.raises(ValueError):
        GCESpotOrchestrator(**{**SOURCE, **override})
    cloud.assert_not_called()


def test_launch_hash_binds_source_and_verifier_metadata(tmp_path):
    orch = GCESpotOrchestrator(**SOURCE, evidence_dir=tmp_path)
    with patch("subprocess.run", return_value=SimpleNamespace(returncode=0, stdout="", stderr="")) as cloud:
        orch.launch_instance(TARGET)
    run = orch.current_run
    source = run["configuration"]["source_bundle"]
    assert source["sha256"] == SOURCE["source_bundle_sha256"]
    assert source["source_commit"] == SOURCE["source_commit"]
    assert source["verifier_sha256"] == hashlib.sha256((ROOT_DIR / "scripts/source_bundle.py").read_bytes()).hexdigest()
    cmd = cloud.call_args.args[0]
    metadata = next(arg for arg in cmd if arg.startswith("--metadata="))
    for field, value in {"source_bundle_uri": source["uri"], "source_bundle_sha256": source["sha256"],
                         "source_commit": source["source_commit"], "source_verifier_sha256": source["verifier_sha256"]}.items():
        assert f"{field}={value}" in metadata
    assert any("source-verifier=" in arg and "source_bundle.py" in arg for arg in cmd)
    saved = json.loads((tmp_path / run["run_id"] / "launch.json").read_text())
    assert saved["configuration"]["source_bundle"] == source


def test_provenance_records_verified_startup_bundle_without_claiming_clean_checkout(tmp_path, monkeypatch):
    monkeypatch.setenv("EXPERIMENT_SOURCE_VERIFIED", "1")
    monkeypatch.setenv("EXPERIMENT_SOURCE_BUNDLE_SHA256", SOURCE["source_bundle_sha256"])
    monkeypatch.setenv("EXPERIMENT_SOURCE_COMMIT", SOURCE["source_commit"])
    dataset = tmp_path / "cases.json"
    dataset.write_text('{}')
    provenance = capture_provenance(tmp_path, dataset, {})
    assert provenance["source_commit"] == SOURCE["source_commit"]
    assert provenance["source_bundle"]["status"] == "VERIFIED"
    assert provenance["source_dirty"] is None
    assert provenance["verification_status"] == "partial_observed_inputs"
    assert provenance["model"]["resolved_revision"] is None


@pytest.mark.parametrize("flag", [None, "0", "true"])
def test_source_commit_echo_without_verification_fails(tmp_path, monkeypatch, flag):
    monkeypatch.delenv("EXPERIMENT_SOURCE_VERIFIED", raising=False)
    if flag is not None:
        monkeypatch.setenv("EXPERIMENT_SOURCE_VERIFIED", flag)
    monkeypatch.setenv("EXPERIMENT_SOURCE_BUNDLE_SHA256", SOURCE["source_bundle_sha256"])
    monkeypatch.setenv("EXPERIMENT_SOURCE_COMMIT", SOURCE["source_commit"])
    with pytest.raises(ValueError, match="verified source"):
        capture_provenance(tmp_path, tmp_path / "cases.json", {})


@pytest.mark.parametrize("mismatch", [None, "digest", "commit", "status", "missing"])
def test_collector_requires_source_evidence_from_both_producers(tmp_path, mismatch):
    orch = GCESpotOrchestrator(**SOURCE, evidence_dir=tmp_path)
    with patch("subprocess.run", return_value=SimpleNamespace(returncode=0, stdout="", stderr="")):
        orch.launch_instance(TARGET)
    run = orch.current_run
    observed = {"status": "VERIFIED", "sha256": SOURCE["source_bundle_sha256"], "source_commit": SOURCE["source_commit"]}
    evaluator_observed = dict(observed)
    if mismatch == "digest": evaluator_observed["sha256"] = "c" * 64
    if mismatch == "commit": evaluator_observed["source_commit"] = "c" * 40
    if mismatch == "status": evaluator_observed["status"] = "REQUESTED"
    if mismatch == "missing": evaluator_observed = None
    identity = {"run_id": run["run_id"], "configuration_hash": run["configuration_hash"], "flavor": TARGET.flavor}
    files = {
        f"soc_tier1_eval_results_{TARGET.flavor}.json": {**identity, "status": "COMPLETED", "provenance": {"source_bundle": evaluator_observed}},
        "lifecycle_status.json": {**identity, "source_bundle": observed, "evaluation": {"status": "COMPLETED", "benchmark_status": "COMPLETED"},
                                  "artifacts": {"upload_status": "COMMAND_SUCCEEDED"}},
        f"benchmark_{TARGET.flavor}.log": "evaluated",
        "benchmark_sample_output.json": {"choices": [{"text": "hello"}]},
    }
    def download(cmd, **kwargs):
        value = files[cmd[-2].rsplit('/', 1)[-1]]
        Path(cmd[-1]).write_text(value if isinstance(value, str) else json.dumps(value))
        return SimpleNamespace(returncode=0)
    with patch("subprocess.run", side_effect=download):
        evidence = orch.collect_results(TARGET)
    assert evidence["source_verification"]["status"] == ("VERIFIED" if mismatch is None else "UNVERIFIED")
    assert evidence["artifact_evidence_status"] == ("COMPLETE" if mismatch is None else "PARTIAL")


def test_cli_refuses_unpinned_live_launch_before_cloud(monkeypatch):
    monkeypatch.setattr('sys.argv', ['run_gce_spot_sweep.py', '--models', TARGET.flavor])
    with patch("subprocess.run") as cloud, pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    cloud.assert_not_called()


def test_cli_inherits_source_pins_for_existing_just_recipes(monkeypatch, capsys):
    monkeypatch.setenv("GCE_SOURCE_BUNDLE_URI", SOURCE["source_bundle_uri"])
    monkeypatch.setenv("GCE_SOURCE_BUNDLE_SHA256", SOURCE["source_bundle_sha256"])
    monkeypatch.setenv("GCE_SOURCE_COMMIT", SOURCE["source_commit"])
    monkeypatch.setattr('sys.argv', ['run_gce_spot_sweep.py', '--models', TARGET.flavor, '--dry-run'])
    with patch("subprocess.run") as cloud:
        assert main() == 0
    cloud.assert_not_called()
    assert f"source_bundle_sha256={SOURCE['source_bundle_sha256']}" in capsys.readouterr().out


def test_recovery_ignores_environment_source_defaults(monkeypatch):
    monkeypatch.setenv("GCE_SOURCE_BUNDLE_URI", "gs://other/wrong.tar.gz")
    monkeypatch.setenv("GCE_SOURCE_BUNDLE_SHA256", "c" * 64)
    monkeypatch.setenv("GCE_SOURCE_COMMIT", "d" * 40)
    monkeypatch.setattr('sys.argv', ['run_gce_spot_sweep.py', '--recover', 'saved-launch.json'])
    with patch.object(GCESpotOrchestrator, 'recover_run', return_value={
        'evaluation_status': 'COMPLETED', 'artifact_evidence_status': 'COMPLETE',
        'cleanup': {'status': 'ABSENT_OBSERVED'},
    }) as recover:
        assert main() == 0
    recover.assert_called_once_with(Path('saved-launch.json'), cleanup=False)
