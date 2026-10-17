# Numba: per-test timing in one short diagnostic

> Development record. See [the documentation guide](../README.md) for current status.

The five-minute sample recorded 441 completed native worker invocations and
two unfinished calls. The slowest completed call took 38.09 seconds. This is
timing evidence, not a baseline: DeepSWE readiness remains **112/113**.

The run started late on October 12 and finished after midnight on October 13
(Europe/Paris). No full-suite retry was made.

## What changed

The short diagnostic now wraps Numba's `_MinimalRunner.__call__` with an
importable subclass. Spawned workers can import that subclass themselves;
patching only the parent's unittest result would not time their work.
The wrapper records the scheduled test ID, worker PID, monotonic start time
and finish duration. Each worker writes its own journal and flushes the start
before calling the original implementation. A killed call therefore leaves a
start without a finish. A finish means the native invocation returned or
raised, **not that its test passed**.

Times include native worker setup, test execution and worker cleanup. They
exclude pool startup, parent aggregation and time waiting in the queue. The
serial-only phase is not instrumented by this wrapper and was not reached.
This does not measure JIT compilation separately from other work.

Before removing the container and its anonymous scratch volume, the helper
copies all journals to `test-timings.json` and writes
`test-timing-summary.json`. A capture error is recorded explicitly. Capture is
bounded at 8 MiB and does not silently truncate. The records are collected at
normal diagnostic shutdown, not continuously backed up during the run.

The changes are confined to the opt-in diagnostic. The registered baseline,
test files, assertions, native discovery, batch ordering and two-worker
schedule are unchanged. The pinned image, candidate-built extensions,
8 GiB memory cap, two-CPU quota, disk-backed scratch, Docker-default swap,
`OPENBLAS_NUM_THREADS=1`, offline network and other Docker protections are
unchanged. The inner test window remains 300 seconds; the outer cap is 1,800.

## Results

There are 884 raw events: 443 starts and 441 finishes. At cutoff, the two
unfinished IDs were:

- `numba.tests.test_array_methods.TestArrayMethods.test_clip`
- `numba.tests.test_array_methods.TestArrayMethods.test_array_view`

They had started about five seconds before the final capture. That elapsed
value includes the short delay between termination and capture; it is not a
completed runtime or proof of a hang.

The slowest completed calls were:

| Test (under `numba.tests`) | Seconds |
| --- | ---: |
| `test_array_manipulation.TestArrayManipulation.test_fill_diagonal_basic` | 38.09 |
| `npyufunc.test_dufunc.TestDUFuncReduceNumPyTests.test_reduce_zero_axis` | 16.62 |
| `test_array_analysis.TestArrayAnalysis.test_numpy_calls` | 15.77 |
| `npyufunc.test_dufunc.TestDUFuncAt.test_ufunc_at_negative_indexes` | 14.54 |
| `npyufunc.test_dufunc.TestDUFuncReduceAt.test_reduceat_axis_kw` | 14.40 |
| `test_array_manipulation.TestArrayManipulation.test_array_transpose_axes` | 13.94 |

The median completed duration was 0.321 seconds. The nearest-rank 95th
percentile was 6.410 seconds. Eleven completed calls took at least ten seconds;
26 took at least five seconds. Those 26 account for 278.04 of the 526.85
summed worker-seconds. Worker-seconds overlap across the two workers and must
not be read as wall time.

The second 100-case pool took about 98.50 seconds between its first start and
last finish. The fourth took about 90.86 seconds. This confirms the slower
groups identified in the earlier batch review, now with individual test IDs.
The fifth group was interrupted after 41 completed calls.

The 29 resource samples recorded a peak of 1,643,921,408 bytes (1.53 GiB), no
OOM events and no swap use. The inner timeout exited with code 124, as intended;
the generic runner labels that `harness_error`. No complete JUnit report or
accepted regression inventory was produced. The shutdown semaphore warning
remains in stderr. The temporary container and scratch volume were removed.

## Interpretation and next step

The early schedule is not blocked on one stuck test: substantial time is
spread across several calls, with a particularly expensive diagonal-fill
case. Its public source constructs a JIT-compiled function and exercises
multiple shapes, layouts, value types and wrapping modes. Compilation is a
plausible contributor, but this timer does not establish its exact share.

This sample does not predict the runtime of the remaining schedule or prove
that another full attempt would finish. Before another retry, inspect the
measured slow cases and the native pool barriers for supported ways to reduce
repeated compilation without dropping tests or changing their assertions.

## Evidence and checks

Artifact directory, relative to the parent of this repository:

```text
output/deepswe-survey/numba-two-worker-diagnostic/logs/agentless-ml-c2b1a3d79e7f4ecaa99c2e15f85b9bb4/
```

It contains the raw timing events, timing summary, resource journal,
`resource-diagnostic.json`, `execution.json`, stdout and stderr.
SHA-256 of `test-timings.json`:

```text
f97764e930beb4741c0c328ce4c2589dfa1c1b9692712e9a49d093e76e8a0c5b
```

The image is unchanged:
`sha256:d30747d56f59cb61bb9a4e87ba8dc4df29ccbb471a1a1146f20d5d9d58fa90ac`.
The task remains pinned to commit
`5781334aa654972fdc749003e7c1e93e6d277110`.

All 19 focused timing, diagnostic and Numba-reporting tests passed. They check
spawned-worker instrumentation, preservation of native returns and exceptions,
a flushed start surviving actual process termination, unfinished-call handling,
capture before removal, and cleanup after capture failure.

Follow-up: the [compilation-event diagnostic](deepswe-numba-compilation-diagnostic-2026-10-13.md)
separates compilation intervals, repeated attempts and source-level recurrences
in one further short sample. The numbers above remain those of this earlier run.
