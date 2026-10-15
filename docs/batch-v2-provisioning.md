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

## Ansible provisioning follow-up

The selected Ansible image was provisioned on 15 October 2026. Its selected
Linux/amd64 manifest contains 18 layers totalling 745,700,455 compressed bytes
(746 MB / 711 MiB). Host free space was about 189 GiB before the pull, well above
the helper's 20-GiB minimum. Only that one image was pulled; no cleanup ran.

The public tag points to an OCI index containing one Linux/amd64 image and an
unknown-platform attestation. The original leaf-only helper stopped before any
download. It now verifies the index's exact bytes against its public digest,
selects exactly one supported Linux/amd64 descriptor, and verifies that child
manifest's bytes against the digest recorded in the index. Missing or ambiguous
platform choices are rejected, not guessed. The pull and local-image check use
the child digest; both parent and child digests remain in the evidence. This
extends the common provisioning helper, not Ansible's code or tests.

The same cheap workspace probe passed in **4.23 seconds**. Image HEAD matches
`f7234968d241d7171aadb1e873a67510753f3163`; committed source extracts into
disposable Linux scratch, the workspace accepts writes and no Git directory is
copied. The extracted workspace uses 27,984 KiB. Existing read-only roots,
offline probing, capability dropping, task-memory/one-CPU/4-GiB scratch and
120-second probe bounds were retained. The container was removed normally;
the verified image remains installed and tagged for batch discovery.

See the [Ansible provisioning evidence](../experiments/swe_bench_pro/v2_ansible_provisioning_2026-10-15.json)
for exact identities, sizes, attempt history and report hashes. Eight focused
provisioning/batch checks passed. No dependencies were installed, no public
tests or full suites ran, and official readiness is unchanged. Ansible is now
`workspace_probe_passed_needs_public_plan`; NodeBB remains parked.

Next: select one bounded Ansible public unit-test check from its pinned
configuration. Do not expand directly to its full integration matrix.

## Ansible public smoke result

All six tests in `test/units/module_utils/parsing/test_convert_bool.py` passed
on 15 October 2026. The command finished in 4.46 seconds including source
preparation. It used the pinned repository's `ansible-test units` runner,
Python 3.11.13, one worker and the original pytest configuration.
`--requirements-mode skip` disabled dependency installation. The existing
JUnit reader verified exactly the six expected test IDs, all passing.

`tools/run_ansible_boolean_smoke.py` checks image HEAD, extracts committed
source into `/tmp/work`, and runs that copy's runner. Its Python paths point
to the extracted source; Ansible's module-utils isolation links that source,
not the image's `/app/lib`. HOME is writable `/tmp`. The image root remains
read-only, with one CPU, 4 GiB memory/scratch, 2,048 PIDs, no network and a
180-second cap. No tests or configuration were edited. Ansible warned that
it used `C.UTF-8` rather than `en_US.UTF-8`; the warning is retained rather
than suppressed. The disposable container was removed normally.

See the [Ansible smoke evidence](../experiments/swe_bench_pro/v2_ansible_boolean_smoke_2026-10-15.json)
for individual outcomes, source fingerprints and report hashes. Four focused
checks for the Ansible and Element wrappers passed. This establishes one
selected public smoke, not full-suite readiness, repair correctness or an
official score. No model or verifier ran. NodeBB remains parked.

Next: consolidate the five-repository pilot results and choose a bounded
expansion across the remaining repositories. Avoid turning each successful
smoke into a full-suite debugging campaign. These standalone smoke wrappers
are evidence; they do not yet register new public plans in the batch helper.

## Consolidated pilot and repository expansion

The original five-repository pilot now has successful workspace evidence for
all five selected tasks, but the public-check coverage is deliberately uneven:

| Repository | Strongest public-check evidence |
| --- | --- |
| Vuls | Selected Go test passed |
| Qutebrowser | Syntax check only |
| Tutanota | Syntax check only |
| Element Web | Five selected Jest assertions passed |
| Ansible | Six selected unit tests passed |

None of these results establishes a full public suite or all revisions in
that repository. Earlier missing-image results remain historical evidence;
the follow-ups supplement them rather than rewriting them.

