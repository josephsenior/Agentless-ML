# Public libc data for the Pwntools diagnostic

This image extends the verified RISC-V image. It is not a replacement for the
published benchmark image and does not change task readiness.

The build uses [public-assets.json](public-assets.json), together with the raw
downloads and API replies retained by the public dependency audit. Those raw
files live outside Git at the manifest's `artifact_base` paths. If they are
missing or any checksum differs, the build stops; it does not silently download
replacement files.

From the repository root:

```powershell
.\.venv\Scripts\python.exe tools/build_pwntools_offline_image.py
.\.venv\Scripts\python.exe tools/run_pwntools_native_tests.py `
  --image agentless-ml/pwntools-offline:2026-10-08 `
  --public-docker-schedule --timeout-seconds 1800 `
  --artifacts ../output/deepswe-survey/pwntools-offline-public-docker-local
```

The staging helper rechecks the download and evidence hashes, then reads only
the pinned regular members of the Debian archives. Historical libc packages
are data, not operating-system upgrades. The only installed packages are
`elfutils` and `libasm1`, both `0.188-2.1`; installation uses the pinned local
archives with build networking disabled. Package inventories and executable
checksums are retained under `/opt/pwntools-offline`.

The image contains 25 genuine library binaries and 24 genuine symbol files at
Pwntools' default `/var/lib/libc-database`. Their package URLs come from the
verified provider replies. This is a finite snapshot of the public examples'
dependencies, not a complete mirror of libc.rip. Two matching debug files and
the current Debian libc/loader pair are kept as cache seeds.

The unchanged native command still sources `/opt/pwntools-setup-local-ssh.sh`.
In this image that script first sources the inherited SSH setup, then copies
the verified seed into a writable cache on `/tmp`. The original seed and local
database stay read-only. This lets the normal Pwntools cache code modify ELF
files without changing the test expectations or the image's source data.

There are no provider mocks, no network access, and no added container
permissions. The public schedule keeps only its existing three page
exclusions: `gdb.rst`, `adb.rst`, and `protocols.rst`. This is not the separate
unexcluded `--full` schedule.

Ubuntu debug archive hashes match publisher package indexes fetched over
HTTPS, but the audit did not verify Ubuntu Release signatures. Debian tool
and runtime-package pins came from APT-authenticated metadata. These are the
same trust limits recorded in the dependency audit.
