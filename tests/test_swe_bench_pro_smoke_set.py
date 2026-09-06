import json
import re
from pathlib import Path

from agentless_ml.adapters.benchmarks import SWE_BENCH_PRO_AGENT_COLUMNS
from agentless_ml.schemas import ValidationKind


ROOT = Path(__file__).parents[1]
EXPERIMENT_ROOT = ROOT / "experiments" / "swe_bench_pro"


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
    forbidden = {
        "patch",
        "test_patch",
        "fail_to_pass",
        "pass_to_pass",
        "selected_test_files_to_run",
    }
    assert forbidden.isdisjoint(SWE_BENCH_PRO_AGENT_COLUMNS)

    for path in EXPERIMENT_ROOT.rglob("*"):
        if path.is_file() and path.name != "task.json":
            content = path.read_text(encoding="utf-8").casefold()
            assert all(token not in content for token in forbidden)
