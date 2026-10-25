"""Pilot preparation retains evidence without promoting unverified runtimes."""

import copy
import json
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import package_deepswe_pilot as pilot
from test_shared_deepswe_specs import build
from test_shared_deepswe_specs import inputs as input_fixture

inputs = input_fixture


@pytest.fixture
def fixture(inputs, monkeypatch):
    original, report = build(inputs)
    root = inputs[-1] / "records"
    root.mkdir()
    entries = []
    records = {}
    for task_id, language in [
        ("control", "go"),
        ("go-task", "go"),
        ("py-task", "python"),
        ("exposed", "python"),
    ]:
        record = copy.deepcopy(original)
        record["identity"]["task_id"] = task_id
        record["identity"]["language"] = language
        record.pop("spec_sha256")
        record["spec_sha256"] = pilot.digest(pilot.canonical(record))
        directory = root / task_id
        directory.mkdir()
        (directory / "task.json").write_bytes(pilot.canonical(record))
        (directory / "baseline-report.json").write_bytes(report)
        entries.append({"task_id": task_id, "spec_sha256": record["spec_sha256"]})
        records[task_id] = record
    (root / "manifest.json").write_bytes(
        pilot.canonical({"errors": [], "records": entries})
    )
    proposal = {
        "bundle_id": "fixture-pilot",
        "corpus_task_count": 4,
        "benchmark_revision": original["identity"]["benchmark_revision"],
        "languages": ["python", "go"],
        "engineering_control": "control",
        "known_exposures": {"control": ["development"], "exposed": ["prior model run"]},
        "exposure_audit_complete": False,
        "selection": {
            "seed": "fixture",
            "require_published_image": True,
            "maximum_public_command_seconds": 1800,
        },
    }
    image = "sha256:" + "d" * 64
    evidence = {
        "task_toolchain_unchanged": True,
        "parent_image_layers_verified": True,
        "prepared_core_runtime": {
            "status": "pass",
            "parent_image_id": original["environment"]["effective_image_id"],
            "prepared_image_id": image,
            "grinta_commit": "a" * 40,
            "codex_transport_install_complete": False,
        },
        "paired_result": {
            "containers_match": True,
            "initial_task_probes_match": True,
            "source_spec_sha256": records["control"]["spec_sha256"],
            "task_id": "control",
            "prepared_runtime_image": image,
        },
    }
    monkeypatch.setattr(
        pilot,
        "implementation_provenance",
        lambda _: {"agentless_revision": "fixed", "grinta_launcher_revision": "fixed"},
    )
    return root, proposal, evidence


def package(fixture, output):
    records, proposal, evidence = fixture
    return pilot.build_bundle(
        records, Path("unused-grinta"), output, proposal, evidence
    )


def test_bundle_has_control_and_unexposed_proposal_with_no_runtime_promotion(
    fixture, tmp_path
):
    output = tmp_path / "bundle"
    result = package(fixture, output)
    assert result["proposed_tasks"] == ["py-task", "go-task"]
    runtime = json.loads((output / "runtime.json").read_bytes())
    assert set(runtime["task_bindings"]) == {"control"}
    manifest = json.loads((output / "manifest.json").read_bytes())
    assert all(
        t["runtime_status"] == "pending"
        for t in manifest["tasks"]
        if t["role"] == "proposed_pilot"
    )
    common = json.loads((output / "configs/common.json").read_bytes())
    assert common["model"] is None and not common["live_launch_enabled"]
    assert all(v is None for v in common["budgets"].values())
    copied = json.loads((output / "tasks/py-task/task.json").read_bytes())
    assert copied["public_validation"]["baseline"]["counts"] == {
        "failed": 1,
        "passed": 1,
        "skipped": 1,
    }


def test_identical_inputs_produce_identical_zip_bytes(fixture, tmp_path):
    for name in ("one", "two"):
        package(fixture, tmp_path / name)
        pilot.create_zip(tmp_path / name, tmp_path / (name + ".zip"))
    assert (tmp_path / "one.zip").read_bytes() == (tmp_path / "two.zip").read_bytes()
    with zipfile.ZipFile(tmp_path / "one.zip") as archive:
        assert "manifest.json" in archive.namelist()


def test_changed_file_and_extra_file_are_rejected(fixture, tmp_path):
    output = tmp_path / "bundle"
    package(fixture, output)
    file = output / "configs/common.json"
    original = file.read_bytes()
    file.write_bytes(original + b" ")
    with pytest.raises(ValueError, match="checksum"):
        pilot.verify_bundle(output)
    file.write_bytes(original)
    (output / "stale.json").write_bytes(b"{}")
    with pytest.raises(ValueError, match="inventory"):
        pilot.verify_bundle(output)


