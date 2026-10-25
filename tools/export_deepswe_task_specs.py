"""Export shared, answer-free DeepSWE inputs without Docker or model calls.

The bundle is an interchange artifact, not authorization to launch an experiment.
Historical baselines remain evidence; a changed command is never called matched.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from agentless_ml.adapters.benchmarks import (
    DeepSWEDataset, DeepSWEDatasetPin, deepswe_test_plan,
    load_test_overrides, pinned_load_options,
)
from agentless_ml.adapters.benchmarks.deepswe import (
    HARBOR_DELIVERY_INSTRUCTION, agent_files_digest, project_deepswe_task,
)
from agentless_ml.validation.reports import ReportFormat, parse_report
from agentless_ml.validation.helm_fixtures import IMAGES as HELM_IMAGES, CONTAINER_SETUP
from agentless_ml.validation.helm_fixtures import BASE as HELM_BASE, SPECIAL_LINKS
from agentless_ml.adapters.benchmarks import deepswe_tomlkit, deepswe_wasmi
from agentless_ml.workspace.local_git import _require_git
from deepswe_environments import environment_for, load_environments, runtime_command

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments/deepswe"
CONFIG_PATHS = ("package.json", "go.work", "packages/core/package.json", "packages/react/package.json")


def encoded(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_record(path):
    """Verify an exported record and its retained native public report."""
    path = Path(path)
    record = json.loads(path.read_bytes())
    digest = record.pop("spec_sha256")
    if (record.get("schema_version") != 1 or record.get("kind") != "shared-deepswe-task"
            or sha(encoded(record)) != digest):
        raise ValueError("shared task specification hash or version mismatch")
    baseline_info = record["public_validation"]["baseline"]
    name = baseline_info["native_report_file"]
    if name not in ("baseline-report.json", "baseline-report.xml"):
        raise ValueError("unexpected native report path")
    if sha((path.parent / name).read_bytes()) != baseline_info["native_report_sha256"]:
        raise ValueError("shared task native report hash mismatch")
    record["spec_sha256"] = digest
    return record


def git(repository, *args):
    return _require_git(repository, "-c", f"safe.directory={Path(repository).resolve().as_posix()}", *args, timeout=60)


def pinned_plan(task, repository, override):
    """Read only the plan's four public config paths from Git, never dirty files."""
    listing = git(repository, "ls-tree", "-rz", "--full-tree", task.base_commit)
    entries = {}
    for entry in listing.split(b"\0"):
        if entry:
            metadata, name = entry.split(b"\t", 1)
            entries[name.decode("utf-8")] = metadata.split()
    with tempfile.TemporaryDirectory(prefix="shared-deepswe-plan-") as temporary:
        directory = Path(temporary)
        for name in CONFIG_PATHS:
            if name not in entries:
                continue
            mode, kind, blob = entries[name]
            if kind != b"blob" or mode not in (b"100644", b"100755"):
                raise ValueError(f"non-regular public configuration: {name}")
            path = directory / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(git(repository, "cat-file", "blob", blob.decode()))
        plan = deepswe_test_plan(task.language, directory, override)
    return plan, {
        "git_tree": git(repository, "rev-parse", task.base_commit + "^{tree}").decode().strip(),
        "tree_listing_sha256": sha(listing),
        "hash_definition": "SHA-256 of git ls-tree -rz --full-tree at base_commit; covers names, modes and object IDs",
        "materialization": "pinned Git tree; launchers must seal history and verify their source before execution",
    }


