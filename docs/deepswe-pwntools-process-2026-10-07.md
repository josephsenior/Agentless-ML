# Pwntools process failures — 7 October 2026

The two failing groups contain three separate problems. None needs another
package installation, and the checks do not point to a broken snapshot or
path conversion in our runner. We reproduced them against the pinned public
source in the existing RISC-V/patchelf image, without changing permissions,
the runner, or any existing public source/test file.

## ASLR: a denied request is treated as success

The process example compares two `/proc/self/maps` outputs that should match
when address randomization is disabled. Inside our container,
`personality(ADDR_NO_RANDOMIZE)` returns `-1` with `errno=1` (`EPERM`), and
the maps still differ. The probe also observed zero effective capabilities,
no-new-privileges enabled and active seccomp filtering.

In the pinned `pwnlib/tubes/process.py`, `_preexec` calls `personality` but
does not inspect its return value. Returning `-1` does not raise a Python
exception, so Pwntools can print that ASLR is disabled even though the kernel
denied the request. We reproduced both the direct syscall denial and the
failed comparison through Pwntools' API.

This is consistent with Docker's default syscall restrictions; Docker
documents `personality` among restricted calls in its
[seccomp profile](https://docs.docker.com/engine/security/seccomp/).
We did not run a relaxed-policy control, so the direct evidence is the
denied request under the current security configuration, not a claim that
we isolated every possible kernel-policy cause. No security policy was
disabled to make this doctest pass.

## Relative path: the pinned code resolves it twice

The original public example uses a generated MIPS binary, but the failure
does not require MIPS or QEMU. A tiny executable shell script reproduces it.

`process._validate` joins the supplied relative `cwd` with `./probe` and
checks that the resulting path exists from the caller's directory. It passes
that still-relative path as `executable` to `subprocess.Popen`, together with
the same `cwd`. The child changes directory and resolves the executable from
there again. The second resolution points somewhere else.

For the probe running from `/tmp/work/docs`:

- `cwd` was `../../agentless-process-bin`.
- The validated executable was `../../agentless-process-bin/./probe`.
- Resolving it again from that directory produced `/agentless-process-bin/probe`,
  which did not exist.

The relative/relative call raised `FileNotFoundError` through both Pwntools
and plain `subprocess`. The controls with an absolute executable or absolute
`cwd` succeeded. This is a path-handling bug in the pinned upstream code,
not evidence that our temporary checkout is missing the binary. Patching the
benchmark repository or rewriting the public example would hide that baseline
failure, so we did neither.

## PID ancestry: PID 1 is not necessarily an ancestor

The doctest expects the ancestry list to end in PID 1. Our runner starts a
container with `--init`, then invokes tests with `docker exec`. In the probe,
the test's visible ancestry was `[25, 24, 18]`; PID 18 reported parent PID 0
and no visible parent. PID 1 existed as `docker-init`, but was not an ancestor
of this exec process. These PID numbers are observations, not fixed values.

Pwntools' list matched `psutil.Process().parents()` exactly. Its `parent()`
helper returns 0 when there is no visible parent, and `ancestors()` stops
there. The failed expectation therefore assumes a process topology that this
container execution route does not have. It is not evidence that ancestry
traversal dropped an accessible PID 1. We did not change the runner lifecycle
or inject a fake ancestor to satisfy the example.

## What the checks mean

All three authored reproduction cases passed: that means they confirmed the
known failure conditions, not that the public examples were repaired.
There was no new full-schedule run, package/image change, test exclusion,
model call or held-out test/solution access. The previous result remains
**44 passing and 10 failing public groups**, and canonical readiness remains
**92/113**.

The appropriate next investigation is `libcdb`'s missing library data and
offline lookup behavior. These process failures should remain visible in
the evidence; they do not justify silently relaxing isolation or patching
the benchmark's base code.

## Evidence and reproduction

The [inventory](../experiments/deepswe/pwntools_process_2026_10_07.json)
contains observations and execution/log hashes. The
[opt-in fixture](../tests/test_pwntools_process_diagnostics.py) checks the
same pinned task in a disposable workspace:

```powershell
$env:AGENTLESS_PWNTOOLS_PROCESS_IMAGE = 'agentless-ml/pwntools-riscv:2026-10-07'
$env:AGENTLESS_PWNTOOLS_PROCESS_ARTIFACTS = 'C:/Users/GIGABYTE/Desktop/Agentless-ML/output/deepswe-survey/pwntools-process-diagnosis-local'
.\.venv\Scripts\python.exe -m pytest tests/test_pwntools_process_diagnostics.py -q
Remove-Item Env:AGENTLESS_PWNTOOLS_PROCESS_IMAGE
Remove-Item Env:AGENTLESS_PWNTOOLS_PROCESS_ARTIFACTS
```

The live host check passed, including three container cases. Focused normal
checks passed **10 tests**, with **4 opt-in checks skipped**; the full
framework suite was not rerun for this diagnostic-only addition.
