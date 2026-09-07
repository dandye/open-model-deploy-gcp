"""Offline launch/transport/recovery tests; no Google Cloud calls are made."""

from dataclasses import asdict
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from scripts.experiment_run import load_run, new_run, identity_error, write_json
from scripts.run_gce_spot_sweep import ALL_GCE_SPOT_TARGETS, GCESpotOrchestrator, main

TARGET = ALL_GCE_SPOT_TARGETS[0]


def response(code=0, stdout="", stderr=""):
    return SimpleNamespace(returncode=code, stdout=stdout, stderr=stderr)


@pytest.fixture
def launch(tmp_path):
    orch = GCESpotOrchestrator(project_id="saved-project", zone="us-central1-a",
                               output_gcs_bucket="gs://bucket/evals", evidence_dir=tmp_path)
    with patch("subprocess.run", return_value=response()):
        orch.launch_instance(TARGET)
    return orch, orch.current_run, tmp_path / orch.current_run["run_id"] / "launch.json"


def payloads(run):
    identity = {"run_id": run["run_id"], "configuration_hash": run["configuration_hash"],
                "flavor": TARGET.flavor}
    return {
        f"soc_tier1_eval_results_{TARGET.flavor}.json": {
            **identity, "status": "COMPLETED", "case_results": [{"usage": {"total_tokens": 42}, "latency_s": 1.2}],
        },
        "lifecycle_status.json": {**identity, "evaluation": {"status": "COMPLETED", "benchmark_status": "COMPLETED"},
                                  "artifacts": {"upload_status": "COMMAND_SUCCEEDED"}},
        f"benchmark_{TARGET.flavor}.log": "evaluation log",
        "benchmark_sample_output.json": {"choices": [{"text": "sample output"}], "usage": {"total_tokens": 42}},
    }


def transport(files):
    def copy(cmd, **kwargs):
        name = cmd[-2].rsplit("/", 1)[-1]
        if name not in files:
            return response(1)
        value = files[name]
        Path(cmd[-1]).write_text(value if isinstance(value, str) else json.dumps(value))
        return response()
    return copy


def test_same_flavor_launches_have_distinct_names_paths_and_durable_records(tmp_path):
    orch = GCESpotOrchestrator(evidence_dir=tmp_path)
    seen = []
    def create(cmd, **kwargs):
        run = orch.current_run
        saved = load_run(tmp_path / run["run_id"] / "launch.json")
        assert saved["launch_status"] == "CREATE_REQUESTED"
        metadata = next(v for v in cmd if v.startswith("--metadata="))
        assert f"run_id={run['run_id']}" in metadata
        assert f"configuration_hash={run['configuration_hash']}" in metadata
        assert f"/runs/{run['run_id']}" in metadata
        seen.append(saved)
        return response()
    with patch("subprocess.run", side_effect=create):
        first = orch.launch_instance(TARGET)
        second = orch.launch_instance(TARGET)
    assert first != second
    assert seen[0]["artifact_uri"] != seen[1]["artifact_uri"]


def test_zone_fallback_persists_distinct_attempt_before_creation(tmp_path):
    orch = GCESpotOrchestrator(zone="us-central1-a", evidence_dir=tmp_path)
    attempts = []
    def create(cmd, **kwargs):
        saved = load_run(tmp_path / orch.current_run["run_id"] / "launch.json")
        assert f"--zone={saved['configuration']['zone']}" in cmd
        attempts.append(saved)
        return response(1, stderr="ZONE_RESOURCE_POOL_EXHAUSTED") if len(attempts) == 1 else response()
    with patch("subprocess.run", side_effect=create):
        orch.launch_instance(TARGET)
    assert len(attempts) == 2
    assert attempts[0]["run_id"] != attempts[1]["run_id"]
    assert attempts[0]["configuration_hash"] != attempts[1]["configuration_hash"]
    assert load_run(tmp_path / attempts[0]["run_id"] / "launch.json")["launch_status"] == "STOCKOUT"


