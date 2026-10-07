# Pwntools: the offline library data fixed the libcdb examples

The separate offline-data image passes **all 42 public libcdb examples**.
The same public Docker schedule now has **45 passing groups and 9 failing
groups**, compared with 44/10 before. Across 3,071 examples, failures fell from
64 to 43. There were no setup or cleanup failures.

This is still a failing diagnostic baseline, not a ready benchmark task.
Canonical readiness remains **92/113**. No held-out files or model responses
were used.

## What changed

The [build helper](../tools/build_pwntools_offline_image.py) uses the
[previously verified pins](../experiments/deepswe/pwntools/public-assets.json).
It checks their bytes again before staging or extracting anything. The new
image adds genuine local library metadata, two matching debug files, the
current libc/loader cache pair, and the two pinned merging-tool packages.

These are dependencies of examples already in the public checkout. We did
not change a doctest, invent a provider response, or relax a permission to
make them pass. Pwntools uses its normal local database and cache paths.
Historical libc binaries are stored as data, not installed over the runtime.
The operating-system libc hash is unchanged.

The image inherits the original SSH bootstrap. A small wrapper copies the
read-only cache seed into writable tmpfs before Python starts. This matters
because Pwntools can delete cache entries and merge debug information into
cached ELF files. The local database and original seed remain read-only.

The package inventory shows only two additions: `elfutils` and `libasm1`, both
`0.188-2.1`, with no upgrades. All build steps ran with networking disabled.
The Ubuntu debug pins retain the audit's trust limit: publisher index hashes
were checked, but Ubuntu Release signatures were not verified.

## What stayed the same

The recorded test command is byte-for-byte identical to the previous RISC-V
run. It uses the same public Docker schedule and the same three exclusions:
`gdb.rst`, `adb.rst`, and `protocols.rst`. No other page was excluded.

Runtime isolation stayed at network-none, read-only root, non-root `travis`,
all capabilities dropped, no-new-privileges, 8 GiB memory, two CPUs, 2,048 PIDs,
and a 4 GiB executable tmpfs. There were no host mounts or published ports.

This schedule is not the separate unexcluded `--full` mode. The original
published image and readiness configuration were left untouched.

## Remaining failures

Only the `libcdb` group's outcome changed. The other groups have exactly the
same example counts and failure counts as before:

| Public group | Failed examples | Existing blocker |
| --- | ---: | --- |
| context | 2 | Proxy/DNS error expectations |
| elf/corefile | 14 | Core capture in this container/WSL environment |
| filesystem | 5 | Home path, permissions and tmpfs block expectations |
| rop/rop | 3 | Core-capture-dependent examples |
| tubes/processes | 2 | ASLR permission and relative-path behavior |
| tubes/sockets | 7 | External network access |
| update | 5 | PyPI access |
| util/proc | 1 | PID-1 ancestry under Docker exec |
| util/web | 4 | External HTTP/DNS access |

Those descriptions refer to the earlier diagnostics; this run confirms their
counts are unchanged, rather than re-diagnosing every individual failure.
The useful next step is to review these remaining environment assumptions,
starting with core capture. Do not treat an augmented-image result as grounds
to mark the original task ready or hide failing public groups.

## Evidence and reproduction

See [build/run instructions](../experiments/deepswe/pwntools/OFFLINE.md) and the
[machine-readable result](../experiments/deepswe/pwntools/offline-result-2026-10-08.json).
The diagnostic image is `agentless-ml/pwntools-offline:2026-10-08`, identity
`sha256:4d9295759148dbdb3b1a18fe58b25d7d4d4ae17d7f6223c3c09db138eeafc5ba`.

The schedule took 246.5 seconds and exited 1, as expected for a report with
nine failing groups. Raw logs, the group report and execution metadata are
retained outside Git under
`../output/deepswe-survey/pwntools-offline-public-docker-2026-10-08/logs/agentless-ml-99efb1cc74d046e78ad31ff7bf57d653/`.
Their hashes are in the result file. The staged files, checksum manifest and
build identity are retained in the separate build artifact directory.

Five local image-helper tests cover pin tampering, byte counts, pinned regular
archive members, unsafe paths, and the bootstrap's diagnostic boundary.
The framework regression run passed 633 tests, with 29 opt-in/platform skips.
The focused image-helper and public-asset checks passed all 14 tests, including
the final path-safety check added after the regression run had collected tests.
