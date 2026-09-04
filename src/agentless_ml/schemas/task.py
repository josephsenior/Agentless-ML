"""Normalized agent-visible task input.

Hidden benchmark answers and verifier material have no fields in ``TaskSpec``.
Adapters must reject suspicious metadata keys before constructing a task.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any


class Benchmark(StrEnum):
    CONTROLLED_FIXTURE = "controlled-fixture"
    DEEPSWE = "deepswe"
    SWE_BENCH_PRO = "swe-bench-pro"


_FORBIDDEN_METADATA_KEYS = frozenset(
    {
        "gold_patch",
        "hidden_tests",
        "reference_patch",
        "reference_solution",
        "solution",
        "solution_patch",
        "test_patch",
    }
)


def _freeze_visible_value(value: Any, location: str = "visible_metadata") -> Any:
    """Reject answer-like fields and return deeply immutable JSON-like data."""
    if isinstance(value, Mapping):
        frozen: dict[str, Any] = {}
        for raw_key, child in value.items():
            if not isinstance(raw_key, str):
                raise TypeError(f"metadata key at {location} must be a string")
            key = str(raw_key).casefold()
            if key in _FORBIDDEN_METADATA_KEYS:
                raise ValueError(
                    f"forbidden agent-visible metadata key: {location}.{raw_key}"
                )
            frozen[raw_key] = _freeze_visible_value(child, f"{location}.{raw_key}")
        return MappingProxyType(frozen)
    elif isinstance(value, (list, tuple)):
        return tuple(
            _freeze_visible_value(child, f"{location}[{index}]")
            for index, child in enumerate(value)
        )
    elif value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported metadata value at {location}: {type(value).__name__}")


@dataclass(frozen=True, slots=True)
class TaskSpec:
    benchmark: Benchmark
    benchmark_revision: str
    instance_id: str
    language: str
    repository_url: str
    base_commit: str
    problem_statement: str
    container_image: str
    container_digest: str | None = None
    timeout_seconds: int = 1_800
    memory_megabytes: int = 8_192
    visible_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        required = {
            "benchmark_revision": self.benchmark_revision,
            "instance_id": self.instance_id,
            "language": self.language,
            "repository_url": self.repository_url,
            "base_commit": self.base_commit,
            "problem_statement": self.problem_statement,
            "container_image": self.container_image,
        }
        for name, value in required.items():
            if not value or not value.strip():
                raise ValueError(f"{name} must not be empty")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.memory_megabytes <= 0:
            raise ValueError("memory_megabytes must be positive")
        frozen_metadata = _freeze_visible_value(self.visible_metadata)
        object.__setattr__(self, "visible_metadata", frozen_metadata)
