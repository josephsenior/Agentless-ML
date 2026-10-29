import copy

import pytest

from agentless_ml.runtime_binding import verified_runtime


def inputs():
    image = "sha256:" + "a" * 64
    record = {
        "identity": {"task_id": "task"},
        "spec_sha256": "spec",
        "environment": {"effective_image_id": "parent"},
    }
    registry = {
        "task_bindings": {
            "task": {"prepared_image_id": image, "parent_image_id": "parent"}
        }
    }
    evidence = [
        {
            "task_id": "task",
            "status": "pass",
            "source_spec_sha256": "spec",
            "parent_image_id": "parent",
            "prepared_runtime_image": image,
            "task_toolchain_unchanged": True,
            "parent_image_layers_verified": True,
            "paired_result": {
                "prepared_runtime_image": image,
                "containers_match": True,
                "initial_task_probes_match": True,
            },
        }
    ]
    return record, registry, evidence


def test_verified_binding_keeps_original_task_record():
    record, registry, evidence = inputs()
    original = copy.deepcopy(record)
    assert (
        verified_runtime(record, registry, evidence)
        == registry["task_bindings"]["task"]["prepared_image_id"]
    )
    assert record == original


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_spec_sha256", "wrong"),
        ("status", "blocked"),
        ("prepared_runtime_image", "wrong"),
        ("task_toolchain_unchanged", False),
    ],
)
def test_unverified_runtime_is_rejected(field, value):
    record, registry, evidence = inputs()
    evidence[0][field] = value
    with pytest.raises(ValueError):
        verified_runtime(record, registry, evidence)
