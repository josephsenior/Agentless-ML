# Pebble: upstream CI-mode diagnostic

Follow-up: the setup was subsequently registered and the
[official survey refresh](deepswe-pebble-registered-ci-2026-10-10.md) reached
109/113 ready. The diagnostic results below remain unchanged.

The three huge-memory row-block tests really do skip under `CI=1`, with
the upstream reason "Skipping test: requires too much memory for CI".
After that verification, one full public schedule completed without an OOM.

## Two phases, no automatic retry

The first phase selected exactly these three public tests in
`./sstable/rowblk`:

- `TestSingularKVBlockRestartsOverflow`
- `TestExceedingMaximumRestartOffset`
- `TestMultipleKVBlockRestartsOverflow`

All three reported skipped, not passed. The gate checks their exact IDs,
statuses and upstream messages before allowing the full run.

The second phase ran `go test -json -count=1 -p 1 ./...` with `CI=1`.
There was no test-name filter in this phase. Both phases used fresh candidate
workspaces and cold writable caches; no image cache was seeded. Only the
public-test command received the environment setting. No source, assertions,
build tags, image, host configuration or held-out scorer was changed.

The original repository and image pins are in the
[compact evidence](../experiments/deepswe/pebble_ci_mode_2026_10_10.json).

## Result

Skip verification took 102.54 seconds including snapshot and setup. It exited
zero with exactly three skips and a peak of 657,530,880 bytes.

The full schedule took **415.17 seconds**, also including snapshot and setup,
well inside the unchanged 1,800-second deadline. Its accepted report contains
**14,251 passed, 10 failed and 18 skipped** test results. All three intended
row-block skips are present in that report. Other skips are retained too.

The command correctly exited **1**: this is a completed failing baseline, not
an all-green run. All ten failed IDs belong to `internal/lint`: nine child
results and their parent `TestLint`. The evidence lists each ID. Their precise
causes have not been established from this run: the compact report contains
statuses, and the bounded final Go event tail does not preserve the early
lint output. Do not infer ten independent code defects or claim those failures
are fixed.

Peak cgroup memory was **2,040,250,368 bytes (1.90 GiB)**. All final memory-event
counters were zero, and Docker reported `OOMKilled=false`. This contrasts with
the [previous run without CI](deepswe-pebble-full-single-worker-2026-10-10.md),
which hit the 8 GiB ceiling.

## Protections and evidence

Live inspection confirmed the same 8 GiB RAM/no extra swap, two CPUs, 2,048
PIDs, 4 GiB tmpfs, no network, read-only root, dropped capabilities and
no-new-privileges. There were no host bind mounts, added hosts, published ports
or privileged mode. Temporary workspaces and owned containers were cleaned up.

The shared sampler still calls its progress messages "compile resource sample";
these were full public tests. Its initial probe can run before cache/log files
exist, and its unused `/tmp/compile-work` check emits a missing-directory warning.
Neither is a test failure. Raw journals, reports, execution records and bounded
Go event tails are hashed in the evidence.

The diagnostic helper and related checks passed **15 host tests**. No permanent
public-validation configuration or official survey was changed: readiness stays
**108/113**.

Next: review registering the scoped `CI=1`, one-worker public setup for both
baseline and candidate validation, then refresh the official survey. A failing
baseline can supply passing regression IDs; this result does not itself change
readiness or authorize silently suppressing lint failures.
