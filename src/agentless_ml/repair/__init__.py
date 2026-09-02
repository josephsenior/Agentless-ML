"""Deterministic repair post-processing and candidate selection."""

from agentless_ml.repair.edits import (
    AppliedRepair,
    EditApplicationError,
    EditParseError,
    SearchReplaceEdit,
    apply_search_replace_edits,
    parse_search_replace_edits,
)
from agentless_ml.repair.patches import (
    build_patch_candidate,
    build_unified_diff,
    normalize_patch,
)
from agentless_ml.repair.prompts import build_repair_prompt
from agentless_ml.repair.selection import (
    NoSelectableCandidate,
    SelectionResult,
    select_candidate,
    select_final_prediction,
)

__all__ = [
    "AppliedRepair",
    "EditApplicationError",
    "EditParseError",
    "NoSelectableCandidate",
    "SearchReplaceEdit",
    "SelectionResult",
    "apply_search_replace_edits",
    "build_patch_candidate",
    "build_repair_prompt",
    "build_unified_diff",
    "normalize_patch",
    "parse_search_replace_edits",
    "select_candidate",
    "select_final_prediction",
]
