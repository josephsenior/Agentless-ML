# DeepSWE baseline survey, 28 September 2026

Follow-up: the [4 October runner review](deepswe-runner-review-2026-10-04.md)
recovered four of the six missing-runner tasks and brought the latest readiness
count to 75. The counts below preserve this earlier snapshot.

This is a snapshot of the pinned 113-task corpus, before using a repair model.
"Ready" means that the unpatched candidate checkout ran in the task's pinned
image and produced at least one passing test with a usable report. It does not
mean the task was solved. Each task's latest result and message are in the local
`output/deepswe-survey/survey.jsonl` file beside the repository.

| Latest status | Tasks |
|---|---:|
| Ready | 71 |
| Repository contains symlinks or submodules unsupported by local-git-v1 | 22 |
| Test runner not yet supported or identifiable | 6 |
| Test command or report failed | 4 |
| No passing baseline tests | 4 |
| Repository preparation or seal failed | 3 |
| Pinned image absent | 1 |
| Survey failed before a test result | 1 |
| Full suite timed out | 1 |

The first sweep had 47 ready tasks. Rerunning results made stale by runner and
language fixes added six. The 14 tasks that had previously stopped at GitHub
DNS now all clone successfully: seven became ready, four reached the repository
support boundary, two reached test-harness problems, and one exposed a custom
runner. Narrow, documented Prometheus test plans added two more ready tasks. A
shared pnpm-workspace runner then brought all five Koota tasks to ready. Clearing
Returns's unsupported pytest plugin options added one more. That brings the
count to 68 without treating a failed build as a passing suite. A task-specific
Mocha JSON report path recovered CSS-tree: its pinned Mocha xUnit reporter wrote
an empty file despite the suite passing, while Mocha's built-in JSON reporter
recorded 16,715 passing tests and two pending tests. The snapshot now has 69
ready tasks. `true-myth-iterable-collection-combinators` also reached ready:
its Vitest typecheck writes into the installed Vitest package, so its runner
copies that small package into writable space while retaining its dependency
links. The unpatched suite then passed 561 tests; the snapshot now has 70 ready
tasks.

The Bandit task exposed a wrong assumption in our runner: Python did not mean
pytest. The published image lacks pytest, but its repository declares stestr
and the image installs it. Running `stestr run` in the image passed 273 tests.
The candidate checkout then passed the same 273 through stestr with a JUnit
report converted from its subunit output. The snapshot now has 71 ready tasks.

## What remains

The 22 `unsupported_repository` results are a deliberate limit, not flaky
tests. The local workspace provider currently refuses symlinks and submodules.
This group includes the original 18 tasks plus `tomlkit-toml-table-converters`,
`valibot-recursive-schema-composition`, `wasmi-trap-coredumps` and
`wazero-multi-module-snapshots`, which could only reach this check after their
repositories cloned. Do not drop the check merely to increase the ready count:
candidate workspaces must preserve those entries safely and still exclude
post-base history. The other 18 are `adaptix-name-mapping-aliases`,
`arktype-json-schema-refs-dependencies`, `clack-async-autocomplete-options`,
`effect-sse-httpapi-streaming`, `goreleaser-retry-publish-auditing`,
`helm-array-merge-strategies`, `helm-unified-manifest-stream`,
`kgateway-consistent-hash-policy`, `optique-conditional-option-dependencies`,
`participle-grammar-conflict-analysis`, `pebble-durability-wait-apis`,
`pest-character-class-coalescing`, `pwntools-tube-multiplexing`,
`python-statemachine-state-data-scoping`,
`query-persist-restored-query-state`, `scc-bounded-memory-spilling`,
`sqlfmt-create-table-ddl-formatting` and `task-task-graph-export`.

The five Koota tasks share a pnpm workspace. Their runner copies relative
dependency links into the candidate, so React's `@koota/core` resolves to the
candidate core package rather than `/app`. It runs both package suites and
merges their reports with distinct `core/` and `react/` test IDs. All five
baseline runs passed, with 160 to 172 tests each.

The six remaining `no_runner` tasks need a command that tests the candidate
checkout and writes a structured per-test report.
`claude-code-by-agents-recursive-delegation` and
`quill-shared-toolbar-focus` need package-level runner discovery.
`cliffy-config-file-parsing` uses Deno, `ink-grid-box-layout` uses AVA,
`kysely-window-grouping-helpers` invokes Mocha through a build-and-test script,
and `yjs-map-conflict-detection` has a custom Node test entry point. These are
not interchangeable with a guessed root-level Vitest command.

The four `harness_error` tasks reached a runner but did not produce a
trustworthy result. `kea-atomic-signal-selectors` failed during Jest setup;
`mnamer-daemon-watch-lifecycle` needs a version source without relying on a
candidate `.git` directory; and
`sql-formatter-bigquery-pipe-formatting` needs generated parser files before
its tests can run. `vitest-duration-sharding` tries to launch its own unbuilt
`dist/cli.js`.

Four tasks produced no passing baseline: `eicrud-keyset-pagination-cursor`
(suite setup timeouts), `igel-persist-feature-schema` (two failing tests and
missing generated fixture material), `numba-stencil-boundary-modes` (its native
extension is not built in the candidate), and `skrub-duration-encoding` (data
collection writes to `/root/skrub_data` on the read-only filesystem). Each
needs its own environment or build check; none should be marked ready by
ignoring the failures.

The remaining six are separate cases. `drizzle-orm-window-function-builders`,
`langchain-request-coalescing` and `meriyah-explicit-resource-declarations`
need repository-ref or seal repair. `mobly-grouped-test-barriers` still lacks
its pinned image. `boa-hierarchical-evaluation-cancellation` had a Windows
checkout-lock error and needs a rerun with the newer temporary-workspace path.
`testem-per-launcher-reports` passed 488 tests in an earlier run, but its latest
whole-suite survey timed out; the previous result is not a substitute for a
repeatable baseline.

## Next checks

The next shared runner work is the two other nested-package projects, then the
single-tool and custom runners. The four harness errors should be fixed
with small task-specific checks where the published image is incomplete; keep
the report/exit-code consistency check in place. Symlink and submodule support
is a separate workspace safety change and should stay excluded until tested.

The survey can be resumed or a task rerun with `tools/survey_deepswe.py`.
Its `--results` file is append-only: use the last record for each task ID, not
the first occurrence, when counting statuses.
