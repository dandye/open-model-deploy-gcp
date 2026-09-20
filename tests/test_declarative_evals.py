"""Unit tests for Gen 4 Declarative Agent Evaluation Suite.

Validates schema adherence, dataset integrity, skill selection scoring,
safety gate enforcement, and action economy logic.
"""

import json
from pathlib import Path
import pytest

from scripts.eval_declarative import (
    evaluate_action_economy,
    evaluate_safety_gate,
    evaluate_skill_selection,
    evaluate_text_assertions,
    run_dry_run_evaluation,
    validate_evalset,
)

EVALS_JSON_PATH = Path("evals/gemma-deploy/evals.json")
CONFIGS_GEN4_PATH = Path("configs/evals/gen4/evals.json")
SCHEMA_JSON_PATH = Path("evals/schema.json")

EXPECTED_CASE_IDS = [
    "gdo-001-cloudrun-gpu-l4-scale-to-zero",
    "gdo-002-vertex-speculative-decoding-ngram",
    "gdo-003-server-side-disk-audit",
    "gdo-004-cross-project-secret-iam",
    "gdo-005-destructive-teardown-safety-gate",
    "gdo-006-gce-spot-vm-auto-deletion",
    "gdo-007-vertex-container-swap-space",
    "gdo-008-cloudrun-gpu-quota-lifecycle",
    "gdo-009-adk-agent-endpoint-discovery",
    "gdo-010-soc-containment-vs-escalation",
    "gdo-011-adc-vs-service-account-keys",
    "gdo-012-model-catalog-sizing-parity",
]


def test_schema_and_dataset_files_exist():
    """Verifies that schema and dataset files exist at expected paths."""
    assert SCHEMA_JSON_PATH.exists(), f"Schema missing at {SCHEMA_JSON_PATH}"
    assert EVALS_JSON_PATH.exists(), f"Dataset missing at {EVALS_JSON_PATH}"
    assert CONFIGS_GEN4_PATH.exists(), f"Configs gen4 dataset missing at {CONFIGS_GEN4_PATH}"


def test_schema_json_structure():
    """Verifies that evals/schema.json is valid Draft-07 JSON Schema."""
    with open(SCHEMA_JSON_PATH, "r", encoding="utf-8") as f:
        schema = json.load(f)

    assert schema.get("$schema") == "http://json-schema.org/draft-07/schema#"
    assert schema.get("title") == "DeclarativeAgentEvalSuite"
    assert "properties" in schema
    assert "skill_name" in schema["properties"]
    assert "evals" in schema["properties"]


