"""Safe DeepSWE task directories to normalized task specifications.

A DeepSWE task directory (Harbor format) keeps agent inputs beside held-out
answers: ``instruction.md`` and ``task.toml`` are agent-visible, while
``solution/`` (reference patch) and ``tests/`` (hidden tests, fail-to-pass test
IDs, grader) are verifier material. The loader opens only the two visible files
by explicit path and never lists, opens or hashes anything under ``tests/`` or
``solution/``.
"""

from __future__ import annotations

import hashlib
import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentless_ml.schemas import Benchmark, TaskSpec

DEEPSWE_AGENT_FIELDS = (
    "task_id",
    "language",
    "repository_url",
    "base_commit",
    "instruction",
    "docker_image",
    "agent_timeout_seconds",
    "memory_megabytes",
)
DEEPSWE_VISIBLE_FILES = ("task.toml", "instruction.md")

# Harbor delivers work by collecting the agent's commits; Agentless-ML exports
# the selected patch itself, so this trailing delivery instruction is removed.
HARBOR_DELIVERY_INSTRUCTION = (
    "IMPORTANT: Please work on this in a new branch from main and commit "
    "everything when you are done."
)

_FIELD_SET = frozenset(DEEPSWE_AGENT_FIELDS)
_SCHEMA_VERSION = "1.3"
# Every top-level table this loader knows holds no answers. A new table could,
# so its presence fails closed until someone reviews it.
_KNOWN_TABLES = frozenset(
    {
        "schema_version",
        "artifacts",
        "task",
        "metadata",
        "verifier",
        "agent",
        "environment",
        "solution",
    }
)
_TASK_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,127}")
_COMMIT = re.compile(r"[0-9a-f]{40}")
# A few tasks record an abbreviated commit, exactly as their own environment
# Dockerfile and verifier do. Workspaces need the full immutable ID.
_COMMIT_PREFIX = re.compile(r"[0-9a-f]{7,40}")
_REPOSITORY_URL = re.compile(
    r"https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?"
)
_IMAGE = re.compile(r"[a-z0-9][a-z0-9._/-]{0,254}:[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}")
_LANGUAGES = frozenset({"go", "javascript", "python", "rust", "typescript"})


@dataclass(frozen=True, slots=True)
class DeepSWEDatasetPin:
    """Immutable identity of a local DeepSWE task corpus.

    ``agent_files_sha256`` covers only the agent-visible files of every task, so
    verifying the pin never requires reading held-out material.
    """

    revision: str
    agent_files_sha256: str
    task_count: int

    def __post_init__(self) -> None:
        if not _COMMIT.fullmatch(self.revision):
            raise ValueError("dataset revision must be a full lowercase Git commit")
        if not re.fullmatch(r"[0-9a-f]{64}", self.agent_files_sha256):
            raise ValueError("agent-file digest must be a lowercase SHA-256")
        if self.task_count <= 0:
            raise ValueError("task count must be positive")


def _read_visible(task_directory: Path, name: str) -> str:
    if name not in DEEPSWE_VISIBLE_FILES:
        raise ValueError(f"not an agent-visible DeepSWE file: {name}")
    path = task_directory / name
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"DeepSWE task file must be a regular file: {path}")
    # Git on Windows may check text out with CRLF; the corpus identity must not
    # depend on the machine that cloned it.
    return path.read_bytes().decode("utf-8").replace("\r\n", "\n")


def agent_files_digest(task_directories: tuple[Path, ...]) -> str:
    """SHA-256 over every task's visible files, in task-name order."""
    digest = hashlib.sha256()
    for directory in sorted(task_directories, key=lambda path: path.name):
        for name in DEEPSWE_VISIBLE_FILES:
            content = _read_visible(directory, name).encode("utf-8")
            digest.update(f"{directory.name}/{name}\0{len(content)}\0".encode())
            digest.update(content)
    return digest.hexdigest()


