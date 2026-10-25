"""Package the verified runtime control and a proposed small DeepSWE pilot.

No model calls, provisioning or benchmark tests. Images remain separate immutable
inputs; this bundle contains public task records, configs and existing evidence.
"""

import argparse
import json
import re
import subprocess
import zipfile
from pathlib import Path, PurePosixPath

from agentless_ml.shared_task import canonical, digest, load_shared_task

ROOT = Path(__file__).resolve().parents[1]
PROPOSAL = ROOT / "experiments/pilots/deepswe_small_v1/proposal.json"
EVIDENCE = ROOT / "experiments/deepswe/shared_container_rehearsal_2026_10_25.json"


def select_tasks(records, proposal):
    """Select by public eligibility and a fixed hash, never by model outcomes."""
    selected = []
    exposed_repositories = {
        records[task_id]["identity"]["repository_url"]
        for task_id in proposal["known_exposures"]
        if task_id in records
    }
    for language in proposal["languages"]:
        eligible = [
            r
            for r in records.values()
            if r["identity"]["language"] == language
            and r["identity"]["task_id"] not in proposal["known_exposures"]
            and r["identity"]["task_id"] != proposal["engineering_control"]
            and (
                not proposal["selection"].get(
                    "exclude_known_exposed_repositories", False
                )
                or r["identity"]["repository_url"] not in exposed_repositories
            )
            and r["public_validation"]["baseline"]["passing_ids"]
            and (
                not proposal["selection"]["require_published_image"]
                or r["environment"]["setup"]["registration"] is None
            )
            and r["timing"]["public_command_timeout_seconds"]
            <= proposal["selection"]["maximum_public_command_seconds"]
        ]
        if not eligible:
            raise ValueError(f"no eligible proposed task for {language}")

        def rank(record, language=language):
            text = "\0".join(
                (proposal["selection"]["seed"], language, record["identity"]["task_id"])
            )
            return digest(text.encode())

        selected.append(min(eligible, key=rank)["identity"]["task_id"])
    return selected


def validate_runtime(control, evidence):
    runtime = evidence["prepared_core_runtime"]
    pair = evidence["paired_result"]
    if (
        runtime["status"] != "pass"
        or not evidence["task_toolchain_unchanged"]
        or not evidence["parent_image_layers_verified"]
        or not pair["containers_match"]
        or not pair["initial_task_probes_match"]
        or pair["source_spec_sha256"] != control["spec_sha256"]
        or pair["task_id"] != control["identity"]["task_id"]
        or runtime["parent_image_id"] != control["environment"]["effective_image_id"]
        or runtime["prepared_image_id"] != pair["prepared_runtime_image"]
    ):
        raise ValueError(
            "verified runtime evidence does not match the engineering control"
        )
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", runtime["prepared_image_id"]):
        raise ValueError("runtime image must be immutable")
    return runtime


def validate_pilot_runtimes(records, selected, evidence):
    bindings = {}
    for item in evidence:
        task_id = item["task_id"]
        if task_id not in selected or task_id in bindings:
            raise ValueError("unexpected or duplicate pilot runtime evidence")
        record = records[task_id]
        pair = item.get("paired_result", {})
        if (
            item.get("status") != "pass"
            or item.get("source_spec_sha256") != record["spec_sha256"]
            or item.get("parent_image_id")
            != record["environment"]["effective_image_id"]
            or not item.get("task_toolchain_unchanged")
            or not item.get("parent_image_layers_verified")
            or not item.get("offline_language_parser_and_executor_import")
            or not pair.get("containers_match")
            or not pair.get("initial_task_probes_match")
            or pair.get("task_id") != task_id
            or pair.get("source_spec_sha256") != record["spec_sha256"]
            or pair.get("prepared_runtime_image") != item.get("prepared_runtime_image")
            or not pair.get("grinta_executor")
            or not all(pair["grinta_executor"].values())
            or not re.fullmatch(
                r"sha256:[0-9a-f]{64}", item.get("prepared_runtime_image", "")
            )
        ):
            raise ValueError("pilot runtime evidence does not verify its task")
        bindings[task_id] = {
            "parent_image_id": item["parent_image_id"],
            "prepared_image_id": item["prepared_runtime_image"],
            "grinta_commit": item["grinta_commit"],
            "codex_transport_install_complete": item[
                "codex_transport_install_complete"
            ],
        }
    if set(bindings) != set(selected):
        raise ValueError("pilot runtime evidence must cover the selected tasks")
    return bindings


