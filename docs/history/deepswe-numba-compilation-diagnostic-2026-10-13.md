# Numba: compilation events in one five-minute sample

> Development record. See [the documentation guide](../README.md) for current status.

The sample found no compilation repeated after a registered result on the
same dispatcher and signature. It did find substantial compilation of new
specializations and fresh function objects created by the public tests.
There is no demonstrated cache fix to apply before another full attempt.

Readiness remains **112/113**. One short diagnostic ran; no full-suite retry
or registered baseline change was made.

## What the hook records

The diagnostic's spawned workers now temporarily listen to Numba's existing
`numba:compile` events around each native test invocation. Each event records
the test ID, PID, a worker-local dispatcher token, source location, closure
representations, argument type names, requested return type and target options.
The dispatcher registry uses weak references, so recording does not keep
compiled functions alive after the test would otherwise release them.

Start records are flushed immediately. End records include duration and whether
the argument signature actually appears in the dispatcher's overload table.
An event ending does not by itself mean compilation succeeded: literal-dispatch
requests and expected typing errors can also end an attempt.

The summary separates repeated attempts on one dispatcher from recurrences
at the same source location across distinct dispatchers or workers. Type names
are rendered strings, not canonical type identities; distinct generated ufunc
types can have the same printed name. Source-level recurrences are therefore
candidates for inspection, not proof of interchangeable compiled code. The
three repeated groups actually observed here use ordinary integer/array/tuple
types and were checked against their public source.

Per-test compiler time is the union of completed event intervals, so nested
compilation is not added twice. Source-group durations remain inclusive and
can overlap. The hook misses imports before a worker invocation, cache hits,
direct compiler pipelines, and any compile event interrupted before its end.
It can observe nested dispatcher compilations inside a direct pipeline without
measuring that pipeline's own complete runtime.

## Results

- 368 completed worker invocations; two unfinished at cutoff.
- 2,599 completed compilation attempts and one unfinished compilation.
- 2,464 attempts registered an overload; 135 did not.
- 2,590 distinct dispatcher/rendered-signature groups among completed attempts.
- Nine extra attempts across three repeated groups; none followed a registered
  overload on that dispatcher/signature.
- 387 source/signature groups recurred across different dispatcher objects.
  These are not 387 proven redundant compilations.

The repeated groups were:

| Public test | Attempts in group | Registered results | Summed inclusive time |
| --- | ---: | ---: | ---: |
| `DocsLiterallyUsageTest.test_literally_usage` | 6 | 0 | 0.142 s |
| `TestDUFuncReduce.test_non_associative_reduce`, first dispatcher | 3 | 0 | 0.012 s |
| Same test, second dispatcher | 3 | 0 | 0.016 s |

The literal example explicitly requests literal dispatch for non-literal
arguments. The reduction helper explicitly expects typing errors for
non-reorderable multi-axis reductions. These small repeated attempts do not
explain the timeout. The total durations in this table include the first
attempt in each group, not just the nine extra attempts.

For four completed slow calls, the captured compilation intervals explain
nearly all their instrumented wall time:

| Test (short name) | Wall time | Compilation interval union | Completed events |
| --- | ---: | ---: | ---: |
| `test_ufunc_at_negative_indexes` | 27.27 s | 27.21 s | 130 |
| `test_reduce_zero_axis` | 25.89 s | 25.87 s | 129 |
| `test_numpy_calls` | 24.43 s | 23.58 s | 174 |
| `test_reduceat_axis_kw` | 22.93 s | 22.92 s | 67 |

These counts include nested dependency compilation, not just the test's own
wrapper. For example, the negative-index test accounts for 50 wrapper events,
50 ufunc implementation events, and 30 array/broadcast helper events. All 130
registered results. Its source deliberately loops over multiple dtypes and
five different ufuncs, while reusing cached helpers within the test instance.

The largest source-level recurrence involved three separate reduction wrappers
in two workers, with the printed signature `array(float64, 3d, A), none,
omitted(default=None)`. They came from three distinct public identityless
reduction tests. The public `_generate_jit` helper constructs a new vectorized
operation and wrapper for each invocation. These two workers belong to the
same 100-test pool: this example is not explained by the pool being restarted.
Other recurrences involve separately created ufunc closures, whose printed
types are not enough to establish equivalent operations.

The prior sample's slowest case, `test_fill_diagonal_basic`, was not reached.
This run was cut off during `test_array_transpose_axes` and `test_array_reshape`.
One transpose compilation also has a start without an end. These incomplete
calls are not reported as finished or passing.

## What this means for the next attempt

Compilation dominates the measured slow calls. The sample does not show a
successful specialization being needlessly rebuilt on the same dispatcher.
Some similar code is compiled again in fresh dispatchers, but that comes from
upstream test construction and cannot safely be removed by assuming closures
or test instances are interchangeable.

Setting `NUMBA_CACHE_DIR` alone would not enable caching for decorators that
leave it disabled. Forcing caching, sharing test-local dispatchers, disabling
JIT, reducing optimization, or modifying pool recycling would change behavior
being exercised and is not justified by this diagnostic. None was done.

An unchanged full retry is not supported by these findings. Keep Numba unready
under the current limits unless a concrete, coverage-preserving runner change
is established. This early sample is not a full-suite runtime estimate.

## Limits, evidence and checks

The same pinned image, candidate extension build, native full discovery,
two-worker schedule, 8 GiB cap, two-CPU quota, 300-second inner window and
1,800-second outer cap were retained. Disk scratch, Docker-default swap,
`OPENBLAS_NUM_THREADS=1`, offline networking and Docker protections are unchanged.
Only the opt-in diagnostic enables the event hook.

There were 29 resource samples. Peak recorded memory was 1,529,290,752 bytes
(1.42 GiB), with no OOM events or swap use. The deliberate inner timeout
returned 124, labelled `harness_error` by the generic runner. There is no final
JUnit report or accepted regression inventory. The shutdown semaphore warning
is retained in stderr. The container and anonymous volume were removed.

Instrumentation adds overhead, and host conditions were not controlled against
the earlier run. Do not treat 368 versus 441 completed calls as a measured
performance regression or use their durations as a clean before/after comparison.

Artifacts, relative to the parent of this repository:

```text
output/deepswe-survey/numba-two-worker-diagnostic/logs/agentless-ml-e233760e5bdf40aea8649011ebbd2687/
```

`test-timings.json` contains 5,937 raw events. Its SHA-256 is:

```text
e2d8092b2ff7f335089909da8a22d7a33119b88b14861436d5e08c1c12f7fbbc
```

`compilation-summary.json` retains the complete per-test breakdown and all
source-level recurrence groups. Resource samples, execution metadata, stdout,
stderr and the test-timing summary are retained alongside it. The journal was
captured within the existing 8 MiB limit, without truncation.

Twenty focused tests passed, including hooks in spawned workers, native
returns/errors, registration versus no registration, exact-repeat grouping,
cross-worker separation, nested interval unions and interrupted records.

See also the [earlier per-test diagnostic](deepswe-numba-per-test-diagnostic-2026-10-13.md).
