# Testem: HOME alone restores the browser connection

The smallest successful setting among the tested single-variable controls was
a **fresh writable HOME under /tmp**. Neither XDG_CACHE_HOME alone nor
XDG_CONFIG_HOME alone restored the connection. The same unchanged public test
then connected to Firefox with HOME alone, but **still failed its assertion**.
This is a verified connection improvement, not a passing baseline.

## Isolating the path settings

All synthetic controls used the public Testem argument order, the same verified
Firefox image, a fresh temporary profile and a 15-second connection window.
The page executed JavaScript which made a real `/beacon` request.

| Only override | Page request and JS beacon |
| --- | --- |
| None; image HOME=/root | No |
| XDG_CACHE_HOME | No |
| XDG_CONFIG_HOME | No |
| HOME | Yes |

The cache-only control removed the Fontconfig warning without restoring the
connection. That warning is therefore not, on its own, the explanation for the
stall. HOME may affect several internal Firefox directories; this experiment
does not identify the exact internal file or prove that no narrower mechanism
could ever work. It establishes one sufficient environment-variable override
among those tested. XDG variables were unset in the image and remained unset
in the successful HOME-only control.

## Verification in the real public test

The same selected test was run once:
`ci mode app multiple launchers returns successfully with passed and skipped tests`.
Its source, assertions, browser arguments and 90-second public timeout were
unchanged. The runner retained its 1,800-second cap. The existing diagnostic
preload observed process output and HTTP traffic, as in the preceding trace.
Only this environment setup was added to the labelled diagnostic command:

```sh
mkdir -p /tmp/testem-firefox-home
export HOME=/tmp/testem-firefox-home
```

The recorded Firefox spawn inherited that HOME. It requested the real localhost
test page, `/testem.js`, `/hello.js`, `/tests.js`, the connection iframe and
Socket.IO scripts. The observer captured polling requests and a WebSocket
upgrade request. Testem logged `New client connected: Firefox 140.0`, attached
the client and reported `Browser Headless Firefox finished all tests. true`.
These events establish a real Testem connection, beyond the synthetic beacon.

The public test nevertheless returned exit code 1 and failed
`expected 1 to equal +0` at `tests/ci/ci_tests.js:110`. The runner recorded
22.5 seconds including its setup and collection. No test was suppressed or
changed to turn this into a pass.

Testem also logged an ENOENT for the fixture's missing favicon. The pinned
server source handles ENOENT by logging it and returning HTTP 404;
`App.getExitCode()` returns the observed `Not all tests passed` error when
`reporter.hasPassed()` is false. We have not established that the favicon caused
the failing reporter result. Do not add a dummy favicon or hide that error
without first inspecting the actual browser-reported results. The channel-error
messages appeared while Testem was terminating Firefox, after test completion;
they are not evidence of a pre-connection crash.

## Scope and evidence

The image remained
`sha256:290cd40e1e05814859e3a0430b7bcbea77d92b8fcdd5161fd6ef1c1fc14e969d`.
The sealed candidate remained
`158f61ea91c9613d2011c41ee9be40ada1d7a307`. Both runs retained offline network,
read-only root, dropped capabilities, no-new-privileges, 8 GiB memory without
extra swap, two CPUs, 2,048 PIDs and 4 GiB /tmp. Native-control Docker inspection
recorded exit zero without OOM; owned containers were removed. The scoped
Windows keep-awake request for the public test was released.

Raw evidence under `../output/deepswe-survey/testem-firefox/`:

- `agentless-ml-testem-controls-99f8ba19ca2e4a0083c700408a1ca705.json` records
  each isolated environment, browser logs, requests and Docker protections.
- `diagnostics/agentless-ml-f2af3251cd874d87be7a25f2b8ea70b6/` contains the
  HOME-only test's `diagnostic.json`, `execution.json`, `report.xml`, and
  observer/Testem logs.

The [compact record](../experiments/deepswe/testem_minimal_home_2026_10_09.json)
keeps the successful connection and failing assertion distinct. No image,
shared runner or canonical benchmark configuration was changed. No full suite
was rerun; canonical readiness remains 100/113. No held-out tests or solutions
were read. Six focused host-side checks passed.

Next, inspect the browser-reported results responsible for `reporter.hasPassed()`
being false in this same test, retaining HOME-only as an explicitly labelled
control. Do not rerun the full suite until that failure is understood.
