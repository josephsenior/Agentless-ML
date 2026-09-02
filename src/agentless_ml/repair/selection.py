"""Controller-owned, deterministic candidate reranking."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Sequence

from agentless_ml.schemas import (
    FinalPrediction,
    PatchCandidate,
    ValidationKind,
    ValidationStatus,
)


class NoSelectableCandidate(ValueError):
    """No candidate can be selected without treating an error as evidence."""


@dataclass(frozen=True, slots=True)
class SelectionResult:
    candidate: PatchCandidate
    reason: str
    vote_count: int
    considered_candidate_ids: tuple[str, ...]


_INFRASTRUCTURE = {
    ValidationStatus.TIMEOUT,
    ValidationStatus.OUT_OF_MEMORY,
    ValidationStatus.HARNESS_ERROR,
}


def _results(candidate: PatchCandidate, kind: ValidationKind):
    return tuple(result for result in candidate.validation if result.kind is kind)


def _has_infrastructure_error(candidate: PatchCandidate) -> bool:
    return any(result.status in _INFRASTRUCTURE for result in candidate.validation)


def select_candidate(candidates: Sequence[PatchCandidate]) -> SelectionResult:
    """Select by regression quality, reproduction success, then majority vote.

    This preserves v1.5.0's ordering and first-appearance tie-break while making
    infrastructure failures ineligible instead of counting them as test fails.
    """
    indexed = [
        candidate
        for candidate in candidates
        if candidate.diff.strip()
        and candidate.normalized_diff.strip()
        and not any(
            result.status is ValidationStatus.PATCH_ERROR
            for result in candidate.validation
        )
    ]
    if not indexed:
        raise NoSelectableCandidate("no non-empty, applicable candidate")
    indexed = [candidate for candidate in indexed if not _has_infrastructure_error(candidate)]
    if not indexed:
        raise NoSelectableCandidate("all candidates have infrastructure failures")

    considered = indexed
    reasons: list[str] = []
    if any(_results(candidate, ValidationKind.REGRESSION) for candidate in considered):
        with_regression = [
            candidate
            for candidate in considered
            if _results(candidate, ValidationKind.REGRESSION)
        ]
        if with_regression:
            failures = {
                candidate.candidate_id: sum(
                    result.status is not ValidationStatus.PASS
                    for result in _results(candidate, ValidationKind.REGRESSION)
                )
                for candidate in with_regression
            }
            best = min(failures.values())
            considered = [
                candidate
                for candidate in with_regression
                if failures[candidate.candidate_id] == best
            ]
            reasons.append("best_regression")

    if any(_results(candidate, ValidationKind.REPRODUCTION) for candidate in considered):
        reproduction_passed = [
            candidate
            for candidate in considered
            if _results(candidate, ValidationKind.REPRODUCTION)
            and all(
                result.status is ValidationStatus.PASS
                for result in _results(candidate, ValidationKind.REPRODUCTION)
            )
        ]
        if reproduction_passed:
            considered = reproduction_passed
            reasons.append("reproduction_passed")
        else:
            reasons.append("reproduction_fallback")

    votes = Counter(candidate.normalized_diff for candidate in considered)
    first_appearance: dict[str, int] = {}
    for index, candidate in enumerate(considered):
        first_appearance.setdefault(candidate.normalized_diff, index)
    selected = max(
        considered,
        key=lambda candidate: (
            votes[candidate.normalized_diff],
            -first_appearance[candidate.normalized_diff],
        ),
    )
    reasons.append("normalized_majority")
    return SelectionResult(
        candidate=selected,
        reason="_then_".join(reasons),
        vote_count=votes[selected.normalized_diff],
        considered_candidate_ids=tuple(
            candidate.candidate_id for candidate in considered
        ),
    )


def select_final_prediction(
    *,
    instance_id: str,
    model_name: str,
    candidates: Sequence[PatchCandidate],
) -> FinalPrediction:
    selected = select_candidate(candidates).candidate
    return FinalPrediction(
        instance_id=instance_id,
        model_patch=selected.diff,
        selected_candidate_id=selected.candidate_id,
        model_name=model_name,
    )
