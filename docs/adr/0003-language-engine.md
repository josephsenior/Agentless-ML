# ADR 0003: Collapse language adapters into a generic engine + per-language tables

- **Status:** Provisional — implementation plan, not yet built
- **Date:** 2026-09-12
- **Refines:** [ADR 0002](0002-language-adapter-boundary.md), which established the
  shared `LanguageAdapter` contract but let each language own a full hand-written
  adapter class. This ADR keeps the contract and replaces the four adapter bodies.

## Context

Zhang's 10 Sept feedback: "pls consider minimizing or even completely removing
language-specific adapters." (Received outside this Gmail account's recorded
thread with him — the last message in `19f95479e374e41c` is the 10 Aug meeting
invite. Confirm the exact sentence before quoting it back to him; "minimizing"
and "removing" are different instructions and the reply below hedges toward
the weaker one on purpose.)

His objection is not to multi-language support, it's to *how* it's built. Four
adapter classes that each hand-roll a tree-sitter walk is "multi-language by
accumulation of code," not language-agnostic — even though every adapter
implements the same `LanguageAdapter` Protocol from ADR 0002. Confirmed by
reading the current code:

| File | Lines | Shared machinery (would collapse) | Irreducible per-language logic |
|---|---|---|---|
| `go.py` | 165 | parse+validate scaffold, `_symbol` span/signature math, path filtering, skeleton body-replacement | `_receiver` (~11 lines), `_specs` grouped-decl flattening (~7 lines) |
| `rust.py` | 141 | same `_symbol`-shaped construction (inlined), same skeleton replacement | impl/trait naming incl. `<T as Trait>`, attribute-item folding into span |
| `javascript.py` | 264 | same construction pattern, same skeleton replacement (plus nested-function short-circuit, shared with the same idea in Go/Rust) | `_name` (member-expression folding, string-key stripping, `module.exports`/`exports.*`) |
| `python.py` | 277 | n/a — parity path, see below | n/a |

That's the ~700-shared / ~50-irreducible split from the working discussion.
`_symbol`/`_make_symbol` in Go and JS are structurally the same function with
one parameter difference (JS takes a separate `span` node for cases like
`export const foo` where the exported wrapper, not the declaration, is where
the signature should start); Rust inlines the identical logic with its own
`start` node for the same reason (attribute folding). One generic constructor
covers all three once it takes an optional span-start node.

## The interface the engine actually needs

The engine asks a fixed set of questions per node; each language answers them.
Both a table lookup and a hook return the same thing — a string (or `None`) —
so the engine cannot tell which produced it and must not care:

| Question | Go's answer | Rust's answer | Shape |
|---|---|---|---|
| what kind is this node type? | `"struct_item"` → `"struct"` | `"struct_item"` → `"struct"` | lookup (data) |
| what is this symbol's name? | read the `name` field | read the `name` field, or fold `impl`/trait | mostly lookup, sometimes hook |
| what is this symbol's qualified name? | `receiver.Method` via `_receiver` | `path::to::Item` via nesting | hook (Go, Rust's impl naming) / generic (nesting) |
| does this node's span start earlier than the node itself? | no | yes, at the first `attribute_item` | hook |

Test for which bucket a rule falls in, stated plainly so it's reusable for the
next language too: **can you read the answer off the page without running
anything?** `"struct_item" → "struct"` — yes, data. Go's receiver-to-name
resolution — no, something has to walk the tree first — code.

## Target layout

**Revised 2026-09-12** — see "Pushing further" below. `hooks.py` is dropped;
the ~50 "irreducible" lines turn out to reduce to tree-sitter query patterns
(alternation + text predicates), which are data, not code.

```
structure/
  contract.py   — the invariant below, as executable equality checks
  engine.py     — tree + LanguageTable + compiled query captures -> FileNode.
                  No language names. Owns: running each language's tags.scm,
                  turning captures into SymbolNode (span/signature math),
                  qualified-name templating, generic chain-flattening.
  skeleton.py   — generic body-replacement renderer
languages/
  go/table.toml, go/tags.scm
  rust/table.toml, rust/tags.scm
  javascript/table.toml, javascript/tags.scm
  typescript/table.toml, typescript/tags.scm
  base.py       — unchanged: still the LanguageAdapter Protocol the controller uses
parity/
  agentless_v15.py  — legacy_symbol_projection, the LibCST skeleton transformer,
                      and _compress_assignments, moved out verbatim. Regression
                      reference, not a workflow component.
```

