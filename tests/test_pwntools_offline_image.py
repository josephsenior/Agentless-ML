"""Offline-image integrity checks, without Docker or network access."""

import hashlib
import importlib.util
import io
import tarfile
from pathlib import Path

import pytest


@pytest.fixture
def builder(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root / "tools"))
    spec = importlib.util.spec_from_file_location("offline_image", root / "tools/build_pwntools_offline_image.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pin_rejects_tampering_and_wrong_size(builder):
    pin = {"sha256": hashlib.sha256(b"real data").hexdigest(), "bytes": 9}
    assert builder.checked(b"real data", pin) == b"real data"
    with pytest.raises(ValueError, match="SHA256"):
        builder.checked(b"fake data", pin)
    with pytest.raises(ValueError, match="Size"):
        builder.checked(b"real data", {**pin, "bytes": 8})


def test_archive_reader_checks_member_hash_and_refuses_links(builder, monkeypatch):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        entry = tarfile.TarInfo("./lib/libc.so.6")
        entry.size = 4
        archive.addfile(entry, io.BytesIO(b"data"))
        link = tarfile.TarInfo("./lib/link")
        link.type = tarfile.SYMTYPE
        link.linkname = "/etc/passwd"
        archive.addfile(link)
    monkeypatch.setattr(builder, "deb_data", lambda _: buffer.getvalue())
    pin = {"name": "./lib/libc.so.6", "sha256": hashlib.sha256(b"data").hexdigest(), "bytes": 4}
    assert builder.member(b"package", pin) == b"data"
    with pytest.raises(ValueError, match="SHA256"):
        builder.member(b"package", {**pin, "sha256": "0" * 64})
    with pytest.raises(ValueError, match="regular"):
        builder.member(b"package", {**pin, "name": "./lib/link"})


def test_artifact_path_cannot_escape_its_evidence_directory(builder):
    with pytest.raises(ValueError, match="basename"):
        builder.downloaded({"artifact_base": "unused", "artifact": "../elsewhere"})


def test_generated_asset_paths_are_contained(builder):
    assert builder.basename("https://libc.rip/download/libc6_2.31-3_amd64.so") == "libc6_2.31-3_amd64.so"
    assert builder.build_id_path("a" * 40) == "a" * 40
    for url in ("https://libc.rip/..", "https://libc.rip/"):
        with pytest.raises(ValueError, match="filename"):
            builder.basename(url)
    with pytest.raises(ValueError, match="build ID"):
        builder.build_id_path("../../outside")


def test_image_and_bootstrap_preserve_diagnostic_boundary(builder):
    templates = builder.ROOT / "experiments/deepswe/pwntools"
    dockerfile = (templates / "Dockerfile.offline").read_text()
    bootstrap = (templates / "setup-offline-data.sh").read_text()
    assert "dpkg --install" in dockerfile
    assert "apt-get" not in dockerfile
    assert dockerfile.rstrip().endswith("USER travis")
    assert ". /opt/pwntools-setup-local-ssh-native.sh" in bootstrap
    assert "sha256sum --check --strict" in bootstrap
    assert "chmod -R u+w" in bootstrap
    assert "exit 125" in bootstrap
