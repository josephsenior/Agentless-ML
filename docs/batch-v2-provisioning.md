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

### Selected Open Library public check (not run)

Select the complete `openlibrary/tests/solr/test_query_utils.py` file. Static
inspection identifies **nine cases**: five query-tree removals, two subtree
replacements, one parser case and one field-replacement case. The tests and
their query implementation use in-process `luqum` parsing, not a live Solr
server. This count is source-derived; pytest collection has not run.

The public `make test-py` target uses pytest with exclusions for Infogami,
vendor and node_modules. Narrow that command to the selected file, preserve
`pyproject.toml` and inherited hooks, and add native individual reporting:

```sh
python -m pytest openlibrary/tests/solr/test_query_utils.py \
  --ignore=infogami --ignore=vendor --ignore=node_modules \
  -o cache_dir=/tmp/openlibrary-pytest-cache \
  --junitxml=/tmp/openlibrary-query.xml
```

Use the same protected disposable workspace, one CPU, 4 GiB memory/scratch
and 180-second complete-command cap. The image's Python 3.12.2 matches the
pinned project's narrow Python range. Installed metadata reports pytest
7.4.4 and luqum 0.11.0, matching the public requirements; this does not yet
prove all inherited imports work. No dependency installation is proposed.

There is one explicit prerequisite: `openlibrary/conftest.py` imports
Infogami. Preserve it, including its own autouse network/sleep restrictions;
do not bypass it with `--noconftest`, disable plugin loading, or replace its
mocks. The parent Git tree pins `vendor/infogami` to
`d918e184ca1b0de7e8d3b02ec7b7dc4a08453cea`. The image contains files there,
but its directory-level `rev-parse HEAD` resolves to the parent Open Library
commit, so it does **not** verify the submodule revision. Before supplying
those files to the extracted workspace, verify their exact public contents
against the required commit. An ordinary parent `git archive` omits them.
The JavaScript WMD submodule is not needed by the inspected test bodies;
do not provision it unless actual setup evidence requires it.

The [selection record](../experiments/swe_bench_pro/v2_openlibrary_query_selection_2026-10-15.json)
contains all nine expected node IDs, source fingerprints, proposed command
and setup caveats. No tests, collection, compilation or dependency installs
ran during this selection. Official readiness is unchanged; NodeBB remains
parked.

Next: verify the required Infogami contents, then implement a small wrapper
and run only this selected public file, retaining all nine individual results
or any setup error. Do not launch the full service stack or suite.

### Open Library query smoke result

The exact public Infogami commit was fetched into a separate bare reference
store. Its tree contains **222 regular tracked files**, with no tracked
symlinks or nested submodules. `tools/run_openlibrary_query_smoke.py` builds
a file/mode/Git-blob manifest from that commit and checks both the Open
Library image HEAD and its committed Infogami gitlink before setup.

`tools/verify_openlibrary_infogami.py` verified every image file's bytes against
the corresponding public Git blob and checked its executable mode. All 222
matched. Only those verified files were supplied to the extracted workspace;
image-only extras, including an extra link, were not copied. All files are
checked before anything is supplied, so a late mismatch cannot leave a
partial dependency copy. The committed top-level Infogami link is preserved.
Per-file SHA-256 fingerprints are retained alongside the public tree and
manifest digest. The public reference fetch occurred before execution; the
test container remained offline.

The selected public file then passed **all nine individual cases**. The entire
command, including extraction and verification, finished in **4.71 seconds**;
pytest reported 0.05 seconds for the test session. Native JUnit confirms the
exact expected cases with no skips or failures. The original pytest config,
inherited hooks, plugin loading and autouse fixtures were preserved. Project
imports resolve from `/tmp/work`, not `/app`. No dependencies were installed
and no tests were changed. Four third-party deprecation warnings are retained
in the log rather than suppressed.

