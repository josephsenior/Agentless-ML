# Public tests in Docker

The controller can apply a prepared patch, run a fixed schedule of public test
commands in Docker, and pass results to deterministic selection. No model API
is called. A running Linux Docker engine is required only for live execution.

Published Agentless already executes regression and reproduction tests through
Docker/SWE-bench infrastructure. This runner implements that execution role for
development; it adds no new algorithmic stage. Test schedules are supplied by the
caller, so this module does not implement Agentless's automated regression-test
selection or reproduction-test generation. See the
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
`touch`, `sleep`, and test dependencies. Image contents and baked-in environment
variables are visible to tests, so images must contain only trusted public material.

Each `PublicTestCommand` gets a new container. The runner archives regular source
files, excludes `.git`, rejects symlinks and special files, and streams source into
`/tmp/work`. There are no host-directory or Docker-socket mounts. Tests run as
UID/GID 65534, with networking disabled, capabilities dropped, no privilege
escalation, and a read-only root filesystem. `/tmp` is a size-limited writable
memory filesystem. Defaults are 512 MB RAM, no additional swap, one CPU, 128
processes, 256 MB temporary storage, and 60 seconds per command. Docker management
operations have separate 30-second timeouts.

Commands are argument lists passed to a fixed bootstrap script without shell
interpolation. Use the same frozen schedule for every candidate. Commands cannot
share generated files because containers are fresh; dependent build/test steps
can be combined in a trusted controller script.

Exit 0 passes; by default exit 1 is a test failure and other exits are harness
errors. The caller must declare failure codes appropriate to its test runner.
For pytest, collection, usage, internal-error, and no-tests exits must not become
ordinary test failures. This backend does not parse framework reports: one command
contributes one validation result. Use one fixed command per test, or a future
framework adapter, before claiming individual failed-test counts. Some runners
use the same exit code for import errors and assertion failures.

Timeouts, Docker-reported OOM kills, patch rejection, and infrastructure errors
remain distinct. Cleanup failures make results ineligible and record the container
name. Saved logs contain the last 1,000 lines within Docker's rotating 1 MB log;
hashes describe these saved excerpts, not necessarily complete output.

`validate_candidate` replaces earlier evidence, applies the patch in an independent
workspace, and runs the schedule. Its return value feeds directly into
`select_candidate`. Results never initiate model calls. Hidden verifier tests and
reference solutions must be absent from source, commands, and images.

This is an initial local execution backend, not a complete benchmark harness or
a guarantee against container escape. Dataset preparation, sealed verification,
framework-specific reports, and model sampling remain separate work.

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
