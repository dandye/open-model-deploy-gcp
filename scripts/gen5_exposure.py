#!/usr/bin/env python3
"""Gen 5 split loader and exposure ledger (spec section 6.6).

Every model-facing loader of a Gen 5 split goes through `load_split`, which
appends one line to `configs/evals/gen5/exposure.jsonl`. `final_test` is
sealed: loading it requires `unseal_final_test=True`, a non-empty purpose, and
an approved pre-registration file (spec section 8.2.5). Nothing else in the
repository writes the ledger. Tests redirect it with the `GEN5_EXPOSURE_LEDGER`
environment variable.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import uuid
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
GEN5_ROOT = ROOT_DIR / "configs" / "evals" / "gen5"
MANIFEST_PATH = GEN5_ROOT / "manifest.json"
DEFAULT_LEDGER_PATH = GEN5_ROOT / "exposure.jsonl"
LEDGER_ENV_VAR = "GEN5_EXPOSURE_LEDGER"
SPLITS: Tuple[str, ...] = ("train", "validation", "final_test")
LEDGER_KEYS: Tuple[str, ...] = ("timestamp", "run_id", "git_sha", "split", "eval_ids_sha256", "purpose", "model")


class ExposureError(ValueError):
    """A split load was requested without the information the ledger needs."""


class FinalTestSealedError(RuntimeError):
    """final_test was requested without an explicit, pre-registered unseal."""


def ledger_path() -> Path:
    """The ledger file: the test override when set, else the committed path."""
    override = os.environ.get(LEDGER_ENV_VAR)
    return Path(override) if override else DEFAULT_LEDGER_PATH


def bundle_path(split: str, root: Path = GEN5_ROOT) -> Path:
    if split not in SPLITS:
        raise ExposureError(f"unknown split {split!r}; expected one of {SPLITS}")
    return Path(root) / f"{split}.json"


def read_bundle(split: str, root: Path = GEN5_ROOT) -> Dict[str, Any]:
    return json.loads(bundle_path(split, root).read_text(encoding="utf-8"))


def eval_ids_sha256(eval_ids: Iterable[str]) -> str:
    """SHA-256 over the sorted, newline-joined eval ids."""
    joined = "\n".join(sorted(str(eval_id) for eval_id in eval_ids))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, capture_output=True, text=True, check=True, timeout=10
        )
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def new_run_id() -> str:
    """Timestamp plus a short random suffix: sortable in the ledger, unique across runs."""
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{uuid.uuid4().hex[:8]}"


def _normalize_family(value: str) -> str:
    text = str(value).strip().upper()
    return text if text.startswith("FAM-") else f"FAM-{text}"


def filter_cases(
    cases: Sequence[Dict[str, Any]],
    families: Optional[Sequence[str]] = None,
    difficulty: Optional[Sequence[int]] = None,
) -> List[Dict[str, Any]]:
    """Keeps the cases whose family is in `families` (short or full ids) and whose difficulty is in `difficulty`."""
    wanted_families = {_normalize_family(f) for f in families} if families else None
    wanted_difficulty = {int(d) for d in difficulty} if difficulty else None
    kept: List[Dict[str, Any]] = []
    for case in cases:
        if wanted_families is not None and _normalize_family(case.get("family_id", "")) not in wanted_families:
            continue
        if wanted_difficulty is not None and int(case.get("difficulty") or 0) not in wanted_difficulty:
            continue
        kept.append(case)
    return kept


def check_preregistration(path: Path) -> Dict[str, Any]:
    """Validates the pre-registration file and returns its ledger reference."""
    path = Path(path)
    if not path.exists():
        raise FinalTestSealedError(f"pre-registration file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as err:
        raise FinalTestSealedError(f"pre-registration file is not valid JSON: {path}: {err}") from err
    acceptance = data.get("acceptance") or {}
    hypotheses = (data.get("gen5") or {}).get("hypotheses") or []
    missing = [key for key in ("approved_by", "approved_at") if not acceptance.get(key)]
    if missing:
        raise FinalTestSealedError(
            f"pre-registration {path} is not approved: acceptance.{', acceptance.'.join(missing)} must be set"
        )
    if not hypotheses:
        raise FinalTestSealedError(f"pre-registration {path} lists no gen5.hypotheses")
    try:
        rel = str(path.resolve().relative_to(ROOT_DIR))
    except ValueError:
        rel = str(path)
    return {"path": rel, "sha256": sha256_file(path)}


def expose_cases(
    split: str,
    cases: Sequence[Dict[str, Any]],
    purpose: str,
    model: str,
    run_id: Optional[str] = None,
    unseal_final_test: bool = False,
    preregistration: Optional[Path] = None,
    record: bool = True,
    ledger: Optional[Path] = None,
) -> Dict[str, Any]:
    """Applies the final_test seal, builds the ledger entry, and appends it unless `record` is False."""
    if split not in SPLITS:
        raise ExposureError(f"unknown split {split!r}; expected one of {SPLITS}")
    if not str(purpose or "").strip():
        raise ExposureError("a non-empty purpose is required to load a Gen 5 split (use --purpose)")
    entry: Dict[str, Any] = {
        "timestamp": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "run_id": run_id or new_run_id(),
        "git_sha": git_sha(),
        "split": split,
        "eval_ids_sha256": eval_ids_sha256(case["eval_id"] for case in cases),
        "purpose": str(purpose).strip(),
        "model": str(model or "unknown"),
    }
    if split == "final_test":
        if not unseal_final_test:
            raise FinalTestSealedError(
                "final_test is sealed. Pass --unseal-final-test --purpose '...' --preregistration <file> "
                "after the pre-registration is approved (spec section 8.2.5)."
            )
        if preregistration is None:
            raise FinalTestSealedError("final_test requires --preregistration <approved comparison file>")
        entry["preregistration"] = check_preregistration(preregistration)
    if record:
        append_exposure(entry, ledger)
    return entry


def append_exposure(entry: Dict[str, Any], ledger: Optional[Path] = None) -> Path:
    path = Path(ledger) if ledger else ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=False) + "\n")
    return path


def read_exposure(ledger: Optional[Path] = None) -> List[Dict[str, Any]]:
    path = Path(ledger) if ledger else ledger_path()
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def final_test_exposures(ledger: Optional[Path] = None) -> List[Dict[str, Any]]:
    return [entry for entry in read_exposure(ledger) if entry.get("split") == "final_test"]


def load_split(
    split: str,
    purpose: str,
    model: str,
    root: Path = GEN5_ROOT,
    families: Optional[Sequence[str]] = None,
    difficulty: Optional[Sequence[int]] = None,
    run_id: Optional[str] = None,
    unseal_final_test: bool = False,
    preregistration: Optional[Path] = None,
    record: bool = True,
    ledger: Optional[Path] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Loads one split, applies the filters, and records the exposure. Returns (cases, ledger entry)."""
    bundle = read_bundle(split, root)
    cases = filter_cases(list(bundle.get("eval_cases", [])), families=families, difficulty=difficulty)
    if not cases:
        raise ExposureError(f"no cases of split {split!r} match families={families} difficulty={difficulty}")
    entry = expose_cases(
        split,
        cases,
        purpose=purpose,
        model=model,
        run_id=run_id,
        unseal_final_test=unseal_final_test,
        preregistration=preregistration,
        record=record,
        ledger=ledger,
    )
    return cases, entry
