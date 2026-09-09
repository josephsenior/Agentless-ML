# Go support

Go is the first non-Python language connected to the recorded controller. A task
with `language="go"` now uses Go file filtering, skeletons and location resolution,
then the same repair parser, patch application, validation schedule and selector
as Python. There are no model calls in this milestone.

## What the adapter represents

`GoAdapter` uses Tree-sitter to read source without compiling or running the
repository. The parser and Go grammar versions are locked in `uv.lock`.

| Go declaration | Representation | Example location |
|---|---|---|
| Function | `function` | `function: Add` |
| Receiver method | Separate `method`, qualified by receiver type | `method: Counter.Add` |
| Struct or interface | `struct` or `interface` | `type: Counter` |
| Other defined type or alias | `type` | `type: ID` |
| Interface method | Child `method` inside the interface's source span | `method: Reader.Read` |
| Package variable or constant | `variable` or `constant` | `variable: DefaultLimit`, `constant: MaxSize` |

Methods stay where Go declares them. A method can be in a different file from its
receiver type, so putting it inside the type's source span would be incorrect.
`Counter.Add` names a method on either `Counter` or `*Counter`; generic receiver
arguments are omitted from the name but retained in its signature. Selecting
`type: Counter` selects that declaration, not its separately declared methods.

Bare method names are accepted only when unambiguous within the selected file.
Exact `line: N` locations are also accepted, with bounds checked against that file.
Every symbol uses one-based, inclusive source lines.

## Parsing and context choices

Tree-sitter has Python bindings and a Go grammar, which lets this adapter run
without requiring a Go toolchain. Go's standard parser was another option, but
would need a helper executable and a separate build/distribution step. We chose
Tree-sitter for this milestone; it is a syntax parser, not a Go type checker.
Sources with syntax errors or missing parser tokens fail explicitly.

The skeleton retains package/import declarations, types, variables, constants and
comments. Function and receiver-method bodies become `{ ... }`. Replacement uses
parser byte spans, so braces in strings and comments do not confuse it and UTF-8
text is preserved. The skeleton is prompt text; it is not compilable source.
Function literals inside package initializers are currently retained.

Unlike the Python prompt, the Go prompt names types and receiver methods explicitly.
The repair instructions use a Go example. Python keeps its existing templates and
fixture comparisons. These are model-visible differences, recorded here rather than
treated as identical prompts.

The file tree includes `.go` files, omits `_test.go`, and excludes `vendor`,
`testdata`, and paths with dot/underscore-prefixed components. Tracked test files
remain available for validation; the current file-location parser can also accept
an explicitly named tracked `_test.go` file. Build tags and OS/architecture suffixes
are not evaluated. This is a source view, not a reconstruction of a Go build.

## What was checked

- [Adapter tests](../tests/test_go_adapter.py) cover declaration kinds, generic
  pointer receivers, interfaces, aliases, grouped declarations, source spans,
  Unicode/CRLF skeletons, syntax failures, ambiguous methods, paths and prompts.
- [Workflow tests](../tests/test_go_workflow.py) take recorded file/symbol responses
  and three repair samples through the shared controller. One is malformed; two
  modify existing files. Independent Git checkouts receive the patches, validation
  distinguishes them, and the selected prediction is exported with zero model calls.
- An optional test runs `go test ./...` on that same small, authored fixture. It
  checks the weaker repair fails its assertion and the correct repair passes.
  This native test runner exists only in the test module. It is not an execution
  backend for arbitrary repositories or a benchmark result.

Run the usual suite with `uv run pytest`. To also run the compiler check with a
locally installed Go toolchain (1.20 or newer), use PowerShell:

```powershell
$env:AGENTLESS_GO_TESTS = '1'
uv run pytest tests/test_go_workflow.py -q
```

The compiler test disables dependency and toolchain downloads and uses its own
cache. The normal suite does not need Go installed.

## Remaining work

There is no package-wide name resolution, type checking, build-tag selection or
dependency analysis. Struct fields are visible in type declarations but are not
separate localization targets. Assignment compression is unsupported. Repeated
declarations such as multiple `init` functions need line locations when ambiguous.
The existing file-creation/deletion limits still apply to repairs.

This milestone does not add automated test selection, reproduction-test generation,
live model sampling or official Go benchmark evaluation. Those gaps remain listed
in the [replication map](replication-map.md). JavaScript/TypeScript now also has
controlled recorded coverage, as does [Rust](rust-adapter.md). The adapter contract can still change.

Parser references: [Python bindings](https://github.com/tree-sitter/py-tree-sitter)
and [Go grammar](https://github.com/tree-sitter/tree-sitter-go).
