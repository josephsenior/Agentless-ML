# DeepSWE contained-symlink reruns — 6 October 2026

Six more tasks now have usable public regression baselines. The latest survey
is **87/113 ready**, up from 81/113 before this batch.

We revisited the 15 remaining tasks whose old `unsupported_repository` result
came from contained relative symlinks. Every task got past workspace creation.
The existing Git-aware snapshot support was enough for six baselines; the
other nine exposed runner, setup or resource problems instead.

## Results

| Task | Latest outcome | Public baseline or blocker |
| --- | --- | --- |
| `arktype-json-schema-refs-dependencies` | `no_runner` | Root script delegates to `testTyped`; discovery does not resolve that Mocha alias |
| `clack-async-autocomplete-options` | `no_runner` | Root script delegates to workspace packages; no root runner dependency |
| `effect-sse-httpapi-streaming` | `ready` | 976 passed, 541 failed, 1,517 reported |
| `goreleaser-retry-publish-auditing` | `harness_error` | Go tries to download the uncached Go 1.26.1 toolchain; networking is disabled |
| `kgateway-consistent-hash-policy` | `harness_error` | Go compilation exhausts the 4-GiB tmpfs; report conversion also rejects the resulting malformed event stream |
| `optique-conditional-option-dependencies` | `no_runner` | Deno workspace without a root `package.json`; Node discovery is the wrong entry point |
| `participle-grammar-conflict-analysis` | `ready` | 168 passed, 1 failed, 169 reported |
| `pebble-durability-wait-apis` | `out_of_memory` | Container OOM during the full Go schedule; saved output includes a linker killed by a signal |
| `pest-character-class-coalescing` | `harness_error` | Public build requires the `pest_bootstrap` executable first |
| `pwntools-tube-multiplexing` | `harness_error` | Default pytest invocation collects zero tests; contributor documentation points to doctests and `TESTING.md` |
| `query-persist-restored-query-state` | `ready` | 112 passed, 143 failed, 255 reported |
| `scc-bounded-memory-spilling` | `ready` | 283 passed, no failures |
| `sqlfmt-create-table-ddl-formatting` | `ready` | 1,089 passed, 139 failed, 1,228 reported |
| `task-task-graph-export` | `ready` | 449 passed, 155 failed, 604 reported |
| `valibot-recursive-schema-composition` | `no_runner` | Root script delegates to workspace packages; no root runner dependency |

Here, `ready` has the survey's existing meaning: the invocation finishes with a
usable report containing at least one passing public test. It does not mean
the whole suite passes, every repository test was collected successfully, or
the benchmark task was solved. Only passing baseline tests become regression
requirements. Failed cases and suite-loading problems remain in the evidence;
they have not been individually explained or repaired in this batch.

The OOM run yields no accepted inventory, even though Pebble reported passes
before it was killed. Its recorded zero tests means no usable completed report,
not that no tests executed.

## What stayed unchanged

Each attempt used the sealed base revision, its pinned published image,
the task's declared 8-GiB memory limit and two CPUs. Runs were sequential, with
the existing 4-GiB tmpfs and 1,800-second command timeout. Networking remained
disabled. No images were pulled or deleted, no task-specific overrides were
added, and no tests were excluded to make a run pass.

No model was called. The benchmark's held-out tests and reference solutions
were not used. These are unpatched public-baseline checks, not evaluation
scores or repair experiments.

## Evidence and next work

[The evidence summary](../experiments/deepswe/symlink_reruns_2026_10_06.json)
records all 15 outcomes, base commits, expected image IDs, execution image IDs
where a runner executed, counts, artifact paths and execution-file SHA-256s.
Raw reports and logs remain outside Git in `../output/deepswe-survey`.
The runs are appended to its local `survey.jsonl`; the latest record for each
task determines readiness.

The corpus now has 87 ready tasks, five harness errors, five old unsupported
records, four missing runners, four baselines without passing tests, three
repository preparation failures, two OOM outcomes, and one each of missing
image, survey error and timeout. Tasks outside this batch keep their previous
results. In particular, the two Helm absolute-link fixture tasks and the three
remaining submodule-only tasks were not rerun. Wazero remains blocked at its
published memory limit; its 16-GiB diagnostic does not count as readiness.

The next small implementation target is Pest's documented bootstrap build,
followed by review of the delegated and Deno public test entry points. Each
change still needs a fresh baseline in the pinned image. Kgateway's tmpfs
capacity, GoReleaser's toolchain availability and Pebble's memory use need
separate checks; this batch did not change their environments.

The existing command and snapshot tests also passed: **86 passed, four skipped**.
The skips were host-native-symlink and opt-in Linux checks. No runner code was
changed for these reruns.
