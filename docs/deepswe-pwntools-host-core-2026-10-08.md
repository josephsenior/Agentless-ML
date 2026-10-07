# Temporary WSL core-dump setting: native retrieval works, ARM still needs investigation

The temporary host change fixed native crash-core retrieval without changing
the benchmark code or container permissions. The unchanged public Docker
schedule finished with **46 passing groups and 8 failing groups**, versus
45/9 before. Across 3,071 examples, failures fell from 43 to 32.

The original host setting was restored immediately after the run and checked
from `docker-desktop`, Ubuntu, and a normal isolated container. Canonical
readiness remains **92/113**. This is a diagnostic result, not a permanent
configuration or a ready baseline.

## The controlled change

With the user's explicit approval, the diagnostic saved the exact original
`kernel.core_pattern` value and recovery instructions before changing it:

```text
original:  |/wsl-capture-crash %t %E %p %s
temporary: core.%p
restored:  |/wsl-capture-crash %t %E %p %s
```

`kernel.core_uses_pid` stayed at `0`. No other sysctl, startup configuration,
image, benchmark runner, public test, or schedule exclusion was changed.
There were no other running Docker containers when the diagnostic began.

The setting was applied through `docker-desktop`'s root WSL shell, not through
a privileged benchmark container. It is a host-wide setting: it changes how
other crashes in the affected WSL environment can be collected during the
testing window. Core dumps can contain sensitive memory and consume space.
The benchmark containers retained their 4-GiB `/tmp` limit, but that limit
does not constrain unrelated WSL processes.

Linux's [core-file documentation](https://man7.org/linux/man-pages/man5/core.5.html)
explains both relative dump paths and external pipe handlers. A relative
`core.%p` pattern writes into the crashing process's working directory; our
test checkout is on writable container tmpfs. The original pipe instead
selects WSL's external handler, and the pinned Pwntools retrieval path tries
to use `cmd.exe` and `wslpath`, which the container lacks. Its error formatter
then misinterprets `%TEMP%` and raises `TypeError`, masking the missing command.

## Probe and public results

A tiny native i386 process first verified the change under the normal
container restrictions. It crashed with SIGSEGV, had unlimited core-file
allowance, and Pwntools found its core automatically. Its instruction pointer,
`eax`, and fault address all matched `0xdeadbeef`. The loaded core-finder source
hash matched the pinned public source.

Only after that probe passed did the diagnostic run the existing public
schedule. The recorded command is identical to the previous offline-data
run. Networking stayed disabled, the root filesystem stayed read-only, all
capabilities stayed dropped, no-new-privileges stayed enabled, and the user
stayed `travis`. Limits stayed at 8 GiB memory, two CPUs, 2,048 PIDs, and 4 GiB
tmpfs. The only excluded pages remained `gdb.rst`, `adb.rst`, and `protocols.rst`.

The `rop/rop` group passed all **176 examples**, removing its three failures.
The `libcdb` group still passed all 42 examples. The core-file group cleared
its previous 14 failing examples, but acquired **six newly failing ARM/QEMU
examples**. These must not be described as six surviving native failures.

In those ARM examples, the retrieved core describes `/usr/bin/qemu-arm-static`
with AMD64 register state, not the ARM `step3` program. That explains the
wrong executable mapping, load address, program counter, register `r0`, stack
register comparison, and fault address. The run demonstrates the wrong dump
was selected; it does not yet establish why QEMU's guest-core path changed.

| Group | Failed examples before | Failed examples during host diagnostic |
| --- | ---: | ---: |
| elf/corefile | 14 | 6, newly failing ARM examples |
| rop/rop | 3 | 0 |
| context | 2 | 2 |
| filesystem | 5 | 5 |
| tubes/processes | 2 | 2 |
| tubes/sockets | 7 | 7 |
| update | 5 | 5 |
| util/proc | 1 | 1 |
| util/web | 4 | 4 |

The schedule took 202.8 seconds and exited 1. There were no setup or cleanup
failures. No model calls or held-out tests/solutions were involved.

## Restoration and reproduction

The [opt-in controller](../tools/run_pwntools_host_core_diagnostic.py) stores
the original setting before applying the temporary one and restores it in
`finally`, including when setup, the probe, or the schedule fails. It checks
restoration and refuses to overwrite an unexpected concurrent setting.
An abrupt termination can bypass `finally`; saved `RECOVERY.txt` instructions
provide the manual recovery route. This is not an ordinary benchmark command.

Use only after explicit approval for another host-wide testing window:

```powershell
.\.venv\Scripts\python.exe tools/run_pwntools_host_core_diagnostic.py --apply-temporary-host-setting
```

The [result inventory](../experiments/deepswe/pwntools/host-core-result-2026-10-08.json)
records image identity, observations and evidence hashes. Raw artifacts are
retained outside Git at
`../output/deepswe-survey/pwntools-host-core-2026-10-08/diagnostic-tvaiygnr/`.

Nine controller tests cover explicit opt-in, literal argument handling,
restoration, failed verification, concurrent changes, and cleanup after
setup/probe/schedule failures without touching WSL. The combined focused
execution and integrity checks passed **104 tests**, with four opt-in skips.
The full framework suite was not rerun for this diagnostic-only addition.

Next: investigate the ARM guest-core behavior under the temporary pattern
before considering this setting for any regular benchmark environment.