def test_interrupted_creation_preserves_recoverable_record_without_retry(tmp_path):
    orch = GCESpotOrchestrator(evidence_dir=tmp_path)
    with patch("subprocess.run", side_effect=KeyboardInterrupt) as create:
        with pytest.raises(KeyboardInterrupt):
            orch.launch_instance(TARGET)
    create.assert_called_once()
    saved = load_run(tmp_path / orch.current_run["run_id"] / "launch.json")
    assert saved["launch_status"] == "CREATE_OUTCOME_UNKNOWN"


@pytest.mark.parametrize("kind", ["evaluation", "lifecycle"])
@pytest.mark.parametrize("field,value", [("run_id", "old-run"), ("configuration_hash", "0" * 64), ("run_id", None)])
def test_mismatched_or_missing_identity_is_rejected(launch, kind, field, value):
    orch, run, _ = launch
    files = payloads(run)
    name = f"soc_tier1_eval_results_{TARGET.flavor}.json" if kind == "evaluation" else "lifecycle_status.json"
    files[name][field] = value
    with patch("subprocess.run", side_effect=transport(files)):
        result = orch.collect_results(TARGET)
    assert result["artifact_collection"]["records"][kind]["status"] == "REJECTED"
    assert result["artifact_evidence_status"] == "PARTIAL"
    if kind == "evaluation":
        assert result["status"] == "UNVERIFIED"
        assert result["case_results"] == []


def test_success_preserves_case_usage_and_hashes_all_downloads(launch):
    orch, run, _ = launch
    with patch("subprocess.run", side_effect=transport(payloads(run))):
        result = orch.collect_results(TARGET)
    assert result["status"] == "COMPLETED"
    assert result["artifact_evidence_status"] == "COMPLETE"
    assert result["case_results"][0]["usage"]["total_tokens"] == 42
    assert result["cleanup"]["status"] == "UNVERIFIED"
    assert all(len(r["sha256"]) == 64 for r in result["artifact_collection"]["records"].values())


def test_failed_transport_never_reuses_prior_or_partial_download(launch):
    orch, run, _ = launch
    with patch("subprocess.run", side_effect=transport(payloads(run))):
        assert orch.collect_results(TARGET)["status"] == "COMPLETED"
    destinations = []
    def partial(cmd, **kwargs):
        destinations.append(cmd[-1])
        if cmd[0] == "gcloud":
            Path(cmd[-1]).write_text(json.dumps(payloads(run)[f"soc_tier1_eval_results_{TARGET.flavor}.json"]))
            return response(1)
        return response()  # Success without producing a file cannot use previous attempt.
    with patch("subprocess.run", side_effect=partial):
        result = orch.collect_results(TARGET)
    assert result["status"] == "UNVERIFIED"
    assert len(set(destinations)) == len(destinations)


@pytest.mark.parametrize("upload", ["FAILED", "REQUESTED", "NOT_REQUESTED"])
def test_incomplete_upload_never_becomes_complete_evidence(launch, upload):
    orch, run, _ = launch
    files = payloads(run)
    files["lifecycle_status.json"]["artifacts"]["upload_status"] = upload
    with patch("subprocess.run", side_effect=transport(files)):
        result = orch.collect_results(TARGET)
    assert result["evaluation_status"] == "COMPLETED"
    assert result["artifact_evidence_status"] == "PARTIAL"


def test_failed_evaluation_survives_successful_collection_and_cleanup(launch):
    _, run, path = launch
    files = payloads(run)
    files[f"soc_tier1_eval_results_{TARGET.flavor}.json"]["status"] = "FAILED"
    def cloud(cmd, **kwargs):
        if "describe" in cmd:
            assert "--project=saved-project" in cmd
            assert "--zone=us-central1-a" in cmd
            return response(1, stderr="The resource 'projects/saved-project/zones/us-central1-a/instances/test' was not found")
        assert "create" not in cmd and "delete" not in cmd
        return transport(files)(cmd, **kwargs)
    recovering = GCESpotOrchestrator(project_id="wrong-default", zone="wrong-zone")
    with patch("subprocess.run", side_effect=cloud):
        result = recovering.recover_run(path)
    assert result["status"] == "FAILED"
    assert result["cleanup"]["status"] == "ABSENT_OBSERVED"


