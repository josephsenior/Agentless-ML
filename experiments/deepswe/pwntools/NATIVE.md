# Separate native/SSH diagnostic

This extends the Sphinx-only image; it does not replace either that image or
the published benchmark image. See the [review and results](../../../docs/deepswe-pwntools-native-2026-10-07.md).

The follow-on [MSP430 image](MSP430.md) fixes the selected assembly failure
and provides an explicit broader public-Docker-schedule diagnostic. Its
results are separate from the native-image results recorded here.

From the repository root, verify the Sphinx parent before building:

```powershell
$pwntoolsDocsParent = 'sha256:57532e55794896c77c6c030962d434ab02bf5211356d1211cb33b49c7390bf2e'
$actual = docker image inspect agentless-ml/pwntools-docs:2026-10-07 --format '{{.Id}}'
if ($LASTEXITCODE -ne 0 -or $actual -ne $pwntoolsDocsParent) { throw 'Sphinx parent differs from the reviewed image' }
docker build -f experiments/deepswe/pwntools/Dockerfile.native `
  -t agentless-ml/pwntools-native:2026-10-07 experiments/deepswe/pwntools

.\.venv\Scripts\python.exe tools/run_pwntools_native_tests.py
```

The default is a selected-page diagnostic, capped at 300 seconds, not the full
baseline. It runs `asm.rst`, `tubes/ssh.rst` and `testexample.rst`; Sphinx can
include related documents, so inspect the actual reported groups. Artifacts
accumulate in unique directories outside Git and are not deleted by this tool.
The native runner is explicit; `test_overrides.json` remains on the Sphinx-only
runner for the canonical image.

To request the complete unchanged schedule explicitly:

```powershell
.\.venv\Scripts\python.exe tools/run_pwntools_native_tests.py --full --timeout-seconds 1800
```

That mode has not been validated. It does not apply the public Docker script's
GDB/ADB/protocol exclusions or grant its privileged/host-network settings.
Do not treat a timeout or an incomplete report as a completed inventory.

## Verification fixtures

```powershell
$env:AGENTLESS_PWNTOOLS_NATIVE_IMAGE = 'agentless-ml/pwntools-native:2026-10-07'
$env:AGENTLESS_PWNTOOLS_NATIVE_ARTIFACTS = 'C:/Users/GIGABYTE/Desktop/Agentless-ML/output/deepswe-survey/pwntools-native-preflight-local'
.\.venv\Scripts\python.exe -m pytest tests/test_pwntools_native_environment.py -q

$env:AGENTLESS_PWNTOOLS_DOCS_IMAGE = $env:AGENTLESS_PWNTOOLS_NATIVE_IMAGE
$env:AGENTLESS_PWNTOOLS_DOCS_RUNNER = 'pwntools-native-doctest'
$env:AGENTLESS_DELEGATED_TASK_REPOSITORIES = 'C:/Users/GIGABYTE/Desktop/Agentless-ML/benchmarks/deepswe/repos'
$env:AGENTLESS_PWNTOOLS_DOCS_ARTIFACTS = 'C:/Users/GIGABYTE/Desktop/Agentless-ML/output/deepswe-survey/pwntools-native-candidate-local'
.\.venv\Scripts\python.exe -m pytest tests/test_deepswe_pwntools.py -q
```

The daemon runs as the same non-root account as its client, with freshly
generated keys, strict host-key checking and loopback-only binding. Home,
authorized keys, host keys, PID and logs are all under the writable temporary
filesystem. Package-generated default keys under `/etc/ssh` are not used.
Port 22 was verified to work without capabilities under this Docker daemon;
startup failure on another host exits as a harness error, never a passing test.

`native-packages.txt` describes the APT inputs, not a version lock. The exact
observed additions/upgrades are in `native-dependencies.json`; full before/after
dpkg lists and the GDB Python pip installation report are also retained under
`/opt` in the image. Compare these when rebuilding. The environment includes
nine upgraded base packages and a changed test user; it is diagnostic evidence
only, not a drop-in published-image result.
