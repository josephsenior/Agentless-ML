import builtins
import io
import json
import os
import re
import shutil
from pathlib import Path

import pytest

from agentless_ml.adapters.benchmarks import (
    DEEPSWE_AGENT_FIELDS,
    DeepSWEDataset,
    DeepSWEDatasetPin,
    load_deepswe_task,
    project_deepswe_task,
)
from agentless_ml.adapters.benchmarks.deepswe import (
    HARBOR_DELIVERY_INSTRUCTION,
    agent_files_digest,
)
from agentless_ml.schemas import Benchmark

ROOT = Path(__file__).parents[1]
REAL_TASK = ROOT / "tests" / "fixtures" / "deepswe" / "abs-module-cache-flags"
CORPUS_PIN = json.loads(
    (ROOT / "experiments" / "deepswe" / "corpus_pin.json").read_text(encoding="utf-8")
)
REVISION = CORPUS_PIN["revision"]


def make_task(root: Path, task_id: str = "demo-task", **toml_overrides: str) -> Path:
    """A DeepSWE-shaped task with held-out files that must never be read."""
    directory = root / task_id
    shutil.copytree(REAL_TASK, directory)
    text = (directory / "task.toml").read_text(encoding="utf-8")
    text = text.replace('task_id = "abs-module-cache-flags"', f'task_id = "{task_id}"')
    for old, new in toml_overrides.items():
        assert old in text, old
        text = text.replace(old, new)
    (directory / "task.toml").write_text(text, encoding="utf-8", newline="\n")
    (directory / "solution").mkdir()
    (directory / "solution" / "solution.patch").write_text("GOLD PATCH", encoding="utf-8")
    (directory / "tests").mkdir()
    (directory / "tests" / "config.json").write_text('{"f2p_node_ids": ["hidden"]}')
    return directory


def pinned(root: Path) -> DeepSWEDatasetPin:
    directories = tuple(path for path in root.iterdir() if path.is_dir())
    return DeepSWEDatasetPin(REVISION, agent_files_digest(directories), len(directories))


@pytest.fixture
def forbid_held_out(monkeypatch):
    """Return a function that, once called, fails on any held-out file access.

    Arm it after the test has created its fake held-out files.
    """
    real_open = io.open

    def guarded(file, *args, **kwargs):
        if {"tests", "solution"} & set(Path(str(file)).parts[-3:-1]):
            raise AssertionError(f"held-out DeepSWE file was opened: {file}")
        return real_open(file, *args, **kwargs)

    def arm() -> None:
        monkeypatch.setattr(builtins, "open", guarded)
        monkeypatch.setattr(io, "open", guarded)

    return arm


def test_real_task_projects_and_normalizes(forbid_held_out) -> None:
    forbid_held_out()
    record = project_deepswe_task(REAL_TASK)
    assert set(record) == set(DEEPSWE_AGENT_FIELDS)
    task = load_deepswe_task(record, dataset_revision=REVISION)
    assert task.benchmark is Benchmark.DEEPSWE
    assert task.instance_id == "abs-module-cache-flags"
    assert task.language == "go"
    assert task.repository_url == "https://github.com/abs-lang/abs.git"
    assert task.base_commit == "cb1b3b671d0ee9fa9da9f7b02f86967953ffd10a"
    assert task.container_image.startswith("public.ecr.aws/d3j8x8q7/swe-bench-202605:")
    assert (task.timeout_seconds, task.memory_megabytes) == (10800, 8192)
    assert task.problem_statement.startswith("Improve ABS module loading")
    assert HARBOR_DELIVERY_INSTRUCTION not in task.problem_statement
    assert task.problem_statement.endswith("focused on the behaviors above.")
    assert dict(task.visible_metadata) == {"repository": "abs-lang/abs"}


