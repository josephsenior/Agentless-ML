# SWE-bench Pro V2 provisioning survey

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

Next, restore Docker, prepare the four sealed task checkouts and execute their
reviewed plans. Broader readiness still requires reviewing full public schedules
and provisioning tasks beyond those four development checks.