On 15 October, `--pilot-size 10 --execute-pilot --workspace-only` selected one
task from every non-parked repository. The new `--workspace-only` flag prevents
even an existing reviewed smoke from running. All five installed images passed
fresh extraction/writability probes (1.86–3.11 seconds each). The other five
repositories were recorded as `needs_local_image`, not failed tests. NodeBB
was excluded, and no dependencies, public tests or full suites ran.

The provisioning helper's new `--inspect-only` mode verified exact public
manifest bytes and selected Linux/amd64 child manifests where an index was
present. It downloaded no image layers and started no containers. All five
new repository manifests were available:

| Repository | Selected image's compressed layers |
| --- | ---: |
| Navidrome | 924 MB |
| Open Library | 1,071 MB |
| Flipt | 1,933 MB |
| Teleport | 3,500 MB |
| Proton Mail webclients | 6,518 MB |

These are decimal compressed totals, not unpacked disk use or incremental
download estimates. Exact task IDs, immutable digests, base revisions, sizes
and batch artifact hashes are in the
[consolidated evidence](../experiments/swe_bench_pro/v2_expanded_pilot_2026-10-15.json).
Fourteen focused checks passed, including explicit tests that workspace-only
cannot launch a smoke and inspect-only cannot pull, tag or probe an image.

The next bounded runtime follow-up selects Navidrome, the smallest verified
image, rather than pulling all five at once. No official readiness count is
promoted by inventory, manifest verification or workspace checks.

### Navidrome runtime follow-up

That single follow-up completed successfully. The helper pulled Navidrome by
the verified Linux/amd64 digest, verified the local image identity and retained
its task tag. The same protected workspace probe passed in **3.90 seconds**:
HEAD matched `2f90fc9bd40e24afd900b5ee85426f32684b960b`, committed source
extracted into scratch, and the extracted workspace accepted writes without
Git history. No repository code, dependency installation or tests ran.

The [Navidrome provisioning evidence](../experiments/swe_bench_pro/v2_navidrome_provisioning_2026-10-15.json)
retains exact image identities, probe results and artifact hashes. The earlier
ten-repository batch snapshot still records five passes and five missing
images; this follow-up brings cumulative selected-task workspace coverage to
**six repositories**, with **four** still needing images. NodeBB remains
parked. None of those counts means full-suite or benchmark-task readiness.

Next: choose one bounded public Navidrome check from its pinned configuration.
For further runtime breadth, Open Library is the next-smallest verified image
(1.07 GB compressed); provision it separately rather than downloading the
remaining four as a batch.

### Selected Navidrome public check (not run)

Select `utils/number/number_test.go`, the complete `./utils/number` package.
It has six Ginkgo specs: empty arguments, integers and floats for each of
`Min` and `Max`. The package needs no server, database, music files or external
service. Its direct implementation imports `golang.org/x/exp/constraints`;
the image contains that module and the pinned Ginkgo/Gomega dependencies,
but dependency resolution is not yet proven by a build.

The public Makefile uses `go test -race ./...`; the pinned CI adds coverage
and verbose output. Keep those settings while narrowing the package:

```sh
go test -race -cover -v -json -count=1 -p 1 -timeout 120s ./utils/number \
  -args -ginkgo.junit-report=/tmp/navidrome-number.xml
```

The eventual wrapper should verify HEAD, extract source into `/tmp/work`, use
the image's read-only module cache and fresh writable build scratch, and cap
the complete invocation at 180 seconds, including compilation. Disable
dependency downloads and automatic toolchain downloads for this bounded
check. Preserve the existing 1-CPU, 4-GiB memory/scratch, read-only-root and
capability protections. Save Go JSON and native Ginkgo JUnit, then require
all six individual specs to pass; the single `TestNumber` wrapper is not six
individual results. Ginkgo's installed public source confirms its JUnit flag.

The image provides Go 1.24.3, whereas the pinned CI matrix used Go 1.18/1.19.
Record this as an image-native smoke, not historical toolchain parity. No
tests, configuration changes, dependency installs or compilation ran during
selection. Exact source hashes, proposed environment and expected spec names
are in the [selection record](../experiments/swe_bench_pro/v2_navidrome_number_selection_2026-10-15.json).

