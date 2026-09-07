import json
from pathlib import Path

from scripts.evaluator_smoke import main, run_smoke


def test_offline_smoke_passes_and_writes_report(tmp_path: Path):
    output = tmp_path / "smoke.json"
    assert run_smoke(output)["status"] == "PASS"
    result = json.loads(output.read_text())
    assert result["schema_version"] == 1
    assert result["synthetic"] is True
    assert result["scope"] == "offline_evaluator_compatibility"
    assert result["checks"]["total_cases"] == 1


def test_smoke_failure_is_explicit_and_nonzero(tmp_path: Path, monkeypatch):
    import scripts.evaluator_smoke as smoke
    monkeypatch.setattr(smoke, "_execute_smoke", lambda: (_ for _ in ()).throw(ImportError("missing dependency")))
    output = tmp_path / "smoke.json"
    assert main(["--output", str(output)]) == 1
    result = json.loads(output.read_text())
    assert result["status"] == "FAIL"
    assert result["error_type"] == "ImportError"


def test_smoke_clears_inherited_launch_identity(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("EXPERIMENT_RUN_ID", "not-a-uuid")
    monkeypatch.setenv("EXPERIMENT_CONFIGURATION_HASH", "f" * 64)
    result = run_smoke(tmp_path / "smoke.json")
    assert result["status"] == "PASS"


def test_isolated_entrypoint_clears_all_inherited_identity(tmp_path):
    import os
    import subprocess
    import sys
    script = Path(__file__).resolve().parents[1] / 'scripts/evaluator_smoke.py'
    output = tmp_path / 'report.json'
    env = dict(os.environ, EXPERIMENT_SOURCE_VERIFIED='invalid', EXPERIMENT_SERVING_RUNTIME='invalid',
               GOOGLE_APPLICATION_CREDENTIALS='/missing/credentials.json')
    result = subprocess.run([sys.executable, '-I', str(script), '--output', str(output)],
                            cwd=tmp_path, env=env, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text())['status'] == 'PASS'
    assert json.loads(result.stdout)['synthetic'] is True
