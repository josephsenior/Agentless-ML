# Drizzle and LangChain repository retries — 8 October 2026

After parking Pwntools and recovering Meriyah, we revisited the two remaining
repository-preparation failures with the existing sealing code. Preparation
does not by itself make a task ready: a usable public baseline is still needed.
Both repository failures are cleared, but neither task has a usable baseline
yet. Readiness stays at **93/113**, with 20 tasks still needing attention and
no latest survey records remaining in `repository_failed`.

## Drizzle

Fresh preparation of `drizzle-orm-window-function-builders` succeeded at
`e8e6edfef5ca69c6188d320388ad440265911057`. The previous dangling
`refs/remotes/origin/HEAD` failure did not recur. The seal passed without
changing the verifier, and the pinned published image was pulled and verified.

The latest survey outcome is **`no_runner`**, not `ready`. The root package's
public test script is `turbo run test --color`; its dependencies do not declare
a root test runner. Turbo's `test` task also depends on `build` and `test:types`.
The package manifests delegate testing across the ORM, schema integrations,
seed, kit, ESLint plugin and integration-tests packages. Running one Vitest
suite directly would not reproduce that root schedule.

No public tests were run in this retry. The next Drizzle step is to implement
and verify the delegated public schedule, including its prerequisites and
per-package reports, before claiming a baseline. This retry took 284.9 seconds.

## LangChain

Fresh preparation of `langchain-request-coalescing` succeeded at
`7cef35bfdebd22148a4c62a10bf01f1fde36e722`. The previous existing-ref Git
transaction error did not recur in the external staged clone. References were
pruned and the complete seal verified without changing the verifier. The pinned
published image was pulled and verified as
`sha256:aa019f0c3c7e1677ea820785cc60d32294ca4a9531cfe64066b760672f9f109d`.

The baseline reached pytest but ended with **`harness_error`**, exit code 3,
and no accepted test report. The generic command collects from the repository
root. Public `libs/core/tests/unit_tests/conftest.py` defines `--only-extended`
and `--only-core`, but the root invocation reaches its collection hook without
those options registered. The immediate failure is
`ValueError: no option named 'only_extended'`; stdout also records 101 collection
errors. No passing regression inventory was established.

The public core Makefile invokes pytest from that package and defaults
`TEST_FILE` to its unit tests. The next runner review should start there, verify
that imports resolve to candidate code rather than the image's editable install,
and preserve the package configuration and socket restrictions. This setup
pass did not alter the runner, narrow the schedule, patch conftest or claim
that all collection errors are explained by the missing option.

Evidence is in
`../output/deepswe-survey/langchain-request-coalescing/logs/agentless-ml-888d42b3845847229d083a1abdaa9d23/`:
execution metadata, stdout and empty stderr. There is no report artifact.
The recorded 25,265.2-second retry includes a long execution interruption;
pytest's own summary says 3.90 seconds. The wall-clock duration is not a
benchmark performance measurement.

## Reproduce

```powershell
.\.venv\Scripts\python.exe tools/survey_deepswe.py `
  --tasks-root ../benchmarks/deepswe/corpus/tasks `
  --repositories ../benchmarks/deepswe/repos `
  --task-id drizzle-orm-window-function-builders `
  --rerun --pull `
  --results ../output/deepswe-survey/survey.jsonl `
  --artifacts ../output/deepswe-survey `
  --timeout-seconds 1800
```

Replace the task ID with `langchain-request-coalescing` for the second retry.
The append-only survey retains the old failures; the latest record for each
task is its current status. Public environment files and sealed repository
configuration were inspected, not the benchmark's held-out tests or solutions.
No model was called.
