"""Diagnostic-only timing around Numba's native spawned worker invocation."""

TIMING_HELPER = r'''
import json
import os
import time
import contextlib
import weakref
from pathlib import Path
from numba.testing.main import _MinimalRunner as NativeMinimalRunner

dispatchers = weakref.WeakKeyDictionary()
next_dispatcher = 0

def compilation_listener(stream, common):
    from numba.core import event as ev
    class Listener(ev.Listener):
        def __init__(self):
            self.pending = {}
            self.sequence = 0

        def on_start(self, event):
            global next_dispatcher
            data = event.data
            dispatcher = data['dispatcher']
            if dispatcher not in dispatchers:
                next_dispatcher += 1
                dispatchers[dispatcher] = next_dispatcher
            function = dispatcher.py_func
            code = function.__code__
            self.sequence += 1
            details = dict(common, compile_id=self.sequence,
                           dispatcher_id=dispatchers[dispatcher],
                           function=dict(module=function.__module__, name=function.__qualname__,
                                         filename=code.co_filename, line=code.co_firstlineno),
                           closure=[repr(cell.cell_contents) for cell in (function.__closure__ or ())],
                           signature=[str(arg) for arg in data['args']],
                           return_type=str(data['return_type']),
                           target_options=repr(sorted(dispatcher.targetoptions.items())),
                           at_ns=time.monotonic_ns())
            self.pending[id(data)] = details
            stream.write(json.dumps(dict(details, event='compile_start')) + '\n')

        def on_end(self, event):
            details = self.pending.pop(id(event.data))
            ended = time.monotonic_ns()
            # The pinned Event.is_failed implementation is not trustworthy.
            # Check actual overload registration, not a guessed success flag.
            registered = tuple(event.data['args']) in event.data['dispatcher'].overloads
            stream.write(json.dumps(dict(details, event='compile_finish', at_ns=ended,
                                         seconds=(ended-details['at_ns'])/1e9,
                                         overload_registered=registered)) + '\n')
    return ev.install_listener('numba:compile', Listener())

class TimedMinimalRunner(NativeMinimalRunner):
    def __call__(self, test):
        directory = Path('/tmp/numba-test-timings')
        directory.mkdir(exist_ok=True)
        # One file per worker; flush the start before entering native code so
        # a killed invocation remains visible. No test outcomes are inferred.
        with (directory / ('%s.jsonl' % os.getpid())).open('a', buffering=1) as stream:
            started = time.monotonic_ns()
            common = dict(pid=os.getpid(), test_id=test.id(), started_ns=started)
            stream.write(json.dumps(dict(common, event='start', at_ns=started)) + '\n')
            try:
                with contextlib.ExitStack() as scope:
                    if os.environ.get('AGENTLESS_NUMBA_COMPILE_TIMING') == '1':
                        scope.enter_context(compilation_listener(stream, common))
                    return super().__call__(test)
            finally:
                ended = time.monotonic_ns()
                stream.write(json.dumps(dict(common, event='finish', at_ns=ended,
                                             seconds=(ended-started)/1e9)) + '\n')

def install():
    import numba.testing.main as native
    native._MinimalRunner = TimedMinimalRunner
'''.strip()

# Run inside the container before its scratch volume is removed. A byte cap
# makes accidental runaway instrumentation an explicit error, not truncation.
COLLECT_TIMINGS = r'''
import json
import time
from pathlib import Path
events = []
total = 0
for path in sorted(Path('/tmp/numba-test-timings').glob('*.jsonl')):
    data = path.read_bytes()
    total += len(data)
    if total > 8 * 1024 * 1024:
        raise RuntimeError('timing journal exceeds diagnostic capture limit')
    for line in data.splitlines():
        events.append(json.loads(line))
print(json.dumps(dict(captured_ns=time.monotonic_ns(), events=events)))
'''.strip()


