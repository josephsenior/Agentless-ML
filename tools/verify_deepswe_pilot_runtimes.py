"""Prepare task-specific core runtimes and observe both runners, without a model.

Only the private Grinta environment, two entrypoints and parser assets are reused
from the previously verified control. Task files and global toolchains stay in
their own pinned parent image. This does not rerun benchmark public baselines.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from package_deepswe_pilot import select_tasks

from agentless_ml.shared_task import canonical, load_shared_task

ROOT = Path(__file__).resolve().parents[1]
CORE = "sha256:3537e0869975ce4e6d66101a4f9236e7e93c3c524b7ec961a1e62e4bbecbe81c"
INSTALLED_COMMIT = "7f8b43a0293c143e2ca6363697baa8185ad3fa34"
PYTHON = "/root/.local/share/uv/tools/grinta/bin/python"
PROBE = r"""
import hashlib,importlib.metadata,json,os,pathlib,shutil,subprocess
tools={}
for name in ('python','go','node','npm','uv','git','curl','rustc','cargo','deno','pnpm'):
 p=shutil.which(name)
 if p:
  r=subprocess.run([p,'version' if name=='go' else '--version'],capture_output=True,timeout=20)
  tools[name]={'path':p,'resolved':str(pathlib.Path(p).resolve()),
   'sha256':hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest(),
   'version':(r.stdout+r.stderr).decode(errors='replace').strip()}
packages=sorted((d.metadata['Name'],d.version) for d in importlib.metadata.distributions())
dpkg=subprocess.run(['dpkg-query','-W','-f=${Package}=${Version}\n'],capture_output=True,check=True)
print(json.dumps({'tools':tools,'python_packages':packages,
 'system_packages_sha256':hashlib.sha256(dpkg.stdout).hexdigest(),
 'environment':{k:os.environ.get(k) for k in ('PATH','HOME','GOPATH','GOMODCACHE','GOFLAGS','PYTHONPATH','NODE_PATH')}}))
