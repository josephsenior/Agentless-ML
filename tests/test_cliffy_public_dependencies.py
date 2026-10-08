import hashlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def audit(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    import verify_cliffy_public_dependencies
    return verify_cliffy_public_dependencies


def test_checksum_and_size_are_both_required(audit):
    data = b"public source"
    metadata = {"size": len(data), "checksum": "sha256-" + hashlib.sha256(data).hexdigest()}
    assert audit.checked_file(data, metadata) == hashlib.sha256(data).hexdigest()
    with pytest.raises(ValueError, match="mismatch"):
        audit.checked_file(data + b"!", metadata)
    with pytest.raises(ValueError, match="mismatch"):
        audit.checked_file(data, {**metadata, "size": 1})


@pytest.mark.parametrize("path", ["../x", "/../x", "/x/./y", "/x%2fy", "/x?y", "/x\\y", "//x"])
def test_manifest_paths_cannot_escape_registry(audit, path):
    with pytest.raises(ValueError):
        audit.source_url("@std/io", "0.225.3", path)


def test_audit_preserves_external_graph_boundary(audit, monkeypatch, tmp_path):
    data = b"source"
    metadata = {"manifest": {"/mod.ts": {
        "size": len(data), "checksum": "sha256-" + hashlib.sha256(data).hexdigest(),
    }}, "moduleGraph2": {"/mod.ts": {"dependencies": [{"specifier": "jsr:@std/assert@^1.0.0"}]}}}
    def get(url):
        if url.endswith("/meta.json"):
            return json.dumps({"versions": {"0.225.3": {}}}).encode()
        if url.endswith("_meta.json"):
            return json.dumps(metadata).encode()
        return data
    monkeypatch.setattr(audit, "download", get)
    result = audit.audit("@std/io", "0.225.3", tmp_path)
    assert result["status"] == "verified"
    assert result["verified_files"] == 1
    assert result["external_specifiers"] == ["jsr:@std/assert@^1.0.0"]
    assert result["version_metadata"]["checksum_kind"] == "locally_measured_metadata_pin"


def test_yanked_version_is_not_accepted(audit, monkeypatch, tmp_path):
    monkeypatch.setattr(audit, "download", lambda url: b'{"versions":{"0.225.3":{"yanked":true}}}')
    with pytest.raises(ValueError, match="yanked"):
        audit.audit("@std/io", "0.225.3", tmp_path)


def test_pin_assembly_rechecks_saved_artifacts(audit, monkeypatch, tmp_path):
    output = tmp_path / "output"
    package_dir = output / "std--io/0.225.3"
    source = b"public source"
    metadata = {"manifest": {"/mod.ts": {
        "size": len(source), "checksum": "sha256-" + hashlib.sha256(source).hexdigest(),
    }}}
    def get(url):
        if url.endswith("/meta.json"):
            return b'{"versions":{"0.225.3":{}}}'
        if url.endswith("_meta.json"):
            return json.dumps(metadata).encode()
        return source
    monkeypatch.setattr(audit, "download", get)
    record = audit.audit("@std/io", "0.225.3", package_dir)
    for name, records in (("verification.json", [record]),
                          ("transitive-verification.json", []),
                          ("preserved-cache-verification.json", [])):
        (output / name).write_text(json.dumps({"records": records}))
    monkeypatch.setattr(audit, "ROOT", tmp_path / "repo")
    monkeypatch.setattr(audit, "PINS", {"@std/io": "0.225.3"})
    monkeypatch.setattr(audit, "TRANSITIVE_PINS", ())
    monkeypatch.setattr(audit, "PRESERVED_CACHE_PINS", ())
    result = audit.assemble_manifest(output)
    assert result["verified_files"] == 1
    assert not result["deno_compatibility_verified"]
    assert not result["full_dependency_graph_verified"]
    Path(record["files"][0]["artifact"]).write_bytes(b"changed")
    with pytest.raises(ValueError, match="mismatch"):
        audit.assemble_manifest(output)
