"""Shared exports use public inputs, preserve outcomes and expose mismatches."""

import copy
import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import export_deepswe_task_specs as export
from agentless_ml.schemas import Benchmark, TaskSpec
from agentless_ml.adapters.benchmarks.deepswe_execution import DeepSWETestPlan
from test_local_workspace import git


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    task = TaskSpec(Benchmark.DEEPSWE, "a" * 40, "example-task", "go",
        "https://github.com/example/repo", "b" * 40, "Fix the public issue",
        "example:base", "sha256:" + "c" * 64)
    plan = DeepSWETestPlan("go", ("./...",))
    command = plan.command()
    limits = {"memory_mb": 8192, "cpus": 2, "pids_limit": 2048,
              "scratch_mode": "tmpfs", "scratch_mb": 4096,
              "swap_policy": "disabled", "timeout_seconds": 1800}
    cases = [{"test_id": "test_a", "status": "passed"},
             {"test_id": "test_b", "status": "failed"},
             {"test_id": "test_c", "status": "skipped"}]
    raw = {"results": {"tool": {"name": "fixture"},
                       "tests": [{"name": c["test_id"], "status": c["status"]} for c in cases]}}
    (tmp_path / "report.json").write_bytes(export.encoded(raw))
    execution = {"image_id": task.container_digest,
        "result": {"command": list(command.argv), "test_cases": cases,
                   "status": "fail", "exit_code": 1, "duration_seconds": 2},
        "limits": limits, "failure_exit_codes": [1],
        "report": {"format": "ctrf-json", "path": "/tmp/ctrf.json",
                   "id_policy": None, "artifact": "report.json"},
        "network_policy": {"execution_phase": "agent", "docker_network": "none"},
        "user": {"run_as_image_user": True, "user": "root"}}
    (tmp_path / "execution.json").write_bytes(export.encoded(execution))
    survey = {"status": "ready", "task_id": task.instance_id, "base_commit": task.base_commit,
        "image_id": task.container_digest, "artifacts": str(tmp_path),
        "tests": 3, "passed": 1, "failed": 1, "skipped": 1,
        "runner": "go", "targets": ["./..."]}
    monkeypatch.setattr(export, "pinned_plan", lambda *a: (plan, {"git_tree": "d" * 40}))
    monkeypatch.setattr(export, "agent_files_digest", lambda *a: "e" * 64)
    monkeypatch.setattr(export, "project_deepswe_task", lambda *a: {
        "instruction": task.problem_statement + "\n" + export.HARBOR_DELIVERY_INSTRUCTION,
        "unexported_extra": "DO_NOT_COPY"})
    return task, survey, command, limits, tmp_path


def build(inputs, **changes):
    task, survey, _, _, directory = inputs
    values = dict(task=task, task_directory=directory, repository=directory,
        override=None, environment=None, survey=survey,
        provenance={"setup_source_hashes": {"fixture.py": "f" * 64}})
    values.update(changes)
    return export.build_record(**values)


def test_deterministic_export_preserves_failures_skips_and_public_boundary(inputs):
    first, report = build(inputs)
    second, _ = build(inputs)
    assert export.encoded(first) == export.encoded(second)
    assert "DO_NOT_COPY" not in export.encoded(first).decode()
    baseline = first["public_validation"]["baseline"]
    assert baseline["counts"] == {"passed": 1, "failed": 1, "skipped": 1}
    assert baseline["passing_ids"] == ["test_a"]
    assert baseline["current_command_evidence"] == "matching"
    assert first["problem"]["delivery_suffix_removed"]
    assert first["timing"]["agreed_total_attempt_seconds"] is None
    assert first["launch"]["authorized"] is False
    assert baseline["native_report_sha256"] == export.sha(report)
    digest = first.pop("spec_sha256")
    assert digest == export.sha(export.encoded(first))


def test_old_command_is_evidence_not_a_silent_match(inputs):
    task, survey, command, limits, directory = inputs
    file = directory / "execution.json"
    record = json.loads(file.read_text())
    record["result"]["command"] = ["old-public-runner"]
    record.pop("network_policy")
    file.write_bytes(export.encoded(record))
    result, _, _ = export.baseline(task, survey, command, limits)
    assert result["current_command_evidence"] == "review_required"
    assert "command" in result["differences"]
    assert "network_or_missing_historical_network" in result["differences"]


def test_reader_detects_record_and_report_tampering(inputs):
    record, report = build(inputs)
    directory = inputs[-1]
    path = directory / "task.json"
    path.write_bytes(export.encoded(record))
    native = directory / record["public_validation"]["baseline"]["native_report_file"]
    native.write_bytes(report)
    assert export.encoded(export.read_record(path)) == export.encoded(record)
    native.write_bytes(report + b" ")
    with pytest.raises(ValueError, match="report hash"):
        export.read_record(path)
    native.write_bytes(report)
    record["problem"]["text"] = "Changed input"
    path.write_bytes(export.encoded(record))
    with pytest.raises(ValueError, match="specification hash"):
        export.read_record(path)


@pytest.mark.parametrize("mutation", ["image", "base", "count", "hash", "inventory", "report_path"])
def test_inconsistent_baseline_is_rejected(inputs, mutation):
    task, survey, command, limits, directory = inputs
    survey = copy.deepcopy(survey)
    if mutation == "image":
        survey["image_id"] = "sha256:" + "d" * 64
    elif mutation == "base":
        survey["base_commit"] = "d" * 40
    elif mutation == "count":
        survey["passed"] = 2
    elif mutation == "hash":
        survey["report_sha256"] = "0" * 64
    else:
        file = directory / "execution.json"
        record = json.loads(file.read_text())
        if mutation == "inventory":
            record["result"]["test_cases"][0]["status"] = "failed"
        else:
            record["report"]["artifact"] = "../../solution/answer.json"
        file.write_bytes(export.encoded(record))
    with pytest.raises(ValueError):
        export.baseline(task, survey, command, limits)


def test_missing_pin_and_changed_schedule_fail_closed(inputs):
    with pytest.raises(ValueError, match="pin"):
        build(inputs, task=replace(inputs[0], container_digest=None))
    with pytest.raises(ValueError, match="schedule"):
        build(inputs, survey={**inputs[1], "targets": ["./narrow"]})


def test_longer_command_allowance_is_not_the_total_attempt_budget(inputs, monkeypatch):
    task, survey, _, _, directory = inputs
    plan = DeepSWETestPlan("go", ("./...",), timeout_seconds=10800)
    monkeypatch.setattr(export, "pinned_plan", lambda *a: (plan, {}))
    record, _ = build(inputs, override={"timeout_seconds": 10800, "reason": "registered override"})
    assert record["timing"]["public_command_timeout_seconds"] == 10800
    assert record["timing"]["published_agent_timeout_seconds"] == 1800
    assert record["timing"]["agreed_total_attempt_seconds"] is None


def test_plan_reads_pinned_objects_not_dirty_worktree(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init")
    (repo / "go.work").write_bytes(b"go 1.24\nuse ./original\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "public base")
    commit = git(repo, "rev-parse", "HEAD").decode().strip()
    (repo / "go.work").write_bytes(b"go 1.24\nuse ./dirty\n")
    task = TaskSpec(Benchmark.DEEPSWE, "a" * 40, "example", "go",
        "https://github.com/example/repo", commit, "Fix issue", "image:base")
    plan, snapshot = export.pinned_plan(task, repo, None)
    assert plan.targets == ("./original/...",)
    assert len(snapshot["tree_listing_sha256"]) == 64
    assert (repo / "go.work").read_bytes().endswith(b"./dirty\n")
