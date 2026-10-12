# Numba: where the short sample spent its time

This review uses the saved 2026-10-12 short diagnostic and discovery-only
probes. No test bodies or new baseline were run during the review. Public
regression readiness remains 112/113, with Numba unready.

## Native batching

At the pinned revision, `numba/testing/main.py:794` divides the parallel
inventory into groups of 100. It starts a new two-worker pool for each group,
waits for that whole group, and joins the old pool before moving on. Recycling
limits memory growth. The 702 serial-only tests run after all 9,907 parallel
entries. Within each group, tests are sorted by the source file's modification
time and dispatched with `imap_unordered`.

The saved process samples identify the first five worker pools. Combining
worker changes with the 100/200/300/400 completion markers gives these bounds:

| Batch | Parallel entries | Public test families | Approximate elapsed range |
| --- | --- | --- | --- |
| 1 | 1–100 | No-CUDA tests, documentation examples, early ufunc cases | 20–41 seconds |
| 2 | 101–200 | Ufunc reductions, generalized ufuncs and related cases | 82–103 seconds |
| 3 | 201–300 | Ufunc building, analysis, annotations, early array attributes | 20–41 seconds |
| 4 | 301–400 | Array attributes/constants, expressions, iteration and manipulation | 82–103 seconds |
| 5 | 401–500 | Array manipulation/methods and early reductions | Incomplete at cutoff |

These are bounds inferred from roughly ten-second samples of pool transitions,
including transition overhead, not per-test stopwatch measurements. Times use
the saved host sampling clock. Batch 2 began between sample offsets 41.38 and
51.61 and finished between 133.66 and 143.90. Batch 4 began between 164.40 and
174.68 and finished between 256.71 and 266.96.

The batch-2 pool used PIDs 317/318; batch 4 used 649/650. During sampled busy
intervals, cgroup CPU usage increased by about two CPU-seconds per elapsed
second. Batch 4 later fell toward one CPU as a remaining worker finished its
work. This is consistent with a batch barrier leaving one worker waiting for
the other. No OOM events or swap use were recorded in the sample.

## Which source belongs to those groups

A discovery-only probe intercepted the native parallel runner before execution
and applied its existing split function. The first 500 ordered IDs have SHA-256
`29099860dbcb9fb760e86e2eab9a0107e2f543f802b231ef3b3ac1dd351a2fda`.
All 414 Python files under the public test trees, `numba/testing`, and the root
runner matched the sealed repository byte-for-byte. The relative-path/hash
manifest has SHA-256
`321668049ffd663b6c137bcee3ce71c854e6420282deab08b30879e2dc83adc4`.
The probe containers were removed automatically.

Batch 2 contains 36 cases from `npyufunc/test_dufunc.py`, 38 from
`npyufunc/test_gufunc.py`, and 26 other ufunc/error/building cases. The reduction
helpers compile functions across different array dimensions and signatures;
see `test_dufunc.py:797`.

Batch 4 contains 11 array-attribute cases, 12 constant-array/byte cases,
21 array-expression cases, 21 iterator cases and 35 manipulation cases.
`test_array_exprs.py:120` explicitly compiles both rewritten and unrewritten
versions of a function; some tests compile further variants as well.

Batch membership is reconstructed from matching public source and native
discovery. Exact within-batch order depends on checkout file timestamps, so
image timestamps are not used to claim which individual test ran at a specific
sample offset.

## What this establishes

The two slower observed groups are doing CPU work. Their source contains
substantial JIT compilation, making compilation a plausible major cost, but
the saved data does not separate compilation time from test computation.
The native pool reset also discards process-local compilation state; its
contribution to elapsed time has not been measured.

The recorder retains progress every 25 completions, worker processes and
resource counters, rather than individual test IDs and durations. It therefore
cannot rank the slowest individual cases or describe the unvisited later
groups. The observed early rate is not a full-suite runtime estimate.

Before spending another full 30-minute attempt, the useful next diagnostic is
per-test start/finish timing in the same short window, including unfinished
test IDs. That would distinguish a few slow cases from widespread compilation
cost while preserving the native schedule, workers and resource limits. No
such instrumentation or further test attempt was added by this review.

The [short diagnostic evidence](deepswe-numba-blas-diagnostic-2026-10-12.md)
identifies the original journal and logs used for these observations.

Follow-up: the [per-test timing diagnostic](deepswe-numba-per-test-diagnostic-2026-10-13.md)
has now recorded individual calls in one further five-minute window. The
measurements above still refer only to the earlier, uninstrumented sample.
