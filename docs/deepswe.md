# DeepSWE integration

DeepSWE provides 113 tasks across Go (34), Python (34), TypeScript (35),
JavaScript (5) and Rust (5), pinned at `datacurve-ai/deep-swe`
`0b9fabbb63b9104d678fe965e1632f2dd9eaa2ea`. It is the only target benchmark
that covers all five workflow languages; SWE-bench Pro has no Rust tasks.

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
  --tasks-root ../benchmarks/deep-swe/tasks `
  --destination ../benchmarks/deepswe-repos `
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
  --tasks-root ../benchmarks/deep-swe/tasks `
  --repositories ../benchmarks/deepswe-repos `
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

## Running the workflow on a task

The regression stage needs an inventory of existing tests to protect. On a
DeepSWE task that inventory is one entry: the language's test command, which
declares a report. The controller runs it once on the unpatched checkout, and
every test the report lists as passing becomes a selectable name. The recorded
exclusion response then removes names by test, and each candidate is judged only
on the names that remain.

`tools/run_deepswe_workflow.py` runs the fixed workflow this way with recorded
responses from `experiments/deepswe/<experiment>/`. On
`actionlint_action_pinning` the four recorded repairs are hand-written harness
inputs, not attempts at the task:

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

## What is not implemented

- **Unchecked JavaScript and TypeScript runners.** Two TypeScript tasks use
  mocha; they would get the mocha command, which has only been run on
  JavaScript. Five TypeScript tasks and one JavaScript task install no reporter
  their Dockerfiles show; none has been run, and `deepswe_test_runner` refuses a
  repository whose runner it cannot tell rather than guessing.
- **Per-task quirks.** Two of the tasks run here needed an argument specific to
  them: fastapi's warning filter, and awilix's
  `--testPathIgnorePatterns=rollup.test`, because `rollup.test.ts` imports the
  build output `lib/awilix`, which is not in the repository. Such arguments are
  found by running a task, not derived automatically.
- **Choosing what to run.** Which part of a repository's suite forms the
  inventory (`"targets": ["."]` for actionlint) is still written by hand per
  experiment, and only one task has a recorded experiment. No DeepSWE task has a
  reproduction specification.
- **Scoring.** The official verifier (Pier/Harbor, run in a separate pristine
  container) is not integrated. It must only ever run after final selection.

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
