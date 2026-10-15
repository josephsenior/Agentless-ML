import hashlib
import importlib
from pathlib import Path

import pytest

from agentless_ml.schemas import TestCaseResult, TestCaseStatus


@pytest.fixture
def modules(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'tools'))
    return (importlib.import_module('run_openlibrary_query_smoke'),
            importlib.import_module('verify_openlibrary_infogami'))


def manifest(verifier, content=b'public file'):
    blob = hashlib.sha1(b'blob ' + str(len(content)).encode() + b'\0' + content).hexdigest()
    return dict(commit=verifier.COMMIT, files=[dict(path='package/file.py', mode='100644', blob=blob)])


def test_verifies_every_blob_and_copies_no_image_extras(modules, tmp_path):
    _, verifier = modules
    source, target = tmp_path / 'image', tmp_path / 'workspace'
    (source / 'package').mkdir(parents=True)
    (source / 'package/file.py').write_bytes(b'public file')
    (source / 'extra.py').write_bytes(b'image extra')
    target.mkdir()  # git archive may create an empty submodule directory.
    result = verifier.verify_and_supply(manifest(verifier), source, target)
    assert result['files_verified'] == result['files_supplied'] == 1
    assert (target / 'package/file.py').read_bytes() == b'public file'
    assert not (target / 'extra.py').exists()


def test_mismatched_content_supplies_nothing(modules, tmp_path):
    _, verifier = modules
    source, target = tmp_path / 'image', tmp_path / 'workspace'
    (source / 'package').mkdir(parents=True)
    (source / 'package/file.py').write_bytes(b'changed')
    with pytest.raises(ValueError, match='differs'):
        verifier.verify_and_supply(manifest(verifier), source, target)
    assert not target.exists()


def test_later_mismatch_does_not_leave_partial_copy(modules, tmp_path):
    _, verifier = modules
    source, target = tmp_path / 'image', tmp_path / 'workspace'
    (source / 'package').mkdir(parents=True)
    (source / 'package/file.py').write_bytes(b'public file')
    (source / 'package/second.py').write_bytes(b'changed')
    pin = manifest(verifier)
    pin['files'].append({**pin['files'][0], 'path': 'package/second.py'})
    with pytest.raises(ValueError, match='differs'):
        verifier.verify_and_supply(pin, source, target)
    assert not target.exists()


@pytest.mark.parametrize('path', ['../escape', '/absolute', '.git/config', 'package\\file.py'])
def test_unsafe_manifest_paths_are_rejected(modules, tmp_path, path):
    _, verifier = modules
    pin = manifest(verifier)
    pin['files'][0]['path'] = path
    with pytest.raises(ValueError, match='unsafe'):
        verifier.verify_and_supply(pin, tmp_path, tmp_path / 'output')


def test_command_verifies_before_pytest_and_preserves_hooks(modules):
    wrapper, _ = modules
    command = wrapper.smoke_command()
    script = command.argv[2]
    assert command.timeout_seconds == 180
    assert script.index('python /tmp/agentless-setup/') < script.index('python -m pytest')
    assert 'python -m pytest ' + wrapper.TEST + ' --ignore=infogami --ignore=vendor --ignore=node_modules' in script
    assert '--noconftest' not in script and 'DISABLE_PLUGIN_AUTOLOAD' not in script
    assert 'pip install' not in script
    assert 'PYTHONPATH=/tmp/work:/tmp/work/vendor/infogami' in script
    assert command.report.path == '/tmp/openlibrary-query.xml'


def test_requires_exact_nine_individual_passes(modules):
    wrapper, _ = modules
    cases = tuple(TestCaseResult(name, TestCaseStatus.PASSED) for name in sorted(wrapper.EXPECTED))
    assert wrapper.verify_cases(cases)
    assert not wrapper.verify_cases(cases[:-1])
    assert not wrapper.verify_cases(cases + cases[:1])
    for status in (TestCaseStatus.SKIPPED, TestCaseStatus.FAILED, TestCaseStatus.ERROR):
        assert not wrapper.verify_cases((TestCaseResult(cases[0].test_id, status),) + cases[1:])
