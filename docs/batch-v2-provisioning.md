# V2 batch provisioning

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

## Current coverage: 17 October 2026

The repository pilot has workspace evidence for one selected task from each of
nine non-parked repositories. These are selected-revision checks, not coverage
of every task in those repositories.

| Repository | Selected public check |
| --- | --- |
| Vuls | Reviewed Go test |
| Qutebrowser | Python syntax smoke |
| Tutanota | TypeScript syntax/compilation smoke |
| Element Web | Five Jest assertions |
| Ansible | Six unit tests |
| Navidrome | Six Ginkgo number specs |
| Open Library | Nine query-utility tests, with verified Infogami |
| Flipt | Six release-version child cases |
| Teleport | One cached-parser test |

NodeBB remains parked with its complete diagnostic and three retained failures.
Proton Mail webclients remains unprovisioned. Its manifest and disk assessment
passed, and the capped range requests worked; the full image has not been pulled.

The [run log](history/v2-provisioning-log.md) retains the original selections,
source hashes, commands, failures, successful results and their evidence links.

## Provisioning limits

The one-image helper currently allows at most 8 GiB compressed and requires
host free space of at least the larger of 20 GiB and four times the compressed
total. These are reserve heuristics; they do not measure final unpacked size.
It pins the reviewed Linux/amd64 manifest and verifies local image identity
before tagging or probing.

The implemented pull cap is still **1,200 seconds**, with sleep-inclusive
deadline checks and a progress journal. The proposed 90-minute allowance for
Proton Mail has not been implemented or used. The small Windows-host range
samples are not sustained Docker throughput measurements.

Use `--inspect-only` for manifest/preflight evidence without pulling layers.
For an actual reviewed image, use `--expected-manifest` to require its exact
leaf digest. `--reuse-downloaded` is for a fully installed image, not an
incomplete prior pull. See [the tools guide](../tools/README.md) for entry points.

## Next work

Use already prepared development tasks for the live-model and budget-accounting
milestone. Expand provisioning and complete public schedules for the selected
experiment as needed; the 642-task inventory is not a claim that all tasks
are ready. Preserve the parked NodeBB evidence and review any further image
download separately.
