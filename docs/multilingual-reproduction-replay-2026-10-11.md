# Recorded multilingual replay — 11 October 2026

All three migrated SWE-bench Pro V2 smoke tasks completed through final
prediction export at implementation revision 5e80f8c. These are hand-written
recorded responses, not model-generated benchmark results.

| Task | Baseline reproduction | Weaker repair | Selected repair |
| --- | --- | --- | --- |
| Go / Vuls | Clean test failure | Regression passed; reproduction failed | repair-2: both passed |
| JavaScript / NodeBB | Clean assertion failure | Regression passed; reproduction failed | repair-2: both passed |
| TypeScript / Tutanota | Clean assertion failure | Regression passed; reproduction failed | repair-2: both passed |

Each run also rejected its malformed repair response. All finished with
infrastructure status ok, zero model calls and a final prediction artifact.
The generated reproduction source is absent from the exported repair patches.

## What stayed fixed

The pinned V1 projection, V2 visible-file corpus, repository base revisions,
image IDs, recorded repair responses and public regression checks were unchanged.
Each execution retained 4 GiB memory, one CPU, 4 GiB scratch and the 2,048-process
cap. Go commands retained their 600-second cap; Node commands retained 60 seconds.
The existing offline Docker runner and protections were used without changes.
There were no retries, downloads, host changes or held-out verifier runs.

JavaScript ran first. Go and TypeScript overlapped after a host-memory check
showed roughly 16 GiB free, comfortably above their combined 8 GiB caps.
These wall times are workflow evidence, not a controlled performance comparison.

## Evidence

The [committed replay summary](../experiments/swe_bench_pro/reporting_replay_2026-10-11.json)
records the run IDs, revisions, image IDs, patch digests, candidate outcomes and
reproduction report hashes. Every reproduction report was nonempty and contained
only passed or failed cases. Go's report embeds the raw JSONL test events. The
JavaScript and TypeScript reports contain normalized CTRF results; their stdout
and stderr remain in the execution logs.

Raw reports, stdout/stderr, controller records and predictions remain locally
under artifacts/reproduction-replay-20261011, in separate language/run directories
listed in that summary. They are ignored by Git; historical runs were not replaced.

The existing language runners accept the same five path arguments described in
[SWE-bench Pro integration](swe-bench-pro.md). Use fresh workspace and artifact
roots when repeating these checks.

This verifies the reporting migration in the real recorded workflow, including
baseline eligibility, regression filtering, candidate reproduction and selection.
It does not establish model repair quality, semantic validity on other tasks,
full repository-suite coverage or an official V2 score. DeepSWE readiness remains
109/113.

Next: add Rust reproduction reporting to cover the remaining supported language.
