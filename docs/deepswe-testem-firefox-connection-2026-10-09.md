# Testem: Firefox starts but does not connect

The targeted diagnostic points to **writable home/cache handling**, rather than
argument order or insufficient memory. This is a diagnosis, not an implemented
benchmark fix or a passing full baseline.

## Trace of one existing public test

We selected `ci mode app multiple launchers returns successfully with passed
and skipped tests` from the pinned public `tests/ci/ci_tests.js`. Its source,
assertions and timeout were unchanged. This single-test selection is explicitly
diagnostic; it is not another full-schedule result.

A Node preload recorded child-process arguments, Firefox stdout/stderr and
HTTP request/upgrade events. It added listeners and logging, but did not replace
browser arguments, environment, HTTP responses, test assertions or exit codes.
Observation adds overhead and is not claimed to be invisible instrumentation.

The test failed in 37.234 seconds. Firefox launched with the public arguments
`-profile --headless <temporary-profile> <localhost-url>`, inherited `HOME=/root`,
and remained alive until Testem sent SIGTERM about 29 seconds later. The observer
recorded **no incoming HTTP requests or upgrades**. Firefox reported:

```
Fontconfig error: No writable cache directories
```

It also emitted namespace/GPU warnings and a SWGL framebuffer message. Those
messages alone do not establish the root cause; several also occur in successful
controls below. The server's lack of incoming requests is consistent with the
missing browser results in the full run, not evidence that its assertions should
be weakened.

## Synthetic connection controls

A separate protected container served a tiny page on 127.0.0.1. Its JavaScript
made a real HTTP `/beacon` request. Each case used a fresh profile and at most
15 seconds to connect. No benchmark tests were involved in these controls.

| Arguments | Home/cache condition | Page request | JavaScript beacon |
| --- | --- | --- | --- |
| Public Testem order | Image home `/root` | No | No |
| `--headless -profile <profile>` | Image home `/root` | No | No |
| Public Testem order | Fresh writable home and XDG paths under `/tmp` | Yes | Yes |
| `--headless -profile <profile>` | Fresh writable home and XDG paths under `/tmp` | Yes | Yes |

The successful requests carried Firefox 140's user-agent. The font-cache warning
disappeared in the writable-home cases. Namespace, missing-GPU/library and SWGL
messages remained even when page loading and JavaScript succeeded, so those
messages are not sufficient evidence of the connection blocker.

This isolates the **combined home/cache configuration** as a causal difference
for the synthetic page: HOME, XDG_CACHE_HOME and XDG_CONFIG_HOME were changed
together. It does not establish which individual variable or directory is
necessary, nor prove that every browser profile argument was interpreted as
intended. Reordering arguments was neither sufficient with the image home nor
necessary with the writable paths in this experiment.

The synthetic page used 127.0.0.1, whereas the real test uses localhost. We did
not establish that hostname resolution or other Testem integration issues are
absent. Nor did we demonstrate that the full public suite passes with writable
paths. The earlier screenshot smoke check also used writable home/cache paths,
which explains why it was not equivalent to the original public launch setup.

## Boundaries and evidence

All runs used the exact verified Firefox image:

```
sha256:290cd40e1e05814859e3a0430b7bcbea77d92b8fcdd5161fd6ef1c1fc14e969d
```

The targeted test used a sealed candidate at
`158f61ea91c9613d2011c41ee9be40ada1d7a307`. The normal runner retained its
1,800-second cap, offline network, read-only root, dropped capabilities,
no-new-privileges, 8 GiB memory without extra swap, two CPUs, 2,048 PIDs and
4 GiB /tmp. Docker inspection confirms the same protections for the native
controls; their container exited zero without an OOM. No sandbox-disable flags
or protection relaxations were used. Both owned containers were removed.

Raw evidence under `../output/deepswe-survey/testem-firefox/`:

- `diagnostics/agentless-ml-6645c6c80f1541248a6c4280e3d0bd8c/` contains the
  public test's `diagnostic.json`, `execution.json`, `report.xml`, observer
  events in `stdout.log`, and Testem's `stderr.log`.
- `agentless-ml-testem-controls-035194417b764b83963c504ea97c35cf.json` contains
  all four native commands, browser logs, actual requests and Docker inspection.

The [compact record](../experiments/deepswe/testem_firefox_connection_2026_10_09.json)
keeps both conditions distinct. Canonical readiness remains 100/113, and the
full baseline remains 489 passed, three skipped and eight failed after
normalization. No held-out tests or solutions were read. No image, benchmark
configuration or shared validation command was changed. No further run started.

## Next step

The [single-variable follow-up](deepswe-testem-minimal-home-2026-10-09.md)
found HOME alone sufficient; the two XDG-only controls did not connect. The same
unchanged public test connected to Testem with HOME alone but still failed its
expected-zero-exit assertion. Inspect the browser-reported failures next,
without changing tests or Docker protections. No full repeat has followed.
