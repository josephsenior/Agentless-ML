# DeepSWE runner review, 4 October 2026

We revisited the six tasks marked `no_runner` in the
[28 September survey](deepswe-survey-2026-09-28.md). Each check used a fresh
checkout at the pinned base revision and the published image's pinned digest.
No repair model was involved. The benchmark's held-out tests and reference
solutions were not read to choose these commands.

| Task | Public regression schedule | Latest outcome |
|---|---|---|
| `claude-code-by-agents-recursive-delegation` | Backend and frontend Vitest suites | Ready: 52 passed, 27 failed, 79 reported |
| `quill-shared-toolbar-focus` | Quill browser unit and jsdom fuzz suites | Ready: 524 passed |
| `ink-grid-box-layout` | Build the candidate, run AVA, convert its TAP report using installed tap-junit | Ready: 930 passed, 2 failed, 932 reported |
| `kysely-window-grouping-helpers` | Build the candidate library and Node tests, then run SQLite and dialect-independent Mocha tests | Ready: 438 passed |
| `cliffy-config-file-parsing` | Deno's declared public suite with cached-only imports and its built-in JUnit reporter | Blocked: the pinned cache lacks `@std/io` metadata |
| `yjs-map-conflict-detection` | Custom Node entry point using `lib0/testing` | Still `no_runner`: a per-test report adapter is needed |

Ready means there is a usable inventory of passing public tests. Agentrooms
already has 27 failing tests on the base revision; those do not become regression
requirements. None of these runs measures whether a model can solve the task.

These four recoveries bring the latest survey to 75 ready tasks out of 113.
The other statuses are 22 unsupported repositories, five harness errors, four
baselines with no passing tests, three repository preparation failures, and one
each of no runner, missing image, survey error and timeout. Only these six tasks
were rerun; the other tasks retain their previous evidence.

## What changed

The runner overrides now take precedence over automatic discovery. Previously,
discovery failed on a missing root `package.json` or an unfamiliar root script
before a reviewed override could be applied. Cliffy and both nested-package
projects exposed that ordering error.

The nested Vitest plans keep each package's own configuration and installed
dependencies. Relative workspace links are copied into the candidate tree, and
report IDs are prefixed by package or suite so identically named tests remain
distinct. An isolated Agentrooms candidate with a new deliberately failing test
reported `backend/agentless-candidate-probe.test.ts::agentless candidate probe` as
failed. That checks that candidate files reach the runner.

The new schedules are defined in `deepswe_execution.py`; their task-specific
reasons are in `experiments/deepswe/test_overrides.json`. Kysely's public test
setup exposes a `DIALECTS` selector. Its full default suite waits for PostgreSQL,
MySQL and MSSQL services absent from this image, so this schedule selects SQLite.
Quill's separate Playwright end-to-end suite requires a web-server build and is
outside the unit/fuzz schedule. Both restrictions must remain part of the
experimental condition.

## Remaining blockers

Follow-up: the [Yjs reporting check](deepswe-yjs-reporting-2026-10-04.md)
subsequently recovered Yjs and raised readiness to 76/113. The outcomes below
describe the initial six-task review, before that follow-up.

Cliffy's Deno runner can use the installed tool and write JUnit, but the whole
public suite cannot load offline with the image's incomplete dependency cache.
The run stops before producing test results. Resolving that requires a separately
recorded environment change or a reviewed smaller suite whose dependencies are
already cached.

Yjs imports its public test modules into `lib0/testing.runTests`. That custom
runner has no installed JUnit or CTRF reporter. A reporter adapter must preserve
its filtering, repetitions and failure handling before this task can provide a
regression inventory. Its lack of a report remains explicit.

## Evidence

The existing append-only `output/deepswe-survey/survey.jsonl`, beside the
repository, holds the task outcomes, image IDs and artifact paths. Latest records
take precedence over earlier attempts. The candidate probe is under
`output/deepswe-survey/candidate-probes/`. Package checks passed with 536 tests
and 14 opt-in checks skipped; the runner tests cover override precedence and
package report IDs. The image checks above were run separately.
The [committed snapshot](../experiments/deepswe/runner_review_2026_10_04.json)
keeps the six outcomes and image pins available without the machine's output
directory.
