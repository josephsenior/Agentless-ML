import json
import os
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from agentless_ml.localization import parse_file_locations
from agentless_ml.schemas import Benchmark, TaskSpec, ValidationResult, ValidationStatus
from agentless_ml.validation import (
    DockerTestRunner,
    PublicTestCommand,
)
from agentless_ml.validation import (
    TestExecution as ExecutionRecord,
)
from agentless_ml.workflow import (
    FixedWorkflowController,
    RecordedEditSample,
    RecordedStageResponses,
)
from agentless_ml.workflow.fixed import WorkflowError

ORIGINAL = "def add(a, b):\n    return a - b\n"
TEST_SOURCE = (
    "import unittest\nfrom calculator import add\n"
    "class TestAdd(unittest.TestCase):\n"
    "    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n"
)


def git(repository: Path, *args: str) -> str:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("GIT_")
    }
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    return (
        subprocess.run(
            [
                "git",
                "-c",
                "core.autocrlf=false",
                "-c",
                "core.hooksPath=" + os.devnull,
                "-c",
                "user.name=Workflow Tests",
                "-c",
                "user.email=tests@example.invalid",
                *args,
            ],
            cwd=repository,
            env=env,
            capture_output=True,
            check=True,
        )
        .stdout.decode()
        .strip()
    )


@pytest.fixture
def source(tmp_path):
    repository = tmp_path / "source"
    repository.mkdir()
    (repository / "calculator.py").write_bytes(ORIGINAL.encode())
    (repository / "test_public.py").write_bytes(TEST_SOURCE.encode())
    git(repository, "init")
    git(repository, "add", ".")
    git(repository, "commit", "-m", "pinned fixture")
    return repository, git(repository, "rev-parse", "HEAD")


def responses():
    def repair(operator):
        return (
            "```python\n### calculator.py\n<<<<<<< SEARCH\n"
            "    return a - b\n=======\n"
            f"    return a {operator} b\n>>>>>>> REPLACE\n```"
        )

    return RecordedStageResponses(
        file_localization="```\ncalculator.py\n```",
        symbol_localization="```\ncalculator.py\nfunction: add\n```",
        repairs=("malformed recorded sample", repair("*"), repair("+")),
        source="controlled fixture",
    )


class FakeRunner:
    image_reference = "python:fixture"
    image_id = "sha256:fixture"

    def run(self, source, command, *, artifact_root=None):
        destination = Path(artifact_root) / "fake-execution"
        destination.mkdir(parents=True)
        passed = "return a + b" in (Path(source) / "calculator.py").read_text()
        result = ValidationResult(
            status=ValidationStatus.PASS if passed else ValidationStatus.FAIL,
            command=command.argv,
            duration_seconds=0.01,
            exit_code=0 if passed else 1,
            kind=command.kind,
        )
        return ExecutionRecord(
            result, self.image_id, "fake-container", str(destination)
        )


def task(commit, image="python:fixture", digest="sha256:fixture"):
    return TaskSpec(
        benchmark=Benchmark.CONTROLLED_FIXTURE,
        benchmark_revision="controlled-fixture-v1",
        instance_id="controlled__python-addition",
        language="python",
        repository_url="https://example.invalid/controlled.git",
        base_commit=commit,
        problem_statement="Make add return the sum of its arguments.",
        container_image=image,
        container_digest=digest,
    )


def controller(tmp_path, source, runner):
    repository, commit = source
    return FixedWorkflowController(
        task=task(commit, runner.image_reference, runner.image_id),
        source_repository=repository,
        workspace_root=tmp_path / "workspaces",
        artifact_root=tmp_path / "runs",
        runner=runner,
        public_commands=(
            PublicTestCommand(("python", "-m", "unittest", "test_public")),
        ),
        implementation_revision="implementation-sha",
        harness_revision="harness-v1",
        model_name="recorded/test-model",
    )


def test_file_location_parser_validates_and_limits_paths():
    response = "```\nrepo/a.py\n../secret.py\nunknown.py\nb.py\na.py\nc.py\n```"
    assert parse_file_locations(
        response,
        ("a.py", "b.py", "c.py", "notes.txt"),
        repository_name="repo",
        maximum_files=2,
    ) == ("a.py", "b.py")


