import importlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def module(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'tools'))
    return importlib.import_module('run_teleport_cached_parser_smoke')


def events(module):
    return [dict(Action=action, Package=module.PACKAGE, **({'Test': name} if name else {}))
            for action, name in [('start', None), ('run', module.TEST), ('pass', module.TEST), ('pass', None)]]


def encode(items):
    return ('\n'.join(json.dumps(item) for item in items) + '\n').encode()


def test_command_preserves_flags_one_test_and_default_cache_size(module):
    command = module.smoke_command()
    assert command.timeout_seconds == 180
    assert '-race -shuffle=on -cover -covermode=atomic' in command.argv[2]
    assert "-run '^TestCachedParser$' ./lib/utils/typical" in command.argv[2]
    assert 'unset TELEPORT_EXPRESSION_CACHE_SIZE' in command.argv[2]
    assert 'GOCACHE=/tmp/teleport-go-build' in command.argv[2]
    assert 'GOPROXY=off GOTOOLCHAIN=local GOMAXPROCS=1 GOFLAGS=-mod=readonly' in command.argv[2]
    assert './...' not in command.argv[2] and 'go mod download' not in command.argv[2]
    assert 'outcome=$?' in command.argv[2] and 'exit "$outcome"' in command.argv[2]


def test_requires_complete_named_test_and_package_pass(module):
    assert module.verify_events(encode(events(module)))


@pytest.mark.parametrize('problem', ['no_test', 'no_package', 'skip', 'fail', 'extra_test',
                                   'wrong_package', 'duplicate', 'after_completion', 'pass_without_run'])
def test_misleading_or_incomplete_events_rejected(module, problem):
    items = events(module)
    if problem == 'no_test':
        items = [items[0], items[-1]]
    elif problem == 'no_package':
        items.pop()
    elif problem in ('skip', 'fail'):
        items[2]['Action'] = problem
    elif problem == 'extra_test':
        items[1]['Test'] = 'TestParser'
    elif problem == 'wrong_package':
        items[0]['Package'] = 'other'
    elif problem == 'duplicate':
        items.insert(2, items[1])
    elif problem == 'after_completion':
        items.append(items[-1])
    elif problem == 'pass_without_run':
        del items[1]
    assert not module.verify_events(encode(items))


@pytest.mark.parametrize('raw', [None, b'', b'{}\n', b'not json', b'[]\n', b'\xff'])
def test_malformed_reports_rejected(module, raw):
    assert not module.verify_events(raw)