"""


def run(argv, *, timeout=120, log=None):
    result = subprocess.run(argv, capture_output=True, timeout=timeout, check=False)
    if log:
        log.with_suffix(".stdout.log").write_bytes(result.stdout)
        log.with_suffix(".stderr.log").write_bytes(result.stderr)
    if result.returncode:
        raise RuntimeError(
            f"command failed ({result.returncode}): {argv[:3]}; {result.stderr.decode(errors='replace')[-1500:]}"
        )
    return result.stdout


def inspect(image):
    info = json.loads(run(["docker", "image", "inspect", image]))[0]
    if (
        info["Os"] != "linux"
        or info["Architecture"] != "amd64"
        or info["Config"].get("Volumes")
    ):
        raise ValueError("unsupported image platform or anonymous volume")
    return info


def probe(image):
    return json.loads(
        run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "--read-only",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--entrypoint",
                "python",
                image,
                "-c",
                PROBE,
            ]
        )
    )


def local_reference(image):
    # BuildKit parses a bare sha256 image ID as a Docker Hub repository name.
    # Give the already inspected local image a deterministic tag and recheck it.
    reference = "agentless-ml/pilot-input:" + image.removeprefix("sha256:")
    run(["docker", "tag", image, reference])
    if inspect(reference)["Id"] != image:
        raise ValueError("local build reference differs from immutable input")
    return reference


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proposal", type=Path, required=True)
    parser.add_argument("--records-root", type=Path, required=True)
    parser.add_argument("--grinta-root", type=Path, required=True)
    parser.add_argument("--pier-python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("output must be a new directory")
    args.output.mkdir(parents=True)
    records = {
        p.parent.name: load_shared_task(p)
        for p in args.records_root.glob("*/task.json")
    }
    selected = select_tasks(records, json.loads(args.proposal.read_bytes()))
    inspect(CORE)
    # Trusted provisioning may fetch parser assets. Execution checks below are offline.
    payload = args.output / "payload"
    payload.mkdir()
    (payload / "Dockerfile").write_text(
        f"FROM {local_reference(CORE)}\n"
        f'RUN {PYTHON} -c "from tree_sitter_language_pack import prefetch; '
        "prefetch(['javascript','typescript','rust'])\"\n",
        encoding="utf-8",
    )
    run(
        [
            "docker",
            "build",
            "--progress=plain",
            "--iidfile",
            str(payload / "image-id"),
            str(payload),
        ],
        timeout=600,
        log=payload / "build",
    )
    payload_id = (payload / "image-id").read_text().strip()
    outcomes = []
    for task_id in selected:
        record = records[task_id]
        directory = args.output / task_id
        directory.mkdir()
        result = {
            "task_id": task_id,
            "source_spec_sha256": record["spec_sha256"],
            "parent_image_id": record["environment"]["effective_image_id"],
            "payload_image_id": payload_id,
            "grinta_commit": INSTALLED_COMMIT,
            "codex_transport_install_complete": False,
            "model_calls": 0,
            "benchmark_tests_run": 0,
            "scope": "core runtime and controlled fixture; not a task baseline",
        }
        try:
            print("VERIFY " + task_id, flush=True)
            parent = inspect(result["parent_image_id"])
            before = probe(parent["Id"])
            (directory / "before.json").write_bytes(canonical(before))
            dockerfile = (
                f"FROM {local_reference(payload_id)} AS core\nFROM {local_reference(parent['Id'])}\n"
                "COPY --from=core /root/.local/share/uv/tools/grinta /root/.local/share/uv/tools/grinta\n"
                "COPY --from=core /root/.local/bin/grinta /root/.local/bin/grinta\n"
                "COPY --from=core /root/.local/bin/grinta-deepswe /root/.local/bin/grinta-deepswe\n"
                "COPY --from=core /root/.cache/tree-sitter-language-pack /root/.cache/tree-sitter-language-pack\n"
            )
            (directory / "Dockerfile").write_text(dockerfile, encoding="utf-8")
            run(
                [
                    "docker",
                    "build",
                    "--network=none",
                    "--progress=plain",
                    "--iidfile",
                    str(directory / "image-id"),
                    str(directory),
                ],
                timeout=300,
                log=directory / "build",
            )
            image = (directory / "image-id").read_text().strip()
            result["prepared_runtime_image"] = image
            prepared = inspect(image)
            result["parent_image_layers_verified"] = (
                prepared["RootFS"]["Layers"][: len(parent["RootFS"]["Layers"])]
                == parent["RootFS"]["Layers"]
            )
            after = probe(image)
            (directory / "after.json").write_bytes(canonical(after))
            result["task_toolchain_unchanged"] = before == after
            if (
                not result["task_toolchain_unchanged"]
                or not result["parent_image_layers_verified"]
            ):
                raise ValueError("task toolchain or parent layers changed")
            language = record["identity"]["language"]
            script = (
                "from tree_sitter_language_pack import get_parser; "
                f'p=get_parser({language!r}); assert p.parse(b" ").root_node; '
                "from backend.execution.server.action_execution_server import RuntimeExecutor; "
                'print("offline parser and executor import passed")'
            )
            run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--network",
                    "none",
                    "--read-only",
                    "--cap-drop",
                    "ALL",
                    "--security-opt",
                    "no-new-privileges",
                    "--tmpfs",
                    "/tmp",
                    "--entrypoint",
                    PYTHON,
                    image,
                    "-c",
                    script,
                ],
                log=directory / "offline-import",
            )
            result["offline_language_parser_and_executor_import"] = True
            run(
                [
                    sys.executable,
                    str(ROOT / "tools/rehearse_shared_containers.py"),
                    "--shared-task",
                    str((args.records_root / task_id / "task.json").resolve()),
                    "--runtime-image",
                    image,
                    "--grinta-root",
                    str(args.grinta_root.resolve()),
                    "--pier-python",
                    str(args.pier_python.resolve()),
                    "--output",
                    str((directory / "paired").resolve()),
                ],
                timeout=420,
                log=directory / "paired-command",
            )
            result["paired_result"] = json.loads(
                (directory / "paired/result.json").read_bytes()
            )
            result["status"] = "pass"
        except (RuntimeError, ValueError, OSError, subprocess.SubprocessError) as exc:
            result.update(status="blocked", error=str(exc))
        (directory / "result.json").write_bytes(canonical(result))
        outcomes.append(result)
        (args.output / "results.json").write_bytes(canonical(outcomes))
        print(task_id + ": " + result["status"], flush=True)
    print(
        json.dumps(
            {
                "passed": sum(x["status"] == "pass" for x in outcomes),
                "total": len(outcomes),
            }
        )
    )


if __name__ == "__main__":
    main()
