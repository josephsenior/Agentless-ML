# Pwntools RISC-V tools and patchelf — 7 October 2026

The same broader public Docker schedule now has **44 passing groups and 10
failing groups**, compared with 42 and 12 in the MSP430-only image. The new
tools resolved all eight failures in `elf/elf` and all three in
`shellcraft/riscv64`. No other group's status or example counts changed.

The run completed in 184 seconds: **3,071 examples executed, 64 failed**,
with no setup or cleanup failures. It remains a failing diagnostic baseline,
not a passing result for the published benchmark image. Canonical readiness
stays **92/113**.

## What changed and how we checked it

The separate image adds Debian bookworm's `binutils-riscv64-linux-gnu=2.40-2`
and `patchelf=0.14.3-1+b1`. Versions are pinned. APT authenticated the package
metadata, and the build checked each downloaded archive against its recorded
SHA-256 before installation. The image retains the metadata, complete package
inventories and installed executable hashes under `/opt/pwntools-riscv/`.

The live check confirmed exactly two additions, with no parent package
upgrades or removals. No Python packages were installed. All 17 new executable
hashes and the inherited MSP430 tool hashes passed verification.

Four in-container smoke checks passed under the usual runtime restrictions:

- Installed package versions, inventories and executable hashes.
- RISC-V assembly, linking, binary extraction and disassembly, with exact bytes.
- The corresponding assembly instruction through Pwntools' own API.
- A real `patchelf` interpreter and RUNPATH rewrite, checked with `readelf`
  and by successfully running the patched executable.

These establish that the installed tools work for the paths we need; they are
not an exhaustive validation of every RISC-V instruction or ELF rewriting mode.

Reviewed image identities:

- MSP430 parent: `sha256:0ce9ca7ee932ed675d22d42eee8ef570c6b18cae73ba0370c689e9067cd045a6`
- RISC-V/patchelf image: `sha256:168f8c6b98131e2e58a4ba9265ac16b658174636cbb2d2de6493a0778c856318`

## The schedule and permissions stayed the same

We reran `--public-docker-schedule` on the same task and pinned base commit.
It still mirrors only the public Docker script's exclusions of `gdb.rst`,
`adb.rst` and `protocols.rst` in a disposable checkout. There were no new
exclusions and no changes to public test expectations or the sealed repository.
This is the documented Docker test selection, not the complete unchanged
`--full` schedule and not an exact reproduction of upstream's environment.

Execution still used the non-root `travis` account, no network except
container loopback, a read-only root, all capabilities dropped and no new
privileges. Limits remained 8 GiB memory, two CPUs, 2,048 processes and a
4-GiB temporary filesystem. SSH used fresh local keys with strict host-key
checking. No privileged mode, host networking, host credentials, Docker
socket or published port was introduced. Package installation had network
access only during preparation/build, not during the public test run.

## Remaining failures

The ten remaining groups have the same failure counts as before. The log
still shows external DNS failures (`context`, `tubes/sockets`, `update`,
`util/web`), WSL core-capture errors and dependent failures (`elf/corefile`,
`rop/rop`), temporary-home/mode/tmpfs assumptions (`filesystem`), missing
library lookup results (`libcdb`), a byte-comparison and executable-path
failure (`tubes/processes`), and a different process-ancestor chain
(`util/proc`). Some failures are cascades, so this is not ten independent
root causes. The [previous review](deepswe-pwntools-msp430-2026-10-07.md)
describes those observed symptoms; the new inventory retains exact counts.

Only wholly passing document/groups can enter supplementary diagnostic
inventory. The 3,007 passing individual examples are not independent
regression cases, and the 44 passing groups do not change canonical readiness.
No model calls or held-out test/solution files were involved.

Next, investigate the process-path and PID-chain assumptions. Network,
library-data and core-dump requirements need separate treatment; installing
more tools alone will not address every remaining failure. We should keep the
same restrictions while establishing which failures are harness assumptions
and which require a different, explicitly reviewed environment.

## Evidence and reproduction

See [build/run instructions](../experiments/deepswe/pwntools/RISCV.md),
[package pins](../experiments/deepswe/pwntools/riscv-packages.json), and
[execution inventory](../experiments/deepswe/pwntools_riscv_2026_10_07.json).
The inventory includes image identities, execution and log hashes, all
reported groups, and the comparison with the previous image.
Raw artifacts remain outside Git under
`../output/deepswe-survey/pwntools-riscv-*-2026-10-07/`.

The framework suite passed **620 tests**, with **27 skipped**. The opt-in
verification passed both host tests and all four in-container cases.
