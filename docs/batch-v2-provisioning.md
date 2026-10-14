# Batch provisioning instead of repository-by-repository debugging

NodeBB is parked. Preserve its complete no-bail diagnostic: 8,092 cases,
8,089 passes and three investigated existing failures. Do not build more cache
images, retry its suite or promote that connected non-default condition to
official/default readiness. The evidence covers the one pinned development
task, not all 38 NodeBB tasks.

`tools/batch_v2_provisioning.py` separates cheap corpus inventory from a small
runtime pilot. It reuses the answer-free, digest-pinned V2/V1 loaders and reads
no hidden verifier or reference solution. This is engineering triage, not a
model experiment or eligibility declaration.

## Inventory

One Docker image listing is matched against all 642 task descriptions. The
output records repository, language, base commit, required image, local-image
availability, host-checkout presence, existing reviewed smoke scope and parked
status. Directory presence does not prove sealing; image presence does not
prove its revision or runtime works. `inventory.json` is a pre-execution
snapshot; pilot checks are reported separately.

## Bounded pilot

The default selects five different repositories, excluding NodeBB. Within each
repository it prefers a task with a local image and reviewed smoke. Across
repositories it prefers language coverage, then local images/reviewed smokes,
then lexical order. Selection is deterministic for a fixed corpus and local
image inventory. The size is explicitly limited to 1–11 repositories.
This availability bias is disclosed; the pilot is not a representative random
research sample and may select tasks whose images are missing.

With `--execute-pilot`, each selected local image resolves to an immutable ID.
A read-only, offline container checks its `/app` or `/testbed` HEAD against the
pinned commit, archives committed source into disposable scratch, checks that
the new workspace accepts a temporary file, and confirms it contains no Git
directory. No repository code or package lifecycle script runs in this probe.
The cap is 120 seconds, with one CPU, task-declared memory, 4 GiB scratch,
disabled swap, dropped capabilities and no host mounts or published ports.
This tests Linux source extraction/writability, not repair application or
complete dependency installation.

For existing reviewed syntax/selected-test plans only, the pilot also reuses
the survey's sealed host-checkout and fresh-workspace smoke execution. It
refuses to launch a full public suite. The existing reviewed command and cap
are preserved. An inventory-only call launches no containers.

Results distinguish missing images, image-pin mismatches, workspace failures,
missing public plans, smoke failures and smoke successes. The script never
pulls images, fetches repositories, installs dependencies, calls a model or
changes readiness. JSONL results are flushed after each task so an interruption
does not erase completed results. Existing unrelated local helper edits are
not overwritten.

## Use

Supply `--v1-parquet`, `--v2-tasks`, `--repositories` and a new `--output`
directory. Add `--pilot-size 5 --execute-pilot` for the bounded runtime pilot;
omit execution for inventory and selection only. Keep `inventory.json`,
`pilot.jsonl`, `summary.json` and execution artifacts together.

Manual work follows evidence: provision a missing selected image before calling
it a framework defect; inspect an actual workspace error before adding a
repository-specific workaround; expand public checks only where the pilot
justifies it. A syntax smoke does not become a passing test suite. Do not
extrapolate a few successes into readiness for all tasks in a repository.

## First pilot result

The first batch inventoried all 642 tasks across 11 repositories. Four task
image tags were available locally, including the parked NodeBB task. The
five-repository pilot selected Go, Python, TypeScript and JavaScript tasks.

- Vuls passed its workspace probe and selected public Go test.
- Qutebrowser passed its workspace probe and existing Python syntax check.
- Tutanota passed its workspace probe and existing TypeScript syntax check.
- Element Web and Ansible were reported as `needs_local_image`; neither ran.

No new provisioning failure appeared in the three executed tasks. These are
previously provisioned development tasks, so they do not establish that unseen
repositories work. The two missing images are availability gaps, not evidence
of framework defects. No image was downloaded, no full public suite or NodeBB
task ran, and no readiness count was promoted. All disposable containers and
workspaces were cleaned up. Twelve focused batch/survey checks passed.

The [pilot evidence](../experiments/swe_bench_pro/v2_batch_pilot_2026-10-14.json)
pins the corpus, helper and full local reports. The 642-row inventory, task
journal and execution artifacts remain under the parent workspace's
`output/swe-bench-pro-v2-readiness/2026-10-14-batch-pilot`.

