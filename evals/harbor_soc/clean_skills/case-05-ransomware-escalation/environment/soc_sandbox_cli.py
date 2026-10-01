#!/usr/bin/env python3
"""Container Sandbox CLI (soc-cli) wrapping SocEnvironment with file persistence."""

import argparse
import datetime
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agent.soc_environment import EnvironmentAction, SocEnvironment

DEFAULT_EVALSET_PATHS = [
    Path("/app/soc_tier1_interactive.json"),
    ROOT_DIR / "configs" / "evals" / "gen3" / "soc_tier1_interactive.json",
]

EPISTEMIC_TOOLS = {
    "get_ip_report",
    "get_ip_address_report",
    "get_domain_report",
    "get_file_report",
    "lookup_entity",
    "summarize_entity",
    "list_cases",
    "get_case",
    "fetch_alert_data",
    "udm_search",
}

PRAGMATIC_ACTIONS = {
    "isolate_host",
    "isolate",
    "unblock_host",
    "unisolate_host",
    "unisolate",
    "block_indicator",
    "block_domain",
    "block_ip",
    "block_hash",
    "update_case_comment",
    "post_case_comment",
    "create_case_comment",
    "add_case_comment",
    "close_case",
    "resolve_case",
}

PRIMARY_ARG_MAP = {
    "get_ip_report": "ip",
    "get_ip_address_report": "ip",
    "get_domain_report": "domain",
    "get_file_report": "file_hash",
    "lookup_entity": "entity_id",
    "summarize_entity": "entity_id",
    "list_cases": "query",
    "get_case": "case_id",
    "fetch_alert_data": "case_id",
    "udm_search": "query",
    "isolate_host": "hostname",
    "isolate": "hostname",
    "unblock_host": "hostname",
    "unisolate_host": "hostname",
    "unisolate": "hostname",
    "block_indicator": "indicator",
    "block_domain": "indicator",
    "block_ip": "indicator",
    "block_hash": "indicator",
    "update_case_comment": "comment",
    "post_case_comment": "comment",
    "create_case_comment": "comment",
    "add_case_comment": "comment",
    "close_case": "case_id",
    "resolve_case": "case_id",
}


def load_eval_case(case_id: str, evalset_path: Optional[Path] = None) -> Dict[str, Any]:
    """Loads a specific case dictionary by eval_id from soc_tier1_interactive.json."""
    candidate_paths = [evalset_path] if evalset_path else DEFAULT_EVALSET_PATHS
    for path in candidate_paths:
        if path and path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            for case in data.get("eval_cases", []):
                if case.get("eval_id") == case_id:
                    return dict(case)
    return {"eval_id": case_id}


def _restore_environment(state_path: Path, case_id: str, evalset_path: Optional[Path] = None) -> SocEnvironment:
    """Restores SocEnvironment from state_path or initializes from case_id."""
    if state_path.exists():
        snapshot = json.loads(state_path.read_text(encoding="utf-8"))
        env_obj = SocEnvironment(initial_state=snapshot)
        env_obj.action_history = [
            EnvironmentAction(**act) for act in snapshot.get("action_history", [])
        ]
        return env_obj

    case_dict = load_eval_case(case_id, evalset_path=evalset_path)
    return SocEnvironment.from_eval_case(case_dict)