Next: implement the small diagnostic wrapper and run this one package, retaining
setup failures or timeouts if they occur. Do not expand to the full suite.

### Navidrome number wrapper

`tools/run_navidrome_number_smoke.py` implements that selected check. It uses
the existing Docker runner and JUnit reader, checks exactly six expected spec
IDs, and refuses to count Go's single `TestNumber` wrapper as six passes.
Build outputs use fresh writable scratch; no image build cache is copied.
The module cache remains read-only, dependency downloads are disabled and
source/configuration hashes are printed before execution.

The first attempt compiled successfully, then Ginkgo rejected the proposed
explicit Go `-parallel 1` flag before executing specs. It exited 1 after
47.31 seconds and produced no JUnit report, correctly recorded as a harness
error rather than a failed test or a passing smoke. The wrapper now omits
that incompatible flag. Ginkgo remains serial by default, with `GOMAXPROCS=1`,
one build worker and the same CPU/resource/time limits. The selection record
retains the original proposal; the runnable command above reflects this
correction. No repository tests or configuration were changed.

The corrected run passed **all six individual specs** in **55.99 seconds**,
including preparation and fresh compilation. Race detection and coverage
remained enabled. Native Ginkgo JUnit is retained as `report.xml`; Go JSON
events are retained in `stdout.log` after the version/source-hash preamble.
The evidence includes both attempts and artifact hashes:
[Navidrome number smoke](../experiments/swe_bench_pro/v2_navidrome_number_smoke_2026-10-15.json).
Fifty-one focused report-parser, provisioning and wrapper checks passed;
the other two smoke wrappers also passed their four checks in the initial
seven-check wrapper run. All diagnostic containers were removed normally.

This establishes a selected public test package, not the full suite, a
historical CI reproduction or task-specific repair correctness. The image's
Go 1.24.3 toolchain difference remains declared. No dependency installation,
model call, official verifier or NodeBB run occurred. Official readiness is
unchanged; the standalone wrapper is not yet a registered batch public plan.

Next: extend runtime breadth to Open Library using its already verified
1.07-GB-compressed image, then reuse the cheap workspace probe before choosing
a public test. No further Navidrome suite expansion is needed for this pilot.

### Open Library provisioning follow-up

The selected Open Library image has 22 layers totalling 1,070,952,548
compressed bytes (1.07 GB). Provisioning uses the previously reviewed
Linux/amd64 digest
`sha256:03205f63224d992c930df7a2b898353d9d3dface4ab4d921eebc73dc909c1ba6`.
The helper now accepts `--expected-manifest` and rejects a changed selected
digest before downloading layers, tagging an image or running a probe. This
run supplied that exact reviewed digest. Matching, mismatched and omitted-pin
paths are covered by focused tests; all twelve provisioning/batch checks
passed.

The existing disk policy still applies: at most 8 GiB compressed per selected
image and host free space of at least the larger of 20 GiB or four times the
compressed total. This run had about 182.55 GiB free before the pull. Only
the selected image is provisioned; no cleanup, cache supplements or other
repository downloads are part of this follow-up.

The pull completed and the same cheap workspace probe passed in **3.72
seconds**. Image HEAD matched
`02f647f7d525286b6e3a661133c3772649e585cd`; committed source extracted into
disposable Linux scratch, accepted a temporary write and contained no Git
directory. The image stayed read-only, with offline probing, dropped
capabilities, no host mounts, one CPU, task-declared memory, 4 GiB scratch,
disabled swap and the existing 120-second cap. The disposable container was
removed; the verified image remains installed with its task tag.

See the [Open Library provisioning evidence](../experiments/swe_bench_pro/v2_openlibrary_provisioning_2026-10-15.json)
for the exact image/base identities, limits, probe outcome and artifact hashes.
Only one image was pulled. No dependency install, repository test, model call,
official verifier or NodeBB run occurred. Cumulative selected-task workspace
coverage is now **seven repositories**; Flipt, Teleport and Proton Mail
webclients still need local images. These are engineering observations, not
full-suite readiness or a changed official readiness count.

Next: inspect Open Library's pinned public test configuration and select one
bounded check before running any tests. Do not jump to its full service stack
or test suite.