def baseline(task, survey, command, limits):
    """Project a public execution record and reparse its native report."""
    if (survey.get("status") != "ready" or survey.get("task_id") != task.instance_id
            or survey.get("base_commit") != task.base_commit):
        raise ValueError("missing or mismatched registered public baseline")
    directory = Path(survey["artifacts"])
    execution_bytes = (directory / "execution.json").read_bytes()
    execution = json.loads(execution_bytes)
    if execution["image_id"] != survey["image_id"]:
        raise ValueError("baseline image disagrees with its registration")
    report = execution["report"]
    artifact = report["artifact"]
    if artifact not in ("report.json", "report.xml"):
        raise ValueError("unsupported baseline report artifact")
    report_bytes = (directory / artifact).read_bytes()
    for key, data in (("execution_sha256", execution_bytes), ("report_sha256", report_bytes)):
        if key in survey and survey[key] != sha(data):
            raise ValueError(f"baseline {key} does not match registration")
    cases = parse_report(report_bytes, ReportFormat(report["format"]), id_policy=report.get("id_policy"))
    inventory = sorted((asdict(case) for case in cases), key=lambda case: case["test_id"])
    recorded = sorted(execution["result"]["test_cases"], key=lambda case: case["test_id"])
    if inventory != recorded:
        raise ValueError("native report and recorded test inventory disagree")
    counts = Counter(case["status"] for case in inventory)
    if (len(inventory) != survey["tests"] or counts["passed"] != survey["passed"]
            or counts["failed"] + counts["error"] != survey["failed"]
            or counts["skipped"] != survey["skipped"] or counts["passed"] < 1):
        raise ValueError("baseline inventory disagrees with registered counts")
    if execution["result"]["status"] not in ("pass", "fail"):
        raise ValueError("baseline did not complete")
    differences = []
    if execution["result"]["command"] != list(command.argv):
        differences.append("command")
    if execution["failure_exit_codes"] != list(command.failure_exit_codes):
        differences.append("failure_exit_codes")
    if any(report.get(k) != v for k, v in asdict(command.report).items()):
        differences.append("report_contract")
    recorded_limits = execution["limits"]
    # Older records predate explicit volume/swap fields. Keep them unknown;
    # do not manufacture historical evidence from today's defaults.
    if any(recorded_limits.get(k) != v for k, v in limits.items()):
        differences.append("limits_or_missing_historical_limits")
    if execution.get("network_policy") != {"execution_phase": "agent", "docker_network": "none"}:
        differences.append("network_or_missing_historical_network")
    return {
        "execution_sha256": sha(execution_bytes), "native_report_sha256": sha(report_bytes),
        "native_report_file": "baseline-" + artifact,
        "status": execution["result"]["status"], "exit_code": execution["result"]["exit_code"],
        "duration_seconds": execution["result"]["duration_seconds"],
        "image_id": execution["image_id"], "executed_command": execution["result"]["command"],
        "report_contract": {k: report.get(k) for k in ("format", "path", "id_policy")},
        "recorded_limits": recorded_limits, "recorded_network": execution.get("network_policy"),
        "counts": dict(counts), "test_cases": inventory,
        "passing_ids": [case["test_id"] for case in inventory if case["status"] == "passed"],
        "current_command_evidence": "matching" if not differences else "review_required",
        "differences": differences,
    }, execution["user"], report_bytes


