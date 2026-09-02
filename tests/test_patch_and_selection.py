import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from agentless_ml.repair import (
    NoSelectableCandidate,
    build_patch_candidate,
    build_unified_diff,
    normalize_patch,
    select_candidate,
    select_final_prediction,
)
from agentless_ml.schemas import ValidationKind, ValidationResult, ValidationStatus


def _candidate(identifier: str, patch: str, index: int, *results: ValidationResult):
    candidate = build_patch_candidate(
        candidate_id=identifier,
        raw_response=f"response {identifier}",
        diff=patch,
        localization_rank=0,
        sample_index=index,
    )
    return replace(candidate, validation=tuple(results))


def _result(status: ValidationStatus, kind=ValidationKind.REGRESSION):
    return ValidationResult(status, ("pytest",), 1.0, kind=kind)


def test_build_multifile_git_patch_is_sorted_and_stable() -> None:
    old = {"z.py": "z = 1\n", "a.py": "a = 1\n"}
    new = {"z.py": "z = 2\n", "a.py": "a = 2\n"}
    patch = build_unified_diff(old, new)
    assert patch.index("diff --git a/a.py") < patch.index("diff --git a/z.py")
    assert "--- a/a.py\n+++ b/a.py" in patch
    assert patch.endswith("\n")


def test_constructed_patch_passes_git_apply_check(tmp_path: Path) -> None:
    original = {"pkg/a.py": "value = 1\n"}
    updated = {"pkg/a.py": "value = 2\n"}
    target = tmp_path / "pkg" / "a.py"
    target.parent.mkdir()
    target.write_text(original["pkg/a.py"], encoding="utf-8", newline="")
    completed = subprocess.run(
        ["git", "apply", "--check", "-"],
        cwd=tmp_path,
        input=build_unified_diff(original, updated),
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_normalization_ignores_git_metadata_but_preserves_hunk_offsets() -> None:
    first = """diff --git a/a.py b/a.py
index abc..def 100644
--- a/a.py
+++ b/a.py
@@ -1 +1 @@
-old
+new
"""
    second = first.replace("index abc..def 100644\n", "")
    assert normalize_patch(first) == normalize_patch(second)
    moved = second.replace("@@ -1 +1 @@", "@@ -20,1 +20,1 @@")
    assert normalize_patch(first) != normalize_patch(moved)


def test_majority_vote_uses_first_appearance_as_tie_break() -> None:
    patch_a = build_unified_diff({"a.py": "x=1\n"}, {"a.py": "x=2\n"})
    patch_b = build_unified_diff({"a.py": "x=1\n"}, {"a.py": "x=3\n"})
    candidates = [
        _candidate("first", patch_a, 0),
        _candidate("second", patch_b, 1),
    ]
    selected = select_candidate(candidates)
    assert selected.candidate.candidate_id == "first"
    assert selected.reason == "normalized_majority"


def test_regression_then_reproduction_then_majority() -> None:
    patch_a = build_unified_diff({"a.py": "x=1\n"}, {"a.py": "x=2\n"})
    patch_b = build_unified_diff({"a.py": "x=1\n"}, {"a.py": "x=3\n"})
    regression_pass = _result(ValidationStatus.PASS)
    reproduction_fail = _result(ValidationStatus.FAIL, ValidationKind.REPRODUCTION)
    reproduction_pass = _result(ValidationStatus.PASS, ValidationKind.REPRODUCTION)
    candidates = [
        _candidate("popular-1", patch_a, 0, regression_pass, reproduction_fail),
        _candidate("popular-2", patch_a, 1, regression_pass, reproduction_fail),
        _candidate("reproduces", patch_b, 2, regression_pass, reproduction_pass),
    ]
    selected = select_candidate(candidates)
    assert selected.candidate.candidate_id == "reproduces"
    assert selected.reason == (
        "best_regression_then_reproduction_passed_then_normalized_majority"
    )


def test_reproduction_falls_back_to_best_regression_candidates() -> None:
    patch = build_unified_diff({"a.py": "x=1\n"}, {"a.py": "x=2\n"})
    candidate = _candidate(
        "fallback",
        patch,
        0,
        _result(ValidationStatus.PASS),
        _result(ValidationStatus.FAIL, ValidationKind.REPRODUCTION),
    )
    assert "reproduction_fallback" in select_candidate([candidate]).reason


def test_infrastructure_failure_cannot_masquerade_as_test_failure() -> None:
    patch = build_unified_diff({"a.py": "x=1\n"}, {"a.py": "x=2\n"})
    candidate = _candidate("timeout", patch, 0, _result(ValidationStatus.TIMEOUT))
    with pytest.raises(NoSelectableCandidate, match="infrastructure"):
        select_candidate([candidate])


def test_final_prediction_uses_selected_candidate() -> None:
    patch = build_unified_diff({"a.py": "x=1\n"}, {"a.py": "x=2\n"})
    prediction = select_final_prediction(
        instance_id="task-1",
        model_name="provider/model",
        candidates=[_candidate("candidate-1", patch, 0)],
    )
    assert prediction.selected_candidate_id == "candidate-1"
    assert prediction.model_patch == patch
