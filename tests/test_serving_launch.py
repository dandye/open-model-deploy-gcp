import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.experiment_run import new_run, validate_run
from scripts.run_gce_spot_sweep import (
    GCESpotOrchestrator,
    ALL_GCE_SPOT_TARGETS,
    build_gce_spot_create_command,
)
from scripts.serving_config import serving_config_hash


def _config(target):
    return {
        "schema_version": 1,
        "target_flavor": target.flavor,
        "model_repository": target.hf_repo,
        "model_revision": "a" * 40,
        "serving_image": "registry.example/serving@sha256:" + "b" * 64,
        "evaluator_image": "registry.example/evaluator@sha256:" + "c" * 64,
        "boot_image": "projects/test-project/global/images/pinned-image",
        "parameters": {
            "tensor_parallel_size": target.tensor_parallel_size,
            "max_model_len": 4096,
            "gpu_memory_utilization": 0.9,
        },
    }


def test_pinned_create_command_uses_exact_image_and_sidecar(tmp_path):
    target = ALL_GCE_SPOT_TARGETS[0]
    config = _config(target)
    sidecar = tmp_path / "serving-config.json"
    sidecar.write_bytes(json.dumps(config, sort_keys=True, separators=(",", ":")).encode())
    command = build_gce_spot_create_command(
        target, "project", "zone-a", "gs://bucket/runs/id",
        image_family="wrong-family", image_project="wrong-project",
        run_id="a" * 32, configuration_hash="d" * 64,
        source_bundle={"uri": "gs://bucket/source.tar.gz", "sha256": "e" * 64,
                       "source_commit": "f" * 40, "verifier_sha256": "1" * 64},
        serving_config=config, serving_config_path=sidecar,
    )
    assert "--image=projects/test-project/global/images/pinned-image" in command
    assert not any(arg.startswith("--image-family=") or arg.startswith("--image-project=") for arg in command)
    assert f"serving_config_sha256={serving_config_hash(config)}" in next(a for a in command if a.startswith("--metadata="))
    assert f"serving-config={sidecar}" in next(a for a in command if a.startswith("--metadata-from-file="))


def test_serving_config_requires_source_pin():
    target = ALL_GCE_SPOT_TARGETS[0]
    with pytest.raises(ValueError, match="source bundle"):
        GCESpotOrchestrator(dry_run=True, serving_config=_config(target))


def test_low_level_builder_rejects_serving_config_without_source(tmp_path):
    target = ALL_GCE_SPOT_TARGETS[0]
    with pytest.raises(ValueError, match="source bundle"):
        build_gce_spot_create_command(
            target, "project", "zone-a", "gs://bucket/runs/id",
            serving_config=_config(target), serving_config_path=tmp_path / "serving-config.json",
        )


def test_live_launch_snapshots_canonical_serving_sidecar(tmp_path, monkeypatch):
    target = ALL_GCE_SPOT_TARGETS[0]
    config = _config(target)
    orchestrator = GCESpotOrchestrator(
        evidence_dir=tmp_path, source_bundle_uri="gs://bucket/source.tar.gz",
        source_bundle_sha256="e" * 64, source_commit="f" * 40,
        serving_config=config,
    )
    config["parameters"]["max_model_len"] = 8192
    monkeypatch.setattr("scripts.run_gce_spot_sweep.subprocess.run",
                        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""))
    orchestrator.launch_instance(target)
    run = orchestrator.current_run
    sidecar = tmp_path / run["run_id"] / "serving-config.json"
    assert json.loads(sidecar.read_text()) == _config(target)
    assert sidecar.read_bytes() == json.dumps(_config(target), sort_keys=True, separators=(",", ":")).encode()


def test_serving_config_is_validated_before_launch():
    target = ALL_GCE_SPOT_TARGETS[0]
    config = _config(target)
    config["target_flavor"] = "other"
    orchestrator = GCESpotOrchestrator(
        dry_run=True, source_bundle_uri="gs://bucket/source.tar.gz",
        source_bundle_sha256="e" * 64, source_commit="f" * 40,
        serving_config=config,
    )
    with pytest.raises(ValueError, match="target"):
        orchestrator.run_sweep(models_filter=[target.flavor], wait=False)


def test_dry_run_does_not_write_launch_manifest_or_sidecar(tmp_path):
    target = ALL_GCE_SPOT_TARGETS[0]
    orchestrator = GCESpotOrchestrator(dry_run=True, evidence_dir=tmp_path)
    orchestrator.launch_instance(target)
    assert not list(tmp_path.rglob("launch.json"))
    assert not list(tmp_path.rglob("serving-config.json"))


def test_validate_run_rejects_serving_config_without_source():
    target = ALL_GCE_SPOT_TARGETS[0]
    config = {"target": {"flavor": target.flavor}, "project_id": "project", "zone": "zone-a",
              "serving_config": _config(target)}
    run = new_run(config, "gs://bucket")
    with pytest.raises(ValueError, match="source bundle"):
        validate_run(run)