def test_cleanup_refuses_mismatched_resource(launch):
    orch, run, _ = launch
    instance = {"id": "123", "metadata": {"items": [{"key": "run_id", "value": "different"}]}}
    with patch("subprocess.run", return_value=response(stdout=json.dumps(instance))) as cloud:
        result = orch.observe_cleanup(run, request_delete=True)
    cloud.assert_called_once()
    assert result["status"] == "IDENTITY_MISMATCH"
    assert not result["delete_requested"]


def test_cleanup_requests_delete_then_observes_absence(launch):
    orch, run, _ = launch
    instance = {"id": "123", "metadata": {"items": [
        {"key": "run_id", "value": run["run_id"]},
        {"key": "configuration_hash", "value": run["configuration_hash"]}]}}
    with patch("subprocess.run", side_effect=[response(stdout=json.dumps(instance)), response(),
               response(1, stderr="The resource was not found")]) as cloud:
        result = orch.observe_cleanup(run, request_delete=True)
    assert cloud.call_count == 3
    assert "delete" in cloud.call_args_list[1].args[0]
    assert result["delete_requested"] and result["status"] == "ABSENT_OBSERVED"


@pytest.mark.parametrize("error", ["account not found", "permission denied", "network failed"])
def test_cleanup_never_claims_absence_on_unrelated_errors(launch, error):
    orch, run, _ = launch
    with patch("subprocess.run", return_value=response(1, stderr=error)):
        assert orch.observe_cleanup(run)["status"] == "STATE_CHECK_FAILED"


def test_tampered_manifest_rejected_before_cloud_access(launch):
    orch, run, path = launch
    run["configuration"]["zone"] = "tampered-zone"
    write_json(path, run)
    with patch("subprocess.run") as cloud, pytest.raises(ValueError, match="hash"):
        orch.recover_run(path)
    cloud.assert_not_called()


def test_conflicting_duplicate_identity_is_rejected(launch):
    _, run, _ = launch
    artifact = payloads(run)[f"soc_tier1_eval_results_{TARGET.flavor}.json"]
    artifact["provenance"] = {"run_id": "stale"}
    assert identity_error(artifact, run)


def test_dry_run_does_not_write_launch_records_or_leak_tokens(tmp_path, capsys):
    orch = GCESpotOrchestrator(dry_run=True, hf_token="private-token", evidence_dir=tmp_path)
    with patch("subprocess.run") as cloud:
        orch.launch_instance(TARGET)
    cloud.assert_not_called()
    assert "private-token" not in capsys.readouterr().out
    assert list(tmp_path.iterdir()) == []
    assert orch.current_run["launch_status"] == "SYNTHETIC"


@pytest.mark.parametrize("sample", ["not JSON", {"error": {"message": "outage"}},
                                      {"choices": []}, {"choices": [{"text": ""}]},
                                      {"choices": [{"text": "partial", "finish_reason": "error"}]}])
def test_invalid_or_failed_benchmark_cannot_complete_evidence(launch, sample):
    orch, run, _ = launch
    files = payloads(run)
    files["benchmark_sample_output.json"] = sample
    with patch("subprocess.run", side_effect=transport(files)):
        result = orch.collect_results(TARGET)
    assert result["artifact_evidence_status"] == "PARTIAL"
    assert result["artifact_collection"]["records"]["benchmark"]["status"] == "REJECTED"


@pytest.mark.parametrize("field", ["artifacts", "evaluation"])
@pytest.mark.parametrize("malformed", [None, [], "bad"])
def test_malformed_lifecycle_still_allows_recovery_observation(launch, field, malformed):
    orch, run, path = launch
    files = payloads(run)
    files["lifecycle_status.json"][field] = malformed
    with patch("subprocess.run", side_effect=transport(files)), \
         patch.object(orch, "observe_cleanup", return_value={"status": "ABSENT_OBSERVED"}) as observe:
        result = orch.recover_run(path)
    observe.assert_called_once()
    assert result["artifact_evidence_status"] == "PARTIAL"
    assert result["cleanup"]["status"] == "ABSENT_OBSERVED"


