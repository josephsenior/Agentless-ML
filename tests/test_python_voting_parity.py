"""Voting-key comparisons captured from the pinned Agentless normalizer."""

import json
from pathlib import Path

from agentless_ml.repair import build_patch_candidate, build_unified_diff


FIXTURE = Path(__file__).parent / "fixtures" / "python" / "voting.agentless-v1.5.0.json"
PINNED_REVISION = "b150f28465a77a81a7f4776384957a4271f5bd69"
REFERENCE_SOURCE_SHA256 = "dc3d237d6760af223a9a0e4a3ad70bd5f255a19ba0c77315ed9645dcc76cb683"


def _cases() -> list[dict[str, str]]:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert fixture["upstream_revision"] == PINNED_REVISION
    assert fixture["upstream_source_sha256"] == REFERENCE_SOURCE_SHA256
    return fixture["cases"]


def _local_key(case: dict[str, str]) -> str:
    old = {"example.py": case["original"]}
    new = {"example.py": case["updated"]}
    return build_patch_candidate(
        candidate_id=case["id"],
        raw_response=case["id"],
        diff=build_unified_diff(old, new),
        localization_rank=0,
        sample_index=0,
        language="python",
        original_sources=old,
        updated_sources=new,
    ).normalized_diff


def test_python_vote_keys_against_pinned_agentless() -> None:
    cases = {case["id"]: case for case in _cases()}
    for case_id in (
        "simple_fix",
        "spacing_variant",
        "inline_comment",
        "same_fix_no_comment",
        "docstring_change",
        "new_function",
        "new_function_before",
        "new_function_between",
    ):
        case = cases[case_id]
        assert _local_key(case) == case["upstream_key"], case_id


def test_known_python_voting_differences_are_explicit() -> None:
    cases = {case["id"]: case for case in _cases()}
    # It can emit an empty key for comment-only changes; ours keeps the patch
    # selectable by falling back to its textual diff.
    assert cases["comment_only"]["upstream_key"] == ""
    assert _local_key(cases["comment_only"]) != ""


def test_python_voting_groups_match_pinned_cases() -> None:
    cases = _cases()
    for left in cases:
        for right in cases:
            reference_same = left["upstream_key"] == right["upstream_key"]
            local_same = _local_key(left) == _local_key(right)
            assert local_same == reference_same, (left["id"], right["id"])
