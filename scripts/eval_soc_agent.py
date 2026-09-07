#!/usr/bin/env python3
"""Automated SOC Tier 1 Evaluation Runner with LLM-as-a-Judge, SDT, and Decision Loss Scoring."""

import argparse
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault("GOOGLE_API_USE_CLIENT_CERTIFICATE", "false")

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from agent.soc_environment import SocEnvironment
from agent.soc_tier1_agent import SocDecision, SocTier1Agent, extract_soc_decision
try:
    from agent.hierarchical_soc_agent import HierarchicalSOCTier1Agent
except ModuleNotFoundError:
    from hierarchical_soc_agent import HierarchicalSOCTier1Agent
from scripts.eval_cost_engine import (
    AssetCriticality,
    DecisionOutcome,
    OperationalLossScorecard,
    SignalDetectionMetrics,
    calculate_counterfactual_consistency,
    calculate_expected_loss_matrix,
    calculate_operational_loss,
    calculate_sdt_metrics,
    classify_decision_outcome,
    normalize_criticality,
    normalize_decision_outcome,
)
from scripts.eval_trajectory_verifier import (
    TrajectoryVerificationResult,
    calculate_epistemic_efficiency,
    is_epistemic_tool,
    verify_agent_trajectory,
)
from scripts.evaluation_provenance import capture_provenance, utc_now


class SemanticJudgeResult(BaseModel):
    """Structured evaluation output from the LLM-as-a-judge."""

    rubric_score: float = Field(description="Score from 0 to 100 based on the rubric criteria.")
    passed: bool = Field(description="True if score >= passing threshold (usually 80 or 85).")
    grounding_score: float = Field(description="Score from 0 to 1.0 assessing factual veracity and lack of hallucinations.")
    critique: str = Field(description="Detailed explanation of strengths, omissions, and operational errors.")


def evaluate_assertions(
    response_text: str,
    must_contain: Optional[List[str]] = None,
    must_not_contain: Optional[List[str]] = None,
) -> Tuple[bool, List[str]]:
    """Evaluates deterministic substring rules case-insensitively.

    Args:
        response_text: Raw output text from the agent response.
        must_contain: Substrings that must be present (case-insensitive).
        must_not_contain: Prohibited substrings that must not appear (case-insensitive).

    Returns:
        Tuple of (passed: bool, failures: List[str]).
    """
    failures: List[str] = []
    text_lower = (response_text or "").lower()
    for item in (must_contain or []):
        if item.lower() not in text_lower:
            failures.append(f"Missing required substring: '{item}'")
    for item in (must_not_contain or []):
        if item.lower() in text_lower:
            failures.append(f"Contained prohibited substring: '{item}'")
    return len(failures) == 0, failures


def calculate_aggregate_score(results: List[Dict[str, Any]], gen: int = 3) -> Dict[str, Any]:
    """Computes summary statistics, token usage, throughput, SDT metrics, and operational losses.

    Args:
        results: List of case evaluation result dictionaries.
        gen: Evaluation generation version (1, 2, or 3).

    Returns:
        Summary statistics dictionary.
    """
    total = len(results)
    if total == 0:
        base_summary = {
            "total_cases": 0,
            "passed_cases": 0,
            "pass_rate": 0.0,
            "avg_rubric_score": 0.0,
            "avg_latency_s": 0.0,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_tokens": 0,
            "avg_tokens_per_case": 0.0,
            "avg_generation_tps": 0.0,
            "avg_total_tps": 0.0,
            "total_tool_calls": 0,
        }
        if gen == 3:
            base_summary.update({
                "sdt_metrics": calculate_sdt_metrics(0, 0, 0, 0).to_dict(),
                "operational_loss": calculate_expected_loss_matrix([]).to_dict(),
                "avg_epistemic_efficiency": 0.0,
                "actions_matched_rate": 0.0,
                "operator_actions_matched_rate": 0.0,
                "advisor_actions_matched_rate": 0.0,
                "prohibited_avoided_rate": 0.0,
            })
        return base_summary

    avg_score = sum(r.get("rubric_score", 0.0) for r in results) / total
    passed_count = sum(1 for r in results if r.get("passed", False))
    total_latency = sum(r.get("latency_s", 0.0) for r in results)
    avg_latency = total_latency / total
    total_prompt_tok = sum(r.get("usage", {}).get("prompt_tokens", 0) for r in results)
    total_comp_tok = sum(r.get("usage", {}).get("completion_tokens", 0) for r in results)
    total_tok = sum(r.get("usage", {}).get("total_tokens", 0) for r in results)
    total_tools = sum(len(r.get("trajectory", [])) for r in results)

    avg_gen_tps = round(total_comp_tok / total_latency, 2) if total_latency > 0 else 0.0
    avg_tot_tps = round(total_tok / total_latency, 2) if total_latency > 0 else 0.0

    summary: Dict[str, Any] = {
        "total_cases": total,
        "passed_cases": passed_count,
        "pass_rate": round((passed_count / total) * 100.0, 1),
        "avg_rubric_score": round(avg_score, 1),
        "avg_latency_s": round(avg_latency, 2),
        "total_prompt_tokens": total_prompt_tok,
        "total_completion_tokens": total_comp_tok,
        "total_tokens": total_tok,
        "avg_tokens_per_case": round(total_tok / total, 1) if total else 0.0,
        "avg_generation_tps": avg_gen_tps,
        "avg_total_tps": avg_tot_tps,
        "total_tool_calls": total_tools,
    }

    # If Gen 3 or if any case contains SDT/trajectory verification metrics
    has_gen3_metrics = gen == 3 or any("decision_outcome" in r or "trajectory_verification" in r for r in results)
    if has_gen3_metrics:
        hits = sum(1 for r in results if r.get("decision_outcome") == DecisionOutcome.TRUE_POSITIVE.value)
        misses = sum(1 for r in results if r.get("decision_outcome") == DecisionOutcome.FALSE_NEGATIVE.value)
        false_alarms = sum(1 for r in results if r.get("decision_outcome") == DecisionOutcome.FALSE_POSITIVE.value)
        correct_rejections = sum(1 for r in results if r.get("decision_outcome") == DecisionOutcome.TRUE_NEGATIVE.value)

        sdt = calculate_sdt_metrics(
            hits=hits,
            misses=misses,
            false_alarms=false_alarms,
            correct_rejections=correct_rejections,
        )

        loss_cases: List[Dict[str, Any]] = []
        for r in results:
            loss_cases.append({
                "case_id": r.get("eval_id"),
                "outcome": r.get("decision_outcome", "TRUE_POSITIVE" if r.get("passed") else "FALSE_NEGATIVE"),
                "criticality": r.get("asset_criticality", "STANDARD"),
                "usage": r.get("usage", {}),
                "trajectory": r.get("trajectory", []),
            })

        loss_scorecard = calculate_expected_loss_matrix(loss_cases)

        epistemic_effs = [r.get("epistemic_efficiency", 1.0) for r in results if "epistemic_efficiency" in r]
        avg_epistemic_eff = sum(epistemic_effs) / len(epistemic_effs) if epistemic_effs else 1.0

        matched_actions = sum(
            1 for r in results
            if r.get("trajectory_verification", {}).get("actions_matched", True)
        )
        matched_operator = sum(
            1 for r in results
            if r.get("trajectory_verification", {}).get("operator_actions_matched", True)
        )
        matched_advisor = sum(
            1 for r in results
            if r.get("trajectory_verification", {}).get("advisor_actions_matched", True)
        )
        avoided_prohibited = sum(
            1 for r in results
            if r.get("trajectory_verification", {}).get("prohibited_actions_avoided", True)
        )

        cf_metrics = calculate_counterfactual_consistency(results)
        summary["sdt_metrics"] = sdt.to_dict()
        summary["operational_loss"] = loss_scorecard.to_dict()
        summary["counterfactual_consistency"] = cf_metrics
        summary["avg_epistemic_efficiency"] = round(avg_epistemic_eff, 3)
        summary["actions_matched_rate"] = round((matched_actions / total) * 100.0, 1)
        summary["operator_actions_matched_rate"] = round((matched_operator / total) * 100.0, 1)
        summary["advisor_actions_matched_rate"] = round((matched_advisor / total) * 100.0, 1)
        summary["prohibited_avoided_rate"] = round((avoided_prohibited / total) * 100.0, 1)

    return summary


