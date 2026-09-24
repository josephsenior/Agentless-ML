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
Each command below therefore says how the candidate becomes the code under
test, and `tests/test_deepswe_execution.py` pins that part of the command.

Commands are chosen per test runner, not per language: across the 40 DeepSWE
JavaScript and TypeScript tasks, 20 use vitest, 9 jest and 5 mocha. The runner
comes from what the repository itself declares, its `package.json` test script,
which is agent-visible; the task's own test invocation lives in its held-out
`tests/` directory, which this project never reads.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

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

# JavaScript and TypeScript runners find the image's installed dependencies
# through links, while every file under test stays the checkout's own. The
# directory itself is real and writable, with one link per installed package:
# vite writes a bundled copy of vitest.config.ts into node_modules/.vite-temp,
# and a single link to the read-only /app/node_modules made that mkdir fail
# before any test ran. The image's own tool caches are not linked, so a runner
# that writes one writes it here.
_NODE_MODULES = (
    f"mkdir -p {WORK}/node_modules && "
    "for entry in /app/node_modules/* /app/node_modules/.[!.]*; do "
    'case "${entry##*/}" in .vite|.vite-temp|.cache) ;; '
    f'*) [ -e "$entry" ] && ln -s "$entry" {WORK}/node_modules/ ;; esac; done; '
)