Next: review the selected Element Web image's public manifest/size, provision
that one image within available disk capacity, resolve its immutable ID and
run the same cheap workspace probe. Then choose a bounded public check from
its actual base configuration. Do not launch all 642 images or begin another
full-suite debugging campaign merely because a plan is absent.

## Element Web follow-up on 15 October 2026

The selected Element Web image is now installed. Its public manifest contains
28 layers totalling 1,836,078,995 compressed bytes (1.84 GB / 1.71 GiB). Before
pulling, the host had about 195 GiB free and Docker's filesystem about 826 GiB.
These figures were ample for this one-image step; no cleanup was performed.
Compressed totals are not unpacked size or incremental disk requirements.

`tools/provision_v2_pilot_image.py` provisions one explicit non-parked task,
verifies its raw manifest against the public digest, applies a bounded
compressed-size/host-free-space policy, pulls by immutable digest and checks
the local image's platform and registry identity. It refuses to replace a
different existing task tag. The local tag makes the verified image discoverable
by the next batch inventory. `--reuse-downloaded` verifies and probes an already
pulled digest without another pull. No public check or dependency install is
launched by this helper.

The first pull stalled around a recorded sleep/resume event. Only its verified
task-owned client was stopped; layers and logs were preserved. One fresh pull
of the same digest completed. Its first verification then exposed a helper
assumption: this Docker containerd image store uses the manifest digest as
image ID, unlike older config-digest IDs. Verification now supports both forms
while requiring the exact registry digest and, for a manifest-ID image, the
matching local descriptor. Seven focused checks passed, including rejection
of unknown IDs, conflicting descriptors, absent registry identity and the
wrong architecture. The downloaded image was reused, not downloaded again.
The engine's reported size is recorded separately; it is not labelled unpacked
size because its meaning differs by storage backend.

The reused cheap probe passed in 3.48 seconds: image HEAD matches
`4f32727829c1087e9d3d9955785d8a6255457c7d`, committed source extracts into
disposable Linux scratch, the workspace is writable, and no Git directory is
copied. The extracted workspace occupies 56,344 KiB. The probe was offline,
read-only outside scratch, capability-dropped and bounded as before. Its
container was removed; the requested image remains installed.

See the [provisioning evidence](../experiments/swe_bench_pro/v2_element_provisioning_2026-10-15.json)
for both digests, size figures, attempt history and report hashes. Element Web
is now `workspace_probe_passed_needs_public_plan`, not test-suite-ready.
No dependency installation, public test, model call or verifier ran. The first
batch's missing-image result remains historical evidence rather than being
rewritten. NodeBB remains parked.

Next: read Element Web's pinned public configuration and select one bounded
public check. That will test whether actual dependency/setup work is needed,
without immediately committing to its full test suite.

## Element Web public smoke result

The selected `test/unit-tests/utils/sets-test.ts` file passed all **five public
assertions** on 15 October 2026. `yarn test` uses the repository's Jest command;
the wrapper selects that one file, uses `--runInBand`, and saves native Jest
JSON and cache under `/tmp`. The original Jest configuration, jsdom environment,
global setup and after-environment hooks are preserved. No test source, setup
hook or configuration was replaced.

`tools/run_element_sets_smoke.py` verifies image HEAD, extracts committed base
source into `/tmp/work` without Git history, and links the existing image's
dependencies. Source-relative imports therefore use the extracted source,
not `/app/src`. The image stays read-only; the container has one CPU, 4 GiB
memory/scratch, 2,048 PIDs, disabled swap, no network and a 180-second command
cap. No install or package-bootstrap command ran. A read-only dependency link
was sufficient for this test invocation; that does not prove installs would
work against it.

The command exited 0 in 62.41 seconds including preparation. Native Jest JSON
shows one suite, exactly the five expected full test names, all passing,
with no pending tests or runtime-error suites. The diagnostic checks that
report independently rather than trusting an exit-only result. Native JSON
is retained as diagnostic evidence, not registered as a new framework-wide
reporting adapter. Two focused wrapper/report checks passed, and the disposable
container was removed.

See the [smoke evidence](../experiments/swe_bench_pro/v2_element_sets_smoke_2026-10-15.json)
for all five outcomes, source hashes, report digests and limits. This upgrades
the engineering observation from workspace-only to a successful selected
public smoke, not full-suite or task-correctness readiness. No official verifier
or model call ran; NodeBB remains parked.

Next: provision the selected Ansible image and reuse the same cheap workspace
probe. Element Web does not need more manual debugging based on this smoke;
expand repository coverage before considering broader tests here.
