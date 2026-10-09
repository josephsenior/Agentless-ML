# DeepSWE integration

DeepSWE provides 113 tasks across Go (35), Python (34), TypeScript (34),
JavaScript (5) and Rust (5), pinned at `datacurve-ai/deep-swe`
`0b9fabbb63b9104d678fe965e1632f2dd9eaa2ea`. These counts use the three
[corrected language labels](#language-corrections); the corpus's own labels give
34, 34 and 35. It is the only target benchmark that covers all five workflow
languages; SWE-bench Pro has no Rust tasks.

The adapter turns a task directory into a `TaskSpec`. It does not run tasks, pull
images, or score results.

## Trust boundary

A DeepSWE task directory uses the Harbor format and mixes agent inputs with
held-out answers:

```text
task.toml          agent-visible metadata (plus a [verifier] table with no answers)
instruction.md     agent-visible task description
environment/       Dockerfile that reproduces the prebuilt agent image
tests/             HELD OUT: hidden tests, test.patch, fail-to-pass test IDs, grader
solution/          HELD OUT: reference patch
```

`project_deepswe_task` opens exactly `task.toml` and `instruction.md`, by name.
It never lists, opens or hashes anything under `tests/` or `solution/`. A test
replaces Python's `open` with a guard that fails on any path in those
directories; on the full pinned corpus the loader opens 452 files (two visible
files, 113 tasks, read once for the pin check and once for projection) and none
under `tests/` or `solution/`. Breaking the adapter to read `tests/config.json`
makes that test fail immediately.

The projected record has exactly these fields; `load_deepswe_task` rejects any
other key, so a record built from a wider read fails instead of leaking:

```text
task_id  language  repository_url  base_commit
instruction  docker_image  agent_timeout_seconds  memory_megabytes
```

`task.toml` is parsed whole because TOML cannot be read partially. Its tables are
checked against the eight reviewed tables of schema 1.3 (`schema_version`,
`artifacts`, `task`, `metadata`, `verifier`, `agent`, `environment`,
`solution`). An unknown table, such as a future one holding answer material,
stops loading until someone reviews it. A different `schema_version` stops
loading for the same reason.

The loader also refuses tasks whose agent needs network access or a non-Linux
environment, because the Docker runner provides neither. All 113 pinned tasks are
`no-network` Linux tasks.

One component does read `tests/` and `solution/`: the scorer
(`agentless_ml.scoring`), which runs after a patch has been selected and says
whether it solves the task ([scoring](#scoring-a-selected-patch)). It is a
separate package that no workflow module imports, and
`tests/test_scoring_boundary.py` fails if one ever does, so held-out material
cannot reach a prompt or a selection decision through it.

## Pinning the corpus

`experiments/deepswe/corpus_pin.json` records the dataset revision, the task
count, and a SHA-256 over the agent-visible files of every task. Loading fails if
a task was added, removed, or had its instruction or metadata edited. Because the
digest covers only visible files, checking it never reads held-out material.
Windows line endings are converted to `\n` before hashing, so a clone with
`core.autocrlf=true` produces the same digest as a Linux clone.

## Abbreviated base commits

Three tasks record an abbreviated commit, consistently in their `task.toml`,
environment Dockerfile and verifier collect command:

| Task | Recorded | Pinned full commit |
|---|---|---|
| `eicrud-keyset-pagination-cursor` | `68dafce` | `68dafce500a85227b996d8fcab466d7a0c88809e` |
| `koota-entity-snapshot-rollback` | `72ebef44b8e024d877250f055eea60cdfaa4506` (39 characters) | `72ebef44b8e024d877250f055eea60cdfaa45069` |
| `langchain-request-coalescing` | `7cef35b` | `7cef35bfdebd22148a4c62a10bf01f1fde36e722` |

Candidate workspaces check out a full commit ID, because a prefix could match a
second commit later. The adapter therefore accepts an abbreviated commit only
together with a pinned full commit that starts with it; without one it raises an
error naming the task. The full commits above were resolved through the GitHub
commits API and are stored in the corpus pin.

## Language corrections

A task's language decides which parser reads its code during localization and
which test runner runs its suite, so a wrong label derails the whole workflow on
that task. Three tasks are mislabelled in the corpus. Comparing each task's
label with GitHub's main language for its repository flagged four; the task's
own instruction and the test tooling its environment Dockerfile installs, both
agent-visible, settled each:

```text
task                                     corpus label   corrected   evidence
httpx-deterministic-cookie-store         typescript     python      adds httpx.CookieStore; image installs pytest
koota-entity-snapshot-rollback           python         typescript  koota ECS API; image installs vitest
prometheus-transactional-reload-status   typescript     go          Prometheus reloaders; image installs the Go reporter
claude-code-by-agents-recursive-...      typescript     (correct)   GitHub says Swift for the repository, but the task
                                                                    is its TypeScript chat flow, tested with vitest
```

The corrections are recorded in `corpus_pin.json` under `language_corrections`,
each with its reason, and `pinned_load_options` applies them whenever a tool loads
tasks. A correction must differ from the corpus label, so if a later corpus
revision fixes a label, loading fails until the stale correction is removed.

## Normalized problem statement

Every DeepSWE instruction ends with the same line:

```text
IMPORTANT: Please work on this in a new branch from main and commit everything when you are done.
```

Harbor collects an agent's work by extracting its commits. Agentless-ML never
commits: the controller builds and exports the selected patch itself. The adapter
removes exactly that final line and nothing else, because every prompt includes
the problem statement and the model cannot act on the instruction. This is a
model-visible change. It must apply identically to every experimental condition
built from the same `TaskSpec`.

## Source repositories

Each task's repository is cloned once, ahead of a run, with everything after its
base commit removed, so the commit that fixes the issue is not sitting in the
`.git` directory the workflow reads from. The step mirrors the "git time-travel"
recipe in every task's own `environment/Dockerfile`, which all 113 tasks share
byte for byte, and whose `ARG BASE_SHA` and clone URL match `task.toml`'s
`metadata.base_commit_hash` and `metadata.repository_url` in every task — so
preparation needs no file the adapter does not already read.

```powershell
$env:PYTHONPATH = 'src'
python tools/prepare_deepswe_repositories.py `
  --tasks-root ../benchmarks/deepswe/corpus/tasks `
  --destination ../benchmarks/deepswe/repos `
  --task-id actionlint-action-pinning-lint
```

See [sealed source repositories](workspaces.md#sealed-source-repositories) for
what the seal guarantees and how it is verified.

## Running a task's tests

A task's image ships the repository already built at `/app`: the Go module cache
is warm, `node_modules` is installed, the Python package is installed. Tests do
not run there. The candidate checkout is streamed into `/tmp/work` and the suite
runs against that, because `/app` is on the container's read-only filesystem and,
more to the point, a candidate patch exists only in the checkout.

Getting that split wrong is silent rather than loud. In the `cattrs` image the
package is installed in editable mode through a `.pth` file containing
`/app/src`, so inside the container `import cattrs` resolves to
`/app/src/cattrs/__init__.py` even with the candidate sitting in `/tmp/work`.
Every candidate would then exercise the image's unpatched code, score
identically, and selection would be ranking noise. Setting
`PYTHONPATH=/tmp/work/src:/tmp/work` moves the import to
`/tmp/work/src/cattrs/__init__.py`; the two entries cover a `src/` layout and a
top-level package with one rule, and a missing entry is ignored. The check that
this is real is that breaking the candidate checkout changes the outcome:
sabotaging its `converters.py` turns a run of 16 passing tests into a collection
error, which it could not do if `/app` were the code under test.

`deepswe_execution.py` holds one command per test runner, with the report the
runner writes. The commands are ours, not the benchmark's: a task's own test
invocation lives in its held-out `tests/` directory. They are built from what
the repository itself declares, which is agent-visible.

A command per language is not enough for JavaScript and TypeScript. Reading the
reporters each task's Dockerfile installs gives, for the 40 JavaScript and
TypeScript tasks:

```text
vitest (built-in JUnit reporter)        20 TypeScript
jest + jest-ctrf-json-reporter           8 TypeScript, 1 JavaScript
mocha + mocha-ctrf-json-reporter         2 TypeScript, 3 JavaScript
no reporter in the Dockerfile            5 TypeScript, 1 JavaScript
```

`deepswe_test_runner` therefore picks the runner a repository's `package.json`
test script invokes — `jest` in awilix's `npm run check && jest`, `vitest` in
ofetch's `pnpm lint && vitest run --coverage` — and failing that the one runner
among its dependencies. A repository where neither settles it is refused. Go,
Python and Rust have one runner each.

| Runner | Report | Failed-test exit | Checked on the published image |
|---|---|---|---|
| `go test -json` + `go-ctrf-json-reporter` | CTRF JSON | 1 | `actionlint-action-pinning-lint` (Go): 1748 tests, 1732 passed, 16 skipped |
| `pytest --junitxml` | JUnit XML | 1 | `cattrs-partial-structuring-recovery` (Python): 26 tests; `fastapi-implicit-head-options`: 10 tests |
| `mocha --reporter xunit` | JUnit XML | 1–124 | `testem-per-launcher-reports` (JavaScript): 6 tests |
| `jest` + `jest-ctrf-json-reporter` | CTRF JSON | 1 | `awilix-async-container-initialization` (TypeScript): 158 tests |
| `vitest run --reporter=junit` | JUnit XML | 1 | `ofetch-per-origin-circuit-breaker` (TypeScript): 28 tests, 27 passed, 1 already failing |
| `cargo nextest run` | JUnit XML | 100 | `fd-deterministic-multi-key-sorting` (Rust): 241 tests, built from source offline in 110 s |

For each runner added here, a small change to the candidate checkout — one that
still compiles — has to change the result, test by test, or the checkout is not
what is being tested:

```text
                                       unchanged checkout      one-line change to it
mocha    testem   lib/api.js           6 passed                3 passed, 3 failed, exit 3
jest     awilix   src/utils.ts         158 passed              153 passed, 5 failed
vitest   ofetch   src/utils.ts         27 passed, 1 failed     24 passed, 4 failed
nextest  fd       src/fmt/input.rs     241 passed              230 passed, 11 failed, exit 100
```

Details each of these needed, found by running them:

- mocha's `xunit` reporter is built in, so no reporter package has to exist in
  the image. mocha exits with the number of failed tests, 3 for three, so exits
  1 to 124 all mean failed tests; above that the exit is indistinguishable from
  a signal.
- jest's reporter comes from `/opt/jest-ctrf`, which every jest task image
  installs outside the repository. It writes `ctrf/ctrf-report.json` in the
  checkout and takes no output option on the command line, so any such file
  already in the checkout is deleted first.
- vitest bundles `vitest.config.ts` into `node_modules/.vite-temp`. A single link
  from the checkout to the read-only `/app/node_modules` made that fail before
  any test ran, so each JavaScript runner gets a writable `node_modules` with one
  link per installed package.
- nextest 0.9.97 writes its JUnit file under the workspace's own `target/` and
  ignores `CARGO_TARGET_DIR`, so its store directory is set explicitly. Cargo
  takes a lock inside `CARGO_HOME`, on the read-only root, so `CARGO_HOME` is a
  writable directory linking back to the image's already-downloaded crates, and
  the build runs offline. Exit 100 is failed tests; exit 101, a failed build, is
  left undeclared.

The Go command ignores `go-ctrf-json-reporter`'s own exit status: the
reporter exits 1 whenever a test failed, after writing the complete report and
logging `build failed`. An earlier version read that as a reporter failure and
turned every real regression into a harness error. `go test`'s status is the
result. A candidate that does not compile leaves an empty report; on the
baseline that is a harness error, and on a candidate it counts as failing every
counted test ([a patch that breaks the build](public-validation.md#a-patch-that-breaks-the-build)).

```powershell
$env:PYTHONPATH = 'src'
python tools/run_deepswe_tests.py `
  --tasks-root ../benchmarks/deepswe/corpus/tasks `
  --repositories ../benchmarks/deepswe/repos `
  --task-id actionlint-action-pinning-lint -- ./...
```

Suites run as the image's own user, because the toolchain caches these tests
need live under `/root`; every other container restriction stays in place.

## Pinned published images

A task names its published image by tag, for example
`public.ecr.aws/d3j8x8q7/swe-bench-202605:kh79dnvkvq8j9bs22ededmsc79823akj-v1.1`
for actionlint. A tag can be moved to different contents at any time; a digest
cannot. `tools/pin_deepswe_images.py` looks up each tag's digest from the
registry, without downloading the image, and records all 113 in
`corpus_pin.json` as `container_digests`. Tasks loaded with that mapping carry
the digest, the controller refuses to run a task in an image whose ID differs,
and `run_deepswe_tests.py` checks the same before running. On Docker's
containerd image store the local image ID after a pull is that registry digest.
Every tag resolves to a single-platform image manifest.

The images are much smaller to fetch than they are on disk: actionlint's is
0.78 GB to download, and the largest Rust image is 2.14 GB.

113 tasks resolve to 106 distinct images. The seven shared ones are all between
tasks on the same repository and base commit, published under different tags —
for example `httpx-deterministic-cookie-store`, `httpx-multipart-response-parsing`
and `httpx-streaming-json-iteration` share one. That is also evidence about the
trust boundary: two different tasks run in a byte-identical image, so the image
cannot contain either task's held-out tests.

Every run recorded on this page uses the published image, pinned by digest.
The same suites were first run in images built locally from each task's
`environment/` directory, and gave identical counts. The `actionlint` image's
`/app` is the repository at `0bdc9571` with 2346 commits and none after it, the
same history a [sealed clone](workspaces.md#sealed-source-repositories)
produces.

One published image cannot run its suite as installed. In
`fastapi-implicit-head-options`, fastapi's `pyproject.toml` sets pytest's
`filterwarnings = ["error"]`, so any warning fails the run. The repository's
`uv.lock` pins starlette 0.52.1, but the image installed starlette 1.2.1, which
warns when it falls back to `httpx` (0.28.1 is installed; it wants `httpx2`).
Collection fails before any test runs, in the image's own `/app` as much as in a
checkout. Ignoring exactly that warning class, and still failing on every other
warning, lets the suite run: 10 tests pass with
`-W ignore::starlette.exceptions.StarletteDeprecationWarning` passed as a test
argument. This is a per-task argument, not part of the pytest command.

## Surveying tasks

Before a model is ever called on a task, four things have to hold: its sealed
repository exists, its pinned image is present, the tests to run are known, and
running them on the unpatched code yields at least one passing test — those
passing tests are the regression inventory. `tools/survey_deepswe.py` checks all
four, task by task, and records the outcome of each, so the tasks that need
attention are known in advance rather than discovered mid-experiment.

What to run is derived, not written per task. `deepswe_test_plan` takes the
runner the repository declares and its whole suite as the repository defines it:
Go gets `./...`; pytest, jest, vitest and Cargo find their own tests from the
repository's configuration; mocha gets the arguments the `package.json` test
script passes it (testem's `mocha tests/*_tests.js tests/**/*_tests.js` gives
the two globs), minus reporter and watch flags that would replace the report.
What cannot be derived lives in `experiments/deepswe/test_overrides.json`, one
entry per task, each with its reason. The file records, for example, FastAPI's
warning filter and the Prometheus tasks' testable package targets. The
transactional-reload image also needs its warmed Go cache copied into writable
temporary storage; its 8 GB `/tmp` allowance is recorded there and used by the
survey, standalone test tool and workflow alike.

The first seven image-backed runs established the runners and candidate-code
checks. Some of their results are shown below as examples, not as the current
survey total:

```text
task                                   runner          passing / tests
actionlint-action-pinning-lint         go               1802 / 1834
awilix-async-container-initialization  jest              158 / 158   (override)
cattrs-partial-structuring-recovery    pytest            879 / 900
fastapi-implicit-head-options          pytest           3134 / 3160  (override)
fd-deterministic-multi-key-sorting     cargo-nextest     241 / 241
ofetch-per-origin-circuit-breaker      vitest             27 / 28
testem-per-launcher-reports            mocha             488 / 500   (first run; later full-suite run timed out)
```

The whole suites are much larger than the targets picked by hand earlier:
testem's two globs cover 500 tests where one file had 6, and fastapi's suite is
3160 where two files had 10. fastapi's 3134 passing tests equal the 3134
pass-to-pass tests DeepSWE's own verifier checks for that task, an independent
confirmation that the derived suite is the right one.

The first survey of cattrs found no tests at all. Six of its test modules import
packages the image does not install (`bson`, `immutables`, ...), and pytest by
default stops the whole session on one module that cannot be imported. The
pytest command now passes `--continue-on-collection-errors`: the six modules are
reported as errors and stay out of the inventory, and the other 879 tests pass.

```powershell
python tools/survey_deepswe.py `
  --tasks-root ../benchmarks/deepswe/corpus/tasks `
  --repositories ../benchmarks/deepswe/repos --language go --pull
```

Each task's outcome is one line in `--results`; a surveyed task is skipped next
time, so an interrupted survey resumes. `--pull` fetches missing images and
checks them against their pinned digests; without it a missing image is
reported as `no_image`. Other outcomes are `no_passing_tests`, `no_runner`,
`image_mismatch`, `repository_failed`, and the runner's `harness_error`,
`timeout` and `out_of_memory`. The survey reads only agent-visible material.

## Running the workflow on a task

The regression stage needs an inventory of existing tests to protect. On a
DeepSWE task that inventory is one entry: the task's test plan, whose command
declares a report. The controller runs it once on the unpatched checkout, and
every test the report lists as passing becomes a selectable name. The recorded
exclusion response then removes names by test, and each candidate is judged only
on the names that remain.

`tools/run_deepswe_workflow.py` runs the fixed workflow this way with recorded
responses from `experiments/deepswe/<experiment>/`. By default the inventory is
the task's whole suite, as in the survey; an experiment can narrow it, and
`actionlint_action_pinning` keeps the root package with `"targets": ["."]`
(1748 tests rather than the whole suite's 1834). Its four recorded repairs are
hand-written harness inputs, not attempts at the task:

```text
baseline      1748 tests, 1732 passing by name -> inventory of 1732
exclusion     github.com/rhysd/actionlint::TestConfigGenerateDefaultConfigFileOK
counted       1731 tests per candidate

repair-0      no edit block                      -> repair_error
repair-1      drops ParseConfig's glob check     -> fail, 2 of 1731 counted broken:
                TestConfigParseError, TestConfigParseError/invalid_glob_pattern
repair-2      adds an unused config field        -> pass, 0 of 1731 broken
repair-3      returns an undefined identifier    -> fail, does not compile: 1731 of 1731
selected      repair-2 (best_regression_then_normalized_majority)
```

`repair-3` shows how a broken build ranks. It stays a candidate and scores as the
worst possible regression, as it would in published Agentless, rather than being
set aside as an infrastructure failure; had every candidate broken the build,
they would all tie and voting would still emit one.

The exclusion is the kind a model is asked for: adding an `action-pinning`
section may legitimately change the generated default config file, so that test
should not count against a candidate.

The run uses the task's published image, and the controller refuses it unless
its ID matches the pinned digest. `--image` can substitute another image, such
as a local build; the tool then rewrites the task to that reference and its ID,
so the substitution is pinned and recorded in the run's `task.json` rather than
hidden by retagging a local image with the published name.

## Recorded Rust workflow smoke task

`experiments/deepswe/fd_rust_smoke/` takes the real
`fd-deterministic-multi-key-sorting` task through localization, Rust edit
application, the pinned image's `cargo nextest` suite, selection, and a final
prediction. Run it with `tools/run_deepswe_workflow.py --experiment fd_rust_smoke`
and the usual tasks, repositories, workspace, and artifact paths. These
hand-written responses are controls, not a solution attempt: one removes
buffered output, while the other retains the current path ordering with an
unstable sort. The baseline had 241 passing tests. The first patch failed 80
of those tests; the second kept all 241 passing and was selected. The
post-selection DeepSWE verifier scored that selected patch unresolved: 0/43
fail-to-pass and 109/109 pass-to-pass. This checks that the Rust workflow can
emit and score a prediction without claiming to implement multi-key sorting.
The empty patch was also unresolved (0/43); the reference patch resolved all
43 fail-to-pass tests and preserved all 109 pass-to-pass tests. Those two
patches were used only after selection to check the scorer.

## Scoring a selected patch

The workflow ends with one selected patch. Whether that patch actually solves
the task is decided by DeepSWE's own hidden tests, which the workflow never sees
— that is the number a result reports, such as "solves 23 of 113 tasks". The
scorer runs those tests on the selected patch, after selection, and nothing it
learns goes back into the workflow.

It reproduces DeepSWE's verifier rather than approximating it. For each task,
`tests/Dockerfile` builds the verifier from the task's published image plus four
files: `test.sh`, `test.patch` (the hidden tests), `grader.py` and `config.json`
(the lists of tests to check). The scorer starts a container of the same pinned
image, copies those four files to `/tests` and the patch to
`/logs/artifacts/model.patch`, with no network and the task's `[verifier]`
limits, and runs `test.sh`. That script applies the patch, applies
`test.patch`, runs the hidden suites, and writes `reward.json`:

```text
reward 1   every fail-to-pass test passes and no pass-to-pass test fails
reward 0   otherwise; a test missing from the report counts as failed
```

The scorer maps that to `resolved`, `unresolved`, `patch_not_applied` (the patch
did not apply to the base commit), `verifier_error` (no `reward.json`, including
DeepSWE's own `-1` crash sentinel) or `timeout`.

Two details decide whether the score equals DeepSWE's:

- The four files are read from git at the pinned revision, not from the working
  tree. This machine's clone uses `core.autocrlf=true`, and every verifier file
  is checked out with CRLF line endings — 1778 in actionlint's `test.patch`
  alone, none in the committed file. `bash test.sh` and `git apply test.patch`
  fail on those, so every task would have scored as broken.
- All 113 verifier Dockerfiles have the same shape: the task image, the four
  `COPY`s and a `chmod`. The scorer copies the files instead of building an
  image, and refuses a task whose Dockerfile has any other shape, because
  copying would then no longer be equivalent.

A scorer is only trustworthy if it can tell a solution from nothing, so it was
first checked with two patches whose answer is known: no change at all, which
must score `unresolved`, and DeepSWE's reference solution from `solution/`,
which must score `resolved`. `DeepSWEVerifier` exposes that solution only as
`reference_patch_for_harness_validation`, and only the scoring tool uses it.

```text
                                   empty patch                  reference solution
actionlint-action-pinning-lint     unresolved  f2p  0/55        resolved  f2p 55/55  p2p 145/145
cattrs-partial-structuring-recovery unresolved f2p  0/69        resolved  f2p 69/69  p2p 7/7
testem-per-launcher-reports        unresolved  f2p  0/65        resolved  f2p 65/65  p2p 469/469
awilix-async-container-init...     unresolved  f2p  0/24        resolved  f2p 24/24  p2p 162/162
ofetch-per-origin-circuit-breaker  unresolved  f2p  0/47        resolved  f2p 47/47  p2p 13/13
fastapi-implicit-head-options      unresolved  f2p  0/43        resolved  f2p 43/43  p2p 3134/3134
fd-deterministic-multi-key-sorting unresolved  f2p  0/43        resolved  f2p 43/43  p2p 109/109
```

Seven tasks, all five languages and all six test runners. In every case the empty patch keeps every pass-to-pass test passing and fails
every fail-to-pass test, and the reference solution passes all of both.

The patch the workflow itself selected on actionlint, `repair-2` (a hand-written
harness input that adds an unused config field), scores `unresolved` with 0 of
55 fail-to-pass tests: the pipeline now runs from the issue text to a score.

```powershell
$env:PYTHONPATH = 'src'
python tools/score_deepswe.py `
  --deepswe-repository ../benchmarks/deepswe/corpus `
  --tasks-root ../benchmarks/deepswe/corpus/tasks `
  --task-id actionlint-action-pinning-lint `
  --prediction <run directory>/prediction.json
```

`--empty` and `--reference` score the two validation patches instead. Each score
writes `score.json` with the outcome, the test counts, the image ID, the patch's
SHA-256 and the DeepSWE revision, beside the verifier's own `reward.json`,
`ctrf.json` and output.

## What is not implemented

- **Runner and environment gaps.** The [4 October review](deepswe-runner-review-2026-10-04.md)
  recovered four of the six missing-runner tasks. The subsequent
  [Yjs reporting check](deepswe-yjs-reporting-2026-10-04.md) recovered a fifth,
  using its original lib0 runner. Cliffy's Deno suite cannot load offline
  with the published image's incomplete dependency cache.
  The [harness review](deepswe-harness-review-2026-10-04.md) then recovered
  Kea, SQL Formatter, mnamer and Vitest through their public setup steps.
- **Baseline eligibility across the corpus.** The survey has attempted all 113
  pinned tasks. The [28 September triage](deepswe-survey-2026-09-28.md) records
  which 71 had a usable baseline and why the other 42 did not. The 4 October
  checks, including Yjs, the harness review, and the Python symlink-task rerun,
  brought the count to 81. The subsequent
  [contained-symlink reruns](deepswe-symlink-reruns-2026-10-06.md) recovered
  six more public baselines, bringing the count to 87/113. The
  [Pest bootstrap step](pest-bootstrap-baseline-2026-10-06.md) then recovered
  another baseline, bringing the count to 88/113. The
  [Arktype and Clack runner review](deepswe-delegated-runners-2026-10-06.md)
  then recovered both delegated scripts, bringing the count to 90/113.
  [Optique and Valibot](deepswe-optique-valibot-runners-2026-10-06.md) recovered
  the last two missing-runner tasks, bringing the count to 92/113.
  The [Meriyah fresh-preparation retry](deepswe-meriyah-baseline-2026-10-08.md)
  then passed the complete public Vitest schedule in its pinned published image,
  bringing the latest count to **93/113**, with 20 tasks still not ready.
  Pwntools is parked; tasks outside these reviews retain their earlier outcomes.
  The [Drizzle and LangChain repository retries](deepswe-repository-retries-2026-10-08.md)
  clear both old preparation failures and verify their published images.
  Drizzle needs its delegated Turbo schedule (`no_runner`); LangChain's
  root-level pytest invocation fails during collection (`harness_error`).
  Neither adds a usable baseline, so readiness remains 93/113.
  The subsequent [package-level LangChain invocation](deepswe-package-schedules-2026-10-08.md)
  follows the public core unit schedule and verifies candidate imports. It
  yields 1,664 passing report IDs, bringing the latest count to **94/113**
  (19 tasks not ready); its 21 baseline failures remain visible.
  The same [package-schedule follow-up](deepswe-package-schedules-2026-10-08.md)
  implements Drizzle's public Turbo graph with its build/type prerequisites,
  pinned offline tools and all nine namespaced package reports. Its completed
  run yields 3,100 passing IDs and brings the latest count to **95/113**
  (18 tasks not ready). Failed and skipped baseline cases remain visible;
  readiness does not mean either complete suite is all-green.
  [Mobly's missing-image retry](deepswe-mobly-baseline-2026-10-08.md) then
  verifies the pinned published image and passes its unchanged public suite:
  804 passing IDs, two skipped, zero failed. The latest count is **96/113**
  (17 tasks not ready), with no remaining `no_image` records.
  [Boa's temporary-workspace retry](deepswe-boa-baseline-2026-10-08.md)
  completes without its old Windows cleanup lock and yields 1,609 passing IDs.
  One nested macro compilation still fails on temporary-storage exhaustion;
  it remains visible and does not empty the usable inventory. The latest count
  is **97/113** (16 tasks not ready), with no remaining `survey_error` records.
  [Igel's working-directory correction](deepswe-igel-baseline-2026-10-08.md)
  starts pytest from `tests/test_igel` before Igel binds its output paths.
  Both unchanged public tests pass in the pinned image. The latest count is
  **98/113** (15 tasks not ready), with three `no_passing_tests` records left.
  [Skrub's public-package baseline](deepswe-skrub-baseline-2026-10-08.md)
  uses its supported writable data directory and declared package schedule.
  The report contains 2,859 passing IDs, four failures and 357 skipped or
  expected-failure cases. The latest count is **99/113** (14 tasks not ready);
  only Eicrud and Numba still have `no_passing_tests` records.
  [Eicrud's offline MongoDB baseline](deepswe-eicrud-baseline-2026-10-08.md)
  rebuilds its candidate CLI and generated clients and starts the image's
  existing database under `/tmp`. All 24 public MongoDB suites run: 147 passing
  and 69 failed report IDs. The latest count is **100/113** (13 tasks not ready);
  Numba is the only remaining `no_passing_tests` task.
  [Numba's candidate-build and native-runner review](deepswe-numba-baseline-2026-10-08.md)
  verifies source-built extensions and candidate imports, then preserves the
  public runner's hardware-aware discovery. Its full serial schedule times out
  at the unchanged 30-minute limit without a complete report. Numba remains
  unready, now classified as `timeout`; the latest count stays **100/113**
  (13 tasks not ready). No latest `no_passing_tests` records remain, which does
  not mean every task now has a passing baseline.
  The separate [two-worker resource sample](deepswe-numba-two-worker-diagnostic-2026-10-08.md)
  exercised parallel-result recording and worker recycling, with a 1.54-GiB
  observed peak and no OOM events. Host/container timing disagreed; this sample
  does not establish full-suite runtime or change the official baseline.
  A clean repeat stopped at the intended five-minute cutoff, with at least
  350 completions, a 1.42-GiB observed peak and no OOM events. It resolved the
  timing discrepancy for that short window, not full-suite readiness.
  The subsequent [full two-worker attempt](deepswe-numba-full-attempt-2026-10-08.md)
  was interrupted without a recoverable report. Its completion is unknown;
  neither readiness nor a parallel-runtime conclusion was recorded.
  An explicitly approved fresh full attempt then stopped at the container's
  unchanged 30-minute cutoff, with at least 1,950 completions, a 4.99-GiB
  observed memory peak and no recorded OOM events. No complete report was
  accepted; readiness stays **100/113**. Its raw exit 124 is retained, and the
  full-attempt review documents the host sampling gap rather than claiming
  an uninterrupted runtime measurement. No further retry was started.
  Numba is now explicitly parked at the user's request under the current
  limits, not excluded from the dataset. Work has moved to
  [GoReleaser's hidden image caches](deepswe-goreleaser-cache-review-2026-10-08.md).
  Its approved separate cache-relocation image passed the offline module check
  and completed the unchanged full-package Go plan in 303.6 seconds, with
  2,907 passed, 46 failed and 47 skipped report IDs. No limits or test exclusions
  changed. This substituted-image inventory is not a canonical readiness
  update; the official count remains **100/113**.
  [Cliffy's cache inventory](deepswe-cliffy-cache-review-2026-10-08.md) confirms
  a different problem: eight declared JSR packages have no entries in its
  published Deno cache. The first saved failure is missing `@std/io` metadata.
  No dependencies were downloaded, image supplemented or baseline rerun in
  that inspection; readiness remains unchanged.
  The [public dependency audit](deepswe-cliffy-public-dependencies-2026-10-09.md)
  subsequently verified 956 files across 28 explicit package/version pairs,
  including missing dependency graphs and the image's existing versions.
  No image was built, tests run or canonical readiness changed. Full offline
  import resolution and Deno 2.0.0 compatibility remain the next checks.
  The approved [cache-image and offline graph check](deepswe-cliffy-offline-graph-2026-10-09.md)
  then identified and checksum-verified the image-resolved assert 0.225.3,
  taking the artifact set to 29 version pairs / 1,011 files. The separate image
  passed native no-run discovery and type checking for all 119 candidate test
  modules in 21.3 seconds, offline with unchanged Deno and limits. No tests
  executed, and the official count remains **100/113**.
  Its subsequent approved [full public baseline](deepswe-cliffy-public-baseline-2026-10-09.md)
  passed in 58.8 seconds with 822 native tests and 76 steps. The raw XML has
  898 passing entries; existing duplicate-label normalization yields 878 IDs.
  No tests were filtered, no failures hidden and no runtime protections changed.
  This completes the labelled supplemented-image baseline, not a canonical
  survey update; the original-image count stays **100/113**.
  [KGateway's build-space inspection](deepswe-kgateway-space-review-2026-10-09.md)
  confirms compiler ENOSPC on our 4-GiB scratch mount. Its Go 1.26.1 toolchain
  and 2.1-GB module cache are already accessible outside `/tmp`; the image's
  build cache is only 59 MB and is not seeded by the current runner. No retry
  or resource change was made during that inspection. The subsequently approved
  [five-minute compile-only check](deepswe-kgateway-compile-diagnostic-2026-10-09.md)
  used one build worker and reached its cutoff without a space error; highest
  sampled scratch use was 1.88 GiB. Compilation was incomplete, so this is not
  proof the full graph fits, a baseline, or a readiness change.
  The approved [full compile attempt](deepswe-kgateway-full-compile-2026-10-09.md)
  encountered a 77-minute monitoring gap consistent with host suspension and
  was stopped. It provides no usable uninterrupted full-build timing result;
  no automatic repeat or readiness change was made.
  A separately approved [keep-awake repeat](deepswe-kgateway-awake-compile-2026-10-09.md)
  ended with build failures after 317.9 seconds and no long sampling gap.
  Scratch reached 98% in the last probe, with no observed OOM. The exact compiler
  error was not retained; this is consistent with the prior space blocker,
  not direct new ENOSPC evidence. One build worker did not yield a successful
  compile, and canonical readiness remains unchanged.
  KGateway is now explicitly parked under these limits (work priority only).
  The next [Testem setup inspection](deepswe-testem-setup-review-2026-10-09.md)
  found no discoverable Firefox in its pinned image, despite the public CI
  installing it and public Mocha tests requiring Headless Firefox. No retry or
  image change was made; the saved timeout's precise cause remains unproven.
  Its subsequent [pre-build verification](deepswe-testem-firefox-verification-2026-10-09.md)
  authenticated Firefox ESR 140.17.0 and 87 Debian package archives. Extracted
  payloads cover all 21 missing ELF dependency names; runtime compatibility is
  untested. APT proposes two existing-library upgrades as well as 85 new packages,
  so this is not an implicitly approved minimal image recipe. No image was built
  and no browser or tests ran; canonical readiness is unchanged.
  An [offline upgrade review](deepswe-testem-upgrade-review-2026-10-09.md) found
  a valid smaller plan: preserve both existing libraries and explicitly select
  Debian's `dbus-x11` session-bus provider. It proposes 71 new packages, no upgrades
  and no removals. Seventy archives are already verified; the new `dbus-x11`
  archive and revised static dependency coverage remain to be checked before
  any build. No installation, download, browser execution or test retry occurred.
  The subsequent approved [revised-set verification](deepswe-testem-no-upgrade-verification-2026-10-09.md)
  acquired and verified the one new `dbus-x11` archive, rehashed all 71 selected
  packages and checked 143 ELF files offline. No missing library names were
  found; `libudev1` and `libsystemd0` remain unchanged. This is static coverage,
  not a browser startup result, image build, test retry or readiness change.
  The approved [separate image and startup check](deepswe-testem-firefox-startup-2026-10-09.md)
  then added exactly the verified 71 packages without changing existing package
  versions. Headless Firefox rendered a local page offline with JavaScript under
  the original Docker protections. Namespace/GPU-probe warnings are retained;
  no sandbox-disable flag or protection relaxation was used. This is not a full
  public baseline. The subsequent [full public attempt](deepswe-testem-public-baseline-2026-10-09.md)
  ended in timeout without a report after an observed host/tool interruption.
  It is not a clean runtime measurement or a readiness change. No repeat has started.
  The [Pwntools doctest review](deepswe-pwntools-doctest-2026-10-07.md) replaces
  its incorrect pytest invocation with the public Sphinx runner. The published
  image lacks Sphinx; a separately augmented diagnostic also exposed missing
  native tools and repeated stalls. Its interrupted run is not a completed
  baseline and does not change the 92/113 count.
  The follow-on [native-tool/SSH review](deepswe-pwntools-native-2026-10-07.md)
  verifies loopback SSH with the runner's capabilities still dropped. Selected
  public pages completed with one MSP430-toolchain failure; this augmented,
  non-root environment is still diagnostic evidence, not a full baseline.
  The [MSP430 follow-up](deepswe-pwntools-msp430-2026-10-07.md) verifies a
  checksum-pinned source-built toolchain: all 431 selected examples pass.
  The documented public Docker schedule completed with 42 passing and 12
  failing groups, using only its three documented page exclusions and our
  existing container restrictions. These derived-image results leave
  canonical readiness unchanged.
  The [RISC-V/patchelf follow-up](deepswe-pwntools-riscv-2026-10-07.md) adds
  two checksum-verified, version-pinned packages without upgrading the parent.
  The same schedule now has 44 passing and 10 failing groups; ELF and RISC-V
  shellcraft groups recovered. No exclusions or execution permissions changed.
  The [process-failure diagnosis](deepswe-pwntools-process-2026-10-07.md)
  reproduces a denied ASLR request, an upstream relative-path bug and a
  nonportable PID-1 expectation. No benchmark code or runner was patched;
  the 44/10 diagnostic result and canonical readiness remain unchanged.
  The [libcdb diagnosis](deepswe-pwntools-libcdb-2026-10-07.md) verifies local
  lookup while identifying missing historical library/package/debug data
  and an upstream provider-list mutation. No data snapshot or new image was
  added, and no public failures were hidden.
  The [public dependency audit](deepswe-pwntools-public-assets-2026-10-07.md)
  verifies all required lookup libraries, the complete symbol-query snapshot,
  matching debug files and pinned tool archives. Some original URLs are gone,
  but exact files remain available through provider/publisher fallbacks.
  That audit did not build an image. The subsequent
  [offline-data diagnostic](deepswe-pwntools-offline-2026-10-08.md) supplies
  those pinned dependencies in a separate image and passes all 42 libcdb
  examples. The unchanged public Docker schedule improves to 45 passing
  groups / 9 failing groups, with no new exclusions or permission changes.
  Canonical readiness remains 92/113.
  The separately approved [temporary host core-dump diagnostic](deepswe-pwntools-host-core-2026-10-08.md)
  restores native core retrieval and improves the same schedule to 46/8.
  It also introduces six ARM/QEMU failures, so it is not a general fix.
  The original WSL host setting was restored; readiness remains unchanged.
  The approved [non-colliding filename follow-up](deepswe-pwntools-noncolliding-core-2026-10-08.md)
  tests `core.native.%p` and passes all 107 core-file and 176 ROP examples.
  The same schedule improves to 47/7, with no new exclusions or container
  permission changes. The host setting was restored again; readiness stays 92/113.
  The [SSH filesystem follow-up](deepswe-pwntools-ssh-aligned-2026-10-08.md)
  uses a separate offline-derived image to align the public home path and
  SFTP creation mask. The unchanged filesystem page passes 148/149 examples,
  up from 144/149; its tmpfs block-allocation expectation remains failed.
  This is a selected-page result, not another full schedule or readiness change.
  A separate [offline HTTPS service diagnostic](deepswe-pwntools-services-2026-10-08.md)
  serves pinned genuine public data without external networking. The unchanged
  update page passes all 11 examples through a real cold HTTPS fetch; no update
  cache is seeded. A follow-up with the exact same image also passes all six
  unchanged public download examples through real HTTPS. These are separate
  selected-page runs, explicitly a modified environment, not a canonical
  readiness improvement or a new full-schedule result.
  The [shared HTTP/TLS follow-up](deepswe-pwntools-protocol-services-2026-10-08.md)
  passes all 164 context and 35 socket examples using real local connections.
  Sphinx also includes 219 passing related tube examples: 418 total, with zero
  setup/cleanup failures. This explicitly labelled three-host condition does
  not demonstrate live Google access or change canonical readiness.
  The [repository review](deepswe-repository-review-2026-10-04.md) found that
  all 22 old unsupported-task trees are accepted by the current provider, but
  Linux symlink semantics and submodule requirements still need runtime checks.
  [Git-aware Linux snapshots](git-aware-linux-snapshots-2026-10-04.md) now
  preserve contained relative links and Git executable modes. The Python
  symlink task now has a passing full public baseline. All 15 remaining
  contained-symlink tasks have since been revisited: six were recovered in that
  batch; Pest, Arktype, Clack, Optique and Valibot recovered five more.
  Four retain setup or memory blockers. Absolute-link fixtures remain
  unsupported, and three submodule-only tasks still need runtime checks.
  A separate [Wazero memory diagnostic](wazero-memory-diagnostic-2026-10-05.md)
  passed the full public schedule at a 16-GiB container limit, with observed
  memory above the published 8-GiB cap. It validates report conversion on the
  large suite but did not change readiness; it remains outside the current
  92/113 count.
  The subsequent [8-GiB retries](wazero-8g-retries-2026-10-06.md) also ended in
  OOM with serial execution and earlier garbage collection. The serial run
  identified the public `TestEngineInterpreter/huge_binary` stress test as an
  OOM victim; Wazero remains resource-blocked for the full public schedule.
- **Workflow and scoring over many tasks.** The survey establishes each task's
  regression inventory, but running the workflow needs repair responses, and
  only actionlint has recorded ones; without a model there is nothing to run for
  the other tasks. The scorer likewise scores one patch at a time. No DeepSWE
  task has a reproduction specification.

## Evidence

[Adapter tests](../tests/test_deepswe_adapter.py) cover the real vendored task
`abs-module-cache-flags` (its `task.toml` and `instruction.md` only), held-out
access, rejected fields, unreviewed tables, schema versions, network and language
checks, abbreviated commits, pin changes, line-ending stability and task
selection. Set `AGENTLESS_DEEPSWE_TASKS` to a local `deep-swe/tasks` directory at
the pinned revision to also load all 113 tasks.

[Execution tests](../tests/test_deepswe_execution.py) pin the part of each
command that makes the checkout the code under test, that targets are passed as
arguments rather than spliced into the script, and that an unverified language
is refused. They do not run Docker; the runs recorded above were made with
`tools/run_deepswe_tests.py` against real images.