def project_deepswe_task(task_directory: Path) -> dict[str, Any]:
    """Return exactly ``DEEPSWE_AGENT_FIELDS`` from one task directory."""
    directory = Path(task_directory)
    try:
        manifest = tomllib.loads(_read_visible(directory, "task.toml"))
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"invalid DeepSWE task.toml in {directory.name}: {exc}") from exc
    if manifest.get("schema_version") != _SCHEMA_VERSION:
        raise ValueError(
            f"unsupported DeepSWE schema_version in {directory.name}: "
            f"{manifest.get('schema_version')!r}"
        )
    unknown = set(manifest) - _KNOWN_TABLES
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ValueError(f"unreviewed DeepSWE task.toml tables in {directory.name}: {names}")

    metadata = _table(manifest, "metadata")
    agent = _table(manifest, "agent")
    environment = _table(manifest, "environment")
    if agent.get("network_mode") != "no-network":
        raise ValueError(f"DeepSWE task {directory.name} requires network access")
    if environment.get("os") != "linux":
        raise ValueError(f"DeepSWE task {directory.name} is not a Linux environment")
    return {
        "task_id": metadata.get("task_id"),
        "language": metadata.get("language"),
        "repository_url": metadata.get("repository_url"),
        "base_commit": metadata.get("base_commit_hash"),
        "instruction": _read_visible(directory, "instruction.md"),
        "docker_image": environment.get("docker_image"),
        "agent_timeout_seconds": agent.get("timeout_sec"),
        "memory_megabytes": environment.get("memory_mb"),
    }


def _table(manifest: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    value = manifest.get(name)
    if not isinstance(value, Mapping):
        raise ValueError(f"DeepSWE task.toml is missing the [{name}] table")
    return value


class DeepSWEDataset:
    """Load answer-free tasks from a digest-pinned local DeepSWE checkout."""

    def __init__(self, tasks_root: Path, pin: DeepSWEDatasetPin) -> None:
        self.tasks_root = Path(tasks_root).resolve(strict=True)
        if not self.tasks_root.is_dir():
            raise ValueError("DeepSWE tasks root must be a directory")
        self.pin = pin

    def _task_directories(self) -> tuple[Path, ...]:
        directories = tuple(
            sorted(
                (path for path in self.tasks_root.iterdir() if path.is_dir()),
                key=lambda path: path.name,
            )
        )
        if len(directories) != self.pin.task_count:
            raise ValueError("DeepSWE task count does not match its pin")
        if agent_files_digest(directories) != self.pin.agent_files_sha256:
            raise ValueError("DeepSWE agent-visible files do not match their pin")
        return directories

    def load_tasks(
        self,
        *,
        language: str | None = None,
        task_ids: tuple[str, ...] | None = None,
        container_digests: Mapping[str, str] | None = None,
        resolved_base_commits: Mapping[str, str] | None = None,
    ) -> tuple[TaskSpec, ...]:
        """Load normalized tasks in task-name order.

        ``resolved_base_commits`` maps task IDs to the full commit their
        abbreviated ``base_commit_hash`` resolves to.
        """
        requested = None if task_ids is None else frozenset(task_ids)
        if task_ids is not None and len(requested) != len(task_ids):
            raise ValueError("task_ids must not contain duplicates")
        digests = container_digests or {}
        resolved = resolved_base_commits or {}
        tasks: list[TaskSpec] = []
        for directory in self._task_directories():
            if requested is not None and directory.name not in requested:
                continue
            record = project_deepswe_task(directory)
            if record["task_id"] != directory.name:
                raise ValueError(
                    f"DeepSWE task_id {record['task_id']!r} does not match "
                    f"its directory {directory.name!r}"
                )
            task = load_deepswe_task(
                record,
                dataset_revision=self.pin.revision,
                container_digest=digests.get(directory.name),
                resolved_base_commit=resolved.get(directory.name),
            )
            if language is None or task.language == language.casefold():
                tasks.append(task)
        if requested is not None:
            missing = requested - {task.instance_id for task in tasks}
            if missing:
                names = ", ".join(sorted(missing))
                raise KeyError(f"DeepSWE tasks not found: {names}")
        return tuple(tasks)


def _string(record: Mapping[str, Any], name: str) -> str:
    value = record.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"DeepSWE field {name!r} must be a nonempty string")
    return value.strip()


