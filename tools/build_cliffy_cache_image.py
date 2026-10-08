"""Build a separate offline image using only the committed verified JSR artifacts."""

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
PARENT = "sha256:0a8dd8f1270ec4bb88efadad3021762e1d07274f686276c8a484d26a00bd91b5"
IMAGE = "agentless-ml/cliffy-cache:2026-10-09"


def checked_blob(item):
    path = (ROOT.parent / item["artifact"]).resolve()
    allowed = (ROOT.parent / "output/deepswe-survey/cliffy-public-dependencies-2026-10-09").resolve()
    if not path.is_relative_to(allowed):
        raise ValueError("Artifact escapes the verified audit directory")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != item["sha256"] or len(data) != item["bytes"]:
        raise ValueError("Verified artifact changed")
    return data


def cache_entry(url, data):
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.netloc != "jsr.io" or parts.query or parts.fragment:
        raise ValueError("Unexpected cache URL")
    key = hashlib.sha256(parts.path.encode()).hexdigest()
    content_type = ("application/json" if parts.path.endswith(".json") else
                    "application/javascript" if parts.path.endswith(".js") else
                    "application/typescript" if parts.path.endswith(".ts") else "text/plain")
    # This encoding and path key were inspected in the exact Deno 2.0 image.
    footer = json.dumps({"headers": {"content-type": content_type}, "url": url, "time": 0},
                        separators=(",", ":")).encode()
    return key, data + b"\n// denoCacheMetadata=" + footer


def stage(manifest, context):
    cache = context / "seed"
    cache.mkdir()
    versions = {}
    indexes = {}
    for record in manifest["records"]:
        versions.setdefault(record["package"], set()).add(record["version"])
        indexes.setdefault(record["package"], record["package_metadata"])
        for item in [record["version_metadata"], *record["files"]]:
            key, data = cache_entry(item["url"], checked_blob(item))
            (cache / key).write_bytes(data)
    curated = []
    for package, item in indexes.items():
        source = json.loads(checked_blob(item))
        source["versions"] = {version: source["versions"][version]
                              for version in sorted(versions[package])}
        raw = json.dumps(source, separators=(",", ":")).encode()
        key, encoded = cache_entry(item["url"], raw)
        (cache / key).write_bytes(encoded)
        curated.append({"package": package, "url": item["url"], "cache_key": key,
                        "source_sha256": item["sha256"],
                        "curated_body_sha256": hashlib.sha256(raw).hexdigest(),
                        "available_verified_versions": sorted(versions[package]),
                        "preserve_existing_image_entry": True})
    shutil.copyfile(ROOT / "experiments/deepswe/cliffy/Dockerfile.cache", context / "Dockerfile")
    return curated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default=IMAGE)
    args = parser.parse_args()
    manifest_path = ROOT / "experiments/deepswe/cliffy/public_dependencies_2026_10_09.json"
    manifest = json.loads(manifest_path.read_text())
    if manifest["parent_image_id"] != PARENT:
        raise ValueError("Manifest parent mismatch")
    actual = subprocess.check_output(["docker", "image", "inspect", PARENT, "--format", "{{.Id}}"], text=True).strip()
    if actual != PARENT:
        raise ValueError("Parent image mismatch")
    with tempfile.TemporaryDirectory(prefix="cliffy-verified-cache-") as temporary:
        context = Path(temporary)
        curated = stage(manifest, context)
        subprocess.run(["docker", "build", "--pull=false", "--network=none", "-t", args.image, str(context)], check=True)
    image_id = subprocess.check_output(["docker", "image", "inspect", args.image, "--format", "{{.Id}}"], text=True).strip()
    evidence = {"label": "substituted_environment_verified_cache_supplement",
                "parent_image_id": PARENT, "image_id": image_id,
                "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                "network_during_build": "none", "source_or_deno_binary_changed": False,
                "curated_package_indexes": curated, "tests_run": False,
                "official_survey_updated": False}
    output = ROOT.parent / "output/deepswe-survey/cliffy-cache"
    output.mkdir(parents=True, exist_ok=True)
    previous = output / "build.json"
    if previous.exists():
        old = json.loads(previous.read_text())
        (output / ("build-" + old["image_id"].split(":")[1] + ".json")).write_bytes(previous.read_bytes())
    (output / ("build-" + image_id.split(":")[1] + ".json")).write_text(json.dumps(evidence, indent=2) + "\n")
    (output / "build.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps({key: value for key, value in evidence.items()
                      if key != "curated_package_indexes"}, indent=2), flush=True)


if __name__ == "__main__":
    main()
