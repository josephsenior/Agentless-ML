import hashlib
import importlib.util
import runpy
import sys
from pathlib import Path
from unittest.mock import patch

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


def test_public_wrapper_preserves_one_real_test_and_failure_codes():
    tools = ROOT / 'tools'
    sys.path.insert(0, str(tools))
    try:
        spec = importlib.util.spec_from_file_location('testem_asset_public', tools / 'run_testem_qunit_public_test.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        original = module.diagnostic_command('home-only')
        wrapped = module.selected_command()
        assert wrapped.timeout_seconds == original.timeout_seconds == 1800
        assert wrapped.failure_exit_codes == original.failure_exit_codes
        assert 125 not in wrapped.failure_exit_codes
        assert wrapped.report == original.report
        assert repr(list(original.argv)) in wrapped.argv[2]
        assert "test=subprocess.Popen(" in wrapped.argv[2]
        compile(wrapped.argv[2], '<supervisor>', 'exec')
        full = module.selected_command(full=True)
        public = module.full_public_command()
        full_script = full.argv[2]
        assert repr(list(public.argv[3:]))[1:-1] in full_script
        assert public.argv[2] in full_script
        assert '--grep' not in full_script
        assert '--require' not in full_script
        assert full.timeout_seconds == public.timeout_seconds == 1800
        assert full.report == public.report
        assert full.failure_exit_codes == public.failure_exit_codes
        assert 'export HOME=/tmp/testem-firefox-home' in full_script
        compile(full_script, '<full-supervisor>', 'exec')
        with patch.object(module.DockerTestRunner, '_docker') as docker:
            runner = object.__new__(module.OfflineAssetRunner)
            runner._docker('create', '--network=none', '--cap-drop=ALL')
            assert docker.call_args.args == ('create', '--add-host=code.jquery.com:127.0.0.1',
                                             '--network=none', '--cap-drop=ALL')
    finally:
        sys.path.pop(0)
