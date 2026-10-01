"""Disciplined Hillclimber Harness: Checksum Lock, Noise Floor Gate, JSONL Ledger, and Cost Staircase."""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


class HarnessTamperError(RuntimeError):
  """Raised when protected evaluation harness files or datasets change without --approve-harness."""


DEFAULT_PROTECTED_HARNESS_PATHS: Tuple[str, ...] = (
    "configs/evals/gen3/soc_tier1_interactive.json",
    "agent/soc_environment.py",
    "scripts/eval_trajectory_verifier.py",
    "scripts/eval_cost_engine.py",
    "scripts/eval_soc_agent.py",
)


class HarnessIntegrityGuard:
  """Locks SHA-256 digests of evaluation datasets and grading code to prevent reward hacking."""

  def __init__(
      self,
      root_dir: Path,
      lock_file: Optional[Path] = None,
      protected_paths: Optional[Sequence[Path | str]] = None,
  ) -> None:
    self.root_dir = Path(root_dir).resolve()
    self.lock_file = (
        Path(lock_file).resolve()
        if lock_file is not None
        else (self.root_dir / ".eval_harness_lock.json")
    )
    raw_paths = (
        protected_paths
        if protected_paths is not None
        else DEFAULT_PROTECTED_HARNESS_PATHS
    )
    self.protected_paths: List[Path] = [Path(p) for p in raw_paths]

  def _resolve_rel_key(self, path: Path) -> Tuple[str, Path]:
    full_path = path if path.is_absolute() else (self.root_dir / path)
    full_path = full_path.resolve()
    try:
      rel_key = str(full_path.relative_to(self.root_dir))
    except ValueError:
      rel_key = str(full_path)
    return rel_key, full_path

  def compute_manifest(self) -> Dict[str, str]:
    """Compute SHA-256 hex digests for all protected harness files."""
    manifest: Dict[str, str] = {}
    for p in self.protected_paths:
      rel_key, full_path = self._resolve_rel_key(p)
      if not full_path.exists():
        raise HarnessTamperError(
            f"Protected harness file is missing: {rel_key} ({full_path})"
        )
      digest = hashlib.sha256(full_path.read_bytes()).hexdigest()
      manifest[rel_key] = digest
    return manifest

  def compute_composite_sha256(self) -> str:
    """Compute a single composite SHA-256 over the sorted manifest."""
    manifest = self.compute_manifest()
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

  def approve_and_save(self) -> Dict[str, Any]:
    """Approve current harness state and write lockfile to disk."""
    manifest = self.compute_manifest()
    payload = {
        "approved_at_utc": datetime.now(timezone.utc).isoformat(),
        "composite_sha256": self.compute_composite_sha256(),
        "files": manifest,
    }
    self.lock_file.parent.mkdir(parents=True, exist_ok=True)
    self.lock_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload

  def verify(self, auto_initialize: bool = True) -> Dict[str, str]:
    """Verify current files against lockfile; raise HarnessTamperError on mismatch."""
    if not self.lock_file.exists():
      if auto_initialize:
        saved = self.approve_and_save()
        return saved["files"]
      raise HarnessTamperError(
          f"Harness lockfile does not exist at {self.lock_file}. "
          "Run with --approve-harness to initialize."
      )

    locked_data = json.loads(self.lock_file.read_text(encoding="utf-8"))
    locked_files: Dict[str, str] = locked_data.get("files", {})
    current_files = self.compute_manifest()

    mismatches: List[str] = []
    for rel_key, curr_hash in current_files.items():
      expected_hash = locked_files.get(rel_key)
      if expected_hash != curr_hash:
        mismatches.append(
            f"{rel_key} (expected {str(expected_hash)[:12]}, got"
            f" {curr_hash[:12]})"
        )
    for rel_key in locked_files:
      if rel_key not in current_files:
        mismatches.append(f"{rel_key} (removed from protected list)")

    if mismatches:
      raise HarnessTamperError(
          "Evaluation harness integrity check failed. Modified files: "
          + ", ".join(mismatches)
          + ". Do not edit evaluation files during hillclimbing, or pass"
          " --approve-harness if intentional."
      )
    return current_files
