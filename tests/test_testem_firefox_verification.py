from pathlib import Path
import pytest


def test_exact_archive_checksum_entry(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    from verify_testem_firefox import matching_checksum
    name = "linux-x86_64/en-US/firefox-140.17.0esr.tar.xz"
    digest = "a" * 128
    assert matching_checksum(f"{digest}  {name}\n", name) == digest
    with pytest.raises(ValueError):
        matching_checksum(f"{digest}  other/{name}\n", name)
    with pytest.raises(ValueError):
        matching_checksum(f"{digest}  {name}\n{digest}  {name}\n", name)


def test_audit_downloads_without_installation(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    from verify_testem_firefox import APT_AUDIT, PRIMARY, SUBKEY
    assert "--simulate --no-install-recommends install" in APT_AUDIT
    assert "--download-only --yes --no-install-recommends install" in APT_AUDIT
    assert "--allow-unauthenticated" not in APT_AUDIT
    assert PRIMARY == "14F26682D0916CDD81E37B6D61B7B526D98F0353"
    assert SUBKEY == "827E658608679618CD349F93678E455D76767AA3"


def test_elf_audit_is_static(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    from verify_testem_firefox import ELF_AUDIT
    assert "['readelf','-d',str(p)]" in ELF_AUDIT
    assert "ldd" not in ELF_AUDIT
    assert "subprocess.run([str(p)" not in ELF_AUDIT
