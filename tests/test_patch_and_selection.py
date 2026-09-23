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


@pytest.mark.parametrize(
    "old,new",
    [
        ("value = 1\n", "value = 2\n"),
        ("value = 1", "value = 2"),
        ("value = 1", "value = 1\n"),
        ("value = 1\n", "value = 1"),
        ("value = 1\n", "value = 2  \n"),
        ("value = 1\r\n", "value = 2\r\n"),
    ],
)
def test_constructed_patch_passes_git_apply_check(
    tmp_path: Path, old: str, new: str
) -> None:
    original = {"pkg/a.py": old}
    updated = {"pkg/a.py": new}
    target = tmp_path / "pkg" / "a.py"
    target.parent.mkdir()
    target.write_text(original["pkg/a.py"], encoding="utf-8", newline="")
    completed = subprocess.run(
        ["git", "-c", "core.autocrlf=false", "apply", "--check", "-"],
        cwd=tmp_path,
        input=build_unified_diff(original, updated).encode(),
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    candidate = build_patch_candidate(
        candidate_id="exact-bytes",
        raw_response="fixture",
        diff=build_unified_diff(original, updated),
        localization_rank=0,
        sample_index=0,
    )
    applied = subprocess.run(
        ["git", "-c", "core.autocrlf=false", "apply", "--whitespace=nowarn", "-"],
        cwd=tmp_path,
        input=candidate.diff.encode(),
        capture_output=True,
        check=False,
    )
    assert applied.returncode == 0, applied.stderr
    assert target.read_bytes() == new.encode()


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


@pytest.mark.parametrize(
    ("language", "path", "original", "fixed_plain", "fixed_commented"),
    [
        (
            "python",
            "calculator.py",
            "def add(a, b):\n    return a - b\n",
            "def add(a, b):\n    return a + b\n",
            "def add(a, b):\n    # fixed: was subtracting instead of adding\n"
            "    return a + b\n",
        ),
        (
            "go",
            "calculator.go",
            "package p\n\nfunc Add(a, b int) int {\n    return a - b\n}\n",
            "package p\n\nfunc Add(a, b int) int {\n    return a + b\n}\n",
            "package p\n\nfunc Add(a, b int) int {\n"
            "    // fixed: was subtracting instead of adding\n"
            "    return a + b\n}\n",
        ),
    ],
)
def test_comment_only_repairs_vote_together_across_languages(
    language: str, path: str, original: str, fixed_plain: str, fixed_commented: str
) -> None:
    """Two candidates make the identical fix; one repair also adds a whole
    new comment line that does not exist in the other candidate's version."""
    plain = build_patch_candidate(
        candidate_id="plain",
        raw_response="plain",
        diff=build_unified_diff({path: original}, {path: fixed_plain}),
        localization_rank=0,
        sample_index=0,
        language=language,
        original_sources={path: original},
        updated_sources={path: fixed_plain},
    )
    commented = build_patch_candidate(
        candidate_id="commented",
        raw_response="commented",
        diff=build_unified_diff({path: original}, {path: fixed_commented}),
        localization_rank=0,
        sample_index=1,
        language=language,
        original_sources={path: original},
        updated_sources={path: fixed_commented},
    )
    # Different real diff text (one has an extra comment line) ...
    assert plain.diff != commented.diff
    # ... but the same voting key, because the comment line disappears entirely
    # rather than leaving a blank line the other candidate's diff lacks.
    assert plain.normalized_diff == commented.normalized_diff


def test_comment_normalization_is_opt_in_and_backward_compatible() -> None:
    """Without sources, voting stays on the plain textual key, as before."""
    path = "calculator.py"
    old, new_plain = "def add(a, b):\n    return a - b\n", "def add(a, b):\n    return a + b\n"
    new_commented = "def add(a, b):\n    # fixed\n    return a + b\n"
    plain = build_patch_candidate(
        candidate_id="plain",
        raw_response="plain",
        diff=build_unified_diff({path: old}, {path: new_plain}),
        localization_rank=0,
        sample_index=0,
    )
    commented = build_patch_candidate(
        candidate_id="commented",
        raw_response="commented",
        diff=build_unified_diff({path: old}, {path: new_commented}),
        localization_rank=0,
        sample_index=1,
    )
    assert plain.normalized_diff != commented.normalized_diff


def test_comment_only_change_falls_back_to_textual_key() -> None:
    """A repair that only adds a comment must not crash candidate construction."""
    path = "calculator.py"
    old = "def add(a, b):\n    return a + b\n"
    new = "def add(a, b):\n    # already correct\n    return a + b\n"
    candidate = build_patch_candidate(
        candidate_id="comment-only",
        raw_response="comment-only",
        diff=build_unified_diff({path: old}, {path: new}),
        localization_rank=0,
        sample_index=0,
        language="python",
        original_sources={path: old},
        updated_sources={path: new},
    )
    # No crash, and still a usable, non-empty voting key (the plain textual one).
    assert candidate.normalized_diff.strip()
    assert candidate.normalized_diff == normalize_patch(candidate.diff)


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


COUNTED = tuple(f"suite::test_{n}" for n in range(1731))


def _suite(broken: tuple[str, ...] = (), *, build_failed: bool = False) -> ValidationResult:
    from agentless_ml.schemas import TestCaseResult, TestCaseStatus

    cases = () if build_failed else tuple(
        TestCaseResult(
            test_id,
            TestCaseStatus.FAILED if test_id in broken else TestCaseStatus.PASSED,
        )
        for test_id in COUNTED
    )
    status = ValidationStatus.FAIL if build_failed or broken else ValidationStatus.PASS
    return ValidationResult(
        status, ("go", "test"), 1.0, test_cases=cases, counted_test_ids=COUNTED
    )


def test_a_broken_build_ranks_below_any_candidate_that_compiles() -> None:
    # Published Agentless grades every regression test absent from the log as
    # failed, so a build failure scores as the worst possible regression.
    patch_a = build_unified_diff({"a.go": "x\n"}, {"a.go": "y\n"})
    patch_b = build_unified_diff({"a.go": "x\n"}, {"a.go": "z\n"})
    broken_build = _suite(build_failed=True)
    assert broken_build.failure_count() == 1731
    candidates = [
        _candidate("broken-build", patch_a, 0, broken_build),
        _candidate("breaks-one-test", patch_b, 1, _suite(("suite::test_7",))),
    ]
    selected = select_candidate(candidates)
    assert selected.candidate.candidate_id == "breaks-one-test"


def test_when_every_candidate_breaks_the_build_one_is_still_selected() -> None:
    # They all tie at the minimum, as upstream's min() does, and voting picks
    # among them; an emitted patch can still resolve the task, none cannot.
    patch_a = build_unified_diff({"a.go": "x\n"}, {"a.go": "y\n"})
    patch_b = build_unified_diff({"a.go": "x\n"}, {"a.go": "z\n"})
    candidates = [
        _candidate("first", patch_a, 0, _suite(build_failed=True)),
        _candidate("second", patch_b, 1, _suite(build_failed=True)),
        _candidate("third", patch_b, 2, _suite(build_failed=True)),
    ]
    selected = select_candidate(candidates)
    assert selected.candidate.candidate_id == "second"
    assert selected.reason == "best_regression_then_normalized_majority"


def test_final_prediction_uses_selected_candidate() -> None:
    patch = build_unified_diff({"a.py": "x=1\n"}, {"a.py": "x=2\n"})
    prediction = select_final_prediction(
        instance_id="task-1",
        model_name="provider/model",
        candidates=[_candidate("candidate-1", patch, 0)],
    )
    assert prediction.selected_candidate_id == "candidate-1"
    assert prediction.model_patch == patch
