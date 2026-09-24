#!/usr/bin/env python3
"""Two-Stage Agentic Skill Discovery and Execution Evaluation Rig.

Tests two critical dimensions of agent intelligence:
  Stage 1: Autonomous Skill Discovery & Routing
           Given a user query and an available skill catalog, does the model
           recognize it needs a skill, identify the correct skill, and search/fetch it?
  Stage 2: Cognitive Reasoning & Prior Correction
           Conditioned on receiving the retrieved skill, does the model follow
           production rules, suppress tutorial antipatterns, and satisfy assertions?
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import urllib.request
import urllib.error

# Ensure non-mTLS endpoint behavior
os.environ.setdefault("GOOGLE_API_USE_CLIENT_CERTIFICATE", "false")


@dataclass
class SkillMeta:
    name: str
    description: str
    path: str
    content: str


@dataclass
class DiscoveryTrialResult:
    scenario_id: str
    prompt: str
    expected_skill: str
    acceptable_skills: List[str]
    # Stage 1: Discovery metrics
    stage1_called_tool: bool
    stage1_selected_skill: Optional[str]
    stage1_is_exact_match: bool
    stage1_is_acceptable: bool
    stage1_raw_response: str
    # Stage 2: Execution metrics (conditioned on retrieval)
    stage2_output: str
    stage2_assertions_total: int
    stage2_assertions_matched: int
    stage2_passed: bool
    # Baseline comparison (unassisted prompt only)
    baseline_output: str
    baseline_assertions_matched: int
    baseline_passed: bool
    # Net lift
    net_assertion_lift: int


def load_skill_catalog(skills_dir: Path) -> Dict[str, SkillMeta]:
    """Loads all skills from skills/*/SKILL.md."""
    catalog = {}
    for skill_file in sorted(skills_dir.glob("*/SKILL.md")):
        text = skill_file.read_text(encoding="utf-8")
        name = skill_file.parent.name
        desc = ""
        
        # Parse YAML frontmatter
        match = re.search(r"^---\n(.*?)\n---", text, re.DOTALL)
        if match:
            header = match.group(1)
            name_m = re.search(r"name:\s*([^\n]+)", header)
            desc_m = re.search(r"description:\s*([^\n]+)", header)
            if name_m:
                name = name_m.group(1).strip()
            if desc_m:
                desc = desc_m.group(1).strip()
        
        catalog[name] = SkillMeta(
            name=name,
            description=desc,
            path=str(skill_file),
            content=text,
        )
    return catalog


def get_gcp_access_token() -> str:
    """Retrieve gcloud ADC token."""
    import subprocess
    res = subprocess.run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True, check=True)
    return res.stdout.strip()


