#!/usr/bin/env python3
"""Outer-to-Inner Loop CLI Analyzer and Fixture Promoter.

Diagnoses SOC agent evaluation execution traces, clusters procedural failures across
runbooks and stages, generates an AQuA Insights-First markdown report (strictly ASCII),
and exports sanitized regression fixtures for inner-loop GEPA reflection and testing.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Sequence

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agent.aqua_diagnostics import (
    CORE_RUNBOOKS,
    FORBIDDEN_EVAL_HOSTNAMES,
    AquaDiagnosticReport,
    cluster_trace_diagnoses,
    sanitize_text,
)

logger = logging.getLogger(__name__)

FINAL_TEST_PATTERN: re.Pattern = re.compile(r"(?:^|[\\/])final_test(?:\.json|[\\/]|$)", re.IGNORECASE)
EXCLUDE_REPORT_NAMES: Sequence[str] = (
    "aqua_diagnostic_report.json",
    "aqua_diagnostic_report.md",
    "evolution_metadata.json",
    "cost_staircase_report.json",
)


def is_forbidden_split_file(path_str: str) -> bool:
    """Returns True if the file path targets the sealed final_test split."""
    norm = path_str.replace("\\", "/")
    return bool(FINAL_TEST_PATTERN.search(norm))


def load_forbidden_literals_from_manifest(manifest_path: str | Path) -> List[str]:
    """Loads forbidden benchmark literals from Gen 5 manifest if present."""
    p = Path(manifest_path)
    if not p.is_absolute():
        p = ROOT_DIR / p
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        lits = data.get("forbidden_literals")
        if isinstance(lits, list):
            return [str(x) for x in lits]
    except Exception as exc:
        logger.warning("Could not read manifest at %s: %s", p, exc)
    return []


def sanitize_trace_payload(
    trace: Dict[str, Any],
    forbidden_literals: Sequence[str] = (),
) -> Dict[str, Any]:
    """Recursively scrubs strings in a trace dict using sanitize_text."""

    def _sanitize_val(val: Any) -> Any:
        if isinstance(val, str):
            return sanitize_text(val, forbidden_literals=forbidden_literals)
        elif isinstance(val, dict):
            return {
                sanitize_text(str(k), forbidden_literals=forbidden_literals): _sanitize_val(v)
                for k, v in val.items()
            }
        elif isinstance(val, list):
            return [_sanitize_val(item) for item in val]
        elif isinstance(val, tuple):
            return tuple(_sanitize_val(item) for item in val)
        return val

    return _sanitize_val(trace)


def _load_harbor_trial(trial_dir: Path) -> Optional[Dict[str, Any]]:
    """Loads a single Harbor trial directory containing scorecard.json."""
    scorecard_path = trial_dir / "scorecard.json"
    if not scorecard_path.exists():
        return None

    try:
        scorecard = json.loads(scorecard_path.read_text(encoding="utf-8"))
    except Exception:
        return None

    # Load trajectory from trajectory.jsonl or trajectory.json if available
    traj_jsonl = trial_dir / "trajectory.jsonl"
    traj_json = trial_dir / "trajectory.json"
    agent_traj = trial_dir / "agent_trajectory.json"

    trajectory: List[Dict[str, Any]] = []
    if traj_jsonl.exists():
        for line in traj_jsonl.read_text(encoding="utf-8").splitlines():
            line_s = line.strip()
            if line_s:
                try:
                    trajectory.append(json.loads(line_s))
                except Exception:
                    pass
    elif traj_json.exists():
        try:
            d = json.loads(traj_json.read_text(encoding="utf-8"))
            if isinstance(d, list):
                trajectory = d
            elif isinstance(d, dict) and "trajectory" in d:
                trajectory = d["trajectory"]
        except Exception:
            pass
    elif agent_traj.exists():
        try:
            d = json.loads(agent_traj.read_text(encoding="utf-8"))
            if isinstance(d, list):
                trajectory = d
            elif isinstance(d, dict) and "trajectory" in d:
                trajectory = d["trajectory"]
        except Exception:
            pass

    if "trajectory" not in scorecard or not scorecard["trajectory"]:
        scorecard["trajectory"] = trajectory

    return scorecard


def _extract_traces_from_dict(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extracts trace/case items from known JSON formats."""
    # Format 1: eval_soc_agent.py results
    for key in ("results", "case_results", "cases", "eval_cases", "trajectories"):
        items = data.get(key)
        if isinstance(items, list):
            return [x for x in items if isinstance(x, dict)]

    # Format 2: single case or Harbor scorecard dict directly
    if "case_id" in data or "eval_id" in data:
        return [data]

    return []


