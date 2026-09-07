"""Execute startup functions with local transport stubs, without booting a VM."""

import json
from pathlib import Path
import shlex
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
STARTUP_SCRIPTS = [ROOT / 'scripts/gce_startup_script.sh',
                   ROOT / 'scripts/templates/gce_startup_template.sh']


@pytest.mark.parametrize('script', STARTUP_SCRIPTS, ids=['startup', 'template'])
@pytest.mark.parametrize('mode,exit_status,remote_status', [
    ('success', 0, 'COMMAND_SUCCEEDED'), ('bulk', 7, None), ('marker', 9, 'REQUESTED'),
])
def test_actual_upload_function_publishes_final_marker_and_preserves_failures(
    tmp_path, script, mode, exit_status, remote_status
):
    content = script.read_text()
    helpers = content.split('# ==============================================================================')[0]
    functions = content[content.index('write_lifecycle_status() {'):]
    functions = functions[:functions.index('\necho "=================================================================="')]
    for filename in ['report.md', 'result.json', 'benchmark.log']:
        (tmp_path / filename).write_text('evaluation failed with useful diagnostics')
    program = helpers + '\n' + functions + f'''
OUTPUT_DIR={shlex.quote(str(tmp_path))}
REPORT_PATH="$OUTPUT_DIR/report.md"
JSON_PATH="$OUTPUT_DIR/result.json"
BENCHMARK_LOG="$OUTPUT_DIR/benchmark.log"
LIFECYCLE_PATH="$OUTPUT_DIR/lifecycle_status.json"
OUTPUT_BUCKET=gs://fixture/runs/test
MODEL_FLAVOR=model
EXPERIMENT_RUN_ID=0123456789abcdef0123456789abcdef
EXPERIMENT_CONFIGURATION_HASH={'a' * 64}
SOURCE_COMMIT=
EVALUATION_STATUS=FAILED
EVALUATOR_EXIT_STATUS=23
EVALUATION_FAILURE_REASON='evaluator failed'
BENCHMARK_STATUS=COMPLETED
ARTIFACT_STATUS=NOT_COLLECTED
ARTIFACT_UPLOAD_STATUS=NOT_REQUESTED
CLEANUP_DELETE_REQUESTED=false
CLEANUP_DELETE_VERIFIED=false
calls=0
gcloud() {{
  calls=$((calls+1))
  if [[ "$calls" == 1 ]]; then
    [[ "$2" == cp && "$3" == -r ]] || return 98
    [[ {mode} != bulk ]] || return 7
  else
    [[ "$calls" == 2 && "$2" == cp && "$3" == "$LIFECYCLE_PATH" ]] || return 99
    [[ {mode} != marker ]] || return 9
  fi
  cp "$LIFECYCLE_PATH" "$OUTPUT_DIR/remote.json"
}}
rc=0
upload_artifacts || rc=$?
printf '%s %s' "$rc" "$calls" > "$OUTPUT_DIR/outcome"
'''
    result = subprocess.run(['bash', '-c', program], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stderr == ''
    expected_calls = 1 if mode == 'bulk' else 2
    assert (tmp_path / 'outcome').read_text() == f'{exit_status} {expected_calls}'
    local = json.loads((tmp_path / 'lifecycle_status.json').read_text())
    assert local['evaluation']['status'] == 'FAILED'
    assert local['evaluation']['evaluator_exit_status'] == 23
    assert local['artifacts']['upload_status'] == ('COMMAND_SUCCEEDED' if mode == 'success' else 'FAILED')
    assert local['run_id'] == '0123456789abcdef0123456789abcdef'
    assert local['configuration_hash'] == 'a' * 64
    remote = tmp_path / 'remote.json'
    if remote_status is None:
        assert not remote.exists()
    else:
        assert json.loads(remote.read_text())['artifacts']['upload_status'] == remote_status