def judge_response_with_llm(
    judge_client: genai.Client,
    prompt: str,
    response: str,
    rubric: str,
    reference: Dict[str, Any],
    trajectory: Optional[List[Dict[str, Any]]] = None,
) -> SemanticJudgeResult:
    """Uses Gemini 2.5 Pro as a strict LLM-as-a-judge auto-rater."""
    if trajectory and len(trajectory) > 0:
        traj_lines = []
        for step in trajectory:
            t_num = step.get("iteration", step.get("step", "?"))
            t_name = step.get("tool", "unknown")
            t_in = json.dumps(step.get("args", step.get("input", {})))
            t_obs = str(step.get("observation", ""))[:500]
            traj_lines.append(f"Step {t_num}: Tool '{t_name}' invoked with {t_in} -> Observation: {t_obs}")
        traj_str = "\n".join(traj_lines)
    else:
        traj_str = "NO TOOLS WERE INVOKED DURING THIS INVESTIGATION (0 tool calls executed)."

    judge_prompt = f"""
You are an expert Security Operations Center (SOC) Quality Assurance Judge.
Evaluate the following Tier 1 SOC Analyst agent response against the operational rubric and the ACTUAL tool execution trajectory.

### User Query / Incident Alert:
{prompt}

### Tool Execution Trajectory (Actual Invocations & Real Observations):
{traj_str}

### Agent Response:
{response}

### Reference Ground Truth:
{json.dumps(reference, indent=2)}

### Operational Grading Rubric:
{rubric}

### Instructions:
1. Objectively evaluate if the response followed triage procedures.
2. Grounding Verification: Cross-reference all claims in the Agent Response against the Tool Execution Trajectory. If the agent claims to have checked threat intelligence, IP routing, process trees, or certificates, but no corresponding tool invocation exists in the trajectory, heavily penalize the grounding_score (< 0.70) and rubric_score.
3. Execution vs Recommendation: If the rubric requires executing containment (e.g. isolate_host, block_indicator), verify whether that tool was actually executed in the trajectory. A text recommendation without actual tool execution must not receive full execution points.
4. Score from 0 to 100 based strictly on verified operational performance.
"""
    res = judge_client.models.generate_content(
        model="gemini-2.5-pro",
        contents=judge_prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=SemanticJudgeResult,
            temperature=0.0,
        ),
    )
    return SemanticJudgeResult.model_validate_json(res.text)


