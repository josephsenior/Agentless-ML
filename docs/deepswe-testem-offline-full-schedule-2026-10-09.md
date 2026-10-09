# Testem: full schedule in the labelled offline-asset condition

The unchanged full public schedule completed in **48.282 seconds** with exit
code 1 and a usable report. Normalized results: **496 passed, three skipped,
one failed** across 500 distinct IDs. This is a completed failing baseline in
the modified offline-delivery condition, not a canonical readiness update.

The one remaining failure is `ci mode app::handles todos correctly`:

```
1 todo (other is failing): expected +0 to equal 1
```

The unchanged assertion is at public `tests/ci/ci_tests.js:493`. It expected one
todo result, but the reporter counted zero. We did not weaken this assertion or
reinterpret the outcome as a pass.

## Execution boundary

The run used the same separately built image
`sha256:96b08a03e607416b109f7d86186d1cdfe92755483eada98693e67ff5f2feba00`,
sealed revision `158f61ea91c9613d2011c41ee9be40ada1d7a307`, HOME-only setting,
owned QUnit service and per-container code.jquery.com loopback mapping.

Both unchanged public globs ran: `tests/*_tests.js` and `tests/**/*_tests.js`.
The full-run path reuses the shared Mocha/xUnit command without `--grep` or
diagnostic prototype observers. The service supervisor preserves that command's
exit code, checks the two pinned HTTP responses before execution, watches
service liveness and cleans up its owned process. The selected-test trace was
instrumented; this full schedule was not. No source, tests, assertions, browser
arguments or report parser were changed.

The configured cap remained 1,800 seconds. Docker inspection confirmed
network=none, read-only root, all capabilities dropped, no-new-privileges,
no privileged mode, 8 GiB memory without extra swap, two CPUs, 2,048 PIDs and
the same 4 GiB executable/nosuid/nodev /tmp. No port was published or credential
mounted. The owned container was removed and scoped keep-awake request released.
No interruption or resource failure was observed in this attempt.

## Counts and comparison

The XML has 503 testcase nodes: 499 passed, three skipped and one failed.
Two passing IDs repeat: the Config isCwdMode test appears three times and the
Launcher stderr test twice. The existing worst-outcome-per-ID normalization
therefore gives 496/3/1 across 500 IDs. No deduplication rule was changed.

The preceding Firefox-only full run had normalized counts 489/3/8. This run has
seven fewer failed IDs, but the reported ID inventories are not identical: the
old failing report-file afterEach hook no longer appears, while the previously
blocked `creates folders in the path if they don't exist` test now does.
Thus this is not a perfectly paired 500-ID comparison. Both raw reports remain
available; improved delivery does not imply general benchmark performance.

## Concrete remaining dependency

The public todo fixture has a custom `tests/fixtures/todo/test.html` referencing
`//code.jquery.com/qunit/qunit-2.9.2.js` and the corresponding CSS. Its `test.js`
uses `QUnit.todo(...)`. The allowlisted service correctly returned HTTP 404 for
both 2.9.2 assets; it supports only the separately verified 1.20.0 files.
The service log captured two requests for each unsupported 2.9.2 path.

This establishes an unsupported public framework dependency in the remaining
test. We did not capture its browser reporter events in this uninstrumented
full run, so do not claim every internal failure is proven or patch the todo
semantics. QUnit 1.20.0 must not replace the explicitly requested 2.9.2 files.
No new asset was acquired, no service image changed and no retry followed.

Raw evidence:
`../output/deepswe-survey/testem-offline-qunit/public-test-logs/agentless-ml-311a4f133ea54924af4a2a507d7a03d6/`:
`offline-full-schedule.json`, `execution.json`, `report.xml`, service/preflight
events in `stdout.log` and `stderr.log`. The
[compact record](../experiments/deepswe/testem_qunit_full_schedule_2026_10_09.json)
keeps normalized/raw counts, the failure and inspected protections.
Fourteen focused host checks passed before execution, including both globs,
absence of filters/observer preload, and preservation of the shared command,
report and timeout contract.

Canonical readiness remains **100/113**. No held-out tests or solutions were
read, and no canonical survey record or shared benchmark configuration changed.
KGateway, Numba and Pwntools remain parked.

Next, verify the exact public QUnit 2.9.2 JS/CSS and assess adding them alongside
the existing 1.20.0 assets in another explicitly labelled image. Then check the
unchanged todo test before requesting another full schedule. No retry started.
