"""Pebble's registered public CI setup preserves the ordinary Go contract."""

from pathlib import Path

from agentless_ml.adapters.benchmarks.deepswe_execution import (
    deepswe_test_command, deepswe_test_plan, load_test_overrides,
)


def test_registered_pebble_plan_changes_only_ci_and_build_workers(tmp_path):
    registry = Path(__file__).resolve().parents[1] / "experiments/deepswe/test_overrides.json"
    override = load_test_overrides(registry)["pebble-durability-wait-apis"]
    plan = deepswe_test_plan("go", tmp_path, override)
    assert plan.runner == "pebble-go-ci"
    assert plan.targets == ("./...",)
    assert plan.override_reason == override["reason"]
    command = plan.command()
    ordinary = deepswe_test_command("go", ("./...",))
    assert command.argv[:2] == ordinary.argv[:2]
    assert command.argv[3:] == ordinary.argv[3:]
    assert command.argv[2] == "export CI=1; " + ordinary.argv[2].replace(
        'go test -json -count=1 "$@"', 'go test -json -count=1 -p 1 "$@"', 1,
    )
    assert command.report == ordinary.report
    assert command.failure_exit_codes == ordinary.failure_exit_codes == (1,)
    assert command.timeout_seconds == ordinary.timeout_seconds == 1800
    assert "CI=1" not in ordinary.argv[2]
    assert "-p 1" not in ordinary.argv[2]


def test_pebble_retains_all_workspace_package_targets(tmp_path):
    (tmp_path / "go.work").write_text("go 1.25.3\nuse (\n ./a\n ./b\n)\n", encoding="utf-8")
    plan = deepswe_test_plan("go", tmp_path, {
        "runner": "pebble-go-ci", "reason": "upstream public CI setup",
    })
    assert plan.targets == ("./a/...", "./b/...")
    assert plan.command().argv[-2:] == plan.targets
