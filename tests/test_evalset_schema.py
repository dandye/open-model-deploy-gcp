"""Unit and schema validation tests for SOC Tier 1 declarative evaluation dataset."""

import json
from pathlib import Path
import pytest

EVALSET_PATH = Path("configs/evals/soc_tier1_evalset.json")

REQUIRED_CASE_IDS = [
    "CASE-01-LOKIBOT-C2",
    "CASE-02-RFC5737-BENIGN-IP",
    "CASE-03-PHISHING-CRED-HARVEST",
    "CASE-04-DUPLICATE-SOAR-CASE",
    "CASE-05-RANSOMWARE-ESCALATION",
]


def test_evalset_file_exists():
    """Verifies that the evaluation dataset JSON file exists."""
    assert EVALSET_PATH.exists(), f"Expected evalset file at {EVALSET_PATH}"


def test_evalset_top_level_schema():
    """Verifies top-level metadata fields in the evalset JSON."""
    assert EVALSET_PATH.exists()
    with open(EVALSET_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("evalset_id") == "soc_tier1_triage"
    assert isinstance(data.get("name"), str) and len(data["name"]) > 0
    assert isinstance(data.get("description"), str) and len(data["description"]) > 0
    assert isinstance(data.get("eval_cases"), list)
    assert len(data["eval_cases"]) == 5


def test_evalset_expected_case_ids():
    """Verifies that all 5 required SOC evaluation cases are defined with unique IDs."""
    assert EVALSET_PATH.exists()
    with open(EVALSET_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    found_ids = [case.get("eval_id") for case in data.get("eval_cases", [])]
    assert len(found_ids) == len(set(found_ids)), "Duplicate eval_id found in eval_cases"

    for required_id in REQUIRED_CASE_IDS:
        assert required_id in found_ids, f"Missing required eval_id: {required_id}"


def test_evalset_cases_structure_and_types():
    """Verifies required fields, types, and non-empty values for every eval case."""
    assert EVALSET_PATH.exists()
    with open(EVALSET_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    for case in data.get("eval_cases", []):
        eval_id = case.get("eval_id", "<unknown>")
        assert isinstance(case.get("name"), str) and len(case["name"]) > 0, f"{eval_id}: missing or empty name"
        assert isinstance(case.get("prompt"), str) and len(case["prompt"]) > 0, f"{eval_id}: missing or empty prompt"

        # Reference validation
        ref = case.get("reference")
        assert isinstance(ref, dict), f"{eval_id}: reference must be a dict"
        assert "expected_verdict" in ref, f"{eval_id}: reference missing expected_verdict"
        assert isinstance(ref.get("grading_rubric"), str) and len(ref["grading_rubric"]) > 0, (
            f"{eval_id}: reference missing or empty grading_rubric"
        )

        # Assertions validation
        assertions = case.get("assertions")
        assert isinstance(assertions, dict), f"{eval_id}: assertions must be a dict"
        assert "must_contain" in assertions, f"{eval_id}: assertions missing must_contain"
        assert "must_not_contain" in assertions, f"{eval_id}: assertions missing must_not_contain"
        assert isinstance(assertions["must_contain"], list), f"{eval_id}: must_contain must be a list"
        assert isinstance(assertions["must_not_contain"], list), f"{eval_id}: must_not_contain must be a list"
        assert len(assertions["must_contain"]) > 0, f"{eval_id}: must_contain must have at least one element"

        for item in assertions["must_contain"]:
            assert isinstance(item, str) and len(item) > 0
        for item in assertions["must_not_contain"]:
            assert isinstance(item, str) and len(item) > 0


def test_evalset_no_emojis_in_dataset():
    """Verifies no unicode emojis exist in the evalset file."""
    assert EVALSET_PATH.exists()
    with open(EVALSET_PATH, "r", encoding="utf-8") as f:
        raw_text = f.read()

    for char in raw_text:
        cp = ord(char)
        is_emoji = (
            (0x1F600 <= cp <= 0x1F64F)
            or (0x1F300 <= cp <= 0x1F5FF)
            or (0x1F680 <= cp <= 0x1F6FF)
            or (0x1F700 <= cp <= 0x1F77F)
            or (0x1F780 <= cp <= 0x1F7FF)
            or (0x1F800 <= cp <= 0x1F8FF)
            or (0x1F900 <= cp <= 0x1F9FF)
            or (0x1FA00 <= cp <= 0x1FA6F)
            or (0x1FA70 <= cp <= 0x1FAFF)
            or (0x2600 <= cp <= 0x26FF)
            or (0x2700 <= cp <= 0x27BF)
        )
        assert not is_emoji, f"Emoji character detected in evalset: '{char}' (U+{cp:04X})"
