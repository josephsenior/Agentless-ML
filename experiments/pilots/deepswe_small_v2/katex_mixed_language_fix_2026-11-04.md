# KaTeX source visibility and per-file language handling

In the November 4 pilot, KaTeX stopped at file localization. The pinned task
record labels the repository JavaScript. The controller used that label to
choose one parser for the entire task, then used that parser to filter the
file tree. This left out existing TypeScript sources such as
`src/environments/array.ts` and `src/parseNode.ts`.

The saved response named `katex-multicolumn-array-spans/src/environments/array.js`.
The prompt showed the task name as the tree root and asked for the full path,
so the prefix was understandable. The parser already strips that exact root
prefix. It rejected the remaining `src/environments/array.js` because the path
does not exist at the pinned commit. The missing TypeScript paths in the
prompt were the underlying visibility bug.

## Design decision

Build the tree from tracked, supported source paths across the repository.
Keep the existing source and test filters and ask for paths relative to the
repository root. Choose the parser and code block label for each selected
path. If a selection mixes languages, keep a single symbol-localization
response and a single SEARCH/REPLACE patch per repair candidate. Normalize
each changed source file with its own language when building the voting key.

This keeps the published task label as metadata and applies the same rule
across repositories. It avoids hand-identifying which files KaTeX needs for
this issue. The model still has to localize them from the tree. The shared
checkout, public schedule, edit authorization, and pilot budgets stay in
force. The broader source inventory can change model input and token usage,
so the original pilot result remains recorded under its original revision.

## Offline verification

The shared-task launcher replayed recorded responses against KaTeX base
`89bede495dc2c85e1c57ba627a18526f71d57396` and the registered Docker image.
One candidate changed comments in both `cli.js` and
`src/environments/array.ts`. The unchanged public schedule passed
**1,252/1,252** on the base and on the candidate. The controller selected
`repair-0` and exported both paths in one prediction with zero model calls.
This verifies mixed-language routing through patch export. The comment edits
were a diagnostic, and no held-out score was collected.

The mixed JS/TS controller test also covers per-file prompt fences and
edit-line localization. Local replay inputs and outputs are under
`artifacts/katex-mixed-language-replay-2026-11-04`.
