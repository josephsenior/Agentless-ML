import json
import re
from pathlib import Path

import pytest

from agentless_ml.adapters.benchmarks import SWE_BENCH_PRO_AGENT_COLUMNS
from agentless_ml.schemas import ValidationKind


ROOT = Path(__file__).parents[1]
EXPERIMENT_ROOT = ROOT / "experiments" / "swe_bench_pro"
SMOKE_CONFIGS = (
    "python_smoke_set.json", "v2_smoke_set.json", "v2_corpus_pin.json",
    "v2_public_plans.json", "v2_full_public_plans.json",
)
FORBIDDEN_INPUT_COLUMNS = {
    "patch", "test_patch", "fail_to_pass", "pass_to_pass", "selected_test_files_to_run",
}


def smoke_input_paths(root):
    # Root-level dated records describe completed runs. Only the registered
    # configurations and fixture directories supply replay inputs.
    for name in SMOKE_CONFIGS:
        path = root / name
        if path.is_file():
            yield path
    for directory in root.iterdir():
        if directory.is_dir():
            yield from (path for path in directory.rglob("*")
                        if path.is_file() and path.name != "task.json")


def assert_answer_free(paths):
    for path in paths:
        content = path.read_text(encoding="utf-8").casefold()
        for token in FORBIDDEN_INPUT_COLUMNS:
            # Also catch gold_patch, without matching MessageDispatcher.
            assert re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", content) is None, (
                f"{path}: forbidden input column {token}"
            )


def test_smoke_set_has_three_unique_pinned_python_tasks() -> None:
    smoke_set = json.loads(
        (EXPERIMENT_ROOT / "python_smoke_set.json").read_text(encoding="utf-8")
    )
    experiments = smoke_set["experiments"]
    assert len(experiments) == 3
    instance_ids = [entry["instance_id"] for entry in experiments.values()]
    assert len(set(instance_ids)) == len(instance_ids)
    assert all(
        re.fullmatch(r"sha256:[0-9a-f]{64}", entry["container_digest"])
        for entry in experiments.values()
    )


def test_each_smoke_task_has_fixed_recorded_inputs_and_validation() -> None:
    smoke_set = json.loads(
        (EXPERIMENT_ROOT / "python_smoke_set.json").read_text(encoding="utf-8")
    )
    for name in smoke_set["experiments"]:
        experiment = EXPERIMENT_ROOT / name
        assert (experiment / "file_localization.txt").read_text().strip()
        assert (experiment / "symbol_localization.txt").read_text().strip()
        assert len(list(experiment.glob("repair_*.txt"))) >= 2
        validation = json.loads(
            (experiment / "validation.json").read_text(encoding="utf-8")
        )
        assert validation
        for command in validation:
            assert set(command) == {"argv", "kind", "timeout_seconds"}
            assert command["argv"]
            assert ValidationKind(command["kind"])
            assert command["timeout_seconds"] > 0


def test_smoke_inputs_do_not_name_dataset_answer_or_verifier_columns() -> None:
    assert FORBIDDEN_INPUT_COLUMNS.isdisjoint(SWE_BENCH_PRO_AGENT_COLUMNS)
    paths = tuple(smoke_input_paths(EXPERIMENT_ROOT))
    assert paths
    assert_answer_free(paths)


@pytest.mark.parametrize("token", sorted(FORBIDDEN_INPUT_COLUMNS))
@pytest.mark.parametrize("location", ("fixture", "configuration"))
def test_input_guard_keeps_rejecting_leaks_while_allowing_run_evidence(tmp_path, token, location):
    fixture = tmp_path / "example"
    fixture.mkdir()
    source = fixture / "file_localization.txt"
    source.write_text("MessageDispatcher", encoding="utf-8")
    config = tmp_path / "python_smoke_set.json"
    config.write_text("{}", encoding="utf-8")
    (tmp_path / "completed_replay.json").write_text(json.dumps({token: "recorded outcome"}),
                                                   encoding="utf-8")
    assert_answer_free(smoke_input_paths(tmp_path))
    target = source if location == "fixture" else config
    target.write_text(json.dumps({"gold_" + token: "forbidden input"}), encoding="utf-8")
    with pytest.raises(AssertionError, match=token):
        assert_answer_free(smoke_input_paths(tmp_path))
