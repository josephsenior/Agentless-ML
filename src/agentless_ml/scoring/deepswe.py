"""Score a selected patch with DeepSWE's own verifier, after selection only.

Steps 1-4 of the workflow (localization, repair, validation, selection) never
see a task's held-out `tests/` or `solution/` directories. This module is the
one place that reads them, and only to answer, for a patch that has already
been selected, whether it solves the task. Nothing here feeds back into the
workflow, and no workflow module imports it (`tests/test_scoring_boundary.py`).

DeepSWE grades a patch in a separate container: the task's published image with
four files from `tests/` copied to `/tests`, and the patch at
`/logs/artifacts/model.patch`. `tests/test.sh` applies the patch and the hidden
`test.patch`, runs the hidden suites, and `tests/grader.py` writes
`/logs/verifier/reward.json`. The reward is 1 only if every fail-to-pass test
passes and no pass-to-pass test fails; a test missing from the report counts as
failed. An empty patch grades the unmodified base.

Two details decide whether a score here equals DeepSWE's own:

- Files are read from git at the pinned DeepSWE revision, not from the working
  tree. On a Windows clone with `core.autocrlf=true` every verifier file is
  checked out with CRLF line endings (1778 of them in actionlint's
  `test.patch`); `bash test.sh` and `git apply test.patch` both fail on those.
- All 113 verifier Dockerfiles are the image plus four COPYs and a chmod.
  The files are streamed into a container of the pinned image with the same
  paths and modes instead of building an image, and a task whose Dockerfile
  has any other shape is refused rather than approximated.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import re
import subprocess
import tarfile
import tomllib
import uuid
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path

from agentless_ml.schemas import TaskSpec

VERIFIER_FILES = ("test.sh", "test.patch", "grader.py", "config.json")
_DOCKERFILE_BODY = (
    "COPY test.sh /tests/test.sh",
    "COPY test.patch /tests/test.patch",
    "COPY grader.py /tests/grader.py",
    "COPY config.json /tests/config.json",
    "RUN chmod +x /tests/test.sh",
)
_TASK_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,127}")
_REVISION = re.compile(r"[0-9a-f]{40}")
_RESULT_FILES = ("reward.json", "reward.txt", "ctrf.json", "run.log")
_MAX_RESULT_BYTES = 32 * 1024 * 1024


class ScoringError(RuntimeError):
    """The scorer could not run the verifier as DeepSWE defines it."""


class ScoreStatus(StrEnum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    PATCH_NOT_APPLIED = "patch_not_applied"
    VERIFIER_ERROR = "verifier_error"
    TIMEOUT = "timeout"


@dataclass(frozen=True, slots=True)
class DeepSWEScore:
    task_id: str
    status: ScoreStatus
    reward: int | None
    f2p_passed: int | None
    f2p_total: int | None
    p2p_passed: int | None
    p2p_total: int | None
    image_id: str
    patch_sha256: str
    dataset_revision: str
    artifact_directory: str
    message: str = ""

    @property
    def resolved(self) -> bool:
        return self.status is ScoreStatus.RESOLVED


def _docker(*args: str, timeout: float, data: bytes | None = None, check: bool = True):
    result = subprocess.run(
        ["docker", *args], input=data, capture_output=True, timeout=timeout, check=False
    )
    if check and result.returncode:
        raise ScoringError(
            f"docker {args[0]} failed: "
            + result.stderr.decode("utf-8", errors="replace")[:1000]
        )
    return result


class DeepSWEVerifier:
    """DeepSWE's verifier for tasks at one pinned revision of the corpus."""

    def __init__(self, repository: Path, revision: str) -> None:
        if not _REVISION.fullmatch(revision):
            raise ValueError("revision must be a full lowercase commit")
        self.repository = Path(repository).resolve(strict=True)
        self.revision = revision
        resolved = self._git("rev-parse", "--verify", revision + "^{commit}").decode().strip()
        if resolved != revision:
            raise ScoringError(f"{revision} is not a commit in {self.repository}")

    def _git(self, *args: str) -> bytes:
        result = subprocess.run(
            ["git", "-c", "core.autocrlf=false", *args],
            cwd=self.repository,
            capture_output=True,
            timeout=60,
            check=False,
        )
        if result.returncode:
            raise ScoringError(result.stderr.decode("utf-8", errors="replace")[:1000])
        return result.stdout

    def _blob(self, task_id: str, relative: str) -> bytes:
        if not _TASK_ID.fullmatch(task_id):
            raise ValueError(f"not a DeepSWE task id: {task_id!r}")
        return self._git("show", f"{self.revision}:tasks/{task_id}/{relative}")

    def verifier_files(self, task: TaskSpec) -> dict[str, bytes]:
        """The files DeepSWE's verifier Dockerfile copies, as committed."""
        dockerfile = self._blob(task.instance_id, "tests/Dockerfile").decode("utf-8")
        lines = [
            line.strip()
            for line in dockerfile.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        if not lines or lines[0] != f"FROM {task.container_image}":
            raise ScoringError(
                f"{task.instance_id}: verifier image is not the task's image "
                f"{task.container_image}"
            )
        if tuple(lines[1:]) != _DOCKERFILE_BODY:
            raise ScoringError(
                f"{task.instance_id}: verifier Dockerfile has an unreviewed shape; "
                "copying its files into the task image would not be equivalent"
            )
        return {name: self._blob(task.instance_id, f"tests/{name}") for name in VERIFIER_FILES}

    def verifier_limits(self, task: TaskSpec) -> tuple[float, int, float]:
        """cpus, memory in MB and timeout in seconds from the task's [verifier]."""
        manifest = tomllib.loads(self._blob(task.instance_id, "task.toml").decode("utf-8"))
        verifier = manifest["verifier"]
        if verifier.get("network_mode") != "no-network":
            raise ScoringError(f"{task.instance_id}: verifier expects network access")
        environment = verifier.get("environment", {})
        return (
            float(environment.get("cpus", 2)),
            int(environment.get("memory_mb", 8192)),
            float(verifier.get("timeout_sec", 1800)),
        )

    def reference_patch_for_harness_validation(self, task: TaskSpec) -> str:
        """DeepSWE's reference solution, for checking the scorer only.

        Scoring it must give `resolved`, as scoring an empty patch must give
        `unresolved`; that is how the harness itself is validated. It must never
        be given to, or compared with anything from, the workflow.
        """
        return self._blob(task.instance_id, "solution/solution.patch").decode("utf-8")

    def score(
        self,
        task: TaskSpec,
        patch: str,
        artifact_root: Path,
        *,
        timeout_seconds: float | None = None,
    ) -> DeepSWEScore:
        """Run DeepSWE's verifier on ``patch`` in the task's pinned image."""
        if not task.container_digest:
            raise ScoringError(f"{task.instance_id}: task image is not pinned by digest")
        files = self.verifier_files(task)
        cpus, memory_mb, limit = self.verifier_limits(task)
        timeout = limit if timeout_seconds is None else timeout_seconds
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout_seconds must be finite and positive")
        inspected = json.loads(
            _docker("image", "inspect", task.container_image, timeout=60).stdout
        )[0]
        image_id = inspected["Id"]
        if image_id != task.container_digest:
            raise ScoringError(
                f"{task.container_image} is {image_id}, not the pinned {task.container_digest}"
            )

        patch_bytes = patch.encode("utf-8")
        patch_sha256 = hashlib.sha256(patch_bytes).hexdigest()
        name = "agentless-ml-verifier-" + uuid.uuid4().hex
        artifacts = Path(artifact_root).resolve() / name
        artifacts.mkdir(parents=True)
        (artifacts / "model.patch").write_bytes(patch_bytes)

        status: ScoreStatus
        message = ""
        exit_code: int | None = None
        results: dict[str, bytes] = {}
        created = False
        try:
            _docker(
                "create",
                "--name", name,
                "--network=none",
                f"--cpus={cpus}",
                f"--memory={memory_mb}m",
                f"--memory-swap={memory_mb}m",
                "--pids-limit=4096",
                "--security-opt=no-new-privileges",
                "--pull=never",
                "--entrypoint", "bash",
                image_id,
                "/tests/test.sh",
                timeout=60,
            )
            created = True
            _docker("cp", "-", f"{name}:/", data=_inputs(files, patch_bytes), timeout=120)
            try:
                run = _docker("start", "--attach", name, timeout=timeout, check=False)
                exit_code = run.returncode
                (artifacts / "test-stdout.txt").write_bytes(run.stdout + run.stderr)
            except subprocess.TimeoutExpired:
                _docker("kill", name, timeout=60, check=False)
                status, message = ScoreStatus.TIMEOUT, f"verifier exceeded {timeout:g}s"
            else:
                exported = _docker("cp", f"{name}:/logs/verifier", "-", timeout=120, check=False)
                results = _results(exported.stdout) if exported.returncode == 0 else {}
                for file_name, content in results.items():
                    (artifacts / file_name).write_bytes(content)
                status, message = _status(results, exit_code)
        except (ScoringError, OSError, subprocess.TimeoutExpired, ValueError, KeyError) as exc:
            status, message = ScoreStatus.VERIFIER_ERROR, str(exc)[:2000]
        finally:
            if created:
                _docker("rm", "--force", "--volumes", name, timeout=60, check=False)

        reward = _reward(results)
        score = DeepSWEScore(
            task_id=task.instance_id,
            status=status,
            reward=reward.get("reward"),
            f2p_passed=reward.get("f2p_passed"),
            f2p_total=reward.get("f2p_total"),
            p2p_passed=reward.get("p2p_passed"),
            p2p_total=reward.get("p2p_total"),
            image_id=image_id,
            patch_sha256=patch_sha256,
            dataset_revision=self.revision,
            artifact_directory=str(artifacts),
            message=message,
        )
        record = {**asdict(score), "verifier_exit_code": exit_code}
        (artifacts / "score.json").write_text(
            json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        return score


def _inputs(files: dict[str, bytes], patch: bytes) -> bytes:
    """A tar placing the verifier files and the patch exactly as DeepSWE does."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as archive:
        entries = [("tests", None, 0o755), ("logs", None, 0o755), ("logs/artifacts", None, 0o755)]
        entries += [
            (f"tests/{file_name}", content, 0o755 if file_name == "test.sh" else 0o644)
            for file_name, content in files.items()
        ]
        entries.append(("logs/artifacts/model.patch", patch, 0o644))
        for path, content, mode in entries:
            info = tarfile.TarInfo(path)
            info.mode, info.uid, info.gid = mode, 0, 0
            if content is None:
                info.type = tarfile.DIRTYPE
                archive.addfile(info)
            else:
                info.size = len(content)
                archive.addfile(info, io.BytesIO(content))
    return buffer.getvalue()


def _results(stream: bytes) -> dict[str, bytes]:
    """Regular result files from the container's /logs/verifier, by name.

    The container ran the patch under test, so its output is untrusted: only
    known names are kept, only regular files, and each is size-capped.
    """
    found: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(stream), mode="r:*") as archive:
        for member in archive:
            parts = member.name.split("/")
            if len(parts) != 2 or parts[1] not in _RESULT_FILES:
                continue
            if not member.isreg() or member.size > _MAX_RESULT_BYTES:
                continue
            extracted = archive.extractfile(member)
            if extracted is not None:
                found[parts[1]] = extracted.read()
    return found


def _reward(results: dict[str, bytes]) -> dict[str, int]:
    raw = results.get("reward.json")
    if raw is None:
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        return {}
    if not isinstance(data, dict):
        return {}
    keys = ("reward", "f2p_passed", "f2p_total", "p2p_passed", "p2p_total", "apply_failed")
    return {
        key: data[key]
        for key in keys
        if isinstance(data.get(key), int) and not isinstance(data.get(key), bool)
    }


def _status(results: dict[str, bytes], exit_code: int | None) -> tuple[ScoreStatus, str]:
    reward = _reward(results)
    if "reward" not in reward:
        sentinel = results.get("reward.txt", b"").decode("utf-8", errors="replace").strip()
        return ScoreStatus.VERIFIER_ERROR, (
            f"no reward.json (reward.txt={sentinel or 'absent'}, exit {exit_code})"
        )
    if reward.get("apply_failed"):
        return ScoreStatus.PATCH_NOT_APPLIED, "the patch did not apply to the base commit"
    if reward["reward"] == 1:
        return ScoreStatus.RESOLVED, ""
    if reward["reward"] == 0:
        return ScoreStatus.UNRESOLVED, ""
    return ScoreStatus.VERIFIER_ERROR, f"unexpected reward {reward['reward']}"