See the [Open Library query smoke evidence](../experiments/swe_bench_pro/v2_openlibrary_query_smoke_2026-10-15.json)
for all nine outcomes, all 222 dependency fingerprints, public provenance and
artifact hashes. The container was removed normally. This establishes one
selected public file, not the full service stack, full suite or task-specific
repair correctness; official readiness is unchanged and NodeBB remains parked.
All 62 focused integrity, wrapper, report-parser and provisioning checks passed.

Next: extend workspace coverage to Flipt, whose public image manifest was
already verified (1.93 GB compressed). Provision only that image, then run the
cheap workspace probe before choosing any public test. No further Open Library
suite expansion is needed for this pilot.

### Flipt provisioning follow-up

The selected Flipt image contains 21 layers totalling 1,933,188,709 compressed
bytes (1.93 GB). The helper was given the previously reviewed Linux/amd64
manifest digest
`sha256:896e9e03b52384f2696043debe8cbf7c55334a6b5900570e6f4c91e0551d165c`
via `--expected-manifest`; the public index and selected manifest still match
the earlier preflight. Host free space was 184,772,161,536 bytes before the
pull, above the existing reserve. Only this one image is in scope; no cleanup
or cache-supplement build is requested. All twelve provisioning/batch checks
passed before execution.

The pull completed, the local image identity was verified and its task tag
retained. The unchanged cheap workspace probe passed in **5.99 seconds**.
Image HEAD matched `85bb23a3571794c7ba01e61904bac6913c3d9729`; committed
source extracted into disposable scratch, accepted a temporary write and
contained no Git directory. Offline probing, read-only image root, dropped
capabilities, no host mounts, one CPU, task-declared memory, 4 GiB scratch,
disabled swap and the 120-second probe cap were unchanged. The disposable
container was removed normally; the verified image remains installed.

The [Flipt provisioning evidence](../experiments/swe_bench_pro/v2_flipt_provisioning_2026-10-15.json)
records exact image/base identities, limits and hashes for the download and
probe artifacts. Only one image was pulled. No dependency installation,
repository tests, model calls, official verifier or NodeBB runs occurred.
Cumulative workspace evidence now covers one selected task in **eight
repositories**. Teleport and Proton Mail webclients still need local images;
NodeBB remains parked. These counts are not full-suite or official readiness.

Next: inspect Flipt's pinned public test configuration and select one bounded
check before running tests. Do not expand directly to its full integration
suite or start additional services without evidence that they are needed.

### Selected Flipt public check (not run)

Select `TestIs` in `internal/release/check_test.go`. Its six named subtests
cover two release versions, `dev`, a snapshot and two release-candidate
formats. They call the in-process `release.Is` regex checks; no server,
database, cloud storage or GitHub request is needed by those test bodies.
The remaining package code and tests still compile, so this is not proof
that its complete dependency graph is available offline.

The pinned CI enters through `mage dagger:run test:unit`. Its implementation
in `build/testing/test.go` uses race detection, one build worker and atomic
coverage, alongside several service containers for other packages. Preserve
those test flags while narrowing to this one public test:

```sh
go test -race -p 1 -coverprofile=/tmp/flipt-release-coverage.txt \
  -covermode=atomic -v -json -count=1 -timeout=60s \
  -run '^TestIs$' ./internal/release
```

The proposed wrapper should extract committed source into `/tmp/work`, keep
the original `go.work` and local module layout, use the image's read-only
module cache, and write a fresh build cache and coverage under `/tmp`.
Keep one CPU, 4 GiB memory/scratch and a 180-second complete-command cap,
including compilation. Disable dependency and automatic toolchain downloads;
install nothing and change no tests. Do not launch Dagger or service
containers for this selected service-independent check.

Retain native Go JSON events and require all six child tests, the `TestIs`
parent and package completion to pass. Do not count the parent as another
independent case, or accept a parent-only or exit-only result. No Go CTRF
reporter was found on the inspected PATH, so the wrapper must verify native
events rather than assume an installed reporter. Report this as diagnostic
evidence, not an implicitly registered framework-wide reporting adapter.

