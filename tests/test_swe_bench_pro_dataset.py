import hashlib
from types import SimpleNamespace

import pytest

from agentless_ml.adapters.benchmarks import (
    SWE_BENCH_PRO_AGENT_COLUMNS,
    SWEbenchProDataset,
    SWEbenchProDatasetPin,
)


REVISION = "7ab5114912baf22bb098818e604c02fe7ad2c11f"


def safe_record(instance_id: str = "instance_example") -> dict[str, object]:
    return {
        "repo": "qutebrowser/qutebrowser",
        "instance_id": instance_id,
        "base_commit": "ebfe9b7aa0c4ba9d451f993e08955004aaec4345",
        "problem_statement": "Correct the behavior.",
        "requirements": None,
        "interface": None,
        "repo_language": "python",
        "dockerhub_tag": "qutebrowser.qutebrowser-example-v1",
    }


def dataset(tmp_path, monkeypatch, records):
    parquet_path = tmp_path / "test.parquet"
    parquet_path.write_bytes(b"pinned parquet fixture")
    digest = hashlib.sha256(parquet_path.read_bytes()).hexdigest()
    observed = {}

    class Table:
        num_rows = len(records)

        @staticmethod
        def to_pylist():
            return records

    def read_table(path, *, columns):
        observed["path"] = path
        observed["columns"] = columns
        return Table()

    monkeypatch.setattr(
        "agentless_ml.adapters.benchmarks.swe_bench_pro.importlib.import_module",
        lambda name: SimpleNamespace(read_table=read_table),
    )
    pin = SWEbenchProDatasetPin(REVISION, digest, len(records))
    return SWEbenchProDataset(parquet_path, pin), observed


def test_parquet_read_projects_safe_columns_before_materializing_rows(
    tmp_path, monkeypatch
) -> None:
    source, observed = dataset(tmp_path, monkeypatch, [safe_record()])
    tasks = source.load_tasks(language="python")

    assert observed["columns"] == list(SWE_BENCH_PRO_AGENT_COLUMNS)
    assert tasks[0].instance_id == "instance_example"


def test_rejects_changed_parquet_before_importing_reader(tmp_path, monkeypatch) -> None:
    source, _ = dataset(tmp_path, monkeypatch, [safe_record()])
    source.parquet_path.write_bytes(b"changed")

    with pytest.raises(ValueError, match="digest"):
        source.load_tasks()


def test_selects_requested_tasks_in_dataset_order(tmp_path, monkeypatch) -> None:
    source, _ = dataset(
        tmp_path,
        monkeypatch,
        [safe_record("instance_b"), safe_record("instance_a")],
    )
    tasks = source.load_tasks(instance_ids=("instance_a", "instance_b"))
    assert [task.instance_id for task in tasks] == ["instance_b", "instance_a"]


def test_rejects_missing_or_duplicate_requested_ids(tmp_path, monkeypatch) -> None:
    source, _ = dataset(tmp_path, monkeypatch, [safe_record()])
    with pytest.raises(KeyError, match="not found"):
        source.load_tasks(instance_ids=("missing",))
    with pytest.raises(ValueError, match="duplicates"):
        source.load_tasks(instance_ids=("instance_example", "instance_example"))


def test_rejects_duplicate_dataset_instances(tmp_path, monkeypatch) -> None:
    source, _ = dataset(
        tmp_path,
        monkeypatch,
        [safe_record(), safe_record()],
    )
    with pytest.raises(ValueError, match="duplicate SWE-bench Pro instance"):
        source.load_tasks()
