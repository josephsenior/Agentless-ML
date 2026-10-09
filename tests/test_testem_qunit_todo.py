"""Host-only contracts; no Docker or benchmark execution."""

import hashlib
import json
import runpy
import shutil
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import testem_qunit_todo as todo
import diagnose_testem_firefox as diagnostic
import run_testem_qunit_public_test as public
sys.path.pop(0)


def test_four_exact_routes_without_changing_legacy(tmp_path):
    source = ROOT / 'experiments/deepswe/testem'
    shutil.copyfile(source / 'offline-qunit.py', tmp_path / 'offline-qunit-base.py')
    shutil.copyfile(source / 'offline-qunit-todo.py', tmp_path / 'offline-qunit.py')
    module = runpy.run_path(str(tmp_path / 'offline-qunit.py'))
    legacy = runpy.run_path(str(source / 'offline-qunit.py'))
    assert len(legacy['PINS']) == 2
    assert len(module['PINS']) == 4
    for suffix in ('js', 'css'):
        route = '/qunit/qunit-2.9.2.' + suffix
        assert module['allowed_request']('code.jquery.com', route)
        assert not module['allowed_request']('code.jquery.com', route + '?x=1')
        assert not module['allowed_request']('other.invalid', route)
    with pytest.raises(FileNotFoundError):
        module['load_assets'](tmp_path)


def test_staging_rehashes_assets_and_rejects_tampering(tmp_path):
    capture = tmp_path / 'capture'; capture.mkdir()
    context = tmp_path / 'context'; context.mkdir()
    records = []
    for suffix in ('js', 'css'):
        name = 'qunit-2.9.2.' + suffix
        data = suffix.encode()
        (capture / name).write_bytes(data)
        records.append({'exact_byte_match': True, 'cdn': {'file': name,
            'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}})
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps({'assets': records}))
    with patch.object(todo, 'MANIFEST', manifest), patch.object(todo, 'CAPTURE', capture):
        todo.stage(context)
        assert (context / 'offline-qunit-base.py').is_file()
        (capture / 'qunit-2.9.2.js').write_bytes(b'altered')
        with pytest.raises(ValueError):
            todo.stage(context)


def test_todo_command_preserves_original_contract():
    with patch.object(diagnostic, 'TEST', todo.TEST):
        original = diagnostic.diagnostic_command('home-only')
        wrapped = public.selected_command()
    assert original.argv[-1] == todo.TEST
    assert original.argv[-3:-1] == ('tests/ci/ci_tests.js', '--grep')
    assert repr(list(original.argv)) in wrapped.argv[2]
    assert wrapped.timeout_seconds == original.timeout_seconds == 1800
    assert wrapped.report == original.report
    assert wrapped.failure_exit_codes == original.failure_exit_codes
    assert 125 not in wrapped.failure_exit_codes
    compile(wrapped.argv[2], '<todo-supervisor>', 'exec')


def test_full_command_uses_both_unchanged_globs_without_observer():
    full = public.selected_command(full=True)
    original = public.full_public_command()
    assert original.argv[3:] == ('deepswe-tests', 'tests/*_tests.js', 'tests/**/*_tests.js')
    assert repr(list(original.argv[3:]))[1:-1] in full.argv[2]
    assert original.argv[2] in full.argv[2]
    assert '--grep' not in full.argv[2]
    assert '--require' not in full.argv[2]
    assert 'firefox-observer' not in full.argv[2]
    assert full.timeout_seconds == original.timeout_seconds == 1800
    assert full.report == original.report
    assert full.failure_exit_codes == original.failure_exit_codes
    compile(full.argv[2], '<full-supervisor>', 'exec')


def test_full_action_checks_the_successful_todo_record(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['testem_qunit_todo.py', 'full'])
    # Restore every shared module setting after the dispatch-only check.
    with patch.object(diagnostic, 'TEST'), patch.object(public, 'TEST'), \
            patch.object(public, 'RESULTS'), patch.object(public, 'IMAGE'), \
            patch.object(public, 'PRIOR_SINGLE'), patch.object(public, 'main') as run:
        assert todo.main() == 0
        run.assert_called_once_with()
        assert sys.argv == ['testem_qunit_todo.py', '--full']
        assert public.IMAGE == todo.IMAGE
        assert public.PRIOR_SINGLE.name == 'testem_qunit_todo_public_test_2026_10_10.json'
