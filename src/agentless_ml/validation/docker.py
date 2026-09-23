"""Run fixed public commands in disposable Linux containers using the Docker CLI."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import tarfile
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import IO

from agentless_ml.schemas import (
    TestCaseStatus,
    ValidationKind,
    ValidationResult,
    ValidationStatus,
)

from .reports import MAX_REPORT_BYTES, ReportError, TestReport, parse_report

LOG_TAIL_BYTES = 1024 * 1024


@dataclass(frozen=True)
class PublicTestCommand:
    """Exit codes are a controller declaration for a known test runner.

    Without ``report`` the command is one selection unit. With ``report`` the
    runner reads the per-test outcomes the command writes, so each test counts.
    ``counted_test_ids`` limits which of those tests count during selection.
    For pytest, 1 means test failure; collection/usage errors remain harness errors.
    """

    argv: tuple[str, ...]
    kind: ValidationKind = ValidationKind.REGRESSION
    timeout_seconds: float = 60
    failure_exit_codes: tuple[int, ...] = (1,)
    report: TestReport | None = None
    counted_test_ids: tuple[str, ...] | None = None

    def __post_init__(self):
        if not self.argv or any(
            not isinstance(v, str) or not v or "\0" in v for v in self.argv
        ):
            raise ValueError("command must contain nonempty arguments without NULs")
        if not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("timeout must be finite and positive")
        if any(
            type(code) is not int or not 1 <= code <= 124
            for code in self.failure_exit_codes
        ):
            raise ValueError("test failure exit codes must be between 1 and 124")
        if self.counted_test_ids is not None:
            if self.report is None:
                raise ValueError("counted_test_ids requires a test report")
            if not self.counted_test_ids or len(set(self.counted_test_ids)) != len(
                self.counted_test_ids
            ):
                raise ValueError("counted_test_ids must be nonempty and unique")


@dataclass(frozen=True)
class TestExecution:
    result: ValidationResult
    image_id: str
    container_name: str
    artifact_directory: str
    message: str = ""


class DockerError(RuntimeError):
    pass


def _snapshot(source: Path, target: Path) -> None:
    """Copy regular source files only, with portable permissions and no history."""
    with tarfile.open(target, "w") as archive:
        for path in sorted(source.rglob("*")):
            relative = path.relative_to(source)
            if any(part.casefold() == ".git" for part in relative.parts):
                continue
            if path.is_symlink() or (not path.is_file() and not path.is_dir()):
                raise DockerError(f"unsupported snapshot entry: {relative}")
            info = archive.gettarinfo(str(path), arcname=relative.as_posix())
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mode = 0o755 if path.is_dir() or info.mode & 0o111 else 0o644
            if path.is_file():
                with path.open("rb") as stream:
                    archive.addfile(info, stream)
            else:
                archive.addfile(info)


UNPRIVILEGED_USER = "65534:65534"


class DockerTestRunner:
    """Images must be trusted and already contain public-test dependencies.

    Tags resolve once to an immutable local image ID. Images declaring volumes
    are rejected. No host directory, credential, socket, or Git history is mounted.

    Commands run as UID/GID 65534 with ``HOME=/tmp`` by default. Benchmark images
    are built as root and keep toolchains and pre-downloaded dependencies in
    ``/root`` (for example Go's module cache), which 65534 cannot read, and the
    container has no network to fetch them again. ``run_as_image_user=True`` runs
    commands as the image's own user with its own ``HOME`` instead; every other
    restriction still applies.
    """

    def __init__(
        self,
        image: str,
        artifact_root: Path,
        *,
        memory_mb: int = 512,
        cpus: float = 1,
        pids_limit: int = 128,
        tmpfs_mb: int = 256,
        run_as_image_user: bool = False,
    ):
        if not image or image.startswith("-"):
            raise ValueError("image must be a local image reference")
        if any(type(v) is not int or v <= 0 for v in (memory_mb, pids_limit, tmpfs_mb)):
            raise ValueError("resource limits must be positive integers")
        if not math.isfinite(cpus) or cpus <= 0:
            raise ValueError("cpus must be finite and positive")
        metadata = json.loads(self._docker("image", "inspect", image).stdout)[0]
        if metadata.get("Os") != "linux" or metadata["Config"].get("Volumes"):
            raise ValueError("a Linux image without declared volumes is required")
        self.image_id = metadata["Id"]
        self.image_reference = image
        self.artifact_root = Path(artifact_root).resolve()
        self.memory_mb, self.cpus = memory_mb, cpus
        self.pids_limit, self.tmpfs_mb = pids_limit, tmpfs_mb
        self.run_as_image_user = run_as_image_user
        # An image with no configured user runs as root.
        self.user = (
            (metadata["Config"].get("User") or "root")
            if run_as_image_user
            else UNPRIVILEGED_USER
        )

    @staticmethod
    def _docker(
        *args: str,
        timeout: float = 30,
        stdin: int | IO[bytes] | None = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess[bytes]:
        result = subprocess.run(
            ["docker", *args],
            stdin=stdin,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        if check and result.returncode:
            raise DockerError(result.stderr.decode("utf-8", errors="replace")[:2000])
        return result

    def _read_file(self, name: str, path: str, limit: int) -> bytes | None:
        """The first ``limit`` bytes of a container file, or None if it is absent."""
        result = self._docker(
            "exec", name, "/bin/sh", "-c",
            'test -f "$1" && head -c "$2" "$1"', "read-file", path, str(limit),
            check=False,
        )
        return result.stdout if result.returncode == 0 else None

    def _tail_file(self, name: str, path: str) -> bytes:
        result = self._docker(
            "exec", name, "/bin/sh", "-c",
            'test -f "$1" && tail -c "$2" "$1"', "tail-file", path, str(LOG_TAIL_BYTES),
            check=False,
        )
        return result.stdout if result.returncode == 0 else b""

    def run(
        self,
        source: Path,
        command: PublicTestCommand,
        *,
        artifact_root: Path | None = None,
    ) -> TestExecution:
        source = Path(source).resolve(strict=True)
        if not source.is_dir():
            raise ValueError("source must be a directory")
        active_artifact_root = (
            self.artifact_root
            if artifact_root is None
            else Path(artifact_root).resolve()
        )
        if active_artifact_root == source or source in active_artifact_root.parents:
            raise ValueError("artifacts must be outside the source checkout")
        name = "agentless-ml-" + uuid.uuid4().hex
        artifacts = active_artifact_root / name
        artifacts.mkdir(parents=True)
        start = time.monotonic()
        status = ValidationStatus.HARNESS_ERROR
        exit_code = None
        message = ""
        stdout = stderr = b""
        report_bytes: bytes | None = None
        test_cases = ()
        # counted_test_ids is only ever set from a baseline in which this exact
        # command wrote a valid report on the unpatched checkout, so a run of it
        # that yields no usable results can only be the patch's doing.
        proven = command.counted_test_ids is not None
        attempted_create = False
        try:
            with tempfile.TemporaryDirectory(prefix="agentless-snapshot-") as temporary:
                snapshot = Path(temporary) / "source.tar"
                _snapshot(source, snapshot)
                attempted_create = True
                # The container itself only waits. The command runs through
                # `docker exec`, so files it writes to the memory-only /tmp (its
                # output and report) can be read before the container is removed.
                identity = (
                    ()
                    if self.run_as_image_user
                    else (f"--user={UNPRIVILEGED_USER}", "--env=HOME=/tmp")
                )
                self._docker(
                    "create",
                    "--name",
                    name,
                    "--label",
                    "agentless-ml.public-test=true",
                    "--pull=never",
                    "--network=none",
                    "--read-only",
                    "--cap-drop=ALL",
                    "--security-opt=no-new-privileges",
                    *identity,
                    f"--memory={self.memory_mb}m",
                    f"--memory-swap={self.memory_mb}m",
                    f"--cpus={self.cpus}",
                    f"--pids-limit={self.pids_limit}",
                    "--init",
                    # `exec`: compiled test binaries (Go test binaries, Rust cargo
                    # tests) are built under /tmp and must be able to run. Docker
                    # mounts tmpfs noexec unless told otherwise.
                    "--tmpfs",
                    f"/tmp:rw,exec,nosuid,nodev,size={self.tmpfs_mb}m,mode=1777",
                    "--log-driver=json-file",
                    "--log-opt=max-size=1m",
                    "--log-opt=max-file=1",
                    "--workdir=/tmp",
                    "--env=PYTHONDONTWRITEBYTECODE=1",
                    "--entrypoint=/bin/sh",
                    self.image_id,
                    "-c",
                    "while :; do sleep 1; done",
                )
                self._docker("start", name)
                with snapshot.open("rb") as stream:
                    self._docker(
                        "exec",
                        "--interactive",
                        name,
                        "/bin/sh",
                        "-c",
                        "mkdir /tmp/work && tar --no-same-owner -xf - -C /tmp/work",
                        stdin=stream,
                    )
            try:
                # The shell script is fixed. User command arguments are passed as
                # positional arguments, never interpolated into shell code.
                completed = self._docker(
                    "exec",
                    name,
                    "/bin/sh",
                    "-c",
                    'cd /tmp/work || exit 125; "$@" >/tmp/agentless-stdout 2>/tmp/agentless-stderr',
                    "public-test",
                    *command.argv,
                    timeout=command.timeout_seconds,
                    check=False,
                )
                exit_code = completed.returncode
            except subprocess.TimeoutExpired:
                status = ValidationStatus.TIMEOUT
            state = json.loads(self._docker("inspect", name).stdout)[0]["State"]
            if status is not ValidationStatus.TIMEOUT:
                if state.get("OOMKilled"):
                    status = ValidationStatus.OUT_OF_MEMORY
                elif state.get("Error") or not state.get("Running"):
                    status = ValidationStatus.HARNESS_ERROR
                    message = "container stopped while the command was running"
                elif exit_code == 0:
                    status = ValidationStatus.PASS
                elif exit_code in command.failure_exit_codes:
                    status = ValidationStatus.FAIL
                elif proven:
                    status = ValidationStatus.FAIL
                    message = (
                        f"exit {exit_code} is not a declared failure code; counted "
                        "against the patch because this command reported "
                        "normally on the unpatched checkout"
                    )
                else:
                    status = ValidationStatus.HARNESS_ERROR
            stdout = self._tail_file(name, "/tmp/agentless-stdout")
            stderr = self._tail_file(name, "/tmp/agentless-stderr")
            if command.report is not None and status in (
                ValidationStatus.PASS,
                ValidationStatus.FAIL,
            ):
                report_path = command.report.container_path()
                report_bytes = self._read_file(name, report_path, MAX_REPORT_BYTES + 1)
                try:
                    if report_bytes is None:
                        raise ReportError(f"declared test report was not written: {report_path}")
                    test_cases = parse_report(report_bytes, command.report.format)
                except ReportError as exc:
                    message = f"{message} {exc}".strip()[:2000]
                    test_cases = ()
                    # A failing run that left no usable report, from a command
                    # proven on the unpatched code, is a patch that broke the
                    # build or the imports; failure_count() then counts every
                    # counted test as failed, as published Agentless does when
                    # none of them appear in the log. Otherwise the harness
                    # itself is in doubt.
                    if not (proven and status is ValidationStatus.FAIL):
                        status = ValidationStatus.HARNESS_ERROR
                else:
                    failing = any(
                        case.status in (TestCaseStatus.FAILED, TestCaseStatus.ERROR)
                        for case in test_cases
                    )
                    # A disagreement means the command or its exit codes are
                    # misdeclared, so neither signal can be trusted as evidence.
                    # A proven command failing with no failed test in the report
                    # is exempt: counted tests missing from the report already
                    # count as failures.
                    contradiction = None
                    if status is ValidationStatus.PASS and failing:
                        contradiction = "exit status 0 contradicts failed tests in the report"
                    elif status is ValidationStatus.FAIL and not failing and not proven:
                        contradiction = "failure exit code, but the report shows no failed test"
                    if contradiction:
                        status = ValidationStatus.HARNESS_ERROR
                        message = contradiction
                        test_cases = ()
        except (
            DockerError,
            OSError,
            subprocess.TimeoutExpired,
            ValueError,
            KeyError,
        ) as exc:
            status = ValidationStatus.HARNESS_ERROR
            message = str(exc)[:2000]
        finally:
            if attempted_create:
                try:
                    self._docker("rm", "--force", "--volumes", name)
                except (DockerError, OSError, subprocess.TimeoutExpired) as exc:
                    status = ValidationStatus.HARNESS_ERROR
                    message += f" Cleanup failed for {name}: {exc}"
        (artifacts / "stdout.log").write_bytes(stdout)
        (artifacts / "stderr.log").write_bytes(stderr)
        report_artifact = None
        if report_bytes is not None and command.report is not None:
            suffix = ".xml" if command.report.format.value == "junit-xml" else ".json"
            report_artifact = "report" + suffix
            (artifacts / report_artifact).write_bytes(report_bytes)
        result = ValidationResult(
            status=status,
            command=command.argv,
            duration_seconds=time.monotonic() - start,
            exit_code=exit_code,
            stdout_digest=hashlib.sha256(stdout).hexdigest(),
            stderr_digest=hashlib.sha256(stderr).hexdigest(),
            kind=command.kind,
            test_cases=test_cases,
            counted_test_ids=command.counted_test_ids,
        )
        execution = TestExecution(result, self.image_id, name, str(artifacts), message)
        record = asdict(execution)
        record["limits"] = {
            "memory_mb": self.memory_mb,
            "cpus": self.cpus,
            "pids_limit": self.pids_limit,
            "tmpfs_mb": self.tmpfs_mb,
            "timeout_seconds": command.timeout_seconds,
        }
        record["failure_exit_codes"] = command.failure_exit_codes
        # Which user ran the command is experimental provenance: every compared
        # condition must use the same setting for a task.
        record["user"] = {"run_as_image_user": self.run_as_image_user, "user": self.user}
        record["logs"] = f"last {LOG_TAIL_BYTES} bytes of the command's stdout and stderr"
        record["report"] = (
            None
            if command.report is None
            else {
                "format": command.report.format.value,
                "path": command.report.path,
                "artifact": report_artifact,
                "test_cases": len(test_cases),
            }
        )
        (artifacts / "execution.json").write_text(
            json.dumps(record, indent=2) + "\n", encoding="utf-8"
        )
        return execution
