# Can a repository index prevent missing source?

The offline prototype exposes the declarations we checked in Koota, Dasel and
Narwhals. It does not establish that the model will select the right files or
solve those tasks. No model calls or benchmark tests were made for this check,
and the production controller still uses its existing workflow.

There are two separate pieces:

1. **A declaration index for file localization.** Each supported source file is
   listed with its recognized declarations and their line ranges. For example,
   Koota's `entity-methods-patch.ts` lists `Number.prototype.changed`. A model
   would see that name before choosing files, rather than having to infer the
   implementation's location from filenames alone. Function bodies are omitted.
2. **Import expansion after file selection.** Starting from saved file choices,
   the controller follows known outgoing imports until no new files are found.
   There is no hop or file-count cutoff. Each added file has a recorded import
   that led to it. This happens in code, with no follow-up model decisions.

The first piece is an index of symbols. The second is currently a graph of
**files**, linked by imports. It is not a graph that resolves every call to a
particular implementation. That distinction matters for dynamic APIs and for
how much context the graph brings in.

## What we measured

These are development examples already inspected during the pilot, not new
evaluation tasks. The index uses their public base revisions. Expansion uses
the files in their saved `coarse-context.json` records. The expected missing
declarations are checked afterward; they are not used as retrieval seeds.

| Repository | Source files indexed | Declarations | Index tokens | File prompt with index |
| --- | ---: | ---: | ---: | ---: |
| Koota | 325 | 880 | 14,248 | 16,571 |
| Dasel | 116 | 639 | 7,801 | 8,852 |
| Narwhals | 201 | 4,698 | 58,305 | 59,962 |

The last column includes the public issue, source tree, declaration index and
current file-selection instructions. The comparable tree-only reconstructions
are 2,323, 1,051 and 1,657 tokens respectively. These reconstruct the inputs with
current defaults; they are not measurements of the exact historical requests.
Counts use `o200k_base` and are estimates, not provider-reported usage.

| Repository | Saved files → import closure | Closure index tokens | All source in closure, tokens |
| --- | ---: | ---: | ---: |
| Koota | 10 → 44 | 3,551 | 34,706 |
| Dasel | 3 → 14 | 1,681 | 13,145 |
| Narwhals | 5 → 153 | 55,133 | 436,057 |

The full-source column measures concatenated source with file headers. It is
not a proposed repair prompt, and does not widen editable regions. In Narwhals,
the import closure reaches 153 of the 201 indexed files. Blindly including every
dependency body would therefore be a substantial context increase.

### Koota: a concrete import connects the missing implementation

The saved ten-file selection included `packages/core/src/entity/entity.ts`.
Its line 12 imports `./entity-methods-patch` for its side effects. Following that
import reaches the file defining `Number.prototype.changed` at lines 41–43.
Line 3 also imports `trait/trait.ts`, exposing `addTrait` at lines 132–174.
Both names appear in the repository index, and both files enter expansion
without using the issue's wording to guess a dependency.

### Dasel: the files were already selected

`NewReaderFn` and `NewWriterFn` appear in the index at `parsing/reader.go:25` and
`parsing/writer.go:34`. Those files were already selected in the earlier run.
Dasel's problem was losing those declarations when the controller narrowed
repair context, not missing their files at file localization. An index alone
does not fix that later loss; the existing
[declaration-retention work](interface-context-review.md) addresses it.

### Narwhals: visibility improves, but import expansion is broad

The index exposes `SQLExpr.rolling_sum` in `narwhals/_sql/expr.py` and
`PolarsSeries.rolling_mean` in `narwhals/_polars/series.py`. Neither file was in
the saved five-file selection. Both are reached by import expansion.

One recorded route to the SQL implementation is:

```text
_arrow/series.py
  → dependencies.py
  → _spark_like/dataframe.py
  → _sql/dataframe.py
  → _sql/expr.py
```

The analysis includes imports inside functions and `TYPE_CHECKING` blocks.
Such imports are useful source relationships even when they do not execute in
a particular run. They also explain why expansion can pull in many backends.
This route demonstrates visibility, not that every imported file is needed for
the requested repair.

## What the prototype guarantees, and what it leaves open

