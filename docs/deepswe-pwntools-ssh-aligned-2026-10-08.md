# Pwntools: aligning the public SSH filesystem environment

The unchanged public `filesystem` page now passes **148 of 149 examples**.
Previously it passed 144. Four failures were assumptions about the SSH user's
home path and file-creation permissions. The remaining example assumes that
an empty directory consumes disk blocks; our writable filesystem is tmpfs.

This is a selected-page diagnostic, not a completed benchmark or a new full
public-schedule result. Canonical readiness remains **92/113**.

## What changed, and why

The diagnostic account now advertises `/home/travis`, as expected by the
public examples. That path is a read-only image link to
`/tmp/pwntools-ssh-user`. The bootstrap creates the target on the fresh tmpfs
before creating SSH keys. Home data still disappears with the container; we
did not add a disk mount or make the root filesystem writable.

The bootstrap reads the account's home from `getent passwd travis` rather
than hard-coding the client home and key paths. It configures
`internal-sftp -u 0002`. Setting only the startup
mask was insufficient: the first live probe still observed SFTP uploads with
mode `0644`. The explicit SFTP mask produces the public examples' `0664`.
The ineffective local mask change was removed; local defaults are unchanged.
Private home/key directories and authorized keys retain explicit `0700` and
`0600` permissions. Authentication remains key-only and loopback-only.

The separate `Dockerfile.ssh-aligned` extends the verified offline image. It
changes the account's advertised home, adds the link, and replaces the native
SSH bootstrap. The offline-data wrapper and all dependencies are unchanged.
The existing offline image/tag was not replaced. No public benchmark source,
expected outputs, exclusions, selection logic or canonical task override was
changed.

## Observed result

| Public expectation | Before | Aligned image |
| --- | --- | --- |
| Home under `/home/...` | `/tmp/pwntools-ssh-user` | `/home/travis` |
| Expanded `~/my-file` under `/home/...` | `/tmp/pwntools-ssh-user/my-file` | `/home/travis/my-file` |
| Initial file mode in the chmod example | `100644` | `100664` |
| Initial file mode in the stat example | `100644` | `100664` |
| Empty-directory `ls -la` header | `total 0` | `total 0` (still fails) |

The remaining failure is deliberately visible. Plain SSH `mkdir`/`ls` and
Pwntools `SSHPath.mkdir` both report `total 0` on this tmpfs; the directory
and its parent report zero allocated blocks. Supplying disk-backed storage
would be a different diagnostic environment, not a correction to this test's
output. We did not do that here.

The final report contains one failed group, 149 examples, one failed example,
and zero setup/cleanup failures. The group remains failed despite recovering
four examples; do not turn this into an overall group-readiness improvement.

## Verification and reproduction

Pinned repository commit: `76894a5404a65d2800b6d0adaf3485ecba275caa`.

Parent image ID:
`sha256:4d9295759148dbdb3b1a18fe58b25d7d4d4ae17d7f6223c3c09db138eeafc5ba`.

Final aligned image ID:
`sha256:35bce93dd151739b946cd6a9c01258591be30a723729d1b367855480c5ed1529`.

From the repository root:

```powershell
$taskParent = docker image inspect agentless-ml/pwntools-offline:2026-10-08 --format '{{.Id}}'
if ($LASTEXITCODE -ne 0 -or $taskParent -ne 'sha256:4d9295759148dbdb3b1a18fe58b25d7d4d4ae17d7f6223c3c09db138eeafc5ba') { throw 'Offline parent differs' }
docker build --network=none -f experiments/deepswe/pwntools/Dockerfile.ssh-aligned `
  -t agentless-ml/pwntools-ssh-aligned:2026-10-08 experiments/deepswe/pwntools

$env:AGENTLESS_PWNTOOLS_NATIVE_IMAGE = 'agentless-ml/pwntools-ssh-aligned:2026-10-08'
$env:AGENTLESS_PWNTOOLS_ALIGNED_IMAGE = $env:AGENTLESS_PWNTOOLS_NATIVE_IMAGE
.\.venv\Scripts\python.exe -m pytest tests/test_pwntools_native_environment.py -q

.\.venv\Scripts\python.exe tools/run_pwntools_native_tests.py `
  --image agentless-ml/pwntools-ssh-aligned:2026-10-08 `
  --artifacts ../output/deepswe-survey/pwntools-ssh-aligned-2026-10-08/filesystem-final `
  --targets source/filesystem.rst --timeout-seconds 300
```

The final command exits **1**, correctly, because one public example remains
failed. `--targets` cannot be combined with either full-schedule flag.

The opted-in preflight passed all nine framework checks. Its in-container
probes verify the home link, file mode, public path expansion and unchanged
tmpfs behavior, as well as the non-root identity, zero effective capabilities,
`NoNewPrivs=1`, native tools and loopback SSH transport.

The framework regression run passed 650 tests with 30 optional checks skipped.
Two additional CLI exclusivity checks were added during that run and verified
separately: the focused native/MSP430/offline/Sphinx tests passed 23 checks with four
optional probes skipped. The opted-in Docker probes above are separate from
those default runs.

The public run retained 8-GiB memory, two CPUs, 4-GiB tmpfs, PID limit 2048,
no external network, a read-only root filesystem, all capabilities dropped
and `no-new-privileges`. No host core-dump setting was changed. The original
`|/wsl-capture-crash %t %E %p %s` pattern was verified after the checks.

Local public evidence lives under:
`../output/deepswe-survey/pwntools-ssh-aligned-2026-10-08/filesystem-final/logs/agentless-ml-92689a63a9ba4c0586ea0a0fd4e45115/`.

Earlier failed bootstrap/mask attempts remain in separate artifact directories;
they are not the final result. The previous 47/7 full-schedule result used a
temporary host core pattern and the previous image. It has not been rerun with
this image, so it must not be presented as this image's result.
