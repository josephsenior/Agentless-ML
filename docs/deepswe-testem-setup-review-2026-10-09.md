# Testem: missing public-suite browser dependency

After parking KGateway under the current limits, we inspected
`testem-per-launcher-reports`. Its pinned image has Node and Mocha, but no
discoverable Firefox executable. Public CI explicitly installs Firefox before
`npm test`, and the public tests request Headless Firefox. A blind full retry
would leave that concrete setup gap unaddressed.

## Evidence

Public base: `158f61ea91c9613d2011c41ee9be40ada1d7a307`.
Pinned image:

```
sha256:fce2e9ebe359b36b031e0b772159884795fc8383a047bc50eaa46c20fa06e4f6
```

The last canonical execution is `timeout`, with no accepted report and 4,916.6
seconds of recorded runner time. Its configured outer timeout was 3,600 seconds;
the public task's verifier timeout is 1,800 seconds. The discrepancy between
configured and observed time is not proof of host suspension: this old run has
no resource journal. Likewise, old warnings do not identify which test stalled.
An earlier reported 488-pass result is not a repeatable current baseline.

The public `package.json` runs:

```sh
mocha tests/*_tests.js tests/**/*_tests.js
```

The saved runner preserves both globs and uses the XUnit reporter. Public
`.mocharc.js` already declares `exit: true`, a 5,000-ms default timeout and
`tests/_prepare.js`. Therefore adding `--exit` is not an established fix.
Some public browser suites override the per-test timeout to 90 seconds.

The public `.github/workflows/ci.yml` installs Firefox using
`browser-actions/setup-firefox@v1`, checks `firefox --version`, and then runs
`npm test`. Its Linux Node matrix includes 20, 22 and 24. The separate integration
and Sauce Labs schedules are not the current public Mocha schedule and are not
being added here.

Public `tests/ci/ci_tests.js`, `tests/ci/dev_tests.js` and
`tests/ci/report_file_tests.js` request `Headless Firefox`. The public browser
catalogue looks for the `firefox` executable on Linux. This is not an optional
browser-only schedule that can simply be removed from `npm test`.

An automatically removed, offline, read-only image inspector reported:

- Node **v24.12.0**, Mocha **11.7.6**.
- Browserify exists at `/app/node_modules/.bin/browserify`.
- `command -v` found none of `firefox`, `firefox-esr`, `chromium`,
  `chromium-browser`, `google-chrome` or `phantomjs`.
- No matching Firefox/Chromium entries were listed under `/usr/bin`.
- `HOME=/root`; the image PATH includes `/app/node_modules/.bin` and normal
  system executable directories.

The inspector kept the same 8-GiB memory, two CPUs, 4-GiB scratch and 2,048-PID
limits, with no network, read-only root, all capabilities dropped and
no-new-privileges. It ran version/path probes only, not tests. The public
Dockerfile installs npm dependencies and the reporter but contains no explicit
Firefox installation. This inspection establishes lack of a discoverable
browser, not that no browser bytes exist anywhere in the image or that missing
Firefox alone explains every timeout.

## Next step

Assess a separately labelled Firefox-supplemented image: first identify a
specific official browser release, verify its public checksum/signature and
required native libraries, then build only after approval. Preserve the original
image, public tests and full schedule; do not fake browser success, filter browser
tests, disable assertions, relax Docker protections or enable runtime internet.
Read-only-root profile/home requirements and browser sandbox compatibility also
need checking rather than assuming installation is sufficient.

No image was built, dependency downloaded, test run or survey record changed.
KGateway, Numba and Pwntools remain parked. Canonical readiness remains
**100/113**. No held-out corpus tests or solutions were read.

Saved timeout evidence:
`../output/deepswe-survey/runs/testem-per-launcher-reports/logs/agentless-ml-1c55a17278694982b307012a3f499008/`.
