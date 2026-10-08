# Pwntools: real offline HTTPS for update and download examples

The unchanged public `update` page passes **all 11 examples** against a
container-local HTTPS service serving a genuine public PyPI snapshot. The
previous network-none run failed five examples in that group.

The follow-up run of the unchanged public `util/web` page passes **all six
examples**, recovering its four previous failures. It uses the exact same
image, snapshots, certificate policy and Docker restrictions. The request
log records two real HTTPS downloads after the bootstrap checks: one returns
the bytes, and the other saves them for the public file-content comparison.
There are zero setup or cleanup failures in both selected-page reports.

This is an **offline-service diagnostic — modified environment**, not the
original benchmark baseline. Canonical readiness remains **92/113**. The
update and download pages were run separately; the full schedule has not
been rerun in this condition.

## Why a service rather than a cache shortcut

The update code calls `requests.get` on a hard-coded HTTPS URL. Putting a
JSON file in the image does not make that call work. Although an earlier
authored probe showed that warming its in-memory cache could exercise version
selection offline, it would bypass the first HTTP request.

This image instead runs a real TLS-wrapped Python HTTP server. The unmodified
code resolves `pypi.org` to loopback, requests `/simple/pwntools/`, checks the
HTTP result, parses the genuine JSON and populates its own cache. We do not
seed `available_on_pypi.cached` or replace requests/socket functions.

The same server serves genuine `httpbingo.org/robots.txt` bytes. An authored
preflight verifies Pwntools' real download, streaming and save-to-file paths.
That authored preflight is separate from the subsequent unchanged public
download-page result above.

## Scope and safeguards

- The separate image extends the SSH-aligned diagnostic; previous images and
  canonical task overrides are untouched.
- Only `pypi.org` and `httpbingo.org` map to `127.0.0.1`. The server binds only
  loopback port 443. There is no Google fixture, TCP port-80 service, DNS
  interception, external network, published port or host mount.
- Only two GET routes serve data. Unknown hosts/paths fail with HTTP 404;
  the PyPI route requires the JSON Accept header and otherwise returns 406.
  This is a frozen metadata endpoint, not a general PyPI package mirror.
- Payloads are read-only, dated and SHA256-pinned. The build helper checks
  the reviewed pins; both image build and service startup check payload bytes.
  Changed public responses require an explicit pin review, not silent refresh.
- Each container gets a newly generated one-day certificate and private key
  under private tmpfs storage. `REQUESTS_CA_BUNDLE` trusts that certificate
  only for the diagnostic shell and test children. No system/user CA store
  is changed; certificate and hostname verification stay enabled.
- Missing data, failed service startup or failed preflight stops the bootstrap
  with exit 125. The runner reports a harness error, not an empty passing suite.
- The service emits route/status logs, copied into the runner's stderr evidence
  during cleanup. Results have a separate `offline-service-diagnostic.json`
  recording the condition, mapped hosts, image, targets and certificate scope.

The non-root `travis` user, read-only root, all-capabilities-dropped policy,
no-new-privileges, network-none, 8-GiB memory, two CPUs, 4-GiB tmpfs and PID
limit 2048 remain in force. The separate runner adds only the two exact
loopback host entries. The canonical `DockerTestRunner` was not modified.
No host core-dump setting was changed; the original WSL pattern was verified.

## Public data and trust limit

The [reviewed pins](../experiments/deepswe/pwntools/service-snapshots.json)
record the exact bytes captured over public HTTPS on October 7 UTC / October 8
local time. Hashes pin those observed bytes; they are not publisher signatures.

| Snapshot | Bytes | SHA256 |
| --- | ---: | --- |
| PyPI JSON metadata | 87,063 | `e827f67b5a093b3b4773267f4f80ece47c5dc5bca1c128a4ef0fd081c8adc328` |
| robots.txt | 30 | `be76b8ab3a1d8db80cafb0c7a768af6c7b6b4ac28ffef3bf6d641c7ed4cec05a` |