@pytest.mark.parametrize('problem', [None, 'missing', 'config', 'serving_id', 'evaluator_id', 'status'])
def test_collector_requires_matching_runtime_evidence(tmp_path, monkeypatch, problem):
    import copy
    target = ALL_GCE_SPOT_TARGETS[0]
    config = _config(target)
    orch = GCESpotOrchestrator(evidence_dir=tmp_path, serving_config=config,
                              source_bundle_uri='gs://bucket/code.tar.gz',
                              source_bundle_sha256='d' * 64, source_commit='e' * 40)
    monkeypatch.setattr('subprocess.run', lambda *a, **kw: SimpleNamespace(returncode=0, stdout='', stderr=''))
    orch.launch_instance(target)
    run = orch.current_run
    identity = {'run_id': run['run_id'], 'configuration_hash': run['configuration_hash'], 'flavor': target.flavor}
    runtime = {'status': 'PINNED_IMAGES_VERIFIED', 'scope': 'container_image_ids_and_requested_model_revision',
               'configuration': config, 'configuration_hash': serving_config_hash(config),
               'serving_image_id': 'sha256:' + '1' * 64, 'evaluator_image_id': 'sha256:' + '2' * 64}
    observed = copy.deepcopy(runtime)
    if problem == 'missing': observed = None
    if problem == 'config': observed['configuration']['model_revision'] = 'f' * 40
    if problem == 'serving_id': observed['serving_image_id'] = 'sha256:' + '3' * 64
    if problem == 'evaluator_id': observed['evaluator_image_id'] = 'sha256:' + '3' * 64
    if problem == 'status': observed['status'] = 'SERVER_STARTED'
    source = {'status': 'VERIFIED', 'sha256': 'd' * 64, 'source_commit': 'e' * 40}
    files = {
        f'soc_tier1_eval_results_{target.flavor}.json': {**identity, 'status': 'COMPLETED',
            'provenance': {'source_bundle': source, 'serving_runtime': observed}},
        'lifecycle_status.json': {**identity, 'source_bundle': source, 'serving_runtime': runtime,
            'evaluation': {'status': 'COMPLETED', 'benchmark_status': 'COMPLETED'},
            'artifacts': {'upload_status': 'COMMAND_SUCCEEDED'}},
        f'benchmark_{target.flavor}.log': 'evaluated',
        'benchmark_sample_output.json': {'choices': [{'text': 'hello'}]},
    }
    def download(cmd, **kwargs):
        value = files[cmd[-2].rsplit('/', 1)[-1]]
        Path(cmd[-1]).write_text(value if isinstance(value, str) else json.dumps(value))
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr('subprocess.run', download)
    result = orch.collect_results(target)
    assert result['serving_verification']['status'] == ('VERIFIED' if problem is None else 'UNVERIFIED')
    assert result['artifact_evidence_status'] == ('COMPLETE' if problem is None else 'PARTIAL')


@pytest.mark.parametrize('mode', ['missing', 'environment', 'recovery', 'override'])
def test_cli_serving_pin_policy(tmp_path, monkeypatch, mode):
    from unittest.mock import patch
    from scripts.run_gce_spot_sweep import main
    for key in ('GCE_SOURCE_BUNDLE_URI', 'GCE_SOURCE_BUNDLE_SHA256', 'GCE_SOURCE_COMMIT', 'GCE_SERVING_CONFIG'):
        monkeypatch.delenv(key, raising=False)
    config = tmp_path / 'serving.json'
    config.write_text(json.dumps(_config(ALL_GCE_SPOT_TARGETS[0])))
    argv = ['sweep', '--models', ALL_GCE_SPOT_TARGETS[0].flavor,
            '--source-bundle-uri', 'gs://bucket/code.tar.gz', '--source-bundle-sha256', 'd' * 64,
            '--source-commit', 'e' * 40]
    if mode == 'environment':
        argv += ['--dry-run']
        monkeypatch.setenv('GCE_SERVING_CONFIG', str(config))
    elif mode in ('recovery', 'override'):
        argv = ['sweep', '--recover', 'saved.json']
        monkeypatch.setenv('GCE_SERVING_CONFIG', '/missing/ignored.json')
        if mode == 'override': argv += ['--serving-config', str(config)]
    monkeypatch.setattr('sys.argv', argv)
    with patch('subprocess.run') as cloud, patch.object(GCESpotOrchestrator, 'recover_run', return_value={
        'evaluation_status': 'COMPLETED', 'artifact_evidence_status': 'COMPLETE',
        'cleanup': {'status': 'ABSENT_OBSERVED'}}) as recover:
        if mode in ('missing', 'override'):
            with pytest.raises(SystemExit) as exc: main()
            assert exc.value.code == 2
        else:
            assert main() == 0
        cloud.assert_not_called()
        assert recover.call_count == (1 if mode == 'recovery' else 0)


@pytest.mark.parametrize('invalid', [False, True])
def test_provenance_records_only_valid_serving_evidence(tmp_path, monkeypatch, invalid):
    from scripts.evaluation_provenance import capture_provenance
    config = _config(ALL_GCE_SPOT_TARGETS[0])
    evidence = {'status': 'PINNED_IMAGES_VERIFIED', 'scope': 'container_image_ids_and_requested_model_revision',
                'configuration': config, 'configuration_hash': serving_config_hash(config),
                'serving_image_id': 'sha256:' + '1' * 64, 'evaluator_image_id': 'sha256:' + '2' * 64}
    if invalid: evidence['status'] = 'SERVER_STARTED'
    monkeypatch.setenv('EXPERIMENT_SOURCE_VERIFIED', '1')
    monkeypatch.setenv('EXPERIMENT_SOURCE_BUNDLE_SHA256', 'd' * 64)
    monkeypatch.setenv('EXPERIMENT_SOURCE_COMMIT', 'e' * 40)
    monkeypatch.setenv('EXPERIMENT_SERVING_RUNTIME', json.dumps(evidence))
    if invalid:
        with pytest.raises(ValueError, match='serving runtime'):
            capture_provenance(tmp_path, tmp_path / 'cases.json', {})
    else:
        observed = capture_provenance(tmp_path, tmp_path / 'cases.json', {})
        assert observed['serving_runtime'] == evidence
        assert observed['model']['resolved_revision'] is None
        assert observed['verification_status'] == 'partial_observed_inputs'
