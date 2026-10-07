"""Build a diagnostic image from previously verified public assets, without network."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from verify_pwntools_public_assets import deb_data

ROOT = Path(__file__).resolve().parents[1]
PARENT = "sha256:168f8c6b98131e2e58a4ba9265ac16b658174636cbb2d2de6493a0778c856318"


def checked(data: bytes, pin: dict) -> bytes:
    if hashlib.sha256(data).hexdigest() != pin["sha256"]:
        raise ValueError("SHA256 mismatch")
    if "bytes" in pin and len(data) != pin["bytes"]:
        raise ValueError("Size mismatch")
    return data


def downloaded(pin: dict) -> bytes:
    base = (ROOT / pin["artifact_base"]).resolve()
    filename = pin["artifact"]
    if Path(filename).name != filename:
        raise ValueError("Artifact must be a basename")
    return checked((base / filename).read_bytes(), pin)


def member(package: bytes, pin: dict) -> bytes:
    # Read only the specifically pinned regular member; never extract archive paths.
    with tarfile.open(fileobj=io.BytesIO(deb_data(package)), mode="r:*") as archive:
        entry = archive.getmember(pin["name"])
        if not entry.isfile():
            raise ValueError("Pinned archive member is not a regular file")
        stream = archive.extractfile(entry)
        assert stream is not None
        return checked(stream.read(), pin)


def basename(url: str) -> str:
    name = Path(urlsplit(url).path).name
    if name in ("", ".", "..") or not re.fullmatch(r"[A-Za-z0-9_.+~-]+", name):
        raise ValueError("Unsafe asset filename")
    return name


def build_id_path(value: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ValueError("Invalid pinned build ID")
    return value


def stage(manifest: dict, destination: Path) -> None:
    metadata = {}
    for evidence in manifest["artifacts"]:
        path = (ROOT / evidence["path"]).resolve()
        report = json.loads(checked(path.read_bytes(), evidence))
        for record in report.get("records", []):
            if record.get("url") == "https://libc.rip/api/find" and record.get("status") == 200:
                reply = json.loads(checked((path.parent / record["artifact"]).read_bytes(), record))
                for item in reply:
                    metadata[item["id"]] = item

    def put(relative: str, data: bytes) -> None:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    for pin in manifest["libraries"]:
        name = basename(pin["url"])
        if name == "libc-2.18.so":
            name = "libc6-i386-2.18-6.so"
        put("data/libc-database/" + name, downloaded(pin))
    for pin in manifest["symbol_files"]:
        name = basename(pin["url"])
        put("data/libc-database/" + name, downloaded(pin))
        library_id = name.removesuffix(".symbols")
        # Preserve the provider's real package URL, not a made-up local endpoint.
        put("data/libc-database/" + library_id + ".url",
            (metadata[library_id]["libs_url"] + "\n").encode())
    for pin in manifest["debug_packages"]:
        debug = pin["debug_member"]
        put("data/cache-seed/libcdb_dbg/build_id/" + build_id_path(debug["elf"]["build_id"]),
            member(downloaded(pin), debug))
    package = manifest["current_library_package"]
    package_data = downloaded(package)
    build_id = next(p["elf"]["build_id"] for p in package["inspected_members"]
                    if p["name"].endswith("/libc.so.6"))
    build_id = build_id_path(build_id)
    for pin in package["inspected_members"]:
        name = Path(pin["name"]).name
        relative = ("data/provenance/libc6-copyright" if name == "copyright" else
                    "data/cache-seed/libcdb_libs/" + build_id + "/" + name)
        put(relative, member(package_data, pin))
    for pin in manifest["tool_packages"]:
        put("packages/" + basename(pin["url"]), downloaded(pin))
    put("data/provenance/public-assets.json", (json.dumps(manifest, indent=2) + "\n").encode())
    sums = [hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.relative_to(destination).as_posix()
            for p in sorted(destination.rglob("*")) if p.is_file()]
    put("SHA256SUMS", ("\n".join(sums) + "\n").encode())
    templates = ROOT / "experiments/deepswe/pwntools"
    shutil.copyfile(templates / "Dockerfile.offline", destination / "Dockerfile")
    # Explicit LF endings: this file is sourced by the Linux shell.
    put("setup-offline-data.sh", (templates / "setup-offline-data.sh").read_text().encode())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="agentless-ml/pwntools-offline:2026-10-08")
    parser.add_argument("--artifacts", type=Path, default=ROOT.parent / "output/deepswe-survey/pwntools-offline-2026-10-08")
    args = parser.parse_args()
    actual = subprocess.check_output(["docker", "image", "inspect", "agentless-ml/pwntools-riscv:2026-10-07",
                                      "--format", "{{.Id}}"], text=True).strip()
    if actual != PARENT:
        raise ValueError("Parent image no longer matches the verified identity")
    args.artifacts.mkdir(parents=True, exist_ok=True)
    context = Path(tempfile.mkdtemp(prefix="build-", dir=args.artifacts))
    manifest_path = ROOT / "experiments/deepswe/pwntools/public-assets.json"
    stage(json.loads(manifest_path.read_text()), context)
    print(f"Verified build context: {context}", flush=True)
    result = subprocess.run(["docker", "build", "--network=none", "--pull=false", "--tag", args.image, str(context)])
    if result.returncode:
        return result.returncode
    identity = subprocess.check_output(["docker", "image", "inspect", args.image, "--format", "{{.Id}}"], text=True).strip()
    (context / "build-result.json").write_text(json.dumps({"image": args.image, "image_id": identity,
        "parent_id": actual, "build_network": "none", "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest()}, indent=2))
    print(f"Diagnostic image: {identity}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
