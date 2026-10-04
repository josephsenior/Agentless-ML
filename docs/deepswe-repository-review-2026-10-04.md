# DeepSWE repository blockers — 4 October 2026

The 22 `unsupported_repository` records are stale as workspace rejections.
All 22 sealed repositories pass the current pinned-tree and workspace-provider
checks. That is not a new passing benchmark baseline: readiness stays at
**80/113** until their public tests are actually rerun with faithful checkouts.

The three `repository_failed` tasks have no local repository in the current
`benchmarks/deepswe/repos` directory. Nothing was recloned, repaired, deleted or
fetched during this review. No model was called.

## What the old category was hiding

The old provider refused any Git symlink or submodule. The current provider
already allows regular-file edits while leaving those entries untouched.
Symlinks are excluded from patch targets, their names remain reserved, and
uninitialized submodules cannot be patched through. The old survey results
were not rerun after those changes.

There is still a separate runtime problem. All 187 tracked symlink entries in
these task checkouts are ordinary files on this Windows host. Their contents
are the link target, not the target file's contents. The Docker snapshot copies
ordinary files as files and rejects actual host symlinks. Neither behavior
currently reconstructs this Git metadata as Linux links.

Copying target contents instead would also be wrong: directory links, chains,
deliberately broken links and links to `/dev/null` have observable behavior.
Their presence does not mean the repository itself is broken.

## The 22 tasks, grouped by next action

| Group | Tasks | What to do next |
|---|---|---|
| Direct internal file links | arktype, clack, effect, kgateway, pest, python-statemachine, query | Preserve Git link metadata in the Linux snapshot, then rerun baselines |
| Internal directory links, sometimes alongside file links | pebble, pwntools, sqlfmt, task, valibot | Same snapshot work, with directory-link tests |
| Link chains | participle, scc | Preserve each link, with cycle/escape checks; direct-target classification alone is insufficient |
| Dangling links | goreleaser, optique | Preserve intentional dangling behavior; do not silently remove or replace links |
| Absolute or drive-style test fixtures | both Helm tasks | Review the container-only safety policy for `/dev/null`, missing absolute targets and a Windows-style target before enabling these |
| Submodules only | adaptix, tomlkit, wasmi, wazero | Inspect whether the public schedule actually needs submodule contents before considering initialization |

These groups cover 18 symlink-only tasks and four submodule-only tasks; none
contains both kinds. The 187 links include 148 direct file targets, 22 directory
targets, seven links to other links, two missing targets and eight absolute or
drive-style targets. Counts are per task: the two Helm tasks share a base tree,
so their five links are counted twice.

The four submodule-only tasks have six Git entries between them:

- Adaptix: `benchmarks/release_data`.
- Tomlkit: `tests/toml-test`.
- Wasmi: `crates/wasmi/benches/rust`, `crates/wast/tests/spec` and
  `crates/wast/tests/wasmi`.
- Wazero: `site/themes/hello-friend`.

Wazero is the smallest first rerun: its only special entry is a website theme,
not a Go source directory. That suggests its public Go suite may not need the
submodule, but only a real baseline can establish readiness. Tomlkit and Wasmi
have test-related submodules, so we cannot assume those are irrelevant or fetch
their current upstream revisions instead of the exact recorded commits.

## The three preparation failures

| Task | Recorded failure | Safe next action |
|---|---|---|
| drizzle-orm-window-function-builders | Dangling `refs/remotes/origin/HEAD` broke seal verification | Fresh preparation using the current symbolic-ref cleanup; verify the complete seal |
| langchain-request-coalescing | Git clone aborted with an existing-ref transaction bug | Retry a fresh staged clone outside the editor-visible benchmark folder; keep the Git failure explicit if it recurs |
| meriyah-explicit-resource-declarations | References retained commits outside the base history | Fresh preparation with the current ref allow-list and object pruning; do not relax the verifier |

The current code already has symbolic-ref cleanup, a ref allow-list, pruning,
fetch locks and external staging. That gives a reason to retry, not proof that
all three issues are fixed. No attempt was made to salvage an old partial
clone, and no later history was inspected.

## Evidence and limits

[The snapshot](../experiments/deepswe/repository_review_2026_10_04.json) records
all 25 task IDs, base commits, previous errors, current preflight results, Git
modes, link target blobs and host representations. Targets were read using
`git cat-file`, never followed on the host. The audit classifies direct targets
only; it does not certify whole link chains as safe.

[The audit tool](../tools/triage_deepswe_repositories.py) verifies existing seals
and constructs a workspace provider without creating a candidate checkout.
It never clones, initializes submodules, runs repository code, calls Docker or
updates survey statuses. `--output` writes only generated audit evidence:

```powershell
.\.venv\Scripts\python.exe tools/triage_deepswe_repositories.py `
  --survey ../output/deepswe-survey/survey.jsonl `
  --repositories ../benchmarks/deepswe/repos `
  --output experiments/deepswe/repository_review_2026_10_04.json
```

[Audit tests](../tests/test_repository_triage.py) check path containment,
latest-record selection, unchanged surveys, rejected seals, direct-target
classification and the distinction between preflight and readiness.

The full package suite passed with 571 tests and 15 opt-in checks skipped.
Two additional output-location guards were checked with the audit tests after
that run; all 27 audit-specific cases pass.

## Recommended next step

Rerun Wazero's public baseline first, using the existing workspace behavior.
Then implement Git-metadata-aware Linux snapshots for internal relative links,
with tests for Windows placeholders, directory links, chains and dangling
targets. Keep links out of source context and patch targets, never dereference
them on the host, and keep the Helm fixture policy explicit. Reprepare the
three missing repositories separately rather than changing benchmark pins.

Follow-up: [Git-aware Linux snapshots](git-aware-linux-snapshots-2026-10-04.md)
implement the contained-link policy and validate it on a real Python task.
The counts above retain this preflight checkpoint.
