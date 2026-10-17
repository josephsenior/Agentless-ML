# Numba: writable user-cache fallback

The previous complete baseline had four nonpassing cache tests because its
user-wide cache resolved to `/root/.cache/numba` on the read-only image.
Numba's pinned `numba/misc/appdirs.py` supports `XDG_CACHE_HOME`, so the shared
Numba public command now sets it to `/tmp/numba-user-cache` and creates that
directory before building the candidate extensions.

This changes the user-wide fallback location. It does not force
`NUMBA_CACHE_DIR`, replace source-local caches, or modify the public tests.
The temporary cache belongs to the disposable candidate container.

All four previously nonpassing public cases passed in a focused Docker run:

- `numba.tests.test_caching.TestCache.test_frozen`
- `numba.tests.test_caching.TestCache.test_non_creatable_pycache`
- `numba.tests.test_caching.TestCache.test_non_writable_pycache`
- `numba.tests.test_caching.TestCacheZip.test_zip_caching`

The command exited 0 and retained four individual results under
`../output/deepswe-survey/2026-10-17-numba-cache-check/logs/agentless-ml-1200ab55921d40a19c6302e27f0712ea/`.
Five focused framework checks also passed. The image, base revision, candidate
extension build, 8-GiB limit, two CPUs, disk scratch and offline networking
remain those of the [previous complete attempt](deepswe-numba-three-hour-attempt-2026-10-17.md).

The user approved one complete rerun with this correction and a three-hour
cap. Its output directory is
`../output/deepswe-survey/2026-10-17-numba-writable-cache-full/`.
The four-case result is not a claim that the full schedule has passed.

## Complete rerun: passed

The approved full rerun completed on 17 October, from 21:26 to 23:00 Paris
time. It exited **0** and retained **10,609 unique test IDs**, exactly the same
set as the previous full attempt. No IDs were added or lost. The only changed
outcomes were the four cache cases above, all now passing.

| Outcome | Count |
| --- | ---: |
| Passed | 9,991 |
| Failed assertions | 0 |
| Test errors | 0 |
| Native skips | 595 |
| Expected failures | 23 |

The structured report maps expected failures to skipped, retaining 618 skipped
outcomes. The native summary is `OK (skipped=595, expected failures=23)`.
Host execution measured 5,650.91 seconds (about 94 minutes); the native runner
reported 5,919.713 seconds (about 99 minutes). These different clock/scope
measurements are retained rather than treated as one precise runtime.

There were 540 resource samples. The largest observed memory peak was
7,324,282,880 bytes (about 6.82 GiB), within the 8-GiB cap. No sampled OOM events,
OOM kills or swap usage were recorded. The owned container was removed.

The [compact result record](../../experiments/deepswe/numba_writable_cache_baseline_2026_10_17.json)
pins the report, logs and resource journal hashes. This establishes a passing
complete public baseline under the approved longer allowance. It does not
register that allowance for candidate validation: the canonical survey still
has 112/113 registered usable baselines. No further attempt, model call or
held-out verifier was run.