The image supplies Go 1.24.3. The workflow variable says 1.21, while `go.mod`
and `go.work` require 1.22.0 with a go1.22.2 toolchain directive. Preserve and
declare that mismatch: this is an image-native smoke, not historical CI
parity. The [selection record](../experiments/swe_bench_pro/v2_flipt_release_selection_2026-10-15.json)
pins source hashes, all six expected names, proposed environment and limits.
No tests, collection, compilation or dependency installation ran during
selection. Official readiness is unchanged; NodeBB remains parked.

Next: implement a small wrapper and run this selected test with native
individual-event verification. Retain any setup failure without expanding
to a full-suite debugging campaign.

### Flipt release-version smoke result

`tools/run_flipt_release_smoke.py` ran only the selected `TestIs` test on
15 October 2026. **All six child cases passed**, followed by the passing
parent and successful package completion. The command exited 0 in **44.95
seconds**, including preparation and fresh compilation. Race detection,
one build worker, atomic coverage, the 60-second Go test timeout and the
180-second complete-command cap were preserved. No additional services,
dependency installs or repository test changes were needed.

The wrapper verifies image HEAD, extracts the committed source and preserves
the original Go workspace/module layout. Dependencies remain read-only;
build outputs use fresh writable scratch, not copied precompiled artifacts.
The image root stays read-only, offline, capability-dropped and bounded by
the selected CPU/memory/scratch limits. The disposable container was removed
normally. The declared toolchain difference remains unchanged.

Native events are saved as `go-native.jsonl` and the coverage profile as
`coverage.txt`. The diagnostic parser requires the six exact child run/pass
pairs, the parent run/pass and package start/pass, rejecting skips, failures,
missing cases, unexpected tests/packages, duplicate outcomes and malformed
events. The shell preserves Go's exit status independently of printing the
saved events. This is explicit diagnostic reporting, not a newly registered
framework-wide report adapter. The retained coverage is **4.3% of package
statements**, consistent with selecting only the version-classification test;
it is not evidence of broad package coverage.

See the [Flipt smoke evidence](../experiments/swe_bench_pro/v2_flipt_release_smoke_2026-10-15.json)
for all six individual outcomes, the parent/package verification and artifact
hashes. All **81 focused checks** for reporting, integrity, provisioning and
the neighboring smoke wrappers passed. No model call, official verifier or
NodeBB run occurred, and official readiness is unchanged. This remains a
selected public smoke, not full-package or full-suite readiness.

Next: extend workspace coverage to Teleport using its already reviewed image
(3.50 GB compressed), then reuse the cheap probe before choosing a public
test. Proton Mail webclients is the other remaining unprovisioned repository;
do not pull both images as an unbounded batch.

### Teleport provisioning follow-up

The selected Teleport image contains 21 layers totalling 3,500,070,075
compressed bytes (3.50 GB). The helper was given the previously reviewed
manifest digest
`sha256:576147fc4357d7a6b4a6a347477e9a95f5e7fd01b277f25284589356350717e9`
via `--expected-manifest`; the public manifest still matches that pin.
Host free space was 177,770,639,360 bytes before the pull, above the existing
reserve. Only this one image is in scope; no cleanup or cache-supplement
build is requested. All twelve provisioning/batch checks passed before
execution.

The single pull attempt reached the existing **1,200-second download cap**
and raised `subprocess.TimeoutExpired`. Docker's subsequent exact-digest
inspection reported no registered image. The helper therefore never tagged
the image or started a workspace probe. The saved pull log contains seven
completed-layer lines and additional downloaded layers; these are partial
download evidence, not a provisioned image. No partial Docker layers were
deleted, no cleanup or retry ran, and no repository tests were started.

The [Teleport provisioning evidence](../experiments/swe_bench_pro/v2_teleport_provisioning_2026-10-15.json)
records the verified preflight, exact cap, incomplete pull log hashes and
failed local-image inspection. This is an image-provisioning timeout, not a
Teleport test failure or a demonstrated framework defect. The available
logs do not distinguish slow transfer from slow extraction sufficiently to
claim a root cause. No dependency installation, model call, official verifier
or NodeBB run occurred. Cumulative selected-task workspace coverage remains
**eight repositories**; Teleport and Proton Mail webclients remain unprovisioned.

