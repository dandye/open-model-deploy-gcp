"""Unit tests for Outer-to-Inner Loop CLI Analyzer & Fixture Promoter (`scripts/run_aqua_soc_diagnosis.py`)."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Dict, List
import pytest

from agent.aqua_diagnostics import (
    FORBIDDEN_EVAL_HOSTNAMES,
    AquaDiagnosticReport,
)
from scripts.run_aqua_soc_diagnosis import (
    build_arg_parser,
    build_markdown_report,
    is_forbidden_split_file,
    load_forbidden_literals_from_manifest,
    load_traces_from_inputs,
    main,
    promote_failure_fixtures,
    sanitize_trace_payload,
)


def _contains_emoji_or_dingbat(text: str) -> bool:
    """Checks if text contains emojis or unicode dingbats."""
    for ch in text:
        cp = ord(ch)
        # Check standard emoji / dingbat / symbols ranges
        # Dingbats: U+2700 - U+27BF
        # Misc Symbols: U+2600 - U+26FF
        # Emoticons / Pictographs: U+1F300 - U+1F9FF
        # Transport & Map: U+1F680 - U+1F6FF
        # Supplemental Symbols: U+1FA00 - U+1FAFF
        if (
            0x2700 <= cp <= 0x27BF
            or 0x2600 <= cp <= 0x26FF
            or 0x1F300 <= cp <= 0x1FAFF
        ):
            return True
    return False


def test_arg_parser_defaults() -> None:
    parser = build_arg_parser()
    args = parser.parse_args([])
    assert args.input_json == ["docs/soc_eval_results"]
    assert args.output_report == "docs/soc_eval_results/aqua_diagnostic_report.md"
    assert args.output_json == "docs/soc_eval_results/aqua_diagnostic_report.json"
    assert args.promote_fixtures_dir is None
    assert args.manifest == "configs/evals/gen5/manifest.json"


def test_is_forbidden_split_file() -> None:
    assert is_forbidden_split_file("configs/evals/gen5/final_test.json") is True
    assert is_forbidden_split_file("path/to/final_test.json") is True
    assert is_forbidden_split_file("path/to/final_test/scorecard.json") is True
    assert is_forbidden_split_file("docs/soc_eval_results/gen5_final_test_report.json") is True
    assert is_forbidden_split_file("docs/soc_eval_results/gen5_validation_report.json") is False
    assert is_forbidden_split_file("docs/soc_eval_results/gemini_report.json") is False


def test_load_traces_from_eval_soc_agent_json(tmp_path: Path) -> None:
    # 1. Report with case_results
    eval_file = tmp_path / "eval_report.json"
    eval_file.write_text(
        json.dumps({
            "flavor": "gemini-2.5-flash",
            "case_results": [
                {
                    "eval_id": "CASE-GEN3-01-LOKIBOT-C2",
                    "prompt": "Triage alert for host DESKTOP-FIN-08 (10.0.4.15).",
                    "score": 0.9,
                    "assert_passed": True,
                    "trajectory": [
                        {"tool": "get_domain_report", "args": {"domain": "evil.com"}},
                        {"tool": "isolate_host", "args": {"hostname": "DESKTOP-FIN-08"}},
                    ],
                    "expected_actions": ["isolate_host"],
                    "executed_actions": ["isolate_host"],
                }
            ],
        }),
        encoding="utf-8",
    )

    traces = load_traces_from_inputs([eval_file])
    assert len(traces) == 1
    assert traces[0]["eval_id"] == "CASE-GEN3-01-LOKIBOT-C2"
    assert traces[0]["score"] == 0.9


def test_load_traces_from_results_key(tmp_path: Path) -> None:
    eval_file = tmp_path / "results_report.json"
    eval_file.write_text(
        json.dumps({
            "results": [
                {
                    "case_id": "CASE-GEN5-C2-01",
                    "score": 0.1,
                    "actual_verdict": "BENIGN",
                    "expected_verdict": "MALICIOUS",
                    "trajectory": [],
                }
            ],
        }),
        encoding="utf-8",
    )

    traces = load_traces_from_inputs([eval_file])
    assert len(traces) == 1
    assert traces[0]["case_id"] == "CASE-GEN5-C2-01"


def test_load_traces_from_harbor_trial_directory(tmp_path: Path) -> None:
    trial_dir = tmp_path / "trial_01"
    trial_dir.mkdir()
    scorecard_path = trial_dir / "scorecard.json"
    scorecard_path.write_text(
        json.dumps({
            "case_id": "CASE-GEN5-INFOSTEALER-01",
            "reward": 0.0,
            "components": {
                "epistemic_gate_score": 0.0,
                "operator_action_score": 0.0,
            },
            "decision_outcome": "FALSE_NEGATIVE",
            "operational_loss_usd": 150000.0,
            "loss_penalty": 0.0,
            "epistemic_efficiency": 0.0,
            "inert": False,
            "executed_actions": [],
            "expected_actions": ["isolate_host"],
            "prohibited_actions": ["close_case"],
            "prohibited_entity_violations": [],
            "epistemic_step_count": 0,
        }),
        encoding="utf-8",
    )

    # Optional trajectory.jsonl
    traj_path = trial_dir / "trajectory.jsonl"
    traj_path.write_text(
        json.dumps({"iteration": 1, "tool": "get_domain_report", "args": {"domain": "bad.com"}}) + "\n",
        encoding="utf-8",
    )

    traces = load_traces_from_inputs([trial_dir])
    assert len(traces) == 1
    assert traces[0]["case_id"] == "CASE-GEN5-INFOSTEALER-01"
    assert traces[0]["reward"] == 0.0
    assert len(traces[0]["trajectory"]) == 1


def test_load_traces_skips_summary_and_forbidden_split(tmp_path: Path) -> None:
    eval_dir = tmp_path / "eval_results"
    eval_dir.mkdir()

    # Valid report
    valid_file = eval_dir / "model_report.json"
    valid_file.write_text(
        json.dumps({
            "results": [{"case_id": "CASE-01", "score": 1.0, "trajectory": [{"tool": "lookup_entity"}]}]
        }),
        encoding="utf-8",
    )

    # Summary report to skip
    summary_file = eval_dir / "aqua_diagnostic_report.json"
    summary_file.write_text(json.dumps({"total_cases": 1}), encoding="utf-8")

    # Forbidden final_test file to skip
    forbidden_file = eval_dir / "final_test.json"
    forbidden_file.write_text(
        json.dumps({"eval_cases": [{"case_id": "CASE-SECRET", "score": 1.0}]}),
        encoding="utf-8",
    )

    # Report whose internal payload specifies split: final_test
    forbidden_payload_file = eval_dir / "sneaky_report.json"
    forbidden_payload_file.write_text(
        json.dumps({
            "split": "final_test",
            "case_results": [{"case_id": "CASE-SNEAKY-FINAL", "score": 0.0}],
        }),
        encoding="utf-8",
    )

    traces = load_traces_from_inputs([eval_dir])
    assert len(traces) == 1
    assert traces[0]["case_id"] == "CASE-01"


def test_sanitize_trace_payload() -> None:
    raw_trace = {
        "case_id": "CASE-GEN3-01-LOKIBOT-C2",
        "prompt": "Investigate DESKTOP-FIN-08 and 192.168.1.50 with secret_token_xyz987",
        "trajectory": [
            {
                "tool": "isolate_host",
                "args": {"hostname": "DESKTOP-FIN-08", "ip": "10.0.4.15"},
                "observation": "Host DESKTOP-FIN-08 isolated. Ref: CASE-12345.",
            }
        ],
        "score": 0.0,
    }

    sanitized = sanitize_trace_payload(
        raw_trace,
        forbidden_literals=["secret_token_xyz987"],
    )

    json_str = json.dumps(sanitized)
    assert "CASE-GEN3-01-LOKIBOT-C2" not in json_str
    assert "CASE-12345" not in json_str
    assert "DESKTOP-FIN-08" not in json_str
    assert "192.168.1.50" not in json_str
    assert "10.0.4.15" not in json_str
    assert "secret_token_xyz987" not in json_str
    assert "[CASE_ID_REDACTED]" in json_str or "[REDACTED]" in json_str


def test_promote_failure_fixtures(tmp_path: Path) -> None:
    traces = [
        {
            "case_id": "CASE-GEN3-01-LOKIBOT-C2",
            "prompt": "Triage alert for host DESKTOP-FIN-08 (10.0.4.15).",
            "score": 0.0,
            "assert_passed": False,
            "actual_verdict": "BENIGN",
            "expected_verdict": "MALICIOUS",
            "trajectory": [],
            "expected_actions": ["isolate_host"],
            "component_name": "malware_triage.md",
        },
        {
            "case_id": "CASE-GEN3-02-CLEAN",
            "prompt": "Clean host triage.",
            "score": 1.0,
            "assert_passed": True,
            "actual_verdict": "BENIGN",
            "expected_verdict": "BENIGN",
            "trajectory": [{"tool": "lookup_entity"}],
            "component_name": "basic_ioc_enrichment.md",
        },
        {
            "case_id": "CASE-GEN3-10-AUTHORIZED-SCANNER-NOISE",
            "prompt": "False positive containment on SRV-PROD-PAYMENT-01.",
            "score": 0.30,
            "assert_passed": True,  # substring assertions passed, but case failed overall
            "passed": False,
            "actual_verdict": "MALICIOUS",
            "expected_verdict": "BENIGN",
            "executed_actions": ["isolate_host"],
            "prohibited_actions": ["isolate_host"],
            "trajectory": [{"tool": "lookup_entity"}, {"tool": "isolate_host"}],
            "component_name": "suspicious_login_triage.md",
        },
    ]

    out_fixtures_dir = tmp_path / "promoted_fixtures"
    saved_files = promote_failure_fixtures(
        traces=traces,
        output_dir=out_fixtures_dir,
        forbidden_literals=["secret_leak"],
    )

    assert len(saved_files) == 2
    for saved_path in saved_files:
        assert saved_path.exists()
        assert "case_id_redacted" not in saved_path.name
        content = saved_path.read_text(encoding="utf-8")
        assert "DESKTOP-FIN-08" not in content
        assert "SRV-PROD-PAYMENT-01" not in content
        assert "10.0.4.15" not in content
        assert "CASE-GEN3-01-LOKIBOT-C2" not in content
        assert "CASE-GEN3-10-AUTHORIZED-SCANNER-NOISE" not in content


def test_build_markdown_report_zero_emojis(tmp_path: Path) -> None:
    traces = [
        {
            "case_id": "CASE-GEN3-01-LOKIBOT-C2",
            "score": 0.0,
            "assert_passed": False,
            "actual_verdict": "BENIGN",
            "expected_verdict": "MALICIOUS",
            "trajectory": [],
            "expected_actions": ["isolate_host"],
            "component_name": "malware_triage.md",
        },
        {
            "case_id": "CASE-GEN3-02-CLEAN",
            "score": 1.0,
            "assert_passed": True,
            "actual_verdict": "BENIGN",
            "expected_verdict": "BENIGN",
            "trajectory": [{"tool": "lookup_entity"}],
            "component_name": "basic_ioc_enrichment.md",
        },
    ]

    from agent.aqua_diagnostics import cluster_trace_diagnoses
    report = cluster_trace_diagnoses(traces)
    md = build_markdown_report(report)

    assert "AQuA SOC Trajectory Diagnostic Report" in md
    assert "malware_triage.md" in md
    assert "basic_ioc_enrichment.md" in md
    # Strictly zero emojis or dingbats
    assert not _contains_emoji_or_dingbat(md)
    # Check ASCII
    assert md.isascii()


def test_main_cli_end_to_end(tmp_path: Path) -> None:
    eval_file = tmp_path / "eval_results.json"
    eval_file.write_text(
        json.dumps({
            "case_results": [
                {
                    "case_id": "CASE-01",
                    "score": 0.0,
                    "assert_passed": False,
                    "actual_verdict": "BENIGN",
                    "expected_verdict": "MALICIOUS",
                    "trajectory": [],
                    "expected_actions": ["isolate_host"],
                    "component_name": "malware_triage.md",
                }
            ]
        }),
        encoding="utf-8",
    )

    report_md = tmp_path / "report.md"
    report_json = tmp_path / "report.json"
    fixtures_dir = tmp_path / "fixtures"

    ret = main([
        "--input-json", str(eval_file),
        "--output-report", str(report_md),
        "--output-json", str(report_json),
        "--promote-fixtures-dir", str(fixtures_dir),
    ])

    assert ret == 0
    assert report_md.exists()
    assert report_json.exists()
    assert fixtures_dir.exists()

    md_content = report_md.read_text(encoding="utf-8")
    assert not _contains_emoji_or_dingbat(md_content)
    assert md_content.isascii()

    json_content = json.loads(report_json.read_text(encoding="utf-8"))
    assert json_content["total_cases"] == 1
    assert json_content["failed_cases"] == 1