def test_recorded_edit_stage(tmp_path, source):
    bundle = replace(responses(), edit_localization="```\ncalculator.py\nline: 2\n```")
    result = controller(tmp_path, source, FakeRunner()).run(bundle)
    directory = Path(result.artifact_directory)
    assert result.prediction.selected_candidate_id == "repair-2"
    assert result.run.model_calls == 0
    assert (
        "2|    return a - b"
        in (directory / "prompts/edit-localization.txt").read_text()
    )
    assert json.loads((directory / "selected-context.json").read_text())[
        "locations"
    ] == {"calculator.py": ["line: 2"]}
    assert (
        json.loads((directory / "controller.json").read_text())["localization_mode"]
        == "edit-lines"
    )
    assert (directory / "symbol-context.json").exists()


def test_multiple_edit_samples_share_selection(tmp_path, source):
    recorded = responses()
    bundle = replace(
        recorded,
        repairs=(),
        edit_samples=(
            RecordedEditSample(
                "```\ncalculator.py\nline: 1\n```", recorded.repairs[:2]
            ),
            RecordedEditSample(
                "```\ncalculator.py\nline: 2\n```",
                (recorded.repairs[2], recorded.repairs[2]),
            ),
        ),
    )
    result = controller(tmp_path, source, FakeRunner()).run(bundle)
    assert result.prediction.selected_candidate_id == "loc-1-repair-0"
    assert [
        (a.localization_rank, a.sample_index, a.status) for a in result.attempts
    ] == [
        (0, 0, "repair_error"),
        (0, 1, "validated"),
        (1, 0, "validated"),
        (1, 1, "validated"),
    ]
    assert result.attempts[2].candidate.localization_rank == 1
    directory = Path(result.artifact_directory)
    assert json.loads((directory / "selection.json").read_text())["vote_count"] == 2
    assert (
        json.loads((directory / "controller.json").read_text())["localization_mode"]
        == "edit-samples"
    )
    assert (directory / "localizations/0/repair.txt").exists()
    assert (directory / "localizations/1/selected-context.json").exists()
    assert not (directory / "prompts/repair.txt").exists()
    assert result.run.model_calls == 0
    assert (source[0] / "calculator.py").read_text() == ORIGINAL
    assert not list((tmp_path / "workspaces").iterdir())


def test_edit_samples_do_not_share_allowed_lines(tmp_path, source):
    repository, _ = source
    long_source = "def add(a, b):\n" + "    # padding\n" * 40 + "    return a - b\n"
    (repository / "calculator.py").write_bytes(long_source.encode())
    git(repository, "add", ".")
    git(repository, "commit", "-m", "separated line contexts")
    recorded = responses()
    bundle = replace(
        recorded,
        repairs=(),
        edit_samples=(
            RecordedEditSample(
                "```\ncalculator.py\nline: 2\n```", (recorded.repairs[2],)
            ),
            RecordedEditSample(
                "```\ncalculator.py\nline: 42\n```", (recorded.repairs[2],)
            ),
        ),
    )
    result = controller(
        tmp_path, (repository, git(repository, "rev-parse", "HEAD")), FakeRunner()
    ).run(bundle)
    assert [a.status for a in result.attempts] == ["repair_error", "validated"]
    assert result.prediction.selected_candidate_id == "loc-1-repair-0"


def test_invalid_sample_stops_before_validation(tmp_path, source):
    recorded = responses()
    bundle = replace(
        recorded,
        repairs=(),
        edit_samples=(
            RecordedEditSample(
                "```\ncalculator.py\nline: 2\n```", (recorded.repairs[2],)
            ),
            RecordedEditSample(
                "```\ncalculator.py\nline: 999\n```", (recorded.repairs[2],)
            ),
        ),
    )
    with pytest.raises(WorkflowError, match="edit sample 1"):
        controller(tmp_path, source, FakeRunner()).run(bundle)
    directory = next((tmp_path / "runs").iterdir())
    assert (directory / "responses.json").exists()
    assert not (directory / "executions").exists()


