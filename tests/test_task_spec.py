from dataclasses import FrozenInstanceError

import pytest

from agentless_ml.schemas import Benchmark, TaskSpec


def make_task(**overrides: object) -> TaskSpec:
    values = {
        "benchmark": Benchmark.DEEPSWE,
        "benchmark_revision": "benchmark-sha",
        "instance_id": "example__repo-1",
        "language": "python",
        "repository_url": "https://example.test/repo.git",
        "base_commit": "0123456789abcdef",
        "problem_statement": "Correct the faulty behavior.",
        "container_image": "example/task:fixed",
        "container_digest": "sha256:abc",
        "visible_metadata": {"difficulty": "medium", "tags": ["parsing"]},
    }
    values.update(overrides)
    return TaskSpec(**values)  # type: ignore[arg-type]


def test_accepts_agent_visible_task() -> None:
    task = make_task()
    assert task.benchmark is Benchmark.DEEPSWE
    assert task.visible_metadata["difficulty"] == "medium"


@pytest.mark.parametrize("key", ["solution", "test_patch", "gold_patch", "hidden_tests"])
def test_rejects_hidden_answer_keys_recursively(key: str) -> None:
    with pytest.raises(ValueError, match="forbidden agent-visible metadata key"):
        make_task(visible_metadata={"nested": [{key: "secret"}]})


def test_task_and_metadata_mapping_are_immutable() -> None:
    task = make_task()
    with pytest.raises(FrozenInstanceError):
        task.language = "rust"  # type: ignore[misc]
    with pytest.raises(TypeError):
        task.visible_metadata["new"] = "value"  # type: ignore[index]
    assert task.visible_metadata["tags"] == ("parsing",)


def test_rejects_non_json_metadata_value() -> None:
    with pytest.raises(TypeError, match="unsupported metadata value"):
        make_task(visible_metadata={"tags": {"parsing"}})


def test_rejects_invalid_resource_limit() -> None:
    with pytest.raises(ValueError, match="timeout_seconds"):
        make_task(timeout_seconds=0)
