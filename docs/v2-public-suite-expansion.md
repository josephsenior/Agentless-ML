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

NodeBB's full test setup is reviewed, not yet implemented or executed. Start
with its bounded offline setup and report-completeness check before registering
a full-suite result. Other Vuls or NodeBB tasks require their own base/image
checks; a successful run on one revision does not provision every task in that
repository automatically.
