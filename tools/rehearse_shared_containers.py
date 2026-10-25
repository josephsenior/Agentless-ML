"""Observe Agentless Docker and real Pier Docker using one prepared runtime image."""

import argparse
import asyncio
import json
import os
import shlex
import subprocess
import sys
import uuid
from pathlib import Path

from agentless_ml.shared_task import canonical, load_shared_task

ROOT = Path(__file__).resolve().parents[1]
PROBE = r"""
import hashlib,json,os,pathlib,shutil,subprocess
tools={}
for name in ('python','go','node','npm','uv','git','curl'):
 path=shutil.which(name)
 if path:
  p=subprocess.run([path,'version' if name=='go' else '--version'],capture_output=True,timeout=20)
  tools[name]={'path':path,'sha256':hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest(),
   'version':(p.stdout+p.stderr).decode(errors='replace').strip()[:1000]}
source={str(p.relative_to('/tmp/work')):{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'mode':p.stat().st_mode & 0o777}
 for p in pathlib.Path('/tmp/work').rglob('*') if p.is_file() and '.git' not in p.parts}
print('SHARED_PROBE='+json.dumps({'tools':tools,'source':source,'uid':os.getuid(),
 'environment':{k:os.environ.get(k) for k in ('PATH','HOME','GOPATH','GOFLAGS','PYTHONPATH','NODE_PATH')}}))
"""
GRINTA_CHECK = r"""
import asyncio,json,os,pathlib,subprocess,tempfile
from backend.core.config.security_config import SecurityConfig
from backend.execution.server.action_execution_server import RuntimeExecutor
from backend.execution.comparison_edit_guard import ComparisonEditGuard,ComparisonContractError
from backend.ledger.action import FileEditAction,CmdRunAction
from backend.ledger.observation import ErrorObservation
from evaluation.deepswe.run_grinta import _capture_patch

def git(root,*args):
 return subprocess.check_output(['git','-c','user.name=Diagnostic','-c','user.email=test@example.invalid',*args],cwd=root)
root=pathlib.Path('/tmp/work')
git(root,'init');git(root,'add','-f','.');git(root,'commit','-m','controlled base')
results={}
async def check():
 executor=RuntimeExecutor([],str(root),'root',0,False,
  security_config=SecurityConfig(comparison_edit_profile='agentless-ml-v1'))
 try:
  await executor.ainit()
  edited=await executor.run_action(FileEditAction(path=str(root/'calculator.py'),command='replace_string',
   old_string='return a - b',new_str='return a + b'))
  assert not isinstance(edited,ErrorObservation),str(edited)
  moved=await executor.run_action(CmdRunAction(command='mv obsolete.py renamed.py; rm remove.py; printf "created = True\\n" > created.py',cwd=str(root)))
  assert not isinstance(moved,ErrorObservation),str(moved)
  assert not (root/'obsolete.py').exists() and (root/'renamed.py').exists()
  passed=await executor.run_action(CmdRunAction(command='python -m unittest test_public',cwd=str(root)))
  assert not isinstance(passed,ErrorObservation),str(passed)
  assert getattr(passed,'exit_code',None)==0,str(passed)
  patch=_capture_patch(root,executor._comparison_edit_guard.base,comparison_edit_profile='agentless-ml-v1')
  assert patch.strip()
  results['native_file_edit_and_shell_create_delete_rename']=True
  results['controlled_public_test_passed']=True
  results['permitted_patch_exported']=True
  try:
   await executor.run_action(CmdRunAction(command="python -c \"from pathlib import Path; Path('calculator.py').write_bytes(bytes([0]))\"",cwd=str(root)))
  except ComparisonContractError: results['binary_command_stopped_before_feedback']=True
  else: raise AssertionError('binary action accepted')
  try: await executor.run_action(CmdRunAction(command='echo should-not-run',cwd=str(root)))
  except ComparisonContractError: results['next_action_stopped']=True
  else: raise AssertionError('next action accepted')
  try: _capture_patch(root,executor._comparison_edit_guard.base,comparison_edit_profile='agentless-ml-v1')
  except ComparisonContractError: results['invalid_final_patch_rejected']=True
  else: raise AssertionError('invalid export accepted')
 finally: await executor.hard_kill()
asyncio.run(check())
for kind in ('chmod','symlink','new_executable','case_collision','rename_executable_with_edit'):
 with tempfile.TemporaryDirectory(dir='/tmp',prefix='edit-contract-') as td:
  p=pathlib.Path(td);(p/'a.py').write_text('x=1\n');(p/'script.sh').write_text('echo old\n');(p/'script.sh').chmod(0o755)
  git(p,'init');git(p,'add','.');git(p,'commit','-m','base');guard=ComparisonEditGuard(p)
  if kind=='chmod':(p/'a.py').chmod(0o755)
  elif kind=='symlink':(p/'link.py').symlink_to('a.py')
  elif kind=='case_collision':(p/'A.py').write_text('x=2\n')
  elif kind=='new_executable':(p/'new.sh').write_text('echo new\n');(p/'new.sh').chmod(0o755)
  else:(p/'script.sh').rename(p/'moved.sh');(p/'moved.sh').write_text('echo edited\n')
  try:guard.check()
  except ComparisonContractError:
   assert kind!='rename_executable_with_edit';results[kind+'_rejected']=True
  else:
   assert kind=='rename_executable_with_edit';results[kind+'_allowed']=True
print('GRINTA_CHECK='+json.dumps(results))
"""


