import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from scripts.serving_config import serving_config_hash
from scripts.serving_runtime import run_evaluator, start_server


@pytest.fixture
def config():
    return {
        "schema_version": 1, "target_flavor": "gemma-2-2b-it", "model_repository": "google/gemma-2-2b-it",
        "model_revision": "a" * 40, "serving_image": "registry.example/team/server@sha256:" + "b" * 64,
        "evaluator_image": "registry.example/team/evaluator@sha256:" + "c" * 64,
        "boot_image": "projects/proj/global/images/ubuntu-v1",
        "parameters": {"tensor_parallel_size": 1, "max_model_len": 4096, "gpu_memory_utilization": 0.9},
    }


def response(text="", code=0):
    return SimpleNamespace(stdout=text, returncode=code)


def inspect_image(digest, image_id):
    return response(json.dumps([{"Id": image_id, "RepoDigests": ["registry.example/team/image@" + digest]}]))


def test_start_server_pulls_and_inspects_both_pinned_images(config, tmp_path):
    serving_digest = config["serving_image"].rsplit("@", 1)[1]
    evaluator_digest = config["evaluator_image"].rsplit("@", 1)[1]
    calls = []
    def fake_docker(*args, **kwargs):
        calls.append(args)
        if args[:3] == ("image", "inspect", config["serving_image"]):
            return inspect_image(serving_digest, "sha256:" + "1" * 64)
        if args[:3] == ("image", "inspect", config["evaluator_image"]):
            return inspect_image(evaluator_digest, "sha256:" + "2" * 64)
        if args[:2] == ("inspect", "--format"):
            if args[2] == "{{.State.Running}}":
                return response("true")
            return response("sha256:" + "1" * 64)
        return response()
    with patch("scripts.serving_runtime.docker", side_effect=fake_docker):
        evidence = start_server(config, tmp_path / "cache", tmp_path / "evidence.json")
    assert evidence["status"] == "SERVER_STARTED"
    assert evidence["serving_image_id"] == "sha256:" + "1" * 64
    assert evidence["evaluator_image_id"] == "sha256:" + "2" * 64
    assert any(c[:2] == ("pull", "--platform") for c in calls)
    assert any(c[:2] == ("image", "inspect") for c in calls)
    create = next(c for c in calls if c[0] == "create")
    assert config["model_revision"] in create
    assert "--tokenizer-revision" in create and "--code-revision" in create
    assert "--max-model-len" in create and "4096" in create


def test_evaluator_inspects_server_and_preserves_nonzero_exit(config, tmp_path):
    evidence_path = tmp_path / "evidence.json"
    evidence = {"status": "SERVER_STARTED", "scope": "container_image_ids_and_requested_model_revision",
                "configuration": config, "configuration_hash": serving_config_hash(config),
                "serving_image_id": "sha256:" + "1" * 64, "evaluator_image_id": "sha256:" + "2" * 64}
    evidence_path.write_text(json.dumps(evidence))
    calls = []
    def fake_docker(*args, **kwargs):
        calls.append(args)
        if args[:2] == ("image", "inspect"):
            digest = config["serving_image"] if config["serving_image"] in args else config["evaluator_image"]
            image_id_value = "sha256:" + ("1" if digest == config["serving_image"] else "2") * 64
            return inspect_image(digest.rsplit("@", 1)[1], image_id_value)
        if args[:2] == ("inspect", "--format"):
            if args[2] == "{{.State.Running}}":
                return response("true")
            if args[2] == "{{json .State}}":
                return response(json.dumps({"Running": False, "ExitCode": 7, "Status": "exited", "Error": ""}))
            return response("sha256:" + ("2" if args[-1] == "soc-evaluator" else "1") * 64)
        if args[0] == "start":
            return response(code=7) if "--attach" in args else response()
        return response()
    # Runtime uses the fixed server name; make the server check succeed and evaluator check succeed.
    with patch("scripts.serving_runtime.docker", side_effect=fake_docker):
        code = run_evaluator(config, tmp_path / "source", tmp_path / "output", evidence_path)
    assert code == 7
    assert json.loads(evidence_path.read_text())["status"] == "PINNED_IMAGES_VERIFIED"
    create = next(c for c in calls if c[0] == 'create')
    assert 'type=bind,src=' + str(tmp_path / 'source') + ',dst=/workspace,readonly' in create
    assert '/output/soc_tier1_eval_results_gemma-2-2b-it.json' in create
    inspect_index = next(i for i, c in enumerate(calls) if c[:3] == ('inspect', '--format', '{{.Image}}') and c[-1] == 'soc-evaluator')
    start_index = next(i for i, c in enumerate(calls) if c[:2] == ('start', '--attach'))
    assert inspect_index < start_index
    assert any(c[:2] == ("inspect", "--format") for c in calls)
    assert any(c[0:2] == ("rm", "--force") for c in calls)


