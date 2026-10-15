"""Bound one Docker pull by elapsed wall time, with a durable progress journal.

Sleep counts toward the deadline. A sleeping host cannot terminate a process;
the first short wait after resume notices expiration and stops only its client.
"""
from datetime import UTC, datetime
import json
from pathlib import Path
import re
import subprocess
import time


def run_pull(reference, output, *, timeout_seconds=1200, wall_clock=None, monotonic_clock=None):
    if timeout_seconds <= 0:
        raise ValueError('pull timeout must be positive')
    wall_clock = wall_clock or time.time
    monotonic_clock = monotonic_clock or time.monotonic
    output = Path(output)
    started_wall, started_mono = wall_clock(), monotonic_clock()
    process = None
    offsets = {'stdout': 0, 'stderr': 0}
    partial = {'stdout': b'', 'stderr': b''}
    argv = ['docker', 'pull', '--platform=linux/amd64', reference]
    record = dict(reference=reference, timeout_seconds=timeout_seconds,
                  deadline_utc=datetime.fromtimestamp(started_wall + timeout_seconds, UTC).isoformat(),
                  sleep_counts_toward_deadline=True, poll_interval_seconds=1,
                  progress_scope='CLI layer states and log bytes, not transferred blob bytes')

    def elapsed():
        # The monotonic guard also prevents a backward wall-clock adjustment
        # from extending an otherwise expired run.
        return max(0, wall_clock() - started_wall, monotonic_clock() - started_mono)

    with (output / 'pull.progress.jsonl').open('x', encoding='utf-8') as journal:
        def emit(event, **fields):
            entry = dict(event=event, observed_at=datetime.now(UTC).isoformat(), elapsed_seconds=elapsed())
            entry.update(fields)
            journal.write(json.dumps(entry) + '\n')
            journal.flush()

        def progress():
            for stream in offsets:
                with (output / ('pull.' + stream + '.log')).open('rb') as reader:
                    reader.seek(offsets[stream])
                    chunk = reader.read(1024 * 1024)
                offsets[stream] += len(chunk)
                if not chunk:
                    continue
                lines = (partial[stream] + chunk).split(b'\n')
                partial[stream] = lines.pop()[-4096:]
                emit('log_growth', stream=stream, log_bytes_observed=offsets[stream])
                for line in lines:
                    match = re.match(rb'^([0-9a-f]{12}): (Already exists|Pulling fs layer|Waiting|Downloading|Download complete|Extracting|Pull complete|Verifying Checksum)', line.strip())
                    if match:
                        emit('layer_state', layer=match[1].decode(), state=match[2].decode())

        try:
            with (output / 'pull.stdout.log').open('xb') as stdout, (output / 'pull.stderr.log').open('xb') as stderr:
                process = subprocess.Popen(argv, stdout=stdout, stderr=stderr)
                emit('started', pid=process.pid, **record)
                next_heartbeat = 0
                while True:
                    current = elapsed()
                    progress()
                    if current >= timeout_seconds:
                        record['status'] = 'wall_clock_timeout'
                        emit('deadline_expired')
                        if process.poll() is None:
                            process.kill()
                        process.wait(timeout=10)
                        raise subprocess.TimeoutExpired(argv, timeout_seconds)
                    code = process.poll()
                    if code is not None:
                        record['status'] = 'pass' if code == 0 else 'pull_failed'
                        if code:
                            raise subprocess.CalledProcessError(code, argv)
                        return record
                    if current >= next_heartbeat:
                        emit('heartbeat', remaining_seconds=max(0, timeout_seconds - current),
                             stdout_log_bytes=offsets['stdout'], stderr_log_bytes=offsets['stderr'])
                        next_heartbeat = current + 5
                    try:
                        process.wait(timeout=min(1, timeout_seconds - current))
                    except subprocess.TimeoutExpired:
                        pass
        except BaseException:
            record.setdefault('status', 'interrupted_or_start_failed')
            if process is not None and process.poll() is None:
                process.kill()
                process.wait(timeout=10)
            raise
        finally:
            record['elapsed_seconds'] = elapsed()
            record['returncode'] = None if process is None else process.poll()
            record['log_bytes_observed'] = offsets
            emit('finished', **record)
            (output / 'pull.status.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
