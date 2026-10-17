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
