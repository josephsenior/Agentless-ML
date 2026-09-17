"""The source operations required by the fixed workflow."""

from collections.abc import Sequence
from typing import Protocol

from agentless_ml.schemas import FileNode
from agentless_ml.schemas.prompts import LanguagePrompts
from agentless_ml.structure.resolution import ResolvedLocations


class LanguageAdapter(Protocol):
    language: str
    extension: str
    extensions: tuple[str, ...]
    prompts: LanguagePrompts

    def is_source_path(self, path: str) -> bool: ...

    def is_test_path(self, path: str) -> bool: ...

    def parse_file(self, path: str, source: str) -> FileNode: ...

    def render_skeleton(
        self,
        source: str,
        *,
        path: str | None = None,
        compress_assign: bool = False,
        total_lines: int = 30,
        prefix_lines: int = 10,
        suffix_lines: int = 10,
    ) -> str: ...

    def resolve_locations(
        self,
        locations: str | Sequence[str],
        file_node: FileNode,
        source: str,
        *,
        context_window: int,
        separate_intervals: bool,
        fine_grained_only: bool,
        remove_line_locations: bool,
    ) -> ResolvedLocations: ...

    def strip_comments(self, source: str, *, path: str | None = None) -> str:
        """Remove this language's comments, for the repair voting key only.

        The result need not be valid source; it is never applied as a patch or
        shown in a prompt. Two sources differing only in comments must strip to
        the same text.
        """
        ...
