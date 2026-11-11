"""Run independent Agentless tasks with parallel repairs and one Docker slot."""

import argparse
import json
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path

from deepswe_environments import runtime_runner
from run_shared_deepswe_workflow import resolve, _revision
from agentless_ml.attempt_budget import AttemptBudget
from agentless_ml.localization.locations import DEFAULT_MAXIMUM_FILES
from agentless_ml.shared_task import load_shared_task
from agentless_ml.validation import RegressionTest
from agentless_ml.workflow import FixedWorkflowController
from agentless_ml.workflow.subscription import SubscriptionResponses

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", nargs="+", required=True)
    parser.add_argument("--records-root", type=Path, required=True)
    parser.add_argument("--repositories", type=Path, required=True)
    parser.add_argument("--grinta-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="gpt-6.1-sol")
    parser.add_argument("--reasoning", default="xhigh",
                        choices=("low", "medium", "high", "xhigh"))
    args = parser.parse_args()
    if len(set(args.tasks)) != len(args.tasks):
        parser.error("task IDs must be unique")
    args.output.mkdir(parents=True, exist_ok=False)
    prepared = {}
    for task_id in args.tasks:
        record = load_shared_task(args.records_root / task_id / "task.json")
        task, registration, command = resolve(record)
        subprocess.run(
            ["docker", "image", "inspect", record["environment"]["effective_image_id"]],
            check=True, capture_output=True,
        )
        source = args.repositories / task_id
        if not source.is_dir():
            raise ValueError(f"missing checkout for {task_id}")
        prepared[task_id] = (record, task, registration, command, source)

    plan = {
        "task_ids": args.tasks, "model": args.model, "reasoning": args.reasoning,
        "revision": _revision(), "task_concurrency": len(args.tasks),
        "repair_concurrency_per_task": 4, "repair_samples": 4, "edit_samples": 1,
        "maximum_files": DEFAULT_MAXIMUM_FILES,
        "retain_declarations": True,
        "docker_concurrency": 1, "once_only_content_tokens_per_task": 2000000,
        "time_limit_seconds_per_task": 7200,
        "queue_policy": "Docker queue waiting counts toward the task deadline except initial baseline preparation. Scoring occurs after export.",
        "scope": "Agentless-only development batch",
    }
    (args.output / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    docker_gate = threading.Lock()
    results = []

    def run_task(task_id):
        record, task, registration, command, source = prepared[task_id]
        directory = args.output / task_id
        directory.mkdir()
        budget = AttemptBudget.pilot()
        docker_events = []
        result = {"task_id": task_id, "status": "starting", "model_calls": 0}
        try:
            limits = record["environment"]["limits"]
            runner = runtime_runner(
                record["environment"]["effective_image_id"],
                directory / "executions", registration, task=task,
                memory_mb=limits["memory_mb"], cpus=limits["cpus"],
                pids_limit=limits["pids_limit"],
                tmpfs_mb=limits["scratch_mb"] or 4096,
                scratch_mode=limits["scratch_mode"], swap_policy=limits["swap_policy"],
                run_as_image_user=True,
            )
            original_run = runner.run

            def serial_run(source_path, public_command, *, artifact_root=None):
                queued = time.monotonic()
                if not docker_gate.acquire(timeout=max(0.001, budget.remaining)):
                    raise TimeoutError("Docker queue exceeded task deadline")
                acquired = time.monotonic()
                try:
                    if not artifact_root or "regression-baseline" not in str(artifact_root):
                        budget.check()
                    return original_run(
                        source_path, public_command, artifact_root=artifact_root
                    )
                finally:
                    docker_events.append({
                        "kind": "public_validation", "queued": queued,
                        "started": acquired, "finished": time.monotonic(),
                        "artifact_root": str(artifact_root),
                    })
                    docker_gate.release()

            runner.run = serial_run
            workflow = FixedWorkflowController(
                task=replace(task, container_image=runner.image_id,
                             container_digest=runner.image_id),
                source_repository=source, workspace_root=directory / "workspaces",
                artifact_root=directory / "runs", runner=runner, public_commands=(),
                regression_tests=(RegressionTest("suite", command),),
                implementation_revision=_revision(), harness_revision=task.benchmark_revision,
                model_name="chatgpt-plan/" + args.model,
            )
            provider = SubscriptionResponses(
                args.grinta_root, model=args.model, reasoning=args.reasoning
            )
            print(f"{task_id}: starting baseline and fixed workflow", flush=True)
            output = workflow.run_live(
                provider, repair_samples=4, edit_samples=1,
                repair_concurrency=4, budget=budget,
            )
            result.update(status="prediction_exported",
                          artifact_directory=output.artifact_directory,
                          model_calls=output.run.model_calls)
            print(f"{task_id}: prediction exported; waiting for scoring slot", flush=True)
            with docker_gate:
                queued_score = time.monotonic()
                with (directory / "score.log").open("w", encoding="utf-8") as log:
                    scored = subprocess.run(
                        [sys.executable, str(ROOT / "tools/score_deepswe.py"),
                         "--deepswe-repository", str(args.repositories.parent / "corpus"),
                         "--tasks-root", str(args.repositories.parent / "corpus/tasks"),
                         "--task-id", task_id,
                         "--prediction", str(Path(output.artifact_directory) / "prediction.json"),
                         "--artifacts", str(directory / "score")],
                        cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                    )
                docker_events.append({
                    "kind": "scoring", "started": queued_score,
                    "finished": time.monotonic(),
                })
            scores = list((directory / "score").rglob("score.json"))
            if scored.returncode or len(scores) != 1:
                raise RuntimeError("Scoring failed; inspect score.log")
            result.update(status="scored", score=json.loads(scores[0].read_bytes()))
        except Exception as exc:
            result.update(status="failed", error_type=type(exc).__name__, message=str(exc))
        finally:
            result["budget"] = budget.snapshot()
            result["docker_events"] = docker_events
            result["docker_queue_wait_seconds"] = sum(
                event["started"] - event["queued"]
                for event in docker_events if "queued" in event
            )
            runs = list((directory / "runs").glob("*/model-calls")) if (directory / "runs").exists() else []
            result["completed_model_responses"] = sum(
                len(list(path.glob("*/response.json"))) for path in runs
            )
            (directory / "result.json").write_text(
                json.dumps(result, indent=2), encoding="utf-8"
            )
            print(f"{task_id}: {result['status']}", flush=True)
        return result

    with ThreadPoolExecutor(max_workers=len(args.tasks)) as pool:
        futures = {pool.submit(run_task, task_id): task_id for task_id in args.tasks}
        for future in as_completed(futures):
            results.append(future.result())
            (args.output / "results.json").write_text(
                json.dumps(sorted(results, key=lambda r: r["task_id"]), indent=2),
                encoding="utf-8",
            )
    return 0 if all(result["status"] == "scored" for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