def call_llm(
    prompt: str,
    system_instruction: Optional[str] = None,
    model: str = "vertex_ai/gemini-2.5-flash",
    model_name: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = 2048,
    project_id: str = "secops-demo-env",
    location: str = "us-central1",
) -> str:
    """Calls Gemini, dedicated Vertex AI Gemma endpoint, or LiteLLM."""
    if model.startswith("vertex_endpoint/"):
        endpoint_id = model.split("/", 1)[1]
        
        full_user = f"{system_instruction}\n\n{prompt}" if system_instruction else prompt
        check_name = (model_name or model).lower()
        if "llama" in check_name:
            if system_instruction:
                formatted_prompt = f"<|start_header_id|>system<|end_header_id|>\n\n{system_instruction}<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n{prompt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
            else:
                formatted_prompt = f"<|start_header_id|>user<|end_header_id|>\n\n{prompt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
        elif "mistral" in check_name:
            if system_instruction:
                formatted_prompt = f"<s>[INST] {system_instruction}\n\n{prompt} [/INST]\n"
            else:
                formatted_prompt = f"<s>[INST] {prompt} [/INST]\n"
        elif "qwen" in check_name or "deepseek" in check_name or "phi" in check_name:
            if system_instruction:
                formatted_prompt = f"<|im_start|>system\n{system_instruction}<|im_end|>\n<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n"
            else:
                formatted_prompt = f"<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n"
        else:
            formatted_prompt = f"<start_of_turn>user\n{full_user}<end_of_turn>\n<start_of_turn>model\n"
        
        from google.cloud import aiplatform
        aiplatform.init(project=project_id, location=location)
        ep = aiplatform.Endpoint(endpoint_id)

        # 1. Try raw_predict (vLLM / SGLang)
        try:
            raw_body = json.dumps({
                "prompt": formatted_prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }).encode("utf-8")
            resp = ep.raw_predict(body=raw_body, headers={"Content-Type": "application/json"})
            data = json.loads(resp.text)
            predictions = data.get("predictions", [])
            output_text = predictions[0] if predictions else ""
            if "Output:\n" in output_text:
                output_text = output_text.split("Output:\n", 1)[1].strip()
            if output_text:
                return output_text
        except Exception:
            pass

        # 2. Fallback to standard predict
        try:
            pred_resp = ep.predict(instances=[{"prompt": formatted_prompt, "max_tokens": max_tokens, "temperature": temperature}])
            predictions = pred_resp.predictions
            if predictions:
                p = predictions[0]
                if isinstance(p, dict):
                    output_text = (
                        p.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        or p.get("text", "")
                        or p.get("content", "")
                    )
                else:
                    output_text = str(p)
                if "Output:\n" in output_text:
                    output_text = output_text.split("Output:\n", 1)[1].strip()
                return output_text
        except Exception as e_std:
            print(f"[ERROR] Vertex endpoint call failed: {e_std}", file=sys.stderr)
            return ""
        return ""

    if "gemini" in model:
        import time as _time
        from google import genai
        from google.genai import types
        
        clean_model = model.replace("vertex_ai/", "")
        target_location = "global" if ("3.7" in clean_model or "3.8" in clean_model or "global" in location) else location
        client = genai.Client(vertexai=True, project=project_id, location=target_location)
        
        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
        if system_instruction:
            config.system_instruction = system_instruction
            
        for attempt in range(4):
            try:
                resp = client.models.generate_content(
                    model=clean_model,
                    contents=prompt,
                    config=config,
                )
                return resp.text or ""
            except Exception as e:
                if attempt == 3:
                    print(f"[ERROR] Gemini call failed after 4 attempts: {e}", file=sys.stderr)
                    return ""
                _time.sleep(3 * (2 ** attempt))
        return ""

    # Generic litellm fallback
    import litellm
    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})
    
    resp = litellm.completion(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content or ""



def evaluate_assertions_with_judge(
    prompt: str,
    output: str,
    assertions: List[str],
    judge_model: str = "vertex_ai/gemini-2.5-flash",
    project_id: str = "secops-demo-env",
) -> Tuple[int, List[Dict[str, Any]]]:
    """Uses LLM judge to evaluate boolean assertion compliance."""
    judge_system = (
        "You are an expert technical evaluator and judge for Google Cloud CLI and architecture solutions. "
        "Your job is to evaluate whether an agent's response satisfies each assertion strictly and factually. "
        "Return a JSON array of objects with fields: 'assertion' (string), 'passed' (boolean), and 'reason' (brief explanation)."
    )
    
    assertions_text = "\n".join(f"- Assertion {i+1}: {a}" for i, a in enumerate(assertions))
    judge_prompt = f"""Task Prompt:
{prompt}

Agent Solution:
{output}

Assertions to Evaluate:
{assertions_text}

Evaluate each assertion individually. Output strictly JSON with no markdown backticks:
[
  {{"assertion": "...", "passed": true, "reason": "..."}}
]"""

    judge_resp = call_llm(
        judge_prompt,
        system_instruction=judge_system,
        model=judge_model,
        temperature=0.0,
        project_id=project_id,
    )
    
    # Parse JSON from judge
    cleaned = judge_resp.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        
    try:
        results = json.loads(cleaned)
        matched = sum(1 for r in results if r.get("passed") is True)
        return matched, results
    except Exception:
        # Fallback heuristic string check if JSON parsing fails
        matched = 0
        results = []
        for a in assertions:
            # Look for keywords in output
            kw = [w.lower() for w in re.findall(r"[\w-]+", a) if len(w) > 4]
            passed = any(k in output.lower() for k in kw) if kw else False
            if passed:
                matched += 1
            results.append({"assertion": a, "passed": passed, "reason": "heuristic fallback"})
        return matched, results


def evaluate_scenario_discovery_and_execution(
    scenario: Dict[str, Any],
    skill_catalog: Dict[str, SkillMeta],
    model: str = "vertex_ai/gemini-2.5-flash",
    model_name: Optional[str] = None,
    judge_model: str = "vertex_ai/gemini-2.5-flash",
    project_id: str = "secops-demo-env",
) -> DiscoveryTrialResult:
    """Executes the two-stage discovery and execution evaluation for one scenario."""
    scenario_id = scenario["id"]
    prompt = scenario["prompt"]
    expected_skill = scenario.get("expected_skill", "")
    acceptable_skills = scenario.get("acceptable_skills", [])
    assertions = scenario.get("assertions", [])
    
    # --- STAGE 1: Autonomous Skill Discovery & Routing ---
    catalog_summary = "\n".join(
        f"- `{name}`: {meta.description}"
        for name, meta in skill_catalog.items()
    )
    
    discovery_system = f"""You are an autonomous cloud engineering agent equipped with a dynamic skills catalog.
When presented with a user request, you must FIRST decide if a specialized skill is required to answer correctly according to production standards.

Available Skills Catalog:
{catalog_summary}

If you need a skill to solve this task, respond with:
SEARCH_SKILL: <skill-name>

If no skill is needed or you can answer natively with 100% confidence, respond with:
NO_SKILL_NEEDED
followed by your answer."""

    stage1_resp = call_llm(
        prompt,
        system_instruction=discovery_system,
        model=model,
        model_name=model_name,
        temperature=0.0,
        max_tokens=1024,
        project_id=project_id,
    )
    
    # Parse Stage 1 routing decision
    called_tool = "SEARCH_SKILL:" in stage1_resp
    selected_skill = None
    if called_tool:
        match = re.search(r"SEARCH_SKILL:\s*([a-zA-Z0-9_-]+)", stage1_resp)
        if match:
            selected_skill = match.group(1).strip()
            
    is_exact = selected_skill == expected_skill
    is_acceptable = is_exact or (selected_skill in acceptable_skills)
    
    # --- UNASSISTED BASELINE: Raw prompt without skill ---
    baseline_output = call_llm(
        prompt,
        model=model,
        model_name=model_name,
        temperature=0.0,
        project_id=project_id,
    )
    b_matched, _ = evaluate_assertions_with_judge(
        prompt, baseline_output, assertions, judge_model=judge_model, project_id=project_id
    )
    b_passed = (b_matched / len(assertions)) >= 0.75 if assertions else True

    # --- STAGE 2: Cognitive Execution with the Retrieved Skill ---
    # Retrieve the skill (either what the agent chose if acceptable, or ground truth expected skill)
    retrieved_skill_name = selected_skill if is_acceptable else expected_skill
    retrieved_skill_content = ""
    if retrieved_skill_name in skill_catalog:
        retrieved_skill_content = skill_catalog[retrieved_skill_name].content
    elif "google-cloud-developer" in skill_catalog:
        retrieved_skill_content = skill_catalog["google-cloud-developer"].content
        
    execution_system = f"""You are an autonomous Google Cloud engineer.
The following specialized skill documentation has been retrieved for your task:

---
{retrieved_skill_content}
---

Apply all guidelines, least-privilege standards, and safety precautions from the skill to solve the user's prompt."""

    stage2_output = call_llm(
        prompt,
        system_instruction=execution_system,
        model=model,
        model_name=model_name,
        temperature=0.0,
        project_id=project_id,
    )
    
    t_matched, _ = evaluate_assertions_with_judge(
        prompt, stage2_output, assertions, judge_model=judge_model, project_id=project_id
    )
    t_passed = (t_matched / len(assertions)) >= 0.75 if assertions else True

    return DiscoveryTrialResult(
        scenario_id=scenario_id,
        prompt=prompt,
        expected_skill=expected_skill,
        acceptable_skills=acceptable_skills,
        stage1_called_tool=called_tool,
        stage1_selected_skill=selected_skill,
        stage1_is_exact_match=is_exact,
        stage1_is_acceptable=is_acceptable,
        stage1_raw_response=stage1_resp[:300],
        stage2_output=stage2_output,
        stage2_assertions_total=len(assertions),
        stage2_assertions_matched=t_matched,
        stage2_passed=t_passed,
        baseline_output=baseline_output,
        baseline_assertions_matched=b_matched,
        baseline_passed=b_passed,
        net_assertion_lift=t_matched - b_matched,
    )


def run_discovery_benchmark(
    evalset_path: Path,
    skills_dir: Path,
    model: str = "vertex_ai/gemini-2.5-flash",
    judge_model: str = "vertex_ai/gemini-2.5-flash",
    project_id: str = "secops-demo-env",
    output_dir: Path = Path("docs/eval_results/discovery"),
    model_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Runs the full discovery and cognitive execution benchmark."""
    output_dir.mkdir(parents=True, exist_ok=True)
    display_model_name = model_name or model
    
    skill_catalog = load_skill_catalog(skills_dir)
    print(f"Loaded {len(skill_catalog)} skills into catalog.")
    
    evalset_data = json.loads(evalset_path.read_text(encoding="utf-8"))
    scenarios = evalset_data.get("evals", [])
    print(f"Evaluating {len(scenarios)} scenarios from {evalset_path.name} on {model}...")
    
    results: List[DiscoveryTrialResult] = []
    
    for idx, sc in enumerate(scenarios, 1):
        print(f"[{idx}/{len(scenarios)}] Testing {sc['id']}...")
        res = evaluate_scenario_discovery_and_execution(
            sc,
            skill_catalog,
            model=model,
            model_name=model_name,
            judge_model=judge_model,
            project_id=project_id,
        )
        results.append(res)
        status_s1 = "MATCH" if res.stage1_is_exact_match else ("ACCEPTABLE" if res.stage1_is_acceptable else "MISSED")
        print(f"    Stage 1 (Discovery): {res.stage1_selected_skill} ({status_s1})")
        print(f"    Stage 2 (Execution): Baseline={res.baseline_assertions_matched}/{res.stage2_assertions_total} -> WithSkill={res.stage2_assertions_matched}/{res.stage2_assertions_total} (Δ: {res.net_assertion_lift:+d})")

    # Aggregate metrics
    total_scenarios = len(results)
    stage1_tool_calls = sum(1 for r in results if r.stage1_called_tool)
    stage1_exact_matches = sum(1 for r in results if r.stage1_is_exact_match)
    stage1_acceptable_matches = sum(1 for r in results if r.stage1_is_acceptable)
    
    baseline_passed_count = sum(1 for r in results if r.baseline_passed)
    stage2_passed_count = sum(1 for r in results if r.stage2_passed)
    
    total_assertions = sum(r.stage2_assertions_total for r in results)
    baseline_assertions_matched = sum(r.baseline_assertions_matched for r in results)
    stage2_assertions_matched = sum(r.stage2_assertions_matched for r in results)
    
    summary = {
        "model": model,
        "evalset": evalset_path.name,
        "total_scenarios": total_scenarios,
        "stage1_discovery": {
            "tool_call_rate": round(stage1_tool_calls / total_scenarios, 4),
            "exact_routing_rate": round(stage1_exact_matches / total_scenarios, 4),
            "acceptable_routing_rate": round(stage1_acceptable_matches / total_scenarios, 4),
            "exact_matches": stage1_exact_matches,
            "acceptable_matches": stage1_acceptable_matches,
        },
        "stage2_execution": {
            "baseline_pass_rate": round(baseline_passed_count / total_scenarios, 4),
            "with_skill_pass_rate": round(stage2_passed_count / total_scenarios, 4),
            "pass_rate_lift": round((stage2_passed_count - baseline_passed_count) / total_scenarios, 4),
            "baseline_assertion_rate": round(baseline_assertions_matched / total_assertions, 4),
            "with_skill_assertion_rate": round(stage2_assertions_matched / total_assertions, 4),
            "assertion_lift": round((stage2_assertions_matched - baseline_assertions_matched) / total_assertions, 4),
            "baseline_assertions_matched": baseline_assertions_matched,
            "with_skill_assertions_matched": stage2_assertions_matched,
            "total_assertions": total_assertions,
        },
    }
    
    # Generate Markdown report
    md_lines = [
        f"# Empirical Evaluation: Two-Stage Skill Discovery & Prior Correction",
        "",
        f"- **Model Under Test:** `{display_model_name}`",
        f"- **Benchmark Suite:** `{evalset_path.name}` ({total_scenarios} scenarios)",
        f"- **Judge Model:** `{judge_model}`",
        f"- **Date:** {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
        "",
        "## 1. Executive Summary Scorecard",
        "",
        "| Evaluation Stage | Metric | Score | Finding |",
        "| :--- | :--- | :---: | :--- |",
        f"| **Stage 1: Autonomous Discovery** | Tool Trigger Rate | **{summary['stage1_discovery']['tool_call_rate']*100:.1f}%** | Recognized need to query catalog |",
        f"| | Exact Skill Routing | **{summary['stage1_discovery']['exact_routing_rate']*100:.1f}%** | Identified canonical target skill |",
        f"| | Acceptable Skill Routing | **{summary['stage1_discovery']['acceptable_routing_rate']*100:.1f}%** | Loaded valid/acceptable domain skill |",
        f"| **Stage 2: Cognitive Prior Correction** | Baseline Pass Rate | **{summary['stage2_execution']['baseline_pass_rate']*100:.1f}%** | Without skills |",
        f"| | With-Skill Pass Rate | **{summary['stage2_execution']['with_skill_pass_rate']*100:.1f}%** | Conditioned on retrieved skill |",
        f"| | **Net Pass Rate Lift (Δ)** | **{summary['stage2_execution']['pass_rate_lift']*100:+.1f}%** | Measurable capability improvement |",
        f"| | Assertion Match Lift | **{summary['stage2_execution']['baseline_assertions_matched']} -> {summary['stage2_execution']['with_skill_assertions_matched']}** ({summary['stage2_execution']['assertion_lift']*100:+.1f}%) | Specific syntax & rule adherence |",
        "",
        "## 2. Scenario-by-Scenario Discovery & Execution Breakdown",
        "",
        "| ID | Expected Skill | Agent Selected Skill | Discovery Status | Baseline Match | With-Skill Match | Net Lift (Δ) |",
        "| :--- | :--- | :--- | :---: | :---: | :---: | :---: |",
    ]
    
    for r in results:
        status_badge = "EXACT" if r.stage1_is_exact_match else ("ACCEPTABLE" if r.stage1_is_acceptable else "MISSED")
        md_lines.append(
            f"| `{r.scenario_id}` | `{r.expected_skill}` | `{r.stage1_selected_skill or 'NONE'}` | `{status_badge}` | "
            f"{r.baseline_assertions_matched}/{r.stage2_assertions_total} | "
            f"**{r.stage2_assertions_matched}/{r.stage2_assertions_total}** | **{r.net_assertion_lift:+d}** |"
        )
        
    md_lines.append("")
    report_text = "\n".join(md_lines)
    
    safe_name = display_model_name.replace("/", "_").replace(".", "_")
    (output_dir / f"{safe_name}_discovery_report.md").write_text(report_text, encoding="utf-8")
    (output_dir / f"{safe_name}_discovery_results.json").write_text(
        json.dumps({"summary": summary, "trials": [asdict(r) for r in results]}, indent=2),
        encoding="utf-8"
    )
    
    print("\n" + report_text)
    return {"summary": summary, "report_path": str(output_dir / f"{safe_name}_discovery_report.md")}


def main():
    parser = argparse.ArgumentParser(description="Two-Stage Skill Discovery and Execution Evaluation Rig")
    parser.add_argument("--evalset", default="evals/kweinmeister/evals.json", help="Path to evals.json")
    parser.add_argument("--skills-dir", default="skills", help="Path to skills directory")
    parser.add_argument("--model", default="vertex_ai/gemini-2.5-flash", help="Model under test")
    parser.add_argument("--model-name", default=None, help="Display/file name override for model under test")
    parser.add_argument("--judge-model", default="vertex_ai/gemini-2.5-flash", help="Judge model")
    parser.add_argument("--project-id", default="secops-demo-env", help="GCP Project ID")
    parser.add_argument("--output-dir", default="docs/eval_results/discovery", help="Output directory")
    args = parser.parse_args()
    
    run_discovery_benchmark(
        evalset_path=Path(args.evalset),
        skills_dir=Path(args.skills_dir),
        model=args.model,
        judge_model=args.judge_model,
        project_id=args.project_id,
        output_dir=Path(args.output_dir),
        model_name=args.model_name,
    )


if __name__ == "__main__":
    main()
