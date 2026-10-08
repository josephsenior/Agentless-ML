# Cliffy: verified public dependency files

The eight declared packages missing from Cliffy's image are available from
the public JSR registry. Their complete package manifests contain **210 files**;
every downloaded file matched both the registry's SHA256 and its declared
byte count. No GitHub token or other authentication was used.

The audit also followed the external dependencies recorded in package metadata
and checked complete package contents at the versions already observed in the
image. In total, **28 package/version pairs and 956 files** were verified. The
original image cache was not changed, no image was built and no tests were run.

## Which versions were checked

For the eight absent root packages, the explicit candidate pins are the lower
bounds declared by the sealed repository's import map. This avoids silently
choosing today's latest release, but it does not recover the benchmark's
unknown historical resolutions: its root configuration disables locking.

| Package | Declared range | Verified candidate pin | Files |
| --- | --- | --- | --- |
| `@c4spar/mock-command` | `^1.0.1` | `1.0.1` | 6 |
| `@c4spar/mock-fetch` | `^1.0.0` | `1.0.0` | 6 |
| `@std/async` | `^1.1.1` | `1.1.1` | 33 |
| `@std/cli` | `^1.0.27` | `1.0.27` | 31 |
| `@std/datetime` | `~0.225.7` | `0.225.7` | 18 |
| `@std/http` | `^1.0.24` | `1.0.24` | 36 |
| `@std/io` | `~0.225.3` | `0.225.3` | 25 |
| `@std/semver` | `^1.0.8` | `1.0.8` | 55 |

The additional graph pins are assert 1.0.2 and 0.225.2, bytes 1.0.6, html 1.0.5,
media-types 1.1.0, net 1.0.6, streams 1.0.17, internal 0.225.1, data-structures
1.1.0, regexp 1.0.2 and async 1.4.0. Older assert/internal versions are needed
by the two mock-library graphs; the existing newer versions must remain.
Data-structures and async 1.4.0 also cover dependencies recorded for the image's
cached testing 1.0.19. That testing version is not the root's exact 1.0.0 pin;
auditing its metadata does not mean the public schedule necessarily uses it.

Nine existing package/version pairs were verified without upgrading them:
assert 1.0.19, encoding 1.0.10, fmt 1.0.10, fs 1.0.24, path 1.1.5, testing 1.0.0
and 1.0.19, text 1.0.19 and internal 1.0.14. The full-package audit is broader
than a proof of only the imports used by the test suite. It includes files and
dependency records that may never be used by that schedule.

## What the checksums establish

The [JSR registry API](https://jsr.io/docs/api) serves immutable version metadata
with per-file sizes and SHA256 checksums. The audit fetched the package index,
checked that each selected version exists and is not yanked, downloaded the
version metadata, then checked every file against its manifest entry.

Source checksums match the registry-published values. The SHA256 pins for the
metadata responses are locally measured snapshots, not additional publisher
signatures. Package-wide `meta.json` is mutable; its response is pinned as an
audit artifact rather than treated as an immutable version record.

Exact URLs, versions, metadata hashes, file hashes, sizes and saved artifact
locations are in
[`public_dependencies_2026_10_09.json`](../experiments/deepswe/cliffy/public_dependencies_2026_10_09.json).
Its assembly step rechecked the saved bytes and rejects incomplete audits,
modified files, missing pin sets or artifact paths outside the audit directory.
The downloaded bytes remain outside Git under
`../output/deepswe-survey/cliffy-public-dependencies-2026-10-09/`.

```powershell
.\.venv\Scripts\python.exe tools/verify_cliffy_public_dependencies.py
.\.venv\Scripts\python.exe tools/verify_cliffy_public_dependencies.py --transitives
.\.venv\Scripts\python.exe tools/verify_cliffy_public_dependencies.py --preserved-cache
.\.venv\Scripts\python.exe tools/verify_cliffy_public_dependencies.py --assemble-manifest
```

Acquisition uses anonymous HTTPS registry reads, not Docker test-time networking.
Previously saved source blobs are reusable only if they still match the
registry checksum and size; registry metadata is fetched again during an audit.
The assembly-only mode makes no network requests. Thirteen focused tests passed,
including checksum/size mismatches, unsafe paths, yanked versions and changed
saved artifacts. The first path-guard test exposed double-slash handling; that
guard was corrected before the final suite and manifest assembly.

## What is still unproven

This is a verified artifact set, **not a Deno resolution lock or a passing
baseline**. Deno 2.0.0 compatibility, actual resolution of every version range,
export/subpath coverage and complete candidate test-import graph remain
unverified. Existing npm dependencies have not been independently audited.
Adding files to a cache alone does not force Deno to resolve the candidate
versions listed above; the later preparation must record the versions it
actually selects and avoid hidden upgrades.

The next step is a separately labelled cache-supplemented image, using these
verified bytes and the exact published parent. Preserve candidate source,
tests, Deno binary, runtime offline policy and resource limits. Verify the
complete import graph offline before attempting the public test schedule;
do not disable checking or prune tests to get through another missing import.
If that graph reveals another dependency, audit it rather than fetch it during
tests. No build or test attempt has been started in this verification step.

Canonical readiness remains **100/113**. Cliffy remains unready; Numba remains
parked. Any later substituted-image results must stay separate from the
canonical pinned-image survey.
