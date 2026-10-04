"""Tests for the Gen 5 branch of scripts/eval_soc_agent.py: split flags, the ledger gate, scoring, infra segregation."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import scripts.eval_soc_agent as runner
from scripts import gen5_exposure as ex

ROOT_DIR = Path(__file__).resolve().parent.parent
GEN5 = ROOT_DIR / "configs" / "evals" / "gen5"


@pytest.fixture
def ledger(tmp_path, monkeypatch) -> Path:
    path = tmp_path / "exposure.jsonl"
    monkeypatch.setenv(ex.LEDGER_ENV_VAR, str(path))
    monkeypatch.setattr(runner, "INFRA_RETRY_BACKOFF_S", 0.0)
    return path


def _first_family(split: str) -> str:
    return json.loads((GEN5 / f"{split}.json").read_text())["eval_cases"][0]["family_id"]


@pytest.fixture
def mock_run(ledger):
    """Runs run_evaluation hermetically: mock judge, no network, real Gen 5 bundles."""
    def run(**kwargs):
        with patch("scripts.eval_soc_agent.genai.Client"), patch.object(runner.SocTier1Agent, "set_up", return_value=None):
            return runner.run_evaluation(
                evalset_path=GEN5 / f"{kwargs.get('split', 'validation')}.json",
                flavor="mock-flavor",
                judge_backend="mock",
                jev_backend="mock",
                purpose="unit test",
                **kwargs,
            )
    return run


def test_parse_args_accepts_gen5_flags() -> None:
    args = runner.parse_args([
        "--gen", "5", "--split", "validation", "--families", "FAM-A", "FAM-B", "--difficulty", "2", "3",
        "--unseal-final-test", "--purpose", "why", "--preregistration", "x.json", "--infra-retries", "4",
    ])
    assert args.gen == 5 and args.split == "validation"
    assert args.families == ["FAM-A", "FAM-B"] and args.difficulty == [2, 3]
    assert args.unseal_final_test is True and args.purpose == "why"
    assert args.preregistration == "x.json" and args.infra_retries == 4
    defaults = runner.parse_args([])
    assert defaults.gen == 3 and defaults.split is None and defaults.infra_retries == 2


def test_split_flag_resolves_the_gen5_bundle() -> None:
    assert runner.resolve_evalset_path(runner.parse_args(["--split", "train"])) == GEN5 / "train.json"
    assert runner.resolve_evalset_path(runner.parse_args(["--gen", "5"])) == GEN5 / "validation.json"
    gen3 = runner.resolve_evalset_path(runner.parse_args([]))
    assert gen3 == ROOT_DIR / "configs" / "evals" / "gen3" / "soc_tier1_interactive.json"


def test_mock_run_on_one_validation_family_scores_oracle_one(mock_run, ledger) -> None:
    family = _first_family("validation")
    out = mock_run(split="validation", families=[family])
    assert out["generation"] == 5 and out["split"] == "validation"
    assert out["case_results"], "expected at least one case"
    for row in out["case_results"]:
        assert row["family_id"] == family
        assert row["gen5_reward"] == 1.0 and row["passed"] is True
        assert row["infra_failure"] is False and row["inert"] is False
        assert row["rubric_score"] == 100.0
        assert row["case_sha256"] and row["manifest_sha256"]
        assert row["tokens_in"] is not None and row["latency_ms"] is not None
    g5 = out["summary"]["gen5"]
    assert g5["split"] == "validation" and g5["pass_threshold"] == 0.80
    assert g5["scored_cases"] == len(out["case_results"]) and g5["infra_failures"] == 0
    assert g5["mean_reward"] == 1.0 and family in g5["per_family"]
    entries = ex.read_exposure(ledger)
    assert len(entries) == 1 and entries[0]["split"] == "validation"
    assert entries[0]["model"] == "mock-flavor" and entries[0]["run_id"] == out["provenance"]["run_id"]
    assert out["gen5_exposure"] == entries[0]


def test_difficulty_filter_restricts_the_cases(mock_run) -> None:
    out = mock_run(split="train", difficulty=[3])
    assert out["case_results"] and all(row["difficulty"] == 3 for row in out["case_results"])


def test_final_test_is_refused_before_any_agent_setup(ledger) -> None:
    with patch("scripts.eval_soc_agent.genai.Client") as client, patch.object(runner.SocTier1Agent, "set_up") as set_up:
        with pytest.raises(ex.FinalTestSealedError):
            runner.run_evaluation(
                evalset_path=GEN5 / "final_test.json", flavor="m", judge_backend="mock", jev_backend="mock",
                split="final_test", purpose="peek",
            )
    set_up.assert_not_called()
    client.assert_not_called()
    assert not ledger.exists()


def test_cli_exits_2_when_final_test_is_sealed(ledger, capsys) -> None:
    """The CLI maps FinalTestSealedError to exit code 2 with a one-line diagnostic, before any client or agent exists."""
    with patch("scripts.eval_soc_agent.genai.Client") as client, patch.object(runner.SocTier1Agent, "set_up") as set_up:
        with pytest.raises(SystemExit) as exc:
            runner.main([
                "--gen", "5", "--split", "final_test", "--flavor", "m",
                "--judge-backend", "mock", "--jev-backend", "mock", "--purpose", "peek",
            ])
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "FinalTestSealedError" in err
    assert "Traceback" not in err
    set_up.assert_not_called()
    client.assert_not_called()
    assert not ledger.exists()


def test_gen5_rejects_the_legacy_judge(ledger) -> None:
    with pytest.raises(ValueError, match="jev or mock"):
        runner.run_evaluation(
            evalset_path=GEN5 / "validation.json", flavor="m", judge_backend="gemini-2.5-pro",
            split="validation", purpose="x",
        )
    assert not ledger.exists()


def test_is_infra_error_matches_the_markers() -> None:
    assert runner.is_infra_error(RuntimeError("429 RESOURCE_EXHAUSTED: quota exceeded"))
    assert runner.is_infra_error(TimeoutError("deadline exceeded"))
    assert runner.is_infra_error(RuntimeError("503 Service Unavailable"))
    assert not runner.is_infra_error(KeyError("prompt"))
    assert not runner.is_infra_error(ValueError("bad verdict"))


def test_infra_failures_are_retried_and_segregated(ledger) -> None:
    class FlakyAgent:  # not a MagicMock: the class name must not trigger the hermetic mock branch
        calls = 0

        def __init__(self, *args, **kwargs):
            self.environment = None

        def set_up(self):
            return None

        def query(self, prompt):
            FlakyAgent.calls += 1
            raise RuntimeError("429 Too Many Requests")

    family = _first_family("validation")
    with patch("scripts.eval_soc_agent.genai.Client"), patch.object(runner, "SocTier1Agent", FlakyAgent):
        out = runner.run_evaluation(
            evalset_path=GEN5 / "validation.json", flavor="m", judge_backend="jev", jev_backend="mock",
            split="validation", families=[family], purpose="x", infra_retries=2,
        )
    rows = out["case_results"]
    assert rows and all(row["infra_failure"] is True for row in rows)
    assert all(row["gen5_reward"] is None and row["passed"] is False for row in rows)
    assert all(row["infra_attempts"] == 3 for row in rows)
    assert FlakyAgent.calls == 3 * len(rows)
    g5 = out["summary"]["gen5"]
    assert g5["infra_failures"] == len(rows) and g5["scored_cases"] == 0 and g5["mean_reward"] is None
    assert out["summary"]["total_cases"] == 0


def test_non_infra_exceptions_propagate(ledger) -> None:
    class BrokenAgent:
        def __init__(self, *args, **kwargs):
            self.environment = None

        def set_up(self):
            return None

        def query(self, prompt):
            raise KeyError("boom")

    with patch("scripts.eval_soc_agent.genai.Client"), patch.object(runner, "SocTier1Agent", BrokenAgent):
        with pytest.raises(KeyError):
            runner.run_evaluation(
                evalset_path=GEN5 / "validation.json", flavor="m", judge_backend="jev", jev_backend="mock",
                split="validation", families=[_first_family("validation")], purpose="x",
            )


def test_inert_responses_score_zero_and_count_as_inert(ledger) -> None:
    class SilentAgent:
        def __init__(self, *args, **kwargs):
            self.environment = None

        def set_up(self):
            return None

        def query(self, prompt):
            return {"response": "", "trajectory": [], "usage": {"prompt_tokens": 1, "completion_tokens": 0, "total_tokens": 1}}

    family = _first_family("validation")
    with patch("scripts.eval_soc_agent.genai.Client"), patch.object(runner, "SocTier1Agent", SilentAgent):
        out = runner.run_evaluation(
            evalset_path=GEN5 / "validation.json", flavor="m", judge_backend="jev", jev_backend="mock",
            split="validation", families=[family], purpose="x",
        )
    rows = out["case_results"]
    assert rows and all(row["inert"] is True and row["gen5_reward"] == 0.0 and row["passed"] is False for row in rows)
    assert out["summary"]["gen5"]["inert_cases"] == len(rows)
    assert out["summary"]["total_cases"] == len(rows)  # inert cases are scored (0.0), not segregated


def test_summarize_gen5_breaks_down_by_family_and_difficulty() -> None:
    rows = [
        {"family_id": "FAM-A", "difficulty": 1, "gen5_reward": 1.0, "passed": True, "inert": False, "safety_gate_triggered": False, "infra_failure": False},
        {"family_id": "FAM-A", "difficulty": 2, "gen5_reward": 0.6, "passed": False, "inert": False, "safety_gate_triggered": True, "infra_failure": False},
        {"family_id": "FAM-B", "difficulty": 2, "gen5_reward": None, "passed": False, "inert": False, "safety_gate_triggered": False, "infra_failure": True},
    ]
    g5 = runner.summarize_gen5(rows, split="validation")
    assert g5["scored_cases"] == 2 and g5["infra_failures"] == 1 and g5["safety_gate_cases"] == 1
    assert g5["mean_reward"] == 0.8 and g5["pass_rate"] == 50.0
    assert g5["per_family"]["FAM-A"] == {"cases": 2, "mean_reward": 0.8, "passed": 1}
    assert "FAM-B" not in g5["per_family"]
    assert g5["per_difficulty"]["2"]["mean_reward"] == 0.6


def test_gen3_runs_do_not_touch_the_ledger_or_the_gen5_summary(ledger) -> None:
    gen3 = ROOT_DIR / "configs" / "evals" / "gen3" / "soc_tier1_interactive.json"
    with patch("scripts.eval_soc_agent.genai.Client"), patch.object(runner.SocTier1Agent, "set_up", return_value=None):
        out = runner.run_evaluation(evalset_path=gen3, flavor="m", judge_backend="mock", jev_backend="mock")
    assert out["generation"] == 3 and "gen5" not in out["summary"]
    assert out.get("gen5_exposure") is None
    assert not ledger.exists()


def test_markdown_report_renders_the_gen5_section(mock_run) -> None:
    out = mock_run(split="validation", families=[_first_family("validation")])
    text = runner.format_markdown_report(out)
    assert "## Gen 5 reward summary" in text
    assert "| Family |" in text and "Infra failures" in text
