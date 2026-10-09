import importlib.util
from pathlib import Path

import pytest


def verifier():
    path = Path(__file__).resolve().parents[1] / 'tools/verify_testem_qunit_assets.py'
    spec = importlib.util.spec_from_file_location('testem_qunit_verifier', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_exact_byte_and_publisher_sri_checks():
    module = verifier()
    assert module.verify_asset(b'abc', b'abc', sri='sha256-ungWv48Bz+pBQUDeXa4iI7ADYaOWF3qctBD/YfIAFa0=')
    with pytest.raises(ValueError, match='CDN bytes differ'):
        module.verify_asset(b'abc', b'abd')
    with pytest.raises(ValueError, match='Publisher SRI mismatch'):
        module.verify_asset(b'abc', b'abc', sri='sha256-wrong')


def test_publisher_links_retain_exact_url_and_duplicate_sri():
    module = verifier()
    links = module.Links()
    links.feed('<a href="https://code.jquery.com/qunit/qunit-1.20.0.js" data-hash="sha256-one"></a>'
               '<a href="https://code.jquery.com/qunit/qunit-1.20.0.js" data-hash="sha256-two"></a>')
    assert links.links['https://code.jquery.com/qunit/qunit-1.20.0.js'] == ['sha256-one', 'sha256-two']


def test_committed_manifest_pins_exact_assets_and_does_not_claim_test_result():
    import json
    root = Path(__file__).resolve().parents[1]
    record = json.loads((root / 'experiments/deepswe/testem_qunit_assets_verified_2026_10_09.json').read_text())
    assert record['upstream_commit'] == verifier().COMMIT
    assert [item['cdn']['sha256'] for item in record['assets']] == [
        '576c7117981fae223d412e94e53a176c124f5e3a4dc321b9d56d58ae680015c0',
        '98abc5dc3d67eb3a1f50eb861c7f888a9a5b43edaa8f29689c50d1841fb915fb']
    assert [item['cdn']['bytes'] for item in record['assets']] == [112454, 5349]
    assert all(item['exact_byte_match'] for item in record['assets'])
    assert record['assets'][0]['publisher_sri_verified'] is True
    assert record['assets'][1]['publisher_sri_verified'] is False
    assert record['benchmark_tests_run'] is False
    assert record['service_started'] is False
    assert record['image_built'] is False
