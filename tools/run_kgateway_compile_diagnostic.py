"""One compile-only diagnostic; opt in to the full 30-minute attempt."""

import argparse
import ctypes
import json
import os
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from contextlib import contextmanager

from agentless_ml.validation import DockerTestRunner, PublicTestCommand
from agentless_ml.workspace import LocalGitWorkspaceProvider, verify_sealed_repository
from run_numba_resource_diagnostic import SampledRunner

ROOT = Path(__file__).resolve().parents[1]
TASK = "kgateway-consistent-hash-policy"
BASE = "7abc5278782e3280fec8292b39807ec1b537eaf4"
IMAGE = "sha256:a4f7250f435dd05fa354c8ea5f54e3d0228678f5203887d98863c5da7ceaf1b9"
ARTIFACTS = ROOT.parent / "output/deepswe-survey/kgateway-compile-diagnostic"


def diagnostic_command(*, full=False):
    window = "" if full else "timeout --signal=TERM --kill-after=10s 300s "
    label = "FULL_1800_SECOND_CAP" if full else "300_SECONDS"
    script = (
        "set -eu; cd /tmp/work; "
        "if [ -f go.work ]; then export GOFLAGS=; fi; "
        "mkdir -p /tmp/go-build /tmp/compile-work; "
        f"echo KGATEWAY_COMPILE_ONLY_{label}_ONE_BUILD_WORKER; "
        "GOCACHE=/tmp/go-build GOTMPDIR=/tmp/compile-work "
        f"{window}"
        "go test -c -p 1 -o /dev/null ./..."
    )
    # -c is the native no-execution mode; /dev/null also avoids collisions
    # between packages with the same binary basename. No report is declared.
    return PublicTestCommand(("/bin/sh", "-c", script), timeout_seconds=1800)


class CompileSampledRunner(SampledRunner):
    def __init__(self):
        # Reuse only the existing sampler startup and incremental journal.
        # Do not initialize or run anything from the parked Numba diagnostic.
        DockerTestRunner.__init__(self, IMAGE, ARTIFACTS / "logs", memory_mb=8192,
                                 cpus=2, pids_limit=2048, tmpfs_mb=4096,
                                 run_as_image_user=True)
        self.samples = []
        self.stop_sampling = threading.Event()
        self.sampler = None

    def sample(self, name):
        started = time.monotonic()
        probe = (
            'echo SCRATCH_DF_BYTES; df -B1 /tmp; '
            'echo DIRECTORY_KIB; du -sk /tmp/go-build /tmp/compile-work /tmp/work; '
            'for f in memory.current memory.peak memory.events cpu.stat pids.current; '
            'do echo "FILE:$f"; cat "/sys/fs/cgroup/$f"; done; '
            'echo PROGRESS; tail -n 3 /tmp/agentless-stdout; '
            'echo STDERR; tail -n 5 /tmp/agentless-stderr'
        )
        while not self.stop_sampling.is_set():
            try:
                result = subprocess.run(["docker", "exec", name, "/bin/sh", "-c", probe],
                    capture_output=True, text=True, timeout=15, check=False)
                sample = {"seconds": round(time.monotonic() - started, 2),
                          "exit_code": result.returncode, "stdout": result.stdout,
                          "stderr": result.stderr}
            except subprocess.TimeoutExpired:
                sample = {"seconds": round(time.monotonic() - started, 2),
                          "error": "resource probe timeout"}
            self.record_sample(name, sample)
            print(f"compile resource sample {sample['seconds']}s", flush=True)
            self.stop_sampling.wait(10)


@contextmanager
def keep_host_awake(enabled, set_state=None):
    """Prevent automatic Windows sleep for this thread, without changing power settings."""
    if not enabled:
        yield
        return
    if set_state is None:
        if os.name != "nt":
            raise RuntimeError("--keep-awake requires Windows")
        set_state = ctypes.windll.kernel32.SetThreadExecutionState
        set_state.argtypes = [ctypes.c_uint]
        set_state.restype = ctypes.c_uint
    if not set_state(0x80000001):  # ES_CONTINUOUS | ES_SYSTEM_REQUIRED
        raise RuntimeError("Windows rejected the temporary keep-awake request")
    print("Temporary Windows system keep-awake request active", flush=True)
    try:
        yield
    finally:
        if not set_state(0x80000000):  # release this thread's requirement
            raise RuntimeError("Windows failed to release the keep-awake request")
        print("Temporary Windows keep-awake request released", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true",
                        help="One full compile-only attempt under the existing 1800-second cap")
    parser.add_argument("--keep-awake", action="store_true",
                        help="Temporarily prevent automatic Windows system sleep during this attempt")
    args = parser.parse_args()
    with keep_host_awake(args.keep_awake):
        run_attempt(args)


def run_attempt(args):
    repository = ROOT.parent / "benchmarks/deepswe/repos" / TASK
    verify_sealed_repository(repository, BASE)
    runner = CompileSampledRunner()
    provider = LocalGitWorkspaceProvider(repository, BASE,
        Path(tempfile.gettempdir()) / "agentless-ml-survey-workspaces")
    try:
        with provider.create() as workspace:
            execution = runner.run(workspace.path, diagnostic_command(full=args.full))
    finally:
        runner.stop_sampling.set()
        if runner.sampler:
            runner.sampler.join(timeout=20)
    evidence = {"label": "compile_only_resource_diagnostic_not_baseline",
        "task_id": TASK, "base_commit": BASE, "image_id": runner.image_id,
        "build_workers": 1, "compile_window_seconds": None if args.full else 300,
        "full_compile_attempt": args.full, "outer_timeout_seconds": 1800,
        "temporary_windows_keep_awake": args.keep_awake,
        "memory_mb": 8192, "cpus": 2, "tmpfs_mb": 4096, "pids_limit": 2048,
        "full_package_target": "./...", "cache_seeded": False,
        "tests_executed": False, "accepted_regression_inventory": False,
        "official_survey_updated": False, "automatic_retry": False,
        "status": execution.result.status.value, "exit_code": execution.result.exit_code,
        "duration_seconds": execution.result.duration_seconds,
        "message": execution.message, "artifacts": execution.artifact_directory,
        "samples": runner.samples}
    target = Path(execution.artifact_directory) / "compile-diagnostic.json"
    target.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in evidence.items() if key != "samples"}, indent=2))
    print(target)


if __name__ == "__main__":
    main()
