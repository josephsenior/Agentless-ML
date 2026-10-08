# Drizzle and LangChain repository retries — 8 October 2026

After parking Pwntools and recovering Meriyah, we revisited the two remaining
repository-preparation failures with the existing sealing code. Preparation
does not by itself make a task ready: a usable public baseline is still needed.

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
