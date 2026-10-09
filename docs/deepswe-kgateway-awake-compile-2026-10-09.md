# KGateway: uninterrupted single-worker compile repeat

The one approved repeat ended with **exit 1 and package build failures**, not
a timeout, after 317.9 seconds of runner time including setup. Reducing build
concurrency to one did not produce a successful cold compile under our limits.

Windows accepted a temporary `SetThreadExecutionState` system-awake request
before workspace setup. The request was released after cleanup; no persistent
power-plan or screen setting was changed. This prevents automatic idle sleep,
not deliberate suspension or every possible host interruption. Unlike the
[previous attempt](deepswe-kgateway-full-compile-2026-10-09.md), this resource
journal has no long monitoring gap: 28 samples span 0.32 to 277.88 seconds,
with a maximum interval of 10.33 seconds.

The same pinned image, sealed base, fresh cold cache and full package graph
were used. The command remained `go test -c -p 1 -o /dev/null ./...`, with
`GOCACHE=/tmp/go-build` and `GOTMPDIR=/tmp/compile-work`. The outer cap stayed
1,800 seconds; memory stayed 8 GiB, CPUs two, scratch 4 GiB and PIDs 2,048.
Networking remained off and Docker protections unchanged. No tests executed.

## Space evidence and its limit

The last probe, also the highest sampled scratch reading, recorded:

- Scratch used: **4,205,412,352 bytes (3.92 GiB)**, 98% of 4 GiB.
- Scratch available: **89,554,944 bytes**, about 85 MiB.
- Build cache: **2,015,960 KiB**; temporary compile work: **2,071,952 KiB**.
- Checkout: **20,292 KiB**.
- Cgroup memory peak: **5,065,572,352 bytes (4.72 GiB)**, with no observed
  OOM or OOM-kill events.

The saved stdout contains many `[build failed]` lines and ends abruptly at
exactly 4,096 bytes. Saved stderr is empty. Neither saved logs nor resource
probes contain the compiler's underlying error message. Exhausted scratch
preventing further log writes is a plausible explanation for this pattern,
but is not directly proven by the retained artifacts. The container was removed
by normal cleanup, so final allocation and missing messages cannot be recovered.

The combination of near-full scratch, increasing compile/cache allocation,
build failure and the original run's explicit ENOSPC is **strongly consistent
with the same space blocker**. It is not a new directly observed ENOSPC message,
a measured final peak, or proof that another compile problem is impossible.
The generic runner's `fail` classification is a compile-command outcome, not
an accepted test failure inventory or evidence about a candidate repair.

## Decision

KGateway remains unready. No baseline, accepted regression inventory, image
change, official survey update or further retry was made; canonical readiness
stays **100/113**. A one-worker cold build is not a demonstrated fix. Park this
task under the current limits; any different scratch/cache condition should be
assessed and explicitly approved separately. Another attempt should also retain
diagnostic errors outside the constrained mount, rather than relying entirely
on files that may stop growing when scratch fills.

Raw artifacts:
`../output/deepswe-survey/kgateway-compile-diagnostic/logs/agentless-ml-f3b8b542de6349d785d5279b7840c168/`.
No held-out tests or solutions were read. Five focused host unit tests passed
before launch, including keep-awake release on exceptions and refusal to start
when Windows rejects the request.
