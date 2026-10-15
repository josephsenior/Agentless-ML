import importlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def module(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'tools'))
    return importlib.import_module('run_flipt_release_smoke')


def events(m):
    def event(action, name=None):
        return dict(Action=action, Package=m.PACKAGE, **({'Test': name} if name else {}))
    result = [event('start'), event('run', 'TestIs')]
    for name in sorted(m.EXPECTED):
        result += [event('run', name), event('pass', name)]
    return result + [event('pass', 'TestIs'), event('pass')]


def encode(items):
    return ('\n'.join(json.dumps(item) for item in items) + '\n').encode()


def test_preserves_selection_race_coverage_and_limits(module):
    command = module.smoke_command()
    assert command.timeout_seconds == 180
    assert "-run '^TestIs$' ./internal/release" in command.argv[2]
    assert '-race -p 1 -coverprofile=/tmp/flipt-release-coverage.txt -covermode=atomic' in command.argv[2]
    assert 'GOPROXY=off GOTOOLCHAIN=local GOMAXPROCS=1 GOFLAGS=-mod=readonly' in command.argv[2]
    assert './...' not in command.argv[2] and 'go mod download' not in command.argv[2]
    assert 'outcome=$?' in command.argv[2] and 'exit "$outcome"' in command.argv[2]


def test_complete_native_children_parent_and_package_pass(module):
    assert module.verify_events(encode(events(module)))


@pytest.mark.parametrize('problem', ['missing_child', 'parent_only', 'missing_package', 'skip',
                                   'fail', 'unexpected_test', 'wrong_package', 'duplicate',
                                   'after_completion', 'pass_without_run'])
def test_incomplete_or_misleading_native_results_rejected(module, problem):
    items = events(module)
    if problem == 'missing_child':
        del items[2:4]
    elif problem == 'parent_only':
        items = items[:2] + items[-2:]
    elif problem == 'missing_package':
        items.pop()
    elif problem in ('skip', 'fail'):
        items[3]['Action'] = problem
    elif problem == 'unexpected_test':
        items[2]['Test'] = 'TestCheck'
    elif problem == 'wrong_package':
        items[0]['Package'] = 'other'
    elif problem == 'duplicate':
        items.insert(4, items[3])
    elif problem == 'after_completion':
        items.append(items[-1])
    elif problem == 'pass_without_run':
        del items[2]
    assert not module.verify_events(encode(items))


@pytest.mark.parametrize('raw', [None, b'', b'{}\n', b'not json', b'[]\n', b'\xff'])
def test_missing_or_malformed_reports_rejected(module, raw):
    assert not module.verify_events(raw)


def test_structured_test_name_rejected_without_exception(module):
    items = events(module)
    items[2]['Test'] = {'unexpected': 'object'}
    assert not module.verify_events(encode(items))