def run_evaluation(
    evalset_path: Path,
    flavor: str,
    endpoint_id: Optional[str] = None,
    cloudrun_url: Optional[str] = None,
    managed_model: Optional[str] = None,
    project_id: str = "dandye-0324-chronicle",
    region: str = "us-central1",
    use_live_mcp: bool = False,
    chronicle_project: Optional[str] = None,
    chronicle_customer_id: Optional[str] = None,
    chronicle_region: Optional[str] = None,
    gen: int = 3,
    agent_mode: str = "single",
    use_runbooks: bool = True,
    runbooks_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Runs the full evaluation suite against the target Gemma model backend."""
    chron_proj = chronicle_project or os.environ.get("CHRONICLE_PROJECT_ID", "secops-demo-env")
    chron_cust = chronicle_customer_id or os.environ.get("CHRONICLE_CUSTOMER_ID", "a13f6726-efed-452e-9008-8fe0d3cb0f75")
    chron_reg = chronicle_region or os.environ.get("CHRONICLE_REGION", "us")

    if use_live_mcp:
        os.environ["CHRONICLE_PROJECT_ID"] = chron_proj
        os.environ["CHRONICLE_CUSTOMER_ID"] = chron_cust
        os.environ["CHRONICLE_REGION"] = chron_reg

    with open(evalset_path, "r", encoding="utf-8") as f:
        evalset = json.load(f)

    eval_gen = int(evalset.get("generation", gen))

    print("==================================================================")
    print(f" Running Gemma SOC Tier 1 Evaluation: {flavor} (Gen {eval_gen})")
    print(f" Agent Mode: {agent_mode.capitalize()} ({'Supervisor-Worker' if agent_mode == 'hierarchical' else 'Single ReAct'})")
    if agent_mode == "hierarchical":
        print(f" Procedural Runbooks: {'Enabled' if use_runbooks else 'Disabled (Generic Control)'}")
    print(f" Live SecOps MCP: {'Enabled' if use_live_mcp else 'Disabled (Local Grounding Dataset)'}")
    if use_live_mcp:
        print(f" Chronicle Tenant: {chron_proj} ({chron_cust}) [Region: {chron_reg}]")
    print("==================================================================")

    # Check model catalog for MaaS metadata
    catalog_path = ROOT_DIR / "configs" / "models.json"
    if catalog_path.exists() and not managed_model and not endpoint_id and not cloudrun_url:
        try:
            with open(catalog_path, "r", encoding="utf-8") as f:
                cat = json.load(f)
                if flavor in cat and cat[flavor].get("type") == "maas":
                    managed_model = cat[flavor].get("modelId") or flavor
                    if "region" in cat[flavor]:
                        region = cat[flavor]["region"]
        except Exception:
            pass

    if not managed_model and not endpoint_id and not cloudrun_url and "llama" in flavor.lower():
        managed_model = flavor
        if region == "us-central1":
            region = "us-east5"

    provenance = capture_provenance(
        ROOT_DIR, evalset_path,
        {"flavor": flavor, "managed_model": managed_model, "endpoint_id": endpoint_id,
         "cloudrun_url": cloudrun_url, "project_id": project_id, "region": region,
         "generation": eval_gen, "agent_mode": agent_mode, "use_runbooks": use_runbooks,
         "use_live_mcp": use_live_mcp},
        (Path(runbooks_dir) if runbooks_dir else ROOT_DIR / "third_party" / "ai-runbooks" / ".clinerules" / "run_books")
        if agent_mode == "hierarchical" and use_runbooks else None,
    )

    soc_env: Optional[SocEnvironment] = None
    if not use_live_mcp and eval_gen == 3:
        soc_env = SocEnvironment()

    if agent_mode == "hierarchical":
        agent = HierarchicalSOCTier1Agent(
            project_id=project_id,
            region=region,
            endpoint_id=endpoint_id,
            cloudrun_url=cloudrun_url,
            managed_model=managed_model,
            use_live_mcp=use_live_mcp,
            environment=soc_env,
            use_runbooks=use_runbooks,
            runbooks_dir=Path(runbooks_dir) if runbooks_dir else None,
        )
    else:
        agent = SocTier1Agent(
            project_id=project_id,
            region=region,
            endpoint_id=endpoint_id,
            cloudrun_url=cloudrun_url,
            managed_model=managed_model,
            use_live_mcp=use_live_mcp,
            environment=soc_env,
        )
    agent.set_up()

    # Judge client uses us-central1 / global for Gemini 2.5 Pro availability
    judge_region = "us-central1"
    judge_client = genai.Client(vertexai=True, project=project_id, location=judge_region)

    results: List[Dict[str, Any]] = []
    for case in evalset.get("eval_cases", []):
        print(f"\n[Case: {case['eval_id']}] {case['name']}...")

        # Setup per-case dynamic environment state and fault injection if in Gen 3
        if not use_live_mcp and eval_gen == 3:
            case_env = SocEnvironment()
            fault_cfg = case.get("fault_injection")
            if fault_cfg and isinstance(fault_cfg, dict):
                case_env.inject_fault(
                    tool_name=fault_cfg.get("tool", ""),
                    status_code=fault_cfg.get("status_code", 503),
                    error=fault_cfg.get("error", "Service Unavailable"),
                )
            agent.environment = case_env

        start_time = time.time()
        res = agent.query(prompt=case["prompt"])
        latency = time.time() - start_time
        response_text = res.get("response", "")
        trajectory = res.get("trajectory", [])
        usage = res.get("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})

        comp_tok = usage.get("completion_tokens", 0)
        tot_tok = usage.get("total_tokens", 0)
        gen_tps = round(comp_tok / latency, 2) if latency > 0 else 0.0
        tot_tps = round(tot_tok / latency, 2) if latency > 0 else 0.0

        # Deterministic Assertions
        assertions = case.get("assertions", {})
        assert_passed, failures = evaluate_assertions(
            response_text=response_text,
            must_contain=assertions.get("must_contain", []),
            must_not_contain=assertions.get("must_not_contain", []),
        )

        # Trajectory & Action Verification
        expected_actions = case.get("expected_actions")
        prohibited_actions = case.get("prohibited_actions")
        expected_entities = case.get("expected_entities")
        traj_verif = verify_agent_trajectory(
            trajectory=trajectory,
            expected_actions=expected_actions,
            prohibited_actions=prohibited_actions,
            expected_entities=expected_entities,
            response_text=response_text,
        )
        epistemic_eff = calculate_epistemic_efficiency(trajectory)
        soc_dec = extract_soc_decision(response_text)

        # Signal Detection Theory (SDT) & Operational Loss Decision Outcome
        asset_crit = case.get("asset_criticality", "STANDARD")
        gt_label = str(case.get("ground_truth_label", "")).upper()
        if gt_label:
            is_threat = gt_label in ["MALICIOUS", "SUSPICIOUS", "CRITICAL_MALICIOUS"]
        else:
            # Fallback heuristic if ground_truth_label omitted
            must_contain_str = " ".join(assertions.get("must_contain", [])).lower()
            is_threat = "isolate" in must_contain_str or "malicious" in must_contain_str

        decision_outcome = classify_decision_outcome(
            ground_truth_threat=is_threat,
            verdict_str=(soc_dec.verdict if soc_dec else None),
            executed_actions=traj_verif.executed_actions,
            recommended_actions=traj_verif.recommended_actions,
            response_text=response_text,
        )
        case_loss = calculate_operational_loss(
            outcome=decision_outcome,
            criticality=asset_crit,
        )

        # Semantic Judge
        judge_res = judge_response_with_llm(
            judge_client=judge_client,
            prompt=case["prompt"],
            response=response_text,
            rubric=case["reference"]["grading_rubric"],
            reference=case["reference"],
            trajectory=trajectory,
        )

        # Case pass evaluation
        if eval_gen == 3:
            correct_detection = (
                (is_threat and decision_outcome == DecisionOutcome.TRUE_POSITIVE)
                or (not is_threat and decision_outcome == DecisionOutcome.TRUE_NEGATIVE)
            )
            # Epistemic investigation enforcement:
            # If the case requires investigation (threat or enrichment where expected_entities
            # or ground_truth_label != "BENIGN" or expected_actions contains tools),
            # require that the agent performed epistemic investigation.
            requires_investigation = bool(
                expected_entities
                or (gt_label and gt_label != "BENIGN")
                or is_threat
                or (expected_actions and any(is_epistemic_tool(act) for act in expected_actions))
            )
            investigation_passed = (not requires_investigation) or (
                traj_verif.epistemic_step_count >= 1
            )
            case_passed = (
                assert_passed
                and judge_res.rubric_score >= 70.0
                and judge_res.grounding_score >= 0.70
                and traj_verif.actions_matched
                and traj_verif.prohibited_actions_avoided
                and correct_detection
                and investigation_passed
            )
        else:
            case_passed = assert_passed and judge_res.passed

        status_label = "PASS" if case_passed else "FAIL"
        print(
            f"  Result: {status_label} | Rubric: {judge_res.rubric_score}/100 | "
            f"Outcome: {decision_outcome.value} | Loss: ${case_loss:,.0f} | "
            f"Latency: {latency:.2f}s | Gen TPS: {gen_tps} tok/s | "
            f"Tokens: {tot_tok} | Tool Calls: {len(trajectory)} | "
            f"Epistemic Eff: {epistemic_eff:.2f}"
        )
        if failures:
            print(f"  Assertion Failures: {failures}")
        if not traj_verif.actions_matched:
            print(f"  Action Verification Notes: {traj_verif.notes}")
        if eval_gen == 3 and not investigation_passed:
            print("  Epistemic Investigation Failure: Case required investigation but agent executed 0 tools.")

        case_data: Dict[str, Any] = {
            "eval_id": case["eval_id"],
            "name": case["name"],
            "prompt": case["prompt"],
            "latency_s": latency,
            "usage": usage,
            "generation_tps": gen_tps,
            "total_tps": tot_tps,
            "trajectory": trajectory,
            "assert_passed": assert_passed,
            "assertion_failures": failures,
            "rubric_score": judge_res.rubric_score,
            "grounding_score": judge_res.grounding_score,
            "passed": case_passed,
            "critique": judge_res.critique,
            "response": response_text,
            "asset_criticality": asset_crit,
            "ground_truth_label": gt_label,
            "decision_outcome": decision_outcome.value,
            "trajectory_verification": traj_verif.to_dict(),
            "soc_decision": soc_dec.to_dict() if soc_dec else None,
            "epistemic_efficiency": epistemic_eff,
            "expected_actions": case.get("expected_actions", []),
            "prohibited_actions": case.get("prohibited_actions", []),
            "counterfactual_pair_id": case.get("counterfactual_pair_id"),
            "case_loss_usd": case_loss,
        }
        results.append(case_data)

    summary = calculate_aggregate_score(results, gen=eval_gen)

    print("\n==================================================================")
    print(f" Evaluation Summary for {flavor} (Gen {eval_gen})")
    print(f" Pass Rate:         {summary['pass_rate']:.1f}% ({summary['passed_cases']}/{summary['total_cases']})")
    print(f" Average Score:     {summary['avg_rubric_score']}/100")
    print(f" Avg Latency:       {summary['avg_latency_s']} s")
    print(f" Output TPS:        {summary['avg_generation_tps']} tok/s (Total TPS: {summary['avg_total_tps']} tok/s)")
    print(f" Total Tokens:      {summary['total_tokens']} (Avg: {summary['avg_tokens_per_case']} / case)")
    print(f" Total Tool Calls:  {summary['total_tool_calls']}")

    if "sdt_metrics" in summary and "operational_loss" in summary:
        sdt = summary["sdt_metrics"]
        loss = summary["operational_loss"]
        print("------------------------------------------------------------------")
        print(" Signal Detection Theory (SDT) & Operational Loss:")
        print(f" Sensitivity (d'):   {sdt['d_prime']:.2f}")
        print(f" Criterion Bias (c): {sdt['criterion_c']:.2f}")
        print(f" Hit Rate:           {sdt['hit_rate']*100:.1f}% (Hits: {sdt['hits']}, Misses: {sdt['misses']})")
        print(f" False Alarm Rate:   {sdt['false_alarm_rate']*100:.1f}% (FA: {sdt['false_alarms']}, CR: {sdt['correct_rejections']})")
        print(f" Total Expected Loss: ${loss['total_loss_usd']:,.2f}")
        print(f"   - False Positives (Downtime):   ${loss['fp_loss_usd']:,.2f}")
        print(f"   - False Negatives (Adversary):  ${loss['fn_loss_usd']:,.2f}")
        op_rate = summary.get("operator_actions_matched_rate", summary.get("actions_matched_rate", 100.0))
        adv_rate = summary.get("advisor_actions_matched_rate", summary.get("actions_matched_rate", 100.0))
        print(f" Epistemic Efficiency: {summary.get('avg_epistemic_efficiency', 1.0):.2f} (Action Match: {summary.get('actions_matched_rate', 100.0)}% | Operator: {op_rate}% | Advisor: {adv_rate}%)")
        if "counterfactual_consistency" in summary and summary["counterfactual_consistency"].get("evaluated_pairs", 0) > 0:
            cf = summary["counterfactual_consistency"]
            print(f" Counterfactual Consistency: {cf['counterfactual_consistency_score']*100:.1f}% ({cf['consistent_pairs']}/{cf['evaluated_pairs']} pairs consistent)")

    print("------------------------------------------------------------------")
    print(f" {'Case ID':<38} | {'Status':<6} | {'Outcome':<14} | {'Rubric':<8} | {'Latency':<7} | {'Loss ($)':<10}")
    print("------------------------------------------------------------------")
    for r in results:
        status_str = "PASS" if r["passed"] else "FAIL"
        outcome_str = r.get("decision_outcome", "N/A")
        loss_val = r.get("case_loss_usd", 0.0)
        print(
            f" {r['eval_id']:<38} | {status_str:<6} | {outcome_str:<14} | "
            f"{r['rubric_score']:>5.1f}/100 | {r['latency_s']:>6.2f}s | ${loss_val:>9,.0f}"
        )
    print("==================================================================")

    provenance["completed_at"] = utc_now()
    provenance["lifecycle"].update({"status": "completed", "evaluation": "completed"})
    return {
        "provenance": provenance,
        "flavor": flavor,
        "generation": eval_gen,
        "agent_mode": agent_mode,
        "use_runbooks": use_runbooks,
        "summary": summary,
        "case_results": results,
    }


def format_markdown_report(eval_data: Dict[str, Any], live_mcp: bool = False) -> str:
    """Renders evaluation report in structured GitHub markdown format."""
    summary = eval_data["summary"]
    flavor = eval_data.get("flavor", "Unknown Model")
    eval_gen = eval_data.get("generation", 3)
    agent_mode = eval_data.get("agent_mode", "single")
    use_runbooks = eval_data.get("use_runbooks", True)

    lines = [
        f"# SOC Evaluation Report: {flavor}",
        f"\n**Date:** {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
        f"**Evaluation Generation:** Gen {eval_gen}",
        f"**Agent Architecture:** {agent_mode.capitalize()} ({'Supervisor-Worker' if agent_mode == 'hierarchical' else 'Single ReAct'})",
        f"**Procedural Runbooks:** {'Enabled' if use_runbooks else 'Disabled (Generic Investigation Control)'}",
        f"**Live SecOps MCP:** {'Enabled' if live_mcp else 'Disabled'}",
        "\n## 1. Executive Summary",
        f"- **Pass Rate:** {summary['pass_rate']}% ({summary['passed_cases']}/{summary['total_cases']})",
        f"- **Average Rubric Score:** {summary['avg_rubric_score']} / 100",
        f"- **Average Latency:** {summary['avg_latency_s']} s",
        f"- **Output Throughput (Generation TPS):** {summary.get('avg_generation_tps', 0.0)} tok/s",
        f"- **Total Processing Throughput:** {summary.get('avg_total_tps', 0.0)} tok/s",
        f"- **Total Token Usage:** {summary['total_tokens']} tokens (Avg: {summary['avg_tokens_per_case']} tok/case)",
        f"- **Total Tool Invocations:** {summary['total_tool_calls']}",
    ]

    if "sdt_metrics" in summary and "operational_loss" in summary:
        sdt = summary["sdt_metrics"]
        loss = summary["operational_loss"]
        lines.extend([
            f"- **Signal Detection Sensitivity (d'):** {sdt['d_prime']:.2f}",
            f"- **Decision Criterion Bias (c):** {sdt['criterion_c']:.2f}",
            f"- **Hit Rate:** {sdt['hit_rate']*100:.1f}% | **False Alarm Rate:** {sdt['false_alarm_rate']*100:.1f}%",
            f"- **Total Operational Financial Loss:** ${loss['total_loss_usd']:,.2f}",
            f"- **False Positive Blast-Radius Loss:** ${loss['fp_loss_usd']:,.2f}",
            f"- **False Negative Breach Loss:** ${loss['fn_loss_usd']:,.2f}",
            f"- **Investigation Compute Cost:** ${loss['investigation_cost_usd']:,.4f}",
            f"- **Epistemic Step Efficiency:** {summary.get('avg_epistemic_efficiency', 1.0):.2f}",
            f"- **Pragmatic Action Compliance Rate:** {summary.get('actions_matched_rate', 100.0)}%",
            f"- **Operator Action Compliance Rate:** {summary.get('operator_actions_matched_rate', summary.get('actions_matched_rate', 100.0))}%",
            f"- **Advisor Action Compliance Rate:** {summary.get('advisor_actions_matched_rate', summary.get('actions_matched_rate', 100.0))}%",
        ])

    lines.extend([
        "\n## 2. Evaluation Scorecard Matrix\n",
        "| Case ID | Case Name | Criticality | Outcome | Rubric Score | Grounding | Actions Matched | Epistemic Eff | Status | Latency | Gen TPS | Total Tokens | Tool Steps | Loss ($) |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ])

    for c in eval_data.get("case_results", []):
        status_str = "PASS" if c["passed"] else "FAIL"
        tok = c.get("usage", {}).get("total_tokens", 0)
        gen_tps = c.get("generation_tps", 0.0)
        tools_cnt = len(c.get("trajectory", []))
        crit_tier = c.get("asset_criticality", "STANDARD")
        outcome_str = c.get("decision_outcome", "N/A")
        act_matched = "YES" if c.get("trajectory_verification", {}).get("actions_matched", True) else "NO"
        ep_eff = c.get("epistemic_efficiency", 1.0)
        loss_usd = c.get("case_loss_usd", 0.0)
        lines.append(
            f"| {c['eval_id']} | {c['name']} | {crit_tier} | {outcome_str} | {c['rubric_score']}/100 | "
            f"{c['grounding_score']:.2f} | {act_matched} | {ep_eff:.2f} | {status_str} | {c['latency_s']:.2f}s | "
            f"{gen_tps} tok/s | {tok} | {tools_cnt} | ${loss_usd:,.0f} |"
        )

    if "sdt_metrics" in summary and "operational_loss" in summary:
        sdt = summary["sdt_metrics"]
        loss = summary["operational_loss"]
        lines.extend([
            "\n---\n\n## 3. Signal Detection & Operational Risk Analysis\n",
            "### Signal Detection Theory (SDT) Matrix",
            "| Metric | Value | Description |",
            "| :--- | :--- | :--- |",
            f"| Sensitivity Index ($d'$) | {sdt['d_prime']:.2f} | Discrimination ability between true threats and benign activity |",
            f"| Decision Criterion ($c$) | {sdt['criterion_c']:.2f} | Response bias (<0 aggressive/liberal, >0 conservative) |",
            f"| True Positives (Hits) | {sdt['hits']} | Real threats correctly detected and contained |",
            f"| False Negatives (Misses) | {sdt['misses']} | Real threats missed / uncontained |",
            f"| False Positives (False Alarms) | {sdt['false_alarms']} | Benign activity incorrectly flagged for disruption |",
            f"| True Negatives (Correct Rejections) | {sdt['correct_rejections']} | Benign activity correctly cleared without disruption |",
            f"| Empirical Hit Rate | {sdt['hit_rate']*100:.1f}% | Ratio of threats successfully identified |",
            f"| Empirical False Alarm Rate | {sdt['false_alarm_rate']*100:.1f}% | Ratio of benign alerts erroneously escalated |",
            "\n### Operational Financial Loss Matrix",
            "| Loss Dimension | Financial Amount (USD) | Operational Impact Description |",
            "| :--- | :--- | :--- |",
            f"| False Positive Loss | ${loss['fp_loss_usd']:,.2f} | Operational downtime, business disruption, unnecessary incident response |",
            f"| False Negative Loss | ${loss['fn_loss_usd']:,.2f} | Uncontained adversary breach, lateral movement, ransomware / exfiltration |",
            f"| Investigation Compute Cost | ${loss['investigation_cost_usd']:,.4f} | LLM inference token consumption and API tool execution costs |",
            f"| **Total Operational Loss** | **${loss['total_loss_usd']:,.2f}** | **Net operational financial risk & investigation cost** |",
        ])

    if "counterfactual_consistency" in summary:
        cf = summary["counterfactual_consistency"]
        if cf.get("evaluated_pairs", 0) > 0:
            lines.extend([
                "\n### Counterfactual Consistency Analysis",
                f"- **Counterfactual Consistency Score:** {cf['counterfactual_consistency_score']*100:.1f}% ({cf['consistent_pairs']}/{cf['evaluated_pairs']} pairs consistent)",
                f"- **Evaluated Pairs:** {cf['evaluated_pairs']} | **Inconsistent Pairs:** {cf['inconsistent_pairs']}",
                "\n| Pair ID | Scenario Pair | Status | Discrimination Analysis |",
                "| :--- | :--- | :--- | :--- |",
            ])
            for p in cf.get("pairs", []):
                pair_label = f"{p.get('threat_case_id')} vs {p.get('non_threat_case_id')}"
                status = "CONSISTENT" if p.get("consistent") else "INCONSISTENT"
                lines.append(f"| {p.get('pair_id')} | {pair_label} | {status} | {p.get('details') or p.get('reason') or 'N/A'} |")

    lines.append("\n---\n\n## 4. Detailed Case Trajectories & Reports\n")
    for c in eval_data.get("case_results", []):
        lines.append(f"### {c['eval_id']}: {c['name']}\n")
        lines.append(f"- **Status:** {'PASS' if c['passed'] else 'FAIL'}")
        lines.append(f"- **Score:** {c['rubric_score']}/100 | Grounding: {c['grounding_score']:.2f} | Latency: {c['latency_s']:.2f}s")
        lines.append(f"- **Decision Outcome:** `{c.get('decision_outcome', 'N/A')}` | Criticality: `{c.get('asset_criticality', 'STANDARD')}` | Case Loss: `${c.get('case_loss_usd', 0.0):,.2f}`")
        u = c.get("usage", {})
        lines.append(
            f"- **Token Usage & Speed:** {u.get('prompt_tokens', 0)} prompt + {u.get('completion_tokens', 0)} completion = "
            f"**{u.get('total_tokens', 0)} total tokens** | **{c.get('generation_tps', 0.0)} output tok/s**"
        )

        if c.get("assertion_failures"):
            lines.append(f"- **Assertion Failures:** `{c['assertion_failures']}`")
        lines.append(f"- **Judge Critique:** {c['critique']}\n")

        # Trajectory
        traj = c.get("trajectory", [])
        lines.append("#### Tool Execution Trajectory:")
        if traj:
            for step in traj:
                lines.append(f"**Step {step['iteration']} - `{step['tool']}`**")
                lines.append(f"- Arguments: `{json.dumps(step['args'])}`")
                lines.append("```json")
                lines.append(step['observation'])
                lines.append("```")
        else:
            lines.append("*(No tools invoked)*\n")

        traj_verif = c.get("trajectory_verification")
        if traj_verif:
            lines.append("\n#### Trajectory & Action Verification:")
            lines.append(f"- **Expected Actions Matched:** {'YES' if traj_verif.get('actions_matched') else 'NO'}")
            lines.append(f"- **Prohibited Actions Avoided:** {'YES' if traj_verif.get('prohibited_actions_avoided') else 'NO'}")
            lines.append(f"- **Epistemic Step Count:** {traj_verif.get('epistemic_step_count', 0)} | **Pragmatic Action Count:** {traj_verif.get('pragmatic_action_count', 0)}")
            lines.append(f"- **Redundant Queries:** {traj_verif.get('redundant_queries', 0)} | **Loop Detected:** {'YES' if traj_verif.get('loop_detected') else 'NO'}")
            lines.append(f"- **Degraded Resilience Score:** {traj_verif.get('degraded_resilience_score', 1.0)}")
            if traj_verif.get("notes"):
                lines.append("- **Verification Notes:**")
                for n in traj_verif["notes"]:
                    lines.append(f"  - {n}")

        lines.append("\n#### Generated Triage Report:")
        lines.append("```markdown")
        lines.append(c["response"])
        lines.append("```\n")
        lines.append("---\n")

    return "\n".join(lines) + "\n"


def format_failure_report(failure_data: Dict[str, Any]) -> str:
    """Render an explicit failed-run artifact without benchmark defaults."""
    provenance = failure_data.get("provenance", {})
    lifecycle = provenance.get("lifecycle", {})
    error = failure_data.get("error", {})
    error_message = error.get("message", "Unknown evaluation failure") if isinstance(error, dict) else str(error)
    error_type = error.get("type", "Exception") if isinstance(error, dict) else "Exception"
    lines = [
        f"# SOC Evaluation Failed: {failure_data.get('flavor', 'Unknown Model')}",
        "",
        "**Status:** FAILED",
        f"**Generation:** {failure_data.get('generation', 'Unknown')}",
        f"**Agent architecture:** {failure_data.get('agent_mode', 'Unknown')}",
        "",
        "No benchmark summary or case scores were produced because the evaluation raised an exception.",
        "",
        "## Failure",
        "",
        f"- **Exception type:** `{error_type}`",
        f"- **Message:** {error_message}",
        "",
        "## Lifecycle",
        "",
        f"- **Evaluation:** `{lifecycle.get('evaluation', 'failed')}`",
        f"- **Artifact collection:** `{lifecycle.get('artifact_collection', 'unverified')}`",
        f"- **Cleanup:** `{lifecycle.get('cleanup', 'unverified')}`",
        "",
        "This failure artifact records observed inputs and the exception. It contains no fabricated scores, cost, latency, or cleanup claim.",
        "",
    ]
    return "\n".join(lines)


def _initial_cli_provenance(
    evalset_file: Path,
    args: argparse.Namespace,
    eval_gen: int,
) -> Dict[str, Any]:
    """Capture inputs before execution so CLI failures remain attributable."""
    runbooks_path = (
        Path(args.runbooks_dir)
        if args.runbooks_dir
        else ROOT_DIR / "third_party" / "ai-runbooks" / ".clinerules" / "run_books"
    ) if args.agent_mode == "hierarchical" and args.use_runbooks else None
    return capture_provenance(
        ROOT_DIR,
        evalset_file,
        {
            "flavor": args.flavor,
            "managed_model": args.managed_model,
            "endpoint_id": args.endpoint,
            "cloudrun_url": args.cloudrun_url,
            "project_id": args.project_id,
            "region": args.region,
            "generation": eval_gen,
            "agent_mode": args.agent_mode,
            "use_runbooks": args.use_runbooks,
            "use_live_mcp": args.live_mcp,
        },
        runbooks_path,
    )


def _write_cli_failure_artifacts(
    failure_data: Dict[str, Any],
    json_path: Optional[Path],
    report_path: Optional[Path],
) -> None:
    """Best-effort persistence for a failed CLI invocation."""
    if json_path:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(failure_data, f, indent=2)
        print(f"Failure JSON saved to: {json_path}")
    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(format_failure_report(failure_data))
        print(f"Failure report saved to: {report_path}")


def main() -> None:
    """CLI entrypoint for running the SOC evaluation runner."""
    parser = argparse.ArgumentParser(description="Evaluate Gemma SOC Agent against Rubrics, SDT, and Loss Matrix.")
    parser.add_argument("--flavor", default="local-gemma", help="Model flavor name")
    parser.add_argument(
        "--gen",
        "--generation",
        dest="gen",
        type=int,
        choices=[1, 2, 3],
        default=3,
        help="Evaluation generation version: 1 for Gen 1 (5-case baseline), 2 for Gen 2 (10-case expanded), 3 for Gen 3 (10-case interactive with SDT and loss engine)",
    )
    parser.add_argument("--evalset", default=None, help="Path to evalset JSON (overrides default for --gen)")
    parser.add_argument("--live-mcp", "--use-live-mcp", dest="live_mcp", action="store_true", default=False, help="Use live Google SecOps Remote MCP tools")
    parser.add_argument("--chronicle-project", default=os.environ.get("CHRONICLE_PROJECT_ID", "secops-demo-env"), help="Google SecOps GCP Project ID")
    parser.add_argument("--chronicle-customer-id", default=os.environ.get("CHRONICLE_CUSTOMER_ID", "a13f6726-efed-452e-9008-8fe0d3cb0f75"), help="Chronicle Customer / Instance ID")
    parser.add_argument("--chronicle-region", default=os.environ.get("CHRONICLE_REGION", "us"), help="Chronicle Region (e.g. us, europe)")
    parser.add_argument("--endpoint", "--endpoint-id", dest="endpoint", default=None, help="Vertex AI Endpoint ID")
    parser.add_argument("--cloudrun-url", default=None, help="Cloud Run URL")
    parser.add_argument("--managed-model", default=None, help="Hosted MaaS model name")
    parser.add_argument("--project-id", default=os.environ.get("GCP_PROJECT_ID", "secops-demo-env"))
    parser.add_argument("--region", default=os.environ.get("GCP_REGION", "us-central1"))
    parser.add_argument(
        "--agent-mode",
        choices=["single", "hierarchical"],
        default="single",
        help="Agent architecture mode: single for standard SocTier1Agent, hierarchical for HierarchicalSOCTier1Agent (supervisor-worker)",
    )
    parser.add_argument(
        "--use-runbooks",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable procedural runbooks in hierarchical agent mode",
    )
    parser.add_argument(
        "--runbooks-dir",
        type=str,
        default=None,
        help="Directory containing custom or evolved runbook markdown files",
    )
    parser.add_argument("--output-report", default=None, help="Markdown report output path")
    parser.add_argument("--output-json", default=None, help="Raw JSON evaluation output path")
    args = parser.parse_args()

    # Determine default evalset based on generation and live MCP mode
    if args.evalset:
        evalset_file = Path(args.evalset)
    elif args.gen == 1:
        evalset_file = ROOT_DIR / "configs" / "evals" / "gen1" / "soc_tier1_triage.json"
        if not evalset_file.exists():
            evalset_file = ROOT_DIR / "configs" / "evals" / "soc_tier1_evalset.json"
    elif args.gen == 2:
        if args.live_mcp:
            evalset_file = ROOT_DIR / "configs" / "evals" / "gen2" / "soc_live_mcp.json"
            if not evalset_file.exists():
                evalset_file = ROOT_DIR / "configs" / "evals" / "soc_live_mcp_evalset.json"
        else:
            evalset_file = ROOT_DIR / "configs" / "evals" / "gen2" / "soc_tier1_triage.json"
            if not evalset_file.exists():
                evalset_file = ROOT_DIR / "configs" / "evals" / "soc_tier1_triage.json"
    else:
        # Gen 3 default
        if args.live_mcp:
            evalset_file = ROOT_DIR / "configs" / "evals" / "gen3" / "soc_live_mcp_interactive.json"
        else:
            evalset_file = ROOT_DIR / "configs" / "evals" / "gen3" / "soc_tier1_interactive.json"

    json_path = Path(args.output_json) if args.output_json else (
        Path(args.output_report).with_suffix(".json") if args.output_report else None
    )
    report_path = Path(args.output_report) if args.output_report else None
    initial_eval_gen = int(args.gen)
    try:
        with open(evalset_file, "r", encoding="utf-8") as f:
            initial_eval_gen = int(json.load(f).get("generation", initial_eval_gen))
    except (AttributeError, OSError, TypeError, ValueError, json.JSONDecodeError):
        # run_evaluation remains responsible for reporting malformed input.
        pass
    initial_provenance = _initial_cli_provenance(evalset_file, args, initial_eval_gen)

    try:
        eval_data = run_evaluation(
            evalset_path=evalset_file,
            flavor=args.flavor,
            endpoint_id=args.endpoint,
            cloudrun_url=args.cloudrun_url,
            managed_model=args.managed_model,
            project_id=args.project_id,
            region=args.region,
            use_live_mcp=args.live_mcp,
            chronicle_project=args.chronicle_project,
            chronicle_customer_id=args.chronicle_customer_id,
            chronicle_region=args.chronicle_region,
            gen=args.gen,
            agent_mode=args.agent_mode,
            use_runbooks=args.use_runbooks,
            runbooks_dir=args.runbooks_dir,
        )
    except Exception as error:
        initial_provenance["completed_at"] = utc_now()
        initial_provenance["lifecycle"].update({
            "status": "failed",
            "evaluation": "failed",
            "artifact_collection": "unverified",
            "cleanup": "unverified",
        })
        failure_data = {
            "status": "FAILED",
            "error": {"type": type(error).__name__, "message": str(error)},
            "provenance": initial_provenance,
            "flavor": args.flavor,
            "generation": initial_eval_gen,
            "agent_mode": args.agent_mode,
            "use_runbooks": args.use_runbooks,
        }
        try:
            _write_cli_failure_artifacts(failure_data, json_path, report_path)
        except Exception as artifact_error:
            print(f"Could not persist failure artifact: {artifact_error}", file=sys.stderr)
        print(f"Evaluation failed: {type(error).__name__}: {error}", file=sys.stderr)
        raise SystemExit(1) from error

    # Save JSON raw artifacts
    if json_path:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(eval_data, f, indent=2)
        print(f"Evaluation JSON saved to: {json_path}")

    # Save Markdown report
    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_text = format_markdown_report(eval_data, live_mcp=args.live_mcp)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_text)
        print(f"Report saved to: {report_path}")


if __name__ == "__main__":
    main()
