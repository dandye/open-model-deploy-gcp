#!/usr/bin/env python3
"""Automated SOC Tier 1 Evaluation Runner with LLM-as-a-Judge Rubric Scoring."""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault("GOOGLE_API_USE_CLIENT_CERTIFICATE", "false")

from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from agent.soc_tier1_agent import SocTier1Agent


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


def calculate_aggregate_score(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Computes summary statistics, token usage, and throughput (TPS) across eval cases."""
    total = len(results)
    if total == 0:
        return {
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
    avg_score = sum(r["rubric_score"] for r in results) / total
    passed_count = sum(1 for r in results if r.get("passed", False))
    total_latency = sum(r.get("latency_s", 0.0) for r in results)
    avg_latency = total_latency / total
    total_prompt_tok = sum(r.get("usage", {}).get("prompt_tokens", 0) for r in results)
    total_comp_tok = sum(r.get("usage", {}).get("completion_tokens", 0) for r in results)
    total_tok = sum(r.get("usage", {}).get("total_tokens", 0) for r in results)
    total_tools = sum(len(r.get("trajectory", [])) for r in results)

    avg_gen_tps = round(total_comp_tok / total_latency, 2) if total_latency > 0 else 0.0
    avg_tot_tps = round(total_tok / total_latency, 2) if total_latency > 0 else 0.0

    return {
        "total_cases": total,
        "passed_cases": passed_count,
        "pass_rate": (passed_count / total) * 100.0,
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


def judge_response_with_llm(
    judge_client: genai.Client,
    prompt: str,
    response: str,
    rubric: str,
    reference: Dict[str, Any],
) -> SemanticJudgeResult:
    """Uses Gemini 2.5 Pro as a strict LLM-as-a-judge auto-rater."""
    judge_prompt = f"""
You are an expert Security Operations Center (SOC) Quality Assurance Judge.
Evaluate the following Tier 1 SOC Analyst agent response against the operational rubric.

### User Query / Incident Alert:
{prompt}

### Agent Response:
{response}

### Reference Ground Truth:
{json.dumps(reference, indent=2)}

### Operational Grading Rubric:
{rubric}

### Instructions:
1. Objectively evaluate if the response followed triage procedures.
2. Check for hallucinations on RFC-5737 test documentation IPs or entity lookups.
3. Score from 0 to 100 based strictly on the rubric criteria.
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
) -> Dict[str, Any]:
    """Runs the full evaluation suite against the target Gemma model backend."""
    print("==================================================================")
    print(f" Running Gemma SOC Tier 1 Evaluation: {flavor}")
    print(f" Live SecOps MCP: {'Enabled' if use_live_mcp else 'Disabled (Local Grounding Dataset)'}")
    print("==================================================================")

    with open(evalset_path, "r", encoding="utf-8") as f:
        evalset = json.load(f)

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

    agent = SocTier1Agent(
        project_id=project_id,
        region=region,
        endpoint_id=endpoint_id,
        cloudrun_url=cloudrun_url,
        managed_model=managed_model,
        use_live_mcp=use_live_mcp,
    )
    agent.set_up()

    # Judge client uses us-central1 / global for Gemini 2.5 Pro availability
    judge_region = "us-central1"
    judge_client = genai.Client(vertexai=True, project=project_id, location=judge_region)

    results: List[Dict[str, Any]] = []
    for case in evalset.get("eval_cases", []):
        print(f"\n[Case: {case['eval_id']}] {case['name']}...")
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

        # Semantic Judge
        judge_res = judge_response_with_llm(
            judge_client=judge_client,
            prompt=case["prompt"],
            response=response_text,
            rubric=case["reference"]["grading_rubric"],
            reference=case["reference"],
        )

        case_passed = assert_passed and judge_res.passed
        status_label = "PASS" if case_passed else "FAIL"
        print(
            f"  Result: {status_label} | Rubric: {judge_res.rubric_score}/100 | "
            f"Latency: {latency:.2f}s | Gen TPS: {gen_tps} tok/s | "
            f"Tokens: {tot_tok} | Tool Calls: {len(trajectory)}"
        )
        if failures:
            print(f"  Assertion Failures: {failures}")

        results.append({
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
        })

    summary = calculate_aggregate_score(results)
    print("\n==================================================================")
    print(f" Evaluation Summary for {flavor}")
    print(f" Pass Rate:         {summary['pass_rate']:.1f}% ({summary['passed_cases']}/{summary['total_cases']})")
    print(f" Average Score:     {summary['avg_rubric_score']}/100")
    print(f" Avg Latency:       {summary['avg_latency_s']} s")
    print(f" Output TPS:        {summary['avg_generation_tps']} tok/s (Total TPS: {summary['avg_total_tps']} tok/s)")
    print(f" Total Tokens:      {summary['total_tokens']} (Avg: {summary['avg_tokens_per_case']} / case)")
    print(f" Total Tool Calls:  {summary['total_tool_calls']}")
    print("------------------------------------------------------------------")
    print(f" {'Case ID':<42} | {'Status':<6} | {'Rubric':<8} | {'Latency':<7}")
    print("------------------------------------------------------------------")
    for r in results:
        status_str = "PASS" if r["passed"] else "FAIL"
        print(f" {r['eval_id']:<42} | {status_str:<6} | {r['rubric_score']:>5.1f}/100 | {r['latency_s']:>6.2f}s")
    print("==================================================================")

    return {"flavor": flavor, "summary": summary, "case_results": results}


