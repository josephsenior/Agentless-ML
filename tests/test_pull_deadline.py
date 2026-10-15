import importlib
import json
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.fixture
def module(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'tools'))
    return importlib.import_module('pull_deadline')


def fake_process(module, monkeypatch, *, wall_jump=1, mono_jump=1, code=0, interrupt=False):
    clocks = dict(wall=1700000000., mono=100.)

    class Process:
        pid = 123
        result = None
        killed = False

        def poll(self):
            return self.result

        def kill(self):
            self.killed = True
            self.result = -9

        def wait(self, timeout):
            if self.result is not None:
                return self.result
            if interrupt:
                raise KeyboardInterrupt()
            clocks['wall'] += wall_jump
            clocks['mono'] += mono_jump
            if wall_jump == mono_jump == 1:
                self.result = code
                return code
            raise subprocess.TimeoutExpired('fake pull', timeout)

    process = Process()

    def spawn(argv, stdout, stderr):
        assert argv == ['docker', 'pull', '--platform=linux/amd64', 'repo@digest']
        stdout.write(b'abcdef123456: Already exists\n')
        stdout.flush()
        return process

    monkeypatch.setattr(module.subprocess, 'Popen', spawn)
    return process, lambda: clocks['wall'], lambda: clocks['mono']


def status(path):
    return json.loads((path / 'pull.status.json').read_text())


def test_success_preserves_cache_state_and_terminal_progress(module, monkeypatch, tmp_path):
    process, wall, mono = fake_process(module, monkeypatch)
    result = module.run_pull('repo@digest', tmp_path, wall_clock=wall, monotonic_clock=mono)
    assert result['status'] == status(tmp_path)['status'] == 'pass'
    assert not process.killed
    events = [json.loads(line) for line in (tmp_path / 'pull.progress.jsonl').read_text().splitlines()]
    assert events[0]['event'] == 'started' and events[-1]['event'] == 'finished'
    assert any(e.get('state') == 'Already exists' for e in events)
    assert any(e['event'] == 'heartbeat' for e in events)


@pytest.mark.parametrize('wall_jump,mono_jump', [(3600, 1), (-3600, 1201)])
def test_sleep_and_backward_wall_adjustment_cannot_extend_deadline(module, monkeypatch, tmp_path, wall_jump, mono_jump):
    process, wall, mono = fake_process(module, monkeypatch, wall_jump=wall_jump, mono_jump=mono_jump)
    with pytest.raises(subprocess.TimeoutExpired):
        module.run_pull('repo@digest', tmp_path, wall_clock=wall, monotonic_clock=mono)
    assert process.killed
    assert status(tmp_path)['status'] == 'wall_clock_timeout'
    assert status(tmp_path)['elapsed_seconds'] >= 1200


def test_nonzero_exit_is_not_success(module, monkeypatch, tmp_path):
    process, wall, mono = fake_process(module, monkeypatch, code=7)
    with pytest.raises(subprocess.CalledProcessError) as error:
        module.run_pull('repo@digest', tmp_path, wall_clock=wall, monotonic_clock=mono)
    assert error.value.returncode == 7
    assert status(tmp_path)['status'] == 'pull_failed'
    assert not process.killed


def test_interrupt_stops_only_owned_client_and_records_terminal_state(module, monkeypatch, tmp_path):
    process, wall, mono = fake_process(module, monkeypatch, interrupt=True)
    with pytest.raises(KeyboardInterrupt):
        module.run_pull('repo@digest', tmp_path, wall_clock=wall, monotonic_clock=mono)
    assert process.killed
    assert status(tmp_path)['status'] == 'interrupted_or_start_failed'


def test_real_local_child_timeout_without_docker(module, monkeypatch, tmp_path):
    original = subprocess.Popen

    def local_child(argv, **kwargs):
        assert argv[0:2] == ['docker', 'pull']
        return original([sys.executable, '-c', 'import time; time.sleep(5)'], **kwargs)

    monkeypatch.setattr(module.subprocess, 'Popen', local_child)
    with pytest.raises(subprocess.TimeoutExpired):
        module.run_pull('unused@digest', tmp_path, timeout_seconds=0.15)
    assert status(tmp_path)['status'] == 'wall_clock_timeout'
    assert status(tmp_path)['returncode'] is not None


def test_spawn_failure_still_records_terminal_state(module, monkeypatch, tmp_path):
    def missing_client(*args, **kwargs):
        raise FileNotFoundError('no docker client')

    monkeypatch.setattr(module.subprocess, 'Popen', missing_client)
    with pytest.raises(FileNotFoundError):
        module.run_pull('unused@digest', tmp_path)
    assert status(tmp_path)['status'] == 'interrupted_or_start_failed'
    assert status(tmp_path)['returncode'] is None