`get_language_adapter()` keeps returning something satisfying `LanguageAdapter`
— for non-Python languages that becomes a thin `GenericAdapter(table, hooks)`
instance instead of a hand-written class. The controller-facing contract from
ADR 0002 does not change; only what sits behind it does.

## The invariant (contract.py)

What must be preserved is the workflow as the model experiences it, not
byte-identity:

- **Preserved:** which symbols exist, parent/child hierarchy, line spans, order.
- **Free to change:** exact signature text, skeleton body markers, whitespace.
- **Exception: Python.** Byte-identity to published Agentless v1.5.0 still
  applies — it's the external regression anchor, not a workflow property.

`contract.py` makes this executable, not just documented:

```python
def assert_structurally_equivalent(before: FileNode, after: FileNode) -> None:
    """Same symbol set, same hierarchy, same spans, same order. Text may differ."""
    assert _order(before) == _order(after)          # qualified_name sequence
    assert _spans(before) == _spans(after)           # (start_line, end_line) per symbol
    assert _shape(before) == _shape(after)           # parent/child tree shape
    # signature text and skeleton markers are deliberately not compared
```

This is what Go/Rust/JS/TS get diffed against after refactor. Python instead
gets the existing byte-diff on rendered localization prompts — a stricter
check, kept as-is.

## Go, mapped exactly (the requested first deliverable)

Of `go.py`'s 165 lines:

- **→ table (`languages/go.toml`), ~25 lines worth of current code:**
  `extension = ".go"`, `skip_dir_names = ["vendor", "testdata"]`,
  `skip_part_prefixes = [".", "_"]`, `test_path_rule = {suffix = "_test.go"}`,
  `requires_root_child = ["package_clause"]`,
  `kind_by_node_type = {function_declaration = "function", method_declaration = "method", struct_type = "struct", interface_type = "interface", var_declaration = "variable", const_declaration = "constant"}`,
  `container_member_kind = {method_elem = "method"}` (interface members),
  `qualifier_separator = "."`, `blank_identifier = "_"`.

- **→ engine (`structure/engine.py`), ~110 lines' worth of current logic,
  written once and shared by Go/Rust/JS/TS:**
  `_parse`'s syntax-error check and the `requires_root_child` check (generic,
  table-driven); `_text`; `_symbol`/`_make_symbol` (span math: `end_line =
  end_point.row + (1 if column else 0)`, signature slicing up to the body,
  optional span-start override) — this exact function appears three times
  today, verbatim in spirit; `is_source_path`/`is_test_path` evaluation
  against the table's skip-dirs/prefixes/test-path-rule; the "grouped
  declaration yields multiple named children" walk for var/const; the
  "container has member kinds, recurse with `parent.name`" walk used by Go's
  interface methods and reusable for JS class/object members; the skeleton
  body-replacement loop (find body-bearing nodes, replace bytes in reverse
  order) used identically by Go/Rust/JS today.

- **→ *originally* "stays as code," ~20 lines: `_receiver` and `_specs`.**
  Superseded by "Pushing further" below — both reduce to `tags.scm`
  alternation patterns once written as tree-sitter queries instead of
  hand-rolled `Node` traversal, so the true answer is 0 lines of Go-specific
  Python, not 20.

Net: **165 lines → ~25 lines' worth of `table.toml` + ~15 lines' worth of
`tags.scm` (data, not Python) + 0 language-specific engine code**, with the
~110 "engine" lines not counted against Go at all since they're written once
and amortized across all four languages.

## `is_test_path` — flagged, not silently unified

Today: Python matches any path part starting with `"test"`; Go matches the
`_test.go` suffix; JS matches `{test,tests,__tests__,__mocks__}` path parts or
a `.test`/`.spec` stem; Rust matches `{tests,benches}` path parts. Four
different rule *shapes*, not just different data for one algorithm.

