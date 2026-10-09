# Cliffy: full offline public schedule

One approved full attempt against the exact cache-supplemented image finished
successfully: native exit **0**, no reported failures or skips. Deno's summary
is **822 tests passed, 76 steps passed**, in about 38 seconds of native test
time. Host execution including preparation and checking took **58.8 seconds**.

This is a completed baseline in the labelled supplemented environment, not a
canonical published-image readiness update. The official survey remains
**100/113**. Numba remains parked.

## Exactly what ran

- Candidate base: `132a437c40cffbdfbe474ca808c8debde59e2633`.
- Image: `sha256:9e49eb0e15b12e2fbded70acbcb9a4f0948bbdbc731539299e0e99bd68ff27c9`.
- Original Deno 2.0.0, existing public Deno command and default full discovery.
- Networking disabled, root read-only, capabilities dropped, no-new-privileges,
  8-GiB memory, two CPUs, 4-GiB tmpfs and the 2,048 PID limit.
- Existing 1,800-second host timeout. No automatic retries, selectors,
  exclusions, source edits or changed assertions.

The same fresh candidate setup used by the graph check ran the exact existing
`DENO.command((), timeout_seconds=1800)`. The no-run flag was removed by selecting
the original command, not by replacing the schedule. The image had already
passed native discovery/type checking for all 119 discovered modules.

The command copies `/deno-cache` to writable `/tmp/deno-cache`, then runs:

```sh
deno test --cached-only --allow-run=deno --allow-env --allow-read --allow-write=./ --parallel --junit-path=/tmp/report.xml
```

`--run-tests` is opt-in in `tools/check_cliffy_offline_graph.py`; its default
remains a no-run graph check. Full mode refuses an image without the recorded
successful graph check, preserves the report declaration and records the
result outside the official survey. Seventeen focused tests passed, including
exact equality of this full command to the existing public command.

## Three counts, not three different results

| Observation | Count |
| --- | --- |
| Native summary | 822 tests + 76 steps passed |
| Raw JUnit testcase entries | 898 passed |
| Normalized regression IDs | 878 passed |

The XML itself declares 898 tests and contains 898 testcase elements, with
zero failure, error or skipped children. The existing report normalizer merges
identical `(classname, name)` IDs, retaining the worst outcome when labels
repeat. This reduces the inventory to 878 unique IDs; it does not mean twenty
tests were excluded from execution.

Deno assigns many cases to the shared public runtime wrapper
`./internal/testing/test/runtime/deno.ts`, so duplicate labels are a report
identity limitation. Raw XML and command logs are retained. Do not describe
the normalized inventory as 898 independently addressable regression IDs,
or silently invent file namespaces without evidence. A future comparison
should retain this conservative duplicate policy consistently, or explicitly
validate a more precise report-ID mapping before changing it.

An early observational probe saw a 689,209,344-byte cgroup memory peak, no OOM
events and about 39 MB used in `/tmp`. This was not continuous monitoring and
is not claimed as the final peak. The completed execution had no timeout, OOM
or harness-error classification. The owned container and candidate clone were
cleaned up normally; no retry followed completion.

## Evidence and reproduction

Evidence directory:
`../output/deepswe-survey/cliffy-cache/logs/agentless-ml-2d44f5e33a9e4534a8f8cfffa1543628/`.
It retains `execution.json`, `public-schedule.json`, the raw `report.xml`,
`stdout.log` and `stderr.log`. The compact committed observation is
`experiments/deepswe/cliffy_public_baseline_2026_10_09.json`.

```powershell
.\.venv\Scripts\python.exe tools/check_cliffy_offline_graph.py --image-id sha256:9e49eb0e15b12e2fbded70acbcb9a4f0948bbdbc731539299e0e99bd68ff27c9 --run-tests
```

Cliffy's setup blocker is resolved for this labelled environment. Its image
substitution and curated dependency availability must remain explicit in any
later experimental protocol; the published image and corpus pin have not been
replaced. Next setup review: KGateway's temporary build-space failure.

Follow-up: the approved [registration and official survey refresh](deepswe-cliffy-registered-readiness-2026-10-10.md)
completed after rechecking the pinned image and dependency artifacts. Cliffy
is now ready in its explicitly labelled cache environment; overall readiness
is 102/113. This earlier diagnostic record and original corpus pin are unchanged.
