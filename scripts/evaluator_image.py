"""Build a dependency image or check evaluator compatibility without model calls."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.experiment_run import write_json
from scripts.source_bundle import verify_bundle

IMAGE_ID = re.compile(r'sha256:[0-9a-f]{64}')
DIGEST_REF = re.compile(r'[a-z0-9.-]+(?::[0-9]+)?(?:/[a-z0-9._-]+)+@sha256:[0-9a-f]{64}')
CHECKS = {'evaluator_completed': True, 'total_cases': 1, 'case_passed': True,
          'json_output': True, 'markdown_output': True, 'provenance_without_launch_claim': True}
OWNER_LABEL = 'open-model-deploy-gcp.preflight-attempt'


def docker(*args, capture=False, check=True, timeout=120):
    return subprocess.run(['docker', *args], capture_output=capture, text=True,
                          check=check, timeout=timeout)


def validate_image(reference, allow_id=False):
    if not isinstance(reference, str) or not (DIGEST_REF.fullmatch(reference) or allow_id and IMAGE_ID.fullmatch(reference)):
        raise ValueError('Use an immutable registry/repository@sha256 reference or a local image ID for checks')


def inspect_image(reference):
    validate_image(reference, allow_id=True)
    records = json.loads(docker('image', 'inspect', reference, capture=True).stdout)
    if not isinstance(records, list) or len(records) != 1 or not isinstance(records[0], dict):
        raise ValueError('Invalid Docker image inspection')
    info = records[0]
    identity = info.get('Id')
    if not isinstance(identity, str) or not IMAGE_ID.fullmatch(identity):
        raise ValueError('Invalid Docker image ID')
    if info.get('Os') != 'linux' or info.get('Architecture') != 'amd64':
        raise ValueError('Evaluator image must be Linux AMD64')
    if IMAGE_ID.fullmatch(reference):
        if identity != reference: raise ValueError('Local image ID mismatch')
    else:
        digests = info.get('RepoDigests')
        if not isinstance(digests, list) or not any(isinstance(d, str) and d.endswith('@' + reference.rsplit('@', 1)[1]) for d in digests):
            raise ValueError('Registry digest mismatch')
    return identity


def build_image(python_image, tag):
    validate_image(python_image)
    if not re.fullmatch(r'[a-z0-9][a-z0-9_.-]*(?::[A-Za-z0-9_.-]+)?', tag):
        raise ValueError('Use a local image tag without registry or namespace')
    with tempfile.TemporaryDirectory(prefix='evaluator-build-') as scratch:
        context = Path(scratch)
        inputs = {}
        for source, destination in [('Dockerfile.evaluator', 'Dockerfile'), ('requirements-evaluator.lock', 'requirements-evaluator.lock')]:
            data = (ROOT / 'docker' / source).read_bytes()
            (context / destination).write_bytes(data)
            inputs[source] = hashlib.sha256(data).hexdigest()
        # Keep the iidfile outside the build context; only the two allowlisted files are sent.
        with tempfile.TemporaryDirectory(prefix='evaluator-build-id-') as ids:
            iidfile = Path(ids) / 'image.id'
            docker('build', '--platform=linux/amd64', '--pull', '--build-arg', f'PYTHON_IMAGE={python_image}',
                   '--iidfile', str(iidfile), '--tag', tag, str(context), timeout=1800)
            identity = iidfile.read_text().strip()
            validate_image(identity, allow_id=True)
            if not IMAGE_ID.fullmatch(identity) or inspect_image(identity) != identity:
                raise ValueError('Build image ID mismatch')
    return {'status': 'BUILT_LOCAL', 'python_image': python_image, 'local_tag': tag,
            'image_id': identity, 'inputs': inputs, 'registry_digest': None}


def validate_smoke(report):
    if (not isinstance(report, dict) or type(report.get('schema_version')) is not int or report['schema_version'] != 1
            or report.get('status') != 'PASS' or report.get('synthetic') is not True
            or report.get('scope') != 'offline_evaluator_compatibility'
            or not isinstance(report.get('python_version'), str) or not report['python_version'].startswith('3.12.')
            or not isinstance(report.get('checks'), dict) or report['checks'] != CHECKS
            or type(report['checks'].get('total_cases')) is not int):
        raise ValueError('Smoke report is missing, failed, or incompatible')
    for name in ('evaluator_completed', 'case_passed', 'json_output', 'markdown_output', 'provenance_without_launch_claim'):
        if report['checks'][name] is not True:
            raise ValueError('Invalid smoke check')


def check_image(reference, archive, digest, commit):
    validate_image(reference, allow_id=True)
    with tempfile.TemporaryDirectory(prefix='evaluator-check-') as scratch:
        base = Path(scratch)
        source, output = base / 'source', base / 'output'
        verify_bundle(archive, digest, commit, source)
        if not (source / 'scripts/evaluator_smoke.py').is_file():
            raise ValueError('Source bundle lacks the evaluator smoke entrypoint')
        output.mkdir()
        identity = inspect_image(reference)
        attempt = uuid.uuid4().hex
        name = 'evaluator-check-' + attempt
        created = False
        try:
            docker('create', '--name', name, '--platform=linux/amd64', '--pull=never',
                   '--label', f'{OWNER_LABEL}={attempt}',
                   '--network=none', '--read-only', '--user=0:0', '--no-healthcheck',
                   '--tmpfs', '/tmp:rw,nosuid,nodev,size=256m', '--workdir', '/workspace',
                   '--entrypoint', 'python3', '--mount', f'type=bind,src={source},dst=/workspace,readonly',
                   '--mount', f'type=bind,src={output},dst=/output',
                   reference, '-I', '-B', '/workspace/scripts/evaluator_smoke.py', '--output', '/output/smoke.json')
            created = True
            observed = docker('inspect', '--format', '{{.Image}}', name, capture=True).stdout.strip()
            if observed != identity:
                raise ValueError('Created container image ID mismatch')
            attached = docker('start', '--attach', name, check=False)
            state = json.loads(docker('inspect', '--format', '{{json .State}}', name, capture=True).stdout)
            if (not isinstance(state, dict) or state.get('Running') is not False or state.get('Status') != 'exited'
                    or type(state.get('ExitCode')) is not int or state['ExitCode'] != 0
                    or state.get('Error') or attached.returncode != 0):
                raise ValueError('Offline evaluator container failed')
            path = output / 'smoke.json'
            if not path.is_file() or path.is_symlink() or path.stat().st_size > 65536:
                raise ValueError('Missing or invalid smoke report')
            report = json.loads(path.read_text())
            validate_smoke(report)
            return {'status': 'PASS', 'synthetic': True, 'scope': 'offline_evaluator_image_preflight',
                    'image_reference': reference, 'image_id': identity, 'source_commit': commit,
                    'source_bundle_sha256': digest, 'smoke': report}
        finally:
            if not created:
                # A lost create response does not prove the daemon created nothing.
                # Never delete a conflicting container without our exact attempt label.
                try:
                    owner = docker('inspect', '--format', '{{ index .Config.Labels "' + OWNER_LABEL + '" }}',
                                   name, capture=True, timeout=10).stdout.strip()
                    created = owner == attempt
                except (OSError, subprocess.SubprocessError):
                    pass
            if created:
                docker('rm', '--force', '--volumes', name)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    build = sub.add_parser('build')
    build.add_argument('--python-image', required=True)
    build.add_argument('--tag', default='evaluator-preflight:local')
    build.add_argument('--output', type=Path, required=True)
    check = sub.add_parser('check')
    check.add_argument('--image', required=True)
    check.add_argument('--archive', type=Path, required=True)
    check.add_argument('--sha256', required=True)
    check.add_argument('--source-commit', required=True)
    check.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    inputs = [ROOT / 'docker/Dockerfile.evaluator', ROOT / 'docker/requirements-evaluator.lock']
    if args.command == 'check':
        inputs.append(args.archive)
    if args.output.resolve() in [path.resolve() for path in inputs]:
        parser.error('Output must not overwrite an input file')
    initial = {'schema_version': 1, 'action': args.command, 'attempt_id': uuid.uuid4().hex, 'status': 'FAIL'}
    write_json(args.output, {**initial, 'error_type': 'IncompleteOperation'})
    try:
        if args.command == 'build':
            result = build_image(args.python_image, args.tag)
        else:
            result = check_image(args.image, args.archive, args.sha256, args.source_commit)
        result = {**initial, **result}
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        result = {**initial, 'error_type': type(exc).__name__}
    write_json(args.output, result)
    print(json.dumps(result, sort_keys=True))
    return 0 if result['status'] in ('PASS', 'BUILT_LOCAL') else 1


if __name__ == '__main__':
    raise SystemExit(main())
