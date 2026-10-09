# KGateway: five-minute single-worker compile check

The short check reached its planned cutoff without a space error. The highest
sampled scratch use was **1.88 GiB of 4 GiB**. That is encouraging, but the full
package graph did not finish compiling, so KGateway is still unready.

## What ran

We used the same pinned repository and image as the
[space inspection](deepswe-kgateway-space-review-2026-10-09.md), with the same
8-GiB memory, two CPUs, 4-GiB scratch and 2,048-PID limits. Networking remained
off, the root filesystem read-only, capabilities dropped and no-new-privileges
enabled. No image was built or cache seeded.

```sh
GOCACHE=/tmp/go-build GOTMPDIR=/tmp/compile-work \
  timeout --signal=TERM --kill-after=10s 300s \
  go test -c -p 1 -o /dev/null ./...
```

`-p 1` allows one Go build program at a time; it does not restrict the compiler
to one OS thread. `-c` compiles without running test binaries, initialization or
`TestMain`. The pinned Go version supports `/dev/null` for multiple packages,
avoiding output-name collisions and discarding the final binaries. All packages
remain targeted. `GOTMPDIR` only moves temporary build work into a named directory
on the same capped mount so we can measure it separately.

This is compile-only, not a full baseline or a controlled concurrency-only
comparison: test execution and retained final binary outputs also differ from
the previous run. There is no accepted test report or regression inventory.

## Observations

The inner timeout returned **124**, as expected for the five-minute cutoff.
The generic runner records this as `harness_error`; here it means the diagnostic
window ended, not that a new setup failure was found. Total runner duration,
including setup and artifact handling, was 351.3 seconds. Stderr was empty.

The resource journal contains 28 samples, from 0.45 to 281.43 seconds after
sampling started. The first probe preceded workspace preparation and returned
1; the other 27 returned 0. The highest sampled values were:

- Scratch used: **2,014,183,424 bytes (1.88 GiB)**, about 47% of the mount.
- Build cache: **941,528 KiB**, about 919 MiB.
- Temporary compile work: **1,005,152 KiB**, about 982 MiB.
- Candidate checkout: **20,292 KiB**, about 20 MiB.
- Cgroup memory peak reported by the last probe: **2,632,216,576 bytes (2.45 GiB)**.

Sampled memory events showed no OOM or OOM kill. No `no space left on device`
message appeared. These are observations through the last probe, not a captured
final peak: sampling did not cover the entire remaining interval to cutoff.
Scratch usage was still growing. The old failed run has no comparable resource
journal, so we cannot quantify a reduction in peak space or claim the complete
build fits based on this partial run.

## Next decision

A single full compile-only attempt, keeping one build worker and the original
30-minute outer cap, would answer whether compilation can finish under these
limits. It has **not** been started. Only after a complete compile should we
consider a fresh full public baseline; test execution adds work this check did
not exercise. No automatic retry or official survey update was made; canonical
readiness remains **100/113**.

Raw evidence:
`../output/deepswe-survey/kgateway-compile-diagnostic/logs/agentless-ml-0732393284c94b80b01190d3d14c431a/`.
This contains `compile-diagnostic.json`, `resource-samples.jsonl`, `execution.json`
and stdout/stderr logs. The owned container and temporary workspace were removed
by the normal runner. No held-out tests or solutions were read.
