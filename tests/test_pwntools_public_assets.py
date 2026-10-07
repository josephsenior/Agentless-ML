"""Local safety/integrity checks; no network calls or downloaded code execution."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('public_assets', ROOT / 'tools/verify_pwntools_public_assets.py')
assets = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assets)


@pytest.mark.parametrize('url', ['http://libc.rip/download/x', 'https://localhost/x',
    'https://libc.rip.attacker.example/x', 'https://user:secret@libc.rip/x',
    'https://libc.rip:8443/x', 'file:///tmp/x'])
def test_fetch_origins_are_fail_closed(url):
    with pytest.raises(ValueError):
        assets.validate_url(url)


def test_known_public_https_origin_and_hashes():
    assets.validate_url('https://libc.rip/download/library.so')
    assert assets.hashes(b'abc')['sha256'] == 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'


def test_only_ar_data_member_is_returned():
    def member(name, data):
        header = f'{name + "/":<16}{0:<12}{0:<6}{0:<6}{0:<8}{len(data):<10}`\n'.encode()
        assert len(header) == 60
        return header + data + (b'\n' if len(data) % 2 else b'')
    archive = b'!<arch>\n' + member('debian-binary', b'2.0\n') + member('data.tar.xz', b'payload')
    assert assets.deb_data(archive) == b'payload'
    with pytest.raises(ValueError):
        assets.deb_data(archive[:-2])


def test_non_elf_bytes_are_rejected_before_any_docker_call():
    with pytest.raises(ValueError, match='Not an ELF'):
        assets.inspect_elf(b'<html>not a library</html>')
