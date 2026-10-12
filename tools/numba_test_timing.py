"""Diagnostic-only timing around Numba's native spawned worker invocation."""

TIMING_HELPER = r'''
import json
import os
import time
from pathlib import Path
from numba.testing.main import _MinimalRunner as NativeMinimalRunner

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