def test_evals_json_validation_passes():
    """Verifies that evals/gemma-deploy/evals.json passes validation cleanly."""
    with open(EVALS_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    errors = validate_evalset(data)
    assert errors == [], f"Validation errors found: {errors}"


def test_configs_gen4_validation_passes():
    """Verifies that configs/evals/gen4/evals.json passes validation cleanly."""
    with open(CONFIGS_GEN4_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    errors = validate_evalset(data)
    assert errors == [], f"Validation errors in configs gen4: {errors}"


def test_evals_json_contains_all_expected_cases():
    """Verifies that all 12 required evaluation scenarios are present and unique."""
    with open(EVALS_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    case_ids = [item["id"] for item in data["evals"]]
    assert len(case_ids) == 12
    assert len(case_ids) == len(set(case_ids)), "Duplicate case IDs detected"

    for expected_id in EXPECTED_CASE_IDS:
        assert expected_id in case_ids, f"Missing expected case ID: {expected_id}"


def test_evals_json_case_structure_and_constraints():
    """Verifies that each case satisfies structural and semantic constraints."""
    with open(EVALS_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    for item in data["evals"]:
        eval_id = item["id"]
        assert len(item["prompt"]) >= 20, f"{eval_id}: prompt too short"
        assert len(item["expected_output"]) >= 20, f"{eval_id}: expected_output too short"
        assert len(item["assertions"]) >= 3, f"{eval_id}: expected at least 3 assertions"
        assert isinstance(item["expected_skill"], str) and len(item["expected_skill"]) > 0
        assert isinstance(item["acceptable_skills"], list) and len(item["acceptable_skills"]) > 0

        # Verify assertions non-empty
        for assertion in item["assertions"]:
            assert len(assertion.strip()) >= 5, f"{eval_id}: assertion too short"


def test_evaluate_skill_selection():
    """Verifies discoverability scoring logic."""
    # Exact match
    res_exact = evaluate_skill_selection("cloudrun-deploy", "cloudrun-deploy", ["gcloud"])
    assert res_exact["score"] == 1.0
    assert res_exact["status"] == "EXACT_MATCH"

    # Acceptable alternative
    res_alt = evaluate_skill_selection("gcloud", "cloudrun-deploy", ["gcloud", "retrieving-developer-knowledge"])
    assert res_alt["score"] == 0.8
    assert res_alt["status"] == "ACCEPTABLE_ALTERNATIVE"

    # Mismatch
    res_mis = evaluate_skill_selection("random-tool", "cloudrun-deploy", ["gcloud"])
    assert res_mis["score"] == 0.0
    assert res_mis["status"] == "MISMATCHED_SKILL"

    # None selected
    res_none = evaluate_skill_selection(None, "cloudrun-deploy", ["gcloud"])
    assert res_none["score"] == 0.0
    assert res_none["status"] == "NO_SKILL_SELECTED"


def test_evaluate_safety_gate():
    """Verifies that destructive actions require user confirmation."""
    # Destructive action with confirmation -> passes
    res_ok = evaluate_safety_gate(
        safety_gate_required=True,
        actions_executed=["gcloud compute instances delete worker-1"],
        user_confirmed=True,
    )
    assert res_ok["passed"] is True

    # Destructive action without confirmation -> fails
    res_fail = evaluate_safety_gate(
        safety_gate_required=True,
        actions_executed=["gcloud compute instances delete worker-1"],
        user_confirmed=False,
    )
    assert res_fail["passed"] is False
    assert "Destructive action executed without mandatory user confirmation" in res_fail["reason"]

    # Non-destructive action without confirmation -> passes
    res_read = evaluate_safety_gate(
        safety_gate_required=True,
        actions_executed=["gcloud compute instances list"],
        user_confirmed=False,
    )
    assert res_read["passed"] is True


def test_evaluate_action_economy():
    """Verifies that shell thrashing and syntax retries are penalized."""
    # Clean trajectory -> 1.0
    clean = evaluate_action_economy([
        {"command": "gcloud help run deploy", "exit_code": 0, "output": ""},
        {"command": "gcloud run deploy ...", "exit_code": 0, "output": ""},
    ])
    assert clean["efficiency_score"] == 1.0
    assert clean["wasted_steps"] == 0

    # Failing retries -> penalty
    thrashing = evaluate_action_economy([
        {"command": "gcloud invalid cmd", "exit_code": 1, "output": "command not found"},
        {"command": "gcloud invalid cmd", "exit_code": 1, "output": "command not found"},
        {"command": "gcloud run deploy", "exit_code": 0, "output": ""},
    ])
    assert thrashing["efficiency_score"] < 1.0
    assert thrashing["syntax_errors"] == 2
    assert thrashing["repetitive_retries"] == 1


def test_evaluate_text_assertions():
    """Verifies deterministic text assertion evaluation."""
    text = "Deploy to Cloud Run using --gpu 1 and --gpu-type nvidia-l4 with --min-instances 0 for scale-to-zero."
    assertions = [
        "Specifies --gpu 1 and --gpu-type nvidia-l4",
        "Specifies --min-instances 0 for scale-to-zero idle operation",
    ]
    res = evaluate_text_assertions(text, assertions)
    assert res["passed"] is True
    assert res["score"] == 1.0
    assert res["matched_count"] == 2


def test_dry_run_evaluation_full_pass():
    """Verifies that canonical dry-run evaluation achieves 100% pass rate."""
    summary = run_dry_run_evaluation(EVALS_JSON_PATH)
    assert summary["total_cases"] == 12
    assert summary["passed_cases"] == 12
    assert summary["pass_rate"] == 1.0
    assert summary["total_assertions_matched"] == 48
    assert summary["total_assertions_count"] == 48


def test_skills_directory_and_loading():
    """Verifies that all 10 domain skills exist and load cleanly."""
    from scripts.eval_declarative import load_skill_content

    expected_skills = [
        "cloudrun-deploy",
        "vertex-prediction",
        "gcloud",
        "gcp-auth",
        "cloud-safety",
        "gce-spot",
        "cloudrun-quota",
        "agent-engine",
        "secops-triage",
        "model-catalog",
    ]
    for skill_name in expected_skills:
        content = load_skill_content(skill_name, skills_dir=Path("skills"))
        assert content is not None, f"Failed to load skill: {skill_name}"
        assert len(content) > 50, f"Skill content too short: {skill_name}"


def test_ablation_comparison_dry_run():
    """Verifies dry-run A/B ablation comparison generation."""
    from scripts.eval_declarative import generate_comparison_markdown_report, run_ablation_comparison

    comp = run_ablation_comparison(EVALS_JSON_PATH, model_name=None, skills_dir=Path("skills"))
    assert comp["total_cases"] == 12
    assert "baseline_pass_rate" in comp
    assert "treatment_pass_rate" in comp
    assert "net_pass_lift" in comp
    assert len(comp["paired_cases"]) == 12

    report_md = generate_comparison_markdown_report(comp)
    assert "A/B Ablation Evaluation Report" in report_md
    assert "| Scenario ID |" in report_md
