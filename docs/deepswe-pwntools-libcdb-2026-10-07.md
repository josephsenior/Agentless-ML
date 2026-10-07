# Pwntools libcdb data requirements — 7 October 2026

Ordinary offline library lookup works. The public `libcdb` examples fail
because they need specific library data that is not in this image, and some
also need debug tooling. Installing another generic libc package would not
provide all of that data.

We confirmed this against the pinned task in the existing RISC-V/patchelf
image. Five authored diagnostic cases passed, with networking disabled and
the normal container restrictions unchanged. They are controls and
reproductions, not five repaired public tests. The broader schedule was not
rerun: its last result remains **44 passing / 10 failing groups**, including
21 failed examples out of 42 in `libcdb`. Canonical readiness stays **92/113**.

## What is available locally

The installed system library is `/usr/lib/x86_64-linux-gnu/libc.so.6`, with
build ID `93ac61ec5a8eb1396f9fbd350e3169a558528a40`. Looking up that build ID
with `offline_only=True, unstrip=False` succeeds and produces the exact same
bytes. This confirms that cache creation and local-system matching work.

We also copied those existing bytes into an authored temporary database.
The real local-database provider matched them by build ID, and the public
lookup API found them by the control's library ID. No historical public
fixtures or expected symbol offsets were invented for this control.

The default `/var/lib/libc-database` does not exist in the image. The public
example's build ID `2d1c5e0b85cb06ff47fa6fa088ec22cb6e06074e` therefore has no
local match. An offline lookup returns `None`, then creates an empty negative
cache entry. The pinned implementation suppresses retries against that cache
for seven days. Our disposable containers have fresh temporary filesystems,
so this does not establish a stale-cache problem across separate runs.

## The public examples need three kinds of data

**Specific libc binaries and search metadata.** Hash examples ask for
historical binaries, not merely whichever libc the OS currently uses.
Symbol-offset search additionally needs a populated database's `.symbols`
and `.url` files. The code can use local metadata, but that database is absent.
The probe's inventory records the literal public hash/library-ID requests;
the deliberate `XX` no-match examples are not required fixtures.

**Matching library/loader packages.** `download_libraries()` takes the local
libc's build ID, queries `libc.rip` for a matching distribution archive, then
downloads and extracts it. It can also try an Ubuntu package URL for an
Ubuntu libc. Having the runtime libc and loader installed does not populate
this separate package cache. Even with `unstrip=False`, our real call returned
`None` after the API's DNS request failed under network isolation. The later
`os.path.join(None, ...)` exceptions are consequences of that missing result.

**Debug symbols and a merging tool.** `eu-unstrip` is absent. The source also
needs matching debuginfo, either already cached or obtained from its
debuginfod servers. Adding `elfutils` supplies the tool, not the historical
libraries or their debug files. Turning debug processing off would change
what the public examples test, so we did not do that to the public schedule.

These are observed requirements, not proof that the remote services still
provide every requested asset. We did not enable online lookup or test
remote availability in this investigation.

## An upstream offline-flag caveat

The pinned `search_by_hash()` aliases `PROVIDERS['offline']`, then uses `+=`
to append online providers during a default lookup. That changes the original
list. We confirmed that a successful local lookup alone expands it from two
providers to four, before an online request is needed. A later
`offline_only=True` call can consequently include online providers too.

There is a second, separate scope issue visible in the source:
`offline_only` selects hash providers, while `unstrip=True` can invoke the
debug downloader independently. Our offline lookup controls explicitly used
`unstrip=False`; they do not validate debug processing.

Neither issue bypasses Docker's `--network=none`. We kept that actual network
boundary, did not patch the pinned library, and reset module state only
between the authored diagnostic cases so their observations were independent.

## What to do next

Prepare a public-data inventory before building another image: identify
exact library binaries, search metadata, matching package archives and debug
files; record their provenance, checksums and redistribution terms. Verify
availability rather than assuming a generic package or a database clone will
satisfy every example. Any prepared snapshot should live in a separate
diagnostic image and be copied into disposable writable caches where needed.
The `_check_elf_cache` example explicitly deletes one cache entry, so merely
preloading lookup-cache files is not enough.

Do not fabricate online responses, seed arbitrary ELF files under requested
hash names, rewrite expected offsets, or read held-out task files. The
current failures should remain visible until genuine public dependencies
are available and the unchanged examples are rerun.

## Evidence and reproduction

The [inventory](../experiments/deepswe/pwntools_libcdb_2026_10_07.json) records
observations, literal public requests and execution/log hashes. The
[opt-in fixture](../tests/test_pwntools_libcdb_diagnostics.py) reproduces the
checks in a disposable checkout:

```powershell
$env:AGENTLESS_PWNTOOLS_LIBCDB_IMAGE = 'agentless-ml/pwntools-riscv:2026-10-07'
$env:AGENTLESS_PWNTOOLS_LIBCDB_ARTIFACTS = 'C:/Users/GIGABYTE/Desktop/Agentless-ML/output/deepswe-survey/pwntools-libcdb-diagnosis-local'
.\.venv\Scripts\python.exe -m pytest tests/test_pwntools_libcdb_diagnostics.py -q
Remove-Item Env:AGENTLESS_PWNTOOLS_LIBCDB_IMAGE
Remove-Item Env:AGENTLESS_PWNTOOLS_LIBCDB_ARTIFACTS
```

The live host check passed, including all five container cases. Focused
normal checks passed **10 tests**, with **5 opt-in checks skipped**. The full
framework suite was not rerun for this diagnostic-only addition. No image,
runner, existing public test or exclusion was changed; no model calls,
historical-data downloads or held-out-file access occurred.
