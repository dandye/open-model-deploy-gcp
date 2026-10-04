"""Harbor Gen 5 tasks: layout, answer-key isolation, one environment hash, oracle reward, --check."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib

import pytest

from scripts import generate_harbor_soc_tasks as gen
from scripts.gen5_instancer import canonical_json, sha256_text
from scripts.soc_sandbox_cli import GEN5_CONTAINER_STATE_BUNDLE

ROOT_DIR = Path(__file__).resolve().parent.parent
GEN5 = ROOT_DIR / "configs" / "evals" / "gen5"
COMMITTED_TREE = ROOT_DIR / "evals" / "harbor_soc_gen5"
ANSWER_KEYS = (
    "oracle", "assertions", "reference", "expected_actions", "prohibited_actions",
    "expected_entities", "prohibited_entities", "ground_truth_label", "liveness",
    "difficulty", "family_id", "split", "name",
)


@pytest.fixture(scope="module")
def generated(tmp_path_factory) -> dict:
    out = tmp_path_factory.mktemp("harbor_gen5") / "tree"
    summary = gen.generate_harbor_soc_gen5_suite(output_root=out)
    return {"out": out, "summary": summary}


def _task_dirs(out: Path):
    return sorted(p.parent for p in out.rglob("task.toml"))


def _meta(task_dir: Path) -> dict:
    return tomllib.loads((task_dir / "task.toml").read_text(encoding="utf-8"))


def _full_case(task_dir: Path) -> dict:
    return json.loads((task_dir / "tests" / "case.json").read_text(encoding="utf-8"))["eval_cases"][0]


def _one_per_family(task_dirs):
    seen, picked = set(), []
    for task_dir in task_dirs:
        family = _full_case(task_dir)["family_id"]
        if family not in seen:
            seen.add(family)
            picked.append(task_dir)
    return picked


def test_slug_handles_gen3_and_gen5_ids() -> None:
    assert gen._case_slug("CASE-GEN3-01-LOKIBOT-C2") == "case-01-lokibot-c2"
    assert gen._case_slug("CASE-GEN5-C2-INFOSTEALER-01") == "case-c2-infostealer-01"


def test_container_bundle_path_matches_soc_cli() -> None:
    assert Path("/app") / gen.GEN5_CONTAINER_STATE_BUNDLE_REL == GEN5_CONTAINER_STATE_BUNDLE
    assert f"COPY state_bundle.json /app/{gen.GEN5_CONTAINER_STATE_BUNDLE_REL}" in gen.GEN5_DOCKERFILE_CONTENT
    assert "soc_tier1_interactive.json" not in gen.GEN5_DOCKERFILE_CONTENT


def test_evolved_runbook_list_mirrors_the_optimizer() -> None:
    from agent.gepa_runbook_optimizer import CORE_RUNBOOKS

    assert gen.GEN5_EVOLVED_RUNBOOKS == tuple(CORE_RUNBOOKS)
    for name in gen.GEN5_EVOLVED_RUNBOOKS:
        assert (gen.DEFAULT_GEN5_RUNBOOKS_DIR / name).exists(), name


def test_strip_case_for_state_keeps_only_world_state() -> None:
    case = gen.load_gen5_split(GEN5, "validation")[0]
    stripped = gen.strip_case_for_state(case)
    assert set(stripped) <= set(gen.GEN5_STATE_KEYS)
    assert stripped["eval_id"] == case["eval_id"] and stripped["generation"] == 5
    assert stripped["prompt"] == case["prompt"]
    assert stripped["environment_state"] == case["environment_state"]
    for key in ANSWER_KEYS:
        assert key not in stripped, key


def test_build_state_bundle_is_sorted_and_deterministic() -> None:
    cases = gen.load_gen5_split(GEN5, "validation") + gen.load_gen5_split(GEN5, "final_test")
    first = gen.build_state_bundle(cases)
    second = gen.build_state_bundle(list(reversed(cases)))
    assert first == second
    payload = json.loads(first)
    assert payload["generation"] == 5 and payload["split"] == "harbor_state"
    ids = [c["eval_id"] for c in payload["eval_cases"]]
    assert ids == sorted(ids) and len(ids) == 50


def test_default_tree_has_100_tasks_two_arms_two_splits(generated) -> None:
    summary = generated["summary"]
    assert summary["arms"] == list(gen.DEFAULT_GEN5_ARMS) == ["clean_skills", "gepa_evolved_skills"]
    assert summary["splits"] == list(gen.GEN5_HARBOR_SPLITS) == ["validation", "final_test"]
    assert summary["cases_per_split"] == {"validation": 20, "final_test": 30}
    assert summary["total_tasks"] == 100
    assert len(_task_dirs(generated["out"])) == 100
    for arm in gen.DEFAULT_GEN5_ARMS:
        for split in gen.GEN5_HARBOR_SPLITS:
            assert (generated["out"] / arm / split).is_dir()


def test_every_task_has_the_gen5_layout_and_one_environment_hash(generated) -> None:
    hashes = set()
    for task_dir in _task_dirs(generated["out"]):
        for rel in (
            "task.toml", "instruction.md", "solution/solve.sh", "tests/test.sh", "tests/case.json",
            "tests/manifest.json", "environment/Dockerfile", "environment/state_bundle.json",
            "environment/soc_environment.py", "environment/soc_sandbox_cli.py",
            "environment/verify_harbor_soc.py", "environment/eval_trajectory_verifier.py",
            "environment/eval_cost_engine.py", "environment/jev_judge.py", "environment/jev_evaluator.py",
        ):
            assert (task_dir / rel).exists(), f"{task_dir.name}: {rel}"
        assert not (task_dir / "environment" / "soc_tier1_interactive.json").exists()
        assert os.access(task_dir / "solution" / "solve.sh", os.X_OK)
        assert os.access(task_dir / "tests" / "test.sh", os.X_OK)
        hashes.add(gen.compute_environment_hash(task_dir / "environment"))
    assert len(hashes) == 1
    assert generated["summary"]["environment_hash"] in hashes


def test_tree_manifest_records_provenance_without_timestamps(generated) -> None:
    tree = json.loads((generated["out"] / "manifest.json").read_text(encoding="utf-8"))
    assert tree["generator_version"] == gen.GEN5_GENERATOR_VERSION
    assert tree["environment_hash"] == generated["summary"]["environment_hash"]
    assert tree["gen5_manifest_sha256"] == sha256_text((GEN5 / "manifest.json").read_text(encoding="utf-8"))
    assert tree["arms"] == list(gen.DEFAULT_GEN5_ARMS) and tree["splits"] == list(gen.GEN5_HARBOR_SPLITS)
    assert len(tree["tasks"]) == 100
    assert not any(key in tree for key in ("generated_at", "timestamp", "git_sha"))
    paths = [row["path"] for row in tree["tasks"]]
    assert paths == sorted(paths)
    for row in tree["tasks"]:
        assert set(row) == {"path", "arm", "split", "eval_id", "family_id", "difficulty", "case_sha256"}
        assert (generated["out"] / row["path"] / "task.toml").exists()


def test_task_toml_carries_split_family_difficulty_and_case_sha(generated) -> None:
    gen5_manifest = json.loads((GEN5 / "manifest.json").read_text(encoding="utf-8"))
    by_id = {row["eval_id"]: row for row in gen5_manifest["cases"]}
    for task_dir in _task_dirs(generated["out"]):
        meta = _meta(task_dir)
        arm, split = task_dir.parent.parent.name, task_dir.parent.name
        eval_id = meta["metadata"]["eval_id"]
        row = by_id[eval_id]
        assert meta["schema_version"] == "1.3"
        assert meta["task"]["name"] == f"secops/soc-gen5-{arm}-{split}-{task_dir.name}"
        assert split in meta["task"]["categories"] and arm in meta["task"]["categories"]
        assert meta["metadata"]["skill_arm"] == arm
        assert meta["metadata"]["generation"] == 5
        assert meta["metadata"]["split"] == split == row["split"]
        assert meta["metadata"]["family_id"] == row["family_id"]
        assert meta["metadata"]["difficulty_level"] == row["difficulty"]
        assert meta["metadata"]["difficulty"] == gen.GEN5_DIFFICULTY_NAMES[row["difficulty"]]
        assert meta["metadata"]["case_sha256"] == row["case_sha256"] == sha256_text(canonical_json(_full_case(task_dir)))
        assert "ground_truth_label" not in meta["metadata"]
        for section in ("environment", "agent", "verifier", "solution"):
            assert meta[section]["env"]["SOC_CASE_ID"] == eval_id
            assert meta[section]["env"]["SOC_SKILL_ARM"] == arm
            assert "SOC_EVALSET_FILE" not in meta[section]["env"]
        assert meta["verifier"]["env"]["SOC_SPLIT"] == split
        assert meta["verifier"]["env"]["SOC_JEV_BACKEND"] == "mock"


def test_state_bundle_in_the_image_carries_no_answer_key(generated) -> None:
    task_dir = _task_dirs(generated["out"])[0]
    bundle = json.loads((task_dir / "environment" / "state_bundle.json").read_text(encoding="utf-8"))
    ids = [c["eval_id"] for c in bundle["eval_cases"]]
    assert len(ids) == 50 and len(set(ids)) == 50
    for case in bundle["eval_cases"]:
        assert set(case) <= set(gen.GEN5_STATE_KEYS)
        assert "environment_state" in case and "prompt" in case
        for key in ANSWER_KEYS:
            assert key not in case, (case["eval_id"], key)


def test_tests_dir_holds_the_full_case_and_the_gen5_manifest(generated) -> None:
    manifest_text = (GEN5 / "manifest.json").read_text(encoding="utf-8")
    for task_dir in _task_dirs(generated["out"]):
        case_bundle = json.loads((task_dir / "tests" / "case.json").read_text(encoding="utf-8"))
        assert case_bundle["generation"] == 5 and len(case_bundle["eval_cases"]) == 1
        case = case_bundle["eval_cases"][0]
        assert case["eval_id"] == _meta(task_dir)["metadata"]["eval_id"]
        assert case_bundle["split"] == task_dir.parent.name
        assert "oracle" in case and "expected_actions" in case and "ground_truth_label" in case
        assert (task_dir / "tests" / "manifest.json").read_text(encoding="utf-8") == manifest_text


def test_instruction_md_shows_the_prompt_and_the_arm_but_not_the_family(generated) -> None:
    for task_dir in _task_dirs(generated["out"]):
        case = _full_case(task_dir)
        text = (task_dir / "instruction.md").read_text(encoding="utf-8")
        assert case["prompt"] in text
        assert f"`{case['eval_id']}`" in text
        assert case["family_id"] not in text
        assert "**Scenario:**" not in text
        assert "recommended_actions" in text and "soc_decision.json" in text
        arm = task_dir.parent.parent.name
        if arm == "clean_skills":
            assert "## Active Operational Skill (`secops-triage`)" in text
            assert "GEPA Evolved Runbook" not in text
        if arm == "gepa_evolved_skills":
            for name in gen.GEN5_EVOLVED_RUNBOOKS:
                assert f"### Runbook: {name}" in text


def test_solve_sh_is_rendered_from_the_oracle_block(generated) -> None:
    from scripts.gen5_reference_policies import plan_oracle

    for task_dir in _one_per_family(_task_dirs(generated["out"])):
        case = _full_case(task_dir)
        trial = plan_oracle(case)
        script = (task_dir / "solution" / "solve.sh").read_text(encoding="utf-8")
        assert script.startswith("#!/usr/bin/env bash\nset -euo pipefail\n")
        assert "$SOC_CLI reset" in script
        for step in trial.steps:
            assert f"$SOC_CLI {step['tool']} --json " in script
        assert trial.report_text.strip() in script
        decision = json.loads(script.split('soc_decision.json"\n', 1)[1].split("\nEOF_DECISION", 1)[0])
        assert decision["verdict"] == case["ground_truth_label"]
        assert decision["recommended_actions"] == trial.decision["recommended_actions"]
        assert decision["case_id"] == case["eval_id"]


def _run_oracle_then_verifier(task_dir: Path, trial_root: Path) -> dict:
    """Runs solve.sh then test.sh the way Harbor would, with soc-cli reading only the stripped bundle."""
    meta = _meta(task_dir)
    artifacts = trial_root / "logs" / "artifacts"
    verifier = trial_root / "logs" / "verifier"
    artifacts.mkdir(parents=True)
    verifier.mkdir(parents=True)
    run_env = dict(os.environ)
    run_env.update(meta["solution"]["env"])
    run_env.update(meta["verifier"]["env"])
    run_env.update({
        "SOC_STATE_FILE": str(trial_root / "state.json"),
        "SOC_TRAJECTORY_FILE": str(artifacts / "trajectory.jsonl"),
        "SOC_ARTIFACTS_DIR": str(artifacts),
        "SOC_VERIFIER_DIR": str(verifier),
        # In the container soc-cli finds /app/configs/evals/gen5/state_bundle.json through
        # DEFAULT_EVALSET_PATHS. Locally that path does not exist, so point the CLI at the
        # task's own stripped bundle: the oracle must succeed without the answer key.
        "SOC_EVALSET_FILE": str(task_dir / "environment" / "state_bundle.json"),
        "SOC_CLI_BIN": f"{sys.executable} {ROOT_DIR / 'scripts' / 'soc_sandbox_cli.py'}",
        "SOC_VERIFY_BIN": f"{sys.executable} {ROOT_DIR / 'scripts' / 'verify_harbor_soc.py'}",
    })
    solve = subprocess.run(["bash", str(task_dir / "solution" / "solve.sh")], env=run_env, capture_output=True, text=True, check=False)
    assert solve.returncode == 0, f"solve.sh failed for {task_dir.name}: {solve.stderr}"
    test = subprocess.run(["bash", str(task_dir / "tests" / "test.sh")], env=run_env, capture_output=True, text=True, check=False)
    assert test.returncode == 0, f"test.sh failed for {task_dir.name}: {test.stderr}"
    scorecard = json.loads((verifier / "scorecard.json").read_text(encoding="utf-8"))
    scorecard["_reward_txt"] = float((verifier / "reward.txt").read_text(encoding="utf-8").strip())
    return scorecard


def test_oracle_scores_through_the_container_scripts_on_one_task_per_family(generated, tmp_path) -> None:
    clean = [d for d in _task_dirs(generated["out"]) if d.parent.parent.name == "clean_skills"]
    picked = _one_per_family(clean)
    assert len(picked) == 16
    for idx, task_dir in enumerate(picked):
        scorecard = _run_oracle_then_verifier(task_dir, tmp_path / f"trial_{idx:02d}")
        assert scorecard["_reward_txt"] >= 0.95, (task_dir.name, scorecard["_reward_txt"])
        assert scorecard["reward"] == scorecard["_reward_txt"]
        assert scorecard["generation"] == 5
        assert scorecard["split"] == task_dir.parent.name
        assert scorecard["manifest_case_sha256_matches"] is True
        assert scorecard["inert"] is False and scorecard["safety_gate_triggered"] is False
        assert scorecard["prohibited_entity_violations"] == []


def test_check_passes_on_a_fresh_tree_and_reports_drift(tmp_path) -> None:
    out = tmp_path / "small"
    summary = gen.generate_harbor_soc_gen5_suite(output_root=out, arms=("clean_skills",), splits=("validation",))
    assert summary["total_tasks"] == 20
    assert gen.check_gen5_tree(output_root=out, arms=("clean_skills",), splits=("validation",)) == []

    victim = sorted(out.rglob("instruction.md"))[0]
    victim.write_text(victim.read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8")
    diffs = gen.check_gen5_tree(output_root=out, arms=("clean_skills",), splits=("validation",))
    assert diffs and any(str(victim.relative_to(out)) in line for line in diffs)

    gen.generate_harbor_soc_gen5_suite(output_root=out, arms=("clean_skills",), splits=("validation",))
    extra = out / "clean_skills" / "validation" / "stray.txt"
    extra.write_text("x", encoding="utf-8")
    diffs = gen.check_gen5_tree(output_root=out, arms=("clean_skills",), splits=("validation",))
    assert any("stray.txt" in line and "unexpected" in line for line in diffs)

    extra.unlink()
    missing = sorted(out.rglob("test.sh"))[0]
    missing.unlink()
    diffs = gen.check_gen5_tree(output_root=out, arms=("clean_skills",), splits=("validation",))
    assert any("test.sh" in line and "missing" in line for line in diffs)


def test_cli_check_passes_against_the_committed_tree() -> None:
    assert COMMITTED_TREE.exists(), "run: .venv/bin/python scripts/generate_harbor_soc_tasks.py"
    result = subprocess.run(
        [sys.executable, str(ROOT_DIR / "scripts" / "generate_harbor_soc_tasks.py"), "--check"],
        capture_output=True, text=True, check=False, cwd=ROOT_DIR,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    tree = json.loads((COMMITTED_TREE / "manifest.json").read_text(encoding="utf-8"))
    assert tree["total_tasks"] == 100
    assert tree["gen5_manifest_sha256"] == sha256_text((GEN5 / "manifest.json").read_text(encoding="utf-8"))


def test_cli_rejects_a_bad_split_and_keeps_gen3_behind_a_flag(tmp_path) -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT_DIR / "scripts" / "generate_harbor_soc_tasks.py"), "--split", "train", "--out", str(tmp_path / "x")],
        capture_output=True, text=True, check=False, cwd=ROOT_DIR,
    )
    assert result.returncode == 2 and "train" in result.stderr
    assert not (tmp_path / "x").exists()
    help_text = subprocess.run(
        [sys.executable, str(ROOT_DIR / "scripts" / "generate_harbor_soc_tasks.py"), "--help"],
        capture_output=True, text=True, check=False, cwd=ROOT_DIR,
    ).stdout
    assert "--gen3" in help_text and "--check" in help_text and "--split" in help_text
