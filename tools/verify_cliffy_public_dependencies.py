"""Acquire and checksum-audit eight missing public JSR packages, without building.

Candidate pins use the exact lower bounds declared by the sealed import map;
they are not claimed to reproduce unknown historical resolutions. Existing
image caches are never changed. Reports distinguish registry file checksums
from locally measured metadata pins and do not assert full graph compatibility.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
PINS = {
    "@c4spar/mock-command": "1.0.1", "@c4spar/mock-fetch": "1.0.0",
    "@std/async": "1.1.1", "@std/cli": "1.0.27",
    "@std/datetime": "0.225.7", "@std/http": "1.0.24",
    "@std/io": "0.225.3", "@std/semver": "1.0.8",
}
TRANSITIVE_PINS = (
    ("@std/assert", "1.0.2"), ("@std/assert", "0.225.2"),
    ("@std/bytes", "1.0.6"), ("@std/html", "1.0.5"),
    ("@std/media-types", "1.1.0"), ("@std/net", "1.0.6"),
    ("@std/streams", "1.0.17"),
    ("@std/internal", "0.225.1"),
    ("@std/data-structures", "1.1.0"), ("@std/regexp", "1.0.2"),
    ("@std/async", "1.4.0"),
)
PRESERVED_CACHE_PINS = (
    ("@std/assert", "1.0.19"), ("@std/encoding", "1.0.10"),
    ("@std/fmt", "1.0.10"), ("@std/fs", "1.0.24"),
    ("@std/path", "1.1.5"), ("@std/testing", "1.0.0"),
    ("@std/testing", "1.0.19"), ("@std/text", "1.0.19"),
    ("@std/internal", "1.0.14"),
)


def download(url):
    request = urllib.request.Request(url, headers={
        "Accept": "application/json, application/typescript, text/plain",
        "User-Agent": "agentless-ml-dependency-audit/1.0",
    })
    with urllib.request.urlopen(request, timeout=30) as response:
        if not response.url.startswith("https://jsr.io/"):
            raise ValueError("Unexpected registry redirect")
        return response.read()


def checked_file(data, metadata):
    expected = metadata["checksum"]
    if not re.fullmatch(r"sha256-[0-9a-f]{64}", expected):
        raise ValueError("Unsupported registry checksum")
    actual = hashlib.sha256(data).hexdigest()
    if expected != "sha256-" + actual or len(data) != metadata["size"]:
        raise ValueError("Registry checksum or size mismatch")
    return actual


def source_url(package, version, path):
    if (not path.startswith("/") or "//" in path or "\\" in path or "%" in path or "?" in path
            or "#" in path or any(part in (".", "..") for part in path.split("/"))
            or PurePosixPath(path).as_posix() != path):
        raise ValueError("Unsafe registry manifest path")
    return f"https://jsr.io/{package}/{version}{path}"


def external_specifiers(value):
    found = set()
    if isinstance(value, dict):
        specifier = value.get("specifier", "")
        if isinstance(specifier, str) and specifier.startswith(("jsr:", "npm:", "https:", "http:")):
            found.add(specifier)
        for item in value.values():
            found.update(external_specifiers(item))
    elif isinstance(value, list):
        for item in value:
            found.update(external_specifiers(item))
    return found


def audit(package, version, destination):
    destination.mkdir(parents=True, exist_ok=True)

    def store(data):
        digest = hashlib.sha256(data).hexdigest()
        path = destination / digest
        # Each package has its own artifact folder, avoiding concurrent writes.
        path.write_bytes(data)
        return {"sha256": digest, "bytes": len(data), "artifact": str(path)}

    package_url = f"https://jsr.io/{package}/meta.json"
    package_bytes = download(package_url)
    package_pin = {"url": package_url, **store(package_bytes),
                   "checksum_kind": "locally_measured_metadata_pin"}
    versions = json.loads(package_bytes)["versions"]
    if version not in versions or versions[version].get("yanked", False):
        raise ValueError("Requested version absent or yanked")
    version_url = f"https://jsr.io/{package}/{version}_meta.json"
    version_bytes = download(version_url)
    version_pin = {"url": version_url, **store(version_bytes),
                   "checksum_kind": "locally_measured_metadata_pin"}
    metadata = json.loads(version_bytes)

    def read_file(item):
        path, entry = item
        url = source_url(package, version, path)
        if not re.fullmatch(r"sha256-[0-9a-f]{64}", entry["checksum"]):
            raise ValueError("Unsupported registry checksum")
        previous = destination / entry["checksum"].removeprefix("sha256-")
        data = previous.read_bytes() if previous.is_file() else download(url)
        digest = checked_file(data, entry)
        return {"path": path, "url": url, **store(data), "sha256": digest,
                "publisher_checksum": entry["checksum"], "publisher_size": entry["size"],
                "checksum_verified": True}

    files = []
    errors = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        pending = {pool.submit(read_file, item): item[0] for item in metadata["manifest"].items()}
        for future in as_completed(pending):
            try:
                files.append(future.result())
            except Exception as error:
                errors.append({"path": pending[future], "error": str(error)})
    return {
        "package": package, "version": version,
        "status": "verified" if not errors else "incomplete",
        "package_metadata": package_pin, "version_metadata": version_pin,
        "manifest_files": len(metadata["manifest"]), "verified_files": len(files),
        "files": sorted(files, key=lambda item: item["path"]), "errors": errors,
        "external_specifiers": sorted(external_specifiers(metadata)),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT.parent /
                        "output/deepswe-survey/cliffy-public-dependencies-2026-10-09")
    parser.add_argument("--transitives", action="store_true",
                        help="Audit explicit missing transitive pins instead of root pins")
    parser.add_argument("--preserved-cache", action="store_true",
                        help="Verify full package files at the versions observed in the image")
    parser.add_argument("--assemble-manifest", action="store_true",
                        help="Recheck saved bytes and emit a portable checksum manifest; no network")
    args = parser.parse_args()
    if args.assemble_manifest:
        manifest = assemble_manifest(args.output)
        target = ROOT / "experiments/deepswe/cliffy/public_dependencies_2026_10_09.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print(target, flush=True)
        return 0
    records = []
    if args.transitives and args.preserved_cache:
        parser.error("Choose one audit set")
    pins = (PRESERVED_CACHE_PINS if args.preserved_cache else
            TRANSITIVE_PINS if args.transitives else tuple(PINS.items()))
    report_name = ("preserved-cache-verification.json" if args.preserved_cache else
                   "transitive-verification.json" if args.transitives else "verification.json")
    for package, version in pins:
        try:
            record = audit(package, version, args.output / package[1:].replace("/", "--") / version)
        except Exception as error:
            record = {"package": package, "version": version, "status": "unavailable",
                      "error": str(error)}
        records.append(record)
        print(json.dumps({key: record[key] for key in ("package", "version", "status")}), flush=True)
        report = {
            "label": "public_dependency_version_and_checksum_audit_not_image_build",
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "selection_policy": "explicit_declared_lower_bounds_not_historical_resolution",
            "transitive_audit": args.transitives,
            "preserved_cache_audit": args.preserved_cache,
            "cached_versions_changed": False, "deno_version": "2.0.0",
            "deno_compatibility_verified": False, "full_dependency_graph_verified": False,
            "image_built": False, "tests_run": False, "official_survey_updated": False,
            "metadata_checksums_are_not_publisher_signatures": True,
            "records": records,
        }
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / report_name).write_text(json.dumps(report, indent=2) + "\n")
    print(args.output / report_name, flush=True)
    return 0 if all(record["status"] == "verified" for record in records) else 1


def assemble_manifest(output):
    def saved_bytes(item):
        path = Path(item["artifact"]).resolve()
        if not path.is_relative_to(output.resolve()):
            raise ValueError("Saved artifact escapes the audit directory")
        return path.read_bytes()

    records = []
    reports = []
    groups = (("verification.json", "declared_missing"),
              ("transitive-verification.json", "additional_graph_dependencies"),
              ("preserved-cache-verification.json", "preserved_cached_versions"))
    for name, group in groups:
        path = output / name
        data = path.read_bytes()
        report = json.loads(data)
        reports.append({"path": path.relative_to(ROOT.parent).as_posix(),
                        "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
        for record in report["records"]:
            if record["status"] != "verified" or record["verified_files"] != record["manifest_files"]:
                raise ValueError("Cannot pin an incomplete package audit")
            pinned = {key: record[key] for key in ("package", "version", "external_specifiers")}
            pinned["group"] = group
            for key in ("package_metadata", "version_metadata"):
                item = record[key]
                raw = saved_bytes(item)
                if hashlib.sha256(raw).hexdigest() != item["sha256"] or len(raw) != item["bytes"]:
                    raise ValueError("Saved registry metadata changed")
                pinned[key] = {**item, "artifact": Path(item["artifact"]).relative_to(ROOT.parent).as_posix()}
            pinned["files"] = []
            for item in record["files"]:
                raw = saved_bytes(item)
                checked_file(raw, {"checksum": item["publisher_checksum"], "size": item["publisher_size"]})
                if hashlib.sha256(raw).hexdigest() != item["sha256"]:
                    raise ValueError("Saved file pin changed")
                pinned["files"].append({**item, "artifact": Path(item["artifact"]).relative_to(ROOT.parent).as_posix()})
            records.append(pinned)
    expected = set(PINS.items()) | set(TRANSITIVE_PINS) | set(PRESERVED_CACHE_PINS)
    if {(item["package"], item["version"]) for item in records} != expected:
        raise ValueError("Saved audits do not cover the current explicit pin sets")
    return {
        "task_id": "cliffy-config-file-parsing",
        "parent_image_id": "sha256:0a8dd8f1270ec4bb88efadad3021762e1d07274f686276c8a484d26a00bd91b5",
        "label": "verified_public_dependency_artifacts_not_resolution_lock",
        "registry_documentation": "https://jsr.io/docs/api",
        "version_selection_is_not_historical_resolution": True,
        "deno_compatibility_verified": False, "full_dependency_graph_verified": False,
        "npm_graph_verified": False, "image_built": False, "tests_run": False,
        "official_survey_updated": False, "audit_reports": reports,
        "package_versions": len(records), "verified_files": sum(len(item["files"]) for item in records),
        "records": records,
    }


if __name__ == "__main__":
    raise SystemExit(main())