def test_edit_sample_input_contract():
    sample = RecordedEditSample("recorded location", ("repair",))
    with pytest.raises(ValueError, match="mixed"):
        replace(responses(), edit_samples=(sample,))
    with pytest.raises(ValueError, match="mixed"):
        replace(
            responses(), repairs=(), edit_localization="line", edit_samples=(sample,)
        )
    with pytest.raises(ValueError, match="nonempty"):
        RecordedEditSample("line", ())


def test_identical_repairs_vote_across_groups(tmp_path, source):
    good_repair = responses().repairs[2]
    bundle = replace(
        responses(),
        repairs=(),
        edit_samples=(
            RecordedEditSample("```\ncalculator.py\nline: 1\n```", (good_repair,)),
            RecordedEditSample("```\ncalculator.py\nline: 2\n```", (good_repair,)),
        ),
    )
    result = controller(tmp_path, source, FakeRunner()).run(bundle)
    assert result.prediction.selected_candidate_id == "loc-0-repair-0"
    selection = json.loads(
        (Path(result.artifact_directory) / "selection.json").read_text()
    )
    assert selection["vote_count"] == 2
    assert selection["considered_candidate_ids"] == ["loc-0-repair-0", "loc-1-repair-0"]


class RegressionRunner:
    image_reference = "python:fixture"
    image_id = "sha256:fixture"

    def __init__(self, broken=False):
        self.calls = []
        self.broken = broken

    def run(self, source, command, *, artifact_root=None):
        content = (Path(source) / "calculator.py").read_text()
        self.calls.append((content, command.argv[0]))
        baseline = "regression-baseline" in str(artifact_root)
        if baseline:
            assert content == ORIGINAL
            status = (
                ValidationStatus.FAIL
                if command.argv[0] == "already-failing"
                else ValidationStatus.PASS
            )
            if self.broken:
                status = ValidationStatus.HARNESS_ERROR
        else:
            assert command.argv[0] == "keep"
            status = (
                ValidationStatus.PASS if "a + b" in content else ValidationStatus.FAIL
            )
        destination = Path(artifact_root) / "execution"
        destination.mkdir(parents=True)
        return ExecutionRecord(
            ValidationResult(
                status=status,
                command=command.argv,
                duration_seconds=0,
                kind=command.kind,
                exit_code=0 if status == ValidationStatus.PASS else 1,
            ),
            self.image_id,
            "fixture",
            str(destination),
        )


def regression_controller(tmp_path, source, runner):
    from agentless_ml.validation import RegressionTest

    repository, commit = source
    return FixedWorkflowController(
        task=task(commit),
        source_repository=repository,
        workspace_root=tmp_path / "workspaces",
        artifact_root=tmp_path / "runs",
        runner=runner,
        public_commands=(),
        regression_tests=tuple(
            RegressionTest(name, PublicTestCommand((name,)))
            for name in ("keep", "exclude", "already-failing")
        ),
        implementation_revision="fixture",
        harness_revision="fixture",
        model_name="recorded",
    )


def test_regression_baseline_and_frozen_schedule(tmp_path, source):
    runner = RegressionRunner()
    result = regression_controller(tmp_path, source, runner).run(
        replace(responses(), regression_exclusions="exclude")
    )
    assert result.prediction.selected_candidate_id == "repair-2"
    assert [name for _, name in runner.calls] == [
        "keep",
        "exclude",
        "already-failing",
        "keep",
        "keep",
    ]
    directory = Path(result.artifact_directory)
    selection = json.loads((directory / "regression-selection.json").read_text())
    assert selection["passing_ids"] == ["keep", "exclude"]
    assert selection["excluded_ids"] == ["exclude"]
    assert selection["selected_ids"] == ["keep"]
    assert json.loads((directory / "controller.json").read_text())["public_commands"][
        0
    ]["argv"] == ["keep"]
    assert result.run.model_calls == 0
    assert not list((tmp_path / "workspaces").iterdir())


