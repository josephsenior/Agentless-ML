"""Opt-in reproductions, not fixes or public regression passes."""

import os
from pathlib import Path

import pytest

from agentless_ml.validation import DockerTestRunner
from agentless_ml.validation.docker import PublicTestCommand
from agentless_ml.validation.reports import ReportFormat, TestReport
from agentless_ml.workspace import LocalGitWorkspaceProvider

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(not os.environ.get("AGENTLESS_PWNTOOLS_PROCESS_IMAGE"), reason="opt-in isolated process-failure diagnosis")
def test_process_failure_reproductions(tmp_path):
    repositories = Path(os.environ.get("AGENTLESS_DELEGATED_TASK_REPOSITORIES", str(ROOT.parent / "benchmarks/deepswe/repos")))
    provider = LocalGitWorkspaceProvider(repositories / "pwntools-tube-multiplexing",
        "76894a5404a65d2800b6d0adaf3485ecba275caa", tmp_path / "workspaces")
    artifacts = Path(os.environ.get("AGENTLESS_PWNTOOLS_PROCESS_ARTIFACTS", str(tmp_path / "logs")))
    runner = DockerTestRunner(os.environ["AGENTLESS_PWNTOOLS_PROCESS_IMAGE"], artifacts,
        memory_mb=8192, cpus=2, tmpfs_mb=4096, pids_limit=2048, run_as_image_user=True)
    with provider.create() as workspace:
        (workspace.path / "agentless_process_probe.py").write_text(r'''import ctypes
import errno
import json
import os
import subprocess
import sys
from pathlib import Path

import psutil
import pytest
from pwn import context, process
from pwnlib.util.proc import ancestors

def record(name, **facts):
    print('PROCESS_DIAGNOSTIC ' + json.dumps(dict(probe=name, **facts), sort_keys=True))

def test_aslr_request_is_denied_and_maps_still_vary():
    code = "import ctypes,json; lib=ctypes.CDLL('libc.so.6',use_errno=True); result=lib.personality(0x0040000); print(json.dumps(dict(result=result,errno=ctypes.get_errno())))"
    facts = json.loads(subprocess.check_output([sys.executable, '-c', code]))
    status = Path('/proc/self/status').read_text().splitlines()
    isolation = [line for line in status if line.startswith(('Seccomp:', 'NoNewPrivs:', 'CapEff:'))]
    first = process(['cat', '/proc/self/maps'], aslr=False).recvall()
    with context.local(aslr=False):
        second = process(['cat', '/proc/self/maps']).recvall()
    record('aslr', **facts, maps_equal=first == second, isolation=isolation)
    assert facts == {'result': -1, 'errno': errno.EPERM}
    assert first != second

def test_relative_cwd_is_resolved_twice_without_qemu():
    os.chdir('/tmp/work/docs')
    directory = Path('/tmp/agentless-process-bin')
    directory.mkdir(exist_ok=True)
    binary = directory / 'probe'
    binary.write_text('#!/bin/sh\nexit 0\n')
    binary.chmod(0o755)
    relative = os.path.relpath(directory)
    # Absolute cwd and absolute executable controls succeed.
    for executable, cwd in [('./probe', str(directory)), (str(binary), relative)]:
        child = process(executable, cwd=cwd)
        assert child.poll(block=True) == 0
        child.close()
    validated = os.path.join(relative, './probe')
    double_resolved = os.path.abspath(os.path.join(relative, validated))
    assert Path(validated).is_file()
    assert not Path(double_resolved).exists()
    with pytest.raises(FileNotFoundError):
        process('./probe', cwd=relative)
    # Standard subprocess alone reproduces the same second resolution.
    with pytest.raises(FileNotFoundError):
        subprocess.run(['./probe'], executable=validated, cwd=relative, check=True)
    record('relative-path', cwd=relative, validated_executable=validated,
           double_resolved=double_resolved, absolute_controls_passed=True,
           reproduced_without_qemu=True)

def test_exec_ancestor_chain_stops_at_namespace_root():
    chain = ancestors(os.getpid())
    direct = [os.getpid()] + [parent.pid for parent in psutil.Process().parents()]
    terminal = psutil.Process(chain[-1])
    terminal_ppid = terminal.ppid()
    record('pid-chain', actual=chain, psutil_chain=direct,
           terminal_ppid=terminal_ppid, terminal_parent_is_none=terminal.parent() is None,
           pid1_name=psutil.Process(1).name(), pid1_in_chain=1 in chain)
    assert chain == direct
    assert terminal_ppid == 0 and terminal.parent() is None
    assert 1 not in chain
''', encoding="utf-8")
        execution = runner.run(workspace.path, PublicTestCommand(
            ("sh", "-c", "cd /tmp/work && PYTHONPATH=/tmp/work PWNLIB_NOTERM=1 python -m pytest -s -q -p no:cacheprovider agentless_process_probe.py --junitxml=/tmp/report.xml"),
            timeout_seconds=90, report=TestReport(ReportFormat.JUNIT_XML, "/tmp/report.xml"),
        ))
    assert execution.result.status.value == "pass", f"{execution.message}; {execution.artifact_directory}"
    assert len(execution.result.test_cases) == 3
