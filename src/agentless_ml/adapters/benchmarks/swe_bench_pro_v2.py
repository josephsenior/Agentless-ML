"""Adapt one SWE-bench Pro V2 Harbor task without reading verifier material.

V2's task.toml does not record the repository or base commit. For the initial
smoke slice, those come from the same instance in the digest-pinned V1 dataset;
the V2 image checkout must be checked against that commit before a run.
"""

from __future__ import annotations

import hashlib
import re
import tomllib
from dataclasses import replace
from pathlib import Path

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


def _read_visible(directory: Path, name: str, expected_sha256: str) -> str:
    if name not in VISIBLE_FILES:
        raise ValueError(f"not an agent-visible V2 file: {name}")
    if not _SHA256.fullmatch(expected_sha256):
        raise ValueError(f"invalid SHA-256 pin for {name}")
    path = directory / name
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"V2 task file must be regular: {path}")
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != expected_sha256:
        raise ValueError(f"V2 task file does not match its pin: {name}")
    return content.decode("utf-8").replace("\r\n", "\n")


def load_swe_bench_pro_v2_task(
    task_directory: Path,
    v1_task: TaskSpec,
    *,
    dataset_revision: str,
    visible_sha256: dict[str, str],
    container_digest: str,
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
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", container_digest):
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
