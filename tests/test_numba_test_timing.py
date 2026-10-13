"""Timing survives spawned workers and does not reinterpret their outcomes."""

import json
import os
import subprocess
import sys
from pathlib import Path


def load_helper(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'tools'))
    import numba_test_timing
    return numba_test_timing


def test_spawned_native_calls_are_timed_even_when_they_raise(tmp_path, monkeypatch):
    helper = load_helper(monkeypatch)
    package = tmp_path / 'numba/testing'
    package.mkdir(parents=True)
    (package.parent / '__init__.py').write_text('')
    (package / '__init__.py').write_text('')
    core = tmp_path / 'numba/core'
    core.mkdir()
    (core / '__init__.py').write_text('')
    (core / 'event.py').write_text('''
from contextlib import contextmanager
listeners = []
class Listener: pass
@contextmanager
def install_listener(kind, listener):
    assert kind == 'numba:compile'
    listeners.append(listener)
    try: yield listener
    finally: listeners.remove(listener)
''')
    (package / 'main.py').write_text('''
from types import SimpleNamespace
from numba.core import event
def function(x): return x
class _MinimalRunner:
    def __call__(self, test):
        # Weak-key registry needs native-like hashable dispatcher identities.
        class Dispatcher:
            py_func = staticmethod(function)
            targetoptions = {}
            def __init__(self): self.overloads = {}
        dispatcher = Dispatcher()
        data = dict(dispatcher=dispatcher, args=('int64',), return_type=None)
        for listener in event.listeners: listener.on_start(SimpleNamespace(data=data))
        try:
            if test.id() == 'raises':
                raise ValueError('native error unchanged')
            dispatcher.overloads[('int64',)] = object()
            return ('native result', test.id())
        finally:
            for listener in event.listeners: listener.on_end(SimpleNamespace(data=data))
''')
    journal = tmp_path / 'timings'
    source = helper.TIMING_HELPER.replace("'/tmp/numba-test-timings'", repr(str(journal)))
    (tmp_path / 'numba_diagnostic_timing.py').write_text(source)
    script = tmp_path / 'probe.py'
    script.write_text('''
import multiprocessing
import numba_diagnostic_timing
class Case:
    def __init__(self, name): self.name = name
    def id(self): return self.name
def invoke(name):
    from numba.testing.main import _MinimalRunner
    try:
        return _MinimalRunner()(Case(name))
    except ValueError as error:
        return str(error)
if __name__ == '__main__':
    numba_diagnostic_timing.install()
    from numba.testing.main import _MinimalRunner
    with multiprocessing.get_context('spawn').Pool(2) as pool:
        runner = _MinimalRunner()
        assert pool.apply(runner, (Case('ok'),)) == ('native result', 'ok')
        try:
            pool.apply(runner, (Case('raises'),))
        except ValueError as error:
            assert str(error) == 'native error unchanged'
        else:
            raise AssertionError('lost native error')
''')
    result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True,
                            timeout=30, env=dict(os.environ, AGENTLESS_NUMBA_COMPILE_TIMING='1'))
    assert result.returncode == 0, result.stderr
    events = [json.loads(line) for path in journal.glob('*.jsonl')
              for line in path.read_text().splitlines()]
    assert len(events) == 8
    assert {e['test_id'] for e in events} == {'ok', 'raises'}
    summary = helper.summarize_timings({'events': events, 'captured_ns': max(e['at_ns'] for e in events)})
    assert summary['finished_invocations'] == 2
    assert not summary['unfinished_invocations']
    assert all(e['seconds'] >= 0 for e in summary['slowest_finished'])
    assert summary['accepted_regression_inventory'] is False
    compilations = helper.summarize_compilations({'events': events})
    assert compilations['completed_compile_events'] == 2
    assert compilations['registered_overloads'] == 1


def test_unfinished_start_is_not_counted_as_finished(monkeypatch):
    helper = load_helper(monkeypatch)
    start = dict(pid=42, test_id='slow.test', started_ns=10, at_ns=10, event='start')
    summary = helper.summarize_timings({'events': [start], 'captured_ns': 2_000_000_010})
    assert summary['finished_invocations'] == 0
    assert summary['unfinished_invocations'] == [dict(test_id='slow.test', pid=42, observed_seconds=2)]