def build_record(task, task_directory, repository, override, environment, survey, provenance):
    if not task.container_digest:
        raise ValueError("missing published image pin")
    plan, snapshot = pinned_plan(task, repository, override)
    # Helm's reviewed change retained the schedule and added an ID policy.
    # Keep that report-contract difference visible rather than discard evidence.
    same_runner = survey.get("runner") == plan.runner
    helm_policy_update = (task.instance_id in HELM_IMAGES
                          and survey.get("runner") == "go" and plan.runner == "helm-go")
    if (not (same_runner or helm_policy_update) or survey.get("targets") != list(plan.targets)):
        raise ValueError("registered public schedule differs from the current plan")
    effective_image = environment["image_id"] if environment else task.container_digest
    if survey.get("image_id") != effective_image:
        raise ValueError("baseline image differs from the registered runtime")
    command = runtime_command(plan.command(), environment)
    override = override or {}
    scratch = override.get("scratch_mode", "tmpfs")
    limits = {
        "memory_mb": task.memory_megabytes, "cpus": 2, "pids_limit": 2048,
        "scratch_mode": scratch,
        "scratch_mb": override.get("tmpfs_mb", 4096) if scratch == "tmpfs" else None,
        "swap_policy": override.get("swap_policy", "disabled"),
        "timeout_seconds": command.timeout_seconds,
    }
    evidence, user, report_bytes = baseline(task, survey, command, limits)
    if user.get("run_as_image_user") is not True or not user.get("user"):
        raise ValueError("baseline does not identify the image user")
    profile = environment["profile"] if environment else "published-image"
    hosts = {}
    if profile == "testem-offline-qunit-v1":
        hosts = {"code.jquery.com": "127.0.0.1"}
    elif profile == "pwntools-protocol-services-v1":
        hosts = {name: "127.0.0.1" for name in ("pypi.org", "httpbingo.org", "google.com")}
    setup = {"profile": profile, "registration": environment, "override": override,
             "container_setup": CONTAINER_SETUP if task.instance_id in HELM_IMAGES else None,
             "setup_source_hashes": provenance["setup_source_hashes"]}
    if task.instance_id in HELM_IMAGES:
        if task.base_commit != HELM_BASE or task.container_digest != HELM_IMAGES[task.instance_id]:
            raise ValueError("Helm fixture setup does not match pinned task")
        setup["profile"] = "helm-container-fixtures-v1"
        setup["public_fixture_links"] = SPECIAL_LINKS
        setup["snapshot_policy"] = "defer only the exact Helm links; recreate inside container"
    if plan.runner == "tomlkit-pytest":
        setup["public_fixtures"] = {"commit": deepswe_tomlkit.COMMIT,
            "manifest_sha256": deepswe_tomlkit.MANIFEST_SHA256, "index": deepswe_tomlkit.INDEX}
    elif plan.runner == "wasmi-cargo-nextest":
        setup["public_fixtures"] = deepswe_wasmi.PINS
    projected = project_deepswe_task(task_directory)
    record = {
        "schema_version": 1, "kind": "shared-deepswe-task",
        "identity": {"task_id": task.instance_id, "language": task.language,
            "benchmark_revision": task.benchmark_revision,
            "visible_input_sha256": agent_files_digest((task_directory,)),
            "repository_url": task.repository_url, "base_commit": task.base_commit,
            "source_snapshot": snapshot},
        "problem": {"text": task.problem_statement,
            "delivery_suffix_removed": projected["instruction"].rstrip().endswith(HARBOR_DELIVERY_INSTRUCTION)},
        "environment": {"published_image": task.container_image,
            "published_image_id": task.container_digest, "effective_image_id": effective_image,
            "user": user, "limits": limits, "source_directory": "/tmp/work",
            "exec_working_directory": "/tmp", "writable_paths": ["/tmp"],
            "environment_variables": {"PYTHONDONTWRITEBYTECODE": "1"},
            "environment_inheritance": "pinned image defaults, then explicit command exports",
            "read_only_root": True, "cap_drop": ["ALL"], "no_new_privileges": True,
            "network": {"agent_and_candidate_validation": "none", "provisioning": "network permitted before attempt"},
            "extra_hosts": hosts, "setup": setup, "setup_sha256": sha(encoded(setup))},
        "public_validation": {"runner": plan.runner, "targets": list(plan.targets),
            "historical_baseline_runner": survey["runner"],
            "command": asdict(command), "command_sha256": sha(encoded(asdict(command))),
            "baseline": evidence},
        "edit_contract": {"regular_text": ["modify", "create", "delete", "rename"],
            "preserve_existing_modes": True, "new_file_mode": "100644",
            "binary_mode_symlink_submodule_changes": False,
            "path_rules": "repository-relative, portable paths; no overwrite or case collision on creation/rename",
            "agentless_localization": "existing-file operations require selected source; text edits require localized intervals",
            "comparison_enforcement": "not implemented"},
        "timing": {"published_agent_timeout_seconds": task.timeout_seconds,
            "public_command_timeout_seconds": command.timeout_seconds,
            "agreed_total_attempt_seconds": None},
        "provenance": provenance,
        "launch": {"authorized": False, "unresolved": [
            "shared launchers and capability matching", "exact model and access",
            "agreed model/resource budget", "pilot task selection",
        ] + (["review baseline differences"] if evidence["differences"] else [])},
    }
    record["spec_sha256"] = sha(encoded(record))
    return record, report_bytes


