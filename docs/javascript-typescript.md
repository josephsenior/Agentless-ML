# JavaScript and TypeScript support

JavaScript and TypeScript now use the same recorded controller as Python and Go.
This milestone adds source parsing, localization, skeletons and repair examples.
The controller still receives saved responses and a supplied test schedule.

## Files and parser choice

`JavaScriptAdapter` accepts `.js`, `.jsx`, `.mjs` and `.cjs`. `TypeScriptAdapter`
accepts `.ts`, `.tsx`, `.mts` and `.cts`, plus JavaScript files for mixed repositories.
Declaration files such as `.d.ts` are included. Each file chooses its own grammar:
JavaScript (including JSX), TypeScript, or TSX.

This required two small changes to the adapter contract: an `extensions` tuple
for accepted files, and a `path` argument when rendering skeletons. The existing
`extension` is retained for examples in prompts. Choosing TSX solely from the task
language would misparse ordinary TypeScript angle-bracket assertions, so the file
path is needed here. Python and Go accept the extra argument without changing
their rendering behavior.

The tree omits `node_modules`, `vendor`, `dist`, `build`, `coverage` and hidden
directories. Test directories (`test`, `tests`, `__tests__`, `__mocks__`) and
`.test.*`/`.spec.*` files are hidden from the localization tree. As with Go, an
explicitly named tracked test file is still accepted by file localization.
These are fixed development filters. We do not read tsconfig, package scripts,
bundler configuration or ignore files to determine the build's actual inputs.

## How declarations are named

| Source construct | Symbol and example location |
|---|---|
| Named function, async function or generator | `function: fetchValue` |
| Variable bound directly to an arrow/function expression | `function: add` |
| Class declaration or variable bound to a class expression | `class: Counter` |
| Class method, constructor or callable field | `method: Counter.add` |
| Class field | `field: Counter.value` |
| Object bound to a variable | `variable: api`, with `method: api.run` for direct methods |
| Variable or constant | `variable: settings` or `constant: limit` |
| TypeScript interface, type alias or enum | `type: Options` |
| Interface method/property | `method: Reader.read` or `field: Reader.ready` |
| Anonymous default export | `function: default` or `class: default`, as applicable |
| Static CommonJS assignment | `function: exports.add` or `method: module.exports.api.run` |

Named default exports keep their declared name. Named export declarations are
unwrapped for parsing; export/import statements remain visible in skeletons.
Re-export lists do not create copies of declarations in another file. CommonJS
names describe the syntax of assignments; the adapter does not evaluate whether
`module` or `exports` has been rebound.

Bound functions use the variable's name because that is what callers see. For
example, `const f = function inner() { ... }` is localized as `function: f`.
Members use lexical ownership: a method's source lies inside its class or object.
Source spans remain one-based and inclusive, so the existing focused-context and
edit-application code can consume them.

If a name resolves to several declarations, localization rejects the ambiguity.
For example, a getter and setter can share `Counter.value`; overload signatures
can share a function name. Use `line: N` to identify the intended source in those
cases. Static and instance methods with identical names follow the same rule.

## Skeletons and trade-offs

We use the Tree-sitter JavaScript and TypeScript grammars, with versions recorded
in `uv.lock`. This reuses the parsing approach introduced for Go without requiring
Node or a TypeScript installation for ordinary framework tests. Babel or the
TypeScript compiler API would provide other useful analysis, but would require
a JavaScript runtime and a separate integration. Type checking and module
resolution are outside this adapter's current role.

Skeletons preserve imports, exports, declarations, comments and type annotations.
Function/method bodies become `{ ... }`; expression-bodied arrows become `...`.
Replacements use syntax-tree byte spans, including for Unicode source. Nested
bodies are not replaced twice. These skeletons are prompt text and need not compile.
The JavaScript/TypeScript localization prompt explains the supported names, and
the repair prompt uses a matching language example. Python's existing prompt
fixtures remain unchanged.

The adapter currently does not assign symbol names to destructured bindings,
computed keys, TypeScript namespace contents, nested local declarations, or
functions hidden behind wrappers such as a call to `memo`. Those constructs remain
in the source and can be selected by line. Function bodies may still be abbreviated
in their skeletons. Nested object values are visible but only direct members receive
qualified symbols. Assignment compression is unsupported. Parser errors fail
explicitly; successful parsing does not imply valid types or a working build.

## Checks performed

[Adapter tests](../tests/test_javascript_adapter.py) cover names and source spans,
class/object members, exports, generic types, syntax failures, ambiguity, mixed
file extensions, JSX/TSX, Unicode/CRLF handling, prompts and selected context.

[Recorded workflow tests](../tests/test_javascript_workflow.py) apply two-file
repairs to independent Git checkouts, reject a malformed response, distinguish a
weaker repair from the correct one, and export the selected patch. The TypeScript
fixture deliberately edits both a `.ts` and a `.js` file. No model is contacted.

The normal suite uses supplied outcomes for execution. An optional check runs
the small authored fixtures with local Node. It has no npm dependencies and does
not run a package installation or build script. With Node 22.6 or newer:

```powershell
$env:AGENTLESS_JS_TESTS = '1'
uv run pytest tests/test_javascript_workflow.py -q
```

The TypeScript check uses Node's `--experimental-strip-types`; it executes the
fixture after erasing supported types. It is not a `tsc` type-check or a benchmark
evaluation. The native runner lives only in the test module.

[Rust](rust-adapter.md) now also has recorded coverage. Automated test selection, reproduction-test
generation, model sampling and full benchmark integration remain separate
unfinished work in the [replication map](replication-map.md).

Parser references: [JavaScript grammar](https://github.com/tree-sitter/tree-sitter-javascript)
and [TypeScript/TSX grammars](https://github.com/tree-sitter/tree-sitter-typescript).
