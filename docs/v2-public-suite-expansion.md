# Expanding V2 public validation by repository

The four existing smoke checks prove that selected source files can be checked
in fresh candidate workspaces. This next pass reviews the normal public CI test
target of each repository and retains individual results. A plan being registered
does not mean its suite has run successfully.

## Vuls: complete public CI test target

At base `0cdc7a3af55e323b86d4e76e17fdc90112b42a63`,
`.github/workflows/test.yml` runs `make test`. Its `GNUmakefile` defines that
target as `GO111MODULE=on go test -cover -v ./...`. The
[reviewed plan](../experiments/swe_bench_pro/v2_go_vuls_header/public_suite.json)
pins those public files and the existing image. No benchmark verifier files
were used to select the command.

The wrapper adds `-json` for reporting and `-count=1` to prevent cached success.
It preserves coverage, verbosity and every package under `./...`. Module
downloads are disabled, the cache is writable under `/tmp`, and compilation
uses candidate source. It reuses the existing streaming Go-to-CTRF converter.
The run uses one CPU, 4 GiB memory, 4 GiB temporary scratch, disabled swap,
no network and the shared runner's existing container protections. The full
target has an explicit 1,800-second command cap, distinct from the earlier
600-second selected-test smoke and below this task's 3,000-second agent cap.
The pinned image reports Go 1.24.3; the historical CI file requested Go 1.16.x.
This run checks the published benchmark image, not an exact reconstruction of
that historical CI toolchain.

The complete `go list ./...` inventory and raw Go event stream are retained
beside the individual-test report. An additional audit checks terminal outcomes
for every discovered package, unfinished tests, duplicate outcomes and package
failures without an individual failing test. Some passing cases cannot hide
missing package execution or build failures. Failed assertions remain ordinary
baseline failures; incomplete coverage cannot become `public_suite_ready`.

"Complete" here means the entire normal `make test` target. The separate
`make diff` and Redis comparison workflows need external services and old/new
binaries; they are not part of that target and have not been provisioned.

The full-target registry is
[`v2_full_public_plans.json`](../experiments/swe_bench_pro/v2_full_public_plans.json).
Use it with the survey's `--plans` option. It is separate from the original
smoke registry so recorded development commands remain reproducible.

The first complete attempt on 13 October passed: **298 tests passed**, with all
25 packages accounted for (23 passed and two reported no tests). The package
audit found no missing packages, unfinished tests or unexplained failures.
Elapsed execution time including runner setup was 430.67 seconds. See the
[saved baseline evidence](../experiments/swe_bench_pro/v2_vuls_public_baseline_2026-10-13.json)
for raw event/report hashes and the exact implementation files used. All 68
focused reporter, survey, V2 adapter and scoring-boundary tests passed.

This is one full-target-ready task. The full-target registry reports the other
641 tasks as needing full public plans; the separate historical smoke evidence
for three other tasks is still valid and has not been overwritten.

## Next repository reviewed: NodeBB

The pinned NodeBB base `61d17c95e573f91ab5c65d25218451e9afd07d77`
defines `npm test` in `install/package.json` as
`nyc --reporter=html --reporter=text-summary mocha`. Public CI first copies that
manifest into the workspace root, installs dependencies, and runs
`node app --setup=... --ci=...` with separate application and test databases.
Its matrix includes Node 18/20 and MongoDB, Redis and PostgreSQL configurations.

A read-only probe of the already pinned image found Node 18.20.8, Mocha 11.1.0,
NYC 17.1.0 and `redis-server`. MongoDB and PostgreSQL server executables were
not on PATH. The next feasible setup to assess is the Redis CI variant, with
disposable container-local storage, databases 0/1 and no published host ports.
It would represent that backend variant, not the entire CI matrix.

The public `.mocharc.yml` enables `bail`. An individual report must therefore
also disclose early termination; a few passes before the first failure cannot
establish a complete baseline inventory. Do not silently disable bail or call
a partial report complete. Setup must generate outputs from candidate source,
and dependency links must not redirect source imports to `/app`.

Public files reviewed (SHA-256):

- `.github/workflows/test.yaml`: `e955029107b24a04208ea780fc903e49ef8cd3ed725ac3d9667b289ce02c4838`
- `install/package.json`: `4e246dfe3ae3c08bea90ac1075f7a07a9f7a68b1f49e20aa3411f2329c523651`
- `.mocharc.yml`: `5e170cc2b39f763c43f923bf13b99d91a86a85ae62d9024f133a5689b322b74d`

