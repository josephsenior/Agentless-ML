"""Verify and supply only Wasmi's pinned public WAST fixtures.

Executed standalone inside the image; no image Rust source is copied.
"""

import hashlib
import json
import os
import re
import stat
import subprocess
from pathlib import Path, PurePosixPath

BASE = "e1f76e285b9ad68a952b7cf5297bbb7ab91e6028"
PINS = {
    "spec": {
        "commit": "d76759e746f3564a03f6106ae19679742f2a1831",
        "manifest": "75c7fc839f3a694b535a23c811e83e835e4cb3f67488c6f2c5926b775081549b",
        "selected_manifest": "e5eb4065eac513103263493470e4d461e21c12cb3b6e7d495b094b686cb418f2",
    },
    "wasmi": {
        "commit": "60701c2664b235ec07ca0231c32a1764dbce4f23",
        "manifest": "7f87901db978e30a31cbddaeb530ae4045a2950aebbd2cac4dc2651dba0eb68f",
        "selected_manifest": "d3af85605031a2847619b9f3f3619d0e2e8da58918784351e10f8b1ab5851461",
    },
}


def _git(root, *args):
    return subprocess.check_output(
        ["git", "-c", "safe.directory=" + str(root), "-C", str(root), *args],
        env=dict(os.environ, GIT_OPTIONAL_LOCKS="0"),
    )


def _digest(entries):
    data = json.dumps(entries, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(data).hexdigest()


def _safe_path(relative):
    path = PurePosixPath(relative)
    if not path.parts or path.is_absolute() or ".." in path.parts or "\\" in relative:
        raise ValueError("unsafe public WAST fixture path")
    return path


def _without_links(path):
    if any(parent.is_symlink() for parent in (path, *path.parents)):
        raise ValueError("symlink in public WAST fixture path")


def provision_fixtures(image=Path("/app"), candidate=Path("/tmp/work"), base=BASE, pins=PINS):
    image, candidate = Path(image), Path(candidate)
    _without_links(image)
    _without_links(candidate)
    if _git(image, "rev-parse", "HEAD").decode().strip() != base:
        raise ValueError("image base commit mismatch")
    # Derive the allowlist from the pinned public test declarations, not from
    # candidate-controlled requests. The selected-file manifest pins the set.
    declarations = _git(image, "show", base + ":crates/wast/tests/mod.rs").decode("utf-8")
    references = re.findall(r'fn\s+\w+\("(spec|wasmi)/([^"\n]+)"\);', declarations)
    if set(pins) != {"spec", "wasmi"} or not references:
        raise ValueError("invalid public WAST fixture configuration")
    prepared = []
    for name, pin in pins.items():
        source = image / "crates/wast/tests" / name
        destination = candidate / "crates/wast/tests" / name
        _without_links(source)
        _without_links(destination)
        if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
            raise ValueError("refusing to overwrite candidate submodule contents")
        if _git(source, "rev-parse", "HEAD").decode().strip() != pin["commit"]:
            raise ValueError("public WAST submodule commit mismatch: " + name)
        manifest, contents = [], {}
        for record in _git(source, "ls-tree", "-rz", "--full-tree", pin["commit"]).split(b"\0"):
            if not record:
                continue
            metadata, raw_path = record.split(b"\t", 1)
            mode, kind, blob = metadata.decode().split()
            relative = raw_path.decode("utf-8")
            _safe_path(relative)
            path = source / relative
            _without_links(path)
            if mode not in ("100644", "100755") or kind != "blob" or not stat.S_ISREG(path.lstat().st_mode):
                raise ValueError("non-regular public WAST entry")
            data = path.read_bytes()
            actual_blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
            if actual_blob != blob:
                raise ValueError("public WAST file differs from pinned blob: " + relative)
            manifest.append({"path": relative, "mode": mode, "git_blob": blob,
                             "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
            contents[relative] = data
        if _digest(manifest) != pin["manifest"]:
            raise ValueError("public WAST source manifest mismatch: " + name)
        required = {relative + ".wast" for group, relative in references if group == name}
        if not required or not required <= contents.keys():
            raise ValueError("required public WAST fixtures missing: " + name)
        for relative in required:
            _safe_path(relative)
            contents[relative].decode("utf-8")
        selected = [entry for entry in manifest if entry["path"] in required]
        if _digest(selected) != pin["selected_manifest"]:
            raise ValueError("public WAST selected manifest mismatch: " + name)
        prepared.append((name, pin, destination, selected, contents, len(manifest)))

    # Verify both submodules completely before copying anything. No Git data,
    # Rust source, unrelated WAST files or benchmark inputs are provisioned.
    summaries = []
    for name, pin, destination, selected, contents, verified_count in prepared:
        for entry in selected:
            target = destination / entry["path"]
            _without_links(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as stream:
                stream.write(contents[entry["path"]])
            target.chmod(0o644)
            if hashlib.sha256(target.read_bytes()).hexdigest() != entry["sha256"]:
                raise ValueError("copied public WAST checksum mismatch")
        summaries.append({"name": name, "commit": pin["commit"],
                          "source_manifest_sha256": pin["manifest"],
                          "copied_manifest_sha256": pin["selected_manifest"],
                          "verified_source_files": verified_count, "copied_files": len(selected),
                          "copied_bytes": sum(entry["bytes"] for entry in selected)})
    return summaries


if __name__ == "__main__":
    print("verified public WAST fixtures: " + json.dumps(provision_fixtures(), sort_keys=True))
