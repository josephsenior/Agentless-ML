"""Canonical patch construction and candidate records."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from difflib import unified_diff

from agentless_ml.schemas import PatchCandidate


def build_unified_diff(
    original_sources: Mapping[str, str],
    updated_sources: Mapping[str, str],
) -> str:
    """Build one deterministic Git-style patch for all changed visible files."""
    if set(original_sources) != set(updated_sources):
        raise ValueError(
            "file creation and deletion are not supported at this boundary"
        )
    chunks: list[str] = []
    for path in sorted(original_sources):
        old = original_sources[path]
        new = updated_sources[path]
        if old == new:
            continue
        body = list(
            unified_diff(
                old.splitlines(keepends=True),
                new.splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
                lineterm="\n",
            )
        )
        rendered = "".join(
            line if line.endswith("\n") else line + "\n\\ No newline at end of file\n"
            for line in body
        )
        chunks.append(f"diff --git a/{path} b/{path}\n" + rendered)
    if not chunks:
        raise ValueError("cannot build an empty patch")
    return "".join(chunks)


def normalize_patch(patch: str) -> str:
    """Return a stable voting key without non-semantic Git metadata."""
    if not patch.strip():
        return ""
    normalized: list[str] = []
    for raw_line in patch.replace("\r\n", "\n").replace("\r", "\n").splitlines():
        line = raw_line.rstrip()
        if line.startswith(("diff --git ", "index ")):
            continue
        if line.startswith("--- "):
            line = "--- " + line[4:].split("\t", 1)[0]
        elif line.startswith("+++ "):
            line = "+++ " + line[4:].split("\t", 1)[0]
        normalized.append(line)
    return "\n".join(normalized).strip()


def build_patch_candidate(
    *,
    candidate_id: str,
    raw_response: str,
    diff: str,
    localization_rank: int,
    sample_index: int,
) -> PatchCandidate:
    """Create a candidate whose digest and voting key are derived, not trusted."""
    # Source CRLFs and trailing spaces are part of a patch's payload, not framing.
    canonical = diff if diff.endswith("\n") else diff + "\n"
    return PatchCandidate(
        candidate_id=candidate_id,
        diff=canonical,
        diff_sha256=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        localization_rank=localization_rank,
        sample_index=sample_index,
        raw_response=raw_response,
        normalized_diff=normalize_patch(canonical),
    )