For identical input bytes, the index and expansion have stable ordering and
identical hashes. They do not silently truncate names or stop at a lookup limit.
Each added file has an import witness, and unresolved or ambiguous imports are
retained in the graph report. A repeated pass over all three repositories
produced identical index, prompt and source-closure hashes.

Validation passed 135 focused index, structure, language-adapter and Python
parity tests, including a dirty-checkout check and a dynamic-dispatch example
that the import graph deliberately cannot resolve.

That does **not** guarantee all needed source. A function may call
`getattr(backend, "rolling")` without importing its implementation. The full
index can list that implementation's declaration, but the import graph cannot
prove the connection. Even a complete list of names cannot guarantee that the
model recognizes the right one. A focused test preserves this counterexample.

Scope is explicit:

- The existing language adapters decide which paths count as source and tests.
  Excluded paths are recorded outside the rendered model input. This is not an
  inventory of every file in the repository.
- Declarations come from the current Python, Go, JavaScript, TypeScript and Rust
  representations. Python module assignments are added for this prototype,
  including assignments inside conditional blocks. Local variables, computed
  declarations and every possible language construct are not covered.
- Python imports use repository-root or `src/` module paths; JS/TS imports use
  relative paths, index files and common `.js`-to-`.ts` source paths. Go uses
  pinned `go.mod` paths and includes other source files in the same directory.
  These are syntactic candidates, not a simulation of each runtime resolver.
- Go build tags, JS package/TypeScript path aliases, Python import hooks and
  arbitrary dynamic imports are not resolved. Rust declarations are indexed,
  but its imports are explicitly marked as unsupported for expansion.
- Parse errors retain a file entry and a visible warning. There were none in
  these three inputs. Unresolved imports remain: the expanded Koota, Dasel and
  Narwhals sets contain 0, 21 and 911 unresolved/dynamic/ambiguous links. Many
  refer to external libraries. These counts are not counts of missing repairs.

The runner reads regular Git blobs at the supplied full base commit, ignoring
working-tree edits and untracked files. Symlinks and submodules are recorded
and not followed. It reads the public issue and saved file selection; it never
executes repository code or opens benchmark scoring material.

## Where this leaves the design

The compact repository index is worth showing Professor Zhang as a proposed
file-localization variant: it makes real missing names visible at a measurable
cost while preserving predetermined stages. We have not measured whether a
model uses that information successfully.

The unbounded import closure is useful diagnostic evidence. The Narwhals result
is a reason to avoid adopting full dependency bodies automatically. A future
symbol-level graph could narrow that set, but it would require more resolution
work and would still have to expose uncertainty around dynamic relationships.
The current prototype should not be described as that finished resolver.

No production stage, default, sample count, edit permission, model setting or
existing score changed. Any live variant should have its context rule agreed
before evaluating fresh tasks.

## Reproducing the check

The library is in
[`source_index.py`](../src/agentless_ml/localization/source_index.py), with
[focused tests](../tests/test_source_index.py). Run
[`inspect_source_index.py`](../tools/inspect_source_index.py) from the repository
root with the installed project environment. It requires local pinned sources
and the saved run; it does not download them.

For example, in PowerShell:

```powershell
python tools/inspect_source_index.py `
  --repository ../benchmarks/deepswe/repos/koota-pair-relation-tracking `
  --base-commit 9c434858b2b522002f8c5eb4a554fa8836a7cf3c `
  --recorded-run artifacts/agentless-koota-pair-files-10-2026-11-11/koota-pair-relation-tracking/runs/run-16264300128c415182e68a4ff498e6a3 `
  --issue ../benchmarks/deepswe/corpus/tasks/koota-pair-relation-tracking/instruction.md `
  --output artifacts/offline-source-index-2026-11-18/koota-pair-relation-tracking `
  --expect-declaration packages/core/src/entity/entity-methods-patch.ts::Number.prototype.changed
```

The [case manifest](../experiments/deepswe/source-index-prototype-2026-11-18/cases.json)
records the arguments for all three checks. Large indexes, augmented prompts,
graph reports and expansion witnesses stay under the recorded local artifact
paths. Compact summaries and hashes are committed in the same evidence folder.
