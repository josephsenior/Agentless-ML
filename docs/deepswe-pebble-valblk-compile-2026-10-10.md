# Pebble: one-package compile diagnostic

The saved full-schedule attempt was classified `out_of_memory` after 400.60
seconds. Its stderr identifies a linker killed while building
`github.com/cockroachdb/pebble/sstable/valblk.test`. No completed report was
accepted. The runner's OOM classification comes from Docker's `State.OOMKilled`,
not from interpreting a generic connection error or killed-linker message.
The older execution artifact does not preserve the raw Docker state or resource
timeline, so it cannot tell us the exact memory peak or competing processes.

The approved short check isolated that package:

```sh
GOCACHE=/tmp/go-build timeout --signal=TERM --kill-after=10s 300s \
  go test -c -p 1 -o /tmp/pebble-valblk.test ./sstable/valblk
```

It used a fresh candidate checkout at
`1454d2bc0f378d7f34766afafee68a77e7b85995` and the original pinned image
`sha256:b063f2d927a8b3d71db24c4ec198a0d05644d3ecbe96289d8b2b2bdbecaa72bd`.
The existing Go build cache was not copied from the image. The installed module
dependencies were available offline.

## Result

Compilation completed with exit **0**. The runner took **114.48 seconds**,
including snapshot preparation and extraction; this is not a compiler-only
timing. The five-minute window was not exhausted. Native `go test -c` compiles
and links the package's test binary without running it, so there is no passing
test inventory or readiness change.

Final cgroup readings showed a **721,887,232-byte peak** (about 688 MiB),
zero `oom` events and zero `oom_kill` events. Docker still reported the owned
container running with `OOMKilled=false` and no state error before cleanup.

Eight incremental samples were saved with elapsed and UTC timestamps; the largest
UTC gap between them was 10.33 seconds. There was no observed Docker connection
failure. The initial sampler invocation returned 1 because it ran before the
command's logs and cache existed, not because Docker disconnected. Its memory
counters were already readable. The reused sampler also checks the unused
`/tmp/compile-work` directory; that missing-directory warning is diagnostic
probe stderr, not compiler stderr. The compiler's saved stderr is empty.

## What this establishes

The isolated package can compile with one build worker under the original
limits. It does not establish that the entire schedule fits. The full attempt
had other package builds and tests in flight, while this diagnostic did not.
Those differences prevent us from attributing the recovery solely to reduced
concurrency. Nor does this successful attempt establish a connection cutoff as
the cause of the earlier recorded OOM.

The next useful check would be one explicitly labelled full-public-schedule
diagnostic with `-p 1`, retaining all targets and the existing 30-minute cap.
It has **not** started, and no permanent test override was added.

## Limits and evidence

Live inspection confirmed 8 GiB RAM with no extra swap, two CPUs, 2,048 PIDs,
4 GiB tmpfs, no network, read-only root, all capabilities dropped,
no-new-privileges, no privileged mode, no host binds, no added hosts and no
published ports. The outer command deadline remained 1,800 seconds; the inner
300-second cap was specific to this short diagnostic. No host power settings
were changed. The owned container and temporary checkout were cleaned up.

The diagnostic helper and its existing sampler checks passed **eight host
tests**. No benchmark tests, model calls or held-out inputs were involved.
Readiness remains **108/113**. The official survey was not updated.

[Compact evidence](../experiments/deepswe/pebble_valblk_compile_2026_10_10.json)
records the limits, final state, sampling caveats and artifact hashes. The raw
resource journal, final cgroup probe and execution logs remain in the referenced
output directory. Reproduce with `python tools/run_pebble_compile_diagnostic.py`
from an environment with `PYTHONPATH=src`; every invocation is a new diagnostic,
not a resumed or accepted baseline.
