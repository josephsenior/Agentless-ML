# Rust support

Rust now uses the same recorded controller as Python, Go and JavaScript/TypeScript.
This is a language-support checkpoint, not a benchmark result or a claim that the
whole Agentless implementation is finished.

## What the adapter reads

The adapter accepts `.rs` files, excluding hidden paths, `target` and `vendor`.
Integration tests and benches are hidden from the project tree. Inline test
modules remain in their source file: filtering them would require interpreting
attributes and could remove useful context.

Tree-sitter supplies source spans for functions, structs, enums, traits, impl
blocks, modules, aliases, constants, statics and named fields. Inline modules
contain their declarations; external `mod name;` declarations do not pull in
another file. Function bodies become `{ ... }` in skeletons. Attributes and
Unicode source are retained. Syntax errors fail explicitly.

We use the [Rust grammar](https://github.com/tree-sitter/tree-sitter-rust), with
its version pinned in the lockfile. This keeps parsing independent of a compiler
installation. A compiler-backed representation could resolve types and macros,
but would also require a working project configuration. That is not necessary
for this first source-local representation.

## Naming and ownership

An inherent method is `Counter::add`; a trait implementation method is
`<Counter as Reset>::reset`. Trait declarations use `Reset::reset`. Inline modules
add their prefix, such as `helpers::add`. Generic arguments keep their source
spelling: `Box<T>::get` rather than an inferred concrete type.

Methods are children of their actual impl block, not of the struct declaration.
The latter would imply a source span that includes separately located code.
Use `type: Counter` to select a struct, `impl: Counter` for an inherent impl,
or `method: Counter::add` for one method. Multiple impl blocks can share a name;
ambiguous requests are left unresolved rather than picking one arbitrarily.
Use a method name or `line: N` in that case.

## Limits

This is syntax parsing, not semantic analysis. We do not expand macros, evaluate
`cfg` conditions, run build scripts, resolve imports, or follow module paths.
Macros stay visible in skeletons but their generated declarations are not indexed.
Locals, closures and positional tuple fields are not separate localization targets.
Use line locations for these cases. Assignment compression is unsupported and
fails explicitly. The shared repair layer still edits existing files only.

## Evidence

[Adapter tests](../tests/test_rust_adapter.py) cover names, attributes, spans,
ambiguous methods, module prefixes, generics, Unicode, skeletons and path filters.
[Workflow tests](../tests/test_rust_workflow.py) exercise two files through recorded
localization, repair parsing, isolated workspaces, validation, selection and export.
The malformed candidate is rejected; the wrong repair fails; the correct one passes.
The original checkout remains unchanged and there are zero model calls.

Ordinary tests use a controlled source-checking runner. Set `AGENTLESS_RUST_TESTS=1`
to compile and execute the authored fixture with the installed `rustc`. That
optional check uses no Cargo dependencies and is not a production execution backend,
a Docker validation test or official benchmark scoring.

The initial five languages now have recorded coverage. Remaining method behavior
is tracked in the [replication map](replication-map.md); live model integration
and full benchmark runs remain later work.
