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
import shlex
from collections.abc import Mapping
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
# Since Go 1.24, `go test -json` also reports a package that fails to build as
# "build-output" and "build-fail" events, and go-ctrf-json-reporter v0.1.0
# writes a 0-byte report when it meets them. In abs, one package imports
# syscall/js, which only builds for WebAssembly, and that single package cost
# the whole suite's 170 test results. Those events are dropped before the
# reporter; the package itself is still reported as failed, without tests.
GO = DeepSWETestCommand(
    script=(
        f'cd {WORK} && {_GO_ENVIRONMENT} go test -json -count=1 "$@" > /tmp/go-test.json; rc=$?; '
        "grep -v '\"Action\":\"build-' /tmp/go-test.json "
        "| go-ctrf-json-reporter -output /tmp/ctrf.json >/dev/null 2>&1; "
        "exit $rc"
    ),
    report=TestReport(ReportFormat.CTRF_JSON, "/tmp/ctrf.json"),
)

# pytest writes JUnit XML itself. `-p no:cacheprovider` keeps it from writing a
# cache directory into the checkout. By default one test module that cannot be
# imported stops the whole session before any test runs: in the cattrs image six
# modules import packages the image does not install (bson, immutables, ...),
# and the entire suite yielded no tests. `--continue-on-collection-errors` runs
# every module that loads; the ones that do not are reported as errors, so they
# stay out of the inventory, and a candidate that breaks an import loses only
# that module's tests.
PYTEST = DeepSWETestCommand(
    script=(
        f"cd {WORK} && {_PYTHON_PATH} python -m pytest -p no:cacheprovider "
        '--continue-on-collection-errors --junitxml=/tmp/report.xml "$@"'
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
    script = _package_script(checkout)
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


def _package_script(checkout: Path) -> str:
    manifest = json.loads((Path(checkout) / "package.json").read_text(encoding="utf-8"))
    return (manifest.get("scripts") or {}).get("test") or ""


# Flags of the repository's own mocha invocation that would replace the report
# this command depends on, or keep mocha running instead of exiting.
_MOCHA_DROPPED = {"-R", "--reporter", "-O", "--reporter-option", "--reporter-options",
                  "-w", "--watch"}
_MOCHA_DROPPED_WITH_VALUE = {"-R", "--reporter", "-O", "--reporter-option",
                             "--reporter-options"}


def deepswe_test_targets(runner: str, checkout: Path) -> tuple[str, ...]:
    """What the whole suite is, as the repository declares it.

    Every runner but mocha finds its tests from the repository's own
    configuration (pytest's testpaths, jest's and vitest's config, Cargo's
    workspace), so it is given none; Go is given ``./...``, every package. mocha
    is given the arguments the ``package.json`` test script passes it — testem's
    ``mocha tests/*_tests.js tests/**/*_tests.js`` gives the two globs — minus
    reporter and watch flags, which would replace the report this command reads.
    """
    if runner == "go":
        return ("./...",)
    if runner != "mocha":
        return ()
    script = _package_script(checkout)
    for segment in re.split(r"&&|\|\||;", script):
        try:
            tokens = shlex.split(segment)
        except ValueError:
            continue
        starts = [i for i, token in enumerate(tokens) if Path(token).name in ("mocha", "_mocha")]
        if not starts:
            continue
        arguments, skip = [], False
        for token in tokens[starts[0] + 1:]:
            if skip:
                skip = False
                continue
            flag = token.split("=", 1)[0]
            if flag in _MOCHA_DROPPED:
                skip = flag == token and flag in _MOCHA_DROPPED_WITH_VALUE
                continue
            arguments.append(token)
        return tuple(arguments)
    raise ValueError(f"no mocha invocation in the test script {script!r}")


@dataclass(frozen=True, slots=True)
class DeepSWETestPlan:
    """Which runner, on which targets, a task's regression suite uses."""

    runner: str
    targets: tuple[str, ...]
    override_reason: str | None = None

    def command(self, *, timeout_seconds: float = 1800) -> PublicTestCommand:
        return deepswe_test_command(self.runner, self.targets, timeout_seconds=timeout_seconds)


def load_test_overrides(path: Path) -> dict[str, dict[str, object]]:
    """Per-task corrections that cannot be derived, each with its reason.

    Keys are task IDs; each entry has a nonempty ``reason`` and ``arguments``
    appended after the derived targets, or ``targets`` replacing them.
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    overrides: dict[str, dict[str, object]] = {}
    for task_id, entry in raw.items():
        if not isinstance(entry, dict) or set(entry) - {"reason", "arguments", "targets"}:
            raise ValueError(f"override for {task_id} has unknown keys")
        if not isinstance(entry.get("reason"), str) or not entry["reason"].strip():
            raise ValueError(f"override for {task_id} needs a reason")
        for key in ("arguments", "targets"):
            value = entry.get(key, [])
            if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
                raise ValueError(f"override for {task_id}: {key} must be a list of strings")
        if not entry.get("arguments") and "targets" not in entry:
            raise ValueError(f"override for {task_id} changes nothing")
        overrides[task_id] = entry
    return overrides


def deepswe_test_plan(
    language: str, checkout: Path, override: Mapping[str, object] | None = None
) -> DeepSWETestPlan:
    """The runner and targets for a task's whole suite, plus any override."""
    runner = deepswe_test_runner(language, checkout)
    targets = deepswe_test_targets(runner, checkout)
    if override is None:
        return DeepSWETestPlan(runner, targets)
    if "targets" in override:
        targets = tuple(override["targets"])  # type: ignore[arg-type]
    targets += tuple(override.get("arguments", ()))  # type: ignore[arg-type]
    return DeepSWETestPlan(runner, targets, str(override["reason"]))


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