def test_dataset_never_opens_held_out_files(tmp_path, forbid_held_out) -> None:
    make_task(tmp_path, "task-a")
    make_task(tmp_path, "task-b")
    pin = pinned(tmp_path)
    forbid_held_out()
    tasks = DeepSWEDataset(tmp_path, pin).load_tasks()
    assert [task.instance_id for task in tasks] == ["task-a", "task-b"]


def test_projected_record_rejects_extra_and_missing_fields() -> None:
    record = project_deepswe_task(REAL_TASK)
    with pytest.raises(ValueError, match="unprojected DeepSWE fields: solution_patch"):
        load_deepswe_task({**record, "solution_patch": "x"}, dataset_revision=REVISION)
    del record["instruction"]
    with pytest.raises(ValueError, match="missing DeepSWE fields: instruction"):
        load_deepswe_task(record, dataset_revision=REVISION)


@pytest.mark.parametrize(
    "old,new,message",
    [
        ('schema_version = "1.3"', 'schema_version = "2.0"', "unsupported DeepSWE schema_version"),
        ('[agent]', '[oracle]\npatch = "x"\n[agent]', "unreviewed DeepSWE task.toml tables in demo-task: oracle"),
        ('network_mode = "no-network"\ntimeout_sec = 10800.0', 'network_mode = "public"\ntimeout_sec = 10800.0', "requires network"),
        ('language = "go"', 'language = "cobol"', "unsupported DeepSWE language"),
        ('repository_url = "https://github.com/abs-lang/abs"', 'repository_url = "https://gitlab.com/a/b"', "GitHub repository URL"),
    ],
)
def test_task_metadata_fails_closed(tmp_path, old, new, message) -> None:
    directory = make_task(tmp_path, **{old: new})
    with pytest.raises(ValueError, match=message):
        load_deepswe_task(project_deepswe_task(directory), dataset_revision=REVISION)


def test_abbreviated_commit_requires_a_matching_pinned_resolution(tmp_path) -> None:
    full = "cb1b3b671d0ee9fa9da9f7b02f86967953ffd10a"
    directory = make_task(tmp_path, **{f'base_commit_hash = "{full}"': 'base_commit_hash = "cb1b3b6"'})
    record = project_deepswe_task(directory)
    with pytest.raises(ValueError, match="abbreviated commit cb1b3b6"):
        load_deepswe_task(record, dataset_revision=REVISION)
    with pytest.raises(ValueError, match="does not start with"):
        load_deepswe_task(record, dataset_revision=REVISION, resolved_base_commit="f" * 40)
    task = load_deepswe_task(record, dataset_revision=REVISION, resolved_base_commit=full)
    assert task.base_commit == full


def test_pin_detects_changed_visible_files_and_task_count(tmp_path) -> None:
    make_task(tmp_path, "task-a")
    pin = pinned(tmp_path)
    instruction = tmp_path / "task-a" / "instruction.md"
    instruction.write_text(instruction.read_text(encoding="utf-8") + "extra", encoding="utf-8")
    with pytest.raises(ValueError, match="do not match their pin"):
        DeepSWEDataset(tmp_path, pin).load_tasks()
    make_task(tmp_path, "task-b")
    with pytest.raises(ValueError, match="task count does not match"):
        DeepSWEDataset(tmp_path, pin).load_tasks()


def test_pin_ignores_held_out_files_and_line_endings(tmp_path) -> None:
    directory = make_task(tmp_path, "task-a")
    pin = pinned(tmp_path)
    (directory / "solution" / "solution.patch").write_text("changed", encoding="utf-8")
    instruction = directory / "instruction.md"
    instruction.write_bytes(instruction.read_bytes().replace(b"\n", b"\r\n"))
    assert len(DeepSWEDataset(tmp_path, pin).load_tasks()) == 1


def test_task_id_must_match_directory(tmp_path) -> None:
    directory = make_task(tmp_path, "task-a")
    directory.rename(tmp_path / "renamed")
    with pytest.raises(ValueError, match="does not match its directory"):
        DeepSWEDataset(tmp_path, pinned(tmp_path)).load_tasks()


