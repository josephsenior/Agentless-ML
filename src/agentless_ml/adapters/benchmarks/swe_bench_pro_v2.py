"""Adapt SWE-bench Pro V2 Harbor tasks without reading verifier material.

V2's task.toml does not record the repository or base commit. Those come from
the same instance in the digest-pinned V1 dataset. Before executing a task,
the V2 image checkout must be checked against that commit.
"""

from __future__ import annotations

import hashlib
import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path

from agentless_ml.adapters.benchmarks.swe_bench_pro import SWEbenchProDataset
from agentless_ml.schemas import Benchmark, TaskSpec

VISIBLE_FILES = ("task.toml", "instruction.md")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_REVISION = re.compile(r"[0-9a-f]{40}")
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


def _visible_bytes(directory: Path, name: str) -> bytes:
    if name not in VISIBLE_FILES:
        raise ValueError(f"not an agent-visible V2 file: {name}")
    path = directory / name
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"V2 task file must be regular: {path}")
    return path.read_bytes()


def _read_visible(directory: Path, name: str, expected_sha256: str) -> str:
    if not _SHA256.fullmatch(expected_sha256):
        raise ValueError(f"invalid SHA-256 pin for {name}")
    content = _visible_bytes(directory, name)
    if hashlib.sha256(content).hexdigest() != expected_sha256:
        raise ValueError(f"V2 task file does not match its pin: {name}")
    return content.decode("utf-8").replace("\r\n", "\n")


def v2_visible_corpus_digest(task_directories: tuple[Path, ...]) -> str:
    """Hash only instruction.md and task.toml, independent of line endings."""
    digest = hashlib.sha256()
    names: set[str] = set()
    for directory in sorted(task_directories, key=lambda path: path.name):
        if directory.name in names:
            raise ValueError(f"duplicate V2 task directory: {directory.name}")
        names.add(directory.name)
        for name in VISIBLE_FILES:
            content = _visible_bytes(directory, name).replace(b"\r\n", b"\n")
            digest.update(f"{directory.name}/{name}\0{len(content)}\0".encode())
            digest.update(content)
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class SWEbenchProV2DatasetPin:
    revision: str
    visible_files_sha256: str
    task_count: int

    def __post_init__(self) -> None:
        if not _REVISION.fullmatch(self.revision):
            raise ValueError("V2 dataset revision must be a full Git commit")
        if not _SHA256.fullmatch(self.visible_files_sha256):
            raise ValueError("V2 visible-file digest must be a SHA-256")
        if self.task_count <= 0:
            raise ValueError("V2 task count must be positive")


class SWEbenchProV2Dataset:
    """Load a digest-pinned V2 corpus using the pinned V1 metadata projection."""

    def __init__(
        self,
        tasks_root: Path,
        pin: SWEbenchProV2DatasetPin,
        v1_dataset: SWEbenchProDataset,
    ) -> None:
        self.tasks_root = Path(tasks_root).resolve(strict=True)
        if not self.tasks_root.is_dir():
            raise ValueError("V2 tasks root must be a directory")
        self.pin = pin
        self.v1_dataset = v1_dataset

    def load_tasks(
        self,
        *,
        language: str | None = None,
        instance_ids: tuple[str, ...] | None = None,
        container_digests: Mapping[str, str] | None = None,
    ) -> tuple[TaskSpec, ...]:
        """Verify the complete visible corpus before selecting requested tasks."""
        directories = tuple(
            sorted(
                (path for path in self.tasks_root.iterdir() if path.is_dir()),
                key=lambda path: path.name,
            )
        )
        if len(directories) != self.pin.task_count:
            raise ValueError("V2 task count does not match its pin")
        if v2_visible_corpus_digest(directories) != self.pin.visible_files_sha256:
            raise ValueError("V2 agent-visible files do not match their pin")
        base_tasks = {task.instance_id: task for task in self.v1_dataset.load_tasks()}
        requested = None if instance_ids is None else frozenset(instance_ids)
        if instance_ids is not None and len(requested) != len(instance_ids):
            raise ValueError("instance_ids must not contain duplicates")
        digests = container_digests or {}
        tasks: list[TaskSpec] = []
        for directory in directories:
            if directory.name not in base_tasks:
                raise ValueError(f"V2 task has no pinned V1 metadata: {directory.name}")
            if requested is not None and directory.name not in requested:
                continue
            visible_sha256 = {
                name: hashlib.sha256(_visible_bytes(directory, name)).hexdigest()
                for name in VISIBLE_FILES
            }
            task = load_swe_bench_pro_v2_task(
                directory,
                base_tasks[directory.name],
                dataset_revision=self.pin.revision,
                visible_sha256=visible_sha256,
                container_digest=digests.get(directory.name),
            )
            if language is None or task.language == language.casefold():
                tasks.append(task)
        if requested is not None:
            missing = requested - {task.instance_id for task in tasks}
            if missing:
                raise KeyError(f"V2 tasks not found: {', '.join(sorted(missing))}")
        return tuple(tasks)


