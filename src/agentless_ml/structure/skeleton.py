"""Hide function bodies while keeping every declaration the model reads."""

from __future__ import annotations

from tree_sitter import Node


def hide_bodies(
    data: bytes,
    root: Node,
    elided_bodies: frozenset[str],
    block_bodies: frozenset[str],
) -> bytes:
    """Replace the body of each ``elided_bodies`` node, outermost first.

    Replacement works on syntax byte spans, so braces inside strings or comments
    cannot confuse it. Nested functions are hidden with their enclosing body.
    Brace-delimited ``block_bodies`` become ``{ ... }``; expression bodies, such as
    an arrow function's, become ``...``.
    """
    replacements = []
    stack = [root]
    while stack:  # Iterative pre-order: deep expression trees cannot hit the recursion limit.
        node = stack.pop()
        if node.type in elided_bodies:
            body = node.child_by_field_name("body")
            if body is not None:
                marker = b"{ ... }" if body.type in block_bodies else b"..."
                replacements.append((body.start_byte, body.end_byte, marker))
                continue
        stack.extend(reversed(node.named_children))
    for start, end, marker in reversed(replacements):
        data = data[:start] + marker + data[end:]
    return data


def strip_comments(data: bytes, root: Node, comment_node_types: frozenset[str]) -> bytes:
    """Remove every ``comment_node_types`` node, outermost first.

    Used only to build a voting key (``repair/patches.py``), never to render a
    prompt or a real patch: the result need not be syntactically valid, only
    deterministic. Comments never contain other comments, so recording one span
    and not descending into it is enough.

    A comment that is the only non-whitespace content on its line removes the
    whole line, including its newline — otherwise the comment would leave a
    blank line behind, and two files differing only by a whole-line comment
    would still normalize to different text. A trailing comment on a line that
    also has real code only loses the comment itself.
    """
    spans: list[tuple[int, int]] = []
    stack = [root]
    while stack:
        node = stack.pop()
        if node.type in comment_node_types:
            start, end = node.start_byte, node.end_byte
            line_start = data.rfind(b"\n", 0, start) + 1
            if data[line_start:start].strip(b" \t") == b"":
                line_end = data.find(b"\n", end)
                if line_end == -1:
                    end = len(data)
                elif data[end:line_end].strip(b" \t") == b"":
                    end = line_end + 1  # also remove the line's own newline
                start = line_start
            spans.append((start, end))
            continue
        stack.extend(reversed(node.named_children))
    for start, end in reversed(spans):
        data = data[:start] + data[end:]
    return data