def observed(inspect):
    host = inspect["HostConfig"]
    return {
        "image_id": inspect["Image"],
        "user": inspect["Config"]["User"] or "root",
        "workdir": inspect["Config"]["WorkingDir"],
        "host": {
            k: host.get(k)
            for k in (
                "NetworkMode",
                "ReadonlyRootfs",
                "CapDrop",
                "SecurityOpt",
                "Memory",
                "MemorySwap",
                "NanoCpus",
                "PidsLimit",
                "Tmpfs",
                "Privileged",
                "ExtraHosts",
                "PortBindings",
            )
        },
        "host_binds": host.get("Binds"),
        "mounts": [
            {"Type": m["Type"], "Destination": m["Destination"]}
            for m in inspect.get("Mounts", [])
        ],
    }


def marker(stdout, name):
    return json.loads(
        next(line[len(name) :] for line in stdout.splitlines() if line.startswith(name))
    )


def fixture(path):
    path.mkdir(parents=True)
    for name, content in {
        "calculator.py": "def add(a,b):\n    return a - b\n",
        "obsolete.py": "old = True\n",
        "remove.py": "remove = True\n",
        ".gitignore": "__pycache__/\n.grinta/\nbuild/\n",
        "test_public.py": "import unittest\nfrom calculator import add\nclass TestAdd(unittest.TestCase):\n def test_add(self): self.assertEqual(add(2,3),5)\n",
    }.items():
        (path / name).write_bytes(content.encode())