def load_swe_bench_pro_v2_task(
    task_directory: Path,
    v1_task: TaskSpec,
    *,
    dataset_revision: str,
    visible_sha256: Mapping[str, str],
    container_digest: str | None = None,
) -> TaskSpec:
    """Load only V2's agent-visible files, with pinned V1 repo/commit metadata."""
    directory = Path(task_directory)
    if v1_task.benchmark is not Benchmark.SWE_BENCH_PRO:
        raise ValueError("base metadata must be a SWE-bench Pro task")
    if directory.name != v1_task.instance_id:
        raise ValueError("V1 and V2 instance IDs differ")
    if not _REVISION.fullmatch(dataset_revision):
        raise ValueError("V2 dataset_revision must be a full Git commit")
    if set(visible_sha256) != set(VISIBLE_FILES):
        raise ValueError("V2 pin must contain exactly the two visible files")
    if container_digest is not None and not re.fullmatch(
        r"sha256:[0-9a-f]{64}", container_digest
    ):
        raise ValueError("V2 container_digest must be a SHA-256 image digest")

    manifest = tomllib.loads(
        _read_visible(directory, "task.toml", visible_sha256["task.toml"])
    )
    instruction = _read_visible(
        directory, "instruction.md", visible_sha256["instruction.md"]
    )
    if manifest.get("schema_version") != "1.4":
        raise ValueError("unsupported SWE-bench Pro V2 task schema")
    if set(manifest) - _KNOWN_TABLES:
        raise ValueError("unreviewed SWE-bench Pro V2 task.toml tables")
    task = manifest.get("task")
    agent = manifest.get("agent")
    environment = manifest.get("environment")
    if not all(isinstance(table, dict) for table in (task, agent, environment)):
        raise ValueError("V2 task is missing task, agent, or environment settings")
    if task.get("name") != f"swebench-pro/{directory.name}":
        raise ValueError("V2 task name does not match its directory")
    if agent.get("network_mode") != "no-network" or environment.get("os") != "linux":
        raise ValueError("V2 task needs an offline Linux agent environment")
    image = f"ghcr.io/scaleapi/swe-bench_pro-v2:{directory.name}"
    if environment.get("docker_image") != image:
        raise ValueError("V2 image does not match the task ID")
    timeout = agent.get("timeout_sec")
    memory = environment.get("memory_mb")
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or value <= 0
        or value != int(value)
        for value in (timeout, memory)
    ):
        raise ValueError("V2 task timeout and memory must be positive whole numbers")
    if not instruction.strip():
        raise ValueError("V2 instruction must not be empty")

    return replace(
        v1_task,
        benchmark_revision=dataset_revision,
        problem_statement=instruction.strip(),
        container_image=image,
        container_digest=container_digest,
        timeout_seconds=int(timeout),
        memory_megabytes=int(memory),
        visible_metadata={**v1_task.visible_metadata, "release": "v2"},
    )