Next: review one explicitly bounded retry of this same immutable digest,
allowing Docker to reuse any retained layers, with a new evidence directory
and the same download cap. Do not extend the timeout, clear Docker's cache
or claim workspace readiness without a successful probe. No retry has started.

### Teleport same-limit retry

One retry was explicitly authorized after the capped first attempt. It uses
the same reviewed manifest digest, the same 1,200-second download cap and a
new artifact directory. Docker's existing layers were retained; its retry
log explicitly reports cached layers as `Already exists`. No cleanup,
cache rebuild or timeout extension was performed. Host free space was
175,137,083,392 bytes at the retry preflight, above the existing reserve.
The first-attempt evidence remains unchanged.

On resuming on 16 October, the saved retry contained nine `Already exists`
layer lines but no completed-image result. Exact-digest inspection still
reported no local image. The original pull client and helper were still
running, approximately **498.9 wall-clock minutes** after preflight. The
configured subprocess timeout had not ended the process across that overnight
interval. This is **not** evidence of an uninterrupted 20-minute retry; the
cause of the timeout's behavior across that interval has not been established.

After verifying PID 24128's command line was the exact authorized digest
pull, only that Docker client was stopped to enforce the wall-clock boundary.
The helper exited with the resulting nonzero client status. Docker's daemon,
cached layers and other containers were untouched. A subsequent image
inspection still found no registered image. The workspace probe did not run,
no public tests or installs ran, and no further retry was started.

See the [retry evidence](../experiments/swe_bench_pro/v2_teleport_provisioning_retry_2026-10-16.json)
for cache-reuse lines, artifact hashes, configured versus observed elapsed
time and the terminal image check. Selected-task workspace coverage remains
eight repositories, with Teleport and Proton Mail webclients unprovisioned;
NodeBB remains parked and official readiness is unchanged.

Next: inspect the incomplete download and wall-clock timeout behavior before
requesting any further retry. Do not treat this overnight-interrupted attempt
as a clean resource diagnostic or silently start another download.

### Teleport diagnosis: sleep-aware timeout, incomplete large transfers

Read-only investigation on 16 October established the overnight explanation.
Windows' Power-Troubleshooter event records sleep from **17:23:29 on 15
October to 01:39:36 on 16 October** (Europe/Paris). Kernel-Power records the
sleep reason as Button or Lid. The retry started around 17:22, so almost the
entire overnight interval was low-power time, not active downloading.

The installed Python Windows wait implementation calls `WaitForSingleObject`
with the requested milliseconds. Microsoft's
[primary API documentation](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-waitforsingleobject)
states that this timeout excludes low-power time on Windows 8 and newer.
Thus `subprocess.run(timeout=1200)` was not a sleep-inclusive wall-clock
deadline. Docker's retry request log reports 3m20.88s, consistent with a short
awake interval rather than eight hours of active transfer. This resolves
the earlier uncertainty about overnight persistence without claiming an
uninterrupted retry or a Python deadlock.

Both attempts had the same two content blobs unfinished: `160ff38caab0…`
(1,316,505,754 compressed bytes) and `ac7254a7cbee…` (1,091,763,652 bytes).
At each client cancellation, containerd logged canceled content writes for
those blobs. Those errors followed cancellation; they are not independent
evidence of corrupt files, extraction failures or a full disk. The first
awake attempt genuinely did not finish within its cap. Its logs do not
establish whether the limiting factor was transfer, storage throughput or
another Docker/registry issue. Calling it a proven download deadlock would
overstate the evidence.