Plan: define a small set of generic predicate primitives evaluated by the
engine — `{suffix = "..."}`, `{any_part_in = [...]}`, `{any_part_startswith =
"..."}`, `{stem_endswith = [...]}`, OR'd together — and give each language's
table the rule it already has, unchanged. This makes every language's rule
sit side-by-side as visible data instead of buried in four different
functions, without reclassifying a single file. Unifying the *rules
themselves* is a separate, explicit decision (raised below), not a side
effect of this refactor.

**Why this matters more than it looks:** `is_test_path` is consumed at
`localization/context.py:112`, where it filters which files appear in the
project tree rendered into the file-localization prompt. Reclassifying a file
therefore changes the text the model reads and the set of files it can choose
from — it is a workflow-level change, not a tidy-up. If the rules are ever
unified, that step needs its own before/after prompt diff on the fixture
corpus, not just a structural-equivalence check.

## Edge cases carried through explicitly (nothing here is allowed to be lost silently)

- Go grouped `var`/`const_spec_list` → `tags.scm` alternation, see above.
- Go `_test.go` / package-clause requirement / `root.has_error` → table + generic engine check.
- Rust attribute-item folding into span and signature start → `tags.scm` captures the leading `attribute_item` run; engine's `span_start` parameter consumes the capture.
- Rust `<T as Trait>` impl naming → `tags.scm` capture + generic templating rule in engine.py.
- JS `export_statement` span-widening, `ambient_declaration` unwrapping, CommonJS `module.exports`/`exports.*` → `tags.scm` captures (incl. `#match?` predicate) + engine's `span_start` parameter + generic chain-flattening rule.
- `is_test_path` divergence → table, explicitly flagged above, not unified yet.

## Rollout order (strangler, one language at a time)

0. **Spike the remaining UNVERIFIED claims above** (Rust impl naming, JS
   `module.exports` predicate, JS member-chain flattening) before committing
   to the query-based design for those languages. Two of the first three
   claims in this ADR were wrong when tested; assume the rest are too until
   run.
1. **Fixture capture (gate before any refactor code lands).** No golden
   snapshot of adapter *output* exists today — `tests/fixtures/go/structure.go`
   etc. are input sources used directly in unit tests, not captured `FileNode`
   JSON. Add `tools/capture_language_structure_fixture.py`: run each current
   adapter's `parse_file` and `render_skeleton` over its existing test fixture
   plus real open-source files per language (to exercise the edge cases above
   on code nobody hand-wrote for the test), dump `FileNode` as JSON per file.
   Commit these as the pre-refactor baseline.

   **Pin the corpus.** This project pins Docker images by digest, the
   SWE-bench Pro Parquet by SHA-256, and the upstream Agentless commit — a
   regression corpus held to a looser standard than the rest of the harness
   would be the weak link. Record an explicit repository URL + commit SHA per
   source file (or vendor the files into `tests/fixtures/` outright, which is
   simpler and makes the fixtures diffable in review).

   **Pin the grammars too.** Golden fixtures are only meaningful against a
   fixed `tree_sitter_go` / `tree_sitter_rust` / `tree_sitter_javascript` /
   `tree_sitter_typescript` version — the `const_spec_list` finding above is
   exactly how a grammar bump breaks a query file. Add the grammar package
   versions to the pinned-state table in the master implementation plan, and
   treat a grammar upgrade as an event that requires re-running the contract
   check, not a routine dependency bump.
2. **`contract.py` first**, tested against itself using the Python adapter's
   existing fixtures (no engine changes yet — this just proves the comparator
   is correct before anything depends on it).
3. **Go**, per the breakdown above: `engine.py` + `skeleton.py` +
   `languages/go/table.toml` + `languages/go/tags.scm`. Keep `go.py`'s current
   class importable under a private name; assert
   `assert_structurally_equivalent(old, new)` over every captured fixture
   plus the existing `test_go_adapter.py` cases. Delete the old
   implementation only once that's green, per file, not per PR.
