"""Canonical patch construction and candidate records."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from difflib import unified_diff

from agentless_ml.adapters.languages import get_language_adapter
from agentless_ml.schemas import PatchCandidate


def build_unified_diff(
    original_sources: Mapping[str, str],
    updated_sources: Mapping[str, str],
) -> str:
    """Build one deterministic Git-style patch for all changed visible files.

    A path present only in ``updated_sources`` is a new regular file (mode 100644).
    A path present only in ``original_sources`` would be a deletion, which is not
    supported.
    """
    if not set(original_sources) <= set(updated_sources):
        raise ValueError("file deletion is not supported at this boundary")
    chunks: list[str] = []
    for path in sorted(updated_sources):
        created = path not in original_sources
        old = "" if created else original_sources[path]
        new = updated_sources[path]
        if old == new and not created:
            continue
        body = list(
            unified_diff(
                old.splitlines(keepends=True),
                new.splitlines(keepends=True),
                fromfile="/dev/null" if created else f"a/{path}",
                tofile=f"b/{path}",
                lineterm="\n",
            )
        )
        rendered = "".join(
            line if line.endswith("\n") else line + "\n\\ No newline at end of file\n"
            for line in body
        )
        header = f"diff --git a/{path} b/{path}\n"
        if created:
            header += "new file mode 100644\n"
        chunks.append(header + rendered)
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


def comment_normalized_diff(
    original_sources: Mapping[str, str],
    updated_sources: Mapping[str, str],
    *,
    language: str,
) -> str | None:
    """A voting key with the language's own comments and docstrings removed first.

    This is on top of, not instead of, ``normalize_patch``: build a diff between
    comment-stripped versions of every changed file, then run the ordinary
    textual normalization over that diff, so Git framing is still removed the
    same way it always is.

    Returns ``None`` when there is nothing left to build a key from — every
    change between the two versions was itself inside a comment or a docstring.
    That candidate made no change this key can see; the caller falls back to
    ``normalize_patch`` on the real diff instead, which is still unique.
    """
    adapter = get_language_adapter(language)

    def stripped(path: str, source: str) -> str:
        # A created file may be in another format (a data file in a Go task);
        # only the task language's own files have comments this adapter knows.
        if not path.endswith(adapter.extensions):
            return source
        return adapter.strip_comments(source, path=path)

    stripped_originals = {
        path: stripped(path, source) for path, source in original_sources.items()
    }
    stripped_updated = {
        path: stripped(path, source) for path, source in updated_sources.items()
    }
    try:
        stripped_diff = build_unified_diff(stripped_originals, stripped_updated)
    except ValueError:
        return None
    return normalize_patch(stripped_diff)


def build_patch_candidate(
    *,
    candidate_id: str,
    raw_response: str,
    diff: str,
    localization_rank: int,
    sample_index: int,
    language: str = "python",
    original_sources: Mapping[str, str] | None = None,
    updated_sources: Mapping[str, str] | None = None,
) -> PatchCandidate:
    """Create a candidate whose digest and voting key are derived, not trusted.

    ``original_sources``/``updated_sources`` are the full pre- and post-repair
    file contents, when the caller has them (the fixed workflow always does).
    When both are supplied, the voting key is built from comment-and-docstring
    -stripped versions of the changed files, so two candidates that differ only
    in a comment vote together. Without them, voting falls back to the plain
    textual key, as it always did.
    """
    # Source CRLFs and trailing spaces are part of a patch's payload, not framing.
    canonical = diff if diff.endswith("\n") else diff + "\n"
    normalized = normalize_patch(canonical)
    if original_sources is not None and updated_sources is not None:
        semantic_key = comment_normalized_diff(
            original_sources, updated_sources, language=language
        )
        if semantic_key:
            normalized = semantic_key
    return PatchCandidate(
        candidate_id=candidate_id,
        diff=canonical,
        diff_sha256=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        localization_rank=localization_rank,
        sample_index=sample_index,
        raw_response=raw_response,
        normalized_diff=normalized,
    )