@pytest.mark.parametrize('failure', ['pull', 'image_inspect', 'digest', 'create', 'container_image', 'start', 'stopped'])
def test_server_failures_never_publish_verified_evidence(config, tmp_path, failure):
    import subprocess
    path = tmp_path / 'evidence.json'
    path.write_text('{"status":"PINNED_IMAGES_VERIFIED"}')
    calls = []
    def fake(*args, **kwargs):
        calls.append(args)
        if args[0] == failure or failure == 'image_inspect' and args[:2] == ('image', 'inspect'):
            raise subprocess.CalledProcessError(9, ['docker', *args])
        if args[:2] == ('image', 'inspect'):
            reference = args[2]
            digest = 'sha256:' + '0' * 64 if failure == 'digest' else reference.rsplit('@', 1)[1]
            return inspect_image(digest, 'sha256:' + ('1' if reference == config['serving_image'] else '2') * 64)
        if args[:2] == ('inspect', '--format'):
            if args[2] == '{{.State.Running}}': return response('false' if failure == 'stopped' else 'true')
            return response('sha256:' + ('0' if failure == 'container_image' else '1') * 64)
        return response()
    with patch('scripts.serving_runtime.docker', side_effect=fake), pytest.raises((ValueError, subprocess.CalledProcessError)):
        start_server(config, tmp_path, path)
    assert not path.exists()
    if failure in ('pull', 'image_inspect', 'digest'):
        assert not any(call[0] == 'create' for call in calls)


@pytest.mark.parametrize('failure', ['image', 'container', 'create', 'stopped', 'stale'])
def test_evaluator_does_not_start_with_unverified_runtime(config, tmp_path, failure):
    import subprocess
    evidence = {'status': 'SERVER_STARTED', 'configuration': config, 'configuration_hash': serving_config_hash(config),
                'serving_image_id': 'sha256:' + '1' * 64, 'evaluator_image_id': 'sha256:' + '2' * 64}
    if failure == 'stale': evidence['configuration_hash'] = '0' * 64
    path = tmp_path / 'evidence.json'; path.write_text(json.dumps(evidence))
    calls = []
    def fake(*args, **kwargs):
        calls.append(args)
        if args[0] == 'create' and failure == 'create': raise subprocess.CalledProcessError(7, args)
        if args[:2] == ('image', 'inspect'):
            identity = '1' if args[2] == config['serving_image'] else '2'
            return inspect_image(args[2].rsplit('@', 1)[1], 'sha256:' + ('0' if failure == 'image' else identity) * 64)
        if args[:2] == ('inspect', '--format'):
            if args[2] == '{{.State.Running}}': return response('false' if failure == 'stopped' else 'true')
            identity = '2' if args[-1] == 'soc-evaluator' else '1'
            return response('sha256:' + ('0' if failure == 'container' and identity == '2' else identity) * 64)
        return response()
    with patch('scripts.serving_runtime.docker', side_effect=fake), pytest.raises((ValueError, subprocess.CalledProcessError)):
        run_evaluator(config, tmp_path, tmp_path, path)
    assert not any(call[:2] == ('start', '--attach') for call in calls)
    assert json.loads(path.read_text())['status'] == 'SERVER_STARTED'


def test_runtime_cli_rejects_missing_launch_identity_before_docker(config, tmp_path, monkeypatch):
    from scripts.serving_runtime import main
    monkeypatch.delenv('EXPERIMENT_RUN_ID', raising=False)
    monkeypatch.delenv('EXPERIMENT_CONFIGURATION_HASH', raising=False)
    path = tmp_path / 'config.json'; path.write_text(json.dumps(config))
    evidence = tmp_path / 'runtime.json'
    with patch('scripts.serving_runtime.docker') as cloud:
        assert main(['start', '--config', str(path), '--sha256', serving_config_hash(config),
                     '--flavor', config['target_flavor'], '--model-repository', config['model_repository'],
                     '--tp-size', '1', '--cache', str(tmp_path), '--evidence', str(evidence)]) == 78
    cloud.assert_not_called()
    assert json.loads(evidence.read_text())['status'] == 'FAILED'
