"""Tests for scripts/harness_lock.py: approve and verify without importing any model code."""

from pathlib import Path

from scripts import harness_lock


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
