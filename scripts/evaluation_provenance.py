"""Capture observed evaluation inputs without claiming deployment verification."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any
import uuid


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def file_identity(path: Path) -> dict[str, Any]:
    try:
        return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    except OSError:
        return {"path": str(path), "sha256": None, "status": "unavailable"}


def capture_provenance(root: Path, dataset: Path, configuration: dict[str, Any],
                       runbooks_dir: Path | None = None) -> dict[str, Any]:
    """Snapshot requested config and local files; resolved serving identity stays unknown."""
    def git(*args: str) -> str | None:
        try:
            return subprocess.run(["git", "-C", str(root), *args], check=True,
                                  text=True, capture_output=True, timeout=5).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return None

    status = git("status", "--porcelain", "--untracked-files=normal")
    source_commit = git("rev-parse", "HEAD")
    sources = ["scripts/eval_soc_agent.py", "scripts/eval_cost_engine.py",
               "scripts/eval_trajectory_verifier.py", "agent/soc_tier1_agent.py",
               "agent/hierarchical_soc_agent.py", "agent/soc_environment.py",
               "agent/gemma_agent.py"]
    runbook_files = sorted(runbooks_dir.rglob("*.md")) if runbooks_dir and runbooks_dir.is_dir() else []
    return {
        "schema_version": 1,
        "run_id": str(uuid.uuid4()),
        "source_commit": source_commit,
        "source_identity": {"status": "observed" if source_commit else "unknown",
                            "reason": None if source_commit else "Git revision unavailable at capture time"},
        "source_dirty": status != "" if status is not None else None,
        "model": {"requested": configuration.get("managed_model") or configuration.get("flavor"),
                  "resolved_revision": None, "identity_status": "requested_only"},
        "configuration": configuration,
        "configuration_hash": hashlib.sha256(json.dumps(configuration, sort_keys=True,
                                                        separators=(",", ":")).encode()).hexdigest(),
        "dataset": file_identity(dataset),
        "runbook": {"enabled": runbooks_dir is not None,
                    "files": [file_identity(path) for path in runbook_files],
                    "status": "captured" if runbook_files else "unavailable" if runbooks_dir else "not_applicable"},
        "evaluator": {"files": [file_identity(root / name) for name in sources]},
        "started_at": utc_now(),
        "completed_at": None,
        "logs": [],
        "lifecycle": {"status": "running", "evaluation": "running",
                      "artifact_collection": "unverified", "cleanup": "unverified"},
        "verification_status": "partial_observed_inputs",
    }