@dataclass(frozen=True, slots=True)
class DeepSWETestCommand:
    """A shell script, the report it writes, and the exits meaning "tests failed"."""

    script: str
    report: TestReport
    failure_exit_codes: tuple[int, ...] = (1,)

    def command(
        self, targets: tuple[str, ...] = (), *, timeout_seconds: float = 1800
    ) -> PublicTestCommand:
        return PublicTestCommand(
            ("sh", "-c", self.script, "deepswe-tests", *targets),
            timeout_seconds=timeout_seconds,
            failure_exit_codes=self.failure_exit_codes,
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
PYTEST = DeepSWETestCommand(
    script=(
        f"cd {WORK} && {_PYTHON_PATH} python -m pytest -p no:cacheprovider "
        '--junitxml=/tmp/report.xml "$@"'
    ),
    report=TestReport(ReportFormat.JUNIT_XML, "/tmp/report.xml"),
)

# mocha's built-in xunit reporter writes JUnit XML, so no reporter package has
# to be present in the image. mocha exits with the number of failed tests (3
# for three failures), not 1, so every exit a test failure can produce is
# declared; the report then has to show a failed test, or the runner does not
# trust the run. Exits of 125 and above stay undeclared because they also mean
# a signal or an unrunnable command (137 is an out-of-memory kill), so a run
# with 125 or more failing tests is not taken as ordinary test failures.
MOCHA = DeepSWETestCommand(
    script=(
        f"cd {WORK} && {_NODE_MODULES}"
        "NODE_PATH=/app/node_modules /app/node_modules/.bin/mocha "
        '--reporter xunit --reporter-option output=/tmp/report.xml "$@"'
    ),
    report=TestReport(ReportFormat.JUNIT_XML, "/tmp/report.xml"),
    failure_exit_codes=tuple(range(1, 125)),
)

# jest has no built-in structured report; the jest task images install
# jest-ctrf-json-reporter into /opt/jest-ctrf, outside /app. It takes no output
# option on the command line and writes ctrf/ctrf-report.json under the working
# directory, so any such file already in the checkout is removed first: a run
# that crashed before reporting must not be read as that stale file. `--ci`
# stops jest writing new snapshots into the checkout.
JEST = DeepSWETestCommand(
    script=(
        f"cd {WORK} && {_NODE_MODULES}rm -rf {WORK}/ctrf; "
        "/app/node_modules/.bin/jest --ci --reporters=default "
        "--reporters=/opt/jest-ctrf/node_modules/jest-ctrf-json-reporter/dist/index.js "
        '"$@"'
    ),
    report=TestReport(ReportFormat.CTRF_JSON, "ctrf/ctrf-report.json"),
)

# vitest's JUnit reporter is built in; it is also what the benchmark's own
# verifier reads, according to the vitest task Dockerfiles. `run` disables
# watch mode.
VITEST = DeepSWETestCommand(
    script=(
        f"cd {WORK} && {_NODE_MODULES}"
        "/app/node_modules/.bin/vitest run --reporter=default --reporter=junit "
        '--outputFile.junit=/tmp/report.xml "$@"'
    ),
    report=TestReport(ReportFormat.JUNIT_XML, "/tmp/report.xml"),
)

# cargo-nextest ships in the Rust images and writes JUnit XML from a profile;
# the profile lives in /tmp so a repository's own nextest config is not edited.
# Its store directory is set explicitly: by default nextest 0.9.97 writes under
# the workspace's own target/ and ignores CARGO_TARGET_DIR, which left the report
# somewhere other than where it was declared. The crates are already downloaded
# into the image's registry, but cargo takes a lock inside CARGO_HOME, which is
# on the read-only root, so CARGO_HOME is a writable directory that links back
# to that registry. nextest exits 100 when tests failed; 101 (build failed) is
# left undeclared, so a candidate that breaks the build is handled as one, and a
# baseline that does not build stops the run.
CARGO_NEXTEST = DeepSWETestCommand(
    script=(
        "mkdir -p /tmp/cargo-home && ln -sfn /root/.cargo/registry /tmp/cargo-home/registry && "
        "printf '[store]\\ndir = \"/tmp/nextest-store\"\\n"
        "[profile.default.junit]\\npath = \"junit.xml\"\\n' > /tmp/nextest.toml && "
        f"cd {WORK} && CARGO_HOME=/tmp/cargo-home CARGO_TARGET_DIR=/tmp/target "
        "CARGO_NET_OFFLINE=true cargo nextest run --config-file /tmp/nextest.toml "
        '--no-fail-fast "$@"'
    ),
    report=TestReport(ReportFormat.JUNIT_XML, "/tmp/nextest-store/default/junit.xml"),
    failure_exit_codes=(100,),
)

TEST_COMMANDS = {
    "go": GO,
    "pytest": PYTEST,
    "mocha": MOCHA,
    "jest": JEST,
    "vitest": VITEST,
    "cargo-nextest": CARGO_NEXTEST,
}

_RUNNER_BY_LANGUAGE = {"go": "go", "python": "pytest", "rust": "cargo-nextest"}
_NODE_RUNNERS = ("vitest", "jest", "mocha")


def deepswe_test_runner(language: str, checkout: Path) -> str:
    """The test runner a task's repository declares.

    Go, Python and Rust each have one. For JavaScript and TypeScript it is the
    runner the ``package.json`` test script invokes, e.g. ``jest`` in awilix's
    ``npm run check && jest``; failing that, the one runner among its
    dependencies. Anything else is refused rather than guessed.
    """
    language = language.casefold()
    if language in _RUNNER_BY_LANGUAGE:
        return _RUNNER_BY_LANGUAGE[language]
    if language not in ("javascript", "typescript"):
        raise ValueError(f"no DeepSWE test runner for language {language!r}")
    manifest = json.loads((Path(checkout) / "package.json").read_text(encoding="utf-8"))
    script = (manifest.get("scripts") or {}).get("test") or ""
    named = {
        runner
        for runner in _NODE_RUNNERS
        if re.search(rf"(?<![\w@/-]){runner}(?![\w-])", script)
    }
    if len(named) == 1:
        return named.pop()
    dependencies = {
        **(manifest.get("dependencies") or {}),
        **(manifest.get("devDependencies") or {}),
    }
    installed = [runner for runner in _NODE_RUNNERS if runner in dependencies]
    if len(installed) == 1:
        return installed[0]
    raise ValueError(
        f"cannot tell which test runner this repository uses: test script {script!r}, "
        f"runner dependencies {installed}"
    )


def deepswe_test_command(
    runner: str, targets: tuple[str, ...] = (), *, timeout_seconds: float = 1800
) -> PublicTestCommand:
    """The test command for ``runner``, optionally narrowed to ``targets``.

    ``targets`` are paths or test selectors the runner understands:
    ``("./...",)`` for Go, ``("tests/test_any.py",)`` for pytest.
    """
    try:
        template = TEST_COMMANDS[runner]
    except KeyError:
        raise ValueError(
            f"no verified DeepSWE test command for {runner!r}; "
            f"have {', '.join(sorted(TEST_COMMANDS))}"
        ) from None
    return template.command(targets, timeout_seconds=timeout_seconds)