The Redis setup was then implemented in `tools/check_v2_nodebb_setup.py` and
passed one bounded offline diagnostic on 13 October. The pinned image's Redis
ran with disposable storage under `/tmp`, no host ports and separate databases
0/1. Public `node app --setup=... --ci=...` generated configuration and built
assets from candidate source. Setup and validation completed in 145.96 seconds
including runner preparation, under a 300-second command cap. See the
[setup evidence](../experiments/swe_bench_pro/v2_nodebb_setup_2026-10-13.json).
The combined focused checks now total 69 passing tests.

## NodeBB individual reporting and early termination

The Redis plan now runs the complete public `npm test` command after the same
candidate-source setup. NYC coverage and `.mocharc.yml` remain active. The
command changes the Mocha reporter and its output location; the public timeout,
file selection and `bail` setting remain as declared by the repository. The
overall command cap is 1,800 seconds under the existing one-CPU, 4-GiB memory,
4-GiB scratch and offline container profile.

`tools/nodebb_mocha_reporter.cjs` extends the installed Mocha JSON reporter. It
retains the unmodified JSON report as `mocha-raw.json` and writes a second report
with separate identities for repeated test names. Each identity consists of
the defining file, full title and occurrence number in registration order.
The derived report preserves `rawFullTitle`; the original report is also kept.
This avoids the shared parser's normal merging of exact-name reruns collapsing
NodeBB's distinct parameterized cases. The occurrence number depends on test
registration order and does not establish semantic identity if that order changes.

The reporter inventories loaded tests and observes additions to every suite.
That matters here: NodeBB's async API suite registers tests after Mocha starts.
At the end, the completion audit compares all registered identities with ended
tests and reported outcomes, checks counts, and records hook failures or aborts.
An ordinary end event after `bail` cannot establish complete coverage.

`tools/check_nodebb_mocha_reporting.py` verifies the actual installed Mocha on
five small fixtures: complete pass/pending coverage, early failure with bail,
failed setup hook, repeated names, and late registration. All five passed on
14 October; the 82 focused Python checks passed as well. Neither fixture
verification nor registration of a full-suite plan is a public baseline result.

The first public attempt on 14 October stopped at the admin plugins page:
`GET /api/admin/extend/plugins` returned HTTP 500 after requests to
`packages.nodebb.org` failed in the offline container. Raw Mocha totals were
296 passes and one failure. Its original reporter merged repeated display names
into 11 passing matching IDs and one failed ID; this exposed the identity issue
fixed above. The original attempt is retained under
`../output/swe-bench-pro-v2-readiness/2026-10-14-nodebb-full/`.

A fresh attempt with the final reporter reached the same failing assertion.
It preserved **296 passing cases and one failed case separately**. The final
inventory contained 4,506 registered tests: 2,011 present initially and 2,495
added after execution started. Only 297 ended; 4,209 did not run. The individual
report and completion counts agree. Both reports retain the underlying failure
and test identities; the original raw JSON remains available too.

The second attempt's host recorder was interrupted after test execution, so
its command exit code was not captured. `tools/recover_nodebb_public_run.py`
recovered the completed reports before its exact owned container and temporary
workspace were removed. The recovery records that interruption and cannot
promote a run to readiness. See the
[attempt evidence and hashes](../experiments/swe_bench_pro/v2_nodebb_public_attempt_2026-10-14.json).
NodeBB remains **not ready** for the complete public baseline. Vuls's earlier
full-target result is unaffected.

Next, assess whether the required public plugin-registry responses can be
verified and delivered through a labelled offline service. NodeBB exposes a
public `registry` setting for these requests. Review the actual data and service
contract before another full attempt; neither fabricated successful responses
nor disabling the failing test would establish the same baseline.

The [registry data assessment](nodebb-registry-assessment.md) now pins all four
reviewed public responses and specifies a local service contract. They are
consistent current snapshots, not historical task data. The
[labelled service replay](nodebb-registry-service.md) then verified exact
delivery and passed all seven admin plugins page cases within a complete
2,496-case public API-file run. A subsequent full public attempt restored the
required `CI=true` setting, passed 3,321 cases and stopped at the Imgur plugin's
missing offline npm installation data. The full completion audit remains
incomplete; see the [full-suite attempts](nodebb-registry-service.md#full-public-suite-attempts).

Other Vuls or NodeBB tasks still require their own base/image checks; success
on one revision does not provision every task in that repository automatically.