Two 15-second-capped public range requests then fetched only the first 64 KiB
of each blob, without saving payloads. Both returned HTTP 206 in under one
second with the expected total blob sizes. Current blob availability is
therefore confirmed; full-download speed and Docker VM network behavior are
not. No new image pull, test, install, Docker restart, power-setting change
or cache deletion occurred. See the
[diagnostic evidence](../experiments/swe_bench_pro/v2_teleport_download_diagnosis_2026-10-16.json)
for event timestamps, log locations, timeout implementation and range results.

Before another retry, the recommended change is an explicit wall-clock
deadline checked in short waits (so expiration is detected promptly after
resume), with durable progress evidence for the two large transfers. Run on
an uninterrupted awake host; do not silently change system power settings or
extend the existing cap. This diagnosis implements no code fix and starts no
retry. Teleport remains unprovisioned and readiness is unchanged.

### Sleep-inclusive deadline and progress journal

`tools/pull_deadline.py` now replaces the provisioning helper's single long
Windows wait. The pull cap remains **1,200 seconds**. The helper waits in
at-most-one-second increments and checks elapsed epoch time on each pass,
so time asleep counts. It also checks monotonic elapsed time to prevent a
backward wall-clock adjustment from extending an expired run. A forward
clock adjustment can end a run early; it does not grant additional time.

No process can enforce a deadline while the host is asleep. On resume, the
short wait ends and the next check kills and reaps only the pull client if
expired. A completion first observed after expiry is conservatively rejected
as a timeout, because its actual completion time is unknown. No daemon,
cache or power-policy change is part of this implementation.

Each new output directory retains `pull.progress.jsonl`: a start record,
five-second heartbeats, remaining time, observed layer states and log-growth
events, plus a terminal record. `pull.status.json` records success, failure,
deadline expiry or interruption, including spawn failure. Original stdout
and stderr remain separate. The journal explicitly labels log byte counts
as **log bytes, not downloaded blob bytes**. Docker's noninteractive CLI does
not provide continuous blob-byte progress here, so no transfer speed or
download percentage is inferred. Files are flushed after journal entries;
this provides saved process evidence, not a claim of power-loss durability.

Tests cover simulated sleep, backward clock changes, successful cached-layer
reporting, failed exits, interruption, spawn failure and a real harmless
local Python child killed at a 0.15-second deadline. No Docker pull is used
by these tests. The [implementation check record](../experiments/swe_bench_pro/v2_pull_deadline_checks_2026-10-16.json)
declares the semantics and limits. Teleport remains unprovisioned; no new
pull, workspace probe or public test has started.
All **19 focused deadline/provisioning/batch checks passed**.

Next: one same-digest, same-cap retry is reasonable once the user can keep
the host awake for the complete attempt. Preserve caches and use a new
output directory. The deadline guard makes resumed runs bounded; it does
not make a sleeping host an uninterrupted diagnostic. Do not change power
settings or start another retry implicitly.

### Teleport retry with the sleep-inclusive deadline: passed

One same-digest retry on 16 October completed successfully. The pull took
**1,147.93 seconds (19 minutes 8 seconds)**, within the unchanged 1,200-second
cap. The verified Linux/amd64 image was registered and retained with its task
tag. No additional pull or timeout extension occurred.

The new journal records the two previously incomplete blobs finishing their
downloads at about 1,009.85 seconds (`ac7254a7cbee…`) and 1,070.51 seconds
(`160ff38caab0…`). Their installation completions followed before the deadline.
Heartbeats remained continuous, with a maximum gap of **5.14 seconds** between
recorded heartbeats. The terminal status is `pass` with client exit 0. This
provides an observed bounded run rather than another overnight-interrupted
attempt; it does not imply that every prior slowdown has been diagnosed.

No cache was cleared. Docker reported one `Already exists` layer event in
this run; cache reuse is recorded as observed, not assumed from the earlier
partial downloads. System power settings and Docker configuration were not
changed. The progress journal still reports layer states and log bytes, not
continuous network-byte throughput.