def main() -> None:
    """CLI entrypoint for running the SOC evaluation runner."""
    parser = argparse.ArgumentParser(description="Evaluate Gemma SOC Agent against Rubrics.")
    parser.add_argument("--flavor", default="local-gemma", help="Model flavor name")
    parser.add_argument("--evalset", default="configs/evals/soc_tier1_evalset.json", help="Path to evalset JSON")
    parser.add_argument("--live-mcp", action="store_true", default=False, help="Use live Google SecOps Remote MCP tools")
    parser.add_argument("--endpoint", "--endpoint-id", dest="endpoint", default=None, help="Vertex AI Endpoint ID")
    parser.add_argument("--cloudrun-url", default=None, help="Cloud Run URL")
    parser.add_argument("--managed-model", default=None, help="Hosted MaaS model name")
    parser.add_argument("--project-id", default=os.environ.get("GCP_PROJECT_ID", "dandye-0324-chronicle"))
    parser.add_argument("--region", default=os.environ.get("GCP_REGION", "us-central1"))
    parser.add_argument("--output-report", default=None, help="Markdown report output path")
    parser.add_argument("--output-json", default=None, help="Raw JSON evaluation output path")
    args = parser.parse_args()

    eval_data = run_evaluation(
        evalset_path=Path(args.evalset),
        flavor=args.flavor,
        endpoint_id=args.endpoint,
        cloudrun_url=args.cloudrun_url,
        managed_model=args.managed_model,
        project_id=args.project_id,
        region=args.region,
        use_live_mcp=args.live_mcp,
    )

    # Save JSON raw artifacts
    json_path = Path(args.output_json) if args.output_json else (
        Path(args.output_report).with_suffix(".json") if args.output_report else None
    )
    if json_path:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(eval_data, f, indent=2)
        print(f"Evaluation JSON saved to: {json_path}")

    # Save Markdown report
    if args.output_report:
        report_path = Path(args.output_report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            f"# SOC Evaluation Report: {args.flavor}",
            f"\n**Date:** {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
            f"**Live SecOps MCP:** {'Enabled' if args.live_mcp else 'Disabled'}",
            "\n## 1. Executive Summary",
            f"- **Pass Rate:** {eval_data['summary']['pass_rate']}% ({eval_data['summary']['passed_cases']}/{eval_data['summary']['total_cases']})",
            f"- **Average Rubric Score:** {eval_data['summary']['avg_rubric_score']} / 100",
            f"- **Average Latency:** {eval_data['summary']['avg_latency_s']} s",
            f"- **Output Throughput (Generation TPS):** {eval_data['summary'].get('avg_generation_tps', 0.0)} tok/s",
            f"- **Total Processing Throughput:** {eval_data['summary'].get('avg_total_tps', 0.0)} tok/s",
            f"- **Total Token Usage:** {eval_data['summary']['total_tokens']} tokens (Avg: {eval_data['summary']['avg_tokens_per_case']} tok/case)",
            f"- **Total Tool Invocations:** {eval_data['summary']['total_tool_calls']}",
            "\n## 2. Evaluation Scorecard Matrix\n",
            "| Case ID | Case Name | Rubric Score | Grounding | Status | Latency | Gen TPS | Total Tokens | Tool Calls |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ]

        for c in eval_data["case_results"]:
            status_str = "PASS" if c["passed"] else "FAIL"
            tok = c.get("usage", {}).get("total_tokens", 0)
            gen_tps = c.get("generation_tps", 0.0)
            tools_cnt = len(c.get("trajectory", []))
            lines.append(
                f"| {c['eval_id']} | {c['name']} | {c['rubric_score']}/100 | "
                f"{c['grounding_score']:.2f} | {status_str} | {c['latency_s']:.2f}s | {gen_tps} tok/s | {tok} | {tools_cnt} |"
            )

        lines.append("\n---\n\n## 3. Detailed Case Trajectories & Reports\n")
        for c in eval_data["case_results"]:
            lines.append(f"### {c['eval_id']}: {c['name']}\n")
            lines.append(f"- **Status:** {'PASS' if c['passed'] else 'FAIL'}")
            lines.append(f"- **Score:** {c['rubric_score']}/100 | Grounding: {c['grounding_score']:.2f} | Latency: {c['latency_s']:.2f}s")
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

            lines.append("\n#### Generated Triage Report:")
            lines.append("```markdown")
            lines.append(c["response"])
            lines.append("```\n")
            lines.append("---\n")

        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"Report saved to: {report_path}")




if __name__ == "__main__":
    main()
