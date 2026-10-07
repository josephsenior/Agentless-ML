# A non-colliding core filename preserves native and ARM retrieval

This follow-up tests `core.native.%p` in another explicitly approved temporary
host window. The earlier `core.%p` pattern fixed native retrieval but introduced
six ARM/QEMU failures. No permanent setting or benchmark-code change is part
of this diagnostic.

The unchanged public Docker schedule passed **47 groups**, with **7 failing**.
All 107 core-file examples and all 176 ROP examples passed. The original WSL
setting was restored and verified after the run. Canonical readiness remains
**92/113**, since this is still an augmented-environment diagnostic.

## Why this filename

The pinned Pwntools core finder first accepts any existing `core.<pid>` in the
current directory. That shortcut comes before the QEMU guest-dump search and
does not check that the dump's architecture matches the program. With a native
emulator dump at that name, the ARM dump can be overlooked.

`core.native.%p` avoids the shortcut. Pwntools can then search for QEMU's
`qemu_<program>_<time>_<pid>.core` first. If that is absent, its existing native
pattern expansion can find `core.native.<pid>`. No new selection algorithm or
wrapper around the public test code is needed.

This assessment concerns newly generated dumps in disposable workspaces.
A stale `core.<pid>` file could still trigger the shortcut. Pwntools can also
rename a successfully retrieved core to that name later; the probe inventories
the original files before that happens.

## Small probes

The native i386 probe found `/tmp/core.native.15` automatically. Its instruction
pointer, `eax`, and fault address were all `0xdeadbeef`, with SIGSEGV recorded.

The ARM probe directly observed both files from the same crash:

| File | Architecture | Bytes |
| --- | --- | ---: |
| `core.native.23` | AMD64 emulator | 163,987,456 |
| `qemu_step3_20261007-225045_23.core` | ARM guest | 8,404,992 |

Pwntools selected the ARM file. Its executable was the generated `step3`,
mapped at `0x41410000`; `pc` was `0xcafebabe` and `r0` was `0xdeadbeef`.
The native core-finder source hash matched the pinned public checkout.

The probes used the existing offline-data image, normal non-root image user,
network-none, read-only root, all capabilities dropped, no-new-privileges,
8-GiB memory, two CPUs, 2,048 PIDs and 4-GiB tmpfs. The subsequent public run
uses its unchanged command and three existing Docker page exclusions.

## Public schedule and restoration

| Host pattern during the run | Passing / failing groups | Failed examples |
| --- | --- | ---: |
| Original WSL handler | 45 / 9 | 43 |
| `core.%p` | 46 / 8 | 32 |
| `core.native.%p` | 47 / 7 | 26 |

All three rows use the same pinned offline-data image and public Docker
schedule. The new run contains 3,071 examples, with no setup or cleanup
failures. It took 155.1 seconds and exited 1 because other groups still fail.
The six ARM failures from the previous host window are gone. The remaining
groups have unchanged failure counts: context 2, filesystem 5, tubes/processes
2, tubes/sockets 7, update 5, util/proc 1, and util/web 4. The libcdb group still
passes all 42 examples.

The recorded public command matches the previous run exactly. No exclusion,
permission, resource limit, image, or benchmark source-file change accounts for the
improvement. The observation supports the filename-selection diagnosis;
it does not explain QEMU's internal decision to produce an extra emulator dump.

After the schedule, the controller restored
`|/wsl-capture-crash %t %E %p %s`. Restoration was checked from `docker-desktop`,
Ubuntu, and a normal isolated container. `core_uses_pid` stayed at `0`.
No model calls or held-out test/solution access were involved.

The [result inventory](../experiments/deepswe/pwntools/noncolliding-core-result-2026-10-08.json)
records the observations, image identity, restoration and evidence hashes.
Raw artifacts are retained outside Git at
`../output/deepswe-survey/pwntools-host-core-native-2026-10-08/diagnostic-q8bo3moj/`.

## Reproduction and safety

Use the [host diagnostic controller](../tools/run_pwntools_host_core_diagnostic.py)
only after approval for a quiet host-wide testing window:

```powershell
.\.venv\Scripts\python.exe tools/run_pwntools_host_core_diagnostic.py `
  --apply-temporary-host-setting --pattern core.native.%p `
  --artifacts ../output/deepswe-survey/pwntools-host-core-native-local
```

The controller accepts only the two reviewed diagnostic patterns, saves the
original setting and recovery instructions, and restores the original in
`finally`. Restoration checks against the particular pattern applied in that
run; the other diagnostic pattern is treated as an unexpected concurrent
change. An abrupt process termination still requires the saved manual recovery
procedure. No WSL startup configuration is edited.

Both patterns are host-wide, not container-only. During the window, unrelated
WSL crashes may produce local files containing sensitive memory or consuming
space. The benchmark tmpfs limit does not bound unrelated WSL workloads.

Fifteen controller tests check explicit opt-in, literal arguments, selected
pattern restoration, concurrent changes, probe requirements, and cleanup on
setup/probe/schedule failure without touching WSL. Combined focused execution
and integrity checks passed 110 tests, with four opt-in skips.
The full framework suite was not rerun for this diagnostic-only change.

Next: investigate the filesystem group's five environment-dependent failures.
This successful core diagnostic does not justify silently adopting a permanent
host setting or promoting the task to ready.
