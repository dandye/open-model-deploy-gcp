#!/usr/bin/env python3
"""Aggregates all discovery evaluation results in docs/eval_results/discovery into a master markdown comparison report."""

import json
from pathlib import Path
import sys

def main():
    discovery_dir = Path("docs/eval_results/discovery")
    if not discovery_dir.exists():
        print(f"Directory {discovery_dir} does not exist.")
        sys.exit(1)

    result_files = sorted(discovery_dir.glob("*_discovery_results.json"))
    if not result_files:
        print("No result files found.")
        sys.exit(0)

    rows = []
    all_scenarios = {}

    for f in result_files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            summary = data.get("summary", {})
            trials = data.get("trials", [])
            model_name = f.stem.replace("_discovery_results", "")

            # If model name has endpoint, try to clean it
            display_name = model_name
            if "vertex_ai_gemini-2_5-flash" in model_name:
                display_name = "gemini-2.5-flash"

            s1 = summary.get("stage1_discovery", {})
            s2 = summary.get("stage2_execution", {})

            rows.append({
                "model": display_name,
                "tool_rate": s1.get("tool_call_rate", 0.0),
                "exact_rate": s1.get("exact_routing_rate", 0.0),
                "accept_rate": s1.get("acceptable_routing_rate", 0.0),
                "baseline_pass": s2.get("baseline_pass_rate", 0.0),
                "with_skill_pass": s2.get("with_skill_pass_rate", 0.0),
                "pass_lift": s2.get("pass_rate_lift", 0.0),
                "baseline_asserts": s2.get("baseline_assertions_matched", 0),
                "with_skill_asserts": s2.get("with_skill_assertions_matched", 0),
                "total_asserts": s2.get("total_assertions", 48),
                "assert_lift": s2.get("assertion_lift", 0.0),
            })

            for t in trials:
                sc_id = t["scenario_id"]
                if sc_id not in all_scenarios:
                    all_scenarios[sc_id] = {
                        "expected_skill": t.get("expected_skill", ""),
                        "models": {}
                    }
                all_scenarios[sc_id]["models"][display_name] = {
                    "selected": t.get("stage1_selected_skill") or "NONE",
                    "exact": t.get("stage1_is_exact_match", False),
                    "acceptable": t.get("stage1_is_acceptable", False),
                    "b_matched": t.get("baseline_assertions_matched", 0),
                    "s_matched": t.get("stage2_assertions_matched", 0),
                    "total": t.get("stage2_assertions_total", 4),
                    "lift": t.get("net_assertion_lift", 0),
                }

        except Exception as e:
            print(f"Error parsing {f}: {e}")

    # Build Markdown table
    md = []
    md.append("# Master Empirical Open-Weights Evaluation: Skill Discovery & Prior Correction")
    md.append("")
    md.append(f"**Total Models Evaluated:** {len(rows)}  ")
    md.append(f"**Benchmark Suite:** `evals/gemma-deploy/evals.json` (12 production scenarios)  ")
    md.append(f"**Judge Model:** `vertex_ai/gemini-2.5-flash`  ")
    md.append("")
    md.append("## 1. Cross-Model Scorecard")
    md.append("")
    md.append("| Model | Tool Trigger Rate | Exact Routing | Acceptable Routing | Baseline Pass | With-Skill Pass | Pass Lift (Δ) | Assertions Matched | Assertion Lift |")
    md.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")

    # Sort rows by model name
    for r in sorted(rows, key=lambda x: x["model"]):
        md.append(
            f"| `{r['model']}` | **{r['tool_rate']*100:.1f}%** | **{r['exact_rate']*100:.1f}%** | **{r['accept_rate']*100:.1f}%** | "
            f"{r['baseline_pass']*100:.1f}% | **{r['with_skill_pass']*100:.1f}%** | **{r['pass_lift']*100:+.1f}%** | "
            f"{r['baseline_asserts']} -> **{r['with_skill_asserts']}**/{r['total_asserts']} | **{r['assert_lift']*100:+.1f}%** |"
        )

    md.append("")
    md.append("## 2. Granular Scenario-by-Scenario Matrix")
    md.append("")

    models_list = sorted([r["model"] for r in rows])
    headers = ["Scenario ID", "Expected Skill"] + [f"`{m}` (Route / Lift)" for m in models_list]
    md.append("| " + " | ".join(headers) + " |")
    md.append("| " + " | ".join([":---" for _ in headers]) + " |")

    for sc_id in sorted(all_scenarios.keys()):
        sc_data = all_scenarios[sc_id]
        row_cells = [f"`{sc_id}`", f"`{sc_data['expected_skill']}`"]
        for m in models_list:
            m_res = sc_data["models"].get(m)
            if m_res:
                status = "EXACT" if m_res["exact"] else ("ACC" if m_res["acceptable"] else "MISS")
                row_cells.append(f"{m_res['selected']} ({status}) / {m_res['s_matched']}/{m_res['total']} ({m_res['lift']:+d})")
            else:
                row_cells.append("-")
        md.append("| " + " | ".join(row_cells) + " |")

    output_path = discovery_dir / "master_open_model_sweep_report.md"
    output_path.write_text("\n".join(md), encoding="utf-8")
    print(f"Master report written to: {output_path}")

if __name__ == "__main__":
    main()
