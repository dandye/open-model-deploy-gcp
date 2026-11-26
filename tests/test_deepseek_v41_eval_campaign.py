"""Hermetic unit tests for scripts/run_deepseek_v41_eval_campaign.py."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import pytest

from agent.gemma_agent import GemmaAgent
from agent.hillclimb_harness import BudgetExceeded, BudgetLedger
from scripts import run_deepseek_v41_eval_campaign as camp


def _mock_zero_gpu_http(url: str, headers: Dict[str, str]) -> Dict[str, Any]:
    assert headers.get("Authorization") == "Bearer mock-token"
    if "/endpoints" in url:
        return {
            "endpoints": [
                {"name": "projects/p/locations/us-central1/endpoints/123", "deployedModels": []}
            ]
        }
    if "/aggregated/instances" in url:
        return {
            "items": {
                "zones/us-central1-a": {
                    "instances": [
                        {
                            "name": "terminated-vm",
                            "status": "TERMINATED",
                            "scheduling": {"provisioningModel": "SPOT"},
                            "guestAccelerators": [{"acceleratorCount": 1}],
                        }
                    ]
                }
            }
        }
    raise AssertionError(f"Unexpected URL: {url}")


def test_parse_args_defaults_and_flags() -> None:
    args = camp.parse_args([])
    assert args.max_usd == 10.0
    assert args.temperature == 0.0
    assert args.jev_backend == "gliner_decide"
    assert args.resume_existing is False

    custom = camp.parse_args([
        "--max-usd", "5.5",
        "--temperature", "0.0",
        "--jev-backend", "mock",
        "--resume-existing",
    ])
    assert custom.max_usd == 5.5
    assert custom.temperature == 0.0
    assert custom.jev_backend == "mock"
    assert custom.resume_existing is True


def test_fail_closed_maas_access_gated_artifacts_and_redaction(tmp_path: Path) -> None:
    soc_doc = tmp_path / "soc_model_comparative_evals.md"
    llama_doc = tmp_path / "llama_model_comparative_evals.md"
    soc_doc.write_text("# Comparative\n\n## 4. Key Architectural Takeaways for Gemma Deployments\n", encoding="utf-8")
    llama_doc.write_text("# Partner\n\n## 3. Key Observations & Comparison\n", encoding="utf-8")

    probe_calls: List[str] = []

    def _gated_probe(
        url: str,
        headers: Dict[str, str],
        payload: Dict[str, Any],
        max_retries: int = 1,
    ) -> Tuple[float, Optional[Dict[str, Any]], Optional[str], int]:
        assert max_retries == 1
        assert payload["temperature"] == 0.0
        probe_calls.append(payload["model"])
        return (
            0.18,
            None,
            "HTTP 404: Publisher Model projects/secret-proj-999/locations/global/publishers/deepseek-ai/models/deepseek-v4.1 not found",
            404,
        )

    out_dir = tmp_path / "results"
    res = camp.run_campaign(
        max_usd=10.0,
        temperature=0.0,
        jev_backend="mock",
        resume_existing=False,
        output_dir=out_dir,
        project_id="secret-proj-999",
        soc_comparative_doc=soc_doc,
        llama_comparative_doc=llama_doc,
        auth_fn=lambda _: ("mock-token", "secret-proj-999"),
        probe_request_fn=_gated_probe,
        gpu_audit_http_fn=_mock_zero_gpu_http,
    )

    # Exactly 1 probe per model (no retry loop)
    assert probe_calls == [camp.PRIMARY_MODEL_ID, camp.BASELINE_MODEL_ID]
    assert res["status"] == "MAAS_ACCESS_GATED"
    assert res["zero_gpu_audit"]["zero_gpu_verified"] is True
    assert res["zero_gpu_audit"]["active_vertex_gpu_endpoints"] == 0
    assert res["zero_gpu_audit"]["active_gce_spot_or_gpu_vms"] == 0

    bench_file = out_dir / "deepseek-v4.1-flash-1017-maas_benchmark.json"
    rep_json = out_dir / "DEEPSEEK_V4_1_FLASH_EVALUATION_REPORT.json"
    rep_md = out_dir / "DEEPSEEK_V4_1_FLASH_EVALUATION_REPORT.md"
    assert bench_file.exists()
    assert rep_json.exists()
    assert rep_md.exists()

    for artifact in (bench_file, rep_json, rep_md, soc_doc, llama_doc):
        txt = artifact.read_text(encoding="utf-8")
        assert "secret-proj-999" not in txt
        assert "MAAS_ACCESS_GATED" in txt
        assert chr(0x2014) not in txt

    md_text = rep_md.read_text(encoding="utf-8")
    assert "## 1. Executive Summary" in md_text
    assert "\\$0.00/hr" in md_text


def test_budget_ceiling_blocks_execution_before_overspend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ledger = BudgetLedger(path=tmp_path / "ledger.json", limit_usd=0.03)
    ledger.record(run_key="seed_spend", delta_usd=0.02, prompt_tokens=1000, completion_tokens=500)

    called = False

    def _should_not_run(self: GemmaAgent, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        nonlocal called
        called = True
        return {"response": "unreachable"}

    monkeypatch.setattr(GemmaAgent, "query", _should_not_run)

    agent = GemmaAgent(project_id="test-proj", managed_model=camp.PRIMARY_MODEL_ID)
    with pytest.raises(BudgetExceeded):
        with camp.enforce_campaign_llm_policy(ledger, temperature=0.0, step_label="test_gate"):
            agent.query("Hello")

    assert called is False


def test_enforce_campaign_llm_policy_forces_temp_zero_and_records_tokens(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    observed_temps: List[float] = []

    def _fake_query(
        self: GemmaAgent,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        image_urls: Optional[List[str]] = None,
        tools_schema: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        observed_temps.append(temperature)
        return {
            "response": "Grounded output",
            "model": camp.PRIMARY_MODEL_ID,
            "token_count_source": "actual",
            "usage": {"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500},
        }

    monkeypatch.setattr(GemmaAgent, "query", _fake_query)
    ledger = BudgetLedger(path=tmp_path / "ledger.json", limit_usd=10.0)
    agent = GemmaAgent(project_id="test-proj", managed_model=camp.PRIMARY_MODEL_ID)

    with camp.enforce_campaign_llm_policy(ledger, temperature=0.0, step_label="unit_step") as stats:
        agent.query("Test prompt", temperature=0.9)

    assert observed_temps == [0.0]
    assert stats["calls"] == 1
    assert stats["prompt_tokens"] == 1000
    assert stats["completion_tokens"] == 500
    expected_cost = round((1000 * 0.30 + 500 * 1.20) / 1_000_000.0, 6)
    assert ledger.spent_usd == pytest.approx(expected_cost)


def test_resume_existing_idempotency_skips_completed_phases(tmp_path: Path) -> None:
    out_dir = tmp_path / "results"
    out_dir.mkdir(parents=True)
    soc_doc = tmp_path / "soc_comparative.md"
    llama_doc = tmp_path / "llama_comparative.md"
    soc_doc.write_text("# SOC\n\n## 4. Key Architectural Takeaways for Gemma Deployments\n", encoding="utf-8")
    llama_doc.write_text("# Partner\n\n## 3. Key Observations & Comparison\n", encoding="utf-8")

    # Pre-populate completed benchmark, Gen 3, Gen 5, and Threat Hunt artifacts
    for flavor in (camp.PRIMARY_FLAVOR, camp.BASELINE_FLAVOR):
        (out_dir / f"{flavor}_benchmark.json").write_text(
            json.dumps([
                {
                    "status": "OK",
                    "concurrency": 1,
                    "avg_latency_s": 1.5,
                    "ttft_p50_ms": 600.0,
                    "ttft_p95_ms": 700.0,
                    "itl_mean_ms": 22.0,
                    "itl_p50_ms": 20.0,
                    "aggregate_tps": 35.0,
                    "request_normalized_tps": 35.0,
                    "token_count_source": "actual",
                    "vision_check": {"status": "OK", "status_code": 200, "latency_ms": 550.0},
                },
                {
                    "status": "OK",
                    "concurrency": 4,
                    "avg_latency_s": 2.1,
                    "ttft_p50_ms": 800.0,
                    "ttft_p95_ms": 950.0,
                    "itl_mean_ms": 28.0,
                    "itl_p50_ms": 25.0,
                    "aggregate_tps": 110.0,
                    "request_normalized_tps": 30.0,
                    "token_count_source": "actual",
                },
            ]),
            encoding="utf-8",
        )
        (out_dir / f"{flavor}_gen3_report.json").write_text(
            json.dumps({
                "status": "COMPLETED",
                "flavor": flavor,
                "summary": {
                    "passed_cases": 9,
                    "total_cases": 10,
                    "pass_rate": 90.0,
                    "avg_rubric_score": 92.0,
                    "mean_harbor_reward": 0.945,
                    "total_tool_calls": 21,
                    "avg_epistemic_efficiency": 0.95,
                    "actions_matched_rate": 90.0,
                    "avg_latency_s": 8.5,
                    "avg_generation_tps": 34.0,
                    "sdt_metrics": {"d_prime": 2.85, "criterion_c": -0.10},
                    "operational_loss": {"total_loss_usd": 250.0, "fp_loss_usd": 250.0, "fn_loss_usd": 0.0},
                },
                "case_results": [
                    {
                        "eval_id": f"CASE-{i:02d}",
                        "name": f"Case {i}",
                        "passed": True,
                        "rubric_score": 92.0,
                        "harbor_reward": 0.945,
                        "decision_outcome": "TRUE_POSITIVE",
                        "case_loss_usd": 0.0,
                        "latency_s": 8.5,
                        "trajectory": [{"tool": "lookup_entity"}],
                    }
                    for i in range(10)
                ],
            }),
            encoding="utf-8",
        )

    for arm in ("clean_skills", "harness2_evolved"):
        (out_dir / f"{camp.PRIMARY_FLAVOR}_gen5_validation_{arm}_report.json").write_text(
            json.dumps({
                "status": "COMPLETED",
                "split": "validation",
                "arm": arm,
                "arm_source": arm,
                "runbook_words": 350 if arm == "clean_skills" else 1743,
                "gen5_exposure": {"split": "validation", "run_id": f"cached-{arm}"},
                "summary": {
                    "total_cases": 20,
                    "total_tool_calls": 100,
                    "sdt_metrics": {"d_prime": 2.91, "criterion_c": -0.23},
                    "operational_loss": {"total_loss_usd": 0.0},
                    "per_verdict_harbor_reward": {
                        "MALICIOUS": 0.98,
                        "BENIGN": 0.98,
                        "SUSPICIOUS": 0.95,
                        "INCONCLUSIVE": 0.98,
                    },
                    "gen5": {
                        "split": "validation",
                        "total_cases": 20,
                        "scored_cases": 20,
                        "passed_cases": 20,
                        "pass_rate": 100.0,
                        "mean_reward": 0.975,
                        "std_reward": 0.012,
                        "inert_cases": 0,
                        "safety_gate_cases": 0,
                        "per_family": {},
                    },
                },
                "case_results": [{"eval_id": f"G5-{i:02d}"} for i in range(20)],
            }),
            encoding="utf-8",
        )

    (out_dir / f"{camp.PRIMARY_FLAVOR}_threat_hunt_report.json").write_text(
        json.dumps({
            "status": "COMPLETED",
            "scenario_count": 4,
            "arms": ["compressed_track_b_hunt", "harness2_evolved_hunt"],
            "arm_aggregates": [
                {
                    "model": camp.PRIMARY_MODEL_ID,
                    "arm": "compressed_track_b_hunt",
                    "mean_hunt_composite": 0.95,
                    "mean_harbor_reward": 0.94,
                    "verdict_accuracy": 1.0,
                    "widening_168h_rate": 1.0,
                    "patient_zero_discovery_rate": 1.0,
                    "lolbin_safe_rate": 1.0,
                    "mean_epistemic_steps": 5.5,
                    "mean_latency_s": 12.0,
                },
                {
                    "model": camp.PRIMARY_MODEL_ID,
                    "arm": "harness2_evolved_hunt",
                    "mean_hunt_composite": 0.98,
                    "mean_harbor_reward": 0.96,
                    "verdict_accuracy": 1.0,
                    "widening_168h_rate": 1.0,
                    "patient_zero_discovery_rate": 1.0,
                    "lolbin_safe_rate": 1.0,
                    "mean_epistemic_steps": 6.0,
                    "mean_latency_s": 13.0,
                },
            ],
            "overall_by_arm": [],
            "runs": [{"eval_id": f"H-{i}"} for i in range(8)],
        }),
        encoding="utf-8",
    )

    def _ok_probe(
        url: str,
        headers: Dict[str, str],
        payload: Dict[str, Any],
        max_retries: int = 1,
    ) -> Tuple[float, Optional[Dict[str, Any]], Optional[str], int]:
        return (
            0.2,
            {
                "choices": [{"message": {"role": "assistant", "content": "READY"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
            },
            None,
            200,
        )

    def _forbid_benchmark(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("BenchmarkRunner should not be called when --resume-existing hits cache")

    temp_exposure = tmp_path / "exposure.jsonl"

    master1 = camp.run_campaign(
        max_usd=10.0,
        temperature=0.0,
        jev_backend="mock",
        resume_existing=True,
        output_dir=out_dir,
        project_id="unit-proj-123",
        soc_comparative_doc=soc_doc,
        llama_comparative_doc=llama_doc,
        auth_fn=lambda _: ("mock-token", "unit-proj-123"),
        probe_request_fn=_ok_probe,
        gpu_audit_http_fn=_mock_zero_gpu_http,
        benchmark_runner_factory=_forbid_benchmark,
        exposure_ledger_path=temp_exposure,
    )
    # Run a second time to verify comparative doc marker replacement is idempotent
    master2 = camp.run_campaign(
        max_usd=10.0,
        temperature=0.0,
        jev_backend="mock",
        resume_existing=True,
        output_dir=out_dir,
        project_id="unit-proj-123",
        soc_comparative_doc=soc_doc,
        llama_comparative_doc=llama_doc,
        auth_fn=lambda _: ("mock-token", "unit-proj-123"),
        probe_request_fn=_ok_probe,
        gpu_audit_http_fn=_mock_zero_gpu_http,
        benchmark_runner_factory=_forbid_benchmark,
        exposure_ledger_path=temp_exposure,
    )

    assert master1["status"] == "COMPLETED"
    assert master2["status"] == "COMPLETED"
    assert not temp_exposure.exists()
    assert soc_doc.read_text(encoding="utf-8").count(camp._SOC_DOC_SECTION_START) == 1
    assert llama_doc.read_text(encoding="utf-8").count(camp._SOC_DOC_SECTION_START) == 1
    assert "unit-proj-123" not in (out_dir / "DEEPSEEK_V4_1_FLASH_EVALUATION_REPORT.md").read_text(encoding="utf-8")


def test_clean_skills_runbooks_mapping_and_katex_escaping() -> None:
    mapped, words = camp.load_clean_skills_runbooks_dict()
    assert words > 100
    assert set(mapped.keys()) == set(camp.CORE_TRIAGE_RUNBOOKS)
    for content in mapped.values():
        assert "get_ip_address_report" in content
        assert "get_ip_report" not in content

    md = "Cost is $0.00/hr and loss is $50,000 while sensitivity is $d'$ and `code $10` stays raw."
    escaped = camp.escape_katex_currency_dollars(md)
    assert "\\$0.00/hr" in escaped
    assert "\\$50,000" in escaped
    assert "$d'$" in escaped
    assert "`code $10`" in escaped