def test_killed_worker_leaves_a_readable_start(tmp_path, monkeypatch):
    import time
    helper = load_helper(monkeypatch)
    package = tmp_path / 'numba/testing'
    package.mkdir(parents=True)
    (package.parent / '__init__.py').write_text('')
    (package / '__init__.py').write_text('')
    (package / 'main.py').write_text('''
class _MinimalRunner:
    def __call__(self, test):
        import time
        time.sleep(30)
''')
    journal = tmp_path / 'timings'
    (tmp_path / 'numba_diagnostic_timing.py').write_text(
        helper.TIMING_HELPER.replace("'/tmp/numba-test-timings'", repr(str(journal))),
    )
    script = tmp_path / 'blocked.py'
    script.write_text('''
from numba_diagnostic_timing import TimedMinimalRunner
class Case:
    def id(self): return 'interrupted.test'
TimedMinimalRunner()(Case())
''')
    process = subprocess.Popen([sys.executable, str(script)])
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            paths = list(journal.glob('*.jsonl'))
            if paths and paths[0].stat().st_size:
                break
            time.sleep(0.01)
        else:
            raise AssertionError('worker did not flush its start')
    finally:
        process.terminate()
        process.wait(timeout=10)
    events = [json.loads(line) for line in paths[0].read_text().splitlines()]
    assert len(events) == 1 and events[0]['event'] == 'start'
    assert events[0]['test_id'] == 'interrupted.test'


def test_capture_precedes_container_removal(tmp_path, monkeypatch):
    load_helper(monkeypatch)
    import threading
    from types import SimpleNamespace
    from run_numba_resource_diagnostic import SampledRunner
    from agentless_ml.validation import DockerTestRunner
    runner = SampledRunner.__new__(SampledRunner)
    runner.artifact_root = tmp_path
    runner.stop_sampling = threading.Event()
    runner.sampler = None
    (tmp_path / 'container').mkdir()
    calls = []
    def docker(self, *args, **kwargs):
        calls.append(args[0])
        return SimpleNamespace(returncode=0, stdout=b'{"captured_ns": 1, "events": []}', stderr=b'')
    monkeypatch.setattr(DockerTestRunner, '_docker', docker)
    runner._docker('rm', '--force', '--volumes', 'container')
    assert calls == ['exec', 'rm']
    assert json.loads((tmp_path / 'container/test-timings.json').read_text())['events'] == []


def test_failed_capture_still_removes_container(tmp_path, monkeypatch):
    load_helper(monkeypatch)
    import threading
    from run_numba_resource_diagnostic import SampledRunner
    from agentless_ml.validation import DockerTestRunner
    runner = SampledRunner.__new__(SampledRunner)
    runner.artifact_root = tmp_path
    runner.stop_sampling = threading.Event()
    runner.sampler = None
    (tmp_path / 'container').mkdir()
    calls = []
    def docker(self, *args, **kwargs):
        calls.append(args[0])
        if args[0] == 'exec':
            raise OSError('capture unavailable')
    monkeypatch.setattr(DockerTestRunner, '_docker', docker)
    runner._docker('rm', '--force', '--volumes', 'container')
    assert calls == ['exec', 'rm']
    summary = json.loads((tmp_path / 'container/test-timing-summary.json').read_text())
    assert summary['capture_error'] == 'capture unavailable'


def test_compilation_summary_distinguishes_repeats_and_unions_nested_time(monkeypatch):
    helper = load_helper(monkeypatch)
    events = []
    def compile_pair(number, dispatcher, signature, begin, end, registered=True, pid=1):
        common = dict(pid=pid, test_id='test', started_ns=0, compile_id=number,
                      dispatcher_id=dispatcher, signature=[signature], return_type='None',
                      target_options='[]', function=dict(module='m', name='f', filename='f.py', line=1))
        events.append(dict(common, event='compile_start', at_ns=begin))
        events.append(dict(common, event='compile_finish', at_ns=end,
                           seconds=(end-begin)/1e9, overload_registered=registered))
    compile_pair(1, 1, 'int64', 0, 10_000_000_000)
    compile_pair(2, 2, 'float64', 2_000_000_000, 4_000_000_000)
    compile_pair(3, 1, 'int64', 11_000_000_000, 12_000_000_000)
    compile_pair(4, 1, 'float64', 13_000_000_000, 14_000_000_000)
    compile_pair(5, 3, 'int64', 15_000_000_000, 16_000_000_000, registered=False)
    compile_pair(6, 3, 'int64', 17_000_000_000, 18_000_000_000)
    compile_pair(1, 1, 'int64', 19_000_000_000, 20_000_000_000, pid=2)
    unfinished = dict(events[0], compile_id=7, at_ns=21_000_000_000)
    events.append(unfinished)
    summary = helper.summarize_compilations({'events': events})
    assert summary['completed_compile_events'] == 7
    assert summary['distinct_dispatcher_signatures'] == 5
    assert len(summary['same_dispatcher_signature_repeats']) == 2
    assert summary['repeats_after_registered_overload'] == 1
    assert summary['unfinished_compile_events'] == [unfinished]
    assert summary['per_test'][0]['compile_union_seconds'] == 14
    int_recurrence = next(r for r in summary['source_signature_recurrences'] if r['signature'] == ['int64'])
    assert int_recurrence['dispatchers'] == 3
    assert int_recurrence['workers'] == [1, 2]
    assert summary['accepted_regression_inventory'] is False
