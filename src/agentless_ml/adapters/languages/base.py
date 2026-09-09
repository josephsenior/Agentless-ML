"""The source operations required by the fixed workflow."""

from typing import Protocol

from agentless_ml.schemas import FileNode


class LanguageAdapter(Protocol):
    language: str
    extension: str
    extensions: tuple[str, ...]

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