def test_wrong_control_evidence_cannot_bind_another_image(fixture, tmp_path):
    fixture[2]["paired_result"]["source_spec_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="engineering control"):
        package(fixture, tmp_path / "bad")


def test_enabling_model_is_rejected_even_with_updated_file_checksum(fixture, tmp_path):
    output = tmp_path / "bundle"
    package(fixture, output)
    file = output / "configs/common.json"
    common = json.loads(file.read_bytes())
    common["live_launch_enabled"] = True
    file.write_bytes(pilot.canonical(common))
    manifest_file = output / "manifest.json"
    manifest = json.loads(manifest_file.read_bytes())
    manifest["files_sha256"]["configs/common.json"] = pilot.digest(file.read_bytes())
    manifest_file.write_bytes(pilot.canonical(manifest))
    with pytest.raises(ValueError, match="live model"):
        pilot.verify_bundle(output)


def test_control_image_cannot_be_reused_for_proposed_task(fixture, tmp_path):
    output = tmp_path / "bundle"
    package(fixture, output)
    file = output / "runtime.json"
    runtime = json.loads(file.read_bytes())
    runtime["task_bindings"]["py-task"] = runtime["task_bindings"]["control"]
    file.write_bytes(pilot.canonical(runtime))
    manifest_file = output / "manifest.json"
    manifest = json.loads(manifest_file.read_bytes())
    manifest["files_sha256"]["runtime.json"] = pilot.digest(file.read_bytes())
    manifest_file.write_bytes(pilot.canonical(manifest))
    with pytest.raises(ValueError, match="unverified tasks"):
        pilot.verify_bundle(output)


def test_reviewed_selection_excludes_other_tasks_from_an_exposed_repository(fixture):
    root, proposal, _ = fixture
    records = {
        p.parent.name: json.loads(p.read_bytes()) for p in root.glob("*/task.json")
    }
    alternate = copy.deepcopy(records["py-task"])
    alternate["identity"].update(
        task_id="fresh-python", repository_url="https://github.com/fresh/python"
    )
    records["fresh-python"] = alternate
    records["go-task"]["identity"]["repository_url"] = "https://github.com/fresh/go"
    proposal["selection"]["exclude_known_exposed_repositories"] = True
    assert pilot.select_tasks(records, proposal) == ["fresh-python", "go-task"]


def runtime_evidence(fixture):
    root, proposal, control = fixture
    records = {
        p.parent.name: json.loads(p.read_bytes()) for p in root.glob("*/task.json")
    }
    items = []
    for task_id in pilot.select_tasks(records, proposal):
        record = records[task_id]
        image = "sha256:" + pilot.digest(task_id.encode())
        items.append(
            {
                "task_id": task_id,
                "status": "pass",
                "source_spec_sha256": record["spec_sha256"],
                "parent_image_id": record["environment"]["effective_image_id"],
                "prepared_runtime_image": image,
                "task_toolchain_unchanged": True,
                "parent_image_layers_verified": True,
                "offline_language_parser_and_executor_import": True,
                "grinta_commit": "a" * 40,
                "codex_transport_install_complete": False,
                "paired_result": {
                    **control["paired_result"],
                    "task_id": task_id,
                    "source_spec_sha256": record["spec_sha256"],
                    "prepared_runtime_image": image,
                    "grinta_executor": {"controlled_public_test_passed": True},
                },
            }
        )
    return items


def test_verified_pilot_images_are_bound_to_their_own_task(fixture, tmp_path):
    root, proposal, control = fixture
    output = tmp_path / "bundle"
    pilot.build_bundle(
        root,
        Path("unused"),
        output,
        proposal,
        control,
        pilot_evidence=runtime_evidence(fixture),
    )
    runtime = json.loads((output / "runtime.json").read_bytes())
    assert set(runtime["task_bindings"]) == {"control", "py-task", "go-task"}
    assert len({v["prepared_image_id"] for v in runtime["task_bindings"].values()}) == 3
    assert (output / "evidence/pilot-runtimes.json").exists()


@pytest.mark.parametrize("change", ["wrong_spec", "missing_task", "failed_executor"])
def test_incomplete_or_mismatched_runtime_cannot_be_promoted(fixture, tmp_path, change):
    root, proposal, control = fixture
    items = runtime_evidence(fixture)
    if change == "wrong_spec":
        items[0]["source_spec_sha256"] = "0" * 64
    elif change == "missing_task":
        items.pop()
    else:
        items[0]["paired_result"]["grinta_executor"][
            "controlled_public_test_passed"
        ] = False
    with pytest.raises(ValueError, match="pilot runtime evidence"):
        pilot.build_bundle(
            root,
            Path("unused"),
            tmp_path / "bundle",
            proposal,
            control,
            pilot_evidence=items,
        )
