"""Minimal reproducibility record shared by experimental conditions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class RunRecord:
    run_id: str
    condition: str
    instance_id: str
    started_at: datetime
    implementation_revision: str
    benchmark_revision: str
    harness_revision: str
    container_digest: str
    model_name: str
    model_calls: int
    input_tokens: int
    output_tokens: int
    wall_time_seconds: float
    final_patch_sha256: str | None = None
    infrastructure_status: str = "ok"

    def __post_init__(self) -> None:
        required = (
            self.run_id,
            self.condition,
            self.instance_id,
            self.implementation_revision,
            self.benchmark_revision,
            self.harness_revision,
            self.container_digest,
            self.model_name,
            self.infrastructure_status,
        )
        if not all(value.strip() for value in required):
            raise ValueError("run identity and provenance fields must not be empty")
        counters = (self.model_calls, self.input_tokens, self.output_tokens)
        if any(value < 0 for value in counters) or self.wall_time_seconds < 0:
            raise ValueError("run counters and duration must not be negative")
        if self.started_at.tzinfo is None:
            raise ValueError("started_at must be timezone-aware")
