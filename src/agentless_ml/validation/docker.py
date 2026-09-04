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

from agentless_ml.schemas import ValidationKind, ValidationResult, ValidationStatus


@dataclass(frozen=True)
class PublicTestCommand:
    """Exit codes are a controller declaration for a known test runner.

    Each command is one selection unit, not necessarily one individual test.
    For pytest, 1 means test failure; collection/usage errors remain harness errors.
    """

    argv: tuple[str, ...]
    kind: ValidationKind = ValidationKind.REGRESSION
    timeout_seconds: float = 60
    failure_exit_codes: tuple[int, ...] = (1,)

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


class DockerTestRunner:
    """Images must be trusted and already contain public-test dependencies.

    Tags resolve once to an immutable local image ID. Images declaring volumes
    are rejected. No host directory, credential, socket, or Git history is mounted.
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
        self.artifact_root = Path(artifact_root).resolve()
        self.memory_mb, self.cpus = memory_mb, cpus
        self.pids_limit, self.tmpfs_mb = pids_limit, tmpfs_mb

    @staticmethod
    def _docker(*args: str, timeout: float = 30, stdin=None):
        result = subprocess.run(
            ["docker", *args],
            stdin=stdin,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode:
            raise DockerError(result.stderr.decode("utf-8", errors="replace")[:2000])
        return result

    def run(self, source: Path, command: PublicTestCommand) -> TestExecution:
        source = Path(source).resolve(strict=True)
        if not source.is_dir():
            raise ValueError("source must be a directory")
        if self.artifact_root == source or source in self.artifact_root.parents:
            raise ValueError("artifacts must be outside the source checkout")
        name = "agentless-ml-" + uuid.uuid4().hex
        artifacts = self.artifact_root / name
        artifacts.mkdir(parents=True)
        start = time.monotonic()
        status = ValidationStatus.HARNESS_ERROR
        exit_code = None
        message = ""
        stdout = stderr = b""
        attempted_create = False
        try:
            with tempfile.TemporaryDirectory(prefix="agentless-snapshot-") as temporary:
                snapshot = Path(temporary) / "source.tar"
                _snapshot(source, snapshot)
                attempted_create = True
                # The shell script is fixed. User command arguments are passed as
                # positional arguments to exec, never interpolated into shell code.
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
                    "--user=65534:65534",
                    f"--memory={self.memory_mb}m",
                    f"--memory-swap={self.memory_mb}m",
                    f"--cpus={self.cpus}",
                    f"--pids-limit={self.pids_limit}",
                    "--init",
                    "--tmpfs",
                    f"/tmp:rw,nosuid,nodev,size={self.tmpfs_mb}m,mode=1777",
                    "--log-driver=json-file",
                    "--log-opt=max-size=1m",
                    "--log-opt=max-file=1",
                    "--workdir=/tmp",
                    "--env=HOME=/tmp",
                    "--env=PYTHONDONTWRITEBYTECODE=1",
                    "--entrypoint=/bin/sh",
                    self.image_id,
                    "-c",
                    'while [ ! -f /tmp/ready ]; do sleep 0.1; done; cd /tmp/work || exit 125; exec "$@"',
                    "public-test",
                    *command.argv,
                )
                self._docker("start", name)
                with snapshot.open("rb") as stream:
                    self._docker(
                        "exec",
                        "--interactive",
                        name,
                        "/bin/sh",
                        "-c",
                        "mkdir /tmp/work && tar -xf - -C /tmp/work && touch /tmp/ready",
                        stdin=stream,
                    )
            try:
                self._docker("wait", name, timeout=command.timeout_seconds)
            except subprocess.TimeoutExpired:
                status = ValidationStatus.TIMEOUT
                self._docker("kill", name)
            state = json.loads(self._docker("inspect", name).stdout)[0]["State"]
            exit_code = state["ExitCode"]
            if status is not ValidationStatus.TIMEOUT:
                if state.get("OOMKilled"):
                    status = ValidationStatus.OUT_OF_MEMORY
                elif state.get("Error") or state.get("Running"):
                    status = ValidationStatus.HARNESS_ERROR
                elif exit_code == 0:
                    status = ValidationStatus.PASS
                elif exit_code in command.failure_exit_codes:
                    status = ValidationStatus.FAIL
                else:
                    status = ValidationStatus.HARNESS_ERROR
            logs = self._docker("logs", "--tail=1000", name)
            stdout, stderr = logs.stdout, logs.stderr
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
        result = ValidationResult(
            status=status,
            command=command.argv,
            duration_seconds=time.monotonic() - start,
            exit_code=exit_code,
            stdout_digest=hashlib.sha256(stdout).hexdigest(),
            stderr_digest=hashlib.sha256(stderr).hexdigest(),
            kind=command.kind,
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
        record["logs"] = "last 1000 lines within Docker's rotating 1 MB log"
        (artifacts / "execution.json").write_text(
            json.dumps(record, indent=2) + "\n", encoding="utf-8"
        )
        return execution