def test_recovery_transport_timeouts_are_partial_evidence(launch):
    import subprocess
    orch, run, path = launch
    def timeout(cmd, **kwargs):
        assert kwargs["timeout"] == 60
        raise subprocess.TimeoutExpired(cmd, 60)
    with patch("subprocess.run", side_effect=timeout):
        result = orch.recover_run(path)
    assert result["artifact_evidence_status"] == "PARTIAL"
    assert result["cleanup"]["status"] == "STATE_CHECK_FAILED"


def test_create_timeout_never_discloses_token_in_errors_or_console(tmp_path, capsys):
    import subprocess
    orch = GCESpotOrchestrator(hf_token="test-secret-token", evidence_dir=tmp_path)
    def timeout(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 60)
    with patch("subprocess.run", side_effect=timeout):
        results = orch.run_sweep(models_filter=[TARGET.flavor])
    assert "test-secret-token" not in capsys.readouterr().out
    assert "test-secret-token" not in json.dumps(results)
    assert results[0]["status"] == "CREATE_OUTCOME_UNKNOWN"
    assert "test-secret-token" not in (tmp_path / orch.current_run["run_id"] / "launch.json").read_text()


def test_delete_timeout_preserves_request_and_unknown_outcome(launch):
    import subprocess
    orch, run, _ = launch
    instance = {"id": "123", "metadata": {"items": [
        {"key": "run_id", "value": run["run_id"]},
        {"key": "configuration_hash", "value": run["configuration_hash"]}]}}
    with patch("subprocess.run", side_effect=[response(stdout=json.dumps(instance)),
                                               subprocess.TimeoutExpired("gcloud delete", 60)]):
        result = orch.observe_cleanup(run, request_delete=True)
    assert result["delete_requested"] is True
    assert result["delete_command_succeeded"] is None
    assert result["status"] == "DELETE_OUTCOME_UNKNOWN"
    assert result["resource"]["provider_id"] == "123"


def test_empty_log_cannot_complete_evidence(launch):
    orch, run, _ = launch
    files = payloads(run)
    files[f"benchmark_{TARGET.flavor}.log"] = ""
    with patch("subprocess.run", side_effect=transport(files)):
        result = orch.collect_results(TARGET)
    assert result["artifact_evidence_status"] == "PARTIAL"
    assert result["artifact_collection"]["records"]["logs"]["status"] == "REJECTED"


def test_each_recovery_snapshot_retains_its_cleanup_observation(launch):
    orch, run, manifest = launch
    with patch("subprocess.run", side_effect=transport(payloads(run))), \
         patch.object(orch, "observe_cleanup", side_effect=[
             {"status": "PRESENT", "resource": {"provider_id": "123"}},
             {"status": "ABSENT_OBSERVED"},
         ]):
        first = orch.recover_run(manifest)
        second = orch.recover_run(manifest)
    assert first["collection_directory"] != second["collection_directory"]
    for result in (first, second):
        saved = json.loads((Path(result["collection_directory"]) / "evidence.json").read_text())
        assert saved["cleanup"] == result["cleanup"]
    assert json.loads((manifest.parent / "evidence.json").read_text())["cleanup"] == second["cleanup"]


def test_monitor_timeout_is_bounded_and_allows_collection(launch):
    import subprocess
    orch, run, _ = launch
    def timeout(cmd, **kwargs):
        assert 0 < kwargs["timeout"] <= 5
        raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])
    with patch("subprocess.run", side_effect=timeout):
        assert orch.monitor_instance_serial(run["instance_name"], timeout_seconds=5) is False
    assert orch.last_monitor_outcome == "STATE_CHECK_FAILED"
