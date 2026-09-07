"""Execute actual startup metadata and pin validation without cloud or Docker."""
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = [ROOT / 'scripts/gce_startup_script.sh', ROOT / 'scripts/templates/gce_startup_template.sh']


@pytest.mark.parametrize('script', SCRIPTS, ids=['startup', 'template'])
@pytest.mark.parametrize('failure', ['success', 'legacy', 'metadata', 'download', 'hash', 'target', 'source', 'cache'])
def test_serving_metadata_and_validation_fail_closed(tmp_path, script, failure):
    config = {'schema_version': 1, 'target_flavor': 'gemma-2-2b-it',
              'model_repository': 'google/gemma-2-2b-it', 'model_revision': 'a' * 40,
              'serving_image': 'registry.example/server@sha256:' + 'b' * 64,
              'evaluator_image': 'registry.example/eval@sha256:' + 'c' * 64,
              'boot_image': 'projects/test/global/images/ubuntu-v1',
              'parameters': {'tensor_parallel_size': 1, 'max_model_len': 4096, 'gpu_memory_utilization': 0.9}}
    if failure == 'target': config['model_repository'] = 'other/model'
    payload = json.dumps(config, sort_keys=True, separators=(',', ':')).encode()
    fixture = tmp_path / 'input.json'; fixture.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest() if failure != 'hash' else '0' * 64
    metadata = 'missing\n404' if failure == 'legacy' else 'unavailable\n503' if failure == 'metadata' else digest + '\n200'
    content = script.read_text()
    initialization = content[:content.index('CONTAINER_NAME="vllm-server"')]
    functions = content[content.index('serving_abort() {'):content.index('\n# 2.5 Ensure Docker')]
    stage = tmp_path / 'stage'; stage.mkdir()
    program = f'''
python3() {{ {shlex.quote(sys.executable)} "$@"; }}
curl() {{
  local url="${{@: -1}}"
  if [[ "$url" == */serving_config_sha256 ]]; then
    printf '%s' {shlex.quote(metadata)}
  elif [[ "$url" == */serving-config ]]; then
    [[ {failure} != download ]] || return 22
    cat {shlex.quote(str(fixture))}
  elif [[ "$url" == */source* ]]; then printf 'missing\\n404'; fi
}}
{initialization}
{functions}
OUTPUT_DIR={shlex.quote(str(tmp_path))}; MODEL_FLAVOR=gemma-2-2b-it
HF_REPO=google/gemma-2-2b-it; TP_SIZE=1; EXTRA_FLAGS=; GCS_MODEL_PATH={'gs://mutable/model' if failure == 'cache' else ''}
SOURCE_DIR={shlex.quote(str(ROOT))}; SOURCE_BUNDLE_STATUS={'FAILED' if failure == 'source' else 'VERIFIED'}
REPORT_PATH="$OUTPUT_DIR/report.md"; JSON_PATH="$OUTPUT_DIR/result.json"; BENCHMARK_LOG="$OUTPUT_DIR/benchmark.log"
mktemp() {{ printf '%s' {shlex.quote(str(stage))}; }}
rc=0
if prepare_serving_config; then rc=0; else rc=$?; fi
printf '%s\\n' "$rc" "${{SERVING_CONFIG_PATH}}" > "$OUTPUT_DIR/outcome"
'''
    result = subprocess.run(['bash', '-c', program], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    outcome = (tmp_path / 'outcome').read_text().splitlines()
    if failure == 'success':
        assert outcome == ['0', str(stage / 'serving-config.json')]
        assert not (tmp_path / 'result.json').exists()
    elif failure == 'legacy':
        assert outcome == ['0', '']
    else:
        assert outcome[0] == '78'
        assert json.loads((tmp_path / 'result.json').read_text())['status'] == 'FAILED'


@pytest.mark.parametrize('script', SCRIPTS, ids=['startup', 'template'])
@pytest.mark.parametrize('failed_action', ['none', 'start', 'evaluate'])
def test_pinned_execution_uses_runtime_and_preserves_failures(tmp_path, script, failed_action):
    content = script.read_text()
    helpers = content.split('# ==============================================================================')[0]
    start = content[content.index('# 5. Launch Containerized'):content.index('# 6. Poll Health Endpoint')]
    evaluation = content[content.index('# 7. Execute SOC'):content.index('echo "[INFO] Running benchmark latency')]
    source = tmp_path / 'source'; (source / 'scripts').mkdir(parents=True)
    (source / 'scripts/eval_soc_agent.py').write_text('raise AssertionError("legacy execution")')
    calls = tmp_path / 'calls'
    program = f'''set -euo pipefail
{helpers}
OUTPUT_DIR={shlex.quote(str(tmp_path))}; SOURCE_DIR={shlex.quote(str(source))}; SERVING_CONFIG_PATH=pinned
MODEL_FLAVOR=gemma-2-2b-it; HF_REPO=google/gemma-2-2b-it; TP_SIZE=1; EXTRA_FLAGS=; HF_TOKEN=; HF_HOME=cache; CONTAINER_NAME=vllm-server
REPORT_PATH="$OUTPUT_DIR/report.md"; JSON_PATH="$OUTPUT_DIR/result.json"; BENCHMARK_LOG="$OUTPUT_DIR/benchmark.log"
run_pinned_runtime() {{
  printf '%s\\n' "$1" >> {shlex.quote(str(calls))}
  [[ "$1" != {failed_action} ]] || return 7
}}
serving_abort() {{ return 78; }}
docker() {{ exit 99; }}
pip3() {{ exit 99; }}
{start}
{evaluation}
printf '%s\\n' "$EVALUATION_STATUS" "$EVALUATOR_EXIT_STATUS" > "$OUTPUT_DIR/outcome"
'''
    result = subprocess.run(['bash', '-c', program], capture_output=True, text=True, timeout=10)
    if failed_action == 'start':
        assert result.returncode == 78
        assert calls.read_text().splitlines() == ['start']
        assert not (tmp_path / 'outcome').exists()
    else:
        assert result.returncode == 0, result.stderr
        assert calls.read_text().splitlines() == ['start', 'evaluate']
        assert (tmp_path / 'outcome').read_text().splitlines() == (
            ['FAILED', '7'] if failed_action == 'evaluate' else ['COMPLETED', '0'])