def _positive_number(record: Mapping[str, Any], name: str) -> int:
    value = record.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"DeepSWE field {name!r} must be a positive number")
    if value != int(value):
        raise ValueError(f"DeepSWE field {name!r} must be a whole number")
    return int(value)


def format_deepswe_instruction(instruction: str) -> str:
    """The instruction without Harbor's trailing commit-delivery line."""
    text = instruction.replace("\r\n", "\n").rstrip()
    lines = text.split("\n")
    if lines and lines[-1].strip() == HARBOR_DELIVERY_INSTRUCTION:
        text = "\n".join(lines[:-1]).rstrip()
    if not text:
        raise ValueError("DeepSWE instruction must not be empty")
    return text


def load_deepswe_task(
    record: Mapping[str, Any],
    *,
    dataset_revision: str,
    container_digest: str | None = None,
    resolved_base_commit: str | None = None,
) -> TaskSpec:
    """Normalize one projected, answer-free DeepSWE record.

    An abbreviated ``base_commit`` needs ``resolved_base_commit``: the full commit
    it names. Resolution happens against the real repository, outside this
    function, and is pinned by the caller.
    """
    if not isinstance(record, Mapping):
        raise TypeError("DeepSWE record must be a mapping")
    keys = set(record)
    if any(not isinstance(key, str) for key in keys):
        raise TypeError("DeepSWE record keys must be strings")
    unexpected = keys - _FIELD_SET
    missing = _FIELD_SET - keys
    if unexpected:
        raise ValueError(f"unprojected DeepSWE fields: {', '.join(sorted(unexpected))}")
    if missing:
        raise ValueError(f"missing DeepSWE fields: {', '.join(sorted(missing))}")
    if not isinstance(dataset_revision, str) or not _COMMIT.fullmatch(
        dataset_revision.strip()
    ):
        raise ValueError("dataset_revision must be a full Git commit")

    task_id = _string(record, "task_id")
    if not _TASK_ID.fullmatch(task_id):
        raise ValueError("DeepSWE task_id must be lowercase letters, digits and hyphens")
    language = _string(record, "language").casefold()
    if language not in _LANGUAGES:
        raise ValueError(f"unsupported DeepSWE language: {language}")
    repository_match = _REPOSITORY_URL.fullmatch(_string(record, "repository_url"))
    if repository_match is None:
        raise ValueError("DeepSWE repository_url must be a GitHub repository URL")
    repository = repository_match.group(1)
    recorded_commit = _string(record, "base_commit")
    if not _COMMIT_PREFIX.fullmatch(recorded_commit):
        raise ValueError("DeepSWE base_commit must be a lowercase Git commit or prefix")
    if resolved_base_commit is None:
        if not _COMMIT.fullmatch(recorded_commit):
            raise ValueError(
                f"DeepSWE task {task_id} records abbreviated commit {recorded_commit}; "
                "supply its pinned full commit as resolved_base_commit"
            )
        base_commit = recorded_commit
    else:
        if not _COMMIT.fullmatch(resolved_base_commit):
            raise ValueError("resolved_base_commit must be a full lowercase Git commit")
        if not resolved_base_commit.startswith(recorded_commit):
            raise ValueError(
                f"resolved commit {resolved_base_commit} does not start with the "
                f"recorded DeepSWE commit {recorded_commit}"
            )
        base_commit = resolved_base_commit
    image = _string(record, "docker_image")
    if not _IMAGE.fullmatch(image):
        raise ValueError("DeepSWE docker_image must be a tagged image reference")

    return TaskSpec(
        benchmark=Benchmark.DEEPSWE,
        benchmark_revision=dataset_revision.strip(),
        instance_id=task_id,
        language=language,
        repository_url=f"https://github.com/{repository}.git",
        base_commit=base_commit,
        problem_statement=format_deepswe_instruction(_string(record, "instruction")),
        container_image=image,
        container_digest=container_digest,
        timeout_seconds=_positive_number(record, "agent_timeout_seconds"),
        memory_megabytes=_positive_number(record, "memory_megabytes"),
        visible_metadata={"repository": repository},
    )
