"""Read-only inventory of Cliffy's public JSR dependencies in the pinned image.

Pipe this script to the image's Python stdin with networking disabled. It reads
only /app/deno.json and /deno-cache/remote/https/jsr.io, never held-out task data.
Metadata presence is not proof that a package's whole dependency graph is cached.
"""

import json
import re
from pathlib import Path

URL = re.compile(rb'"url":"(https://jsr\.io/[^"\r\n]+)"')
PACKAGE = re.compile(r"^https://jsr\.io/(@[^/]+/[^/]+)/(.+)$")


def inventory(config, cache):
    packages = {}
    ignored = 0
    for entry in sorted(cache.iterdir()):
        if not entry.is_file():
            continue
        matches = URL.findall(entry.read_bytes())
        # Deno 2.0's cache files include source plus a trailing metadata object.
        # Use the final URL field, not any earlier example embedded in source.
        match = PACKAGE.fullmatch(matches[-1].decode()) if matches else None
        if not match:
            ignored += 1
            continue
        package, resource = match.groups()
        record = packages.setdefault(package, {"package_metadata": False,
                                               "version_metadata": [], "files": 0})
        record["files"] += 1
        if resource == "meta.json":
            record["package_metadata"] = True
        elif resource.endswith("_meta.json"):
            record["version_metadata"].append(resource)
    requested = {}
    for alias, specifier in config["imports"].items():
        if not specifier.startswith("jsr:") or alias.startswith("@cliffy/"):
            continue  # Local workspace packages resolve to candidate source.
        package = specifier[4:].rsplit("@", 1)[0]
        requested[alias] = {"specifier": specifier, **packages.get(package, {
            "package_metadata": False, "version_metadata": [], "files": 0,
        })}
    return {
        "label": "read_only_public_dependency_cache_inventory",
        "metadata_presence_is_not_complete_dependency_coverage": True,
        "ignored_files": ignored,
        "requested_jsr_packages": requested,
        "missing_package_metadata": [alias for alias, record in requested.items()
                                     if not record["package_metadata"]],
        "cached_jsr_packages": packages,
    }


if __name__ == "__main__":
    print(json.dumps(inventory(json.loads(Path("/app/deno.json").read_text()),
                               Path("/deno-cache/remote/https/jsr.io")), indent=2))