def load_traces_from_inputs(paths: Sequence[str | Path]) -> List[Dict[str, Any]]:
    """Loads traces from evaluation result JSON files, directories, or Harbor trial directories.

    Skips summary diagnostic reports and sealed final_test split files.
    """
    traces: List[Dict[str, Any]] = []

    resolved_paths: List[Path] = []
    for p in paths:
        path_obj = Path(p)
        if not path_obj.is_absolute():
            path_obj = ROOT_DIR / path_obj
        resolved_paths.append(path_obj)

    files_or_dirs_to_check: List[Path] = []
    for rpath in resolved_paths:
        if not rpath.exists():
            continue
        if rpath.is_file():
            files_or_dirs_to_check.append(rpath)
        elif rpath.is_dir():
            # Check if this directory is itself a Harbor trial
            if (rpath / "scorecard.json").exists():
                files_or_dirs_to_check.append(rpath)
            else:
                # Recurse or iterate files
                for child in rpath.rglob("*"):
                    if is_forbidden_split_file(str(child)):
                        continue
                    if child.is_dir() and (child / "scorecard.json").exists():
                        files_or_dirs_to_check.append(child)
                    elif child.is_file() and child.suffix == ".json":
                        files_or_dirs_to_check.append(child)

    seen_case_keys = set()

    for item in files_or_dirs_to_check:
        if is_forbidden_split_file(str(item)):
            continue
        if item.is_file() and item.name in EXCLUDE_REPORT_NAMES:
            continue

        if item.is_dir():
            trial_data = _load_harbor_trial(item)
            if trial_data:
                cid = str(trial_data.get("case_id") or trial_data.get("eval_id") or "")
                key = (cid, str(item))
                if key not in seen_case_keys:
                    seen_case_keys.add(key)
                    traces.append(trial_data)
        elif item.is_file():
            try:
                content = json.loads(item.read_text(encoding="utf-8"))
            except Exception:
                continue

            if isinstance(content, dict):
                sub_traces = _extract_traces_from_dict(content)
                for st in sub_traces:
                    cid = str(st.get("case_id") or st.get("eval_id") or "")
                    key = (cid, str(item), id(st))
                    if key not in seen_case_keys:
                        seen_case_keys.add(key)
                        traces.append(st)
            elif isinstance(content, list):
                for st in content:
                    if isinstance(st, dict):
                        cid = str(st.get("case_id") or st.get("eval_id") or "")
                        key = (cid, str(item), id(st))
                        if key not in seen_case_keys:
                            seen_case_keys.add(key)
                            traces.append(st)

    return traces


def build_markdown_report(report: AquaDiagnosticReport) -> str:
    """Generates an AQuA Insights-First diagnostic markdown report (strictly ASCII)."""
    lines: List[str] = [
        "# AQuA SOC Trajectory Diagnostic Report",
        "",
        "## Executive Summary",
        "",
        f"- Total Evaluated Cases: {report.total_cases}",
        f"- Failed Cases: {report.failed_cases}",
        f"- Zero-Tool Hesitation Cases: {report.zero_tool_hesitation_cases}",
        f"- Inert Cases: {report.inert_cases}",
        f"- Total Operational Loss: ${report.total_operational_loss_usd:,.2f}",
        "",
        "## Failure Breakdown by Category",
        "",
        "| Failure Category | Incident Count |",
        "| :--- | :---: |",
    ]

    for cat, count in sorted(report.category_counts.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"| `{cat}` | {count} |")

    lines.extend([
        "",
        "## Runbook Allocation & Freezing Status",
        "",
        "| Runbook Name | Status | Target Stages | Primary Categories | Clusters |",
        "| :--- | :---: | :--- | :--- | :---: |",
    ])

    for rb in CORE_RUNBOOKS:
        directive = report.directives.get(rb)
        if directive and directive.is_frozen:
            lines.append(f"| `{rb}` | FROZEN (LOCKED) | None (Passing) | None | 0 |")
        elif directive:
            stages_s = ", ".join(directive.target_stages) or "STAGE_A_IDENTITY"
            cats_s = ", ".join(directive.primary_failure_categories) or "None"
            n_clust = len(directive.clusters)
            lines.append(f"| `{rb}` | MUTATING | `{stages_s}` | `{cats_s}` | {n_clust} |")
        else:
            lines.append(f"| `{rb}` | FROZEN (LOCKED) | None (Passing) | None | 0 |")

    lines.extend([
        "",
        "## Clustered Failure Diagnostics",
        "",
    ])

    if not report.clusters:
        lines.append("No failure clusters identified across evaluated traces.")
    else:
        for idx, cluster in enumerate(report.clusters, 1):
            lines.extend([
                f"### Cluster {idx}: `{cluster.implicated_runbook}` - `{cluster.failure_category}` (`{cluster.implicated_stage}`)",
                f"- Cluster ID: `{cluster.cluster_id}`",
                f"- Incidents: {cluster.occurrence_count}",
                f"- Mean Score: {cluster.mean_score:.4f}",
                f"- Total Operational Loss: ${cluster.total_operational_loss_usd:,.2f}",
                f"- Root Cause: {cluster.consolidated_root_cause}",
                f"- Targeted Mutation Directive: {cluster.targeted_mutation_instruction}",
                "",
            ])

    lines.extend([
        "## Reflective Mutation Directives for GEPA Inner Loop",
        "",
    ])

    for rb in CORE_RUNBOOKS:
        directive = report.directives.get(rb)
        if directive:
            lines.append(f"### Directives for `{rb}`")
            lines.append("```markdown")
            lines.append(directive.render_prompt_block())
            lines.append("```")
            lines.append("")

    content = "\n".join(lines)
    # Ensure strictly ASCII
    return content.encode("ascii", "replace").decode("ascii")