Sources are the [PyPI index API](https://docs.pypi.org/api/index-api/) endpoint
`https://pypi.org/simple/pwntools/` with JSON content negotiation, and the
public [robots.txt](https://httpbingo.org/robots.txt) endpoint. Requests supports
the [explicit certificate bundle](https://docs.python-requests.org/en/latest/user/advanced/#ssl-cert-verification)
used here. No held-out benchmark data or model responses were used.

Freeze the same snapshots across any compared systems. Do not mix a pinned
offline condition with a live-provider condition and call their environments
equivalent.

## Checks and evidence

The opted-in service tests pass all nine checks. They cover payload tampering,
missing/unexpected files, invalid version data, capture pin replacement, exact
Docker host mappings and the absence of cache seeding/TLS bypasses. The real
Docker preflight checks a cold update fetch, download/save byte equality and
these negative controls:

- Default CA trust rejects the diagnostic certificate.
- The diagnostic certificate fails for the wrong hostname.
- An unsupported path returns 404.
- Stopping the service makes a cold update request fail.

The default-bundle check explicitly names Requests' normal CA bundle. Passing
`verify=True` alone still allows its environment-based bundle, so the first
attempt correctly stopped at preflight and was not a test result. That check
was corrected before the final run. Earlier attempts are retained separately.

The focused Docker/DeepSWE/Pwntools regression run passed 146 checks with 15
optional checks skipped, including the opted-in service transport test.

The pinned public repository commit is
`76894a5404a65d2800b6d0adaf3485ecba275caa`. The final image is
`agentless-ml/pwntools-services:2026-10-08`, identity
`sha256:073d1fdb8c6d5a5fd8fa276997a994aaa0a2b11d217c9fb001dddd41990d63f1`.

Build/capture evidence is under
`../output/deepswe-survey/pwntools-services-2026-10-08/build-reviewed/`.
The original reviewed snapshot capture is under `build-verified/snapshots/`.
Selected public-run evidence is under `update-reviewed/logs/` in that same
diagnostic artifact root. Request logs should contain the bootstrap checks
and an additional real PyPI request from the public update examples.

The download follow-up evidence is under
`web-reviewed/logs/agentless-ml-002393876d6d40f8a8e7568b190bdea9/`
in the same artifact root. Its `report.json` contains one passing `util/web`
group, six examples and zero example/setup/cleanup failures. Its condition
record pins the same image identity and selects only `source/util/web.rst`.
The normal unreachable external Sphinx inventory warnings remain visible;
the diagnostic does not provide arbitrary internet access.

## Reproduction

From the repository root, reuse the retained capture without network:

```powershell
.\.venv\Scripts\python.exe tools/build_pwntools_service_image.py `
  --destination ../output/deepswe-survey/pwntools-services-rebuild `
  --snapshots ../output/deepswe-survey/pwntools-services-2026-10-08/build-verified/snapshots

$env:AGENTLESS_PWNTOOLS_SERVICE_IMAGE = 'agentless-ml/pwntools-services:2026-10-08'
.\.venv\Scripts\python.exe -m pytest tests/test_pwntools_services.py -q

.\.venv\Scripts\python.exe tools/run_pwntools_service_tests.py `
  --artifacts ../output/deepswe-survey/pwntools-services-update-repeat

.\.venv\Scripts\python.exe tools/run_pwntools_service_tests.py `
  --artifacts ../output/deepswe-survey/pwntools-services-web-repeat `
  --targets source/util/web.rst
```

Omitting `--snapshots` fetches the two public URLs on the host, with standard
HTTPS verification, then compares them with the committed pins. Image build
steps and test containers still have networking disabled. The builder creates
a new artifact directory and refuses to overwrite one. The helper restricts
selected pages to `source/update.rst` and `source/util/web.rst`; it does not
offer an unreviewed full-suite mode.

Next: assess separate local TCP/TLS services for the socket/proxy examples.
They cannot be recovered by adding more static snapshot files alone.

That follow-up is now recorded in the
[shared HTTP/TLS diagnostic](deepswe-pwntools-protocol-services-2026-10-08.md).
It preserves this two-host image/profile and adds an explicit three-host
profile whose unchanged context/socket pages pass. Its results and image
identity are separate from the historical results in this note.
