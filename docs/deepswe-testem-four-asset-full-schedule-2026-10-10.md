# Testem: passing full public schedule in the four-asset condition

The unchanged full public schedule passed in **61.734 seconds**, exit code 0:
**497 passed, three skipped, zero failed** across 500 distinct test IDs.
This is a passing baseline in the explicitly labelled offline-delivery
environment, not a repair result or a canonical readiness update.

The last remaining failure from the preceding full run,
`ci mode app::handles todos correctly`, now passes. Its public fixture can
load the exact QUnit 2.9.2 assets alongside the separately pinned 1.20.0 files.
No test, assertion or todo behavior was changed.

## Same schedule and protections

One authorized attempt ran in the existing four-asset image
`sha256:e12cec1885154964e390345726e5ae53955831965fc1340f1cd5b9f11220328f`
against sealed revision `158f61ea91c9613d2011c41ee9be40ada1d7a307`.
No rebuild or asset update was needed. The entry point checks that the build,
delivery preflight and successful targeted test refer to this exact image.

Both original public globs ran: `tests/*_tests.js` and `tests/**/*_tests.js`.
The full path uses the shared Mocha/xUnit command, without `--grep`, observer
preload or prototype instrumentation. The proven writable HOME setting and
four-file HTTP service are the same as in the targeted check. The supervisor
checks the exact asset responses and service liveness, preserves the test
process exit code and stops its owned service on completion.

The 1,800-second cap, report parser and failure-code contract were unchanged.
Actual Docker inspection confirmed network=none, read-only root, cap-drop=ALL,
no-new-privileges, no privileged mode, 8 GiB memory with no extra swap,
two CPUs, 2,048 PIDs and the same 4 GiB executable/nosuid/nodev /tmp.
The only added hostname mapping points code.jquery.com at container loopback;
no port is published. The service delivered pinned public asset bytes, not
test responses or fabricated success. The owned container was removed and
the scoped host keep-awake request released.

Nineteen focused host checks passed before execution, including preservation
of both public globs, absence of observer/filter flags, unchanged timeout and
report contracts, and the four-asset full action's prior-success guard.

## Counts and evidence

The raw XML contains 503 testcase nodes: 500 passed, three skipped and zero
failed. Two passing IDs repeat: Config's isCwdMode case appears three times,
and Launcher's stderr case twice. The existing normalization produces 497
passed and three skipped across 500 IDs; no counting rule changed.

The [compact record](../experiments/deepswe/testem_qunit_todo_full_schedule_2026_10_10.json)
retains normalized/raw counts, inspected protections, delivered hashes and
log/report digests. Raw `execution.json`, `offline-full-schedule.json`,
`report.xml`, `stdout.log` and `stderr.log` remain under
`../output/deepswe-survey/testem-offline-qunit-todo/public-test-logs/agentless-ml-28d7832522794599b495ee64ebb7f69b/`.
The run can be requested explicitly with `PYTHONPATH=src`:

```text
python tools/testem_qunit_todo.py full
```

No held-out tests or solutions were used. No further retry has started.
Canonical readiness remains **100/113** because the shared task configuration
and official survey have not been updated to use this labelled environment.
KGateway, Numba and Pwntools remain parked.

Next: review registering this verified setup for Testem, then refresh its
official readiness survey. This run establishes that the full public baseline
passes in this environment; it does not silently promote the diagnostic image.

Follow-up: the approved [registration and official refresh](deepswe-testem-registered-readiness-2026-10-10.md)
completed with another passing full baseline. The official count is now 101/113,
including Testem's explicitly registered modified environment. This earlier
diagnostic record and the original published-image pin remain unchanged.