async def pier_side(args, record):
    from evaluation.deepswe.shared_environment import create_shared_environment

    environment = create_shared_environment(
        record,
        args.runtime_image,
        args.output / "pier-definition",
        args.output / "pier-trial",
        "shared-" + uuid.uuid4().hex[:12],
    )
    try:
        await environment.start(force_build=False)
        await environment.upload_file(
            args.output / "source.tar", "/tmp/shared-source.tar"
        )
        copied = await environment.exec(
            "mkdir -p /tmp/work && tar --no-same-owner -xf /tmp/shared-source.tar -C /tmp/work",
            timeout_sec=30,
        )
        if copied.return_code:
            raise RuntimeError(copied.stderr)
        probe = await environment.exec(
            "python -c " + shlex.quote(PROBE), cwd="/tmp", timeout_sec=60
        )
        if probe.return_code:
            raise RuntimeError(probe.stderr)
        (args.output / "pier-probe.json").write_bytes(
            canonical(marker(probe.stdout or "", "SHARED_PROBE="))
        )
        ids = await environment._run_docker_compose_command(["ps", "--quiet", "main"])
        inspection = json.loads(
            subprocess.check_output(["docker", "inspect", ids.stdout.strip()])
        )[0]
        (args.output / "pier-container.json").write_bytes(
            canonical(observed(inspection))
        )
        command = (
            "export GRINTA_LOG_ROOT=/tmp/grinta-logs; "
            'python_bin="$(head -n 1 "$HOME/.local/bin/grinta-deepswe" | cut -c 3-)"; '
            '"$python_bin" -c ' + shlex.quote(GRINTA_CHECK)
        )
        check = await environment.exec(command, cwd="/tmp/work", timeout_sec=120)
        (args.output / "grinta-check.stdout.log").write_text(
            check.stdout or "", encoding="utf-8"
        )
        (args.output / "grinta-check.stderr.log").write_text(
            check.stderr or "", encoding="utf-8"
        )
        if check.return_code:
            raise RuntimeError("actual Grinta executor diagnostic failed; see logs")
        (args.output / "grinta-check.json").write_bytes(
            canonical(marker(check.stdout or "", "GRINTA_CHECK="))
        )
    finally:
        await environment.stop(delete=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shared-task", type=Path, required=True)
    parser.add_argument("--runtime-image", required=True)
    parser.add_argument("--grinta-root", type=Path, required=True)
    parser.add_argument("--pier-python", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--side", choices=("both", "pier"), default="both")
    args = parser.parse_args()
    sys.path.insert(0, str(args.grinta_root.resolve()))
    record = load_shared_task(args.shared_task)
    if args.side == "pier":
        asyncio.run(pier_side(args, record))
        return
    from agentless_ml.validation import DockerTestRunner, PublicTestCommand
    from agentless_ml.validation.docker import _snapshot

    if args.output.exists():
        raise ValueError("output must be new")
    args.output.mkdir(parents=True)
    fixture(args.output / "source")
    _snapshot(args.output / "source", args.output / "source.tar")

    class Observer(DockerTestRunner):
        def _docker(self, *argv, **kwargs):
            result = super()._docker(*argv, **kwargs)
            if argv and argv[0] == "inspect":
                (args.output / "agentless-container.json").write_bytes(
                    canonical(observed(json.loads(result.stdout)[0]))
                )
            return result

    limits = record["environment"]["limits"]
    runner = Observer(
        args.runtime_image,
        args.output / "agentless",
        memory_mb=limits["memory_mb"],
        cpus=limits["cpus"],
        pids_limit=limits["pids_limit"],
        tmpfs_mb=limits["scratch_mb"] or 4096,
        scratch_mode=limits["scratch_mode"],
        swap_policy=limits["swap_policy"],
        run_as_image_user=True,
    )
    execution = runner.run(
        args.output / "source",
        PublicTestCommand(("python", "-c", PROBE), timeout_seconds=60),
    )
    if execution.result.exit_code != 0:
        raise RuntimeError("Agentless container probe failed")
    stdout = (Path(execution.artifact_directory) / "stdout.log").read_text()
    (args.output / "agentless-probe.json").write_bytes(
        canonical(marker(stdout, "SHARED_PROBE="))
    )
    child_environment = dict(
        os.environ,
        PYTHONPATH=os.pathsep.join(
            [str(ROOT / "src"), str(args.grinta_root.resolve())]
        ),
    )
    subprocess.run(
        [
            str(args.pier_python),
            str(Path(__file__).resolve()),
            "--side",
            "pier",
            "--shared-task",
            str(args.shared_task.resolve()),
            "--runtime-image",
            args.runtime_image,
            "--grinta-root",
            str(args.grinta_root.resolve()),
            "--output",
            str(args.output.resolve()),
        ],
        env=child_environment,
        check=True,
        timeout=240,
    )

    def read(name):
        return json.loads((args.output / name).read_bytes())

    a, b = read("agentless-container.json"), read("pier-container.json")
    # Compose represents an absent host mapping as [] rather than null.
    for item in (a, b):
        for key in ("ExtraHosts", "PortBindings"):
            item["host"][key] = item["host"][key] or None
        item["host_binds"] = item["host_binds"] or None
    result = {
        "task_id": record["identity"]["task_id"],
        "source_spec_sha256": record["spec_sha256"],
        "prepared_runtime_image": args.runtime_image,
        "containers_match": a == b,
        "initial_task_probes_match": read("agentless-probe.json")
        == read("pier-probe.json"),
        "observed_agentless": a,
        "observed_pier": b,
        "grinta_executor": read("grinta-check.json"),
        "model_calls": 0,
        "benchmark_tests_run": 0,
        "controlled_public_check_run": True,
        "condition": "runtime-supplemented controlled diagnostic; benchmark readiness unchanged",
    }
    (args.output / "result.json").write_bytes(canonical(result))
    print(json.dumps(result))
    if not result["containers_match"] or not result["initial_task_probes_match"]:
        raise RuntimeError("observed container mismatch; inspect result.json")


if __name__ == "__main__":
    main()
