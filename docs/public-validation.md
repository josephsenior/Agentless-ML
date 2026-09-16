# Public tests in Docker

The controller can apply a prepared patch, run a fixed schedule of public test
commands in Docker, and pass results to deterministic selection. No model API
is called. A running Linux Docker engine is required only for live execution.

Published Agentless already executes regression and reproduction tests through
Docker/SWE-bench infrastructure. This runner implements that execution role for
development; it adds no new algorithmic stage. Test schedules are supplied by the
caller. The controller can now derive regression schedules from a trusted inventory
and [recorded exclusions](regression-selection.md), and can use one
[recorded generated reproduction test](reproduction-tests.md). Automatic discovery
and live generation remain unfinished. See the
[replication map](replication-map.md) for the reuse trade-off and remaining gaps.

## Try the demonstration

From the repository root in PowerShell:

```powershell
docker pull python:3.11-slim
$env:PYTHONPATH = 'src'
python tools/demo_public_validation.py
```

On Linux, use `PYTHONPATH=src python tools/demo_public_validation.py` after
pulling the image. The demo uses Python's standard library. For other repositories,
prepare a trusted image with their dependencies first and pass `--image`.
The runner never pulls images or installs packages itself.

The demo creates a faulty addition function. Two prepared patches change
subtraction to multiplication and addition. Multiplication fails the public test;
addition passes and is selected. Each invocation keeps a unique evidence directory
under `artifacts/public-validation`, including the fixture repository, summary,
logs, image ID, limits, and candidate/workspace provenance. Containers and candidate
checkouts are removed after use.

## Execution contract

`DockerTestRunner` resolves the local image to an immutable ID once. Images must
be Linux images without declared volumes, and include `/bin/sh`, `tar`, `mkdir`,
`sleep`, `test`, `head`, `tail`, and test dependencies. Image contents and baked-in environment
variables are visible to tests, so images must contain only trusted public material.

Each `PublicTestCommand` gets a new container. The runner archives regular source
files, excludes `.git`, rejects symlinks and special files, and streams source into
`/tmp/work`. There are no host-directory or Docker-socket mounts. Tests run as
UID/GID 65534, with networking disabled, capabilities dropped, no privilege
escalation, and a read-only root filesystem. `/tmp` is a size-limited writable
memory filesystem. Defaults are 512 MB RAM, no additional swap, one CPU, 128
processes, 256 MB temporary storage, and 60 seconds per command. Docker management
operations have separate 30-second timeouts.

The container's own process only waits. After the source is in place, the runner
starts the command with `docker exec`, passing its arguments to a fixed script as
positional parameters, never as shell text. The command's output goes to files in
`/tmp`, and the command's exit code is the result of that `exec`. While the
container is still running, the runner reads the output files and any declared
report, then removes the container. It works this way because `/tmp` is a
memory filesystem that disappears when the container stops, and the read-only
root filesystem and absence of mounts leave nowhere else a report could be
written and read back. Use the same frozen schedule for every candidate. Commands cannot
share generated files because containers are fresh; dependent build/test steps
can be combined in a trusted controller script.

Exit 0 passes; by default exit 1 is a test failure and other exits are harness
errors. The caller must declare failure codes appropriate to its test runner.
For pytest, collection, usage, internal-error, and no-tests exits must not become
ordinary test failures. Some runners use the same exit code for import errors and
assertion failures.

## Per-test results from reports

A command without a report is one selection unit: it passes or fails as a whole.
A command can instead declare a `TestReport`: a format and the path its test
runner writes. The runner then reads the individual test outcomes into
`ValidationResult.test_cases`, and selection counts failing tests instead of
failing commands.

Two formats are supported, because every language in the target benchmarks
already has a reporter for one of them installed in its images:

| Format | Written by (examples found in benchmark images) |
|---|---|
| `junit-xml` | `pytest --junitxml` (built into pytest), cargo-nextest, vitest |
| `ctrf-json` | `go-ctrf-json-reporter`, `jest-ctrf-json-reporter`, `mocha-ctrf-json-reporter` |

