# Pwntools: the unchanged socket and context pages pass offline

The shared local HTTP/TLS diagnostic passes all **164 context examples** and
all **35 socket examples**. These groups previously had two and seven failed
examples respectively. Sphinx also included the related `tubes` page, which
passed all 219 examples. The actual report is **3 passing groups, 418 examples,
zero example failures and zero setup/cleanup failures**.

This is an **offline protocol-service diagnostic — modified environment**.
It does not show live Google connectivity, replace the original benchmark
baseline or change canonical readiness (**92/113**). The full public schedule
has not been run against this image.

## One server, not a second competing HTTPS listener

The earlier [two-host service diagnostic](deepswe-pwntools-services-2026-10-08.md)
already occupied port 443. Starting a separate Google TLS fixture there would
conflict with it. The new profile uses one Go service with a shared HTTPS
listener for `pypi.org`, `httpbingo.org` and `google.com`, plus a loopback HTTP
listener on port 80.

The two genuine public snapshot routes are unchanged: PyPI JSON metadata and
the 30-byte robots.txt body. Both retain their reviewed SHA256 pins. The
server validates the snapshot inventory and bytes before opening listeners;
it never seeds the update cache or replaces client socket/requests functions.

Google is a **protocol fixture**, not a mirror of Google's pages. Its public
examples send `GET /` followed by CRLF twice, without an HTTP version. Go's
standard HTTP parser rejects that malformed request with a real HTTP 400
response on either listener. The public socket tests only check the first
four bytes, `HTTP`. The service contains no hard-coded `HTTP` reply used to
manufacture a passing result; valid unknown requests return HTTP 404.

This is why the shared server uses Go rather than the earlier Python handler:
we verified the real parser behavior needed by the unchanged examples. It
uses only the standard library from Go 1.25.5 already present in the pinned
parent image. No compiler, modules or other packages were downloaded. A
multi-stage build keeps the compilation cache out of the final image, and
retains the compiler version and compiler/binary SHA256 records.

## Keep the negative cases negative

Ports **1 and 1080 remain closed**. The proxy example expects refusal at
`localhost:1080`; deploying a SOCKS proxy would defeat that test. Mapping
`google.com` to loopback lets hostname resolution finish so the example can
reach the intended proxy-refusal path. Its exact exception message was
verified separately, not just its exception class.

The service binds only `127.0.0.1:80` and `127.0.0.1:443`. All three hostnames
have explicit loopback entries. There is no general DNS interception, public
port, host mount or external networking. The normal non-root user, read-only
root, dropped capabilities, no-new-privileges, 8-GiB memory, two CPUs, 4-GiB
tmpfs and PID limit 2048 remain unchanged.

One ephemeral certificate covers the three names. Trust is scoped to the
diagnostic shell/test children through `REQUESTS_CA_BUNDLE`; no system/user
trust store changes. Requests and the preflight verify certificates and
hostnames. The public Pwntools remote client's own TLS policy is unchanged.
The bootstrap runs the genuine snapshot checks and protocol checks before
Sphinx. Failure exits 125 as a harness error, rather than publishing an empty
passing report.

## Verification

The opted-in service test file passes all ten checks. The real Docker probe
verifies cold PyPI fetches, streamed/saved download bytes, both parser-generated
HTTP 400 responses and the exact proxy error. Its negative controls verify:

- certificate rejection with the default CA bundle;
- hostname mismatch rejection with diagnostic trust;
- HTTP 404 for unsupported requests and 406 for missing PyPI JSON negotiation;
- rejection of corrupted snapshot data by the compiled service;
- refused connections on both listeners after stopping the service.

The focused Docker/DeepSWE/Pwntools regression run passed **147 checks**, with
15 optional checks skipped. Compiler and service binary checksum verification
also passed. No host core-dump settings were changed; the original WSL pattern
was verified. The expected rejected-TLS preflight and unreachable external
Sphinx inventory warnings remain visible in evidence.

## Reproduce the selected-page run

The new image is `agentless-ml/pwntools-protocol-services:2026-10-08`, identity
`sha256:7beea7ed2a0c9ba6e609797581beeaa067921e9eb25c90c2bcc2259207cb217b`.
It extends the same pinned SSH-aligned parent as the earlier service image,
which remains available under its original tag. The original two-host runner
profile is still the default; the three-host profile requires an explicit flag.

```powershell
.\.venv\Scripts\python.exe tools/build_pwntools_service_image.py `
  --protocol-services `
  --destination ../output/deepswe-survey/pwntools-protocol-services-repeat-build `
  --snapshots ../output/deepswe-survey/pwntools-services-2026-10-08/build-verified/snapshots

$env:AGENTLESS_PWNTOOLS_SERVICE_IMAGE = 'agentless-ml/pwntools-protocol-services:2026-10-08'
$env:AGENTLESS_PWNTOOLS_PROTOCOL_SERVICES = '1'
.\.venv\Scripts\python.exe -m pytest tests/test_pwntools_services.py -q

.\.venv\Scripts\python.exe tools/run_pwntools_service_tests.py `
  --protocol-services `
  --artifacts ../output/deepswe-survey/pwntools-protocol-services-repeat `
  --targets source/tubes/sockets.rst source/context.rst
```

The public repository revision remains
`76894a5404a65d2800b6d0adaf3485ecba275caa`. Neither source nor doctest expected
outputs were changed. Only the selected public pages were requested; no new
exclusions were applied.

Build evidence is under
`../output/deepswe-survey/pwntools-protocol-services-2026-10-08/build-reviewed/`.
Public report, command/limit metadata, condition record and logs are under
`socket-context/logs/agentless-ml-159cff1167cf4f95afecae2d6449e9dc/`
in the same artifact root. The report records the additional related `tubes`
group explicitly rather than hiding it in the selected-page count.

Next: run all four supported public pages together against this shared image
to check the combined condition. The PyPI/download routes passed real
functional preflight here, but their earlier full-page results were obtained
with the earlier two-host image and should not be silently carried forward.
