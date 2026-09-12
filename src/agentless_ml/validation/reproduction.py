"""Recorded test source installed only for its trusted reproduction command."""

import re
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from agentless_ml.schemas import ValidationKind

from .docker import PublicTestCommand


def select_reproduction_source(verified: dict[int, str]) -> tuple[int, int]:
    """Exact-source votes among baseline-eligible samples; ties keep first input."""
    if not verified:
        raise ValueError("no reproduction sample failed on the original revision")
    votes = Counter(verified.values())
    selected = max(sorted(verified), key=lambda index: (votes[verified[index]], -index))
    return selected, votes[verified[selected]]


@dataclass(frozen=True, slots=True)
class ReproductionSpec:
    path: str
    command: PublicTestCommand

    def __post_init__(self):
        parts = self.path.split("/")
        if (
            not self.path
            or PurePosixPath(self.path).is_absolute()
            or any(
                part in {"", ".", ".."} or part.casefold() == ".git" for part in parts
            )
            or any(c in self.path for c in '\\:\0\r\n<>"|?*')
            or any(
                part.split(".")[0].upper()
                in {
                    "CON",
                    "PRN",
                    "AUX",
                    "NUL",
                    *(f"COM{i}" for i in range(1, 10)),
                    *(f"LPT{i}" for i in range(1, 10)),
                }
                for part in parts
            )
            or any(part.endswith((".", " ")) for part in parts)
        ):
            raise ValueError(
                "reproduction path must be a safe repository-relative file path"
            )
        if self.command.kind != ValidationKind.REPRODUCTION:
            raise ValueError("reproduction command must have reproduction kind")


def render_reproduction_prompt(
    problem: str, language: str, spec: ReproductionSpec
) -> str:
    return (
        f"### Issue ###\n{problem}\n\n"
        f"Write one complete {language} test source file for {spec.path}.\n"
        "It must fail an assertion when the described issue is present and pass when fixed.\n"
        "Do not hide import, build or setup failures as assertion failures.\n"
        "Use existing public repository interfaces; do not inspect repair patches or reference solutions.\n"
        f"The controller will run this fixed argument list: {spec.command.argv!r}\n"
        f"Return only the file contents in one ```{language} code block.\n"
    )


def parse_reproduction_source(response: str, language: str) -> str:
    match = re.fullmatch(
        r"\s*```" + re.escape(language) + r"\r?\n(.*?)\r?\n```\s*", response, re.DOTALL
    )
    if not match or not match[1].strip() or "```" in match[1] or "\0" in match[1]:
        raise ValueError("expected one nonempty reproduction source block")
    return match[1] + "\n"


@contextmanager
def reproduction_file(root: Path, spec: ReproductionSpec, source: str):
    """Never replace repository files, traverse symlinks or touch caller checkouts."""
    root = root.resolve()
    target = root.joinpath(*spec.path.split("/"))
    if not target.resolve().is_relative_to(root):
        raise ValueError("reproduction path escapes workspace")
    current = root
    for part in spec.path.split("/"):
        current = current / part
        if current.is_symlink():
            raise ValueError("reproduction path contains a symlink")
    if target.exists():
        raise ValueError("reproduction path already exists in repository")
    # Require an existing directory so installation never creates project structure.
    if not target.parent.is_dir():
        raise ValueError("reproduction parent directory must already exist")
    with target.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(source)
    try:
        yield
    finally:
        target.unlink()
