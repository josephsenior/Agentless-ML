# Declaration names during file localization

File localization now receives the repository tree **and a declaration index**
by default. This is a context extension to the Agentless method, adopted on
18 November 2026 after the [offline census](source-context-census.md). The
[first fresh live check](clack-declaration-index-run.md) selected both expected
Clack files; its patch passed 81/82 issue checks and remains unresolved.

For example, a file can now appear with:

```text
packages/core/src/entity/entity-methods-patch.ts [typescript; ... lines]
  41-43 function Number.prototype.changed
```

The model can recognize a relevant declaration before choosing its files. The
index contains names, kinds and line ranges, not function bodies. Existing
adapters supply functions, classes, methods, types and other supported
declarations. Python module assignments are added without changing its legacy
structure representation. Parameters, local variables and computed declarations
are not a complete part of this inventory.

The controller reads regular tracked files from a fresh checkout of the pinned
base revision. Existing source/test filters apply. It uses each file's own
language adapter, including mixed JavaScript/TypeScript repositories. Source
working-tree changes, untracked files, symlinks and submodule targets do not
supply declaration context.

There is no import graph, dependency expansion or extra model inspection phase.
The model still returns at most ten file paths, followed by the existing symbol
and edit localization stages. Seeing a declaration does not authorize editing
its file; the later selected intervals still control repairs.

The index has no independent token cap and does not silently truncate names.
Live runs with the configured once-only context budget check the complete
request before calling the provider. That existing budget applies to the
augmented prompt; this change does not introduce a new allowance or a fallback
that removes declarations. Provider context-window limits still apply as well.

Every run records:

- `file-localization-index.txt`: the exact index, saved before the file request.
- `file-localization-index.json`: policy `declaration-index-v1`, pinned commit
  and tree, declaration/file counts, SHA-256, estimated index and whole-prompt
  tokens using `o200k_base`, and diagnostics.
- `controller.json`: `file_localization_context: declaration-index-v1`.

Parse failures retain a file entry and a warning. Unreadable UTF-8 files stay
visible in the source tree and receive an explicit index warning. Those files
do not acquire invented declaration names. The index therefore means all names
the current parsers recognize, not a guarantee of complete semantic coverage.
If later selected source cannot be parsed, the existing workflow failure rules
still apply.

The census and earlier experiments retain their original inputs and scores.
The offline census used the prototype renderer, whose explanatory headings
differ slightly from this production prompt. Its numbers remain historical
estimates; current runs record their actual rendered prompt estimate separately.

Why begin here? A declaration index directly addresses the need to infer a
file's contents from its name. It avoids import-resolution assumptions and
keeps the fixed stages intact. A full map can be expensive; capping a map can
omit needed connections. Both alternatives remain offline diagnostics. An
extra review phase would be a separate workflow decision.

The [source-visibility recheck](../experiments/deepswe/declaration-index-default-2026-11-18.json)
retains all six inspected declarations in Koota, Dasel and Narwhals under the
production renderer. Controller checks passed 76 tests with five optional
execution checks skipped; the focused structure, prompt and budget checks passed
125 tests. These groups overlap. No model calls or benchmark scoring were used.
