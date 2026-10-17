# Recorded multilingual replay — 11 October 2026

> Development record. See [the documentation guide](../README.md) for current status.

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

The [committed replay summary](../../experiments/swe_bench_pro/reporting_replay_2026-10-11.json)
records the run IDs, revisions, image IDs, patch digests, candidate outcomes and
reproduction report hashes. Every reproduction report was nonempty and contained
only passed or failed cases. Go's report embeds the raw JSONL test events. The
JavaScript and TypeScript reports contain normalized CTRF results; their stdout
and stderr remain in the execution logs.

Raw reports, stdout/stderr, controller records and predictions remain locally
under artifacts/reproduction-replay-20261011, in separate language/run directories
listed in that summary. They are ignored by Git; historical runs were not replaced.

The Python qutebrowser replay was completed later the same day. It used the same
pinned V2 corpus and image, but a different task and a later implementation
revision. Its saved evidence is in
[`python_reproduction_replay_2026-10-11.json`](../../experiments/swe_bench_pro/python_reproduction_replay_2026-10-11.json).
The baseline reproduction failed, the compile-only regression check passed,
`repair-1` passed compilation but failed reproduction, and `repair-2` passed
both and was selected. This check made zero model calls; its selected patch was
subsequently resolved by the pinned local V2 verifier. Its full recorded run is under
`artifacts/python-qutebrowser-v2-reproduction-20261011/controller-pinned/`.

Together these give real-task reproduction coverage for Python, Go, JavaScript
and TypeScript in SWE-bench Pro V2. Rust has a separate real-task DeepSWE
reproduction-and-regression run ([record](../../experiments/reproduction/fd_combined_validation_2026-10-11.json)).
These are still manually recorded workflow checks, not model-generated results;
the language rows also differ in task, regression breadth and implementation
revision, so they are not a controlled comparison.

These runs verify baseline eligibility, regression filtering, candidate
reproduction and selection in real task images. They do not establish model
repair quality, generalization to other tasks, full repository-suite coverage or
an official V2 score. The local verifier result is post-selection evidence, not
an official Harbor score. The next substantial gaps are live-model integration
and broader benchmark evaluation. DeepSWE readiness remains 109/113.
