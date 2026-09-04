"""Run the complete recorded Python workflow without calling a model API."""

import argparse
import os
import subprocess
import uuid
from pathlib import Path

from agentless_ml.schemas import Benchmark, TaskSpec
from agentless_ml.validation import DockerTestRunner, PublicTestCommand
from agentless_ml.workflow import FixedWorkflowController, RecordedStageResponses


def _git(repository: Path, *arguments: str) -> str:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("GIT_")
    }
    environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    return (
        subprocess.run(
            [
                "git",
                "-c",
                "core.autocrlf=false",
                "-c",
                "core.hooksPath=" + os.devnull,
                "-c",
                "user.name=Agentless Demo",
                "-c",
                "user.email=demo@example.invalid",
                *arguments,
            ],
            cwd=repository,
            env=environment,
            check=True,
            capture_output=True,
        )
        .stdout.decode()
        .strip()
    )


def _repair(operator: str) -> str:
    return (
        "```python\n### calculator.py\n<<<<<<< SEARCH\n"
        "    return a - b\n=======\n"
        f"    return a {operator} b\n>>>>>>> REPLACE\n```"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="python:3.11-slim")
    parser.add_argument("--output", type=Path, default=Path("artifacts/fixed-workflow"))
    parser.add_argument("--implementation-revision", default="working-tree-demo")
    arguments = parser.parse_args()

    root = arguments.output.resolve() / uuid.uuid4().hex
    source = root / "source"
    source.mkdir(parents=True)
    (source / "calculator.py").write_bytes(b"def add(a, b):\n    return a - b\n")
    (source / "test_public.py").write_bytes(
        b"import unittest\nfrom calculator import add\n"
        b"class TestAdd(unittest.TestCase):\n"
        b"    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n"
    )
    _git(source, "init")
    _git(source, "add", ".")
    _git(source, "commit", "-m", "Pinned controlled task")
    commit = _git(source, "rev-parse", "HEAD")

    runner = DockerTestRunner(arguments.image, root / "unused-default-executions")
    task = TaskSpec(
        benchmark=Benchmark.CONTROLLED_FIXTURE,
        benchmark_revision="controlled-fixture-v1",
        instance_id="controlled__python-addition",
        language="python",
        repository_url="local://controlled/python-addition",
        base_commit=commit,
        problem_statement="Make add return the sum of its arguments.",
        container_image=arguments.image,
        container_digest=runner.image_id,
    )
    controller = FixedWorkflowController(
        task=task,
        source_repository=source,
        workspace_root=root / "workspaces",
        artifact_root=root / "runs",
        runner=runner,
        public_commands=(
            PublicTestCommand(("python", "-m", "unittest", "-v", "test_public")),
        ),
        implementation_revision=arguments.implementation_revision,
        harness_revision="controlled-unittest-v1",
        model_name="recorded/controlled-responses",
    )
    result = controller.run(
        RecordedStageResponses(
            file_localization="```\ncalculator.py\n```",
            symbol_localization="```\ncalculator.py\nfunction: add\n```",
            repairs=("malformed sample", _repair("*"), _repair("+")),
            source="checked-in controlled demonstration",
        )
    )
    for attempt in result.attempts:
        statuses = (
            ", ".join(item.status.value for item in attempt.candidate.validation)
            if attempt.candidate
            else attempt.status
        )
        print(f"{attempt.candidate_id}: {statuses}")
    print(f"Selected: {result.prediction.selected_candidate_id}")
    print(f"LLM API calls: {result.run.model_calls}")
    print(f"Run artifacts: {result.artifact_directory}")


if __name__ == "__main__":
    main()
