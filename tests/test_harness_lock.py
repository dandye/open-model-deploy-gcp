import json
from pathlib import Path
import subprocess
import sys

from scripts import harness_lock

ROOT_DIR = Path(__file__).resolve().parent.parent


def _root(tmp_path: Path) -> Path:
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs" / "a.json").write_text("{}", encoding="utf-8")
    (tmp_path / "grader.py").write_text("x = 1\n", encoding="utf-8")
    return tmp_path


def test_approve_then_verify_passes(tmp_path: Path, capsys) -> None:
    root = _root(tmp_path)
    lock = tmp_path / "lock.json"
    args = ["--root", str(root), "--lock-file", str(lock), "--path", "configs", "--path", "grader.py"]
    assert harness_lock.main(["approve", *args]) == 0
    assert lock.exists()
    assert harness_lock.main(["verify", *args]) == 0
    out = capsys.readouterr().out
    assert "composite_sha256" in out and "harness lock verified" in out


def test_verify_fails_after_tampering(tmp_path: Path, capsys) -> None:
    root = _root(tmp_path)
    lock = tmp_path / "lock.json"
    args = ["--root", str(root), "--lock-file", str(lock), "--path", "configs", "--path", "grader.py"]
    assert harness_lock.main(["approve", *args]) == 0
    (root / "grader.py").write_text("x = 2\n", encoding="utf-8")
    assert harness_lock.main(["verify", *args]) == 1
    assert "grader.py" in capsys.readouterr().err


def test_verify_without_a_lock_does_not_initialize(tmp_path: Path, capsys) -> None:
    root = _root(tmp_path)
    lock = tmp_path / "missing.json"
    assert harness_lock.main(["verify", "--root", str(root), "--lock-file", str(lock), "--path", "grader.py"]) == 1
    assert not lock.exists()


def test_default_paths_are_the_harness_defaults() -> None:
    from agent.hillclimb_harness import DEFAULT_PROTECTED_HARNESS_PATHS

    parser = harness_lock.build_parser()
    args = parser.parse_args(["verify"])
    assert harness_lock.resolve_paths(args) == list(DEFAULT_PROTECTED_HARNESS_PATHS)


def test_committed_lock_verifies_at_head() -> None:
    """Every protected path matches .eval_harness_lock.json. After an intended change: just harness-approve."""
    result = subprocess.run(
        [sys.executable, str(ROOT_DIR / "scripts" / "harness_lock.py"), "verify"],
        capture_output=True, text=True, check=False, cwd=ROOT_DIR,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_committed_lock_covers_the_gen5_inputs() -> None:
    lock = json.loads((ROOT_DIR / ".eval_harness_lock.json").read_text(encoding="utf-8"))
    locked = set(lock["files"]) if isinstance(lock.get("files"), dict) else {entry["path"] for entry in lock["files"]}
    for rel in (
        "configs/evals/gen5/manifest.json", "configs/evals/gen5/train.json", "configs/evals/gen5/validation.json",
        "configs/evals/gen5/final_test.json", "scripts/gen5_instancer.py", "scripts/verify_harbor_soc.py",
        "configs/evals/gen3/soc_tier1_interactive.json",
    ):
        assert rel in locked, rel
    assert any(path.startswith("configs/evals/gen5/families/") for path in locked)
