"""Native full test discovery/type checking only; never execute Cliffy tests."""

import argparse
import json
import tempfile
from dataclasses import replace
from pathlib import Path

from agentless_ml.adapters.benchmarks.deepswe_execution import DENO
from agentless_ml.validation import DockerTestRunner
from agentless_ml.workspace import LocalGitWorkspaceProvider, verify_sealed_repository

ROOT = Path(__file__).resolve().parents[1]
BASE = "132a437c40cffbdfbe474ca808c8debde59e2633"
TASK = "cliffy-config-file-parsing"


def graph_command():
    command = DENO.command((), timeout_seconds=1800)
    script = command.argv[2].replace("deno test --cached-only", "deno test --no-run --cached-only")
    return replace(command, argv=(command.argv[0], command.argv[1], script, *command.argv[3:]), report=None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-id", required=True)
    args = parser.parse_args()
    build = json.loads((ROOT.parent / "output/deepswe-survey/cliffy-cache/build.json").read_text())
    if args.image_id != build["image_id"]:
        raise ValueError("Graph image does not match the recorded build")
    repository = ROOT.parent / "benchmarks/deepswe/repos" / TASK
    verify_sealed_repository(repository, BASE)
    provider = LocalGitWorkspaceProvider(repository, BASE,
        Path(tempfile.gettempdir()) / "agentless-ml-survey-workspaces")
    runner = DockerTestRunner(args.image_id, ROOT.parent / "output/deepswe-survey/cliffy-cache/logs",
        memory_mb=8192, cpus=2, tmpfs_mb=4096, pids_limit=2048, run_as_image_user=True)
    with provider.create() as workspace:
        execution = runner.run(workspace.path, graph_command())
    evidence = {"label": "offline_native_test_import_graph_no_execution",
                "task_id": TASK, "base_commit": BASE, "image_id": runner.image_id,
                "status": execution.result.status.value, "exit_code": execution.result.exit_code,
                "duration_seconds": execution.result.duration_seconds,
                "tests_run": False, "official_survey_updated": False,
                "message": execution.message, "artifacts": execution.artifact_directory}
    (Path(execution.artifact_directory) / "graph-check.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2), flush=True)
    return 0 if execution.result.exit_code == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