def implementation_provenance(grinta_root):
    def revision(root):
        return (
            subprocess.check_output(
                [
                    "git",
                    "-c",
                    f"safe.directory={root.as_posix()}",
                    "-C",
                    str(root),
                    "rev-parse",
                    "HEAD",
                ]
            )
            .decode()
            .strip()
        )

    return {
        "agentless_revision": revision(ROOT),
        "grinta_launcher_revision": revision(grinta_root),
        "packager_sha256": digest(Path(__file__).read_bytes()),
        "note": "Installed Grinta revision is pinned separately in runtime.json.",
    }


def check_image(image_id):
    info = json.loads(
        subprocess.check_output(["docker", "image", "inspect", image_id])
    )[0]
    if info["Id"] != image_id or info["Os"] != "linux" or info["Config"].get("Volumes"):
        raise ValueError(
            "local runtime image does not match the supported immutable image"
        )


def create_zip(directory, destination):
    if destination.exists():
        raise ValueError("archive destination must be new")
    with zipfile.ZipFile(
        destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for file in sorted(directory.rglob("*")):
            if file.is_file():
                entry = zipfile.ZipInfo(
                    file.relative_to(directory).as_posix(), (2026, 10, 25, 0, 0, 0)
                )
                entry.compress_type = zipfile.ZIP_DEFLATED
                entry.create_system = 3
                entry.external_attr = 0o100644 << 16
                archive.writestr(entry, file.read_bytes())


def verify_bundle(directory):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_bytes())
    expected = set(manifest["files_sha256"])
    actual = {
        p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()
    }
    if actual != expected | {"manifest.json"}:
        raise ValueError("bundle file inventory changed")
    for name, expected_hash in manifest["files_sha256"].items():
        path = PurePosixPath(name)
        file = directory / name
        if (
            path.is_absolute()
            or ".." in path.parts
            or file.is_symlink()
            or not file.resolve().is_relative_to(directory.resolve())
        ):
            raise ValueError("unsafe bundle path")
        if digest(file.read_bytes()) != expected_hash:
            raise ValueError(f"bundle checksum mismatch: {name}")
    common = json.loads((directory / "configs/common.json").read_bytes())
    if common["live_launch_enabled"] is not False or common["model"] is not None:
        raise ValueError("this preparation bundle must not enable a live model")
    runtime = json.loads((directory / "runtime.json").read_bytes())
    control_id = manifest["engineering_control"]
    records = {
        item["task_id"]: load_shared_task(directory / item["task_file"])
        for item in manifest["tasks"]
    }
    validate_runtime(
        records[control_id],
        json.loads((directory / "evidence/container-rehearsal.json").read_bytes()),
    )
    pilot_bindings = {}
    review_file = directory / "evidence/pilot-runtimes.json"
    if review_file.exists():
        pilot_bindings = validate_pilot_runtimes(
            records,
            [i["task_id"] for i in manifest["tasks"] if i["role"] == "proposed_pilot"],
            json.loads(review_file.read_bytes()),
        )
    if set(runtime["task_bindings"]) != {control_id, *pilot_bindings}:
        raise ValueError(
            "verified control image must not be assigned to unverified tasks"
        )
    if any(
        runtime["task_bindings"][key] != value for key, value in pilot_bindings.items()
    ):
        raise ValueError("pilot runtime binding differs from observed evidence")
    if (
        runtime["task_bindings"][control_id]["prepared_image_id"]
        != manifest["verified_runtime_image"]
    ):
        raise ValueError("runtime binding differs from the manifest")
    if any(
        item["task_id"] in manifest["known_exposures"]
        for item in manifest["tasks"]
        if item["role"] == "proposed_pilot"
    ):
        raise ValueError("known exposed task entered the proposed pilot")
    for arm in ("agentless-ml", "grinta", "mainstream-agent"):
        config = json.loads((directory / f"configs/{arm}.json").read_bytes())
        if (
            config["live_launch_enabled"] is not False
            or config["common_settings"] != "common.json"
        ):
            raise ValueError("arm overrides shared preparation settings")
    return {
        "bundle_id": manifest["bundle_id"],
        "verified_files": len(expected),
        "proposed_tasks": [
            item["task_id"]
            for item in manifest["tasks"]
            if item["role"] == "proposed_pilot"
        ],
        "engineering_control": control_id,
        "live_launch_enabled": False,
    }