The unchanged cheap workspace probe then passed in **8.60 seconds**. Image
HEAD matched `4d7c51b4f535cecfd139625e6af1746c46abc712`; committed source
extracted into disposable scratch, accepted a temporary write and contained
no Git directory. Existing offline, read-only-root, capability, no-host-mount,
one-CPU, task-memory, 4-GiB scratch and 120-second probe protections remained
unchanged. The disposable probe container was removed normally. No repository
code, dependency install or tests ran.

See the [successful deadline retry evidence](../experiments/swe_bench_pro/v2_teleport_deadline_retry_2026-10-16.json)
for exact image identities, terminal pull status, heartbeat summary, large-layer
events, probe results and hashes for all retained artifacts. Earlier failure
and interrupted-retry records remain intact. Cumulative selected-task
workspace coverage is now **nine repositories**. Proton Mail webclients is
the only remaining unprovisioned non-parked repository; NodeBB remains parked.
These counts do not establish full-suite or task-specific correctness, and
official readiness is unchanged.

Next: inspect Teleport's pinned public test configuration and select one
bounded service-independent check. Do not jump to its full integration suite.

### Selected Teleport public check (not run)

Select `TestCachedParser` in `lib/utils/typical/cached_parser_test.go`. This
is **one named Go test**, not hundreds of individually reported cases. Its
assertion loops fill the default 1,000-entry parser cache, verify that reuse
does not grow it, check bounded eviction and confirm eviction-log thresholds.
It uses in-memory expressions and the repository's own test logger, with no
server, database, network request or timing-dependent sleep.

Docker was stopped during selection. The inspected source came directly from
the public repository at the exact pinned base commit, rather than a guessed
current branch. Installed Go version, module-cache location and dependency
availability must still be checked in the image before execution; no container
or test was started here.

The public Makefile's `test-go-unit` target uses coverage, native Go JSON,
race detection and shuffled execution. Keep these while selecting one test:

```sh
go test -race -shuffle=on -cover -json -v -count=1 -p 1 -timeout=60s \
  -run '^TestCachedParser$' ./lib/utils/typical
```

The proposed complete-command cap is 180 seconds, including extraction and
fresh compilation, with one CPU and the existing 4-GiB memory/scratch
protections. Use extracted source, read-only image dependencies, writable
`/tmp` caches and no dependency or toolchain downloads. Leave
`TELEPORT_EXPRESSION_CACHE_SIZE` unset so the test sees its repository default.
Retain native JSON and require exactly this test and its package to complete
successfully; assertion-loop iterations are not independent result rows.

This is a direct package smoke, not the full Makefile preparation chain or
native-feature-tagged CI run. The selected package's five Go files have no
build constraints or `TestMain`, but other test files still compile:
`parser_test.go` imports the broader `lib/utils` package. Do not delete those
files to shrink the compilation graph. Actual dependency resolution and
transitive initialization remain unverified. The module declares Go 1.21;
do not assume the image's toolchain matches without inspecting it.

The [selection record](../experiments/swe_bench_pro/v2_teleport_cached_parser_selection_2026-10-16.json)
contains source URLs, exact byte hashes, proposed limits and setup caveats.
No tests, collection, compilation or installs ran. Official readiness remains
unchanged and NodeBB remains parked.

Next: with Docker running, inspect the installed toolchain/module cache,
implement a small wrapper and run only this public test with individual
report verification. Retain any setup error rather than expanding into the
full integration suite.

### Teleport cached-parser smoke result

Docker Desktop was started in the background as requested. Inspection of the
pinned image confirmed Go **1.23.1**, `/go/pkg/mod`, an available C compiler
and source hashes matching the public selection record. The module declares
Go 1.21; this toolchain difference is retained rather than claiming historical
CI parity.

`tools/run_teleport_cached_parser_smoke.py` then ran only `TestCachedParser`.
The named test and its package both **passed**. The complete command took
**97.73 seconds**, including committed-source extraction and fresh compilation,
within the 180-second cap. The test itself reported 0.04 seconds. Race
detection, shuffle, coverage, one build worker and the 60-second test-binary
timeout were preserved. The shuffle seed is retained in native output.

