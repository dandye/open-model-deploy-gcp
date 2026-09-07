import hashlib
import json
from pathlib import Path
import subprocess
import tarfile

import pytest

from scripts.source_bundle import build_bundle, verify_bundle

ROOT = Path(__file__).resolve().parents[1]


def test_bundle_is_reproducible_and_excludes_dirty_files(tmp_path):
    first = tmp_path / "one.tar.gz"
    second = tmp_path / "two.tar.gz"
    (ROOT / "UNTRACKED-BUNDLE-PROBE").write_text("must not ship")
    try:
        a = build_bundle(ROOT, "HEAD", first)
        b = build_bundle(ROOT, "HEAD", second)
        assert a["sha256"] == b["sha256"]
        with tarfile.open(first, "r:gz") as archive:
            names = archive.getnames()
            assert "source_manifest.json" in names
            assert "UNTRACKED-BUNDLE-PROBE" not in names
            manifest = json.load(archive.extractfile("source_manifest.json"))
            assert manifest["source_commit"] == a["source_commit"]
            assert manifest["submodules"]["third_party/ai-runbooks"]
            assert "third_party/ai-runbooks" in manifest["submodules"]
    finally:
        (ROOT / "UNTRACKED-BUNDLE-PROBE").unlink(missing_ok=True)


def test_verify_rejects_corruption_and_existing_destination(tmp_path):
    archive = tmp_path / "bundle.tar.gz"
    descriptor = build_bundle(ROOT, "HEAD", archive)
    corrupted = tmp_path / "corrupt.tar.gz"
    corrupted.write_bytes(archive.read_bytes() + b"x")
    with pytest.raises(ValueError, match="SHA-256"):
        verify_bundle(corrupted, descriptor["sha256"], descriptor["source_commit"], tmp_path / "out")
    destination = tmp_path / "out"
    destination.mkdir()
    with pytest.raises(FileExistsError):
        verify_bundle(archive, descriptor["sha256"], descriptor["source_commit"], destination)