def build_bundle(
    records_root,
    grinta_root,
    output,
    proposal,
    evidence,
    *,
    inspect_image=False,
    pilot_evidence=None,
):
    if output.exists():
        raise ValueError("bundle output must be a new directory")
    inventory = json.loads((records_root / "manifest.json").read_bytes())
    if (
        inventory["errors"]
        or len(inventory["records"]) != proposal["corpus_task_count"]
    ):
        raise ValueError("shared record inventory is incomplete")
    records = {}
    for entry in inventory["records"]:
        task_id = entry["task_id"]
        if task_id in records:
            raise ValueError("duplicate task in shared record inventory")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,127}", task_id):
            raise ValueError("unsafe task ID")
        record = load_shared_task(records_root / task_id / "task.json")
        if (
            record["identity"]["task_id"] != task_id
            or record["spec_sha256"] != entry["spec_sha256"]
            or record["identity"]["benchmark_revision"]
            != proposal["benchmark_revision"]
        ):
            raise ValueError("shared record does not match pinned corpus inventory")
        records[task_id] = record
    selected = select_tasks(records, proposal)
    control_id = proposal["engineering_control"]
    runtime = validate_runtime(records[control_id], evidence)
    pilot_bindings = (
        validate_pilot_runtimes(records, selected, pilot_evidence)
        if pilot_evidence is not None
        else {}
    )
    if inspect_image:
        check_image(runtime["prepared_image_id"])
        for binding in pilot_bindings.values():
            check_image(binding["prepared_image_id"])
    output.mkdir(parents=True)

    def write(name, data):
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(canonical(data))

    task_entries = []
    for task_id in [control_id, *selected]:
        record = records[task_id]
        role = "engineering_control" if task_id == control_id else "proposed_pilot"
        write(f"tasks/{task_id}/task.json", record)
        report_name = record["public_validation"]["baseline"]["native_report_file"]
        (output / "tasks" / task_id / report_name).write_bytes(
            (records_root / task_id / report_name).read_bytes()
        )
        task_entries.append(
            {
                "task_id": task_id,
                "language": record["identity"]["language"],
                "role": role,
                "task_file": f"tasks/{task_id}/task.json",
                "spec_sha256": record["spec_sha256"],
                "runtime_status": "controlled_rehearsal_verified"
                if role == "engineering_control"
                else (
                    "controlled_rehearsal_verified"
                    if task_id in pilot_bindings
                    else "pending"
                ),
                "baseline_evidence": record["public_validation"]["baseline"][
                    "current_command_evidence"
                ],
            }
        )
    write("proposal.json", proposal)
    write("evidence/container-rehearsal.json", evidence)
    if pilot_evidence is not None:
        write("evidence/pilot-runtimes.json", pilot_evidence)
    write(
        "runtime.json",
        {
            "schema_version": 1,
            "scope": "core runtime only; model transport deferred",
            "task_bindings": {
                control_id: {
                    k: runtime[k]
                    for k in (
                        "parent_image_id",
                        "prepared_image_id",
                        "grinta_commit",
                        "codex_transport_install_complete",
                    )
                },
                **pilot_bindings,
            },
            "local_image_inspected": inspect_image,
            "other_tasks": "Require separately prepared runtime images and observed matching; never reuse the control image blindly.",
        },
    )
    write(
        "configs/common.json",
        {
            "kind": "pilot-preparation-settings",
            "live_launch_enabled": False,
            "model": None,
            "model_access": None,
            "reasoning_effort": None,
            "budgets": {
                "total_attempt_seconds": None,
                "input_tokens": None,
                "output_tokens": None,
                "sample_allocation": None,
                "retry_policy": None,
            },
            "public_command_limits": "Use each task record; these are not total attempt budgets.",
            "gates_before_live_run": [
                "review/freeze pilot selection and exposure audit",
                "prepare and verify each selected runtime image",
                "review historical baseline differences",
                "select model and access",
                "agree and enforce aggregate budgets",
                "choose and integrate mainstream comparison agent",
                "freeze scoring configuration",
            ],
        },
    )
    for arm, extra in {
        "agentless-ml": {
            "workflow": "fixed",
            "entrypoint": "tools/run_shared_deepswe_workflow.py",
        },
        "grinta": {
            "workflow": "adaptive",
            "entrypoint": "evaluation.deepswe.run_grinta",
            "environment_factory": "evaluation.deepswe.shared_environment.create_shared_environment",
            "comparison_edit_profile": "agentless-ml-v1",
        },
        "mainstream-agent": {"agent": None, "entrypoint": None},
    }.items():
        write(
            f"configs/{arm}.json",
            {
                "kind": "pilot-arm-contract",
                "arm": arm,
                "live_launch_enabled": False,
                "common_settings": "common.json",
                "runtime_registry": "../runtime.json",
                "task_files": [f"../tasks/{i}/task.json" for i in selected],
                **extra,
            },
        )
    readme = (
        "# DeepSWE small pilot preparation\n\n"
        "This bundle packages public task records, public baseline reports, comparison contracts and existing evidence.\n"
        "The proposal contains one task per language. Selection is provisional; known exposed tasks are excluded.\n"
        "Actionlint is an exposed engineering control, not an unseen research result.\n\n"
        + (
            "All five proposed tasks have separate verified core-runtime images. These checks use a controlled fixture, not full task baselines.\n"
            if pilot_bindings
            else "Only the control has a verified prepared core-runtime image. The other runtime images remain pending.\n"
        )
        + "Docker images and source repositories are separate inputs identified by immutable pins.\n"
        "Installed Grinta code is pinned separately from the current launcher revisions.\n\n"
        "Verify integrity from Agentless-ML: python tools/package_deepswe_pilot.py verify --bundle <this-folder>\n"
        "For the model-free control, use tools/rehearse_shared_containers.py with the control task.json,\n"
        "the runtime.json image pin, the Grinta checkout, the Pier interpreter and a new output directory.\n\n"
        "Live execution is disabled. Resolve the gates in configs/common.json before any model run.\n"
    )
    (output / "README.md").write_bytes(readme.encode())
    manifest = {
        "schema_version": 1,
        "bundle_id": proposal["bundle_id"],
        "status": "preparation_only",
        "selection_frozen": False,
        "engineering_control": control_id,
        "tasks": task_entries,
        "known_exposures": proposal["known_exposures"],
        "exposure_audit_complete": proposal["exposure_audit_complete"],
        "verified_runtime_image": runtime["prepared_image_id"],
        "implementations": implementation_provenance(grinta_root),
        "files_sha256": {
            p.relative_to(output).as_posix(): digest(p.read_bytes())
            for p in sorted(output.rglob("*"))
            if p.is_file()
        },
    }
    write("manifest.json", manifest)
    return verify_bundle(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--records-root", type=Path, required=True)
    build.add_argument("--grinta-root", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--proposal", type=Path, default=PROPOSAL)
    build.add_argument("--pilot-runtime-evidence", type=Path)
    build.add_argument("--check-local-image", action="store_true")
    build.add_argument("--zip", type=Path)
    verify = commands.add_parser("verify")
    verify.add_argument("--bundle", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "verify":
        print(json.dumps(verify_bundle(args.bundle)))
        return
    result = build_bundle(
        args.records_root,
        args.grinta_root,
        args.output,
        json.loads(args.proposal.read_bytes()),
        json.loads(EVIDENCE.read_bytes()),
        inspect_image=args.check_local_image,
        pilot_evidence=(
            json.loads(args.pilot_runtime_evidence.read_bytes())
            if args.pilot_runtime_evidence
            else None
        ),
    )
    if args.zip:
        create_zip(args.output, args.zip)
        result["zip_sha256"] = digest(args.zip.read_bytes())
    print(json.dumps(result))


if __name__ == "__main__":
    main()