All package files, including the other tests and example, remained available
for normal compilation. Only the selected test executed. Its internal cache
loops are not reported as additional test cases. The cache-size override was
unset, preserving the repository's default, and source/build scratch was
writable only under `/tmp`. Dependencies stayed read-only, and no package,
toolchain or service installation occurred. No test source or configuration
was edited. Existing offline, read-only-root, capability and resource
protections were unchanged; the disposable container was removed normally.

The wrapper saves native Go events as `go-native.jsonl` and atomic coverage
as `coverage.txt`. Its diagnostic parser requires exactly this named test to
run/pass and the package to start/complete successfully, rejecting missing,
extra, skipped, failed, duplicate or malformed outcomes. It preserves Go's
exit code independently of printing saved events. Coverage was **17.3% of
package statements**, a selected-test result rather than broad suite coverage.
This is a standalone diagnostic, not a registered framework report adapter.

The [Teleport smoke evidence](../experiments/swe_bench_pro/v2_teleport_cached_parser_smoke_2026-10-16.json)
retains the individual outcome, exact command/toolchain, coverage and artifact
hashes. All **93 focused checks** for reporting, pull deadlines and
provisioning passed. No full suite, official verifier, model call or NodeBB
run occurred, and official readiness remains unchanged.

Next: assess Proton Mail webclients' remaining verified image against current
disk and download limits before provisioning it. No further Teleport suite
expansion is needed for this repository-coverage pilot.

### Proton Mail remaining-image assessment (no pull)

On 16 October, inspect-only verification confirmed the previously reviewed
Proton Mail webclients index and Linux/amd64 manifest still match their pins.
The selected image has **18 layers totalling 6,518,064,990 compressed bytes**
(6.52 GB / 6.07 GiB), below the helper's 8-GiB compressed-image cap. Neither
the exact digest nor the selected task tag is installed locally.

Host free space was **159,602,200,576 bytes** (159.6 GB / 148.6 GiB). The
helper requires the larger of 20 GiB and four times the compressed total:
**26,072,259,960 bytes** (26.1 GB / 24.3 GiB) here. The disk policy therefore
passes comfortably. Docker's data VHD is also on C:, so this host volume is
relevant to its growth. These are reserve heuristics, not measurements of the
image's final unpacked size. No cleanup is needed to meet this policy, and
Docker's reported reclaimable images are not authorization to delete
benchmark images needed later.

The download cap remains **1,200 seconds**, enforced by the sleep-inclusive
deadline and progress journal. Its success is less certain than disk capacity:
the image contains two large compressed blobs of **2,638,433,164** and
**2,630,852,592 bytes**, plus a 952,907,708-byte blob. Teleport's 3.50-GB pull
finished in 1,147.93 seconds. Scaling that total duration by manifest size
gives about **2,137.75 seconds (35.63 minutes)**. This is a rough comparison,
not an ETA or a measured Proton Mail network rate; caching, transfer
concurrency, extraction and current connectivity can change the result.
With no cached payload, even ignoring installation overhead, 6.52 GB in
20 minutes requires an average **5.43 MB/s** of payload transfer.

Three manifest entries match Teleport's reviewed image, totalling only 96
compressed bytes. This limited comparison does not inspect Docker's entire
content cache or prove that no other image shares useful layers. Likewise,
the full compressed total must not be labelled the incremental download size.

The [assessment evidence](../experiments/swe_bench_pro/v2_protonmail_assessment_2026-10-16.json)
records exact digests, layer sizes, current free space, policy calculations
and manifest hashes. No image pull, container, install, test, configuration
change or cleanup ran. Proton Mail remains the only unprovisioned non-parked
repository; official readiness is unchanged and NodeBB remains parked.

Next: assess a small byte-capped transfer diagnostic before choosing a full
pull. A single attempt is allowed by the size/disk policy, but finishing under
20 minutes is not yet supported by evidence. Do not silently raise the cap
or launch repeated pulls to make this assessment look successful.
