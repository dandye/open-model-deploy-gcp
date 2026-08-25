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
    must_contain: List[str],
    must_not_contain: List[str],
) -> Tuple[bool, List[str]]:
    """Evaluates deterministic substring rules."""
    failures: List[str] = []
    text_lower = response_text.lower()
    for item in must_contain:
        if item.lower() not in text_lower:
            failures.append(f"Missing required substring: '{item}'")
    for item in must_not_contain:
        if item.lower() in text_lower:
            failures.append(f"Contained prohibited substring: '{item}'")
    return len(failures) == 0, failures


def calculate_aggregate_score(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Computes summary statistics across eval cases."""
    total = len(results)
    if total == 0:
        return {
            "total_cases": 0,
            "passed_cases": 0,
            "pass_rate": 0.0,
            "avg_rubric_score": 0.0,
            "avg_latency_s": 0.0,
        }
    avg_score = sum(r["rubric_score"] for r in results) / total
    passed_count = sum(1 for r in results if r.get("passed", False))
    avg_latency = sum(r.get("latency_s", 0.0) for r in results) / total
    return {
        "total_cases": total,
        "passed_cases": passed_count,
        "pass_rate": (passed_count / total) * 100.0,
        "avg_rubric_score": round(avg_score, 1),
        "avg_latency_s": round(avg_latency, 2),
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
) -> Dict[str, Any]:
    """Runs the full evaluation suite against the target Gemma model backend."""
    print("==================================================================")
    print(f" Running Gemma SOC Tier 1 Evaluation: {flavor}")
    print("==================================================================")

    with open(evalset_path, "r", encoding="utf-8") as f:
        evalset = json.load(f)

    agent = SocTier1Agent(
        project_id=project_id,
        region=region,
        endpoint_id=endpoint_id,
        cloudrun_url=cloudrun_url,
        managed_model=managed_model,
    )
    agent.set_up()

    judge_client = genai.Client(vertexai=True, project=project_id, location=region)

    results: List[Dict[str, Any]] = []
    for case in evalset.get("eval_cases", []):
        print(f"\n[Case: {case['eval_id']}] {case['name']}...")
        start_time = time.time()
        res = agent.query(prompt=case["prompt"])
        latency = time.time() - start_time
        response_text = res.get("response", "")

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
        print(f"  Result: {status_label} | Rubric: {judge_res.rubric_score}/100 | Latency: {latency:.2f}s")
        if failures:
            print(f"  Assertion Failures: {failures}")

        results.append({
            "eval_id": case["eval_id"],
            "name": case["name"],
            "latency_s": latency,
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
    print(f" Pass Rate:     {summary['pass_rate']:.1f}% ({summary['passed_cases']}/{summary['total_cases']})")
    print(f" Average Score: {summary['avg_rubric_score']}/100")
    print(f" Avg Latency:   {summary['avg_latency_s']} s")
    print("==================================================================")

    return {"flavor": flavor, "summary": summary, "case_results": results}


def main() -> None:
    """CLI entrypoint for running the SOC evaluation runner."""
    parser = argparse.ArgumentParser(description="Evaluate Gemma SOC Agent against Rubrics.")
    parser.add_argument("--flavor", default="local-gemma", help="Model flavor name")
    parser.add_argument("--evalset", default="configs/evals/soc_tier1_evalset.json", help="Path to evalset JSON")
    parser.add_argument("--endpoint", default=None, help="Vertex AI Endpoint ID")
    parser.add_argument("--cloudrun-url", default=None, help="Cloud Run URL")
    parser.add_argument("--managed-model", default=None, help="Hosted MaaS model name")
    parser.add_argument("--project-id", default=os.environ.get("GCP_PROJECT_ID", "dandye-0324-chronicle"))
    parser.add_argument("--region", default=os.environ.get("GCP_REGION", "us-central1"))
    parser.add_argument("--output-report", default=None, help="Markdown report output path")
    args = parser.parse_args()

    eval_data = run_evaluation(
        evalset_path=Path(args.evalset),
        flavor=args.flavor,
        endpoint_id=args.endpoint,
        cloudrun_url=args.cloudrun_url,
        managed_model=args.managed_model,
        project_id=args.project_id,
        region=args.region,
    )

    if args.output_report:
        report_path = Path(args.output_report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            f"# SOC Evaluation Report: {args.flavor}",
            f"\n**Date:** {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
            "\n## Summary",
            f"- **Pass Rate:** {eval_data['summary']['pass_rate']}%",
            f"- **Average Rubric Score:** {eval_data['summary']['avg_rubric_score']}/100",
            f"- **Average Latency:** {eval_data['summary']['avg_latency_s']} s",
            "\n## Detailed Case Breakdown\n",
            "| Case ID | Case Name | Rubric Score | Grounding | Status | Latency |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ]
        for c in eval_data["case_results"]:
            status_str = "PASS" if c["passed"] else "FAIL"
            lines.append(
                f"| {c['eval_id']} | {c['name']} | {c['rubric_score']}/100 | "
                f"{c['grounding_score']:.2f} | {status_str} | {c['latency_s']:.2f}s |"
            )
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    main()
