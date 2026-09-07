"""Build and verify deterministic, committed source bundles."""

import argparse
import gzip
import hashlib
import io
import json
import os
import re
from pathlib import Path
from pathlib import PurePosixPath
import subprocess
import shutil
import tarfile
import tempfile
from typing import Dict, List, Tuple


SOURCE_MANIFEST = "source_manifest.json"
SUBMODULES = {"third_party/ai-runbooks": "pinned"}
EXCLUDED_SUBMODULES = {
    "external/adk_runbooks": "unused external submodule; excluded from source bundle",
}
EXCLUDED_LINKS = {
    "scripts/deploy_vertex.sh": "legacy deployment alias; not used by evaluation",
    "third_party/ai-runbooks/readme.md": "runbook repository README alias; not used by evaluation",
}
SECRET_NAMES = ("credentials.json", "secrets.json", "id_rsa", "id_ed25519")
SECRET_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".tfstate", ".tfvars")
MAX_ENTRY_SIZE = 64 << 20
MAX_TOTAL_SIZE = 512 << 20
MAX_ARCHIVE_SIZE = 256 << 20
MAX_ENTRIES = 20000


def _run(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          capture_output=True, text=True).stdout


def _is_secret(path: str) -> bool:
    name = Path(path).name.lower()
    return ((name == ".env" or name.startswith(".env.") and not name.endswith(".example"))
            or name in SECRET_NAMES or any(name.endswith(s) for s in SECRET_SUFFIXES))


def _safe_name(name: str) -> bool:
    if not isinstance(name, str) or not name or any(ord(c) < 32 for c in name) or "\\" in name or name.startswith("/") or name.startswith("./") or "//" in name:
        return False
    parts = name.split("/")
    return all(part not in ("", ".", "..") and part.casefold() != ".git" for part in parts)


def _committed_files(repo: Path, revision: str, excluded: list | None = None, prefix: str = "") -> List[Tuple[str, str, str]]:
    raw = subprocess.run(["git", "-C", str(repo), "ls-tree", "-rz", revision], check=True, capture_output=True).stdout
    rows = raw.decode("utf-8", "surrogateescape").split("\0")
    result = []
    for row in rows:
        if not row:
            continue
        fields, name = row.split("\t", 1)
        mode, kind, obj = fields.split()
        if kind == "commit":
            if name not in SUBMODULES and name not in EXCLUDED_SUBMODULES:
                raise ValueError(f"Undeclared nested submodule: {name}")
            continue
        full_name = f"{prefix}/{name}" if prefix else name
        if mode == "120000" and full_name in EXCLUDED_LINKS and excluded is not None:
            excluded.append({"path": full_name, "reason": EXCLUDED_LINKS[full_name]})
            continue
        if kind != "blob" or not _safe_name(name) or mode not in {"100644", "100755"}:
            raise ValueError(f"Unsupported committed entry: {name}")
        if _is_secret(name):
            raise ValueError(f"Refusing to bundle a credential/state filename: {name}")
        result.append((name, obj, mode))
    return result


def _submodule_commit(repo: Path, revision: str, path: str) -> str:
    line = _run(repo, "ls-tree", revision, "--", path).strip()
    if not line:
        raise ValueError(f"Required submodule missing from revision: {path}")
    fields, name = line.split("\t", 1)
    mode, kind, commit = fields.split()
    if mode != "160000" or kind != "commit" or name != path:
        raise ValueError(f"Invalid submodule entry: {path}")
    return commit


def _blob(repo: Path, revision: str, name: str) -> bytes:
    return subprocess.run(["git", "-C", str(repo), "show", f"{revision}:{name}"],
                          check=True, capture_output=True).stdout


def _submodule_blob(subrepo: Path, commit: str, name: str) -> bytes:
    return subprocess.run(["git", "-C", str(subrepo), "show", f"{commit}:{name}"],
                          check=True, capture_output=True).stdout


def _add_file(tar: tarfile.TarFile, name: str, data: bytes, mode: str = "100644") -> None:
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mode = int(mode, 8) & 0o777
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    info.mtime = 0
    tar.addfile(info, io.BytesIO(data))


