"""Observe Sphinx's real doctest groups without replacing their execution.

Pwntools supplies its own platform-aware builder. Hook the base methods it
delegates to, leaving setup, shared namespaces, flags and cleanup untouched.
A report case is a whole document/group, not an individual >>> example: a
single failure excludes that group from the passing regression inventory.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def run(report_path: Path = Path("/tmp/ctrf.json"), *, files: tuple[str, ...] = ()) -> int:
    from sphinx.cmd.build import build_main
    from sphinx.ext.doctest import DocTestBuilder

    cases: list[dict[str, object]] = []
    document = ""
    original_doc = DocTestBuilder.test_doc
    original_group = DocTestBuilder.test_group

    def test_doc(builder, docname, doctree):
        nonlocal document
        document = docname
        return original_doc(builder, docname, doctree)

    def test_group(builder, group):
        runners = (builder.test_runner, builder.setup_runner, builder.cleanup_runner)
        before = [(runner.tries, runner.failures) for runner in runners]
        result = original_group(builder, group)
        delta = [
            (runner.tries - tries, runner.failures - failures)
            for runner, (tries, failures) in zip(runners, before, strict=True)
        ]
        (tries, failures), (_, setup_failures), (_, cleanup_failures) = delta
        # Successful setup alone is not a passing test. A failed setup/cleanup
        # is an error even when some examples happened to pass beforehand.
        if tries or setup_failures or cleanup_failures:
            status = (
                "other" if setup_failures or cleanup_failures
                else "failed" if failures else "passed"
            )
            cases.append({
                "suite": document, "name": group.name, "status": status,
                "duration": 0, "examples": tries, "exampleFailures": failures,
                "setupFailures": setup_failures, "cleanupFailures": cleanup_failures,
            })
        return result

    DocTestBuilder.test_doc = test_doc
    DocTestBuilder.test_group = test_group
    arguments = ["-b", "doctest", "-d", "build/doctrees", "source", "build/doctest", *files]
    # conf.py explicitly checks argv for 'doctest' before registering its
    # PlatformDocTestBuilder. Retain the same arguments as make -C docs doctest.
    original_argv = sys.argv
    sys.argv = ["sphinx-build", *arguments]
    try:
        exit_code = build_main(arguments)
        report_path.write_text(json.dumps({
            "results": {"tool": {"name": "sphinx-doctest-groups"}, "tests": cases}
        }), encoding="utf-8")
        return exit_code
    finally:
        sys.argv = original_argv
        DocTestBuilder.test_doc = original_doc
        DocTestBuilder.test_group = original_group


if __name__ == "__main__":
    raise SystemExit(run(files=tuple(sys.argv[1:])))
