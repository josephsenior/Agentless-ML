# Pwntools MSP430 tools and broader public schedule — 7 October 2026

The missing MSP430 tools are now installed in a separate diagnostic image.
The previously selected public pages pass all **431 examples**. We then ran
the broader schedule documented by Pwntools' public Docker setup: **42 groups
passed and 12 failed**, with 75 failed examples out of 3,071 executed.
The run finished normally in 175 seconds; it did not time out.

This is progress on the diagnostic environment, not a passing benchmark
baseline. The published image is unchanged and canonical readiness stays
**92/113**. No model calls or held-out test/solution files were involved.

## What was verified

We built GNU Binutils 2.40 for `msp430-elf`, matching the native image's
Binutils generation. The source archive's SHA-256 was checked against the
[publisher's release announcement](https://lists.gnu.org/archive/html/info-gnu/2023-01/msg00003.html)
before extraction. This is a checksum verification, not a claim that we
verified a GPG signature.

The final image adds only the installed toolchain, its license, binary hashes
and source manifest. It inherits the reviewed native image without another
APT or Python installation. All 15 installed executable hashes were checked.
A live fixture assembled, linked, extracted and disassembled an MSP430
instruction, then verified the same bytes through Pwntools' `asm()` API.

Two initial fixture assertions needed correction: the link address had to be
inside MSP430's default flash region, and the disassembler prints a branch
alias for `mov #42, r0`. Those were probe mistakes, not toolchain failures;
the earlier logs remain alongside the successful run.

Image identities:

- Native parent: `sha256:3edc96947982c955bf4e7161e8f3dbadcf157d1943b27ecab1716ab9ff7560e4`
- MSP430 image: `sha256:0ce9ca7ee932ed675d22d42eee8ef570c6b18cae73ba0370c689e9067cd045a6`

## Exactly which schedule ran

The selected-page rerun requested `asm.rst`, `tubes/ssh.rst` and
`testexample.rst`; Sphinx also reported the parent `tubes` group. All four
groups passed, with no page exclusions in that run.

The broader run used `--public-docker-schedule`. It mirrors the pinned public
`travis/docker/doctest3` script's three empty pages: `gdb.rst`, `adb.rst` and
`protocols.rst`. Only a fresh disposable checkout was changed. There were no
additional exclusions based on observed failures, and the sealed repository
was untouched. This completed the documented Docker *test selection*, not
the complete unmodified suite or an exact reproduction of its environment.
The separate `--full` mode still requests the unchanged suite and was not
run here.

We did not adopt upstream's privileged container, host networking or sysctl
changes. Both runs retained network isolation, a read-only root, all
capabilities dropped, no new privileges, the non-root `travis` account and
ephemeral loopback SSH. Limits were 8 GiB memory, two CPUs, 2,048 processes
and a 4-GiB temporary filesystem. No host credentials, sockets or ports were
exposed.

## What remains broken

These are observations from the public doctest log, not a claim that every
root cause has been resolved. Some later exceptions cascade from an earlier
failed example in the same shared namespace.

| Group | Failed / executed examples | Observed issue |
| --- | ---: | --- |
| `context` | 2 / 164 | DNS failure differs from the expected proxy error. |
| `elf/corefile` | 14 / 107 | WSL core-capture path raises a formatting `TypeError`; follow-up examples fail. |
| `elf/elf` | 8 / 105 | Missing RISC-V assembler and `patchelf`, plus output differences. |
| `filesystem` | 5 / 149 | Expected `/home/...`, mode 664 and disk blocks differ from our temporary home, mode 644 and tmpfs. |
| `libcdb` | 21 / 42 | Library lookup/download returns no path; subsequent examples fail. Needs a separate offline-data review. |
| `rop/rop` | 3 / 176 | Same core-capture formatting error, then undefined `core`. |
| `shellcraft/riscv64` | 3 / 29 | Missing RISC-V assembler. |
| `tubes/processes` | 2 / 185 | Byte-comparison mismatch and a relative executable-path lookup failure. |
| `tubes/sockets` | 7 / 35 | External DNS failures, socket errors and dependent undefined variables. |
| `update` | 5 / 11 | PyPI lookup fails under network isolation; dependent expectations also fail. |
| `util/proc` | 1 / 18 | Expected ancestor chain ending in PID 1 differs from the observed chain. |
| `util/web` | 4 / 6 | `httpbingo.org` lookup fails under network isolation; dependent examples fail. |

There were no setup or cleanup failures. A report case remains an entire
document/group: the 2,996 individually passing examples do not become 2,996
independent regression cases. Only the 42 wholly passing groups are potential
supplementary diagnostic inventory, not canonical readiness evidence.

The next small step is to verify RISC-V binutils and `patchelf` in another
explicit image, then rerun this same schedule. Network, core-dump and
environment-sensitive examples need separate decisions; we should not widen
permissions or rewrite their expectations just to obtain a green report.

## Evidence and reproduction

See the [build and run instructions](../experiments/deepswe/pwntools/MSP430.md),
[source manifest](../experiments/deepswe/pwntools/msp430-source.json) and
[execution inventory](../experiments/deepswe/pwntools_msp430_2026_10_07.json).
The inventory records image identities, execution/log hashes and every
reported group. Raw artifacts remain outside Git under
`../output/deepswe-survey/pwntools-msp430-*-2026-10-07/`.

Verification: the framework suite passed **619 tests**, with **26 skipped**;
the opt-in MSP430 check passed its three host tests and all three in-container
probe cases.
