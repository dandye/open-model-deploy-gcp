"""soc-cli reads Gen 5 cases, and the reference policies score the same through both transports."""

import json
from pathlib import Path

import pytest

from scripts import gen5_reference_policies as rp
from scripts.soc_sandbox_cli import DEFAULT_EVALSET_PATHS, load_eval_case, run_soc_cli

ROOT_DIR = Path(__file__).resolve().parent.parent
GEN5 = ROOT_DIR / "configs" / "evals" / "gen5"


def _validation_cases():
    return json.loads((GEN5 / "validation.json").read_text(encoding="utf-8"))["eval_cases"]


def _one_per_family(cases):
    seen, picked = set(), []
    for case in cases:
        if case["family_id"] not in seen:
            seen.add(case["family_id"])
            picked.append(case)
    return picked


def _env(tmp_path: Path, case_id: str, evalset_file: Path = None) -> dict:
    env = {
        "SOC_CASE_ID": case_id,
        "SOC_STATE_FILE": str(tmp_path / "state.json"),
        "SOC_TRAJECTORY_FILE": str(tmp_path / "trajectory.jsonl"),
    }
    if evalset_file is not None:
        env["SOC_EVALSET_FILE"] = str(evalset_file)
    return env


def test_default_evalset_paths_include_the_gen5_bundles_after_gen3() -> None:
    names = [p.name for p in DEFAULT_EVALSET_PATHS]
    assert names[0] == "soc_tier1_interactive.json"
    assert "state_bundle.json" in names
    assert {"validation.json", "final_test.json", "train.json"} <= set(names)


def test_soc_cli_resets_a_gen5_case_from_the_committed_bundles(tmp_path: Path) -> None:
    case = _validation_cases()[0]
    env = _env(tmp_path, case["eval_id"])
    rc, payload = run_soc_cli(["reset"], env=env)
    assert rc == 0 and payload["status"] == "RESET"
    hostname = next(iter(case["environment_state"]["hosts"]))
    rc, payload = run_soc_cli(["lookup_entity", "--entity_id", hostname], env=env)
    assert rc == 0 and payload.get("status") != "NOT_FOUND"
    assert hostname.lower() in json.dumps(payload).lower()
    records = [json.loads(line) for line in (tmp_path / "trajectory.jsonl").read_text().splitlines()]
    assert records[0]["tool"] == "lookup_entity"


def test_soc_cli_honors_soc_evalset_file(tmp_path: Path) -> None:
    case = dict(_validation_cases()[0])
    case["eval_id"] = "CASE-GEN5-TEST-01"
    bundle = tmp_path / "bundle.json"
    rp.write_case_bundle(case, bundle)
    rc, payload = run_soc_cli(["reset"], env=_env(tmp_path, "CASE-GEN5-TEST-01", bundle))
    assert rc == 0 and payload["case_id"] == "CASE-GEN5-TEST-01"


def test_soc_cli_refuses_an_unknown_gen5_case_id(tmp_path: Path) -> None:
    rc, payload = run_soc_cli(["reset"], env=_env(tmp_path, "CASE-GEN5-NOPE-99"))
    assert rc == 1 and payload["status"] == "ERROR" and "CASE-GEN5-NOPE-99" in payload["error"]
    assert not (tmp_path / "state.json").exists()


def test_gen3_lookup_keeps_the_stub_fallback() -> None:
    assert load_eval_case("CASE-UNKNOWN") == {"eval_id": "CASE-UNKNOWN"}
    with pytest.raises(LookupError):
        load_eval_case("CASE-UNKNOWN", strict=True)


@pytest.mark.parametrize("policy", ["oracle", "shotgun"])
def test_python_and_soc_cli_transports_agree_per_case(tmp_path: Path, policy: str) -> None:
    for case in _one_per_family(_validation_cases()):
        py = rp.run_policy_on_case(case, policy, 1, tmp_path / "py" / case["eval_id"], split="validation", transport="python")
        cli = rp.run_policy_on_case(case, policy, 1, tmp_path / "cli" / case["eval_id"], split="validation", transport="soc-cli")
        assert cli["transport"] == "soc-cli" and py["transport"] == "python"
        assert abs(py["mean"] - cli["mean"]) <= rp.PARITY_TOLERANCE, (case["eval_id"], py["mean"], cli["mean"])
        if policy == "oracle":
            assert cli["mean"] == 1.0, (case["eval_id"], cli["notes"])


def test_evaluate_transport_parity_flags_disagreements() -> None:
    py = {"oracle": [{"eval_id": "a", "mean": 1.0}, {"eval_id": "b", "mean": 1.0}], "shotgun": [{"eval_id": "a", "mean": 0.2}, {"eval_id": "b", "mean": 0.2}]}
    cli = {"oracle": [{"eval_id": "a", "mean": 1.0}, {"eval_id": "b", "mean": 0.95}], "shotgun": [{"eval_id": "a", "mean": 0.2}, {"eval_id": "b", "mean": 0.2}]}
    gate = rp.evaluate_transport_parity(py, cli)
    assert gate["passed"] is False and gate["failing_cases"] == ["oracle:b"] and gate["max_delta"] == pytest.approx(0.05)
    cli["oracle"][1]["mean"] = 1.0
    assert rp.evaluate_transport_parity(py, cli)["passed"] is True


def test_calibrate_both_transports_reports_parity(tmp_path: Path) -> None:
    report = tmp_path / "cal.md"
    report_json = tmp_path / "cal.json"
    rc = rp.main([
        "calibrate", "--trials", "1", "--splits", "validation", "--transport", "both",
        "--report", str(report), "--json", str(report_json),
    ])
    assert rc == 0
    data = json.loads(report_json.read_text(encoding="utf-8"))
    assert data["meta"]["transport"] == "both"
    assert set(data["results_by_transport"]) == {"python", "soc-cli"}
    assert data["gates"]["transport_parity"]["passed"] is True and data["gates"]["all_passed"] is True
    assert "Transport parity" in report.read_text(encoding="utf-8")


def test_run_command_accepts_the_soc_cli_transport(capsys) -> None:
    rc = rp.main(["run", "--policy", "oracle", "--split", "validation", "--limit", "2", "--transport", "soc-cli"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "oracle: 2 case(s), mean 1.0000" in out