def summarize_timings(snapshot):
    """Invocation completion is not a passing-test or regression inventory."""
    starts = {}
    finished = []
    for event in snapshot['events']:
        if event['event'].startswith('compile_'):
            continue
        key = (event['pid'], event['test_id'], event['started_ns'])
        if event['event'] == 'start':
            if key in starts:
                raise ValueError('duplicate timing start')
            starts[key] = event
        elif event['event'] == 'finish':
            if key not in starts:
                raise ValueError('timing finish without start')
            starts.pop(key)
            finished.append(dict(test_id=event['test_id'], pid=event['pid'],
                                 seconds=event['seconds']))
        else:
            raise ValueError('unknown timing event')
    unfinished = [dict(test_id=event['test_id'], pid=event['pid'],
                       observed_seconds=(snapshot['captured_ns']-event['started_ns'])/1e9)
                  for event in starts.values()]
    return dict(scope='native parallel worker invocations, including worker cleanup',
                finished_invocations=len(finished), unfinished_invocations=unfinished,
                slowest_finished=sorted(finished, key=lambda row: row['seconds'], reverse=True)[:20],
                accepted_regression_inventory=False)


def summarize_compilations(snapshot):
    """Keep exact dispatcher repeats separate from source-level similarities."""
    import json
    starts = {}
    finished = []
    for event in snapshot['events']:
        key = (event['pid'], event['started_ns'], event.get('compile_id'))
        if event['event'] == 'compile_start':
            if key in starts:
                raise ValueError('duplicate compilation start')
            starts[key] = event
        elif event['event'] == 'compile_finish':
            if key not in starts:
                raise ValueError('compilation finish without start')
            start = starts.pop(key)
            finished.append(dict(event, compile_started_ns=start['at_ns']))
    exact = {}
    source = {}
    tests = {}
    for event in finished:
        signature = (tuple(event['signature']), event['return_type'], event['target_options'])
        exact_key = (event['pid'], event['dispatcher_id'], signature)
        exact.setdefault(exact_key, []).append(event)
        # Similar source is NOT proof of equivalent dispatchers or closures.
        source_key = (json.dumps(event['function'], sort_keys=True), signature)
        source.setdefault(source_key, []).append(event)
        test_key = (event['pid'], event['test_id'], event['started_ns'])
        tests.setdefault(test_key, []).append(event)
    per_test = []
    for (pid, test_id, started_ns), events in tests.items():
        intervals = sorted((e['compile_started_ns'], e['at_ns']) for e in events)
        total_ns = 0
        end = -1
        for begin, stop in intervals:
            total_ns += max(0, stop-max(begin, end))
            end = max(end, stop)
        per_test.append(dict(pid=pid, test_id=test_id, started_ns=started_ns,
                             completed_compile_events=len(events),
                             registered_overloads=sum(e['overload_registered'] for e in events),
                             compile_union_seconds=total_ns/1e9))
    def repeated_group(events):
        return dict(function=events[0]['function'], signature=events[0]['signature'],
                    return_type=events[0]['return_type'], target_options=events[0]['target_options'],
                    attempts=len(events), registered=sum(e['overload_registered'] for e in events),
                    workers=sorted({e['pid'] for e in events}),
                    dispatchers=len({(e['pid'], e['dispatcher_id']) for e in events}),
                    tests=sorted({e['test_id'] for e in events}),
                    inclusive_seconds=sum(e['seconds'] for e in events))
    repeats = [events for events in exact.values() if len(events) > 1]
    return dict(label='compilation_diagnostic_only_not_baseline',
                completed_compile_events=len(finished), unfinished_compile_events=list(starts.values()),
                registered_overloads=sum(e['overload_registered'] for e in finished),
                distinct_dispatcher_signatures=len(exact),
                same_dispatcher_signature_repeats=[repeated_group(e) for e in repeats],
                repeats_after_registered_overload=sum(
                    sum(any(previous['overload_registered'] for previous in events[:i])
                        for i in range(1, len(events))) for events in repeats),
                source_signature_recurrences=sorted(
                    [repeated_group(e) for e in source.values()
                     if len({(v['pid'], v['dispatcher_id']) for v in e}) > 1],
                    key=lambda row: row['inclusive_seconds'], reverse=True),
                per_test=sorted(per_test, key=lambda row: row['compile_union_seconds'], reverse=True),
                limitations='Only dispatcher compile events during worker invocations; '
                            'excludes imports, direct compiler pipelines and cache hits. '
                            'Signatures use rendered type names, which can conflate distinct types. '
                            'Source-level recurrences do not establish semantic equivalence. '
                            'Nested inclusive durations overlap; per-test unions do not.',
                accepted_regression_inventory=False)