4. **Rust**, same steps — expected to also validate the `span_start`
   generalization from Go (Go doesn't need it; Rust does).
5. **JavaScript/TypeScript** — largest of the three, and the one most likely
   to reveal a gap in the "container member" generic walk (class/object
   members, not just interface methods). Do this last of the three so the
   generic engine has already been exercised twice.
6. **Python — do not touch without Zhang's answer to the open question
   below.** The one mechanical, no-risk move available now regardless of his
   answer: relocate `legacy_symbol_projection`, the LibCST skeleton
   transformer, and `_compress_assignments` into `parity/agentless_v15.py` as
   a pure file move with import fixups — it's a regression reference, not a
   workflow component, and moving it doesn't touch behavior either way.
7. **`is_test_path` unification** — separate follow-up, only after flagging
   the reclassification explicitly (changelog entry + updated fixtures for
   whichever files newly cross the line), not bundled into 3–5.

## Pushing further: tree-sitter queries eliminate the remaining hooks

The first pass of this ADR put ~50 lines per language into `hooks.py` as
Python functions, on the grounds that they navigate-branch-retrieve rather
than look up. That's the right test, but it doesn't mean the result has to be
Python. Every hook identified above is, on inspection, pure tree-shape
matching — alternation over a small number of concrete grammar shapes, plus
at most string interpolation:

Each claim below is marked with its verification status. **VERIFIED** means a
query was compiled and run against the real grammar (spike, 2026-09-12);
**CORRECTED** means the first draft of this ADR was wrong and the entry
records what actually works; **UNVERIFIED** means it is still an assumption.

- **Go receiver — VERIFIED.** Alternation handles value, pointer, generic and
  pointer-to-generic receivers in one pattern, producing exactly the
  `Server.Start` / `Server.Stop` / `Box.Get` set that `_receiver` produces:
  ```scheme
  (method_declaration
    receiver: (parameter_list
      (parameter_declaration
        type: [ (type_identifier) @recv
                (pointer_type (type_identifier) @recv)
                (generic_type type: (type_identifier) @recv)
                (pointer_type (generic_type type: (type_identifier) @recv)) ]))
    name: (field_identifier) @name) @method
  ```
- **Go `_specs` — CORRECTED.** The first draft proposed
  `(const_declaration (const_spec_list (const_spec) @spec))`. There is no
  `const_spec_list` node in the Go grammar and that query fails to compile.
  The grammar is genuinely asymmetric: `var_declaration` wraps its specs in a
  `var_spec_list`, while `const_declaration` holds `const_spec` children
  directly. The current `_specs()` suffix heuristic papers over that
  asymmetry by accident. The query must name the real shapes:
  `(var_declaration [(var_spec_list (var_spec) @spec) (var_spec) @spec])` and
  `(const_declaration (const_spec) @spec)`. Note the upside: a wrong node
  type is a hard `QueryError` at load time, not a silent miss — but every
  query in this ADR must be derived from the grammar and executed, never
  written from memory.
- **Rust attribute folding — CORRECTED, and it is not a query at all.**
  The first draft claimed `(attribute_item)* @attr . (item) @sym` captures a
  leading attribute run. Tested: with `*` it captures nothing, with `+` it
  captures nothing, and only the single-attribute form
  `(attribute_item) @a . (function_item) @fn` matches — which then also
  misses every function that has no attributes. A variable-length run of
  preceding siblings is not expressible this way.
  **Replacement:** a generic engine primitive — after a symbol is captured,
  walk backwards over immediately-preceding siblings whose type appears in
  `span_extends_over_preceding`, and move `start_line`/signature start to the
  first one. That is a table entry (`span_extends_over_preceding =
  ["attribute_item"]` for Rust, `[]` elsewhere) plus shared engine code. It
  generalizes better than the query would have: Python and JS decorators
  need exactly the same primitive.
- **Rust impl/trait naming — UNVERIFIED.** Intended shape: capture `type` and
  optional `trait` fields, with `<{type} as {trait}>` produced by a generic
  templating rule driven by a per-kind `qualified_name_template` table entry.
  Spike before relying on it.
- **JS `module.exports`/`exports.*` — UNVERIFIED.** Tree-sitter supports
  `#match?` text predicates, but this specific pattern has not been run.
- **JS member-expression folding (`a.b.c`) — UNVERIFIED, and the highest
  remaining risk.** Intended as a generic chain-flattening primitive
  (`chain_node_type`, `chain_fields`, `separator`). Note the subtlety that
  makes this risky: qualified names are part of the preserved contract, not
  free-floating text, so any divergence here (whitespace or comments inside a
  member chain, computed keys, subscript vs member access) is a contract
  violation rather than a cosmetic difference. Spike this before committing
  to the approach for JS.

Net effect: `hooks.py` disappears. Each language becomes exactly two files —
`table.toml` (the pure lookups from the original plan) and `tags.scm` (a
tree-sitter query file — the same kind of file editors already ship for
syntax-aware code navigation) — both data, zero Python.

**The honest limit, so "no tradeoffs" doesn't overclaim:** this eliminates
per-language *code*, not per-language *facts*. A `tags.scm` is still a
per-language artifact, the same way `table.toml` already was — a system that
parses five different grammars cannot have zero language-specific knowledge
anywhere, only zero language-specific *procedures*. Two real, smaller costs:
tree-sitter query predicates can't express arbitrary computation (everything
currently in `hooks.py` fits within alternation + text-match, so this isn't
a live constraint today, only a ceiling if a future language needs real
computation to name a symbol); and `.scm` query syntax is a second format to
learn alongside TOML. Given Zhang's stated objection was to adapters as
hand-written code, not to the presence of per-language *data*, this should
clear his bar — but it's worth naming precisely what "no tradeoffs" bought,
rather than asserting zero cost.

