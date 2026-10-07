# RISC-V and patchelf diagnostic image

This adds two verified Debian packages to the MSP430 image. It is not a
replacement for the published benchmark image. Package versions and archive
SHA-256 values are recorded in [riscv-packages.json](riscv-packages.json).
See the [results and remaining failures](../../../docs/deepswe-pwntools-riscv-2026-10-07.md).
The [process-failure diagnosis](../../../docs/deepswe-pwntools-process-2026-10-07.md)
explains three remaining examples without modifying this image or schedule.
APT authenticates repository metadata; the recipe additionally checks the
downloaded archives before installation.

From the repository root:

```powershell
$pwntoolsMsp430Parent = 'sha256:0ce9ca7ee932ed675d22d42eee8ef570c6b18cae73ba0370c689e9067cd045a6'
$actual = docker image inspect agentless-ml/pwntools-msp430:2026-10-07 --format '{{.Id}}'
if ($LASTEXITCODE -ne 0 -or $actual -ne $pwntoolsMsp430Parent) { throw 'MSP430 parent differs from the reviewed image' }
docker build -f experiments/deepswe/pwntools/Dockerfile.riscv `
  -t agentless-ml/pwntools-riscv:2026-10-07 experiments/deepswe/pwntools
```

The build records complete before/after package inventories, authenticated
APT package metadata and installed executable hashes under
`/opt/pwntools-riscv/`. Our live probe checks that every parent package version
is unchanged and that only the two requested packages were added. Installation
uses network access during the image build; benchmark execution does not.
A rebuild may have a different image identity; inspect and record it.

Run the functional verification:

```powershell
$env:AGENTLESS_PWNTOOLS_RISCV_IMAGE = 'agentless-ml/pwntools-riscv:2026-10-07'
$env:AGENTLESS_PWNTOOLS_RISCV_ARTIFACTS = 'C:/Users/GIGABYTE/Desktop/Agentless-ML/output/deepswe-survey/pwntools-riscv-preflight-local'
.\.venv\Scripts\python.exe -m pytest tests/test_pwntools_riscv.py -q
Remove-Item Env:AGENTLESS_PWNTOOLS_RISCV_IMAGE
Remove-Item Env:AGENTLESS_PWNTOOLS_RISCV_ARTIFACTS
```

The four container cases verify package versions and hashes (including the
inherited MSP430 tools), RISC-V assembly/linking/disassembly, Pwntools'
RISC-V assembly API, and a real `patchelf` interpreter/RUNPATH rewrite.
The patched executable must still run successfully. These are smoke checks,
not a claim of exhaustive toolchain validation.

Rerun the same broader schedule:

```powershell
.\.venv\Scripts\python.exe tools/run_pwntools_native_tests.py `
  --image agentless-ml/pwntools-riscv:2026-10-07 `
  --public-docker-schedule --timeout-seconds 1800 `
  --artifacts ../output/deepswe-survey/pwntools-riscv-public-docker-local
```

This keeps the public Docker script's three documented page exclusions
(`gdb.rst`, `adb.rst`, `protocols.rst`), with no additional exclusions or
permission changes. It is not the separate unchanged-suite `--full` mode.
Raw artifacts accumulate outside Git in unique directories. Canonical
readiness is not changed by an augmented-image diagnostic.
