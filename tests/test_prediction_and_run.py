from datetime import UTC, datetime

import pytest

from agentless_ml.schemas import RunRecord, ValidationResult, ValidationStatus


def test_validation_distinguishes_infrastructure_outcomes() -> None:
    result = ValidationResult(
        status=ValidationStatus.TIMEOUT,
        command=("python", "-m", "pytest"),
        duration_seconds=30.0,
    )
    assert result.status is ValidationStatus.TIMEOUT
    assert result.exit_code is None


def test_run_record_requires_timezone_aware_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        RunRecord(
            run_id="run-1",
            condition="agentless-ml",
            instance_id="task-1",
            started_at=datetime(2026, 8, 31),
            implementation_revision="impl-sha",
            benchmark_revision="bench-sha",
            harness_revision="harness-sha",
            container_digest="sha256:abc",
            model_name="provider/model",
            model_calls=0,
            input_tokens=0,
            output_tokens=0,
            wall_time_seconds=0,
        )


def test_run_record_accepts_zero_usage_before_execution() -> None:
    record = RunRecord(
        run_id="run-1",
        condition="agentless-ml",
        instance_id="task-1",
        started_at=datetime.now(UTC),
        implementation_revision="impl-sha",
        benchmark_revision="bench-sha",
        harness_revision="harness-sha",
        container_digest="sha256:abc",
        model_name="provider/model",
        model_calls=0,
        input_tokens=0,
        output_tokens=0,
        wall_time_seconds=0,
    )
    assert record.infrastructure_status == "ok"
