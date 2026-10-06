# Arktype and Clack public baselines — 6 October 2026

Both delegated test scripts now have working public-baseline commands:
Arktype reports **1,678 passes** and Clack reports **640 passes**, with no
reported failures or skips. The latest DeepSWE readiness count is **90/113**,
up from 88/113 before these two checks.

## Arktype: follow the alias without changing its scope

The root `test` script is `pnpm testTyped --skipTypes`. The `testTyped` script
invokes Mocha and excludes `ark/attest/**/*.test.*`. Previously discovery found
the Mocha dependency but could not derive arguments from the delegated script.

The reviewed override invokes Mocha with that same exclusion and `--skipTypes`.
Mocha still reads the root package's declared globs, TypeScript loader,
`ark-ts` condition, timeout and global setup. We did not add a new test filter
or turn type checking off ourselves: `--skipTypes` is already in the public
root script. This baseline is that runtime schedule, not Arktype's separate
type-checking, benchmark or multi-version jobs.

Installed dependencies are copied into writable temporary storage. Relative
`@ark` workspace links then resolve into the candidate's `ark` packages rather
than the image's `/app` source. The built-in Mocha JSON reporter writes directly
to its report file, keeping setup logging separate from report data. No new
reporter dependency is installed.

## Clack: build first, then run both package suites

The root `pretest` runs `pnpm run build`; its `test` recursively invokes package
tests. Core and prompts both declare `vitest run`. The two example packages
have no test script, so there are two public suites to execute.

The new command copies installed dependencies while preserving relative
workspace links, runs the root build script against the candidate, and then
runs Vitest from each package with its existing configuration. Build failure
exits before tests. Core's and prompts' JUnit cases receive package prefixes
when merged, so equal test names cannot collide. Narrowed targets are refused
for this multi-suite command rather than silently ignored.

## Check that candidate code is actually tested

A passing baseline alone would not catch a runner using `/app` instead of the
candidate. We ran a separate probe for each task in a fresh temporary checkout.
Each probe added a source-only export and two tests importing it through the
workspace package name: one assertion had to pass, and one deliberate failure
had to be detected.

Arktype's probe imported the new export from `@ark/util`. Clack's prompts probe
imported it from `@clack/core`, exercising the rebuilt cross-package dependency.
Both runners reported exactly one passing visibility test and one failing
probe test. The sealed repositories were not edited, and probe results were
not appended as baseline evidence or included in readiness counts.

The opt-in tests preserve this check for future runner changes:

```powershell
$env:AGENTLESS_DELEGATED_TASK_REPOSITORIES = '<sealed repositories directory>'
$env:AGENTLESS_DELEGATED_TASK_ARTIFACTS = '<separate probe artifacts directory>'
.\.venv\Scripts\python.exe -m pytest tests/test_deepswe_execution.py `
  -k delegated_runner_detects_candidate_workspace_source -q
```

## Conditions and evidence

Both baselines used the sealed base revision and pinned published image,
8 GiB of memory, two CPUs, 4-GiB tmpfs and a 1,800-second timeout. Baseline
survey durations were about 57 seconds for Arktype and 42 seconds for Clack.
The probes used the same limits with a 600-second timeout. Networking remained
disabled. No model, held-out tests or reference solutions were used.

[The evidence summary](../experiments/deepswe/delegated_runners_2026_10_06.json)
records both baselines, candidate probe test IDs and statuses, pinned identities
and execution hashes. Raw reports and logs remain outside Git under
`../output/deepswe-survey`; probe logs are in `candidate-probes/delegated`.
The reviewed reasons are in
[the task overrides](../experiments/deepswe/test_overrides.json).

All **75 command tests passed**, and both opt-in Docker candidate tests passed.
The full local suite passed with **598 passed and 21 skipped**. The two new
candidate checks are opt-in and skipped in that general run; they were executed
separately as described above. The other skips are existing opt-in integration
checks and host-native symlink checks.

Other tasks retain their previous outcomes. These runs establish public
regression inventories, not task-solving results.

Next: review Optique's Deno workspace and Valibot's delegated package tests,
the two remaining `no_runner` tasks.
