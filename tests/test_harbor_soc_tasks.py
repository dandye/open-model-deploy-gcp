"""End-to-end tests for Harbor SOC task generation, image deduplication, and oracle calibration."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib

from scripts.generate_harbor_soc_tasks import (
    SKILL_ARMS,
    compute_environment_hash,
    generate_harbor_soc_suite,
)

ROOT_DIR = Path(__file__).resolve().parent.parent


def test_generate_harbor_soc_suite_and_verify_30_tasks_and_oracles(tmp_path: Path):
    """Verify all 30 tasks are generated, share 1 environment hash, and score 1.0000 on oracle."""
    harbor_out = tmp_path / "harbor_soc"
    evals_json_out = tmp_path / "evals.json"

    summary = generate_harbor_soc_suite(output_root=harbor_out, evals_json_out=evals_json_out)
    assert summary["total_tasks"] == len(SKILL_ARMS) * 10
    assert len(summary["unique_environment_hashes"]) == 1
    assert evals_json_out.exists()

    evals_manifest = json.loads(evals_json_out.read_text(encoding="utf-8"))
    assert len(evals_manifest["evals"]) == 10

    env_hashes = set()
    for arm in SKILL_ARMS:
        arm_dir = harbor_out / arm
        assert arm_dir.is_dir()
        task_dirs = sorted(p for p in arm_dir.iterdir() if p.is_dir())
        assert len(task_dirs) == 10

        for task_dir in task_dirs:
            toml_path = task_dir / "task.toml"
            instr_path = task_dir / "instruction.md"
            solve_path = task_dir / "solution" / "solve.sh"
            test_path = task_dir / "tests" / "test.sh"
            env_dir = task_dir / "environment"

            assert toml_path.exists()
            assert instr_path.exists()
            assert solve_path.exists()
            assert test_path.exists()
            assert (env_dir / "Dockerfile").exists()

            parsed_toml = tomllib.loads(toml_path.read_text(encoding="utf-8"))
            assert parsed_toml["schema_version"] == "1.3"
            assert parsed_toml["metadata"]["skill_arm"] == arm
            case_id = parsed_toml["environment"]["env"]["SOC_CASE_ID"]
            assert case_id.startswith("CASE-GEN3-")

            env_hashes.add(compute_environment_hash(env_dir))

    # Critical harbor-gke-ext requirement: all 30 tasks share a single build context hash
    assert len(env_hashes) == 1

    # Execute oracle (solve.sh) + verifier (test.sh) across all 10 cases in clean_skills arm
    for idx, task_dir in enumerate(sorted((harbor_out / "clean_skills").iterdir())):
        parsed_toml = tomllib.loads((task_dir / "task.toml").read_text(encoding="utf-8"))
        case_id = parsed_toml["environment"]["env"]["SOC_CASE_ID"]

        trial_root = tmp_path / f"trial_{idx + 1:02d}"
        state_file = trial_root / "var" / "lib" / "soc" / "state.json"
        artifacts_dir = trial_root / "logs" / "artifacts"
        verifier_dir = trial_root / "logs" / "verifier"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        verifier_dir.mkdir(parents=True, exist_ok=True)

        run_env = dict(os.environ)
        run_env.update({
            "SOC_CASE_ID": case_id,
            "SOC_SKILL_ARM": "clean_skills",
            "SOC_STATE_FILE": str(state_file),
            "SOC_TRAJECTORY_FILE": str(artifacts_dir / "trajectory.jsonl"),
            "SOC_ARTIFACTS_DIR": str(artifacts_dir),
            "SOC_VERIFIER_DIR": str(verifier_dir),
            "SOC_CLI_BIN": f"{sys.executable} {ROOT_DIR / 'scripts' / 'soc_sandbox_cli.py'}",
            "SOC_VERIFY_BIN": f"{sys.executable} {ROOT_DIR / 'scripts' / 'verify_harbor_soc.py'}",
        })

        solve_res = subprocess.run(
            ["bash", str(task_dir / "solution" / "solve.sh")],
            env=run_env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert solve_res.returncode == 0, f"solve.sh failed for {case_id}: {solve_res.stderr}"

        verify_res = subprocess.run(
            ["bash", str(task_dir / "tests" / "test.sh")],
            env=run_env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert verify_res.returncode == 0, f"test.sh failed for {case_id}: {verify_res.stderr}"

        reward_val = float((verifier_dir / "reward.txt").read_text(encoding="utf-8").strip())
        assert reward_val == 1.0, f"Oracle reward for {case_id} was {reward_val}, expected 1.0000"
