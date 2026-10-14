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
