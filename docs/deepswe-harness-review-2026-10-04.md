# Reviewing the five DeepSWE harness errors — 4 October 2026

This follows the [Yjs reporting check](deepswe-yjs-reporting-2026-10-04.md).
The five remaining harness errors had different causes. We reviewed their
recorded logs, public repository configurations and installed dependencies in
the pinned images. No held-out tests or reference solutions were read, and no
model was called.

Four tasks are recovered, bringing the latest survey to **80 ready tasks out
of 113**. Cliffy remains blocked by its published dependency cache.

| Task | Passed | Failed/error | Skipped | Latest status |
|---|---:|---:|---:|---|
| Kea | 153 | 0 | 0 | Ready |
| SQL Formatter | 5,709 | 0 | 2 | Ready |
| mnamer | 310 | 204 | 8 | Ready |
| Vitest | 2,123 | 4 | 93 | Ready |
| Cliffy | 0 | 0 | 0 | Harness error, no report |

Ready means a usable inventory of passing public baseline tests, not an
all-green suite. Existing failures and errors are retained as evidence but
do not become regression requirements. These runs do not score task solutions.

## Kea: missing Babel environment

The public `test:jest` script sets `BABEL_ENV=test`. Our direct Jest invocation
did not. Without that setting, Babel left import statements unchanged, so all
33 suites failed to load the setup file before any test ran.

Setting Babel's environment alone produced 108 passing tests and 45 failures.
The failures exposed a second setup issue: the image sets `NODE_ENV=production`,
so React's `act` test helper refuses to run. The reviewed command sets both
`BABEL_ENV=test` and `NODE_ENV=test`, restoring Jest's normal test environment.
It uses the existing reporter and runs the whole configured Jest suite, without
excluding failing tests. The separate `test:tsd` and `test:types` commands are
not part of this Jest schedule. Earlier attempts remain in the append-only
survey rather than being erased.

With both environment settings, all 153 distinct reported tests pass.

## SQL Formatter: missing generated grammar

Its public test script runs the grammar generator before Jest. The generated
`src/parser/grammar.ts` is not tracked, so a clean candidate lacked it. Five
suites could run, but 22 others failed TypeScript compilation. The process
failed while its report showed only passing tests; rejecting that inconsistent
result was correct.

The runner now invokes the installed `nearleyc` on the candidate's own
`src/parser/grammar.ne` before Jest. It does not copy the image's generated
parser, suppress TypeScript diagnostics or remove suites. The completed
baseline reports 5,709 passing tests and two skips.

## mnamer: version metadata, then slow offline retries

The candidate snapshot intentionally has no Git history. It also lacks the
untracked `mnamer/__version__.py` file, causing the package to fall back to
setuptools-scm and fail during conftest imports.

The published image supplies a small version stub containing `0.0.0`. The
reviewed runner copies only that file when it is absent, matching the existing
image environment. It keeps any candidate-provided version file and continues
to import candidate package source first. Copying the whole installed package
would have tested the wrong source; inventing a release version would have
changed the environment unnecessarily.

With imports fixed, the full suite reached its network tests. Those tests call
external services and declare retries; the TVDB provider tests request five
reruns with two-second delays. A 300-second smoke check timed out at that stage.
The follow-up allows 900 seconds, without excluding network tests, disabling
retries or enabling networking. That follow-up completed, yielding 310 passing
tests, 204 failed/error outcomes and eight skips. The survey records 446.8
seconds; pytest's own summary reports 471.12 seconds. The
earlier timeout remains recorded; it was not used as an inventory.

## Vitest: installed dependencies, but no built runner

The image has workspace dependencies, but no `packages/vitest/dist/cli.js`.
The generic runner therefore failed before test discovery. This is the Vitest
repository itself, not a project using an already-built published Vitest.

A disposable offline probe successfully ran the public root build in 117.2
seconds. The reviewed command copies installed root and package dependency
links into the candidate tree and builds candidate packages. It checks that
the root Vitest dependency resolves to the candidate package and launches the
candidate-built CLI, never `/app`'s old source.

The selected schedule is the core/thread suite from the public root `test`
script. It is not the broader `test:ci` schedule, other worker-pool variants or
the browser suite. The temporary filesystem is 8 GB, as verified in the build
probe; the image and network policy remain unchanged.

The completed core/thread baseline reports 2,123 passes, four failures and 93
skips, or 2,220 tests in total, in 160.2 seconds including setup and build.

## Cliffy: incomplete published cache

The rerun again failed before test discovery: the installed Deno cache lacks
`https://jsr.io/@std/io/meta.json`, required by the public prompt code. The
installed runner is Deno 2.0.0, and its 21 MB cache cannot satisfy this checkout's
imports offline.

We did not fetch dependencies, substitute registry packages, change the image
or quietly select a smaller suite. Cliffy remains an explicit environment
blocker. Repairing it would require a separately recorded dependency-cache
change, with versions and provenance reviewed before calling it ready.

## Where the decisions live

The commands are in
[deepswe_execution.py](../src/agentless_ml/adapters/benchmarks/deepswe_execution.py).
Each task's reason and resource exception is in
[test_overrides.json](../experiments/deepswe/test_overrides.json).
[Runner tests](../tests/test_deepswe_execution.py) check setup order, candidate
paths, preserved selectors and report formats. Real runs use the pinned images
with networking disabled. The survey remains append-only, keeping failed
attempts as well as the latest outcomes under `output/deepswe-survey/` beside
this repository.

The [committed snapshot](../experiments/deepswe/harness_review_2026_10_04.json)
records the five outcomes, base revisions, image digests and setup conditions.

The full package regression suite passed with 546 tests and 15 opt-in checks
skipped. All 67 runner contract checks passed separately.

## Next boundary

The remaining 33 tasks comprise 22 unsupported repositories, four baselines
without passing tests, three repository preparation failures, and one each of
harness error, missing image, survey error and timeout.

Next, review the 22 unsupported repositories and three preparation failures.
Classify their exact snapshot or checkout restrictions before extending the
workspace code. Cliffy needs a separately documented environment decision,
not another parser or reporter workaround.
