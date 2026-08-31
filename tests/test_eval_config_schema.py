"""Unit and schema validation tests for expanded 10-case SOC Tier 1 evaluation suite."""

import json
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT_DIR / "configs" / "evals" / "soc_tier1_triage.json"

EXPECTED_CASE_IDS = [
    "CASE-01-LOKIBOT-C2",
    "CASE-02-RFC5737-BENIGN-IP",
    "CASE-03-PHISHING-CRED-HARVEST",
    "CASE-04-DUPLICATE-SOAR-CASE",
    "CASE-05-RANSOMWARE-ESCALATION",
    "CASE-06-AMBIGUOUS-DNS-TUNNEL",
    "CASE-07-LATERAL-MOVEMENT",
    "CASE-08-SUPPLY-CHAIN-REVOKED-CERT",
    "CASE-09-TOOL-FAILURE-RESILIENCE",
    "CASE-10-AUTHORIZED-SCANNER-TRUE-NEGATIVE",
]


def test_eval_suite_contains_ten_cases():
    """Verify configs/evals/soc_tier1_triage.json contains exactly 10 valid cases."""
    assert CONFIG_PATH.exists(), f"Expected eval config file at {CONFIG_PATH}"
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    assert data.get("evalset_id") == "soc_tier1_triage"
    assert isinstance(data.get("name"), str) and len(data["name"]) > 0
    assert isinstance(data.get("description"), str) and len(data["description"]) > 0
    assert isinstance(data.get("eval_cases"), list)
    assert len(data["eval_cases"]) == 10

    case_ids = [c.get("eval_id") for c in data["eval_cases"]]
    assert case_ids == EXPECTED_CASE_IDS


def test_eval_suite_case_structure_and_types():
    """Verify all 10 cases have required schema fields, rubric, and assertions."""
    assert CONFIG_PATH.exists()
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    for case in data.get("eval_cases", []):
        eval_id = case.get("eval_id", "<unknown>")
        assert "eval_id" in case, "Case missing eval_id"
        assert isinstance(case.get("name"), str) and len(case["name"]) > 0, f"{eval_id}: missing name"
        assert isinstance(case.get("prompt"), str) and len(case["prompt"]) > 0, f"{eval_id}: missing prompt"

        # Reference validation
        ref = case.get("reference")
        assert isinstance(ref, dict), f"{eval_id}: reference must be a dict"
        assert "expected_verdict" in ref, f"{eval_id}: reference missing expected_verdict"
        assert "grading_rubric" in ref, f"{eval_id}: reference missing grading_rubric"
        assert isinstance(ref["grading_rubric"], str) and len(ref["grading_rubric"]) > 0

        # Assertions validation
        assertions = case.get("assertions")
        assert isinstance(assertions, dict), f"{eval_id}: assertions must be a dict"
        assert "must_contain" in assertions, f"{eval_id}: assertions missing must_contain"
        assert "must_not_contain" in assertions, f"{eval_id}: assertions missing must_not_contain"
        assert isinstance(assertions["must_contain"], list), f"{eval_id}: must_contain must be list"
        assert isinstance(assertions["must_not_contain"], list), f"{eval_id}: must_not_contain must be list"
        assert len(assertions["must_contain"]) > 0, f"{eval_id}: must_contain must be non-empty"


def test_eval_suite_no_emojis():
    """Verify zero unicode emojis exist in soc_tier1_triage.json."""
    assert CONFIG_PATH.exists()
    raw_text = CONFIG_PATH.read_text(encoding="utf-8")

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
        assert not is_emoji, f"Emoji character detected in eval config: '{char}' (U+{cp:04X})"


def test_live_mcp_evalset_structure():
    """Verify configs/evals/soc_live_mcp_evalset.json has valid schema and cases."""
    live_path = ROOT_DIR / "configs" / "evals" / "soc_live_mcp_evalset.json"
    assert live_path.exists(), f"Missing live MCP evalset at {live_path}"
    data = json.loads(live_path.read_text(encoding="utf-8"))
    assert data.get("evalset_id") == "soc_live_mcp_evalset"
    assert len(data.get("eval_cases", [])) == 5

    for case in data["eval_cases"]:
        assert "eval_id" in case
        assert "prompt" in case
        assert "reference" in case
        assert "grading_rubric" in case["reference"]
        assert "assertions" in case
        assert len(case["assertions"].get("must_contain", [])) > 0


def test_live_mcp_evalset_no_emojis():
    """Verify zero unicode emojis exist in soc_live_mcp_evalset.json."""
    live_path = ROOT_DIR / "configs" / "evals" / "soc_live_mcp_evalset.json"
    raw_text = live_path.read_text(encoding="utf-8")
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
        assert not is_emoji, f"Emoji character detected in live eval config: '{char}' (U+{cp:04X})"
