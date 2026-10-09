import hashlib
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def service():
    return runpy.run_path(str(ROOT / 'experiments/deepswe/testem/offline-qunit.py'))


def test_exact_host_and_route_allowlist():
    allowed = service()['allowed_request']
    assert allowed('code.jquery.com', '/qunit/qunit-1.20.0.js')
    assert allowed('code.jquery.com:80', '/qunit/qunit-1.20.0.css')
    assert not allowed('unexpected.invalid', '/qunit/qunit-1.20.0.js')
    assert not allowed('code.jquery.com', '/qunit/qunit-1.20.0.js?extra=1')
    assert not allowed('code.jquery.com', '/favicon.ico')
    assert not allowed('code.jquery.com', '/qunit/../qunit/qunit-1.20.0.js')


def test_asset_integrity_fails_closed():
    verify = service()['verify_bytes']
    verify(b'abc', 3, hashlib.sha256(b'abc').hexdigest())
    with pytest.raises(ValueError):
        verify(b'abd', 3, hashlib.sha256(b'abc').hexdigest())
    with pytest.raises(ValueError):
        verify(b'abc', 4, hashlib.sha256(b'abc').hexdigest())


def test_missing_assets_prevent_startup(tmp_path):
    with pytest.raises(FileNotFoundError):
        service()['load_assets'](tmp_path)