def build_bundle(repo: Path, revision: str, output: Path) -> dict:
    revision = _run(repo, "rev-parse", "--verify", f"{revision}^{{commit}}").strip()
    files: Dict[str, str] = {}
    contents: Dict[str, Tuple[bytes, str]] = {}
    excluded_files = []
    for name, _obj, mode in _committed_files(repo, revision, excluded_files):
        if name.startswith(tuple(p + "/" for p in SUBMODULES)) or name.startswith(tuple(p + "/" for p in EXCLUDED_SUBMODULES)):
            continue
        data = _blob(repo, revision, name)
        files[name] = hashlib.sha256(data).hexdigest()
        contents[name] = (data, mode)

    submodules: Dict[str, str] = {}
    for path in SUBMODULES:
        commit = _submodule_commit(repo, revision, path)
        subrepo = repo / path
        if not (subrepo / ".git").exists():
            raise ValueError(f"Required submodule is unavailable: {path}")
        submodules[path] = commit
        for name, _obj, mode in _committed_files(subrepo, commit, excluded_files, path):
            if not _safe_name(name) or _is_secret(name):
                continue
            archive_name = f"{path}/{name}"
            data = _submodule_blob(subrepo, commit, name)
            files[archive_name] = hashlib.sha256(data).hexdigest()
            contents[archive_name] = (data, mode)

    manifest = {
        "schema_version": 1,
        "source_commit": revision,
        "files": dict(sorted(files.items())),
        "submodules": submodules,
        "excluded_files": sorted(excluded_files, key=lambda entry: entry["path"]),
        "excluded_submodules": [{"path": p, "reason": r} for p, r in sorted(EXCLUDED_SUBMODULES.items())],
    }
    manifest_bytes = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode()
    if SOURCE_MANIFEST in contents:
        raise ValueError(f"Source repository contains reserved path: {SOURCE_MANIFEST}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0, compresslevel=9) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as tar:
                for name in sorted(contents):
                    _add_file(tar, name, *contents[name])
                _add_file(tar, SOURCE_MANIFEST, manifest_bytes)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    descriptor = {"path": str(output), "sha256": digest, "source_commit": revision}
    output.with_suffix(output.suffix + ".json").write_text(json.dumps(descriptor, indent=2) + "\n")
    return descriptor


def verify_bundle(archive: Path, sha256: str, source_commit: str, destination: Path) -> dict:
    if not re.fullmatch(r"[0-9a-f]{64}", sha256) or not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise ValueError("Expected digest and commit must be full lowercase hashes")
    if archive.stat().st_size > MAX_ARCHIVE_SIZE:
        raise ValueError("Compressed archive exceeds size limit")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != sha256:
        raise ValueError("Archive SHA-256 mismatch")
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{destination.name}.", dir=destination.parent))
    try:
        with tarfile.open(archive, "r:gz") as tar:
            members = []
            total_size = 0
            for member in tar:
                total_size += member.size
                if (len(members) >= MAX_ENTRIES or member.size < 0 or member.size > MAX_ENTRY_SIZE
                        or total_size > MAX_TOTAL_SIZE or member.issparse()):
                    raise ValueError("Archive exceeds entry or size limits")
                members.append(member)
            all_names = [m.name for m in members]
            if len(all_names) != len(set(all_names)) or any(not _safe_name(n) for n in all_names):
                raise ValueError("Archive contains duplicate or unsafe paths")
            if any(not (m.isfile() or m.isdir()) for m in members):
                raise ValueError("Archive contains non-regular entry")
            manifest_member = next((m for m in members if m.name == SOURCE_MANIFEST), None)
            if manifest_member is None or not manifest_member.isfile():
                raise ValueError("Archive is missing regular source manifest")
            manifest = json.load(tar.extractfile(manifest_member))
            if not isinstance(manifest, dict) or manifest.get("schema_version") != 1 or manifest.get("source_commit") != source_commit:
                raise ValueError("Source manifest commit mismatch")
            expected = manifest.get("files")
            file_names = {m.name for m in members if m.isfile()}
            if not isinstance(expected, dict) or SOURCE_MANIFEST in expected or file_names != set(expected) | {SOURCE_MANIFEST}:
                raise ValueError("Archive does not match manifest inventory")
            # Reject file/directory collisions before writing anything to the stage.
            for name in all_names:
                if any(str(parent) in file_names for parent in PurePosixPath(name).parents if str(parent) != "."):
                    raise ValueError("Archive file/directory collision")
            for name, expected_hash in expected.items():
                if not _safe_name(name) or not isinstance(expected_hash, str):
                    raise ValueError("Invalid manifest file inventory")
                data = tar.extractfile(name).read()
                if hashlib.sha256(data).hexdigest() != expected_hash:
                    raise ValueError(f"File hash mismatch: {name}")
            files = {m.name: m for m in members if m.isfile()}
            for name, expected_hash in expected.items():
                member = files[name]
                data = tar.extractfile(member).read()
                target = stage / PurePosixPath(name)
                target.parent.mkdir(parents=True, exist_ok=True)
                try:
                    with target.open("xb") as stream:
                        stream.write(data)
                except FileExistsError as exc:
                    raise ValueError("Archive paths collide on the destination filesystem") from exc
                os.chmod(target, 0o755 if member.mode & 0o111 else 0o644)
            with (stage / SOURCE_MANIFEST).open("xb") as stream:
                stream.write(tar.extractfile(SOURCE_MANIFEST).read())
            actual_names = {file.relative_to(stage).as_posix() for file in stage.rglob("*") if file.is_file()}
            if actual_names != file_names:
                raise ValueError("Extracted paths differ from the manifest inventory")
            for name, expected_hash in expected.items():
                if hashlib.sha256((stage / name).read_bytes()).hexdigest() != expected_hash:
                    raise ValueError("Extracted bytes differ from the manifest")
        stage.rename(destination)
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return {"path": str(destination), "sha256": digest, "source_commit": source_commit}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--repo", type=Path, default=Path.cwd())
    build.add_argument("--revision", default="HEAD")
    build.add_argument("--output", type=Path, required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--archive", type=Path, required=True)
    verify.add_argument("--sha256", required=True)
    verify.add_argument("--source-commit", required=True)
    verify.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args(argv)
    result = build_bundle(args.repo, args.revision, args.output) if args.command == "build" else verify_bundle(args.archive, args.sha256, args.source_commit, args.destination)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
