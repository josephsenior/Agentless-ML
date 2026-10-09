"""Supply pinned public TOML conformance fixtures, never image source code.

This file also runs standalone inside the pinned image via python -c.
"""

import hashlib
import importlib
import json
import os
import stat
import subprocess
from pathlib import Path, PurePosixPath

COMMIT = "08ed8697864548b3cdb4b8decbf496bef47e1c82"
MANIFEST_SHA256 = "00968accf894aefccffc2d3c47c2c78a3f9a06a21f4b62c3a3f5c0d9c2bd7055"
INDEX = "tests/files-toml-1.1.0"


def _safe_path(relative):
    path = PurePosixPath(relative)
    if not relative or path.is_absolute() or ".." in path.parts or "\\" in relative:
        raise ValueError("unsafe public fixture path: " + relative)
    return path


def _without_links(path):
    if any(parent.is_symlink() for parent in (path, *path.parents)):
        raise ValueError("symlink in public fixture path: " + str(path))


def provision_fixtures(
    source=Path("/app/tests/toml-test"),
    destination=Path("/tmp/work/tests/toml-test"),
    expected_commit=COMMIT,
    expected_manifest=MANIFEST_SHA256,
):
    """Verify the complete tracked source manifest before copying its data subset."""
    source, destination = Path(source), Path(destination)
    _without_links(source)
    _without_links(destination)
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        raise ValueError("refusing to overwrite candidate submodule contents")

    def git(*args):
        return subprocess.check_output(
            ["git", "-c", "safe.directory=" + str(source), "-C", str(source), *args],
            env=dict(os.environ, GIT_OPTIONAL_LOCKS="0"),
        )

    head = git("rev-parse", "HEAD").decode().strip()
    if head != expected_commit:
        raise ValueError("public fixture submodule commit mismatch")
    manifest = []
    contents = {}
    for record in git("ls-tree", "-rz", "--full-tree", head).split(b"\0"):
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        mode, kind, oid = metadata.decode().split()
        relative = raw_path.decode("utf-8")
        _safe_path(relative)
        path = source / relative
        _without_links(path)
        if mode not in ("100644", "100755") or kind != "blob" or not stat.S_ISREG(path.lstat().st_mode):
            raise ValueError("non-regular public fixture entry: " + relative)
        content = path.read_bytes()
        blob = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
        if blob != oid:
            raise ValueError("public fixture differs from Git blob: " + relative)
        contents[relative] = content
        manifest.append({"path": relative, "mode": mode, "git_blob": oid,
                         "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()})
    encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    if hashlib.sha256(encoded).hexdigest() != expected_manifest:
        raise ValueError("public fixture manifest mismatch")

    required = {INDEX}
    lines = [line.strip() for line in contents[INDEX].decode("utf-8").splitlines() if line.strip()]
    for relative in lines:
        path = _safe_path(relative)
        if path.parts[0] not in ("valid", "invalid") or path.suffix not in (".toml", ".json"):
            raise ValueError("unexpected public fixture reference: " + relative)
        required.add("tests/" + relative)
        if relative.startswith("valid/") and relative.endswith(".toml"):
            required.add("tests/" + relative[:-5] + ".json")
    if not required <= contents.keys():
        raise ValueError("public fixture index references missing tracked data")

    # No docs, executable tools, Git metadata or repository Python files enter
    # the candidate. All source bytes were verified before the first write.
    selected = [entry for entry in manifest if entry["path"] in required]
    for entry in selected:
        target = destination / entry["path"]
        _without_links(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(contents[entry["path"]])
        target.chmod(0o644)
        if hashlib.sha256(target.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError("copied public fixture checksum mismatch")
    selected_encoded = json.dumps(selected, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return {"submodule_commit": head, "verified_source_files": len(manifest),
            "source_manifest_sha256": expected_manifest, "fixture_index_entries": len(lines),
            "copied_files": len(selected), "copied_bytes": sum(entry["bytes"] for entry in selected),
            "copied_manifest_sha256": hashlib.sha256(selected_encoded).hexdigest()}


def verify_candidate_import(root=Path("/tmp/work/tomlkit")):
    module = importlib.import_module("tomlkit")
    if not Path(module.__file__).resolve().is_relative_to(Path(root).resolve()):
        raise ValueError("refusing non-candidate import: tomlkit")
    print("candidate import verified: tomlkit -> " + module.__file__)


if __name__ == "__main__":
    print("verified public fixtures: " + json.dumps(provision_fixtures(), sort_keys=True))
    verify_candidate_import()
