"""Post-selection replay with the pinned SWE-bench Pro V2 verifier.

The selected patch is replayed in a fresh official task image. Verifier files
are read from the pinned benchmark commit, never through a workflow adapter.
This local Docker path needs empty/reference gate checks before its results can
be treated as equivalent to the official Harbor re-grade.
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
from pathlib import Path

from agentless_ml.schemas import Benchmark, TaskSpec
from agentless_ml.scoring.deepswe import ScoreStatus, ScoringError, _docker, _results

VERIFIER_FILES = (
    "test.sh",
    "run_script.sh",
    "parser.py",
    "config.json",
    "test_patch.patch",
)
_REVISION = re.compile(r"[0-9a-f]{40}")
_TASK_ID = re.compile(r"instance_[A-Za-z0-9_.-]+")
_REWARD = frozenset({"0", "1"})


@dataclass(frozen=True, slots=True)
class SWEbenchProV2Score:
    instance_id: str
    status: ScoreStatus
    reward: int | None
    image_id: str
    patch_sha256: str
    dataset_revision: str
    artifact_directory: str
    message: str = ""

    @property
    def resolved(self) -> bool:
        return self.status is ScoreStatus.RESOLVED


class SWEbenchProV2Verifier:
    """Replay a final patch with verifier blobs from one pinned V2 commit."""

    def __init__(self, repository: Path, revision: str) -> None:
        if not _REVISION.fullmatch(revision):
            raise ValueError("revision must be a full lowercase Git commit")
        self.repository = Path(repository).resolve(strict=True)
        self.revision = revision
        resolved = (
            self._git("rev-parse", "--verify", revision + "^{commit}").decode().strip()
        )
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
            raise ValueError(f"not a SWE-bench Pro V2 instance ID: {task_id!r}")
        return self._git("show", f"{self.revision}:v2/tasks/{task_id}/{relative}")

    def _settings(self, task: TaskSpec) -> tuple[float, int, float, str]:
        if task.benchmark is not Benchmark.SWE_BENCH_PRO:
            raise ValueError("not a SWE-bench Pro task")
        if task.benchmark_revision != self.revision:
            raise ScoringError("task and verifier revisions differ")
        manifest = tomllib.loads(self._blob(task.instance_id, "task.toml").decode())
        environment = manifest["environment"]
        verifier = manifest["verifier"]
        if environment.get("docker_image") != task.container_image:
            raise ScoringError("verifier image differs from the task image")
        dockerfile = self._blob(task.instance_id, "environment/Dockerfile").decode()
        lines = tuple(
            line.strip()
            for line in dockerfile.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
        if lines != (f"FROM {task.container_image}",):
            raise ScoringError("V2 environment Dockerfile has an unreviewed shape")
        network = verifier.get("network_mode")
        if network not in {"public", "no-network"}:
            raise ScoringError("unsupported V2 verifier network mode")
        cpus = environment.get("cpus")
        memory = environment.get("memory_mb")
        timeout = verifier.get("timeout_sec")
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value <= 0
            for value in (cpus, memory, timeout)
        ):
            raise ScoringError("invalid V2 verifier resource limits")
        return float(cpus), int(memory), float(timeout), network

    def reference_patch_for_harness_validation(self, task: TaskSpec) -> str:
        """The gold patch is available only to validate this post-selection scorer."""
        return self._blob(task.instance_id, "solution/gold_patch.diff").decode("utf-8")

    def score(
        self,
        task: TaskSpec,
        patch: str,
        artifact_root: Path,
        *,
        timeout_seconds: float | None = None,
    ) -> SWEbenchProV2Score:
        if not task.container_digest:
            raise ScoringError(
                f"{task.instance_id}: task image is not pinned by digest"
            )
        cpus, memory, limit, network = self._settings(task)
        timeout = limit if timeout_seconds is None else timeout_seconds
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout_seconds must be finite and positive")
        files = {
            name: self._blob(task.instance_id, f"tests/{name}")
            for name in VERIFIER_FILES
        }
        inspected = json.loads(
            _docker("image", "inspect", task.container_image, timeout=60).stdout
        )[0]
        image_id = inspected["Id"]
        if image_id != task.container_digest:
            raise ScoringError(
                f"{task.container_image} is {image_id}, not the pinned {task.container_digest}"
            )

        patch_bytes = patch.encode("utf-8")
        name = "agentless-ml-v2-verifier-" + uuid.uuid4().hex
        artifacts = Path(artifact_root).resolve() / name
        artifacts.mkdir(parents=True)
        reward: int | None = None
        status = ScoreStatus.VERIFIER_ERROR
        message = ""
        exit_code: int | None = None
        created = False
        command = (
            "cd /app 2>/dev/null || cd /testbed || exit 20; "
            f'test "$(git rev-parse HEAD)" = "{task.base_commit}" || exit 21; '
            "if [ -s /tmp/model.patch ]; then "
            "git apply --verbose /tmp/model.patch || "
            "git apply --3way /tmp/model.patch || "
            "patch --fuzz=3 -p1 -i /tmp/model.patch || exit 30; fi; "
            "bash /tests/test.sh"
        )
        try:
            _docker(
                "create",
                "--name",
                name,
                f"--network={'bridge' if network == 'public' else 'none'}",
                f"--cpus={cpus:g}",
                f"--memory={memory}m",
                f"--memory-swap={memory}m",
                "--pids-limit=4096",
                "--security-opt=no-new-privileges",
                "--pull=never",
                "--entrypoint",
                "bash",
                image_id,
                "-c",
                command,
                timeout=60,
            )
            created = True
            _docker(
                "cp", "-", f"{name}:/", data=_inputs(files, patch_bytes), timeout=120
            )
            try:
                run = _docker("start", "--attach", name, timeout=timeout, check=False)
                exit_code = run.returncode
                (artifacts / "verifier-stdout.txt").write_bytes(run.stdout + run.stderr)
            except subprocess.TimeoutExpired:
                _docker("kill", name, timeout=60, check=False)
                status, message = ScoreStatus.TIMEOUT, f"verifier exceeded {timeout:g}s"
            else:
                exported = _docker(
                    "cp", f"{name}:/logs/verifier", "-", timeout=120, check=False
                )
                results = _results(exported.stdout) if exported.returncode == 0 else {}
                reward_bytes = results.get("reward.txt", b"").strip()
                if reward_bytes.decode("ascii", errors="replace") in _REWARD:
                    reward = int(reward_bytes)
                    if (reward == 1) != (exit_code == 0):
                        status, message = (
                            ScoreStatus.VERIFIER_ERROR,
                            f"reward.txt and verifier exit code disagree ({exit_code})",
                        )
                    else:
                        status = (
                            ScoreStatus.RESOLVED if reward else ScoreStatus.UNRESOLVED
                        )
                        (artifacts / "reward.txt").write_bytes(reward_bytes + b"\n")
                elif exit_code == 30:
                    status, message = (
                        ScoreStatus.PATCH_NOT_APPLIED,
                        "patch did not apply",
                    )
                else:
                    message = f"missing or invalid reward.txt (exit {exit_code})"
        except (
            ScoringError,
            OSError,
            subprocess.TimeoutExpired,
            ValueError,
            KeyError,
        ) as exc:
            status, message = ScoreStatus.VERIFIER_ERROR, str(exc)[:2000]
        finally:
            if created:
                _docker("rm", "--force", "--volumes", name, timeout=60, check=False)

        score = SWEbenchProV2Score(
            instance_id=task.instance_id,
            status=status,
            reward=reward,
            image_id=image_id,
            patch_sha256=hashlib.sha256(patch_bytes).hexdigest(),
            dataset_revision=self.revision,
            artifact_directory=str(artifacts),
            message=message,
        )
        (artifacts / "score.json").write_text(
            json.dumps(
                {
                    **asdict(score),
                    "status": status.value,
                    "verifier_exit_code": exit_code,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return score


def _inputs(files: dict[str, bytes], patch: bytes) -> bytes:
    """Create the verifier-only files and patch input for a fresh container."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as archive:
        entries = [("tests", None, 0o755), ("tmp", None, 0o1777)]
        entries += [
            (
                f"tests/{name}",
                content,
                0o755 if name in {"test.sh", "run_script.sh"} else 0o644,
            )
            for name, content in files.items()
        ]
        entries.append(("tmp/model.patch", patch, 0o644))
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