The parser reads the format, not the framework, so the knowledge of which tool
writes what stays in the command declaration. Test IDs are `classname::name`
(JUnit) or `suite::name` (CTRF). A test listed twice keeps its worst outcome.

Checked against real reporters inside images built from DeepSWE tasks, running as
the unprivileged container user:

```text
pytest --junitxml (Python image)
  test_calc::test_add passed | test_calc::test_sub failed | test_calc::test_param[1] passed
  test_calc::test_param[2] passed | test_calc::test_skipped skipped      -> fail, 1 failing test
mocha + mocha-ctrf-json-reporter (JavaScript image; command sets NODE_PATH=/app/node_modules)
  calc adds passed | calc subtracts failed | calc pending one skipped      -> fail, 1 failing test
```

A report path is either relative (inside `/tmp/work`) or an absolute path under
`/tmp`. Reports come from code under test, so they are untrusted: reading stops at
32 MB, JUnit files declaring a `DOCTYPE` or entities are refused, and anything
malformed, empty or missing makes the result a harness error.

The exit code and the report must agree, or neither is trusted:

```text
exit 0, report has a failed or errored test          -> harness error
declared failure exit code, report has no failed test -> harness error
(for example a collection or build error that wrote an empty-looking report)
```

When the command did not finish normally (timeout, out of memory, harness error),
the report is not read at all.

How failures are counted (`ValidationResult.failure_count`):

```text
no report                        -> 1 if the command did not pass, else 0
report                           -> every failed or errored test; skipped is not a failure
report + counted_test_ids        -> each counted test that did not pass;
                                    skipped or missing from the report counts as failed
```

`counted_test_ids` is meant for tests that passed on the unpatched code: if one of
them is skipped or disappears after a patch, that is not evidence it still works.
Nothing sets `counted_test_ids` yet; test-level regression selection is not
implemented.

Timeouts, Docker-reported OOM kills, patch rejection, and infrastructure errors
remain distinct. Cleanup failures make results ineligible and record the container
name. Saved logs contain the last 1 MB of the command's stdout and stderr; hashes
describe these saved excerpts, not necessarily complete output. A declared report
is saved beside them as `report.xml` or `report.json`.

`validate_candidate` replaces earlier evidence, applies the patch in an independent
workspace, and runs the schedule. Its return value feeds directly into
`select_candidate`. Results never initiate model calls. Hidden verifier tests and
reference solutions must be absent from source, commands, and images.

This is an initial local execution backend, not a complete benchmark harness or
a guarantee against container escape. Dataset preparation, sealed verification,
test-level regression selection, and model sampling remain separate work.

## Known limit: images built to run as root

Commands always run as UID/GID 65534. Benchmark images are built as root, and some
toolchains keep what they need in `/root`, which only root can read. In a Go image
built from a DeepSWE task, `go vet ./...` succeeds as root (dependencies are
pre-downloaded in `/root/go/pkg/mod`). As 65534 the module cache moves to an empty
`/tmp/go`, Go tries to download dependencies, and the build fails because the
container has no network; `/root/go/bin/go-ctrf-json-reporter` is also permission
denied. Rust images keep their toolchain under `/root/.cargo` as well. Python and
JavaScript images work as 65534. Running such tasks requires deciding whether
commands may run as the image's own user.

## Tests

Ordinary `python -m pytest` runs mocked lifecycle and failure-handling checks.
After the image is available, opt in to live checks:

```powershell
$env:PYTHONPATH = 'src'
$env:AGENTLESS_DOCKER_TESTS = '1'
python -m pytest tests/test_docker_validation.py -q
```

Set `AGENTLESS_TEST_IMAGE` for another prepared image. Live checks cover two-patch
selection, timeout cleanup, missing executables, non-root execution, history
exclusion, and writes that stay inside the container.
