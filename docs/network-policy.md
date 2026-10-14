# Network access belongs to an execution phase

We previously disabled Docker networking for every public-test run. That was
our harness default, not a property of Agentless. It also made legitimate
dependency downloads look like repository setup failures.

The [official SWE-bench Pro V2 locked protocol](https://github.com/scaleapi/SWE-bench_Pro-os/blob/main/v2/README.md#the-locked-protocol),
reviewed on 14 October 2026, distinguishes the phases: agent execution has no
network except the model endpoint, while setup and verification have normal
access. Final scoring replays the exported patch in a pristine environment.
This policy does not automatically apply to DeepSWE; its intended runner
settings need a separate review before changing them.

The locally pinned NodeBB `task.toml` agrees explicitly: `[agent]` uses
`no-network`, while `[environment]` and `[verifier]` use `public`. Its SHA-256
is `34eeb52a87d513adbdbf6996612ced8027707cb3efb293c39022f2009c8d52b2`.
Thus the phase distinction is present in our task files, not just today's
upstream README. Our connected baseline is a setup diagnostic, not an official
verifier run or an exemption for agent-side public-test feedback.

## What changes locally

The Docker runner now records its execution phase and network mode. Its default
is still `agent` / `none`. It refuses connected agent-phase execution, and the
candidate-selection entry point rejects non-agent or connected runners.
Trusted setup, unchanged-base diagnostics and final verification can explicitly
request Docker bridge networking. This is normal egress, **not** a hostname
allowlist or a guarantee that private-network addresses cannot be reached.
Only reviewed commands should use it; do not feed it arbitrary candidate code
during selection. Merely setting a phase label does not establish trust.

Read-only container roots, capability dropping, no-new-privileges, no host
credentials/socket mounts, disposable workspaces and resource limits remain.
There are no published ports. This is not a global switch to connected testing.

`tools/run_nodebb_network_baseline.py` is an explicit unchanged-base diagnostic.
It verifies the sealed pinned repository, creates an unpatched workspace and
uses the original NodeBB image, live registries, and the existing Redis/public
test configuration. It disables npm's offline flag rather than adding more
cache workarounds. `--probe-only` checks two fixed public JSON endpoints;
`--full-suite` runs the existing full public schedule and individual reporter.
The same one CPU, 4 GiB memory, 4 GiB scratch and 30-minute suite cap remain.
The probe has its own 60-second cap. It does not install packages or run tests.

Network-enabled baseline results are diagnostic evidence, **not** an inventory
to silently combine with offline candidate results. Candidate public-test
checks are part of the agent-side workflow even when a controller runs them:
if they affect patch selection, their information/network policy matters.
The experimental protocol still needs to declare a matching setup for those
checks and for Grinta. Final verification remains separate; this change does
not run or modify the held-out verifier.

## Work we are pausing

Do not build an Imgur cache supplement or extend the registry snapshot service
just to satisfy our former blanket offline requirement. Keep the previous
snapshots, checksum manifests, images and reports as labelled historical
evidence. They have not been deleted or reclassified as official results.
No existing readiness count changes merely because networking is available.

## Verification on 14 October 2026

The original pinned image successfully reached both public registry endpoints
over HTTPS. Both returned HTTP 200 and agreed on Imgur `latest=5.0.0`.
See the [probe evidence](../experiments/swe_bench_pro/v2_js_nodebb_upload_path/network-probe-2026-10-14.json).
Normal container/workspace cleanup completed. The full runner elapsed time was
124.66 seconds including source preparation; the command cap remained 60 seconds.
The probe ran no tests, verifier, dependency installs or model calls. There was
no cache image build or full-suite retry. The focused policy/NodeBB checks
passed (66 tests; eight optional Docker integration cases skipped).

## Connected full public suite result

The requested full suite ran once on the unpatched base with the original
image, live registries, `CI=true` and npm offline mode disabled. It reached
**3,321 passes and one failure**. The run took 333.41 seconds including runner
preparation; Mocha itself took 173.33 seconds. The same limits and public bail
setting remained in place. No snapshot service or cache supplement was used.

The missing-cache error is gone. The same plugin-install test now fails with
`EROFS`: npm tries to rename `/tmp/work/node_modules/.bin/acorn`. Our setup
links `.bin`, like the other dependencies, into the read-only image at
`/app/node_modules`. Networking does not make that dependency layout writable.
This is another harness setup issue, not evidence that the repository repair
or Imgur plugin is faulty.

The completion audit accounts for 7,986 registered tests and 3,322 ended tests;
4,664 did not run after bail. Individual and raw reports agree, with no hook
failures. The baseline remains incomplete, and it is not eligible for offline
candidate selection. See the [full-run evidence](../experiments/swe_bench_pro/v2_js_nodebb_upload_path/network-full-public-2026-10-14.json)
for the exact failure and report hashes. Normal container/workspace cleanup
completed. No retry, verifier, image build or model call followed.

The [writable-dependency assessment](nodebb-writable-dependencies.md) now shows
that a complete private dependency copy fits the same CPU/memory/scratch ceilings
and supports both executable and package-directory writes without altering the
image. This is a copy-only diagnostic, not a successful npm transaction or a
full-suite retry. The subsequent [public lifecycle diagnostic](nodebb-writable-dependencies.md#public-lifecycle-result)
passed all five unchanged cases with that copy and normal networking. Next is
the unchanged full schedule using the same layout, without the group filter.
No full-suite retry has started and agent-side candidate checks remain offline.
