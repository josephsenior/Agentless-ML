"""Run a DeepSWE task's tests against a candidate checkout, not the image's copy.

A DeepSWE image ships the task's repository already built at `/app`: Go module
cache warmed, `node_modules` installed, the Python package installed. The runner
does not test that copy. It streams the candidate checkout into `/tmp/work` and
runs there, because `/app` is on the container's read-only filesystem and,
more importantly, because a candidate patch only exists in the checkout.

That split is easy to get silently wrong. In the `cattrs` image the package is
installed in editable mode through a `.pth` file holding `/app/src`, so inside
the container `import cattrs` resolves to `/app/src/cattrs/__init__.py` even
with the candidate sitting in `/tmp/work`. Every candidate would then run the
image's unpatched code, pass identically, and validation would rank noise.
Each language below therefore says how the candidate becomes the code under
test, and `tests/test_deepswe_execution.py` pins that part of the command.

The test commands are ours, not the benchmark's: a task's own test invocation
lives in its held-out `tests/` directory, which this project never reads. They
are built from what the repository itself declares (a `go.mod`, a `package.json`
test script, a pytest layout), which is agent-visible material.
"""

from __future__ import annotations

from dataclasses import dataclass

from agentless_ml.validation.docker import PublicTestCommand
from agentless_ml.validation.reports import ReportFormat, TestReport

WORK = "/tmp/work"

# Paths a language's tooling writes to; on the read-only root filesystem they
# must land in the writable /tmp.
_GO_ENVIRONMENT = "GOCACHE=/tmp/go-build GOFLAGS=-mod=mod"

# src-layout first, then flat layout. A missing entry is ignored by Python, so
# one rule covers `src/cattrs/` and a top-level `fastapi/` package alike, and
# both come before the image's own installed copy.
_PYTHON_PATH = f"PYTHONPATH={WORK}/src:{WORK}"


@dataclass(frozen=True, slots=True)
class DeepSWETestCommand:
    """A shell script and the report it writes, for one language."""

    script: str
    report: TestReport

    def command(
        self, targets: tuple[str, ...] = (), *, timeout_seconds: float = 1800
    ) -> PublicTestCommand:
        return PublicTestCommand(
            ("sh", "-c", self.script, "deepswe-tests", *targets),
            timeout_seconds=timeout_seconds,
            report=self.report,
        )


# `go test` compiles the sources in the working directory, so moving to the
# candidate checkout is all that is needed. The reporter converts `go test
# -json` into CTRF, and its exit status is ignored: it exits 1 whenever a test
# failed, while still writing the complete report (and logging "build failed"),
# so treating that as a reporter failure would turn every real regression into
# a harness error. `go test`'s own status is the result; a report that was never
# written is caught by the runner, which refuses a missing or empty report.
GO = DeepSWETestCommand(
    script=(
        f'cd {WORK} && {_GO_ENVIRONMENT} go test -json -count=1 "$@" > /tmp/go-test.json; rc=$?; '
        "go-ctrf-json-reporter -output /tmp/ctrf.json < /tmp/go-test.json >/dev/null 2>&1; "
        "exit $rc"
    ),
    report=TestReport(ReportFormat.CTRF_JSON, "/tmp/ctrf.json"),
)

# pytest writes JUnit XML itself. `-p no:cacheprovider` keeps it from writing a
# cache directory into the checkout.
PYTHON = DeepSWETestCommand(
    script=(
        f"cd {WORK} && {_PYTHON_PATH} python -m pytest -p no:cacheprovider "
        '--junitxml=/tmp/report.xml "$@"'
    ),
    report=TestReport(ReportFormat.JUNIT_XML, "/tmp/report.xml"),
)

# mocha's built-in xunit reporter writes JUnit XML, so no reporter package has
# to be present in the image. The dependency symlink lets `require` find the
# image's installed modules while the code under test stays the checkout's.
JAVASCRIPT = DeepSWETestCommand(
    script=(
        f"cd {WORK} && ln -s /app/node_modules {WORK}/node_modules 2>/dev/null; "
        "NODE_PATH=/app/node_modules /app/node_modules/.bin/mocha "
        '--reporter xunit --reporter-option output=/tmp/report.xml "$@"'
    ),
    report=TestReport(ReportFormat.JUNIT_XML, "/tmp/report.xml"),
)

TEST_COMMANDS = {"go": GO, "python": PYTHON, "javascript": JAVASCRIPT}


def deepswe_test_command(
    language: str, targets: tuple[str, ...] = (), *, timeout_seconds: float = 1800
) -> PublicTestCommand:
    """The test command for ``language``, optionally narrowed to ``targets``.

    ``targets`` are paths or test selectors the language's runner understands:
    ``("./...",)`` for Go, ``("tests/test_any.py",)`` for pytest.
    """
    try:
        template = TEST_COMMANDS[language.casefold()]
    except KeyError:
        raise ValueError(
            f"no verified DeepSWE test command for {language!r}; "
            f"have {', '.join(sorted(TEST_COMMANDS))}"
        ) from None
    return template.command(targets, timeout_seconds=timeout_seconds)
