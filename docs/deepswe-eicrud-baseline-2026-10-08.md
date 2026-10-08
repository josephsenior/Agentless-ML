# Eicrud offline MongoDB baseline — 8 October 2026

Eicrud now has a usable public baseline: **147 passed, 69 failed, none skipped**.
All 24 public MongoDB suites ran, with 17 passing and seven failing. The official
survey records `ready`, bringing overall readiness to **100/113**, with 13
tasks remaining. Readiness means a passing regression inventory, not an
all-green suite.

## What was missing

The original generic Jest invocation had no running database. The public test
application defaults to MongoDB, so its shared setup timed out before tests
could exercise application behavior. The candidate checkout also lacked the
untracked generated clients required by two suites. The image had generated
them during its build, but using those outputs would bypass candidate changes.

The public CI provides database services, runs `setup:tests`, builds, then
invokes `test:mongo`. The reviewed override reproduces the offline preparation
and MongoDB schedule rather than repeating package installation or modifying
tests. PostgreSQL and the separate microservice schedules are not included.

## Candidate preparation and database

Third-party dependencies remain the image's installed packages. Every local
`@eicrud/*` package link instead resolves to the candidate checkout, with an
explicit path check. The shared library and CLI are compiled there, then the
candidate CLI exports DTOs, superclient and OpenAPI schemas. The installed
OpenAPI generator consumes that new schema to generate the test client. The
public root build runs afterward. A failed prerequisite exits as a setup
failure; it cannot become a partial passing baseline.

The image's existing `mongod` runs inside the same isolated container, bound to
`127.0.0.1:27017`, with database files, log and PID file under `/tmp/eicrud-mongo`.
The installed Node MongoDB client verifies a real local database ping before
Jest starts. The process is stopped at command exit; the normal runner then
removes the container and candidate workspace. No host database or exposed
host port is needed.

The test invocation preserves `test:mongo`'s `TEST_CRUD_DB=mongo` and
`--forceExit`, runs all configured suites and retains CTRF reporting. Its worker
count is explicitly two, matching the existing two-CPU budget. No tests,
assertions, hook timeouts, dependencies or image contents were changed. Docker
still runs offline with a read-only root filesystem and its normal capability,
memory, PID and temporary-storage restrictions.

An initial attempt appended `--maxWorkers=2` to the public script's existing
`--maxWorkers=50%`. Jest 30 interpreted the duplicate flags as 50 workers. That
owned diagnostic container was stopped before an OOM; its observed cgroup OOM
counters were zero. The incomplete attempt remains recorded as `harness_error`,
not a passing result. The corrected equivalent invocation specifies the worker
count only once. Two workers were verified during the completed run.

## Completed result and remaining failures

The sealed base is `68dafce500a85227b996d8fcab466d7a0c88809e`. The verified
published image remains
`sha256:e4256a45acc84af565c5981b94ec1375870d87b65370c000216c7653291ea6bd`.
The final survey took 156.4 seconds; Jest reports 134.35 seconds. Exit code 1
is the declared test-failure exit, with a complete 216-ID report.

The generated OpenAPI and superclient suites now run without missing-module
errors. Most remaining failures are shared setup timeouts at the tests' existing
8- or 16-second limits. A command rate-limit test also expects HTTP 201 but
receives 429. This run records those outcomes; it does not establish every
remaining failure's cause. None was suppressed or included in the passing
inventory.

The report, stdout, stderr and execution metadata are under
`../output/deepswe-survey/eicrud-keyset-pagination-cursor/logs/agentless-ml-a9c5258c87f44e89a1527fcd18cfc527/`.

```powershell
.\.venv\Scripts\python.exe tools/survey_deepswe.py `
  --tasks-root ../benchmarks/deepswe/corpus/tasks `
  --repositories ../benchmarks/deepswe/repos `
  --task-id eicrud-keyset-pagination-cursor --rerun `
  --results ../output/deepswe-survey/survey.jsonl `
  --artifacts ../output/deepswe-survey --timeout-seconds 1800
```

Focused execution, adapter and report checks: 137 passed, five skipped.
Full project suite: 669 passed, 31 skipped. Held-out tests and solutions were
not inspected, and no model was called. Numba is now the only task still recorded
with no passing public tests and is the next setup review.
