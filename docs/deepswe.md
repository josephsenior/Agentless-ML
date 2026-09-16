# DeepSWE integration

DeepSWE provides 113 tasks across Go (34), Python (34), TypeScript (35),
JavaScript (5) and Rust (5), pinned at `datacurve-ai/deep-swe`
`0b9fabbb63b9104d678fe965e1632f2dd9eaa2ea`. It is the only target benchmark
that covers all five workflow languages; SWE-bench Pro has no Rust tasks.

The adapter turns a task directory into a `TaskSpec`. It does not run tasks, pull
images, or score results.

## Trust boundary

A DeepSWE task directory uses the Harbor format and mixes agent inputs with
held-out answers:

```text
task.toml          agent-visible metadata (plus a [verifier] table with no answers)
instruction.md     agent-visible task description
environment/       Dockerfile that reproduces the prebuilt agent image
tests/             HELD OUT: hidden tests, test.patch, fail-to-pass test IDs, grader
solution/          HELD OUT: reference patch
```

`project_deepswe_task` opens exactly `task.toml` and `instruction.md`, by name.
It never lists, opens or hashes anything under `tests/` or `solution/`. A test
replaces Python's `open` with a guard that fails on any path in those
directories; on the full pinned corpus the loader opens 452 files (two visible
files, 113 tasks, read once for the pin check and once for projection) and none
under `tests/` or `solution/`. Breaking the adapter to read `tests/config.json`
makes that test fail immediately.

The projected record has exactly these fields; `load_deepswe_task` rejects any
other key, so a record built from a wider read fails instead of leaking:

```text
task_id  language  repository_url  base_commit
instruction  docker_image  agent_timeout_seconds  memory_megabytes
```

`task.toml` is parsed whole because TOML cannot be read partially. Its tables are
checked against the eight reviewed tables of schema 1.3 (`schema_version`,
`artifacts`, `task`, `metadata`, `verifier`, `agent`, `environment`,
`solution`). An unknown table, such as a future one holding answer material,
stops loading until someone reviews it. A different `schema_version` stops
loading for the same reason.

The loader also refuses tasks whose agent needs network access or a non-Linux
environment, because the Docker runner provides neither. All 113 pinned tasks are
`no-network` Linux tasks.

## Pinning the corpus

`experiments/deepswe/corpus_pin.json` records the dataset revision, the task
count, and a SHA-256 over the agent-visible files of every task. Loading fails if
a task was added, removed, or had its instruction or metadata edited. Because the
digest covers only visible files, checking it never reads held-out material.
Windows line endings are converted to `\n` before hashing, so a clone with
`core.autocrlf=true` produces the same digest as a Linux clone.

## Abbreviated base commits

Three tasks record an abbreviated commit, consistently in their `task.toml`,
environment Dockerfile and verifier collect command:

| Task | Recorded | Pinned full commit |
|---|---|---|
| `eicrud-keyset-pagination-cursor` | `68dafce` | `68dafce500a85227b996d8fcab466d7a0c88809e` |
| `koota-entity-snapshot-rollback` | `72ebef44b8e024d877250f055eea60cdfaa4506` (39 characters) | `72ebef44b8e024d877250f055eea60cdfaa45069` |
| `langchain-request-coalescing` | `7cef35b` | `7cef35bfdebd22148a4c62a10bf01f1fde36e722` |

Candidate workspaces check out a full commit ID, because a prefix could match a
second commit later. The adapter therefore accepts an abbreviated commit only
together with a pinned full commit that starts with it; without one it raises an
error naming the task. The full commits above were resolved through the GitHub
commits API and are stored in the corpus pin.

## Normalized problem statement

Every DeepSWE instruction ends with the same line:

```text
IMPORTANT: Please work on this in a new branch from main and commit everything when you are done.
```

Harbor collects an agent's work by extracting its commits. Agentless-ML never
commits: the controller builds and exports the selected patch itself. The adapter
removes exactly that final line and nothing else, because every prompt includes
the problem statement and the model cannot act on the instruction. This is a
model-visible change. It must apply identically to every experimental condition
built from the same `TaskSpec`.

## What is not implemented

- **Source repositories.** Candidate workspaces need a local clone of each task's
  repository. An upstream clone contains commits made after the base commit, which
  may include the real fix. DeepSWE's own Dockerfiles delete that future history;
  a local preparation step must do the same before a clone is used.
- **Execution.** No DeepSWE task has been run. Each image is about 8 GB on public
  ECR and must be pulled and pinned by digest first.
- **Public validation schedules.** No regression inventory or reproduction
  specification exists for any DeepSWE task.
- **Scoring.** The official verifier (Pier/Harbor, run in a separate pristine
  container) is not integrated. It must only ever run after final selection.

## Evidence

[Adapter tests](../tests/test_deepswe_adapter.py) cover the real vendored task
`abs-module-cache-flags` (its `task.toml` and `instruction.md` only), held-out
access, rejected fields, unreviewed tables, schema versions, network and language
checks, abbreviated commits, pin changes, line-ending stability and task
selection. Set `AGENTLESS_DEEPSWE_TASKS` to a local `deep-swe/tasks` directory at
the pinned revision to also load all 113 tasks.
