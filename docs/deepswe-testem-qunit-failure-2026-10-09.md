# Testem: the browser failure is missing QUnit

The HOME-only targeted test connects successfully, but its browser reports:

```
Global error: ReferenceError: QUnit is not defined at http://localhost:<port>/tests.js, line 4
```

That is the result behind the expected-zero-exit assertion. The missing favicon
was a separate HTTP 404, not the failed reporter result captured in this run.

## What was observed

One further run selected the same existing public test,
`ci mode app multiple launchers returns successfully with passed and skipped tests`.
The diagnostic retained the HOME-only setting and existing launch/HTTP observer,
and added observation of the real `Reporter.report()` and `hasPassed()` methods.
Each wrapper calls the original method with its original receiver/arguments and
returns its original value; no reported result, counter, assertion or decision
is replaced. This remains labelled instrumentation, not a full baseline.

Firefox loaded the real local page and scripts and connected to Testem. The
reporter received **one result, failed**, with the global ReferenceError above.
Its counters were total=1, passed=0, skipped=0, todo=0. The original `hasPassed()`
returned false. Testem consequently returned exit code 1; the unchanged public
test failed `expected 1 to equal +0` at `tests/ci/ci_tests.js:110`.
The runner recorded 11.922 seconds including setup and collection.

## Why QUnit is absent

At the pinned public revision, the fixture declares `framework: qunit`.
`lib/server/index.js` selects `views/qunitrunner.mustache`, whose framework
resources are external:

```html
<script src="//code.jquery.com/qunit/qunit-1.20.0.js"></script>
<link rel="stylesheet" href="//code.jquery.com/qunit/qunit-1.20.0.css"/>
```

The local page uses HTTP, so those protocol-relative URLs resolve to HTTP at
code.jquery.com. The protected offline container has no external connectivity;
the page does not obtain the CDN script defining QUnit. The fixture's
`tests.js` calls `QUnit.test(...)` on line 4 and throws. This combines a captured
browser error with the exact public loading path; the observer did not capture
Firefox's external DNS/HTTP error details or independently fetch the CDN.

The QUnit version is taken from the pinned source, not a guess or an upgrade
proposal. We have not checked current availability or checksums, acquired the
assets, served replacements, modified the template or enabled external access.
The finding concerns this selected test; it does not establish that every
remaining full-suite failure has the same cause.

## Unchanged boundaries

The image remained
`sha256:290cd40e1e05814859e3a0430b7bcbea77d92b8fcdd5161fd6ef1c1fc14e969d`;
the sealed candidate remained
`158f61ea91c9613d2011c41ee9be40ada1d7a307`. Only the already-labelled diagnostic
setting `HOME=/tmp/testem-firefox-home` was used. Public test source, assertions,
browser arguments, public timeout and report parsing were unchanged.

The runner retained the 1,800-second cap, no network, read-only root, all
capabilities dropped, no-new-privileges, 8 GiB memory without extra swap,
two CPUs, 2,048 PIDs and 4 GiB /tmp. The scoped Windows keep-awake request was
released and the owned container removed. No image or shared benchmark
configuration was changed. No full-suite retry started; canonical readiness
remains 100/113. No held-out tests or solutions were read.

Raw evidence is under
`../output/deepswe-survey/testem-firefox/diagnostics/agentless-ml-7e9cec56ab3e437bbd90d26f36994652/`:
`diagnostic.json`, `execution.json`, `report.xml`, observer events in `stdout.log`
and Testem logs in `stderr.log`. The
[compact record](../experiments/deepswe/testem_qunit_reporter_failure_2026_10_09.json)
retains the actual reporter inputs and false decision. Seven focused host-side
checks passed, including a Node contract check proving that observation leaves
the original report object, counter updates, return value and failure decision
intact.

## Next step

Verify the public QUnit 1.20.0 assets and assess a separately labelled offline
asset-delivery diagnostic that preserves the test content and Docker protections.
Do not enable unrestricted internet, upgrade the framework, suppress the global
error or report a passing baseline without actually running the unchanged test.
