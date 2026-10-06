# Optique and Valibot public baselines — 6 October 2026

Optique now reports **3,046 passes and ten skips** on its public Node schedule.
Valibot reports **4,509 passes**, with no reported failures or skips. These
recoveries bring the latest DeepSWE readiness count to **92/113**. No tasks
remain in `no_runner`; the other 21 tasks still have their existing blockers.

## Optique: use the public runtime the image actually supplies

Optique is organized as a Deno workspace, but its pinned published image has
Node 24.12.0 and no Deno executable or Deno cache. Its public `deno.json` also
declares `test:node`, which recursively runs the package test scripts.

We use that declared Node schedule rather than installing a new runtime. All
nine packages with test scripts are included: core, config, git, logtape, man,
run, temporal, valibot and zod. The example and documentation packages have no
test script. Dependencies are copied with their relative workspace links, all
nine candidate packages are rebuilt, and each Node suite runs with the public
`--experimental-transform-types` flag. Man retains its explicit source glob;
the other packages retain Node's default discovery.

The built-in Node JUnit reporter supplies the per-test results. The ten skips
come from the public tests; we added no test exclusions. This is the Node
runtime schedule, not a claim that the Deno, Bun or combined `test-all` schedule
works in this image.

## Valibot: include all three delegated test packages

The root test script recursively runs three suites: `library` and
`packages/to-json-schema` use Vitest with `--typecheck`; `codemod/zod-to-valibot`
uses Vitest without that flag. The other workspace packages have no test
script. All three suites keep their existing configurations, and both declared
type checks remain enabled.

The candidate library is built before testing because the codemod's workspace
dependency resolves through the library's generated package exports. The JSON
schema converter also retains its configured source-path alias into the
candidate library. We do not borrow the image's built library. A failed build
stops the command before testing, and package-prefixed report IDs keep equally
named cases separate.

## What the candidate probes caught

Each live probe used a fresh temporary candidate checkout, added a source-only
export, and imported it through the package name from another package. One
probe test had to pass; another deliberately failed. The sealed repositories
were untouched, and probe results were not included in readiness counts.

The first Optique probe exposed a report-merger bug: Node placed the new cases
directly under the report root, while the merger only retained suites. The
failure exit was rejected as a harness error because the merged report had
lost the failing case. The shared merger now preserves root cases and nested
subtrees exactly once.

Review also found that Node gives many cases the classname `test`; equal leaf
names from different files or describe blocks were collapsing into one test
ID. The Node-specific merge now retains the file and enclosing suite path.
Optique's initial 2,765-pass inventory is superseded by the final 3,046-pass
inventory. This is corrected reporting, not newly added public tests.

Regression fixtures check root-level failures, nested suites, and equal names
in different files and contexts. Both final live probes passed: Optique's run
package imported the rebuilt core export, and Valibot's converter imported
the candidate library export. Both intentional failures were reported.

## Conditions and evidence

Both baselines used their sealed base revisions and pinned published images,
the declared 8-GiB memory limit, two CPUs, 4-GiB tmpfs and a 1,800-second timeout.
Probe timeouts were 600 seconds. Networking remained disabled. No model,
held-out benchmark tests or reference solutions were used.

[The evidence summary](../experiments/deepswe/optique_valibot_runners_2026_10_06.json)
records the final baselines, skip IDs, successful candidate probes, the initial
failed probe, image identities and execution hashes. Raw logs and reports stay
outside Git under `../output/deepswe-survey`.

Verification: **81 command tests passed**, **604 local tests passed with 23
skipped**, and **both new opt-in Docker candidate tests passed separately**.
The general run skips opt-in integrations and unavailable host-native symlink
checks. The two earlier delegated-runner probes remain covered by their
previous recorded runs.

Next: review Pwntools' public doctest entry point. Its current pytest schedule
collects no tests, so it remains a harness error rather than a usable baseline.