## Scope and sequencing — the real tradeoff

The 10 Sept note reads in full: *"Thanks for the update, and overall the plan
looks great to me. Just a minor suggestion: pls consider minimizing or even
completely removing language-specific adapters."* That is a low-stakes aside
on an approved plan, not a blocking objection. The calendar says the same
thing: the internship runs Sept–Dec 2026, it is currently 12 Sept, and there
are still zero live-model runs and zero benchmark results. The research
contribution is the Grinta comparison, not the parser.

So there are two honest sizes for this work, and the choice between them is a
schedule decision rather than an architectural one:

- **Cut A — engine unification only (~2–3 days).** Collapse the three
  tree-sitter adapters onto one generic engine plus per-language tables,
  keeping the handful of navigate-branch-retrieve rules as small named
  functions. Roughly 570 lines of Go/Rust/JS become ~250. Fully defensible to
  Zhang as "one engine, no per-language adapters," because it is true.
- **Cut B — Cut A plus the `tags.scm` conversion (~1–2 weeks).** Removes the
  last per-language Python entirely. More elegant, and the strongest possible
  answer to "completely removing" — but the spike above shows the conversion
  is not uniform (Rust's attribute run does not convert at all, and three JS
  claims remain unverified), so the estimate carries real variance.

Recommendation: do Cut A now, keep the fixture corpus and contract layer from
this ADR (they are the durable part and are needed either way), and treat Cut
B as an optional follow-up to run only if the benchmark work is on schedule.
The invalidation argument for doing this before live runs is sound, but it
applies equally to Cut A, which captures most of the point at a fraction of
the calendar cost.

## Open questions for Zhang (do not decide unilaterally)

1. ~~Confirm the actual wording of the 10 Sept note.~~ **Resolved** — full
   text quoted above; it is a "minor suggestion," which supports the smaller
   Cut A scoping rather than an urgent rewrite.
2. Should Python's `parse_file` also route through the generic engine while
   keeping the parity skeleton renderer unchanged? Extraction and rendering
   are separable. **This does not need to block on an email** — it is
   testable locally: route Python extraction through the engine behind a
   flag and run the existing byte-diff parity check. If the rendered
   localization prompts stay byte-identical, the question answers itself and
   Zhang can simply be told the outcome. Only raise it with him if the parity
   check fails and the tradeoff becomes real.

## Consequences

Golden fixtures captured in step 1 become the permanent regression net for
all non-Python languages going forward, not just for this refactor — any
future grammar upgrade (tree-sitter version bumps) gets checked against them
too. The generic engine also becomes the natural place to add a fifth
language later: a table + a handful of hooks, no new adapter class.
