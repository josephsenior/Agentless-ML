# Testem: the unchanged public QUnit test passes offline

The selected public test **passed with exit code 0** in the separately labelled
offline-asset condition. The runner recorded 14.234 seconds including setup,
preflight and report collection. This is one public test, not a full baseline.

The test was `ci mode app multiple launchers returns successfully with passed
and skipped tests`. Its source, assertions, browser arguments and public timeout
were unchanged. The existing diagnostic observer retained the original reporter
methods' inputs and decisions without replacing them. The fresh sealed candidate
was at `158f61ea91c9613d2011c41ee9be40ada1d7a307`.

## Labelled environment and actual results

The run used the built offline-asset image
`sha256:96b08a03e607416b109f7d86186d1cdfe92755483eada98693e67ff5f2feba00`,
HOME-only under /tmp, and the owned loopback service. The two pinned QUnit
1.20.0 files were delivered through the per-container code.jquery.com mapping.
Template URLs and asset bytes were not edited; no external access or TLS bypass
was introduced.

Before executing the test, the supervisor verified the image files and fetched
both assets over HTTP, checking size, hash and MIME type. Startup, preflight or
service-liveness failures return undeclared exit 125, a harness error rather
than an ordinary test outcome. The public command's original exit was preserved.

The real Firefox reporter produced:

- `says hello world`: passed, including its hello-world assertion.
- `works without content`: passed.
- `says hello to person`: skipped, as declared by the fixture.

Counters were total=3, passed=2, skipped=1, todo=0; original `hasPassed()`
returned true. The outer Mocha report contained one passed public test. These
are two levels of results, not four passing public tests. The missing favicon
still produced its ordinary 404 log and did not fail the test. No assertion or
failure was suppressed.

## Protections, evidence and next step

Actual Docker inspection confirmed network=none, read-only root, all
capabilities dropped, no-new-privileges, no privileged mode, 8 GiB memory without
extra swap, two CPUs, 2,048 PIDs and 4 GiB executable/nosuid/nodev /tmp. Only the
declared code.jquery.com loopback mapping was added. No port was published,
credential mounted or external network created. The owned service and container
were removed and the scoped Windows keep-awake request released.

Raw evidence is under
`../output/deepswe-survey/testem-offline-qunit/public-test-logs/agentless-ml-afd7341f486145298efff61ecff2bdae/`:
`offline-public-test.json`, `execution.json`, `report.xml`, observer/service
events in `stdout.log` and Testem logs in `stderr.log`. The
[compact record](../experiments/deepswe/testem_qunit_public_test_2026_10_09.json)
preserves the actual reporter results and inspected protections. Fourteen
focused host-side checks passed, including command/report/exit preservation.

No full-suite retry started, no shared benchmark configuration changed, and no
held-out tests or solutions were read. Canonical readiness remains 100/113.
This does not prove recovery of the other full-suite failures or live-CDN access.

The subsequent [unchanged full schedule](deepswe-testem-offline-full-schedule-2026-10-09.md)
completed in 48.282 seconds: 496 passed, three skipped and one failed after
normalization. The remaining todo fixture requests unsupported QUnit 2.9.2
assets. No additional assets or test retry followed.