def test_verify_rejects_manifest_commit_mismatch_without_partial_destination(tmp_path):
    archive = tmp_path / "bundle.tar.gz"
    descriptor = build_bundle(ROOT, "HEAD", archive)
    with pytest.raises(ValueError, match="commit mismatch"):
        verify_bundle(archive, descriptor["sha256"], "0" * 40, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_verify_extracts_verified_files_and_modes(tmp_path):
    archive = tmp_path / "bundle.tar.gz"
    descriptor = build_bundle(ROOT, "HEAD", archive)
    destination = tmp_path / "out"
    result = verify_bundle(archive, descriptor["sha256"], descriptor["source_commit"], destination)
    assert result["source_commit"] == descriptor["source_commit"]
    manifest = json.loads((destination / "source_manifest.json").read_text())
    sample = next(iter(manifest["files"]))
    assert hashlib.sha256((destination / sample).read_bytes()).hexdigest() == manifest["files"][sample]


@pytest.mark.parametrize("name", ["../escape", "/absolute", "./dot", "a//b"])
def test_verify_rejects_unsafe_archive_paths(tmp_path, name):
    archive = tmp_path / "bad.tar.gz"
    manifest = {"schema_version": 1, "source_commit": "a" * 40, "files": {}, "submodules": {}}
    with tarfile.open(archive, "w:gz") as tar:
        info = tarfile.TarInfo(name)
        info.size = 1
        tar.addfile(info, __import__("io").BytesIO(b"x"))
        data = (json.dumps(manifest) + "\n").encode()
        info = tarfile.TarInfo("source_manifest.json")
        info.size = len(data)
        tar.addfile(info, __import__("io").BytesIO(data))
    with pytest.raises(ValueError, match="unsafe"):
        verify_bundle(archive, hashlib.sha256(archive.read_bytes()).hexdigest(), "a" * 40, tmp_path / "out")


def _git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _commit(repo):
    _git(repo, 'add', '.')
    _git(repo, '-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=/dev/null',
         '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture')
    return _git(repo, 'rev-parse', 'HEAD')


def test_build_uses_committed_parent_and_pinned_submodule_objects(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    _git(repo, 'init', '-q')
    sub = repo / 'third_party/ai-runbooks'
    sub.mkdir(parents=True)
    _git(sub, 'init', '-q')
    (sub / 'book.md').write_text('pinned runbook')
    pin = _commit(sub)
    (repo / 'main.py').write_text('committed source')
    (repo / 'exécutable file.sh').write_text('#!/bin/sh\nexit 0\n')
    (repo / 'exécutable file.sh').chmod(0o755)
    commit = _commit(repo)
    (repo / 'main.py').write_text('dirty source')
    (repo / '.env').write_text('untracked secret')
    (sub / 'book.md').write_text('later runbook')
    _commit(sub)
    archive = tmp_path / 'bundle.tar.gz'
    descriptor = build_bundle(repo, commit, archive)
    output = tmp_path / 'extracted'
    verify_bundle(archive, descriptor['sha256'], commit, output)
    assert (output / 'main.py').read_text() == 'committed source'
    assert (output / 'third_party/ai-runbooks/book.md').read_text() == 'pinned runbook'
    assert (output / 'exécutable file.sh').stat().st_mode & 0o111
    assert not (output / '.env').exists()
    manifest = json.loads((output / 'source_manifest.json').read_text())
    assert manifest['submodules']['third_party/ai-runbooks'] == pin


@pytest.mark.parametrize('problem', ['symlink', 'hardlink', 'device', 'fifo', 'duplicate',
                                   'directory_traversal', 'directory_collision', 'missing',
                                   'extra', 'wrong_hash', 'manifest_list', 'manifest_directory'])
def test_adversarial_archives_leave_no_destination(tmp_path, problem):
    import io
    archive = tmp_path / 'bad.tar.gz'
    content = b'verified bytes'
    manifest = {'schema_version': 1, 'source_commit': 'a' * 40,
                'files': {'file.py': hashlib.sha256(content).hexdigest()}, 'submodules': {}}
    entries = [('file.py', content, tarfile.REGTYPE)]
    if problem in {'symlink', 'hardlink', 'device', 'fifo'}:
        entries.append(('evil', b'', {'symlink': tarfile.SYMTYPE, 'hardlink': tarfile.LNKTYPE,
                                     'device': tarfile.CHRTYPE, 'fifo': tarfile.FIFOTYPE}[problem]))
    if problem == 'duplicate': entries.append(('file.py', content, tarfile.REGTYPE))
    if problem == 'directory_traversal': entries.append(('../outside', b'', tarfile.DIRTYPE))
    if problem == 'directory_collision':
        entries.append(('file.py/child', content, tarfile.REGTYPE))
        manifest['files']['file.py/child'] = hashlib.sha256(content).hexdigest()
    if problem == 'missing': entries = []
    if problem == 'extra': entries.append(('extra.py', content, tarfile.REGTYPE))
    if problem == 'wrong_hash': manifest['files']['file.py'] = '0' * 64
    if problem == 'manifest_list': manifest = []
    manifest_kind = tarfile.DIRTYPE if problem == 'manifest_directory' else tarfile.REGTYPE
    entries.append(('source_manifest.json', json.dumps(manifest).encode(), manifest_kind))
    with tarfile.open(archive, 'w:gz') as tar:
        for name, data, kind in entries:
            info = tarfile.TarInfo(name)
            info.type = kind
            info.size = len(data) if kind == tarfile.REGTYPE else 0
            info.linkname = '../outside' if kind in {tarfile.SYMTYPE, tarfile.LNKTYPE} else ''
            tar.addfile(info, io.BytesIO(data) if info.size else None)
    with pytest.raises(ValueError):
        verify_bundle(archive, hashlib.sha256(archive.read_bytes()).hexdigest(), 'a' * 40, tmp_path / 'out')
    assert not (tmp_path / 'out').exists()
    assert not list(tmp_path.glob('.out.*'))
    assert not (tmp_path / 'outside').exists()


@pytest.mark.parametrize('names', [('Agent.py', 'agent.py'), ('Foo/a.py', 'foo/b.py')])
def test_filesystem_aliases_cannot_silently_change_verified_output(tmp_path, names):
    import io
    archive = tmp_path / 'alias.tar.gz'
    data = {names[0]: b'first', names[1]: b'second'}
    manifest = {'schema_version': 1, 'source_commit': 'a' * 40,
                'files': {name: hashlib.sha256(value).hexdigest() for name, value in data.items()}}
    with tarfile.open(archive, 'w:gz') as tar:
        for name, content in {**data, 'source_manifest.json': json.dumps(manifest).encode()}.items():
            info = tarfile.TarInfo(name); info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
    try:
        verify_bundle(archive, hashlib.sha256(archive.read_bytes()).hexdigest(), 'a' * 40, tmp_path / 'out')
    except ValueError:
        assert not (tmp_path / 'out').exists()
    else:
        # Case-sensitive filesystems may represent both names, but bytes must remain exact.
        for name, content in data.items():
            assert (tmp_path / 'out' / name).read_bytes() == content
