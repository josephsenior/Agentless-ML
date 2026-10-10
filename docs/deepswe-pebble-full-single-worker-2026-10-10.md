# Pebble: full schedule with one package worker

One approved diagnostic ran the complete existing public package target
`./...` with `go test -json -count=1 -p 1`. The only change to the ordinary Go
template was `-p 1`; targets, reporting, failure exit codes and the
1,800-second deadline were retained. The original pinned image and sealed
candidate checkout were used. No cache was seeded from the image.

The attempt finished with **out_of_memory**, command exit **1**, after
**386.61 seconds** including snapshot and setup. It did not reach the 30-minute
deadline. Docker's final state had `OOMKilled=true`, and final cgroup counters
showed:

```text
memory.peak 8589934592
memory.events:
  max 114
  oom 1
  oom_kill 1
  oom_group_kill 0
```

This directly records a memory kill in this attempt, not merely a connection
cutoff. The container's idle main process survived, allowing final counters to
be collected; `State.Running=true` does not negate the recorded OOM of a process
inside it.

## What ran and what remains unknown

The Go event stream showed root-package, lint, metamorphic, record, SSTable and
WAL test activity. A one-worker package schedule is not the same workload as the
[successful isolated valblk compilation](deepswe-pebble-valblk-compile-2026-10-10.md).
It includes executing tests and accumulating caches and scratch data.
Also, `-p 1` does not serialize every goroutine or test-internal subprocess.

There were 36 resource samples, no probe timeouts, and a largest UTC sample gap
of 10.56 seconds. The first sampled OOM appeared at 350.59 seconds after container
start; the preceding 340.28-second sample still had zero OOM counters.
The initial sampler response was 1 because logs/cache were not yet present.
The shared scratch probe's unused `/tmp/compile-work` check also emits a
missing-directory warning, unrelated to test failure or connection loss.

Only a bounded last 1 MiB of the Go JSON event stream was retained. It does not
identify the killed process or exact test. Unlike the earlier default-concurrency
attempt, this attempt's saved stderr does not identify a killed linker; it is
empty. We therefore should not assume the same victim or blame a specific
SSTable test from timing alone.

No inventory was accepted. The runner deliberately does not parse or copy a
report after Docker has reported an OOM. The recorded zero accepted test cases
does **not** mean that no tests ran. No full event stream or raw CTRF report was
saved from this attempt; the compact tail cannot reconstruct the complete run.

## Limits, status and next step

Live inspection confirmed the unchanged original protections: 8 GiB RAM/no
extra swap, two CPUs, 2,048 PIDs, 4 GiB tmpfs, no network, read-only root, all
capabilities dropped, no-new-privileges, no privileged mode, no host bind mounts,
no added hosts and no published ports. No host power settings were changed.
The owned container and temporary checkout were cleaned up afterward.

The helper checks passed **11 host tests**. The permanent public-test
configuration and official survey were not changed. Readiness remains
**108/113**, with Pebble still unready. No automatic retry started.

The next useful investigation is to identify the memory-heavy package/process
using targeted instrumentation. This result does not justify calling Pebble
ready, increasing its canonical memory limit, dropping tests, or repeating the
same full attempt without a new diagnostic question.

[Compact evidence](../experiments/deepswe/pebble_full_single_worker_2026_10_10.json)
records pins, observed protections, final Docker state and artifact hashes.
The raw resource journal and final cgroup probe remain in the referenced output
directory. `tools/run_pebble_schedule_diagnostic.py` reproduces one fresh
diagnostic; it is separate from the normal survey and workflow runners.
