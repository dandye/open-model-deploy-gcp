"""Tests for the Gen 5 exposure ledger and split loader (spec section 6.6)."""

import json
from pathlib import Path

import pytest

from scripts import gen5_exposure as ex

ROOT_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture
def ledger(tmp_path, monkeypatch) -> Path:
    path = tmp_path / "exposure.jsonl"
    monkeypatch.setenv(ex.LEDGER_ENV_VAR, str(path))
    return path


def _approved_prereg(tmp_path: Path) -> Path:
    path = tmp_path / "prereg.json"
    path.write_text(json.dumps({
        "schema_version": 1,
        "acceptance": {"approved_by": "owner", "approved_at": "2026-10-10T00:00:00Z"},
        "gen5": {"hypotheses": ["H1: evolved runbooks beat seed on validation by more than tau_accept"]},
    }), encoding="utf-8")
    return path


def test_split_names_and_bundle_paths_are_fixed() -> None:
    assert ex.SPLITS == ("train", "validation", "final_test")
    assert ex.bundle_path("validation") == ex.GEN5_ROOT / "validation.json"
    assert ex.DEFAULT_LEDGER_PATH == ex.GEN5_ROOT / "exposure.jsonl"
    for split in ex.SPLITS:
        assert ex.bundle_path(split).exists(), split


def test_ledger_path_honors_the_test_override(ledger: Path) -> None:
    assert ex.ledger_path() == ledger


def test_eval_ids_sha256_is_order_independent() -> None:
    assert ex.eval_ids_sha256(["b", "a", "c"]) == ex.eval_ids_sha256(["c", "b", "a"])
    assert ex.eval_ids_sha256(["a"]) != ex.eval_ids_sha256(["a", "b"])
    assert len(ex.eval_ids_sha256(["a"])) == 64


def test_filter_cases_by_family_and_difficulty() -> None:
    cases = [
        {"eval_id": "1", "family_id": "FAM-A", "difficulty": 1},
        {"eval_id": "2", "family_id": "FAM-B", "difficulty": 2},
        {"eval_id": "3", "family_id": "FAM-A", "difficulty": 3},
    ]
    assert [c["eval_id"] for c in ex.filter_cases(cases, families=["FAM-A"])] == ["1", "3"]
    assert [c["eval_id"] for c in ex.filter_cases(cases, families=["A"])] == ["1", "3"]
    assert [c["eval_id"] for c in ex.filter_cases(cases, difficulty=[2, 3])] == ["2", "3"]
    assert [c["eval_id"] for c in ex.filter_cases(cases, families=["FAM-A"], difficulty=[3])] == ["3"]
    assert ex.filter_cases(cases) == cases


def test_load_split_appends_exactly_the_spec_keys(ledger: Path) -> None:
    cases, entry = ex.load_split("validation", purpose="unit test", model="mock", run_id="run-1")
    assert len(cases) == 20
    assert tuple(entry) == ex.LEDGER_KEYS
    assert entry["split"] == "validation"
    assert entry["run_id"] == "run-1"
    assert entry["purpose"] == "unit test"
    assert entry["model"] == "mock"
    assert entry["eval_ids_sha256"] == ex.eval_ids_sha256([c["eval_id"] for c in cases])
    lines = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert lines == [entry]


def test_load_split_requires_a_purpose(ledger: Path) -> None:
    with pytest.raises(ex.ExposureError):
        ex.load_split("train", purpose="", model="mock")
    with pytest.raises(ex.ExposureError):
        ex.load_split("train", purpose="   ", model="mock")
    assert not ledger.exists()


def test_filtered_load_hashes_the_filtered_ids(ledger: Path) -> None:
    full, full_entry = ex.load_split("train", purpose="t", model="m", record=False)
    family = full[0]["family_id"]
    some, some_entry = ex.load_split("train", purpose="t", model="m", families=[family], record=False)
    assert 0 < len(some) < len(full)
    assert some_entry["eval_ids_sha256"] != full_entry["eval_ids_sha256"]
    assert not ledger.exists()


def test_final_test_is_sealed_by_default(ledger: Path) -> None:
    with pytest.raises(ex.FinalTestSealedError):
        ex.load_split("final_test", purpose="peek", model="mock")
    with pytest.raises(ex.FinalTestSealedError):
        ex.load_split("final_test", purpose="peek", model="mock", unseal_final_test=True)
    assert not ledger.exists()


def test_final_test_unseal_requires_an_approved_preregistration(ledger: Path, tmp_path: Path) -> None:
    unapproved = tmp_path / "unapproved.json"
    unapproved.write_text(json.dumps({"acceptance": {"approved_by": None, "approved_at": None}, "gen5": {"hypotheses": ["H1"]}}))
    with pytest.raises(ex.FinalTestSealedError):
        ex.load_split("final_test", purpose="campaign 1", model="m", unseal_final_test=True, preregistration=unapproved)
    assert not ledger.exists()

    prereg = _approved_prereg(tmp_path)
    cases, entry = ex.load_split("final_test", purpose="campaign 1", model="m", unseal_final_test=True, preregistration=prereg)
    assert len(cases) == 30
    assert tuple(entry) == ex.LEDGER_KEYS + ("preregistration",)
    assert entry["preregistration"]["sha256"] == ex.sha256_file(prereg)
    assert ex.final_test_exposures() == [entry]


def test_read_exposure_on_a_missing_ledger_is_empty(ledger: Path) -> None:
    assert ex.read_exposure() == []
    assert ex.final_test_exposures() == []


def test_committed_ledger_has_zero_final_test_entries() -> None:
    committed = ROOT_DIR / "configs" / "evals" / "gen5" / "exposure.jsonl"
    assert committed.exists()
    entries = ex.read_exposure(committed)
    assert [e for e in entries if e["split"] == "final_test"] == []
    for entry in entries:
        assert set(ex.LEDGER_KEYS) <= set(entry)


def test_new_run_id_is_unique_and_sortable() -> None:
    first, second = ex.new_run_id(), ex.new_run_id()
    assert first != second
    assert len(first.split("-")) == 2


def test_sealed_final_test_is_refused_before_the_bundle_is_read(ledger: Path, tmp_path: Path, monkeypatch) -> None:
    def _explode(*args, **kwargs):
        raise AssertionError("bundle must not be read")

    monkeypatch.setattr(ex, "read_bundle", _explode)
    with pytest.raises(ex.FinalTestSealedError):
        ex.load_split("final_test", purpose="peek", model="m")
    with pytest.raises(ex.FinalTestSealedError):
        ex.load_split("final_test", purpose="peek", model="m", unseal_final_test=True)
    unapproved = tmp_path / "unapproved.json"
    unapproved.write_text(json.dumps({"acceptance": {"approved_by": None, "approved_at": None}, "gen5": {"hypotheses": ["H1"]}}), encoding="utf-8")
    with pytest.raises(ex.FinalTestSealedError):
        ex.load_split("final_test", purpose="peek", model="m", unseal_final_test=True, preregistration=unapproved)
    with pytest.raises(ex.ExposureError):
        ex.load_split("train", purpose="", model="m")
    assert not ledger.exists()


def test_empty_filters_match_nothing(ledger: Path) -> None:
    cases = ex.read_bundle("train")["eval_cases"]
    assert ex.filter_cases(cases, families=[]) == []
    assert ex.filter_cases(cases, difficulty=[]) == []
    assert ex.filter_cases(cases) == list(cases)
    with pytest.raises(ex.ExposureError):
        ex.load_split("train", purpose="t", model="m", families=[], record=False)
    assert not ledger.exists()

