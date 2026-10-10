"""Five-minute single-package compile diagnostic, never a public baseline."""

import json
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

from agentless_ml.validation import DockerTestRunner, PublicTestCommand
from agentless_ml.workspace import LocalGitWorkspaceProvider, verify_sealed_repository
from run_kgateway_compile_diagnostic import CompileSampledRunner

ROOT = Path(__file__).resolve().parents[1]
TASK = "pebble-durability-wait-apis"
BASE = "1454d2bc0f378d7f34766afafee68a77e7b85995"
IMAGE = "sha256:b063f2d927a8b3d71db24c4ec198a0d05644d3ecbe96289d8b2b2bdbecaa72bd"
ARTIFACTS = ROOT.parent / "output/deepswe-survey/pebble-valblk-compile-diagnostic"
FINAL_PROBE = (
    'for f in memory.current memory.peak memory.events cpu.stat pids.current; '
    'do echo "FILE:$f"; cat "/sys/fs/cgroup/$f"; done; '
    'echo SCRATCH_DF_BYTES; df -B1 /tmp; '
    'echo PROCESSES; ps -eo pid,ppid,rss,args'
)


def diagnostic_command():
    script = (
        "set -u; cd /tmp/work || exit 125; command -v timeout || exit 125; "
        "echo PEBBLE_VALBLK_COMPILE_ONLY_300_SECONDS_ONE_BUILD_WORKER; "
        "GOCACHE=/tmp/go-build timeout --signal=TERM --kill-after=10s 300s "
        "go test -c -p 1 -o /tmp/pebble-valblk.test ./sstable/valblk; "
        'rc=$?; printf "COMPILE_EXIT_CODE=%s\\n" "$rc"; exit "$rc"'
    )
    return PublicTestCommand(("/bin/sh", "-c", script), timeout_seconds=1800)


class PebbleCompileRunner(CompileSampledRunner):
    def __init__(self, *, artifact_root=None):
        # Reuse sampling only. Neither parked task's initializer or attempt runs.
        DockerTestRunner.__init__(self, IMAGE, artifact_root or ARTIFACTS / "logs", memory_mb=8192,
                                 cpus=2, pids_limit=2048, tmpfs_mb=4096,
                                 run_as_image_user=True)
        if self.image_id != IMAGE:
            raise ValueError("Pebble diagnostic requires its original pinned image")
        self.samples = []
        self.stop_sampling = threading.Event()
        self.sampler = None
        self.final_state = None
        self.observed_host_config = None
        self.final_probe = None

    def record_sample(self, name, sample):
        super().record_sample(name, {
            **sample, "observed_utc": datetime.now(timezone.utc).isoformat(),
        })

    def _docker(self, *args, **kwargs):
        result = super()._docker(*args, **kwargs)
        if args[0] == "inspect":
            metadata = json.loads(result.stdout)[0]
            self.final_state = metadata["State"]
            self.observed_host_config = {key: metadata["HostConfig"][key] for key in (
                "NetworkMode", "ReadonlyRootfs", "CapDrop", "SecurityOpt",
                "Memory", "MemorySwap", "NanoCpus", "PidsLimit", "Tmpfs",
                "Privileged", "ExtraHosts", "PortBindings", "Binds",
            )}
            probe = DockerTestRunner._docker(
                "exec", args[1], "/bin/sh", "-c", FINAL_PROBE, timeout=15, check=False,
            )
            self.final_probe = {
                "exit_code": probe.returncode,
                "stdout": probe.stdout.decode(errors="replace"),
                "stderr": probe.stderr.decode(errors="replace"),
            }
        return result


def main():
    repository = ROOT.parent / "benchmarks/deepswe/repos" / TASK
    verify_sealed_repository(repository, BASE)
    runner = PebbleCompileRunner()
    try:
        with LocalGitWorkspaceProvider(
            repository, BASE, Path(tempfile.gettempdir()) / "agentless-ml-survey-workspaces",
        ).create() as workspace:
            execution = runner.run(workspace.path, diagnostic_command())
    finally:
        runner.stop_sampling.set()
        if runner.sampler:
            runner.sampler.join(timeout=20)
    evidence = {
        "condition": "single-package compile-only diagnostic, not a baseline",
        "task_id": TASK, "base_commit": BASE, "image_id": runner.image_id,
        "package": "./sstable/valblk", "build_workers": 1,
        "compile_window_seconds": 300, "outer_timeout_seconds": 1800,
        "tests_executed": False, "cache_seeded": False,
        "official_survey_updated": False, "automatic_retry": False,
        "status": execution.result.status.value, "exit_code": execution.result.exit_code,
        "window_exhausted": execution.result.exit_code == 124,
        "duration_seconds": execution.result.duration_seconds,
        "message": execution.message, "artifacts": execution.artifact_directory,
        "observed_host_config": runner.observed_host_config,
        "final_state": runner.final_state, "final_probe": runner.final_probe,
        "samples": runner.samples,
    }
    target = Path(execution.artifact_directory) / "compile-diagnostic.json"
    target.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in evidence.items() if key != "samples"}, indent=2))
    print(target)


if __name__ == "__main__":
    main()
