# SWE-bench Pro V2 provisioning survey

Current engineering direction: [batch inventory and bounded cross-repository
pilot](batch-v2-provisioning.md). NodeBB is parked with its complete, labelled
diagnostic evidence; its three existing failures remain recorded. No further
NodeBB run or official/default readiness promotion is planned here.

The [repository-by-repository expansion](v2-public-suite-expansion.md) records
the complete public targets being reviewed beyond the original four smoke plans.

`tools/survey_swe_bench_pro_v2.py` inventories all 642 pinned V2 tasks. It uses
the existing answer-free loader and a reviewed public-plan registry. Execution
requires explicit task IDs, so an inventory command cannot accidentally start
hundreds of containers or downloads.

The first four plans reuse the existing qutebrowser, Vuls, NodeBB and Tutanota
development configurations. Three check syntax/compilation; Vuls runs a selected
public test. Those scopes are retained. Passing one produces `smoke_checked`,
never `public_suite_ready`.

## Evidence collected

An execution checks the immutable local image ID, verifies `/app` is at the
task's pinned commit, verifies a sealed source repository, creates a fresh
candidate workspace and runs the reviewed public command through the shared
Docker runner. The image probe is offline, read-only and drops capabilities;
it is removed even after a timeout. The public command uses the existing
one-CPU, 4-GiB scratch smoke profile and task-declared memory.

Each task record says whether the image, workspace and command were actually
checked. Execution logs and workspace provenance are retained. A completed
`full_public_suite` plan needs an individual-test report and at least one
passing test before it becomes ready; failing baseline tests remain visible.
Image, source, workspace and runtime failures have separate statuses.

The command does not fetch repositories or pull images. It expects sealed
checkouts at `<repositories>/<instance_id>`. Existing shared V2 development
clones are not assumed to be sealed and should not be relabelled as such.
Use the repository preparation facilities to create separate pinned checkouts;
do not remove history or remotes from an existing user checkout in place.

Neither the plans nor the survey use benchmark `tests/` or `solution/` files.
Scoring is still a separate post-selection command. A source-plan digest and
the corpus/registry digests accompany the evidence so later command changes
can be distinguished from earlier results.

## Commands

Inventory only:

```powershell
.venv/Scripts/python.exe tools/survey_swe_bench_pro_v2.py --v1-parquet ../benchmarks/swe-bench-pro/dataset/data/test-00000-of-00001.parquet --v2-tasks ../benchmarks/swe-bench-pro-v2/v2/tasks --output ../output/swe-bench-pro-v2-readiness/inventory-new
```

To check reviewed tasks, add `--execute`, repeat `--task-id <instance_id>` for
each selected task, and supply `--repositories` and `--workspace-root`. Use a
new output directory for each survey. The output contains a flushed per-task
`survey.jsonl`, `summary.json`, and any actual command artifacts.

Add a new task by reviewing its public base configuration and recording its
immutable image, base commit, command, scope and report contract in a public
experiment specification. Register that specification in
[`v2_public_plans.json`](../experiments/swe_bench_pro/v2_public_plans.json).
Do not derive public commands from hidden verifier files, copy a passing command
from an unrelated repository, or declare a full suite without reviewing coverage.

## Initial inventory: 13 October 2026

The pinned corpus loaded all 642 tasks: 638 have status `needs_public_plan`,
and the four explicitly selected development checks have status
`docker_unavailable`. Docker's Linux engine was stopped. No image, workspace
or public command was checked; no model calls or verifier runs occurred.
The 638 tasks are unreviewed, not observed provisioning failures.

Local evidence is in
`../output/swe-bench-pro-v2-readiness/2026-10-13-initial/summary.json`
and the adjacent `survey.jsonl` (relative to the repository root). Earlier
recorded workflow runs remain historical evidence, not fresh survey executions.

The subsequent replay below clears this Docker blocker for the four configured
checks. Broader readiness still requires reviewing full public schedules and
provisioning tasks beyond those four development checks.

## Source preparation for the Docker replay

After Docker was started on 13 October, all four pinned images were available
locally. The existing development sources were partial clones. Attempting to
seal a separate qutebrowser copy failed during Git repacking because an object
was missing; the temporary failed copy was removed by the preparation helper.
The original development repositories were left unchanged.

For this replay, new sources were fetched from the four public upstream
repositories at exactly the configured base commits with `--depth=1 --no-tags`.
Each was then cloned and sealed under
`../benchmarks/swe-bench-pro-v2/repos/<instance_id>`. The sealed checkouts have
the complete base source tree, no remote, and no later commits. They are shallow:
earlier commit history is absent. This preparation is sufficient to attempt the
four source-based smoke commands; it does not establish equivalence for future
history-dependent public suites. The adjacent `.sealed.json` records preserve
base tree IDs and preparation provenance.

## Completed offline replay

All four unchanged checks passed in fresh candidate workspaces on 13 October:
qutebrowser's Python compilation check, Vuls's selected
`TestSplitAptCachePolicy`, NodeBB's JavaScript syntax check and Tutanota's two
TypeScript module parse checks. Each record confirms the pinned image/base,
sealed repository, workspace creation and actual public-command execution.
The existing one-CPU, task-memory, scratch, timeout and offline protections
were unchanged. No model calls or held-out verifier runs occurred.

The resulting inventory is **4 `smoke_checked`, 638 `needs_public_plan`**.
None of these four plans establishes full public-suite readiness. See the
[checked-in evidence and artifact hashes](../experiments/swe_bench_pro/v2_provisioning_replay_2026-10-13.json).
The full local journal and execution artifacts are under
`../output/swe-bench-pro-v2-readiness/2026-10-13-docker/`.
The 28 focused survey, sealing, adapter and scoring-boundary tests also passed.

Next, review a complete public schedule for one repository, including its test
setup and individual-result reporting, and verify it on the unchanged base.
Then expand by repository; passing syntax checks alone does not change research
eligibility.
