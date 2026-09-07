"""Offline image orchestration tests: never start Docker or call a provider."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from scripts import evaluator_image as module

IMAGE = 'registry.example/evaluator@sha256:' + 'a' * 64
ID = 'sha256:' + 'b' * 64


def smoke():
    return {'schema_version': 1, 'status': 'PASS', 'synthetic': True,
            'scope': 'offline_evaluator_compatibility', 'python_version': '3.12.13',
            'checks': dict(module.CHECKS)}


def response(value='', code=0):
    return SimpleNamespace(stdout=value, returncode=code)


@pytest.mark.parametrize('problem', [None, 'arch', 'digest', 'container', 'create', 'attach', 'timeout', 'missing', 'schema', 'cleanup'])
def test_checker_gates_execution_and_report(tmp_path, monkeypatch, problem):
    calls = []
    mounts = {}
    def verify(archive, digest, commit, destination):
        (destination / 'scripts').mkdir(parents=True)
        (destination / 'scripts/evaluator_smoke.py').write_text('# fixture')
    monkeypatch.setattr(module, 'verify_bundle', verify)
    def docker(*args, **kwargs):
        calls.append(args)
        if args[:2] == ('image', 'inspect'):
            return response(json.dumps([{'Id': ID, 'Os': 'linux', 'Architecture': 'arm64' if problem == 'arch' else 'amd64',
                                        'RepoDigests': [IMAGE if problem != 'digest' else 'wrong@sha256:' + 'c' * 64]}]))
        if args[0] == 'create':
            if problem == 'create': raise subprocess.CalledProcessError(1, args)
            for arg in args:
                if arg.startswith('type=bind,src='):
                    mounts[arg.split('dst=', 1)[1].split(',')[0]] = Path(arg.split('src=', 1)[1].split(',')[0])
            return response('created')
        if args[:3] == ('inspect', '--format', '{{.Image}}'):
            return response(ID if problem != 'container' else 'sha256:' + 'd' * 64)
        if args[0] == 'start':
            if problem == 'timeout': raise subprocess.TimeoutExpired(args, 120)
            if problem != 'missing':
                report = smoke()
                if problem == 'schema': report['checks']['case_passed'] = False
                (mounts['/output'] / 'smoke.json').write_text(json.dumps(report))
            return response(code=1 if problem == 'attach' else 0)
        if args[:3] == ('inspect', '--format', '{{json .State}}'):
            return response(json.dumps({'Running': False, 'Status': 'exited', 'ExitCode': 0, 'Error': ''}))
        if args[0] == 'rm' and problem == 'cleanup': raise subprocess.CalledProcessError(1, args)
        return response()
    monkeypatch.setattr(module, 'docker', docker)
    if problem:
        with pytest.raises((ValueError, subprocess.SubprocessError)):
            module.check_image(IMAGE, tmp_path / 'archive', 'e'*64, 'f'*40)
    else:
        report = module.check_image(IMAGE, tmp_path / 'archive', 'e'*64, 'f'*40)
        assert report['status'] == 'PASS' and report['synthetic'] is True
        assert report['image_id'] == ID and report['image_reference'] == IMAGE
    created = next((c for c in calls if c[0] == 'create'), None)
    if created:
        assert '--pull=never' in created and '--network=none' in created and '--read-only' in created
        assert any(a.endswith('dst=/workspace,readonly') for a in created)
        assert '-I' in created and '-B' in created
    if problem in ('arch', 'digest', 'container', 'create'):
        assert not any(c[0] == 'start' for c in calls)
    assert any(c[0] == 'rm' for c in calls) == (problem not in ('arch', 'digest', 'create'))


def test_build_sends_only_snapshotted_inputs(tmp_path, monkeypatch):
    (tmp_path / 'docker').mkdir()
    inputs = {'Dockerfile.evaluator': b'FROM fixture', 'requirements-evaluator.lock': b'fixture==1 --hash=sha256:abc'}
    for name, content in inputs.items(): (tmp_path / 'docker' / name).write_bytes(content)
    (tmp_path / 'docker' / 'credentials.json').write_text('must not send')
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    def docker(*args, **kwargs):
        if args[0] == 'build':
            context = Path(args[-1])
            assert sorted(p.name for p in context.iterdir()) == ['Dockerfile', 'requirements-evaluator.lock']
            assert (context / 'Dockerfile').read_bytes() == inputs['Dockerfile.evaluator']
            assert '--platform=linux/amd64' in args
            Path(args[args.index('--iidfile') + 1]).write_text(ID)
            return response()
        return response(json.dumps([{'Id': ID, 'Os': 'linux', 'Architecture': 'amd64'}]))
    monkeypatch.setattr(module, 'docker', docker)
    result = module.build_image(IMAGE, 'evaluator:local')
    assert result['registry_digest'] is None
    assert result['inputs']['Dockerfile.evaluator'] == hashlib.sha256(inputs['Dockerfile.evaluator']).hexdigest()


@pytest.mark.parametrize('value', ['latest', 'image:tag', 'registry/image@sha256:short', 'registry/image@sha256:' + 'A'*64])
def test_mutable_or_invalid_images_fail_before_docker(monkeypatch, value):
    monkeypatch.setattr(module, 'docker', lambda *a, **kw: pytest.fail('unexpected Docker call'))
    with pytest.raises(ValueError): module.inspect_image(value)


@pytest.mark.parametrize('field,value', [('status', 'FAIL'), ('synthetic', False), ('schema_version', True),
                                        ('scope', 'live'), ('python_version', '3.11.1'), ('checks', {})])
def test_report_requires_exact_offline_contract(field, value):
    report = smoke(); report[field] = value
    with pytest.raises(ValueError): module.validate_smoke(report)


def test_stale_success_becomes_failed_attempt(tmp_path, monkeypatch):
    output = tmp_path / 'result.json'; output.write_text('{"status":"PASS"}')
    monkeypatch.setattr(module, 'build_image', lambda *a: (_ for _ in ()).throw(FileNotFoundError('docker')))
    assert module.main(['build', '--python-image', IMAGE, '--output', str(output)]) == 1
    report = json.loads(output.read_text())
    assert report['status'] == 'FAIL' and report['error_type'] == 'FileNotFoundError'
    assert report['attempt_id']


def test_output_cannot_overwrite_source_archive(tmp_path):
    archive = tmp_path / 'source.tar.gz'; archive.write_bytes(b'preserve')
    with pytest.raises(SystemExit):
        module.main(['check', '--image', IMAGE, '--archive', str(archive), '--sha256', 'a'*64,
                     '--source-commit', 'b'*40, '--output', str(archive)])
    assert archive.read_bytes() == b'preserve'


@pytest.mark.parametrize('owned', [True, False])
def test_unknown_create_outcome_cleans_only_owned_container(tmp_path, monkeypatch, owned):
    names = {}; calls = []
    def verify(archive, digest, commit, destination):
        (destination / 'scripts').mkdir(parents=True)
        (destination / 'scripts/evaluator_smoke.py').write_text('# fixture')
    monkeypatch.setattr(module, 'verify_bundle', verify)
    def docker(*args, **kwargs):
        calls.append(args)
        if args[:2] == ('image', 'inspect'):
            return response(json.dumps([{'Id': ID, 'Os': 'linux', 'Architecture': 'amd64', 'RepoDigests': [IMAGE]}]))
        if args[0] == 'create':
            names['attempt'] = args[args.index('--label') + 1].split('=', 1)[1]
            raise subprocess.TimeoutExpired(args, 120)
        if args[0] == 'inspect': return response(names['attempt'] if owned else 'someone-else')
        return response()
    monkeypatch.setattr(module, 'docker', docker)
    with pytest.raises(subprocess.TimeoutExpired):
        module.check_image(IMAGE, tmp_path / 'archive', 'e'*64, 'f'*40)
    assert any(c[:3] == ('rm', '--force', '--volumes') for c in calls) is owned
