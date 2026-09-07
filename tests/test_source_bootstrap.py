"""Offline execution tests for the startup source-bundle bootstrap."""

import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import shlex
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
STARTUPS = [ROOT / "scripts/gce_startup_script.sh", ROOT / "scripts/templates/gce_startup_template.sh"]
COMMIT = "0" * 40


def _archive(path: Path) -> None:
    data = b"print('evaluator')\n"
    manifest = {"schema_version": 1, "source_commit": COMMIT,
                "files": {"scripts/evaluator.py": hashlib.sha256(data).hexdigest()},
                "submodules": {}, "excluded_submodules": []}
    with tarfile.open(path, "w:gz") as tar:
        for name, payload in [("scripts/evaluator.py", data),
                              ("source_manifest.json", (json.dumps(manifest) + "\n").encode())]:
            info = tarfile.TarInfo(name); info.size = len(payload)
            tar.addfile(info, io.BytesIO(payload))


@pytest.mark.parametrize("script", STARTUPS, ids=["startup", "template"])
@pytest.mark.parametrize("failure", ["success", "verifier_hash", "archive_hash", "download", "commit", "incomplete", "legacy", "metadata_outage"])
def test_pinned_bootstrap_rejects_before_evaluator(tmp_path, script, failure):
    archive = tmp_path / "bundle.tar.gz"; _archive(archive)
    verifier = ROOT / "scripts/source_bundle.py"
    verifier_sha = hashlib.sha256(verifier.read_bytes()).hexdigest()
    archive_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    values = {"uri": "gs://fixture/bundle.tar.gz", "archive_sha": archive_sha,
              "commit": COMMIT, "verifier_sha": verifier_sha}
    if failure == "verifier_hash": values["verifier_sha"] = "a" * 64
    if failure == "archive_hash": values["archive_sha"] = "b" * 64
    if failure == "commit": values["commit"] = "1" * 40
    if failure == "incomplete": values["uri"] = ""
    if failure in {"legacy", "metadata_outage"}: values = {key: "" for key in values}
    helpers = script.read_text().split("# ==============================================================================", 1)[0]
    content = script.read_text(); start = content.index("source_bundle_abort() {")
    end = content.index("\n# 2.5 Ensure Docker", start)
    functions = content[start:end]
    run_id = hashlib.sha256(str(tmp_path).encode()).hexdigest()[:32]
    bootstrap = tmp_path / "bootstrap"
    bootstrap.mkdir()
    program = f'''set -euo pipefail
{helpers}
OUTPUT_DIR={shlex.quote(str(tmp_path))}; MODEL_FLAVOR=model; REPORT_PATH="$OUTPUT_DIR/report.md"; JSON_PATH="$OUTPUT_DIR/result.json"; BENCHMARK_LOG="$OUTPUT_DIR/benchmark.log"
EVALUATION_STATUS=NOT_STARTED; EVALUATOR_EXIT_STATUS=null; EVALUATION_FAILURE_REASON=; SOURCE_BUNDLE_STATUS=NOT_REQUESTED; SOURCE_DIR=
SOURCE_METADATA_FAILED={"true" if failure == "metadata_outage" else "false"}
SOURCE_BUNDLE_URI={shlex.quote(values['uri'])}; SOURCE_BUNDLE_SHA256={shlex.quote(values['archive_sha'])}; SOURCE_COMMIT={shlex.quote(values['commit'])}; SOURCE_VERIFIER_SHA256={shlex.quote(values['verifier_sha'])}; EXPERIMENT_RUN_ID={run_id}
unset EXPERIMENT_SOURCE_VERIFIED EXPERIMENT_SOURCE_BUNDLE_SHA256 EXPERIMENT_SOURCE_COMMIT
get_source_verifier() {{ cat {shlex.quote(str(verifier))}; }}
mktemp() {{ printf '%s' {shlex.quote(str(bootstrap))}; }}
gcloud() {{
  [[ "$1 $2" == "storage cp" ]] || return 9
  [[ {failure} != download ]] || return 7
  cp {shlex.quote(str(archive))} "$4"
}}
python3() {{ {shlex.quote(sys.executable)} "$@"; }}
{functions}
rc=0
if prepare_source_bundle; then rc=0; else rc=$?; fi
printf '%s\\n' "$rc" "$SOURCE_BUNDLE_STATUS" "$SOURCE_DIR" "${{EXPERIMENT_SOURCE_VERIFIED:-unset}}" > "$OUTPUT_DIR/outcome"
'''
    result = subprocess.run(["bash", "-c", program], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    outcome = (tmp_path / "outcome").read_text().splitlines()
    if failure == "success":
        assert outcome == ["0", "VERIFIED", str(bootstrap / "source"), "1"]
        assert (bootstrap / "source/scripts/evaluator.py").read_text() == "print('evaluator')\n"
        assert not (tmp_path / "result.json").exists()
    elif failure == "legacy":
        assert outcome == ["0", "NOT_REQUESTED", "", "unset"]
        assert list(bootstrap.iterdir()) == []
    else:
        assert outcome == ["78", "FAILED", "", "unset"]
        assert not (bootstrap / "source").exists()
        assert json.loads((tmp_path / "result.json").read_text())["status"] == "FAILED"


@pytest.mark.parametrize('script', STARTUPS, ids=['startup', 'template'])
@pytest.mark.parametrize('response,exit_code,expected', [('', 7, 1), ('unavailable\n503', 0, 1), ('\n200', 0, 1), ('not found\n404', 0, 0), ('source-value\n200', 0, 0)])
def test_source_metadata_distinguishes_absence_from_transport_failure(tmp_path, script, response, exit_code, expected):
    content = script.read_text()
    function = content[content.index('get_source_metadata() {'):content.index('INSTANCE_NAME="$(get_metadata')]
    program = function + f'''
METADATA_URL=http://metadata.invalid/
curl() {{ printf '%s' {shlex.quote(response)}; return {exit_code}; }}
rc=0
value="$(get_source_metadata instance/attributes/source_bundle_uri)" || rc=$?
printf '%s' "$rc" > {shlex.quote(str(tmp_path / 'status'))}
'''
    result = subprocess.run(['bash', '-c', program], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / 'status').read_text() == str(expected)
