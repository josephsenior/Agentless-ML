"""Short metadata/behavior diagnostic only; never runs Go tests or changes readiness."""

import argparse
import json
import tempfile
from pathlib import Path

from agentless_ml.adapters.benchmarks import DeepSWEDataset, DeepSWEDatasetPin, pinned_load_options
from agentless_ml.validation import PublicTestCommand
from agentless_ml.validation.helm_fixtures import ALL_LINKS, IMAGES, SPECIAL_LINKS
from agentless_ml.workspace import LocalGitWorkspaceProvider, verify_sealed_repository
from deepswe_environments import runtime_runner

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTIC = r'''
import json, os, stat, tempfile
from pathlib import Path
root = Path("/tmp/work")
links = json.loads(LINKS_JSON)
observed = []
with tempfile.TemporaryDirectory(prefix="helm-link-copy-") as temporary:
    for index, (relative, target) in enumerate(links.items()):
        link = root / relative
        if not stat.S_ISLNK(link.lstat().st_mode) or os.readlink(link) != target:
            raise RuntimeError("wrong reconstructed link: " + relative)
        copy = Path(temporary) / str(index)
        os.symlink(os.readlink(link), copy)
        if os.readlink(copy) != target:
            raise RuntimeError("symlink target did not survive metadata-only copy")
        if target == "/dev/null":
            device = link.stat()
            if not stat.S_ISCHR(device.st_mode) or (os.major(device.st_rdev), os.minor(device.st_rdev)) != (1, 3):
                raise RuntimeError("wrong /dev/null behavior")
            behavior = "native character device 1:3"
        elif target == "../test.file":
            if link.read_bytes() != (link.parent / target).read_bytes():
                raise RuntimeError("relative fixture does not resolve to candidate data")
            behavior = "relative link resolves inside candidate"
        else:
            if link.exists():
                raise RuntimeError("expected dangling fixture resolved")
            behavior = "dangling; target text preserved"
        observed.append({"path": relative, "target": target, "behavior": behavior,
                         "metadata_copy_target_preserved": True})
if (root / ".git").exists():
    raise RuntimeError("Git metadata entered candidate container")
print(json.dumps({"condition": "Helm link-behavior diagnostic only; no public tests", "links": observed}, sort_keys=True))
'''.replace("LINKS_JSON", repr(json.dumps(ALL_LINKS))).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks-root", type=Path, default=ROOT.parent / "benchmarks/deepswe/corpus/tasks")
    parser.add_argument("--repositories", type=Path, default=ROOT.parent / "benchmarks/deepswe/repos")
    parser.add_argument("--artifacts", type=Path, default=ROOT.parent / "output/deepswe-helm-fixture-diagnostic")
    args = parser.parse_args()
    pin = json.loads((ROOT / "experiments/deepswe/corpus_pin.json").read_text())
    tasks = DeepSWEDataset(args.tasks_root, DeepSWEDatasetPin(
        pin["revision"], pin["agent_files_sha256"], pin["task_count"],
    )).load_tasks(task_ids=tuple(IMAGES), **pinned_load_options(pin))
    for task in tasks:
        source = args.repositories / task.instance_id
        verify_sealed_repository(source, task.base_commit)
        runner = runtime_runner(task.container_image, args.artifacts / task.instance_id, None,
                                task=task, memory_mb=task.memory_megabytes, cpus=2,
                                pids_limit=2048, tmpfs_mb=4096, run_as_image_user=True)
        with LocalGitWorkspaceProvider(
            source, task.base_commit, Path(tempfile.gettempdir()) / "agentless-helm-link-workspaces",
        ).create() as workspace:
            execution = runner.run(workspace.path, PublicTestCommand(
                ("python", "-c", DIAGNOSTIC), timeout_seconds=60,
            ))
        record = {
            "condition": "short container-only Helm link-behavior diagnostic; no baseline",
            "task_id": task.instance_id, "base_commit": task.base_commit,
            "image_id": runner.image_id, "status": execution.result.status.value,
            "exit_code": execution.result.exit_code, "seconds": execution.result.duration_seconds,
            "public_tests_run": False, "readiness_changed": False,
            "special_links": SPECIAL_LINKS, "workspace_setup": runner.workspace_setup,
            "observed_host_config": {key: runner.observed_host_config[key] for key in (
                "NetworkMode", "ReadonlyRootfs", "CapDrop", "SecurityOpt", "Memory",
                "MemorySwap", "NanoCpus", "PidsLimit", "Tmpfs", "Privileged",
                "ExtraHosts", "PortBindings", "Binds",
            )} if runner.observed_host_config else None,
            "artifacts": execution.artifact_directory, "message": execution.message,
        }
        directory = Path(execution.artifact_directory)
        (directory / "diagnostic.json").write_text(json.dumps(record, indent=2) + "\n")
        print(json.dumps(record, indent=2), flush=True)
        if execution.result.status.value != "pass":
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