@pytest.mark.parametrize(
    "exclusions,broken,match",
    [
        ("already-failing", False, "nonpassing"),
        ("keep\nexclude", False, "no public"),
        ("", True, "infrastructure"),
    ],
)
def test_regression_selection_failures_stop_candidates(
    tmp_path, source, exclusions, broken, match
):
    runner = RegressionRunner(broken)
    with pytest.raises(WorkflowError, match=match):
        regression_controller(tmp_path, source, runner).run(
            replace(responses(), regression_exclusions=exclusions)
        )
    assert len(runner.calls) == 3
    directory = next((tmp_path / "runs").iterdir())
    assert (directory / "regression-baseline.json").exists()
    assert (directory / "failure.json").exists()


def test_inventory_requires_recorded_selection(tmp_path, source):
    runner = RegressionRunner()
    with pytest.raises(WorkflowError, match="together"):
        regression_controller(tmp_path, source, runner).run(responses())
    assert not runner.calls


def test_invalid_edit_stage_does_not_fall_back(tmp_path, source):
    bundle = replace(
        responses(), edit_localization="```\ncalculator.py\nline: 999\n```"
    )
    with pytest.raises(WorkflowError, match="not shown"):
        controller(tmp_path, source, FakeRunner()).run(bundle)
    directory = next((tmp_path / "runs").iterdir())
    assert (directory / "symbol-context.json").exists()
    assert (directory / "failure.json").exists()
    assert not (directory / "executions").exists()


def test_file_location_prefers_exact_path_when_package_matches_repository():
    assert parse_file_locations(
        "```\nqutebrowser/utils/qtlog.py\n```",
        ("qutebrowser/utils/qtlog.py",),
        repository_name="qutebrowser",
    ) == ("qutebrowser/utils/qtlog.py",)


def test_recorded_workflow_exports_prediction_and_run(tmp_path, source):
    repository, _ = source
    result = controller(tmp_path, source, FakeRunner()).run(responses())

    assert result.prediction.selected_candidate_id == "repair-2"
    assert [attempt.status for attempt in result.attempts] == [
        "repair_error",
        "validated",
        "validated",
    ]
    assert (
        result.run.model_calls
        == result.run.input_tokens
        == result.run.output_tokens
        == 0
    )
    assert result.run.container_digest == "sha256:fixture"
    assert result.selected_files == ("calculator.py",)
    assert (repository / "calculator.py").read_text() == ORIGINAL
    assert not list((tmp_path / "workspaces").iterdir())
    artifacts = Path(result.artifact_directory)
    assert (
        json.loads((artifacts / "prediction.json").read_text())["selected_candidate_id"]
        == "repair-2"
    )
    assert json.loads((artifacts / "run.json").read_text())["model_calls"] == 0
    assert json.loads((artifacts / "task.json").read_text())["benchmark"] == (
        "controlled-fixture"
    )
    assert json.loads((artifacts / "controller.json").read_text())["public_commands"][
        0
    ]["argv"] == ["python", "-m", "unittest", "test_public"]
    assert (
        json.loads((artifacts / "responses.json").read_text())["source"]
        == "controlled fixture"
    )
    assert len(list((artifacts / "executions").glob("*/*/candidate.json"))) == 2


def test_controller_rejects_container_provenance_mismatch(tmp_path, source):
    repository, commit = source
    with pytest.raises(ValueError, match="image reference"):
        FixedWorkflowController(
            task=task(commit, image="other:image"),
            source_repository=repository,
            workspace_root=tmp_path / "workspaces",
            artifact_root=tmp_path / "runs",
            runner=FakeRunner(),
            public_commands=(PublicTestCommand(("true",)),),
            implementation_revision="impl",
            harness_revision="harness",
            model_name="recorded",
        )


docker_enabled = pytest.mark.skipif(
    os.environ.get("AGENTLESS_DOCKER_TESTS") != "1",
    reason="opt-in local Docker integration",
)


@docker_enabled
def test_real_docker_recorded_workflow(tmp_path, source):
    runner = DockerTestRunner(
        os.environ.get("AGENTLESS_TEST_IMAGE", "python:3.11-slim"),
        tmp_path / "unused-default-executions",
    )
    result = controller(tmp_path, source, runner).run(responses())
    validated = [attempt.candidate for attempt in result.attempts if attempt.candidate]
    assert [candidate.validation[0].status for candidate in validated] == [
        ValidationStatus.FAIL,
        ValidationStatus.PASS,
    ]
    assert result.prediction.selected_candidate_id == "repair-2"
