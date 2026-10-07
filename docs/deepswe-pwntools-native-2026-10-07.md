# Pwntools native tools and local SSH — 7 October 2026

The separate native image now runs Pwntools' public SSH examples under our
existing container isolation. The selected-page check completed with **430
passing examples out of 431**. The remaining failure needs an MSP430 assembler
that Debian's configured repositories do not provide. This is not a completed
full-suite baseline; canonical readiness remains **92/113**.

## What the public setup actually does

We reviewed the pinned repository's `TESTING.md`, `travis/install.sh`,
`travis/ssh_setup.sh`, and the Dockerfile, Makefile and `doctest3` script under
`travis/docker/`.

Its Docker Makefile uses `--privileged` and host networking. Its entrypoint
empties `gdb.rst`, `adb.rst` and `protocols.rst` before testing, with a comment
that GDB tests do not work in that Docker setup. It also changes an IPv6 sysctl.
So the public Docker route is not proof that the complete unmodified suite
works in a restricted benchmark container.

We did not copy those permission settings, change host services or sysctls,
or apply those test exclusions. The new image adds distribution-provided
native dependencies corresponding to the public setup: cross-binutils,
GDB/GDB server, QEMU, multilib support, shells, SSH and terminal utilities.
It does not fetch the setup script's old Ubuntu binaries, configure host
binfmt registrations or install the unrelated interactive development tools.

GDB embeds Python 3.11, while this benchmark image uses Python 3.12. The RPC
package installed for the benchmark was therefore invisible to GDB. We added
the same `rpyc==6.0.2` and `plumbum==2.0.1` versions to GDB's Python site
directory. The check confirms that GDB can import them; it does not establish
that its debugger integration tests pass.

## SSH without widening container permissions

The public tests connect to `example.pwnme` as `travis`. Our diagnostic maps
that name to `127.0.0.1` in SSH configuration, not external DNS.

The image declares a non-root `travis` account, with its home under `/tmp`.
Both the tests and SSH daemon run as that account. This lets the daemon log
into its own account without requiring Docker's SETUID or SETGID capabilities.
It is an explicit change from the published image's root user, not a setting
silently added to the benchmark runner.

Each disposable container generates new host and client keys in its temporary
home, pins the generated host key in `known_hosts`, and starts SSH on loopback
only. Password and root login are disabled. No host credentials are mounted,
no port is published, and no daemon is installed or started on Windows.
The shell stops its daemon on exit; the usual runner removes the container.
The passwd account has an empty password to avoid a locked-account rejection,
but the daemon explicitly refuses password and empty-password authentication.

The existing runner still supplies no network, a read-only root, all
capabilities dropped, no new privileges, an 8-GiB memory cap and two CPUs.
The live check verifies a non-root UID and zero effective capabilities, native
tool availability, OpenSSH login, a writable remote home, and the actual
Pwntools SSH transport.

An initial check caught a real setup mistake: OpenSSH reads the account's
passwd home, not merely the `HOME` environment variable. Putting its config in
a separate client home left the alias unresolved. Using the same temporary
account home for both resolved that without changing container permissions.

## What completed

The diagnostic tool selects the public assembly, SSH and example pages using
Sphinx's file arguments, the same mechanism documented as Docker's `TARGET`.
Sphinx also tested the related parent `tubes` document. Its report contains:

| Document/group | Executed examples | Failures |
| --- | ---: | ---: |
| `asm/default` | 54 | 1 |
| `testexample/default` | 6 | 0 |
| `tubes/default` | 219 | 0 |
| `tubes/ssh/default` | 152 | 0 |

There were no setup or cleanup failures. The structured inventory is **three
passing groups and one failing group**, not 430 independently eligible tests:
the conservative observer excludes the entire assembly group because one
example failed. The remaining example needs MSP430 binutils; `apt-cache policy`
reports no candidate. We did not replace that example, mark it skipped or borrow
another architecture's compiler. Adding SPARC64 binutils removed the other
assembly failure observed in the first completed attempt.

A separate candidate probe using this native runner confirms candidate-only
source visibility, platform/skip handling and reporting of deliberate test,
setup and cleanup failures. Its intentionally failing cases are verification,
not failed benchmark repairs.

Verification: **617 framework tests passed, 25 skipped**; native environment
checks passed **7/7**, and the candidate/config checks passed **8/8**.

## Reproducibility and the remaining decision

The [build/run instructions](../experiments/deepswe/pwntools/NATIVE.md) and
[dependency manifest](../experiments/deepswe/pwntools/native-dependencies.json)
record the separate image. Native APT installation added 63 packages and
upgraded nine existing ones, including libc and OpenSSL. Those changes matter:
this environment cannot be presented as the unchanged published condition.
The manifest records exact versions and the RPC wheel hashes. The APT inputs
are not version locked; a later rebuild must be compared and assigned its own
image identity rather than assumed equivalent.

The [execution evidence](../experiments/deepswe/pwntools_native_2026_10_07.json)
records failed setup attempts, intermediate assembly failures, the final
selected-page run, probes, resource limits and execution-file hashes.

We have not rerun the whole suite in this image or recreated the public
privileged Docker environment. The next bounded step is to review an MSP430
toolchain from an upstream source, then decide whether to test the complete
schedule or a clearly labeled schedule with the public Docker exclusions.
Neither choice should silently change canonical readiness.
