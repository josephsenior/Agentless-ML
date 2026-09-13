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
