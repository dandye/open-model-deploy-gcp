#!/usr/bin/env python3
"""Approve or verify the evaluation harness lock without importing any model code.

`approve` recomputes the digests of the protected paths (shared scoring code,
the Gen 5 inputs, the frozen Gen 3 suite) and rewrites the lock file. `verify`
checks the current files against the lock and exits 1 on any mismatch. The
optimizer runs the same check before every hillclimb; this script exists so the
lock can be re-approved after an intentional change without spending a model
call on a dry run.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agent.hillclimb_harness import (  # noqa: E402
    DEFAULT_PROTECTED_HARNESS_PATHS,
    HarnessIntegrityGuard,
    HarnessTamperError,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Approve or verify .eval_harness_lock.json")
    parser.add_argument("command", choices=["approve", "verify"])
    parser.add_argument("--root", default=str(ROOT_DIR), help="repository root the protected paths are relative to")
    parser.add_argument("--lock-file", default=None, help="lock file path (default: <root>/.eval_harness_lock.json)")
    parser.add_argument(
        "--path", action="append", default=None,
        help="protected path relative to --root; repeatable; default: the harness defaults",
    )
    return parser


def resolve_paths(args: argparse.Namespace) -> List[str]:
    return list(args.path) if args.path else list(DEFAULT_PROTECTED_HARNESS_PATHS)


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve()
    lock_file = Path(args.lock_file).resolve() if args.lock_file else root / ".eval_harness_lock.json"
    guard = HarnessIntegrityGuard(root_dir=root, lock_file=lock_file, protected_paths=resolve_paths(args))
    try:
        if args.command == "approve":
            payload = guard.approve_and_save()
            print(f"approved {len(payload['files'])} protected file(s); composite_sha256={payload['composite_sha256']}")
            print(f"lock written to {lock_file}")
            return 0
        files = guard.verify(auto_initialize=False)
        print(f"harness lock verified: {len(files)} file(s), composite_sha256={guard.compute_composite_sha256()}")
        return 0
    except HarnessTamperError as err:
        print(f"error: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