def test_selection_by_task_id_and_language(tmp_path) -> None:
    make_task(tmp_path, "task-a")
    make_task(tmp_path, "task-b")
    dataset = DeepSWEDataset(tmp_path, pinned(tmp_path))
    assert [t.instance_id for t in dataset.load_tasks(task_ids=("task-b",))] == ["task-b"]
    assert dataset.load_tasks(language="rust") == ()
    with pytest.raises(KeyError, match="not found: task-z"):
        dataset.load_tasks(task_ids=("task-z",))


def test_checked_in_corpus_pin_is_well_formed() -> None:
    DeepSWEDatasetPin(
        CORPUS_PIN["revision"], CORPUS_PIN["agent_files_sha256"], CORPUS_PIN["task_count"]
    )
    assert CORPUS_PIN["task_count"] == 113
    for commit in CORPUS_PIN["resolved_base_commits"].values():
        assert len(commit) == 40 and set(commit) <= set("0123456789abcdef")
    # Every task's published image is pinned by registry digest, so a moved tag
    # cannot silently change the environment a result was produced in.
    digests = CORPUS_PIN["container_digests"]
    assert len(digests) == 113
    assert all(re.fullmatch(r"sha256:[0-9a-f]{64}", d) for d in digests.values())
    assert digests["abs-module-cache-flags"] == digests["abs-stepped-slices"]


def test_container_digest_must_be_a_sha256_digest() -> None:
    record = project_deepswe_task(REAL_TASK)
    with pytest.raises(ValueError, match="sha256 image digest"):
        load_deepswe_task(record, dataset_revision=REVISION, container_digest="latest")
    task = load_deepswe_task(
        record,
        dataset_revision=REVISION,
        container_digest=CORPUS_PIN["container_digests"]["abs-module-cache-flags"],
    )
    assert task.container_digest.startswith("sha256:")


@pytest.mark.skipif(
    "AGENTLESS_DEEPSWE_TASKS" not in os.environ,
    reason="opt-in check against a local DeepSWE checkout at the pinned revision",
)
def test_pinned_real_corpus_loads(forbid_held_out) -> None:
    forbid_held_out()
    pin = DeepSWEDatasetPin(
        CORPUS_PIN["revision"], CORPUS_PIN["agent_files_sha256"], CORPUS_PIN["task_count"]
    )
    tasks = DeepSWEDataset(Path(os.environ["AGENTLESS_DEEPSWE_TASKS"]), pin).load_tasks(
        resolved_base_commits=CORPUS_PIN["resolved_base_commits"],
        container_digests=CORPUS_PIN["container_digests"],
    )
    assert len(tasks) == 113
    assert all(task.container_digest for task in tasks)
    assert {task.language for task in tasks} == {"go", "javascript", "python", "rust", "typescript"}


def test_a_language_correction_replaces_a_mislabel() -> None:
    record = project_deepswe_task(REAL_TASK)
    task = load_deepswe_task(record, dataset_revision=REVISION, corrected_language="rust")
    assert task.language == "rust"
    with pytest.raises(ValueError, match="already labelled go"):
        load_deepswe_task(record, dataset_revision=REVISION, corrected_language="go")
    with pytest.raises(ValueError, match="unsupported corrected language"):
        load_deepswe_task(record, dataset_revision=REVISION, corrected_language="cobol")


def test_the_pinned_language_corrections_are_explained() -> None:
    from agentless_ml.adapters.benchmarks import pinned_load_options

    corrections = pinned_load_options(CORPUS_PIN)["language_corrections"]
    assert corrections == {
        "httpx-deterministic-cookie-store": "python",
        "koota-entity-snapshot-rollback": "typescript",
        "prometheus-transactional-reload-status": "go",
    }
    unexplained = {"language_corrections": {"t": {"language": "go", "reason": " "}}}
    with pytest.raises(ValueError, match="needs a reason"):
        pinned_load_options(unexplained)