def _save_environment(env_obj: SocEnvironment, state_path: Path) -> Dict[str, Any]:
    """Persists SocEnvironment state snapshot to disk."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot = env_obj.get_state_snapshot()
    state_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    return snapshot


def _append_trajectory_step(
    traj_path: Path,
    tool_name: str,
    args: Dict[str, Any],
    observation: Dict[str, Any],
) -> None:
    """Appends a single tool or action step to the JSONL trajectory log."""
    traj_path.parent.mkdir(parents=True, exist_ok=True)
    existing_lines = 0
    if traj_path.exists():
        existing_lines = sum(
            1 for line in traj_path.read_text(encoding="utf-8").splitlines() if line.strip()
        )
    record = {
        "step": existing_lines + 1,
        "iteration": existing_lines + 1,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "tool": tool_name,
        "args": args,
        "observation": observation,
    }
    with traj_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def _parse_tool_args(command: str, raw_args: List[str]) -> Dict[str, Any]:
    """Parses flexible CLI flags, positional arguments, or --json payloads."""
    parser = argparse.ArgumentParser(prog=f"soc-cli {command}", add_help=False)
    parser.add_argument("positional", nargs="*")
    parser.add_argument("--json", dest="json_payload", default=None)
    for flag in (
        "ip",
        "domain",
        "file_hash",
        "hash",
        "sha256",
        "entity_id",
        "entity",
        "entity_type",
        "type",
        "query",
        "filter",
        "case_id",
        "caseId",
        "hostname",
        "host",
        "target",
        "indicator",
        "value",
        "comment",
        "text",
        "note",
        "verdict",
        "resolution",
    ):
        parser.add_argument(f"--{flag}", default=None)

    ns, unknown = parser.parse_known_args(raw_args)
    parsed: Dict[str, Any] = {}

    if ns.json_payload:
        try:
            loaded = json.loads(ns.json_payload)
            if isinstance(loaded, dict):
                parsed.update(loaded)
        except json.JSONDecodeError:
            pass

    for key, val in vars(ns).items():
        if key in ("positional", "json_payload") or val is None:
            continue
        parsed[key] = val

    # Parse any extra --key=value or --key value pairs in unknown
    idx = 0
    while idx < len(unknown):
        token = unknown[idx]
        if token.startswith("--"):
            clean_key = token[2:].replace("-", "_")
            if "=" in clean_key:
                k_part, v_part = clean_key.split("=", 1)
                parsed[k_part] = v_part
            elif idx + 1 < len(unknown) and not unknown[idx + 1].startswith("--"):
                parsed[clean_key] = unknown[idx + 1]
                idx += 1
        idx += 1

    if ns.positional:
        primary_key = PRIMARY_ARG_MAP.get(command)
        if primary_key and primary_key not in parsed:
            parsed[primary_key] = ns.positional[0]
            if command in ("update_case_comment", "post_case_comment", "create_case_comment", "add_case_comment"):
                if len(ns.positional) >= 2 and "case_id" not in parsed:
                    parsed["case_id"] = ns.positional[0]
                    parsed["comment"] = " ".join(ns.positional[1:])

    # Default case_id for comment/close if omitted by agent
    if command in (
        "update_case_comment",
        "post_case_comment",
        "create_case_comment",
        "add_case_comment",
        "close_case",
        "resolve_case",
    ) and not parsed.get("case_id") and not parsed.get("caseId"):
        parsed["case_id"] = "CASE-33279"

    return parsed


def run_soc_cli(
    argv: List[str],
    env: Optional[Dict[str, str]] = None,
    evalset_path: Optional[Path] = None,
) -> Tuple[int, Dict[str, Any]]:
    """Executes a soc-cli command and returns (exit_code, response_dict)."""
    runtime_env = dict(os.environ)
    if env:
        runtime_env.update(env)

    case_id = runtime_env.get("SOC_CASE_ID", "CASE-GEN3-01-LOKIBOT-C2")
    state_path = Path(runtime_env.get("SOC_STATE_FILE", "/var/lib/soc/state.json"))
    traj_path = Path(runtime_env.get("SOC_TRAJECTORY_FILE", "/logs/artifacts/trajectory.jsonl"))

    if not argv or argv[0] in ("-h", "--help", "help"):
        help_payload = {
            "epistemic_tools": sorted(EPISTEMIC_TOOLS),
            "pragmatic_actions": sorted(PRAGMATIC_ACTIONS),
            "lifecycle_commands": ["reset", "status"],
            "case_id": case_id,
        }
        return 0, help_payload

    command = argv[0].strip().lower()
    rest = argv[1:]

    if command == "reset":
        case_dict = load_eval_case(case_id, evalset_path=evalset_path)
        env_obj = SocEnvironment.from_eval_case(case_dict)
        _save_environment(env_obj, state_path)
        if traj_path.exists():
            traj_path.unlink()
        traj_path.parent.mkdir(parents=True, exist_ok=True)
        traj_path.write_text("", encoding="utf-8")
        return 0, {"status": "RESET", "case_id": case_id, "state_file": str(state_path)}

    if command == "status":
        env_obj = _restore_environment(state_path, case_id, evalset_path=evalset_path)
        snapshot = _save_environment(env_obj, state_path)
        return 0, snapshot

    env_obj = _restore_environment(state_path, case_id, evalset_path=evalset_path)
    tool_args = _parse_tool_args(command, rest)

    if command in EPISTEMIC_TOOLS:
        result = env_obj.query_tool(command, tool_args)
        _save_environment(env_obj, state_path)
        _append_trajectory_step(traj_path, command, tool_args, result)
        return 0, result

    if command in PRAGMATIC_ACTIONS:
        result = env_obj.execute_action(command, tool_args)
        _save_environment(env_obj, state_path)
        _append_trajectory_step(traj_path, command, tool_args, result)
        return 0, result

    err = {
        "status": "ERROR",
        "error": f"Unknown soc-cli command '{command}'",
        "supported_epistemic_tools": sorted(EPISTEMIC_TOOLS),
        "supported_pragmatic_actions": sorted(PRAGMATIC_ACTIONS),
    }
    return 1, err


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point for /usr/local/bin/soc-cli."""
    args = sys.argv[1:] if argv is None else argv
    rc, payload = run_soc_cli(args)
    print(json.dumps(payload, indent=2))
    return rc


if __name__ == "__main__":
    sys.exit(main())