def promote_failure_fixtures(
    traces: Sequence[Dict[str, Any]],
    output_dir: str | Path,
    forbidden_literals: Sequence[str] = (),
    pass_threshold: float = 0.80,
) -> List[Path]:
    """Exports sanitized failure traces as regression fixture JSON files."""
    out_path = Path(output_dir)
    if not out_path.is_absolute():
        out_path = ROOT_DIR / out_path
    out_path.mkdir(parents=True, exist_ok=True)

    saved_paths: List[Path] = []
    counter = 1

    for trace in traces:
        score = float(trace.get("score") if trace.get("score") is not None else trace.get("reward", 0.0))
        assert_passed = trace.get("assert_passed")
        is_pass = (score >= pass_threshold) if assert_passed is None else bool(assert_passed)

        if is_pass:
            continue

        sanitized = sanitize_trace_payload(dict(trace), forbidden_literals=forbidden_literals)
        cid = str(sanitized.get("case_id") or sanitized.get("eval_id") or f"failure_{counter:03d}")
        slug = re.sub(r"[^a-zA-Z0-9_-]", "_", cid.lower())
        file_name = f"fixture_{counter:03d}_{slug}.json"
        dest_file = out_path / file_name

        dest_file.write_text(json.dumps(sanitized, indent=2), encoding="utf-8")
        saved_paths.append(dest_file)
        counter += 1

    return saved_paths


def build_arg_parser() -> argparse.ArgumentParser:
    """Builds CLI argument parser for run_aqua_soc_diagnosis.py."""
    parser = argparse.ArgumentParser(
        description="AQuA SOC Trajectory Diagnostic Analyzer & Fixture Promoter",
    )
    parser.add_argument(
        "--input-json",
        nargs="+",
        required=False,
        default=["docs/soc_eval_results"],
        help="One or more evaluation result JSON files or Harbor trial directories.",
    )
    parser.add_argument(
        "--output-report",
        default="docs/soc_eval_results/aqua_diagnostic_report.md",
        help="Path to write the AQuA Insights-First diagnostic Markdown report.",
    )
    parser.add_argument(
        "--output-json",
        default="docs/soc_eval_results/aqua_diagnostic_report.json",
        help="Path to write the structured AquaDiagnosticReport JSON.",
    )
    parser.add_argument(
        "--promote-fixtures-dir",
        default=None,
        help="Optional directory where failure trajectories are exported as sanitized fixtures.",
    )
    parser.add_argument(
        "--manifest",
        default="configs/evals/gen5/manifest.json",
        help="Path to Gen 5 manifest for loading forbidden benchmark literals.",
    )
    return parser


def main(args: Optional[List[str]] = None) -> int:
    """CLI main entry point."""
    parser = build_arg_parser()
    parsed_args = parser.parse_args(args)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    forbidden_literals = load_forbidden_literals_from_manifest(parsed_args.manifest)

    logger.info("Loading traces from: %s", parsed_args.input_json)
    traces = load_traces_from_inputs(parsed_args.input_json)
    logger.info("Loaded %d traces for diagnosis.", len(traces))

    report = cluster_trace_diagnoses(
        traces=traces,
        forbidden_literals=forbidden_literals,
    )

    out_md = Path(parsed_args.output_report)
    if not out_md.is_absolute():
        out_md = ROOT_DIR / out_md
    out_md.parent.mkdir(parents=True, exist_ok=True)
    md_content = build_markdown_report(report)
    out_md.write_text(md_content, encoding="ascii")
    logger.info("Wrote diagnostic report to %s", out_md)

    out_json = Path(parsed_args.output_json)
    if not out_json.is_absolute():
        out_json = ROOT_DIR / out_json
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    logger.info("Wrote structured report JSON to %s", out_json)

    if parsed_args.promote_fixtures_dir:
        promoted = promote_failure_fixtures(
            traces=traces,
            output_dir=parsed_args.promote_fixtures_dir,
            forbidden_literals=forbidden_literals,
        )
        logger.info("Promoted %d sanitized failure fixtures to %s", len(promoted), parsed_args.promote_fixtures_dir)

    return 0


if __name__ == "__main__":
    sys.exit(main())
