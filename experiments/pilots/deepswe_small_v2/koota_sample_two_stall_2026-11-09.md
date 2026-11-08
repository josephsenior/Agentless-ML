# Why Koota sample two stalls

The stall is an infinite loop in Koota's existing query code. Sample two's
registration strategy triggers it. The same defect reproduces on the pinned
base revision without the candidate patch, so this inspection establishes no
Agentless-ML runner bug.

## What happens

The patch keeps every created aspect in a module-level `Set`. World reset removes
subscriptions, then reinstalls retained aspects. Each aspect needs a backing
trait. As the issue suite creates more aspects, later tests register more backing
traits even after resetting the world.

The test `Aspect > Changed modifier > should not match unchanged entities`
reaches 31 registered traits and queries a mask of `1073741824` (`2**30`).
Koota scans that mask with this loop, already present at line 372 of the base
revision's `packages/core/src/query/query.ts`:

```ts
for (let bit = 1; bit <= mask; bit <<= 1) {
```

After the counter reaches `1073741824`, JavaScript's signed bit shift makes it
`-2147483648`, then `0`. Both satisfy `bit <= mask`; shifting zero keeps it zero.
The loop keeps running. This explains sustained CPU activity with low memory use
and why a longer timeout would not resolve this execution path.

## Checks performed

All diagnostics used the same pinned image, two CPUs, 8 GiB and no networking.
They made zero model calls. They did not update the official prediction or score.

- A 75-second run with test-start/end logging stopped at the unchanged-entity
  tracking test, matching the full verifier's hang.
- A disposable source copy added a tripwire that throws when `bit <= 0`.
  It captured `bit=-2147483648`, `mask=1073741824`, `worldTraits=31` at that test.
- The exact saved candidate passed that test when run alone: 1 passed, 50 filtered
  skips. This supports the accumulated-registration trigger.
- A synthetic test on base commit
  `9c434858b2b522002f8c5eb4a554fa8836a7cf3c`, without applying the candidate,
  registered 29 filler traits plus the target trait (and the world's existing
  excluded trait). A Changed query hit the same tripwire and values. This
  independently reproduces the underlying base-code defect.

With the tripwire, the issue suite finished in under a second of Vitest time:
49 tests passed and two failed. One failure is the intentional tripwire; the
other is `should work with Or modifier alongside aspect`, where a query returned
an empty result despite a matching entity. These are diagnostic observations,
not a replacement score. The official saved-patch result remains the 30-minute
timeout. The original selected sample zero remains at 5/51 issue checks.

## What this means for the experiment

There is no Agentless-ML implementation fix established by this stall. The
underlying loop defect belongs to the benchmark repository, and the generated
patch exposes it. We should retain the timeout and leave the exported patch
unchanged. A manual repair based on these held-out tests would not be a valid
Agentless prediction. The separate Or failure also prevents claiming that an
overflow fix alone would solve the task.

Next, spend the next authorized model attempt on a fresh task rather than repeat
this identical Koota patch. Review any selection-policy change separately using
public validation signals.

[Structured evidence](koota_sample_two_stall_2026-11-09.json),
[progress log](koota_sample_two_stall_2026-11-09/test-progress.txt),
[tripwire log](koota_sample_two_stall_2026-11-09/tripwire-output.txt),
[isolated test log](koota_sample_two_stall_2026-11-09/isolated-output.txt), and
[independent base reproduction](koota_sample_two_stall_2026-11-09/base-overflow-output.txt).
Diagnostic drivers are stored beside the logs. They use temporary containers,
add diagnostic setup/source instrumentation as described, and delete those
containers after execution. Local originals are under
`artifacts/koota-sample-two-stall-2026-11-09`.