def source_provenance():
    paths = set((ROOT / "src/agentless_ml/adapters/benchmarks").glob("deepswe*.py"))
    paths.update((ROOT / "src/agentless_ml/validation").glob("*.py"))
    paths.add(ROOT / "src/agentless_ml/adapters/benchmarks/go_json_to_ctrf.go")
    for name in ("deepswe_environments.py", "run_testem_qunit_public_test.py",
                 "run_goreleaser_cache_diagnostic.py", "run_pwntools_service_tests.py",
                 "export_deepswe_task_specs.py"):
        paths.add(ROOT / "tools" / name)
    return {"agentless_revision": git(ROOT, "rev-parse", "HEAD").decode().strip(),
        "revision_note": "HEAD is a reference; setup_source_hashes identify exact working-file contents",
        "grinta_revision": None,
        "setup_source_hashes": {p.relative_to(ROOT).as_posix(): sha(p.read_bytes()) for p in sorted(paths)},
        "corpus_pin_sha256": sha((EXPERIMENTS / "corpus_pin.json").read_bytes())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks-root", type=Path, required=True)
    parser.add_argument("--repositories", type=Path, required=True)
    parser.add_argument("--survey", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--task-id", action="append")
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("output must be a new directory")
    pin = json.loads((EXPERIMENTS / "corpus_pin.json").read_text())
    dataset = DeepSWEDataset(args.tasks_root, DeepSWEDatasetPin(
        pin["revision"], pin["agent_files_sha256"], pin["task_count"]))
    tasks = dataset.load_tasks(task_ids=tuple(args.task_id) if args.task_id else None,
                               **pinned_load_options(pin))
    surveys = {row["task_id"]: row for row in map(json.loads, args.survey.read_text().splitlines())}
    overrides = load_test_overrides(EXPERIMENTS / "test_overrides.json")
    environments = load_environments()
    provenance = source_provenance()
    args.output.mkdir(parents=True)
    summary = {"schema_version": 1, "records": [], "errors": [], "launched_runs": 0}
    for task in tasks:
        try:
            record, report = build_record(task, args.tasks_root / task.instance_id,
                args.repositories / task.instance_id, overrides.get(task.instance_id),
                environment_for(task, environments), surveys[task.instance_id], provenance)
            directory = args.output / task.instance_id
            directory.mkdir()
            (directory / "task.json").write_bytes(encoded(record))
            baseline_info = record["public_validation"]["baseline"]
            (directory / baseline_info["native_report_file"]).write_bytes(report)
            summary["records"].append({"task_id": task.instance_id, "spec_sha256": record["spec_sha256"],
                "baseline_evidence": baseline_info["current_command_evidence"],
                "differences": baseline_info["differences"], "counts": baseline_info["counts"]})
        except (ValueError, KeyError, OSError, RuntimeError) as exc:
            summary["errors"].append({"task_id": task.instance_id, "error": str(exc)})
    (args.output / "manifest.json").write_bytes(encoded(summary))
    print(json.dumps({"exported": len(summary["records"]), "errors": summary["errors"],
        "baseline_evidence": dict(Counter(r["baseline_evidence"] for r in summary["records"]))}))
    return bool(summary["errors"])


if __name__ == "__main__":
    raise SystemExit(main())
