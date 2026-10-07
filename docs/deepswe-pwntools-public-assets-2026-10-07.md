# Pwntools public dependency audit — 7 October 2026

The files needed for a genuine offline-data diagnostic are available. We
downloaded and inspected **25 distinct library binaries**, **24 symbol
metadata files**, **two matching debug files**, the current Debian libc/loader
package, and the `elfutils`/`libasm1` package archives. Every checked binary
matched its recorded identifiers/checksums. No image was built and none of the
downloaded binaries was executed.

The important finding is that the original endpoints are not all sufficient.
The older libc comes from the GitLab fallback, and both debug files must come
from publisher archives rather than the configured debuginfod services.
Those services returned 404 for all six requests we tried. That does not mean
the files are unavailable elsewhere: we found the exact matching archive
members, not substitutes from a newer release.

## What was verified

| Dependency | Availability and verification |
| --- | --- |
| Five libraries used by literal hash/library-ID lookups | Four resolved through `libc.rip`; the older library resolved through GitLab. All requested hashes and build IDs matched real bytes. |
| Complete symbol-query snapshot | Both public queries returned ten entries. All twenty libraries and symbol files were checked; the returned ID order is recorded. |
| Two debug files | Exact GNU build IDs matched the required libraries. Their containing Ubuntu packages matched publisher SHA-256 values. |
| Current libc/loader package | Debian's package SHA-256 matched APT-authenticated metadata. Its libc bytes and build ID match the current diagnostic image. |
| Debug-merging tool dependencies | `elfutils` and `libasm1` version `0.188-2.1` archives match APT-authenticated Debian SHA-256 values. They were not installed. |

The twenty symbol-query libraries are additional to the five literal-lookup
libraries. Twenty-four symbol files were available from `libc.rip`; the old
GitLab library is needed for hash lookup, not either symbol-offset query.
The deliberately invalid `XX` examples do not require a dependency file.

This is a frozen observation of the public service, not a promise that its
future result ordering or membership will remain unchanged. The upstream
[libc-database documentation](https://github.com/niklasb/libc-database)
describes the local database format and web service. Our inventory records
the actual responses, bytes and identifiers checked today, rather than
assuming a newly downloaded database will reproduce them.

## The fallback assets

The library with build ID
`fe136e485814fee2268cf19e5c124ed0f73f4400` has no current `libc.rip` result.
Following GitLab's public relative link retrieves the original ELF file.
Its SHA-256 is
`5e877a8272da934812d2d1f9ee94f73c77c790cbc5d8251f5322389fc9667f21`,
exactly the value in the public example. Its MD5, SHA-1 and build ID also
match the corresponding examples. The extracted `read` symbol remains
`0xda260`; no expected offset was changed.

For build ID `69389d485a9793dbe873f0ea2c93e02efaa9aa3d`, Launchpad still
provides `libc6-dbg_2.35-0ubuntu3.1_amd64.deb`. The current Ubuntu pool URL
returned 404, but the publisher's historical package index is available
through Ubuntu's snapshot service. Its SHA-256 matches the downloaded
Launchpad archive:
`76884b5e6b5a911cbfd9d9d71653f94454d438881f9fc6d63d388623bd58cf36`.
The exact build-ID debug member is present, including `main_arena=0x219c80`
as required by the public example.

For build ID `d1704d25fbbb72fa95d517b883131828c0883fe9`, Ubuntu's old-releases
archive provides `libc6-dbg_2.36-0ubuntu4_amd64.deb`. The SHA-256 matches its
Kinetic package index:
`c6128653f0d9688e05741a6c67c9c644f276e91f49f1fe77171be12a57f78391`.
Its matching debug member is present and contains `main_arena`.

Exact URLs, downloaded-byte hashes, package-index checksums and archive member
names are in the [asset inventory](../experiments/deepswe/pwntools/public-assets.json).

## What the checksum claims mean

Downloaded libraries were checked against service-provided MD5, SHA-1 and
SHA-256 values and their GNU build IDs. The two SHA-256 examples additionally
provide independent expected content pins in the pinned public source.
GitLab's old library matched all four corresponding public identifiers.
Symbol files matched the API's published symbol values, with no missing
required fields; their own SHA-256 values are measured content pins.

The Ubuntu debug archives matched SHA-256 values from publisher package
indexes fetched over HTTPS. We did **not** verify those indexes' OpenPGP
Release signatures. Debian package checksums came from APT-authenticated
metadata. A build ID alone is not cryptographic authentication, and computing
a SHA-256 alone is not the same as checking a publisher's checksum. The
inventory keeps these distinctions explicit.

The current Debian package also contains the matching loader and package
copyright notice. A broader redistribution review is separate from this
availability/checksum audit; no bundled image was published.

## How the checks were kept separate from the benchmark

The verifier used network access on the host to retrieve public files. It
sent ELF bytes to a fixed parser in the existing immutable diagnostic image,
with network disabled, a read-only root, all capabilities dropped and no new
privileges. There were no host mounts, credential mounts or Docker socket
mounts in those inspection containers. No downloaded library, package
maintainer script or debug file was executed or installed.

Archives were inspected as data, without extracting arbitrary paths onto the
host. URL origins and redirects are restricted to explicit public HTTPS
hosts, responses have size limits, and each run uses a new artifact directory.
Successful process exit means the audit finished; inspect individual records
for unavailable endpoints or failed checks, rather than treating exit zero
as proof that every original URL works.

Raw downloads, API replies and publisher indexes occupy about **93 MB** under
`../output/deepswe-survey/pwntools-public-assets-2026-10-07/`. Only the
inventory and verifier are committed. All stored byte hashes must be checked
again before those files are reused.

## Reproduction and next step

Run [the verifier](../tools/verify_pwntools_public_assets.py) from the repo root:

```powershell
.\.venv\Scripts\python.exe tools/verify_pwntools_public_assets.py
```

It prints the path of the new `verification.json`. Use that path for the two
additional checks, which also create separate evidence directories:

```powershell
.\.venv\Scripts\python.exe tools/verify_pwntools_public_assets.py --supplement <initial-verification.json>
.\.venv\Scripts\python.exe tools/verify_pwntools_public_assets.py --supplement <initial-verification.json> --complete-symbol-data
.\.venv\Scripts\python.exe tools/verify_pwntools_public_assets.py --tool-archives
```

The next implementation can use these verified files in a **separate offline
diagnostic image**: install pinned merging tools, supply genuine local
database metadata, and populate writable package/debug caches from the
verified archives. Preserve the original test expectations, container
restrictions and three documented schedule exclusions. Then rerun the public
schedule; file availability is not proof that all examples pass.

The framework suite passed **629 tests**, with **29 skipped**. The verifier's
nine local safety/integrity checks passed. No model calls or held-out task
files were involved. The previous public result stays **44/10**, and canonical
readiness stays **92/113**.
