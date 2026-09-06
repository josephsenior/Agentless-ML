import json
from pathlib import Path

import pytest

from agentless_ml.adapters.benchmarks import (
    SWE_BENCH_PRO_AGENT_COLUMNS,
    load_swe_bench_pro_task,
)
from agentless_ml.schemas import Benchmark


DATASET_REVISION = "7ab5114912baf22bb098818e604c02fe7ad2c11f"
EXPERIMENT = (
    Path(__file__).parents[1]
    / "experiments"
    / "swe_bench_pro"
    / "qutebrowser_qtlog"
)


def safe_record(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "repo": "qutebrowser/qutebrowser",
        "instance_id": "instance_qutebrowser__qutebrowser-example-v1",
        "base_commit": "ebfe9b7aa0c4ba9d451f993e08955004aaec4345",
        "problem_statement": "Move the Qt warning filter.",
        "requirements": "Preserve its behavior.",
        "interface": "hide_qt_warning(pattern: str)",
        "repo_language": "python",
        "dockerhub_tag": "qutebrowser.qutebrowser-example-v1",
    }
    record.update(overrides)
    return record


def test_agent_columns_exclude_answers_and_verifier_material() -> None:
    assert set(SWE_BENCH_PRO_AGENT_COLUMNS).isdisjoint(
        {"patch", "test_patch", "fail_to_pass", "pass_to_pass"}
    )


def test_pinned_real_task_fixture_is_exactly_the_safe_projection() -> None:
    manifest = json.loads((EXPERIMENT / "task.json").read_text(encoding="utf-8"))
    assert set(manifest["record"]) == set(SWE_BENCH_PRO_AGENT_COLUMNS)

    task = load_swe_bench_pro_task(
        manifest["record"],
        dataset_revision=manifest["dataset_revision"],
        container_digest=manifest["container_digest"],
    )
    assert task.instance_id.startswith("instance_qutebrowser__qutebrowser-")
    assert task.base_commit == "ebfe9b7aa0c4ba9d451f993e08955004aaec4345"
    assert task.container_digest == (
        "sha256:bca2bc90cbe20acca25e9b5e2e96aa751a231a5b6f8f5bc7b7ea3a7b7d449758"
    )


def test_normalizes_projected_record() -> None:
    task = load_swe_bench_pro_task(
        safe_record(), dataset_revision=DATASET_REVISION
    )

    assert task.benchmark is Benchmark.SWE_BENCH_PRO
    assert task.repository_url == "https://github.com/qutebrowser/qutebrowser.git"
    assert task.container_image == (
        "jefzda/sweap-images:qutebrowser.qutebrowser-example-v1"
    )
    assert task.language == "python"
    assert task.problem_statement == (
        "Move the Qt warning filter.\n\n"
        "Requirements:\nPreserve its behavior.\n\n"
        "New interfaces introduced:\nhide_qt_warning(pattern: str)"
    )


@pytest.mark.parametrize(
    "forbidden",
    [
        "patch",
        "test_patch",
        "fail_to_pass",
        "pass_to_pass",
        "selected_test_files_to_run",
    ],
)
def test_rejects_unprojected_full_dataset_fields(forbidden: str) -> None:
    record = safe_record()
    record[forbidden] = "must remain outside the agent boundary"

    with pytest.raises(ValueError, match="unprojected SWE-bench Pro fields"):
        load_swe_bench_pro_task(record, dataset_revision=DATASET_REVISION)


def test_requires_every_safe_projection_column() -> None:
    record = safe_record()
    del record["requirements"]

    with pytest.raises(ValueError, match="missing SWE-bench Pro fields"):
        load_swe_bench_pro_task(record, dataset_revision=DATASET_REVISION)


@pytest.mark.parametrize(
    ("raw", "normalized"),
    [("python", "python"), ("js", "javascript"), ("ts", "typescript"), ("go", "go")],
)
def test_normalizes_official_language_labels(raw: str, normalized: str) -> None:
    task = load_swe_bench_pro_task(
        safe_record(repo_language=raw), dataset_revision=DATASET_REVISION
    )
    assert task.language == normalized


def test_omits_null_optional_problem_sections() -> None:
    task = load_swe_bench_pro_task(
        safe_record(requirements=None, interface=None),
        dataset_revision=DATASET_REVISION,
    )
    assert task.problem_statement == "Move the Qt warning filter."


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("repo", "not-a-repository", "owner/name"),
        ("base_commit", "short", "full lowercase Git commit"),
        ("dockerhub_tag", "bad/tag", "valid Docker tag"),
        ("repo_language", "java", "unsupported SWE-bench Pro language"),
    ],
)
def test_rejects_malformed_identifiers(field: str, value: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        load_swe_bench_pro_task(
            safe_record(**{field: value}), dataset_revision=DATASET_REVISION
        )
