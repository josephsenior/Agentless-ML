"""Safe SWE-bench Pro dataset records to normalized task specifications.

The public dataset stores agent-visible inputs beside gold patches and verifier
material. Callers must project exactly ``SWE_BENCH_PRO_AGENT_COLUMNS`` before
passing a record here. Rejecting additional columns makes an accidental full-row
load fail closed at the benchmark boundary.
"""

from __future__ import annotations

import re
import hashlib
import importlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentless_ml.schemas import Benchmark, TaskSpec


SWE_BENCH_PRO_AGENT_COLUMNS = (
    "repo",
    "instance_id",
    "base_commit",
    "problem_statement",
    "requirements",
    "interface",
    "repo_language",
    "dockerhub_tag",
)

_AGENT_COLUMN_SET = frozenset(SWE_BENCH_PRO_AGENT_COLUMNS)
_REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
_COMMIT = re.compile(r"[0-9a-f]{40}")
_DOCKER_TAG = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}")
_LANGUAGES = {
    "go": "go",
    "js": "javascript",
    "python": "python",
    "ts": "typescript",
}


@dataclass(frozen=True, slots=True)
class SWEbenchProDatasetPin:
    """Immutable identity of one local SWE-bench Pro Parquet split."""

    revision: str
    parquet_sha256: str
    row_count: int

    def __post_init__(self) -> None:
        if not _COMMIT.fullmatch(self.revision):
            raise ValueError("dataset revision must be a full lowercase Git commit")
        if not re.fullmatch(r"[0-9a-f]{64}", self.parquet_sha256):
            raise ValueError("Parquet digest must be a lowercase SHA-256")
        if self.row_count <= 0:
            raise ValueError("dataset row count must be positive")


class SWEbenchProDataset:
    """Read only answer-free columns from a digest-pinned Parquet split."""

    def __init__(self, parquet_path: Path, pin: SWEbenchProDatasetPin) -> None:
        self.parquet_path = Path(parquet_path).resolve(strict=True)
        if not self.parquet_path.is_file():
            raise ValueError("SWE-bench Pro split must be a regular file")
        self.pin = pin

    def _verify_digest(self) -> None:
        digest = hashlib.sha256()
        with self.parquet_path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != self.pin.parquet_sha256:
            raise ValueError("SWE-bench Pro Parquet digest does not match its pin")

    def _safe_records(self) -> tuple[dict[str, Any], ...]:
        self._verify_digest()
        try:
            parquet = importlib.import_module("pyarrow.parquet")
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "reading SWE-bench Pro requires the 'benchmarks' package extra"
            ) from exc
        table = parquet.read_table(
            self.parquet_path,
            columns=list(SWE_BENCH_PRO_AGENT_COLUMNS),
        )
        if table.num_rows != self.pin.row_count:
            raise ValueError("SWE-bench Pro row count does not match its pin")
        records = tuple(table.to_pylist())
        if any(set(record) != _AGENT_COLUMN_SET for record in records):
            raise ValueError("projected SWE-bench Pro schema is incomplete")
        return records

    def load_tasks(
        self,
        *,
        language: str | None = None,
        instance_ids: tuple[str, ...] | None = None,
        container_digests: Mapping[str, str] | None = None,
    ) -> tuple[TaskSpec, ...]:
        """Load normalized tasks in dataset order from the safe projection."""
        requested = None if instance_ids is None else frozenset(instance_ids)
        if instance_ids is not None and len(requested) != len(instance_ids):
            raise ValueError("instance_ids must not contain duplicates")
        digests = container_digests or {}
        tasks: list[TaskSpec] = []
        seen: set[str] = set()
        for record in self._safe_records():
            instance_id = _required_string(record, "instance_id")
            if instance_id in seen:
                raise ValueError(f"duplicate SWE-bench Pro instance: {instance_id}")
            seen.add(instance_id)
            if requested is not None and instance_id not in requested:
                continue
            task = load_swe_bench_pro_task(
                record,
                dataset_revision=self.pin.revision,
                container_digest=digests.get(instance_id),
            )
            if language is None or task.language == language.casefold():
                tasks.append(task)
        if requested is not None:
            missing = requested - {task.instance_id for task in tasks}
            if missing:
                names = ", ".join(sorted(missing))
                raise KeyError(f"SWE-bench Pro instances not found: {names}")
        return tuple(tasks)


def _required_string(record: Mapping[str, Any], name: str) -> str:
    value = record.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"SWE-bench Pro field {name!r} must be a nonempty string")
    return value.strip()


def _optional_section(record: Mapping[str, Any], name: str) -> str | None:
    value = record.get(name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"SWE-bench Pro field {name!r} must be a string or null")
    value = value.strip()
    return value or None


def _format_problem(record: Mapping[str, Any]) -> str:
    sections = [_required_string(record, "problem_statement")]
    requirements = _optional_section(record, "requirements")
    interface = _optional_section(record, "interface")
    if requirements:
        sections.append(f"Requirements:\n{requirements}")
    if interface:
        sections.append(f"New interfaces introduced:\n{interface}")
    return "\n\n".join(sections)


def load_swe_bench_pro_task(
    record: Mapping[str, Any],
    *,
    dataset_revision: str,
    container_digest: str | None = None,
    timeout_seconds: int = 1_800,
    memory_megabytes: int = 8_192,
) -> TaskSpec:
    """Normalize one deliberately projected, answer-free dataset record."""
    if not isinstance(record, Mapping):
        raise TypeError("SWE-bench Pro record must be a mapping")
    keys = set(record)
    if any(not isinstance(key, str) for key in keys):
        raise TypeError("SWE-bench Pro record keys must be strings")
    unexpected = keys - _AGENT_COLUMN_SET
    missing = _AGENT_COLUMN_SET - keys
    if unexpected:
        names = ", ".join(sorted(unexpected))
        raise ValueError(f"unprojected SWE-bench Pro fields: {names}")
    if missing:
        names = ", ".join(sorted(missing))
        raise ValueError(f"missing SWE-bench Pro fields: {names}")
    if not isinstance(dataset_revision, str) or not _COMMIT.fullmatch(
        dataset_revision.strip()
    ):
        raise ValueError("dataset_revision must be a full Git commit")

    repository = _required_string(record, "repo")
    if not _REPOSITORY.fullmatch(repository):
        raise ValueError("repo must have the form owner/name")
    base_commit = _required_string(record, "base_commit")
    if not _COMMIT.fullmatch(base_commit):
        raise ValueError("base_commit must be a full lowercase Git commit")
    docker_tag = _required_string(record, "dockerhub_tag")
    if not _DOCKER_TAG.fullmatch(docker_tag):
        raise ValueError("dockerhub_tag is not a valid Docker tag")
    raw_language = _required_string(record, "repo_language").casefold()
    try:
        language = _LANGUAGES[raw_language]
    except KeyError as exc:
        raise ValueError(f"unsupported SWE-bench Pro language: {raw_language}") from exc

    return TaskSpec(
        benchmark=Benchmark.SWE_BENCH_PRO,
        benchmark_revision=dataset_revision.strip(),
        instance_id=_required_string(record, "instance_id"),
        language=language,
        repository_url=f"https://github.com/{repository}.git",
        base_commit=base_commit,
        problem_statement=_format_problem(record),
        container_image=f"jefzda/sweap-images:{docker_tag}",
        container_digest=container_digest,
        timeout_seconds=timeout_seconds,
        memory_megabytes=memory_megabytes,
        visible_metadata={"repository": repository},
    )
