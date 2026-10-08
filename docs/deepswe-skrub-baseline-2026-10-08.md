# Skrub public test setup — 8 October 2026

Skrub now has a usable public baseline: **2,859 passing report IDs**, four
failures and 357 skipped or expected-failure cases. The official survey records
`ready`, bringing overall readiness to **99/113**, with 14 tasks remaining.
This is a regression inventory, not an all-green suite or a solution attempt.

## Why the old baseline had no passing tests

Skrub creates its default data directory during import. The published image
runs as root, so that directory was `/root/skrub_data`. Our runner keeps the
image filesystem read-only, and the import failed while trying to create it.
The saved result contains 26 collection errors, not 26 executed test failures.

The root-level pytest command also collected documentation, examples and build
helpers because the repository enables `--doctest-modules`. Its one executed
test was a documentation helper with a stale Python source-line expectation.
Skrub's package tests never reached execution.

## The corrected invocation

The public `pyproject.toml` declares its Pixi test task as
`pytest -vsl --cov=skrub --cov-report=xml skrub`. User-guide doctests are a
separate task. The checked-in `skrub-pytest` override runs that complete package
schedule, including its configured doctests, rather than collecting unrelated
root-level examples and documentation helpers.

The command exports the supported `SKB_DATA_DIRECTORY=/tmp/skrub_data` before
import. Coverage data and XML also go under `/tmp`; this changes only artifact
locations. Candidate source stays first on `PYTHONPATH`, JUnit reporting is
retained, and narrowed targets are refused. No test expectations or application
code were changed, no individual tests were excluded, and no dependencies were
installed.

The sealed base is `24c4466fea94f551fb73d21eba54038dc5b346d3`, and the published
image remains
`sha256:53c898620ea0fb580b17c4552f57f2eddf11e4fac7ca90189b75695cee3064a5`.
The run retains offline networking, a read-only image filesystem, the normal
capability restrictions and existing limits: 8-GiB memory, two CPUs, 4-GiB
temporary storage, 2,048 PIDs and a 1,800-second timeout.

## Reproduce

The complete package schedule collected 3,220 items and completed with exit
code 1, the declared test-failure exit. Pytest reports 2,536 ordinary passes,
323 unexpected passes under non-strict expected-failure marks, 298 skips and
59 expected failures, plus four failures. JUnit records the 323 unexpected
passes as passes and the 59 expected failures as skipped: 2,859 passed,
357 skipped and four failed report IDs. No collection errors remain.

The survey took 1,078.4 seconds, including workspace cleanup. The JUnit report,
stdout, stderr and execution metadata are under
`../output/deepswe-survey/skrub-duration-encoding/logs/agentless-ml-283487bd27c74c5b96d3b3f44827e304/`.

The four remaining failures stay in the report and outside the passing inventory:

- `test_optuna_optimize_learner[False-None]`: the sampled optimum is
  `1.9558307887618431`, outside the test's `2.0 ± 0.01` assertion. This run
  establishes the observed numerical mismatch, not its underlying cause.
- `test_warning_redownload_checksum_has_changed`: the employee-salaries
  dataset cannot be downloaded under the unchanged offline network policy.
- `test_get_data_home_without_parameter`: the test changes the home directory
  but expects that to control the data path. Our explicitly requested
  `SKB_DATA_DIRECTORY` takes precedence, so this assertion fails. The test
  expectation was not patched or suppressed.
- `test_transform_deterministic`: the Midwest-survey dataset cannot be
  downloaded offline. Other download tests retain their upstream
  expected-failure handling; none was converted to a fake success.

```powershell
.\.venv\Scripts\python.exe tools/survey_deepswe.py `
  --tasks-root ../benchmarks/deepswe/corpus/tasks `
  --repositories ../benchmarks/deepswe/repos `
  --task-id skrub-duration-encoding --rerun `
  --results ../output/deepswe-survey/survey.jsonl `
  --artifacts ../output/deepswe-survey --timeout-seconds 1800
```

The focused execution, adapter and report checks passed: 136 passed, five
opt-in tests skipped. The full project suite passed: 668 passed, 31 skipped.
Held-out tests and solutions were not inspected, and no model was called.
